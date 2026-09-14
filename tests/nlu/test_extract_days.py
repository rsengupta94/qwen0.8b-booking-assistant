from app.nlu import extract_days as m

CTX = {"day_terms": ["today", "tomorrow", "monday", "tuesday"]}


def test_valid_days_lowercased_and_deduped():
    out, ok, _ = m.validate({"time_pref": "morning", "days": ["Monday", "monday", "today"]}, CTX)
    assert ok and out == {"days": ["monday", "today"], "time_pref": "morning"}


def test_day_outside_enum_falls_back():
    assert m.validate({"time_pref": None, "days": ["someday"]}, CTX) == ({"days": [], "time_pref": None}, False, "day_not_in_enum")


def test_empty_days_falls_back():
    assert m.validate({"time_pref": None, "days": []}, CTX)[2] == "no_days"


def test_bad_time_pref_falls_back():
    assert m.validate({"time_pref": "noon", "days": ["monday"]}, CTX)[2] == "time_pref_not_in_enum"


def test_schema_time_pref_first_and_enum_from_context():
    s = m.schema(CTX)
    assert list(s["properties"]) == ["time_pref", "days"]
    assert s["properties"]["days"]["items"]["enum"] == CTX["day_terms"]
