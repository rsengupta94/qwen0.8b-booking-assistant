"""Owns the workflow: states, transitions, session updates and all tool calls.

The model never decides a transition. Code calls an NLU function at the states
that need one, reads the fields it returns, and picks the next state.

NLU contract (Phase 2 supplies the real one; tests supply a stub):

    nlu(prompt_name, session, text, context) -> dict

`prompt_name` is a row from design.md section 4.1. `context` carries the facts
that call needs, such as the doctor shortlist or the offered slots.

Two kinds of state. Waiting states consume one user turn. Auto states run in
code inside the same turn until the session reaches the next waiting state.

step() returns reply *facts* for the next state, not text. Phase 3 NLG and
templates turn facts into a reply.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Callable

from app.nlg.clarify import QUESTIONS as QUESTION_TEXT  # code-owned question sentences, keyed like QUESTION_FOR_STATE
from app.session import Session
from app.tools import fixtures, mock_backend

NLU = Callable[[str, Session, str, dict], dict]

MAX_LOOPS = 3  # re-asks per state, and no-slot rounds at ASK_DAYS, before hand-off
MAX_CORRECTIONS = 3  # per session; past this the classifier is not called and turns are taken as answers
SLOTS_PER_OFFER = 3
# Doctor matching (design.md section 5). True: doctor_pick sees only doctors tagged with the category.
# False: full ranking over all doctors, category matches listed first so the validator fallback is still code's top candidate.
FILTER_SHORTLIST = True
# Re-ask reasons where the user did name something, so an FAQ detour makes no sense.
NO_DETOUR_REASONS = {"doctor_not_found", "doctor_ambiguous"}
# Deterministic gate before the off_script model call: only text shaped like a question qualifies.
QUESTION_WORDS = {"what", "when", "where", "which", "who", "why", "how", "do", "does", "did", "is", "are", "can", "could", "will", "would", "should"}
NEW_PATIENT_SESSION_TYPE = "first_consultation"  # set by code; ASK_SESSION_TYPE is for returning patients only

RELATIVE_DAYS = {"today": 0, "tomorrow": 1, "day_after_tomorrow": 2}
DAY_TERMS = list(RELATIVE_DAYS) + mock_backend.WEEKDAYS  # enum for extract_days.days[]


class State(StrEnum):
    GREET = "GREET"
    ASK_FIRST_CONSULT = "ASK_FIRST_CONSULT"
    ASK_PROBLEM = "ASK_PROBLEM"
    ASK_DOCTOR_PREF = "ASK_DOCTOR_PREF"
    CAPTURE_DOCTOR = "CAPTURE_DOCTOR"
    PICK_DOCTOR = "PICK_DOCTOR"
    ASK_PHONE = "ASK_PHONE"
    ASK_SESSION_TYPE = "ASK_SESSION_TYPE"
    ASK_DAYS = "ASK_DAYS"
    SHOW_SLOTS = "SHOW_SLOTS"
    CAPTURE_CHOICE = "CAPTURE_CHOICE"
    CONFIRM = "CONFIRM"
    END = "END"


# Question intent the bot asks when it lands on a waiting state.
QUESTION_FOR_STATE = {
    State.ASK_FIRST_CONSULT: "first_consult",
    State.ASK_PROBLEM: "problem",
    State.ASK_DOCTOR_PREF: "doctor_pref",
    State.ASK_PHONE: "phone",
    State.ASK_SESSION_TYPE: "session_type",
    State.ASK_DAYS: "days",
    State.CAPTURE_CHOICE: "slot_choice",  # only used by clarify; CAPTURE_CHOICE re-asks via present_slots
}


# Correction intent (design.md section 3): field -> the waiting state that owns it.
REWIND_MAP = {
    "problem": State.ASK_PROBLEM,
    "doctor": State.ASK_DOCTOR_PREF,
    "phone": State.ASK_PHONE,
    "session_type": State.ASK_SESSION_TYPE,
    "days": State.ASK_DAYS,
}

# Session fields cleared on rewind: the owned field plus everything downstream in workflow order.
CLEAR_ON_REWIND = {
    State.ASK_PROBLEM: ["problem", "category", "doctor_id", "days", "offered_slots", "chosen_slot"],
    State.ASK_DOCTOR_PREF: ["doctor_id", "days", "offered_slots", "chosen_slot"],
    State.ASK_PHONE: ["phone", "doctor_id", "session_type", "days", "offered_slots", "chosen_slot"],
    State.ASK_SESSION_TYPE: ["session_type", "days", "offered_slots", "chosen_slot"],
    State.ASK_DAYS: ["days", "offered_slots", "chosen_slot"],
}


@dataclass
class TurnResult:
    state: str
    reply: dict  # facts for NLG, always has "kind"
    nlu_output: dict | None
    correction: dict | None = None  # {"field", "rewound_to"} when this turn rewound


# --- helpers -----------------------------------------------------------------


def _advance(session: Session, new_state: State) -> None:
    """Leave the current state successfully: clear its re-ask count, move on."""
    session.loop_counts["reask"].pop(session.state, None)
    session.state = new_state


def _ask(session: Session, **extra) -> dict:
    return {"kind": "ask_question", "question": QUESTION_FOR_STATE[State(session.state)], **extra}


def _reask(session: Session, reason: str, text: str, nlu: NLU) -> dict:
    """Stay in the current state and ask again. Past MAX_LOOPS, hand off and end.

    Off-script (design.md section 6): before counting a re-ask, allow one detour per state. If
    off_script says the user asked a question, reply with the FAQ answer (matched in code) plus the
    pending question, and do not spend a re-ask.
    """
    detours = session.loop_counts["detour"]
    if (reason not in NO_DETOUR_REASONS and not detours.get(session.state)
            and getattr(nlu, "last_ok", True) and _looks_like_question(text)):
        out = nlu("off_script", session, text, {"question": QUESTION_TEXT[QUESTION_FOR_STATE[State(session.state)]]})
        if out.get("is_question"):
            detours[session.state] = True
            topic = out.get("topic")
            return {
                "kind": "clarify",
                "question": QUESTION_FOR_STATE[State(session.state)],
                "faq_answer": fixtures.faq_answer(topic),
                "topic": topic,
            }
    counts = session.loop_counts["reask"]
    counts[session.state] = counts.get(session.state, 0) + 1
    if counts[session.state] >= MAX_LOOPS:
        session.state = State.END
        return {"kind": "handoff", "reason": f"reask_limit:{reason}"}
    if session.state == State.CAPTURE_CHOICE:
        return _present_slots(session, reask=True, reason=reason)
    return _ask(session, reask=True, reason=reason)


def _present_slots(session: Session, **extra) -> dict:
    doctor = fixtures.doctor_by_id(session.doctor_id)
    return {"kind": "present_slots", "doctor_name": doctor["name"], "slots": list(session.offered_slots), **extra}


def _looks_like_question(text: str) -> bool:
    """Cheap shape check so requests like "please suggest one" never reach the off_script model call.
    The state NLU's own validator failure is also not a reason to look for a question (see nlu.last_ok)."""
    words = text.lower().split()
    return "?" in text or (bool(words) and words[0].strip(".,!") in QUESTION_WORDS)


