from app.nlu import doctor_pick as m

SHORTLIST = [
    {"id": "d_a", "categories": ["sleep", "stress"]},
    {"id": "d_b", "categories": ["sleep"]},
]
CTX = {"shortlist": SHORTLIST, "category": "sleep"}


def test_pick_in_shortlist_with_reason_passes():
    assert m.validate({"doctor_id": "d_b", "reason": "sleep expert"}, CTX) == ({"doctor_id": "d_b", "reason": "sleep expert"}, True, "ok")


def test_pick_outside_shortlist_falls_back_to_top_candidate():
    assert m.validate({"doctor_id": "d_z", "reason": "x"}, CTX) == ({"doctor_id": "d_a", "reason": None}, False, "doctor_not_in_shortlist")


def test_category_mismatch_falls_back():
    ctx = {"shortlist": SHORTLIST, "category": "stress"}
    assert m.validate({"doctor_id": "d_b", "reason": "x"}, ctx)[2] == "category_mismatch"


def test_no_category_skips_overlap_check():
    ctx = {"shortlist": SHORTLIST, "category": None}
    assert m.validate({"doctor_id": "d_b", "reason": "x"}, ctx)[1] is True


def test_empty_reason_falls_back():
    assert m.validate({"doctor_id": "d_b", "reason": ""}, CTX)[2] == "empty_reason"


def test_schema_enum_is_shortlist_ids():
    assert m.schema(CTX)["properties"]["doctor_id"]["enum"] == ["d_a", "d_b"]
