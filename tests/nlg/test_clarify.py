from app.nlg import clarify as m

FACTS = {"kind": "clarify", "faq_answer": "A session costs 1500 rupees.", "question": "Which days work for you?"}


def test_template_is_answer_then_question():
    assert m.template(FACTS) == "A session costs 1500 rupees. Which days work for you?"


def test_altered_answer_falls_back():
    assert m.validate({"reply": "A session costs 1200 rupees. Which days work for you?"}, FACTS)[2] == "faq_answer_altered"


def test_verbatim_answer_passes():
    r = "Sure: A session costs 1500 rupees. Now, which days work for you?"
    assert m.validate({"reply": r}, FACTS) == (r, True, "ok")


def test_no_faq_hit_uses_generic_line():
    assert m.template({"kind": "clarify", "faq_answer": None, "question": "Which days work for you?"}).startswith("I can only help with booking")
