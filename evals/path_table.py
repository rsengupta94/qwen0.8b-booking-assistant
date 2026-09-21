"""Expected next state and expected NLU fields for one simulated turn.

This is the eval's own small model of the booking workflow. It reads the card, the sidecar act,
the corrected facts so far, and the fixtures (doctors, slots, patients). It never imports
app.state_machine, on purpose: a routing bug in the product must not become gold.
Deviations from the product are findings, not errors, and are scored by evals/score.py.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "fixtures"

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
RELATIVE = {"today": 0, "tomorrow": 1, "day_after_tomorrow": 2}
HORIZON_DAYS = 14
SLOTS_PER_OFFER = 3
MAX_REASKS = 3
MAX_NO_SLOTS = 3
MAX_CORRECTIONS = 3
TIME_PREF_HOURS = {"morning": (0, 12), "afternoon": (12, 17), "evening": (17, 24)}

REWIND_TARGET = {"problem": "ASK_PROBLEM", "doctor": "ASK_DOCTOR_PREF", "phone": "ASK_PHONE", "days": "ASK_DAYS"}


def _load(name: str):
    return json.loads((FIX / name).read_text())


DOCTORS = _load("doctors.json")
PATIENTS = {p["phone"]: p for p in _load("patients.json")}
SLOTS = _load("slots.json")


def doctors_for(category: str | None) -> list[str]:
    if not category:
        return [d["id"] for d in DOCTORS]
    return [d["id"] for d in DOCTORS if category in (d.get("tags") or d.get("categories") or [])]


def resolve_doctor(text: str | None) -> tuple[str | None, list[str]]:
    """Token match against roster names, like the product does. (unique_id, candidates)."""
    if not text:
        return None, []
    tokens = {t.strip(".,!?").lower() for t in text.split()} - {"dr", "doctor"}
    scored = []
    for d in DOCTORS:
        hits = len(tokens & {t.lower() for t in d["name"].split()})
        if hits:
            scored.append((hits, d["id"]))
    if not scored:
        return None, []
    best = max(h for h, _ in scored)
    cands = [i for h, i in scored if h == best]
    return (cands[0] if len(cands) == 1 else None), cands


def resolve_days(terms: list[str], today: date) -> list[date]:
    out: set[date] = set()
    for term in terms:
        term = term.strip().lower()
        if term in RELATIVE:
            out.add(today + timedelta(days=RELATIVE[term]))
        elif term in WEEKDAYS:
            for off in range(HORIZON_DAYS):
                d = today + timedelta(days=off)
                if WEEKDAYS[d.weekday()] == term:
                    out.add(d)
    return sorted(out)


def slots_for(doctor_id: str, days: list[date], time_pref: str | None, today: date, now: datetime | None = None) -> list[str]:
    """ISO starts for the doctor on the given dates (all horizon dates when days is empty), sorted.
    Falls back to the whole day when the preferred window is empty, like the product."""
    wanted = set(days)
    starts = []
    for s in SLOTS:
        if s["doctor_id"] != doctor_id:
            continue
        for off in range(HORIZON_DAYS):
            d = today + timedelta(days=off)
            if WEEKDAYS[d.weekday()] != s["weekday"] or (wanted and d not in wanted):
                continue
            for t in s["times"]:
                iso = f"{d.isoformat()}T{t}:00"
                if now is None or datetime.fromisoformat(iso) > now:
                    starts.append(iso)
    starts.sort()
    if time_pref in TIME_PREF_HOURS:
        lo, hi = TIME_PREF_HOURS[time_pref]
        narrowed = [x for x in starts if lo <= int(x[11:13]) < hi]
        if narrowed:
            return narrowed
    return starts


@dataclass
class Walk:
    """Mutable expectation state for one transcript."""
    card: dict
    today: date
    now: datetime | None = None                     # local generation time; slots before it are not offerable
    facts: dict = field(default_factory=dict)
    corrections: int = 0
    reasks: dict = field(default_factory=dict)      # state -> count
    no_slots_rounds: int = 0
    doctor_id: str | None = None                    # effective doctor from the card (named, phone, or correction)
    picked: str | None = None                       # the product's shortlist pick; used for slot routing only, never for gold
    last_offered: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.facts = dict(self.card["facts"])
        pref = self.facts.get("doctor_pref") or {}
        if pref.get("mode") == "named":
            self.doctor_id, _ = resolve_doctor(pref.get("name"))

    # ---- helpers -------------------------------------------------------------------------------
    def _reask(self, state: str, note: str) -> dict:
        self.reasks[state] = self.reasks.get(state, 0) + 1
        if self.reasks[state] >= MAX_REASKS:
            return {"next": "END", "end": "handoff", "note": f"{note}; third re-ask hands off"}
        return {"next": state, "note": note}

    def _leave(self, state: str) -> None:
        self.reasks.pop(state, None)

    def _days_route(self, terms: list[str], picked_doctor: str | None) -> dict:
        doc = self.doctor_id or picked_doctor
        dates = resolve_days(terms, self.today)
        if not dates and terms != ["any"]:
            return self._reask("ASK_DAYS", "no resolvable day")
        if doc is None:
            return {"next": {"CAPTURE_CHOICE", "ASK_DAYS"}, "note": "doctor unknown to gold; either route accepted"}
        offered = slots_for(doc, dates, self.facts.get("time_pref"), self.today, self.now)[:SLOTS_PER_OFFER]
        if offered:
            self.last_offered = offered
            self._leave("ASK_DAYS")
            return {"next": "CAPTURE_CHOICE", "note": "slots offered", "offered": offered}
        self.no_slots_rounds += 1
        if self.no_slots_rounds >= MAX_NO_SLOTS:
            return {"next": "END", "end": "handoff", "note": "third no-slots round hands off"}
        return {"next": "ASK_DAYS", "note": "no slots, re-ask days"}

    # ---- main ----------------------------------------------------------------------------------
    def expect(self, turn: dict, picked_doctor: str | None = None, extracted_category: str | None = None) -> dict:
        """Return {'next': state | set | 'END', 'end': kind?, 'nlu': {prompt: {field: value}}, 'note'}."""
        state = turn["answering_state"]
        sc = turn.get("sidecar") or {}
        act, fld, val = sc.get("act"), sc.get("field"), sc.get("value")
        text = turn.get("user") or ""
        nlu: dict = {}
        out: dict

        if picked_doctor:
            self.picked = picked_doctor
        picked_doctor = self.picked

        # Correction: classifier must fire; product rewinds and re-runs with the new value.
        if act == "correction":
            if self.corrections >= MAX_CORRECTIONS:
                nxt = {state, "ASK_DAYS"} if state == "CAPTURE_CHOICE" else state
                out = {"next": nxt, "note": "correction past cap is taken as a plain answer", "nlu": nlu}
                return out
            self.corrections += 1
            nlu["turn_classifier"] = {"is_correction": True, "correction_field": fld}
            if fld == "problem":
                self.facts["problem_category"] = val
                self.doctor_id = None
                nlu["extract_problem"] = {"category": val}
                out = {"next": "ASK_DOCTOR_PREF", "note": "problem corrected, re-ask doctor pref"}
            elif fld == "doctor":
                self.doctor_id, _ = resolve_doctor(val)
                self.facts["doctor_pref"] = {"mode": "named", "name": val}
                out = {"next": "ASK_DAYS", "note": "doctor corrected, ask days again"}
            elif fld == "phone":
                digits = re.sub(r"\D", "", val or "")[-10:]
                self.facts["phone"] = digits
                nlu["extract_phone"] = {"digits": digits}
                if digits in PATIENTS:
                    self.doctor_id = PATIENTS[digits]["doctor_id"]
                out = {"next": "ASK_SESSION_TYPE" if digits in PATIENTS else "ASK_PHONE", "note": "phone corrected"}
            elif fld == "days":
                terms = val if isinstance(val, list) else [val]
                self.facts["days"] = terms
                nlu["extract_days"] = {"days": sorted(t.lower() for t in terms)}
                out = self._days_route(terms, picked_doctor)
            else:
                out = {"next": state, "note": f"unknown correction field {fld}"}
            out["nlu"] = nlu
            return out

        if act in ("non_answer", "repeat", "faq_question", "wants_other") or (act == "answer" and fld is None and state != "GREET"):
            if state != "GREET":
                nlu["turn_classifier"] = {"is_correction": False}
            if act == "faq_question":
                nlu["off_script"] = {"is_question": True}
            if state == "ASK_DAYS" and act != "wants_other":
                nlu["extract_days"] = {"days": []}
            if state == "ASK_PROBLEM":
                nlu["extract_problem"] = {"category": None}  # schema cannot say "not a problem"; any pick is wrong
            if act == "wants_other" and state == "CAPTURE_CHOICE":
                nlu["slot_choice"] = {"wants_other": True}
                self._leave("CAPTURE_CHOICE")
                out = {"next": "ASK_DAYS", "note": "wants other slots"}
            elif act == "repeat" and fld:
                # A faithful restatement of an earlier answer: treat as that answer.
                return self.expect({**turn, "sidecar": {**sc, "act": "answer"}}, picked_doctor)
            else:
                if state == "CAPTURE_CHOICE":
                    nlu["slot_choice"] = {"choice_index": None, "wants_other": False}
                out = self._reask(state, f"{act} at {state}")
            out["nlu"] = nlu
            return out

        # Plain answers, by state.
        if state != "GREET":
            nlu["turn_classifier"] = {"is_correction": False}
        if state == "GREET":
            out = {"next": "ASK_FIRST_CONSULT", "note": "greeting"}
        elif state == "ASK_FIRST_CONSULT":
            nlu["yes_no"] = {"intent": "yes" if val == "new" else "no"}
            self._leave(state)
            out = {"next": "ASK_PROBLEM" if val == "new" else "ASK_PHONE", "note": "patient type"}
        elif state == "ASK_PROBLEM":
            nlu["extract_problem"] = {"category": val}
            self.facts["problem_category"] = val
            self._leave(state)
            out = {"next": "ASK_DOCTOR_PREF", "note": "problem given"}
        elif state == "ASK_DOCTOR_PREF":
            uid, cands = resolve_doctor(text)
            if val:  # persona intends a named doctor
                if uid:
                    self.doctor_id = uid
                    self._leave(state)
                    out = {"next": "ASK_DAYS", "note": "roster name matched in code"}
                elif cands:
                    out = self._reask(state, "ambiguous surname, re-ask naming candidates")
                else:
                    nlu["doctor_pref"] = {"mode": {"other", "you_decide"}}
                    out = self._reask(state, "name not on roster (misspelled); model cannot say named")
            else:
                nlu["doctor_pref"] = {"mode": "you_decide"}
                # doctor_pick is judged against the category the product actually extracted, so a wrong
                # category is charged to extract_problem once, not to doctor_pick as well.
                nlu["doctor_pick"] = {"doctor_id": set(doctors_for(extracted_category or self.facts.get("problem_category")))}
                self._leave(state)
                out = {"next": "ASK_DAYS", "note": "you decide; shortlist pick"}
        elif state == "ASK_PHONE":
            digits = re.sub(r"\D", "", val or "")[-10:]
            nlu["extract_phone"] = {"digits": digits}
            if digits in PATIENTS:
                self.doctor_id = PATIENTS[digits]["doctor_id"]
                self._leave(state)
                out = {"next": "ASK_SESSION_TYPE", "note": "known patient"}
            else:
                out = self._reask(state, "unknown phone")
        elif state == "ASK_SESSION_TYPE":
            nlu["session_type"] = {"type": val}
            self._leave(state)
            out = {"next": "ASK_DAYS", "note": "session type"}
        elif state == "ASK_DAYS":
            terms = [t.strip() for t in re.split(r"[,;]", val or "") if t.strip()]
            if terms != ["any"]:
                nlu["extract_days"] = {"days": sorted(t.lower() for t in terms)}
                self.facts["days"] = terms
            out = self._days_route([] if terms == ["any"] else terms, picked_doctor)
        elif state == "CAPTURE_CHOICE":
            idx = int(val) if str(val).isdigit() else None
            nlu["slot_choice"] = {"choice_index": idx, "wants_other": False}
            self._leave(state)
            out = {"next": "END", "end": "booking_confirmed", "note": "slot picked",
                   "expected_start": self.last_offered[idx - 1] if idx and idx <= len(self.last_offered) else None}
        else:
            out = {"next": state, "note": f"no rule for {state}/{act}"}
        out["nlu"] = nlu
        return out


def expected_doctors(walk: Walk) -> set[str]:
    """Doctors an acceptable final booking may name, given the effective facts."""
    if walk.doctor_id:
        return {walk.doctor_id}
    return set(doctors_for(walk.facts.get("problem_category")))
