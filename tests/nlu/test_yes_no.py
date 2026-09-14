from app.nlu import yes_no as m


def test_valid_intents_pass():
    for i in ("yes", "no", "other"):
        assert m.validate({"intent": i}, {}) == ({"intent": i}, True, "ok")


def test_bad_intent_falls_back_to_other():
    assert m.validate({"intent": "maybe"}, {}) == ({"intent": "other"}, False, "intent_not_in_enum")
    assert m.validate(None, {}) == ({"intent": "other"}, False, "intent_not_in_enum")


def test_schema_enum_and_version():
    assert m.schema({})["properties"]["intent"]["enum"] == ["yes", "no", "other"]
    assert m.VERSION
