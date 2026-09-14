from app.nlu import off_script as m


def test_question_with_topic_passes_lowercased():
    assert m.validate({"is_question": True, "topic": " Fees "}, {}) == ({"is_question": True, "topic": "fees"}, True, "ok")


def test_not_a_question_normalises():
    assert m.validate({"is_question": False, "topic": "fees"}, {}) == ({"is_question": False, "topic": None}, True, "ok")


def test_bad_shape_falls_back():
    assert m.validate({"is_question": "yes", "topic": None}, {}) == ({"is_question": False, "topic": None}, False, "not_object")
