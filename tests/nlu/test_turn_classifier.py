from app.nlu import turn_classifier as m

NOT = {"is_correction": False, "correction_field": None, "new_value": None}


def test_correction_with_field_and_value_passes():
    out, ok, _ = m.validate({"is_correction": True, "correction_field": "days", "new_value": " Wednesday "}, {})
    assert ok and out == {"is_correction": True, "correction_field": "days", "new_value": "Wednesday"}


def test_not_a_correction_normalises_to_safe_default():
    assert m.validate({"is_correction": False, "correction_field": "days", "new_value": "x"}, {}) == (NOT, True, "ok")


def test_correction_without_field_or_value_falls_back():
    assert m.validate({"is_correction": True, "correction_field": None, "new_value": "x"}, {}) == (NOT, False, "field_not_in_enum")
    assert m.validate({"is_correction": True, "correction_field": "doctor", "new_value": ""}, {})[2] == "correction_without_value"
