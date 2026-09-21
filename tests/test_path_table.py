"""Path table: expected routing and gold fields per scenario group, on hand-built sidecar sequences."""
from datetime import date

from evals import path_table as pt

TODAY = date(2026, 9, 18)  # a Friday, the generation date


def card(**facts):
    base = {"patient_type": "new", "phone": None, "problem_category": "anxiety", "symptom_brief": [],
            "doctor_pref": {"mode": "named", "name": "Dr. Meera Rao"}, "session_type": None,
            "days": ["wednesday"], "time_pref": "afternoon", "slot_rule": "first"}
    base.update(facts)
    return {"card_id": "t", "facts": base, "scripted_events": [], "verbatim": {}, "stop_after": "booking_confirmed"}


def turn(state, act="answer", field=None, value=None, text=""):
    return {"turn": 1, "answering_state": state, "user": text, "sidecar": {"act": act, "field": field, "value": value, "slot_rule": None}, "bot": {}}


def test_happy_new_named():
    w = pt.Walk(card(), TODAY)
    assert w.expect(turn("GREET", text="hi"))["next"] == "ASK_FIRST_CONSULT"
    e = w.expect(turn("ASK_FIRST_CONSULT", "answer", "patient_type", "new"))
    assert e["next"] == "ASK_PROBLEM" and e["nlu"]["yes_no"] == {"intent": "yes"}
    e = w.expect(turn("ASK_PROBLEM", "answer", "problem", "anxiety"))
    assert e["next"] == "ASK_DOCTOR_PREF" and e["nlu"]["extract_problem"] == {"category": "anxiety"}
    e = w.expect(turn("ASK_DOCTOR_PREF", "answer", "doctor", "Dr. Meera Rao", text="Dr. Meera Rao please"))
    assert e["next"] == "ASK_DAYS" and "doctor_pref" not in e["nlu"]
    e = w.expect(turn("ASK_DAYS", "answer", "days", "wednesday"))
    assert e["next"] == "CAPTURE_CHOICE" and e["offered"][0] == "2026-09-23T14:00:00"
    e = w.expect(turn("CAPTURE_CHOICE", "answer", "slot", "1"))
    assert e["next"] == "END" and e["end"] == "booking_confirmed" and e["expected_start"] == "2026-09-23T14:00:00"


def test_returning_flow_and_unknown_phone_handoff():
    w = pt.Walk(card(patient_type="returning", phone="9876543210", doctor_pref=None, session_type="therapy", days=["monday"], time_pref=None), TODAY)
    assert w.expect(turn("ASK_FIRST_CONSULT", "answer", "patient_type", "returning"))["next"] == "ASK_PHONE"
    e = w.expect(turn("ASK_PHONE", "answer", "phone", "+91 98765 43210"))
    assert e["next"] == "ASK_SESSION_TYPE" and e["nlu"]["extract_phone"] == {"digits": "9876543210"} and w.doctor_id == "d_rao"
    w2 = pt.Walk(card(patient_type="returning", phone="9000000001", doctor_pref=None), TODAY)
    for i in range(2):
        assert w2.expect(turn("ASK_PHONE", "answer", "phone", "9000000001"))["next"] == "ASK_PHONE"
    e = w2.expect(turn("ASK_PHONE", "answer", "phone", "9000000001"))
    assert e["next"] == "END" and e["end"] == "handoff"


def test_you_decide_shortlist_and_ambiguous_surname():
    w = pt.Walk(card(problem_category="depression", doctor_pref={"mode": "you_decide"}), TODAY)
    w.expect(turn("ASK_PROBLEM", "answer", "problem", "depression"))
    e = w.expect(turn("ASK_DOCTOR_PREF", "answer", "doctor", None, text="you pick"))
    assert e["next"] == "ASK_DAYS" and e["nlu"]["doctor_pick"]["doctor_id"] == {"d_rao", "d_khan"}
    w = pt.Walk(card(), TODAY)
    e = w.expect(turn("ASK_DOCTOR_PREF", "answer", "doctor", "Dr. Meera Rao", text="Rao"))
    assert e["next"] == "ASK_DOCTOR_PREF"
    e = w.expect(turn("ASK_DOCTOR_PREF", "answer", "doctor", "Dr. Meera Rao", text="Dr Roa"))
    assert e["next"] == "ASK_DOCTOR_PREF" and e["nlu"]["doctor_pref"]["mode"] == {"other", "you_decide"}


def test_non_answers_reask_then_handoff_and_faq_expects_off_script():
    w = pt.Walk(card(), TODAY)
    e = w.expect(turn("ASK_PROBLEM", "faq_question", "topic", "fees"))
    assert e["next"] == "ASK_PROBLEM" and e["nlu"]["off_script"] == {"is_question": True} and e["nlu"]["extract_problem"] == {"category": None}
    assert w.expect(turn("ASK_PROBLEM", "non_answer"))["next"] == "ASK_PROBLEM"
    e = w.expect(turn("ASK_PROBLEM", "non_answer"))
    assert e["next"] == "END" and e["end"] == "handoff"


def test_sunday_only_no_slots_three_rounds():
    w = pt.Walk(card(days=["sunday"], time_pref=None), TODAY)
    assert w.expect(turn("ASK_DAYS", "answer", "days", "sunday"))["next"] == "ASK_DAYS"
    assert w.expect(turn("ASK_DAYS", "repeat", "days", "sunday"))["next"] == "ASK_DAYS"
    e = w.expect(turn("ASK_DAYS", "repeat", "days", "sunday"))
    assert e["next"] == "END" and e["end"] == "handoff"


def test_corrections_rewind_and_cap():
    w = pt.Walk(card(problem_category="stress", doctor_pref={"mode": "you_decide"}, days=["saturday"]), TODAY)
    e = w.expect(turn("ASK_DOCTOR_PREF", "correction", "problem", "addiction"))
    assert e["next"] == "ASK_DOCTOR_PREF" and e["nlu"]["turn_classifier"]["is_correction"] and e["nlu"]["extract_problem"] == {"category": "addiction"}
    e = w.expect(turn("ASK_DAYS", "correction", "doctor", "Dr. Sana Khan"))
    assert e["next"] == "ASK_DAYS" and w.doctor_id == "d_khan"
    e = w.expect(turn("CAPTURE_CHOICE", "correction", "days", "thursday"))
    assert e["next"] == "CAPTURE_CHOICE"  # Khan has Thursday slots
    e = w.expect(turn("CAPTURE_CHOICE", "correction", "days", "saturday"))
    assert e["next"] == {"CAPTURE_CHOICE", "ASK_DAYS"} and "turn_classifier" not in e["nlu"]  # fourth correction: plain answer


def test_wants_other_and_slot_gold():
    w = pt.Walk(card(days=["wednesday"], time_pref=None, slot_rule="last"), TODAY)
    w.expect(turn("ASK_DAYS", "answer", "days", "wednesday"))
    e = w.expect(turn("CAPTURE_CHOICE", "wants_other"))
    assert e["next"] == "ASK_DAYS" and e["nlu"]["slot_choice"] == {"wants_other": True}
    w.expect(turn("ASK_DAYS", "answer", "days", "wednesday"))
    e = w.expect(turn("CAPTURE_CHOICE", "non_answer"))
    assert e["next"] == "CAPTURE_CHOICE" and e["nlu"]["slot_choice"] == {"choice_index": None, "wants_other": False}
