"""Phase 1: walk both workflows end to end with a stubbed NLU and assert a booking exists."""

from datetime import date

import pytest

from app.session import Session
from app.state_machine import MAX_LOOPS, State, step
from app.tools import mock_backend

TODAY = date(2026, 9, 21)  # a Monday


class ScriptedNLU:
    """Returns hard-coded answers in order, per prompt name. Records every call."""

    def __init__(self, answers: dict[str, list[dict]]):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, prompt_name, session, text, context):
        self.calls.append((prompt_name, text, context))
        return self.answers[prompt_name].pop(0)


@pytest.fixture(autouse=True)
def clean_backend(monkeypatch):
    monkeypatch.setattr(mock_backend, "today", lambda: TODAY)
    mock_backend.reset()
    yield
    mock_backend.reset()


def run(session, nlu, turns):
    return [step(session, text, nlu) for text in turns]


def test_new_patient_named_doctor_books():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "anxious and not sleeping", "category": "anxiety"}],
        "doctor_pref": [{"mode": "named", "doctor_name": "Dr Meera Rao"}],
        "extract_days": [{"days": ["wednesday"], "time_pref": None}],
        "slot_choice": [{"choice_index": 1, "wants_other": False, "other": None}],
    })
    s = Session("t1")
    r = run(s, nlu, ["hi", "yes", "anxious, not sleeping", "Dr Meera Rao please", "wednesday", "the first one"])

    assert [x.state for x in r] == [
        State.ASK_FIRST_CONSULT, State.ASK_PROBLEM, State.ASK_DOCTOR_PREF,
        State.ASK_DAYS, State.CAPTURE_CHOICE, State.END,
    ]
    assert r[4].reply["kind"] == "present_slots"
    # both Wednesdays in the 14-day horizon, nearest first, capped at 3
    assert [sl["start"] for sl in r[4].reply["slots"]] == ["2026-09-23T14:00", "2026-09-23T15:00", "2026-09-30T14:00"]
    assert s.days == ["2026-09-23", "2026-09-30"]
    assert r[5].reply["kind"] == "confirm_booking"

    bookings = mock_backend.bookings()
    assert len(bookings) == 1
    b = bookings[0]
    assert b["doctor_id"] == "d_rao" and b["start"] == "2026-09-23T14:00"
    assert b["patient_type"] == "new" and b["session_type"] == "first_consultation" and b["phone"] is None
    assert s.booking == b


def test_returning_patient_books_with_own_doctor():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9876543210"}],
        "session_type": [{"type": "followup"}],
        "extract_days": [{"days": ["monday"], "time_pref": "morning"}],
        "slot_choice": [{"choice_index": 2, "wants_other": False, "other": None}],
    })
    s = Session("t2")
    r = run(s, nlu, ["hello", "no", "9876543210", "follow up", "monday morning", "second"])

    assert [x.state for x in r] == [
        State.ASK_FIRST_CONSULT, State.ASK_PHONE, State.ASK_SESSION_TYPE,
        State.ASK_DAYS, State.CAPTURE_CHOICE, State.END,
    ]
    assert s.patient_type == "returning" and s.doctor_id == "d_rao"
    b = mock_backend.bookings()
    assert len(b) == 1
    assert b[0]["doctor_id"] == "d_rao" and b[0]["start"] == "2026-09-21T11:00"
    assert b[0]["phone"] == "9876543210" and b[0]["session_type"] == "followup"


def test_you_decide_picks_from_category_shortlist():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "cannot sleep", "category": "sleep"}],
        "doctor_pref": [{"mode": "you_decide", "doctor_name": None}],
        "doctor_pick": [{"doctor_id": "d_mehta", "reason": "sleep routines"}],
        "extract_days": [{"days": ["wednesday"], "time_pref": None}],
        "slot_choice": [{"choice_index": 1, "wants_other": False, "other": None}],
    })
    s = Session("t3")
    run(s, nlu, ["hi", "yes", "cannot sleep", "you decide", "wednesday", "1"])

    pick_call = next(c for c in nlu.calls if c[0] == "doctor_pick")
    assert [d["id"] for d in pick_call[2]["shortlist"]] == ["d_iyer", "d_mehta"]
    b = mock_backend.bookings()
    assert len(b) == 1 and b[0]["doctor_id"] == "d_mehta" and b[0]["start"] == "2026-09-23T09:00"


