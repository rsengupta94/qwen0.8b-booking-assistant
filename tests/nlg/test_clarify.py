from app.nlg import clarify as m

Q = "Which days work for you?"
FACTS = {"kind": "clarify", "faq_answer": "A session costs 1500 rupees.", "question": "days", "topic": "fees"}


def test_template_is_answer_then_question():
    assert m.template(FACTS) == "A session costs 1500 rupees. " + Q


def test_altered_answer_falls_back():
    assert m.validate({"reply": "A session costs 1200 rupees. " + Q}, FACTS)[2] == "faq_answer_altered"


def test_verbatim_answer_passes():
    r = "Sure: A session costs 1500 rupees. Now, " + Q[0].lower() + Q[1:]
    assert m.validate({"reply": r}, FACTS)[2] == "question_altered"  # question must appear word for word
    r = "Sure: A session costs 1500 rupees. " + Q
    assert m.validate({"reply": r}, FACTS) == (r, True, "ok")


def test_missing_question_falls_back():
    out, ok, reason = m.validate({"reply": "A session costs 1500 rupees."}, FACTS)
    assert (ok, reason) == (False, "question_altered") and out == m.template(FACTS)


def test_no_faq_hit_uses_generic_line():
    facts = {"kind": "clarify", "faq_answer": None, "question": "days", "topic": "parking"}
    assert m.template(facts) == m.NO_FAQ_LINE + " " + Q
    assert m.validate({"reply": "Good question! " + Q}, facts)[1] is True


def test_slot_choice_question_resolves():
    facts = {"kind": "clarify", "faq_answer": None, "question": "slot_choice", "topic": None}
    assert m.template(facts).endswith("Which one would you like?")