def _resolve_doctor(name: str | None) -> tuple[dict | None, list[dict]]:
    """Match name tokens against doctor names, case-insensitive. Code, not model.

    Returns (doctor, candidates). Exactly one best match gives (doctor, [doctor]).
    A tie, e.g. "Dr Rao" with two Raos, gives (None, [both]). No match gives (None, []).
    """
    if not name:
        return None, []
    tokens = {t.strip(".,").lower() for t in name.split()} - {"dr", "doctor"}
    scored = []
    for d in fixtures.doctors():
        doc_tokens = {t.strip(".,").lower() for t in d["name"].split()}
        hits = len(tokens & doc_tokens)
        if hits:
            scored.append((hits, d))
    if not scored:
        return None, []
    best = max(h for h, _ in scored)
    candidates = [d for h, d in scored if h == best]
    return (candidates[0] if len(candidates) == 1 else None), candidates


def _resolve_days(terms: list[str]) -> list[date]:
    """Turn extract_days terms into concrete dates inside the booking horizon. Unknown terms are dropped.
    A weekday name gives every matching date in the horizon, nearest first, today included."""
    start = mock_backend.today()
    out: set[date] = set()
    for term in terms:
        term = term.lower()
        if term in RELATIVE_DAYS:
            out.add(start + timedelta(days=RELATIVE_DAYS[term]))
        elif term in mock_backend.WEEKDAYS:
            for offset in range(mock_backend.HORIZON_DAYS):
                d = start + timedelta(days=offset)
                if mock_backend.WEEKDAYS[d.weekday()] == term:
                    out.add(d)
    return sorted(out)


def _correctable_fields(session: Session) -> set[str]:
    """Fields the user answered earlier, so a correction can apply. Code-set values do not count."""
    out = set()
    if session.problem is not None:
        out.add("problem")
    if session.doctor_id is not None:
        out.add("doctor")
    if session.phone is not None:
        out.add("phone")
    if session.session_type in ("therapy", "followup"):
        out.add("session_type")
    if session.days:
        out.add("days")
    return out