def test_doctor_pick_outside_shortlist_falls_back_to_top_candidate():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "grieving", "category": "grief"}],
        "doctor_pref": [{"mode": "you_decide", "doctor_name": None}],
        "doctor_pick": [{"doctor_id": "d_iyer", "reason": "made up"}],
    })
    s = Session("t4")
    run(s, nlu, ["hi", "yes", "grieving", "you decide"])
    assert s.doctor_id == "d_khan" and s.state == State.ASK_DAYS


def test_no_slots_three_times_hands_off():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "stress", "category": "anxiety"}],
        "doctor_pref": [{"mode": "named", "doctor_name": "Meera Rao"}],
        "extract_days": [{"days": ["sunday"], "time_pref": None}] * MAX_LOOPS,
    })
    s = Session("t5")
    r = run(s, nlu, ["hi", "yes", "stress", "Meera Rao", "sunday", "sunday", "sunday"])

    assert r[4].reply == {"kind": "no_slots", "days": ["2026-09-27", "2026-10-04"]} and r[4].state == State.ASK_DAYS
    assert r[5].reply["kind"] == "no_slots"
    assert r[6].reply["kind"] == "handoff" and r[6].state == State.END
    assert mock_backend.bookings() == []


def test_unknown_doctor_name_reasks_then_accepts():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "low mood", "category": "depression"}],
        "doctor_pref": [
            {"mode": "named", "doctor_name": "Dr Nobody"},
            {"mode": "named", "doctor_name": "Khan"},
        ],
    })
    s = Session("t6")
    r = run(s, nlu, ["hi", "yes", "low mood", "Dr Nobody", "Dr Khan"])
    assert r[3].state == State.ASK_DOCTOR_PREF and r[3].reply["reason"] == "doctor_not_found"
    assert r[4].state == State.ASK_DAYS and s.doctor_id == "d_khan"
    assert s.loop_counts["reask"] == {}


def test_ambiguous_doctor_name_reasks_with_candidates_then_full_name_resolves():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "stress", "category": "stress"}],
        "doctor_pref": [
            {"mode": "named", "doctor_name": "Dr Rao"},
            {"mode": "named", "doctor_name": "Anil Rao"},
        ],
    })
    s = Session("t6b")
    r = run(s, nlu, ["hi", "yes", "stress", "Dr Rao", "Anil Rao"])
    assert r[3].state == State.ASK_DOCTOR_PREF and r[3].reply["reason"] == "doctor_ambiguous"
    assert r[3].reply["candidates"] == ["Dr. Meera Rao", "Dr. Anil Rao"]
    assert r[4].state == State.ASK_DAYS and s.doctor_id == "d_arao"


def test_unknown_phone_routes_to_new_patient_flow():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "0000000000"}],
    })
    s = Session("t7")
    r = run(s, nlu, ["hi", "no", "0000000000"])
    assert r[2].state == State.ASK_PROBLEM and r[2].reply.get("phone_not_found") is True
    assert s.patient_type == "new" and s.phone == "0000000000" and s.session_type == "first_consultation"


def test_wants_other_slots_returns_to_ask_days():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9123456780"}],
        "session_type": [{"type": "therapy"}],
        "extract_days": [{"days": ["monday"], "time_pref": None}, {"days": ["thursday"], "time_pref": None}],
        "slot_choice": [
            {"choice_index": None, "wants_other": True, "other": "later in the week"},
            {"choice_index": 1, "wants_other": False, "other": None},
        ],
    })
    s = Session("t8")
    r = run(s, nlu, ["hi", "no", "9123456780", "therapy", "monday", "anything later?", "thursday", "1"])
    assert r[5].state == State.ASK_DAYS and r[5].reply == {"kind": "ask_question", "question": "days", "other_slots": True}
    b = mock_backend.bookings()
    assert len(b) == 1 and b[0]["doctor_id"] == "d_khan" and b[0]["start"] == "2026-09-24T14:00"


