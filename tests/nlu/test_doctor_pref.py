from app.nlu import doctor_pref as m


def test_named_with_name_passes():
    assert m.validate({"mode": "named", "doctor_name": " Dr Rao "}, {}) == ({"mode": "named", "doctor_name": "Dr Rao"}, True, "ok")


def test_named_without_name_falls_back():
    assert m.validate({"mode": "named", "doctor_name": None}, {}) == ({"mode": "other", "doctor_name": None}, False, "named_without_name")


def test_you_decide_drops_stray_name():
    assert m.validate({"mode": "you_decide", "doctor_name": "Rao"}, {}) == ({"mode": "you_decide", "doctor_name": None}, True, "ok")


def test_bad_mode_falls_back():
    assert m.validate({"mode": "x", "doctor_name": None}, {})[1:] == (False, "mode_not_in_enum")
