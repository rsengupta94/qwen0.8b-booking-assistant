"""Phase 5: off-script detour (design.md section 6) and the shortlist filter flag (section 5), with a stubbed NLU."""

from datetime import datetime

import pytest

from app import state_machine
from app.session import Session
from app.state_machine import MAX_LOOPS, State, step
from app.tools import fixtures, mock_backend

NOW = datetime(2026, 9, 21, 8, 0)  # a Monday, 08:00
NOT_Q = {"is_question": False, "topic": None}
FEES = fixtures.faq_answer("fees")


def question(topic):
    return {"is_question": True, "topic": topic}


class ScriptedNLU:
    def __init__(self, answers):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.calls = []

    def __call__(self, prompt_name, session, text, context):
        self.calls.append((prompt_name, text, context))
        if prompt_name == "turn_classifier" and not self.answers.get(prompt_name):
            return {"is_correction": False, "correction_field": None, "new_value": None}
        if prompt_name == "off_script" and not self.answers.get(prompt_name):
            return NOT_Q
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


# --- FAQ fixture ---------------------------------------------------------------


def test_faq_fixture_has_the_three_design_topics():
    assert {e["topic"] for e in fixtures.faq()} == {"fees", "hours", "first_visit"}
    assert all(e["keywords"] and e["answer"] for e in fixtures.faq())


def test_faq_answer_matches_keywords_deterministically():
    assert fixtures.faq_answer("fees") == FEES
    assert fixtures.faq_answer("Session Cost") == FEES
    assert fixtures.faq_answer("opening hours") == fixtures.faq_answer("weekend")
    assert fixtures.faq_answer("first_visit") is not None
    assert fixtures.faq_answer("parking") is None and fixtures.faq_answer(None) is None


# --- detour --------------------------------------------------------------------


def test_fee_question_at_first_consult_answers_and_reasks_without_spending_a_reask():
    nlu = ScriptedNLU({"yes_no": [{"intent": "other"}, {"intent": "yes"}], "off_script": [question("fees")]})
    s = Session("o1")
    r = run(s, nlu, ["hi", "what are your fees?"])
    assert r[1].state == State.ASK_FIRST_CONSULT
    assert r[1].reply == {"kind": "clarify", "question": "first_consult", "faq_answer": FEES, "topic": "fees"}
    assert nlu.names() == ["yes_no", "off_script"]
    assert s.loop_counts["reask"] == {} and s.loop_counts["detour"] == {State.ASK_FIRST_CONSULT: True}
    r2 = step(s, "yes", nlu)
    assert r2.state == State.ASK_PROBLEM and s.patient_type == "new"


def test_question_without_faq_hit_still_detours_with_no_answer():
    nlu = ScriptedNLU({"yes_no": [{"intent": "other"}], "off_script": [question("parking")]})
    s = Session("o2")
    r = run(s, nlu, ["hi", "is there parking?"])
    assert r[1].reply == {"kind": "clarify", "question": "first_consult", "faq_answer": None, "topic": "parking"}


def test_second_question_in_same_state_is_a_normal_reask():
    nlu = ScriptedNLU({"yes_no": [{"intent": "other"}] * 2, "off_script": [question("fees"), question("hours")]})
    s = Session("o3")
    r = run(s, nlu, ["hi", "what are your fees?", "and your hours?"])
    assert r[1].reply["kind"] == "clarify"
    assert r[2].reply == {"kind": "ask_question", "question": "first_consult", "reask": True, "reason": "not_yes_no"}
    assert nlu.names().count("off_script") == 1  # detour used: off_script is not called again in this state
    assert s.loop_counts["reask"] == {State.ASK_FIRST_CONSULT: 1}


def test_detour_is_per_state():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "other"}, {"intent": "no"}],
        "extract_phone": [{"digits": ""}, {"digits": "9876543210"}],
        "off_script": [question("fees"), question("hours")],
    })
    s = Session("o4")
    r = run(s, nlu, ["hi", "how much?", "no", "are you open saturdays?", "9876543210"])
    assert r[1].reply["kind"] == "clarify" and r[1].reply["question"] == "first_consult"
    assert r[3].reply["kind"] == "clarify" and r[3].reply["question"] == "phone" and r[3].state == State.ASK_PHONE
    assert r[3].reply["faq_answer"] == fixtures.faq_answer("hours")
    assert r[4].state == State.ASK_SESSION_TYPE and s.loop_counts["reask"] == {}