def test_relative_days_and_time_pref():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9123456780"}],
        "session_type": [{"type": "therapy"}],
        "extract_days": [
            {"days": ["tomorrow", "day_after_tomorrow"], "time_pref": None},
            {"days": ["today"], "time_pref": "morning"},   # d_khan has only 16:00 on Monday -> no slots
            {"days": ["today"], "time_pref": "afternoon"},
        ],
        "slot_choice": [
            {"choice_index": None, "wants_other": True, "other": None},
            {"choice_index": 1, "wants_other": False, "other": None},
        ],
    })
    s = Session("t10")
    r = run(s, nlu, ["hi", "no", "9123456780", "therapy", "tomorrow or the day after", "other", "today morning", "today afternoon", "1"])
    # tomorrow = Tue 22nd (10:00, 10:30); day after = Wed 23rd (none for d_khan)
    assert [sl["start"] for sl in r[4].reply["slots"]] == ["2026-09-22T10:00", "2026-09-22T10:30"]
    assert r[6].reply == {"kind": "no_slots", "days": ["2026-09-21"]}
    assert [sl["start"] for sl in r[7].reply["slots"]] == ["2026-09-21T16:00"]
    b = mock_backend.bookings()
    assert len(b) == 1 and b[0]["start"] == "2026-09-21T16:00"


def test_unknown_day_terms_reask():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9876543210"}],
        "session_type": [{"type": "therapy"}],
        "extract_days": [{"days": ["someday"], "time_pref": None}],
    })
    s = Session("t11")
    r = run(s, nlu, ["hi", "no", "9876543210", "therapy", "someday"])
    assert r[4].state == State.ASK_DAYS and r[4].reply["reason"] == "no_days"


def test_reask_limit_hands_off():
    nlu = ScriptedNLU({"yes_no": [{"intent": "other"}] * MAX_LOOPS})
    s = Session("t9")
    r = run(s, nlu, ["hi", "?", "??", "???"])
    assert r[1].reply["kind"] == "ask_question" and r[1].reply["reask"] is True
    assert r[3].reply["kind"] == "handoff" and s.state == State.END


def test_empty_phone_reasks_then_accepts():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": ""}, {"digits": "9876543210"}],
    })
    s = Session("t12")
    r = run(s, nlu, ["hi", "no", "I don't remember"])
    assert r[2].state == State.ASK_PHONE and r[2].reply == {"kind": "ask_question", "question": "phone", "reask": True, "reason": "no_phone"}
    assert s.phone is None
    r4 = step(s, "9876543210", nlu)
    assert r4.state == State.ASK_SESSION_TYPE and s.phone == "9876543210" and s.doctor_id == "d_rao"
    assert s.loop_counts["reask"] == {}


def test_other_session_type_reasks_then_accepts():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9876543210"}],
        "session_type": [{"type": "other"}, {"type": "therapy"}],
    })
    s = Session("t13")
    r = run(s, nlu, ["hi", "no", "9876543210", "what do you mean?"])
    assert r[3].state == State.ASK_SESSION_TYPE and r[3].reply["reask"] is True and r[3].reply["reason"] == "not_session_type"
    assert s.session_type is None
    r5 = step(s, "therapy", nlu)
    assert r5.state == State.ASK_DAYS and s.session_type == "therapy"


def test_invalid_slot_choice_represents_slots_then_accepts():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9876543210"}],
        "session_type": [{"type": "therapy"}],
        "extract_days": [{"days": ["monday"], "time_pref": None}],
        "slot_choice": [
            {"choice_index": 7, "wants_other": False, "other": None},      # out of range
            {"choice_index": None, "wants_other": False, "other": "hmm"},  # no choice at all
            {"choice_index": 2, "wants_other": False, "other": None},
        ],
    })
    s = Session("t14")
    r = run(s, nlu, ["hi", "no", "9876543210", "therapy", "monday", "seven", "hmm", "the second"])
    offered = r[4].reply["slots"]
    for i in (5, 6):
        assert r[i].state == State.CAPTURE_CHOICE
        assert r[i].reply["kind"] == "present_slots" and r[i].reply["reask"] is True and r[i].reply["reason"] == "no_valid_choice"
        assert r[i].reply["slots"] == offered
    assert r[7].state == State.END
    b = mock_backend.bookings()
    assert len(b) == 1 and b[0]["start"] == offered[1]["start"] == "2026-09-21T11:00"
