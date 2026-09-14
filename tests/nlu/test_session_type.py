from app.nlu import session_type as m


def test_valid_types_pass():
    for t in ("therapy", "followup", "other"):
        assert m.validate({"type": t}, {}) == ({"type": t}, True, "ok")


def test_bad_type_falls_back_to_other():
    assert m.validate({"type": "checkup"}, {}) == ({"type": "other"}, False, "type_not_in_enum")
