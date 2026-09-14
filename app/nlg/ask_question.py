"""ask_question: phrase the next question, with an acknowledgement of what just happened."""

from app.nlg import basic_checks, reply_schema
from app.tools import fixtures

VERSION = "1"
MAX_CHARS = 240
MAX_TOKENS = 96
APOLOGY_MARKERS = ("sorry", "didn't catch", "did not catch", "apolog")

QUESTIONS = {
    "first_consult": "Is this your first consultation with us?",
    "problem": "Could you tell me briefly what you would like help with?",
    "doctor_pref": "Do you have a doctor in mind, or would you like us to suggest one?",
    "phone": "Could you share the phone number registered with us?",
    "session_type": "Is this a therapy session or a follow-up?",
    "days": "Which days work for you?",
}


def _note(facts: dict) -> str:
    """The situation to acknowledge before the question. Empty when there is none."""
    if facts.get("greeting"):
        return f"Welcome to {fixtures.clinic()['name']}."
    if facts.get("phone_not_found"):
        return "I couldn't find that number in our records, so let's set you up as a new patient."
    if facts.get("other_slots"):
        return "Sure, let's look at other days."
    reason = facts.get("reason", "")
    if reason == "doctor_not_found":
        return "I couldn't find a doctor by that name."
    if reason == "doctor_ambiguous":
        names = " and ".join(facts.get("candidates", []))
        return f"We have more than one doctor by that name: {names}."
    if facts.get("reask"):
        return "Sorry, I didn't catch that."
    return ""


def inputs(facts: dict) -> dict:
    question = QUESTIONS[facts["question"]]
    if facts.get("reason") == "doctor_ambiguous":
        question = "Which one would you like?"
    return {"note": _note(facts), "question": question}


def schema(facts: dict) -> dict:
    return reply_schema(MAX_CHARS)


def validate(output, facts: dict) -> tuple[str, bool, str]:
    reply, reason = basic_checks(output, MAX_CHARS)
    if reply is None:
        return template(facts), False, reason
    if "?" not in reply:
        return template(facts), False, "no_question"
    if inputs(facts)["question"] not in reply:
        return template(facts), False, "question_altered"
    if facts.get("greeting") and fixtures.clinic()["name"] not in reply:
        return template(facts), False, "clinic_name_missing"
    if not _note(facts) and any(m in reply.lower() for m in APOLOGY_MARKERS):
        return template(facts), False, "false_apology"  # nothing went wrong, so no apology
    for name in facts.get("candidates", []):
        if name not in reply:
            return template(facts), False, "candidate_missing"
    return reply, True, "ok"


def template(facts: dict) -> str:
    i = inputs(facts)
    return f"{i['note']} {i['question']}".strip()
