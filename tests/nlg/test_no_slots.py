from app.nlg import no_slots as m

FACTS = {"kind": "no_slots", "doctor_id": "d_rao", "days": ["2026-09-27", "2026-10-04"]}


def test_template_names_doctor_and_days_and_asks():
    t = m.template(FACTS)
    assert t == "Sorry, Dr. Meera Rao has no free slots on Sunday 27 September or Sunday 4 October. Would another day work for you?"


def test_reply_needs_question_doctor_and_days():
    assert m.validate({"reply": "Dr. Meera Rao is booked on Sunday 27 September and Sunday 4 October."}, FACTS)[2] == "no_question"
    assert m.validate({"reply": "Nothing on Sunday 27 September or Sunday 4 October. Another day?"}, FACTS)[2] == "doctor_missing"
    assert m.validate({"reply": "Dr. Meera Rao has nothing on Sunday 27 September. Another day?"}, FACTS)[2] == "day_missing"
    good = "Dr. Meera Rao is booked out on Sunday 27 September and Sunday 4 October. Another day?"
    assert m.validate({"reply": good}, FACTS) == (good, True, "ok")


def test_three_days_join():
    t = m.template({**FACTS, "days": ["2026-09-21", "2026-09-22", "2026-09-23"]})
    assert "Monday 21 September, Tuesday 22 September or Wednesday 23 September" in t
