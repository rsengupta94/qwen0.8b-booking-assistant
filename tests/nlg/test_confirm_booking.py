from app.nlg import confirm_booking as m

FACTS = {"kind": "confirm_booking", "booking": {
    "booking_id": "b0001", "doctor_name": "Dr. Meera Rao", "start": "2026-09-23T14:00", "session_type": "first_consultation",
}}
GOOD = "Your first consultation with Dr. Meera Rao is booked for Wednesday 23 September at 14:00. Reference b0001."


def test_template_has_every_field():
    t = m.template(FACTS)
    for s in ("Dr. Meera Rao", "Wednesday 23 September", "14:00", "first consultation", "b0001"):
        assert s in t


def test_complete_reply_passes():
    assert m.validate({"reply": GOOD}, FACTS) == (GOOD, True, "ok")


def test_missing_field_falls_back():
    assert m.validate({"reply": GOOD.replace("b0001", "your reference")}, FACTS)[2] == "booking_id_missing"
    assert m.validate({"reply": GOOD.replace("14:00", "2pm")}, FACTS)[2] == "time_missing"


def test_extra_time_or_number_falls_back():
    assert m.validate({"reply": GOOD + " Please arrive by 13:45."}, FACTS)[2] == "extra_time"
    assert m.validate({"reply": GOOD + " Call 9876543210 to change."}, FACTS)[2] == "extra_number"
