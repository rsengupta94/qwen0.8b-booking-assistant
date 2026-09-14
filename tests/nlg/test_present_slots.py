from app.nlg import present_slots as m

FACTS = {
    "kind": "present_slots", "doctor_name": "Dr. Meera Rao",
    "slots": [{"start": "2026-09-23T14:00"}, {"start": "2026-09-23T15:00"}],
}
TEMPLATE = "Dr. Meera Rao is available at:\n1. Wednesday 23 September, 14:00\n2. Wednesday 23 September, 15:00\nWhich one would you like?"


def test_template_lists_every_slot():
    assert m.template(FACTS) == TEMPLATE


def test_reply_with_all_slots_passes():
    good = "Dr. Meera Rao can see you on:\n1. Wednesday 23 September, 14:00\n2. Wednesday 23 September, 15:00\nWhich suits you?"
    assert m.validate({"reply": good}, FACTS) == (good, True, "ok")


def test_fake_slot_falls_back_to_template():
    fake = "Dr. Meera Rao is available at:\n1. Wednesday 23 September, 14:00\n2. Wednesday 23 September, 15:00\n3. Thursday 24 September, 16:00\nWhich one?"
    assert m.validate({"reply": fake}, FACTS) == (TEMPLATE, False, "extra_time")


def test_dropped_slot_falls_back():
    assert m.validate({"reply": "Dr. Meera Rao is free Wednesday 23 September, 14:00. OK?"}, FACTS)[2] == "slot_missing"


def test_altered_time_format_is_caught():
    bad = "Dr. Meera Rao is available at:\n1. Wednesday 23 September, 14:00\n2. Wednesday 23 September, 15:00 or 3pm\nWhich one?"
    assert m.validate({"reply": bad}, FACTS)[2] == "extra_time"


def test_missing_doctor_or_question_falls_back():
    assert m.validate({"reply": "1. Wednesday 23 September, 14:00\n2. Wednesday 23 September, 15:00\nWhich?"}, FACTS)[2] == "doctor_missing"
    assert m.validate({"reply": "Dr. Meera Rao: Wednesday 23 September, 14:00 and Wednesday 23 September, 15:00."}, FACTS)[2] == "no_question"