def test_not_a_question_is_a_normal_reask_and_counts_toward_handoff():
    nlu = ScriptedNLU({"yes_no": [{"intent": "other"}] * MAX_LOOPS, "off_script": [NOT_Q] * MAX_LOOPS})
    s = Session("o5")
    r = run(s, nlu, ["hi", "?", "??", "???"])
    assert r[1].reply["kind"] == "ask_question" and r[1].reply["reask"] is True
    assert nlu.names().count("off_script") == MAX_LOOPS  # checked on every re-ask while the detour is unused
    assert r[3].reply["kind"] == "handoff" and s.state == State.END


def test_no_detour_when_a_doctor_name_was_given_but_not_found():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "stress", "category": "stress"}],
        "doctor_pref": [{"mode": "named", "doctor_name": "Dr Nobody"}],
        "off_script": [question("fees")],  # must not be consumed
    })
    s = Session("o6")
    r = run(s, nlu, ["hi", "yes", "stress", "Dr Nobody"])
    assert r[3].reply["reason"] == "doctor_not_found" and "off_script" not in nlu.names()


def test_detour_at_capture_choice_reasks_slot_choice():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "no"}],
        "extract_phone": [{"digits": "9876543210"}],
        "session_type": [{"type": "therapy"}],
        "extract_days": [{"days": ["monday"], "time_pref": None}],
        "slot_choice": [{"choice_index": None, "wants_other": False, "other": "how long is a session?"},
                        {"choice_index": 1, "wants_other": False, "other": None}],
        "off_script": [question("session length")],
    })
    s = Session("o7")
    r = run(s, nlu, ["hi", "no", "9876543210", "therapy", "monday", "how long is a session?", "1"])
    assert r[5].state == State.CAPTURE_CHOICE
    assert r[5].reply == {"kind": "clarify", "question": "slot_choice", "faq_answer": None, "topic": "session length"}
    assert s.offered_slots == r[4].reply["slots"]  # offer intact
    assert r[6].state == State.END


# --- shortlist pick ------------------------------------------------------------


def test_you_decide_reply_names_the_suggested_doctor():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "low mood", "category": "depression"}],
        "doctor_pref": [{"mode": "you_decide", "doctor_name": None}],
        "doctor_pick": [{"doctor_id": "d_khan", "reason": "long-term therapy"}],
    })
    s = Session("o8")
    r = run(s, nlu, ["hi", "yes", "low mood", "you decide"])
    pick = next(c for c in nlu.calls if c[0] == "doctor_pick")
    assert [d["id"] for d in pick[2]["shortlist"]] == ["d_rao", "d_khan"]  # the one deliberate overlap: depression
    assert r[3].state == State.ASK_DAYS
    assert r[3].reply == {"kind": "ask_question", "question": "days", "suggested_doctor": "Dr. Sana Khan"}


def test_filter_flag_on_passes_only_category_matches():
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "grieving", "category": "grief"}],
        "doctor_pref": [{"mode": "you_decide", "doctor_name": None}],
        "doctor_pick": [{"doctor_id": "d_khan", "reason": "grief"}],
    })
    s = Session("o9")
    run(s, nlu, ["hi", "yes", "grieving", "you decide"])
    pick = next(c for c in nlu.calls if c[0] == "doctor_pick")
    assert [d["id"] for d in pick[2]["shortlist"]] == ["d_khan"]


def test_filter_flag_off_ranks_all_doctors_matches_first(monkeypatch):
    monkeypatch.setattr(state_machine, "FILTER_SHORTLIST", False)
    nlu = ScriptedNLU({
        "yes_no": [{"intent": "yes"}],
        "extract_problem": [{"summary": "grieving", "category": "grief"}],
        "doctor_pref": [{"mode": "you_decide", "doctor_name": None}],
        "doctor_pick": [{"doctor_id": "d_iyer", "reason": "picked outside the category"}],
    })
    s = Session("o10")
    run(s, nlu, ["hi", "yes", "grieving", "you decide"])
    pick = next(c for c in nlu.calls if c[0] == "doctor_pick")
    ids = [d["id"] for d in pick[2]["shortlist"]]
    assert ids[0] == "d_khan" and set(ids) == {d["id"] for d in fixtures.doctors()}
    # stub returned a non-grief doctor; with the real runner the validator's category_mismatch fallback returns ids[0]
    assert s.doctor_id == "d_iyer" and s.state == State.ASK_DAYS


def test_filter_off_validator_mismatch_falls_back_to_code_top_candidate():
    from app.nlu import doctor_pick
    monkeypatch_shortlist = state_machine._shortlist
    state_machine.FILTER_SHORTLIST = False
    try:
        shortlist = monkeypatch_shortlist("grief")
    finally:
        state_machine.FILTER_SHORTLIST = True
    out, ok, reason = doctor_pick.validate({"doctor_id": "d_iyer", "reason": "x"}, {"shortlist": shortlist, "category": "grief"})
    assert (ok, reason) == (False, "category_mismatch") and out["doctor_id"] == "d_khan"
