from app.nlg import present_slots as m

FACTS = {
    "kind": "present_slots", "doctor_name": "Dr. Meera Rao",
    "slots": [{"start": "2026-09-23T14:00"}, {"start": "2026-09-23T15:00"}],
}
LIST = "1. Wednesday 23 September, 14:00\n2. Wednesday 23 September, 15:00"
TEMPLATE = f"Dr. Meera Rao is available at:\n{LIST}\nWhich one would you like?"


def test_template_lists_every_slot():
    assert m.template(FACTS) == TEMPLATE


def test_reply_with_all_slots_passes():
    good = f"Dr. Meera Rao can see you on:\n{LIST}\nWhich suits you?"
    assert m.validate({"reply": good}, FACTS) == (good, True, "ok")


def test_fake_slot_falls_back_to_template():
    fake = f"Dr. Meera Rao is available at:\n{LIST}\n3. Thursday 24 September, 16:00\nWhich one?"
    assert m.validate({"reply": fake}, FACTS) == (TEMPLATE, False, "extra_time")


def test_dropped_slot_falls_back():
    assert m.validate({"reply": "Dr. Meera Rao is free Wednesday 23 September, 14:00. OK?"}, FACTS)[2] == "slot_missing"


def test_altered_time_format_is_caught():
    bad = f"Dr. Meera Rao is available at:\n{LIST} or 3pm\nWhich one?"
    assert m.validate({"reply": bad}, FACTS)[2] == "extra_time"


def test_missing_doctor_or_question_falls_back():
    assert m.validate({"reply": f"{LIST}\nWhich?"}, FACTS)[2] == "doctor_missing"
    assert m.validate({"reply": "Dr. Meera Rao: Wednesday 23 September, 14:00 and Wednesday 23 September, 15:00."}, FACTS)[2] == "no_question"


def test_reask_lead():
    facts = {**FACTS, "reask": True, "reason": "no_valid_choice"}
    assert m.template(facts).startswith("Sorry, I didn't catch which one. Dr. Meera Rao is available at:")
    assert m.inputs(facts)["lead"] == "Sorry, I didn't catch which one."


def test_time_pref_missed_lead_and_check():
    facts = {**FACTS, "time_pref_missed": "morning"}
    t = m.template(facts)
    assert t.startswith("There are no morning slots on those days, but here is what is open. Dr. Meera Rao is available at:")
    out, ok, reason = m.validate({"reply": TEMPLATE}, facts)  # model dropped the missed-window note
    assert (ok, reason) == (False, "missed_window_not_mentioned") and out == t
    good = f"No morning slots, but Dr. Meera Rao is available at:\n{LIST}\nWhich one would you like?"
    assert m.validate({"reply": good}, facts) == (good, True, "ok")
