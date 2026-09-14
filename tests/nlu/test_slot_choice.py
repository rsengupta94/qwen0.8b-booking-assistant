from app.nlu import slot_choice as m

CTX = {"offered_slots": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
FALLBACK = {"choice_index": None, "wants_other": False, "other": None}


def test_valid_index_passes():
    assert m.validate({"choice_index": 2, "wants_other": False, "other": None}, CTX)[0]["choice_index"] == 2


def test_wants_other_passes():
    out, ok, _ = m.validate({"choice_index": None, "wants_other": True, "other": "evening"}, CTX)
    assert ok and out == {"choice_index": None, "wants_other": True, "other": "evening"}


def test_index_out_of_range_falls_back():
    assert m.validate({"choice_index": 4, "wants_other": False, "other": None}, CTX) == (FALLBACK, False, "index_out_of_range")
    assert m.validate({"choice_index": 0, "wants_other": False, "other": None}, CTX)[2] == "index_out_of_range"


def test_index_and_wants_other_together_falls_back():
    assert m.validate({"choice_index": 1, "wants_other": True, "other": None}, CTX)[2] == "index_and_wants_other"


def test_schema_maximum_matches_offer_size():
    assert m.schema(CTX)["properties"]["choice_index"]["maximum"] == 3