def _rewind(session: Session, target: State) -> None:
    """Leave the current state, clear the target's field and everything downstream, land on target."""
    session.loop_counts["reask"].pop(session.state, None)
    for name in CLEAR_ON_REWIND[target]:
        default = [] if name in ("days", "offered_slots") else None
        setattr(session, name, default)
    session.state = target


def _shortlist(category: str | None) -> list[dict]:
    """Doctors whose tags include the category, code's top candidate first.

    FILTER_SHORTLIST on: only matches (all doctors when nothing matches). Off: matches first, then the rest.
    """
    matched = [d for d in fixtures.doctors() if category in d["categories"]]
    rest = [d for d in fixtures.doctors() if category not in d["categories"]]
    if FILTER_SHORTLIST:
        return matched or list(fixtures.doctors())
    return matched + rest


# --- waiting-state handlers: (session, text, nlu) -> (nlu_output, reply or None)


def _on_greet(session: Session, text: str, nlu: NLU):
    _advance(session, State.ASK_FIRST_CONSULT)
    return None, _ask(session, greeting=True)


def _on_first_consult(session: Session, text: str, nlu: NLU):
    out = nlu("yes_no", session, text, {})
    if out.get("intent") == "yes":
        session.patient_type = "new"
        session.session_type = NEW_PATIENT_SESSION_TYPE
        _advance(session, State.ASK_PROBLEM)
    elif out.get("intent") == "no":
        session.patient_type = "returning"
        _advance(session, State.ASK_PHONE)
    else:
        return out, _reask(session, "not_yes_no", text, nlu)
    return out, None


def _on_problem(session: Session, text: str, nlu: NLU):
    out = nlu("extract_problem", session, text, {"categories": fixtures.categories()})
    session.problem = out.get("summary") or text
    session.category = out.get("category")
    _advance(session, State.ASK_DOCTOR_PREF)
    return out, None


def _on_doctor_pref(session: Session, text: str, nlu: NLU):
    # Code first: if a roster name is in the text, the doctor is a fact and the model is not asked.
    # Otherwise the model chooses between you_decide and other; "named" is removed from its enum.
    doctor, candidates = _resolve_doctor(text)
    if doctor or candidates:
        out = {"mode": "named", "doctor_name": doctor["name"] if doctor else None, "source": "roster_match"}
    else:
        out = nlu("doctor_pref", session, text, {"name_in_text": False})
    mode = out.get("mode")
    if mode == "named":
        session.state = State.CAPTURE_DOCTOR
        if out.get("source") != "roster_match":
            doctor, candidates = _resolve_doctor(out.get("doctor_name"))
        if doctor is None:
            session.state = State.ASK_DOCTOR_PREF
            if candidates:
                reply = _reask(session, "doctor_ambiguous", text, nlu)
                reply["candidates"] = [d["name"] for d in candidates]
                return out, reply
            return out, _reask(session, "doctor_not_found", text, nlu)
        session.doctor_id = doctor["id"]
        session.loop_counts["reask"].pop(State.ASK_DOCTOR_PREF, None)
        session.state = State.ASK_DAYS
        return out, None
    if mode == "you_decide":
        _advance(session, State.PICK_DOCTOR)
        return out, None
    return out, _reask(session, "no_doctor_pref", text, nlu)


def _on_phone(session: Session, text: str, nlu: NLU):
    out = nlu("extract_phone", session, text, {})
    digits = out.get("digits") or ""
    if not digits:
        return out, _reask(session, "no_phone", text, nlu)
    session.phone = digits
    patient = mock_backend.fetch_patient(digits)
    if patient is None:
        # Unknown number: treat as a new patient and take the new-patient path.
        session.patient_type = "new"
        session.session_type = NEW_PATIENT_SESSION_TYPE
        _advance(session, State.ASK_PROBLEM)
        return out, _ask(session, phone_not_found=True)
    session.doctor_id = patient["doctor_id"]
    _advance(session, State.ASK_SESSION_TYPE)
    return out, None


def _on_session_type(session: Session, text: str, nlu: NLU):
    out = nlu("session_type", session, text, {})
    kind = out.get("type")
    if kind not in ("therapy", "followup"):
        return out, _reask(session, "not_session_type", text, nlu)
    session.session_type = kind
    _advance(session, State.ASK_DAYS)
    return out, None


