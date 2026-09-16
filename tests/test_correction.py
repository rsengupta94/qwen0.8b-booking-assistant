"""Phase 4: correction intent. Rewind map, downstream clearing, correction cap, with a stubbed NLU."""

from datetime import datetime

import pytest

from app.session import Session
from app.state_machine import MAX_CORRECTIONS, REWIND_MAP, State, step
from app.tools import mock_backend

NOW = datetime(2026, 9, 21, 8, 0)  # a Monday, 08:00
NOT = {"is_correction": False, "correction_field": None, "new_value": None}


def corr(field, value):
    return {"is_correction": True, "correction_field": field, "new_value": value}


class ScriptedNLU:
    """Answers in order per prompt name; turn_classifier defaults to 'not a correction'. Records every call."""

    def __init__(self, answers):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.calls = []

    def __call__(self, prompt_name, session, text, context):
        self.calls.append((prompt_name, text, str(session.state)))
        if prompt_name == "turn_classifier" and not self.answers.get(prompt_name):
            return NOT
        if prompt_name == "off_script" and not self.answers.get(prompt_name):
            return {"is_question": False, "topic": None}
        return self.answers[prompt_name].pop(0)

    def names(self):
        return [c[0] for c in self.calls]


@pytest.fixture(autouse=True)
def clean_backend(monkeypatch):
    monkeypatch.setattr(mock_backend, "now", lambda: NOW)
    mock_backend.reset()
    yield
    mock_backend.reset()


def run(session, nlu, turns):
    return [step(session, text, nlu) for text in turns]


def test_rewind_map_covers_every_classifier_field():
    from app.nlu.turn_classifier import FIELDS
    assert set(REWIND_MAP) == set(FIELDS)


def test_classifier_not_called_before_any_answer_is_correctable():
    nlu = ScriptedNLU({"yes_no": [{"intent": "yes"}], "extract_problem": [{"summary": "stress", "category": "stress"}]})
    s = Session("c0")
    run(s, nlu, ["hi", "yes", "stress"])
    assert "turn_classifier" not in nlu.names()  # nothing set yet at GREET, ASK_FIRST_CONSULT, ASK_PROBLEM
    r = step(s, "Anil Rao", ScriptedNLU({"doctor_pref": [{"mode": "named", "doctor_name": "Anil Rao"}]}))
    assert r.correction is None


def test_change_doctor_at_capture_choice_rewinds_clears_and_refetches():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "anxious", "category": "anxiety"}],
        "doctor_pref": [{"mode": "named", "doctor_name": "Dr Meera Rao"}, {"mode": "named", "doctor_name": "Dr Sana Khan"}],
        "extract_days": [{"days": ["wednesday"], "time_pref": None}, {"days": ["thursday"], "time_pref": None}],
        "turn_classifier": [NOT, NOT, corr("doctor", "Dr Sana Khan"), NOT, NOT],
        "slot_choice": [{"choice_index": 1, "wants_other": False, "other": None}],
    })
    s = Session("c1")
    r = run(s, nlu, ["hi", "yes", "anxious", "Dr Meera Rao", "wednesday", "actually Dr Sana Khan instead"])

    assert r[4].reply["kind"] == "present_slots" and r[4].reply["doctor_name"] == "Dr. Meera Rao"
    assert r[5].correction == {"field": "doctor", "rewound_to": "ASK_DOCTOR_PREF"}
    assert r[5].state == State.ASK_DAYS and r[5].reply == {"kind": "ask_question", "question": "days"}
    assert s.doctor_id == "d_khan" and s.days == [] and s.offered_slots == [] and s.chosen_slot is None
    r += run(s, nlu, ["thursday", "1"])
    # the correction turn ran the classifier, then the owning state's NLU on the same text
    assert [c for c in nlu.calls if c[1] == "actually Dr Sana Khan instead"] == [
        ("turn_classifier", "actually Dr Sana Khan instead", "CAPTURE_CHOICE"),
        ("doctor_pref", "actually Dr Sana Khan instead", "ASK_DOCTOR_PREF"),
    ]
    assert r[6].reply["kind"] == "present_slots" and r[6].reply["doctor_name"] == "Dr. Sana Khan"
    assert [sl["start"] for sl in r[6].reply["slots"]] == ["2026-09-24T14:00", "2026-09-24T15:00", "2026-10-01T14:00"]
    b = mock_backend.bookings()
    assert len(b) == 1 and b[0]["doctor_id"] == "d_khan" and b[0]["start"] == "2026-09-24T14:00"
    assert s.loop_counts["corrections"] == 1


def test_change_days_at_capture_choice_keeps_doctor():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9876543210"}],
        "session_type": [{"type": "followup"}],
        "extract_days": [{"days": ["monday"], "time_pref": None}, {"days": ["friday"], "time_pref": None}],
        "turn_classifier": [NOT, NOT, corr("days", "friday")],
    })
    s = Session("c2")
    r = run(s, nlu, ["hi", "no", "9876543210", "follow up", "monday", "actually friday"])
    assert r[5].correction == {"field": "days", "rewound_to": "ASK_DAYS"}
    assert s.doctor_id == "d_rao" and s.session_type == "followup" and s.phone == "9876543210"
    assert r[5].state == State.CAPTURE_CHOICE and [sl["start"] for sl in r[5].reply["slots"]] == ["2026-09-25T10:00", "2026-09-25T11:00", "2026-10-02T10:00"]
    assert s.offered_slots == r[5].reply["slots"]


