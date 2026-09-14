from app.nlg import ask_question as m

Q = "Is this your first consultation with us?"


def test_greeting_template_has_clinic_name_and_question():
    t = m.template({"kind": "ask_question", "question": "first_consult", "greeting": True})
    assert "Willow Lane" in t and t.endswith(Q)


def test_valid_reply_passes():
    assert m.validate({"reply": "Hello! " + Q}, {"question": "first_consult"}) == ("Hello! " + Q, True, "ok")


def test_missing_question_mark_falls_back_to_template():
    out, ok, reason = m.validate({"reply": "Tell me about your first consultation."}, {"question": "first_consult"})
    assert (ok, reason) == (False, "no_question") and out == Q


def test_too_long_falls_back():
    assert m.validate({"reply": "x" * 241 + "?"}, {"question": "days"})[2] == "too_long"


def test_ambiguous_doctor_needs_every_candidate():
    facts = {"question": "doctor_pref", "reask": True, "reason": "doctor_ambiguous", "candidates": ["Dr. Meera Rao", "Dr. Anil Rao"]}
    assert m.validate({"reply": "Did you mean Dr. Meera Rao? Which one would you like?"}, facts)[2] == "candidate_missing"
    t = m.template(facts)
    assert "Dr. Meera Rao and Dr. Anil Rao" in t and t.endswith("Which one would you like?")


def test_reask_and_phone_not_found_notes():
    assert m.template({"question": "phone", "reask": True, "reason": "no_phone"}).startswith("Sorry, I didn't catch that.")
    assert "new patient" in m.template({"question": "problem", "phone_not_found": True})


def test_wrong_question_falls_back():
    facts = {"question": "days"}
    out, ok, reason = m.validate({"reply": "Welcome! Is this your first consultation with us?"}, facts)
    assert (ok, reason) == (False, "question_altered") and out == "Which days work for you?"


def test_greeting_without_clinic_name_falls_back():
    assert m.validate({"reply": "Hi! " + Q}, {"question": "first_consult", "greeting": True})[2] == "clinic_name_missing"


def test_apology_without_a_reask_falls_back():
    out, ok, reason = m.validate({"reply": "I'm sorry, I didn't catch that. Which days work for you?"}, {"question": "days"})
    assert (ok, reason) == (False, "false_apology") and out == "Which days work for you?"
    assert m.validate({"reply": "Sorry, I didn't catch that. Which days work for you?"}, {"question": "days", "reask": True, "reason": "no_days"})[1] is True
