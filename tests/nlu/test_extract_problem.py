from app.nlu import extract_problem as m

CTX = {"categories": ["anxiety", "sleep"], "user_text": "I cannot sleep"}


def test_valid_output_passes_and_strips():
    out, ok, reason = m.validate({"category": "sleep", "summary": "  cannot sleep "}, CTX)
    assert (out, ok, reason) == ({"summary": "cannot sleep", "category": "sleep"}, True, "ok")


def test_category_outside_fixture_enum_falls_back():
    out, ok, reason = m.validate({"category": "stress", "summary": "x"}, CTX)
    assert not ok and reason == "category_not_in_enum"
    assert out == {"summary": "I cannot sleep", "category": None}


def test_empty_or_long_summary_falls_back():
    assert m.validate({"category": "sleep", "summary": "  "}, CTX)[2] == "empty_summary"
    assert m.validate({"category": "sleep", "summary": "x" * 201}, CTX)[2] == "summary_too_long"


def test_schema_uses_context_categories_category_first():
    s = m.schema(CTX)
    assert s["properties"]["category"]["enum"] == ["anxiety", "sleep"]
    assert list(s["properties"]) == ["category", "summary"]