def _on_days(session: Session, text: str, nlu: NLU):
    out = nlu("extract_days", session, text, {"day_terms": DAY_TERMS})
    dates = _resolve_days(out.get("days") or [])
    if not dates:
        return out, _reask(session, "no_days", text, nlu)
    session.days = [d.isoformat() for d in dates]
    time_pref = out.get("time_pref")
    slots = mock_backend.fetch_availability(session.doctor_id, dates, time_pref)
    time_pref_missed = None
    if not slots and time_pref:
        # Nothing in the preferred window: offer whatever the day has, and say the window was missed.
        slots = mock_backend.fetch_availability(session.doctor_id, dates)
        time_pref_missed = time_pref if slots else None
    if not slots:
        session.loop_counts["no_slots"] += 1
        if session.loop_counts["no_slots"] >= MAX_LOOPS:
            session.state = State.END
            return out, {"kind": "handoff", "reason": "no_slots_limit"}
        return out, {"kind": "no_slots", "days": list(session.days), "doctor_id": session.doctor_id}
    session.offered_slots = slots[:SLOTS_PER_OFFER]
    _advance(session, State.SHOW_SLOTS)
    extra = {"time_pref_missed": time_pref_missed} if time_pref_missed else {}
    return out, _present_slots(session, **extra)


def _on_choice(session: Session, text: str, nlu: NLU):
    out = nlu("slot_choice", session, text, {"offered_slots": list(session.offered_slots)})
    if out.get("wants_other"):
        session.offered_slots = []
        _advance(session, State.ASK_DAYS)
        return out, _ask(session, other_slots=True)
    idx = out.get("choice_index")  # 1-based: the number shown next to the slot
    if isinstance(idx, int) and 1 <= idx <= len(session.offered_slots):
        session.chosen_slot = session.offered_slots[idx - 1]
        _advance(session, State.CONFIRM)
        return out, None
    return out, _reask(session, "no_valid_choice", text, nlu)


WAITING_HANDLERS = {
    State.GREET: _on_greet,
    State.ASK_FIRST_CONSULT: _on_first_consult,
    State.ASK_PROBLEM: _on_problem,
    State.ASK_DOCTOR_PREF: _on_doctor_pref,
    State.ASK_PHONE: _on_phone,
    State.ASK_SESSION_TYPE: _on_session_type,
    State.ASK_DAYS: _on_days,
    State.CAPTURE_CHOICE: _on_choice,
}


# --- auto-state handlers: (session, nlu) -> reply or None


def _auto_pick_doctor(session: Session, nlu: NLU):
    shortlist = _shortlist(session.category)
    out = nlu("doctor_pick", session, session.problem or "", {"shortlist": shortlist})
    ids = [d["id"] for d in shortlist]
    chosen = out.get("doctor_id")
    session.doctor_id = chosen if chosen in ids else ids[0]
    _advance(session, State.ASK_DAYS)
    return _ask(session, suggested_doctor=fixtures.doctor_by_id(session.doctor_id)["name"])


def _auto_show_slots(session: Session, nlu: NLU):
    _advance(session, State.CAPTURE_CHOICE)
    return None  # _on_days built the present_slots facts (with any time_pref_missed note); step() keeps them


def _auto_confirm(session: Session, nlu: NLU):
    session.booking = mock_backend.create_booking(
        doctor_id=session.doctor_id,
        slot=session.chosen_slot,
        phone=session.phone,
        session_type=session.session_type,
        patient_type=session.patient_type,
    )
    _advance(session, State.END)
    return {"kind": "confirm_booking", "booking": dict(session.booking)}


AUTO_HANDLERS = {
    State.PICK_DOCTOR: _auto_pick_doctor,
    State.SHOW_SLOTS: _auto_show_slots,
    State.CONFIRM: _auto_confirm,
}


# --- entry point -------------------------------------------------------------


def step(session: Session, text: str, nlu: NLU) -> TurnResult:
    """Process one user turn. Mutates `session`. Returns the new state and reply facts."""
    session.turn += 1
    if session.state == State.END:
        return TurnResult(State.END, {"kind": "ended"}, None)

    correction = None
    correctable = _correctable_fields(session)
    if correctable and session.loop_counts["corrections"] < MAX_CORRECTIONS:
        out = nlu("turn_classifier", session, text, {})
        field = out.get("correction_field")
        if out.get("is_correction") and field in correctable and REWIND_MAP[field] != session.state:
            _rewind(session, REWIND_MAP[field])
            session.loop_counts["corrections"] += 1
            correction = {"field": field, "rewound_to": str(session.state)}

    nlu_output, reply = WAITING_HANDLERS[State(session.state)](session, text, nlu)

    while session.state in AUTO_HANDLERS:
        auto_reply = AUTO_HANDLERS[State(session.state)](session, nlu)
        reply = auto_reply or reply

    if reply is None:
        reply = _ask(session)
    return TurnResult(session.state, reply, nlu_output, correction)
