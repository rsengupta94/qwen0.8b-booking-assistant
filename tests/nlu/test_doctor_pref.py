from app.nlu import doctor_pref as m


def test_named_with_name_passes():
    assert m.validate({"mode": "named", "doctor_name": " Dr Rao "}, {}) == ({"mode": "named", "doctor_name": "Dr Rao"}, True, "ok")


def test_named_without_name_falls_back():
    assert m.validate({"mode": "named", "doctor_name": None}, {}) == ({"mode": "other", "doctor_name": None}, False, "named_without_name")


def test_you_decide_drops_stray_name():
    assert m.validate({"mode": "you_decide", "doctor_name": "Rao"}, {}) == ({"mode": "you_decide", "doctor_name": None}, True, "ok")


def test_bad_mode_falls_back():
    assert m.validate({"mode": "x", "doctor_name": None}, {})[1:] == (False, "mode_not_in_enum")


def test_schema_puts_name_before_mode():
    assert list(m.schema({})["properties"]) == ["doctor_name", "mode"]


def test_named_is_removed_from_enum_when_no_roster_name_in_text():
    assert m.schema({"name_in_text": False})["properties"]["mode"]["enum"] == ["you_decide", "other"]
    assert m.schema({"name_in_text": True})["properties"]["mode"]["enum"] == ["named", "you_decide", "other"]
    # even if a model somehow returned "named" with no roster name, the validator rejects it
    assert m.validate({"mode": "named", "doctor_name": "Dr Nobody"}, {"name_in_text": False})[1:] == (False, "mode_not_in_enum")