def test_change_phone_clears_doctor_and_session_type():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9876543210"}, {"digits": "9123456780"}],
        "session_type": [{"type": "followup"}],
        "turn_classifier": [NOT, corr("phone", "9123456780")],
    })
    s = Session("c3")
    r = run(s, nlu, ["hi", "no", "9876543210", "follow up", "wait, my number is 9123456780"])
    assert r[4].correction == {"field": "phone", "rewound_to": "ASK_PHONE"}
    assert r[4].state == State.ASK_SESSION_TYPE and s.phone == "9123456780" and s.doctor_id == "d_khan"
    assert s.session_type is None


def test_change_session_type_rewinds_from_capture_choice():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9876543210"}],
        "session_type": [{"type": "followup"}, {"type": "therapy"}],
        "extract_days": [{"days": ["monday"], "time_pref": None}],
        "turn_classifier": [NOT, NOT, corr("session_type", "therapy")],
    })
    s = Session("c4")
    r = run(s, nlu, ["hi", "no", "9876543210", "follow up", "monday", "sorry, therapy not follow-up"])
    assert r[5].correction == {"field": "session_type", "rewound_to": "ASK_SESSION_TYPE"}
    assert r[5].state == State.ASK_DAYS and s.session_type == "therapy" and s.days == [] and s.offered_slots == []


def test_change_problem_clears_doctor_and_reasks_pref():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "stress", "category": "stress"}, {"summary": "grieving", "category": "grief"}],
        "doctor_pref": [{"mode": "named", "doctor_name": "Anil Rao"}],
        "turn_classifier": [NOT, corr("problem", "grief")],
    })
    s = Session("c5")
    r = run(s, nlu, ["hi", "yes", "stress", "Anil Rao", "actually it is more about grief"])
    assert r[4].correction == {"field": "problem", "rewound_to": "ASK_PROBLEM"}
    assert r[4].state == State.ASK_DOCTOR_PREF and s.category == "grief" and s.doctor_id is None


def test_correction_on_unset_field_is_a_normal_answer():
    """New patient: session_type is code-set, so a session_type 'correction' is not honoured."""
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "stress", "category": "stress"}],
        "doctor_pref": [{"mode": "named", "doctor_name": "Anil Rao"}],
        "extract_days": [{"days": ["tuesday"], "time_pref": None}],
        "turn_classifier": [NOT, corr("session_type", "therapy")],
    })
    s = Session("c6")
    r = run(s, nlu, ["hi", "yes", "stress", "Anil Rao", "tuesday"])
    assert r[4].correction is None and r[4].state == State.CAPTURE_CHOICE
    assert s.session_type == "first_consultation" and s.loop_counts["corrections"] == 0


def test_correction_targeting_current_state_is_a_normal_answer():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "stress", "category": "stress"}],
        "doctor_pref": [{"mode": "named", "doctor_name": "Meera Rao"}],
        "extract_days": [{"days": ["sunday"], "time_pref": None}, {"days": ["monday"], "time_pref": None}],
        "turn_classifier": [NOT, NOT, corr("days", "monday")],
    })
    s = Session("c7")
    r = run(s, nlu, ["hi", "yes", "stress", "Meera Rao", "sunday", "actually monday"])
    assert r[4].reply["kind"] == "no_slots" and r[4].state == State.ASK_DAYS
    assert r[5].correction is None and r[5].reply["kind"] == "present_slots" and s.loop_counts["corrections"] == 0


def test_corrections_are_capped_and_classifier_stops_running():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "stress", "category": "stress"}],
        "doctor_pref": [{"mode": "named", "doctor_name": n} for n in ["Meera Rao", "Sana Khan", "Anil Rao", "Arjun Iyer"]],
        "turn_classifier": [NOT] + [corr("doctor", "x")] * MAX_CORRECTIONS,
        "extract_days": [{"days": ["tuesday"], "time_pref": None}],
    })
    s = Session("c8")
    run(s, nlu, ["hi", "yes", "stress", "Meera Rao", "no, Sana Khan", "no, Anil Rao", "no, Arjun Iyer"])
    assert s.loop_counts["corrections"] == MAX_CORRECTIONS and s.doctor_id == "d_iyer"
    assert nlu.names().count("turn_classifier") == MAX_CORRECTIONS + 1  # one non-correction turn, then three corrections
    r = step(s, "tuesday", nlu)
    assert nlu.names().count("turn_classifier") == MAX_CORRECTIONS + 1  # cap reached: no more classifier calls
    assert r.correction is None and r.state == State.CAPTURE_CHOICE and r.reply["doctor_name"] == "Dr. Arjun Iyer"


def test_rewind_clears_reask_count_of_the_state_left():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "stress", "category": "stress"}],
        "doctor_pref": [{"mode": "named", "doctor_name": "Meera Rao"}, {"mode": "named", "doctor_name": "Sana Khan"}],
        "extract_days": [{"days": ["wednesday"], "time_pref": None}],
        "slot_choice": [{"choice_index": None, "wants_other": False, "other": "hmm"}],
        "turn_classifier": [NOT, NOT, NOT, corr("doctor", "Sana Khan")],
    })
    s = Session("c9")
    r = run(s, nlu, ["hi", "yes", "stress", "Meera Rao", "wednesday", "hmm", "actually Sana Khan"])
    assert r[5].reply.get("reask") is True and s.loop_counts["reask"] == {} and r[6].state == State.ASK_DAYS
