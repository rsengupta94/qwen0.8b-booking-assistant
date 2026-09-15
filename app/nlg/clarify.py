"""clarify: answer a FAQ question verbatim, then re-ask the pending question.

Facts: question (intent key, same as ask_question facts), faq_answer (fixture text or None).
"""

from app.nlg import ask_question, basic_checks, reply_schema

VERSION = "2"
MAX_CHARS = 320
MAX_TOKENS = 128
NO_FAQ_LINE = "I can only help with booking appointments here."

QUESTIONS = {**ask_question.QUESTIONS, "slot_choice": "Which one would you like?"}


def inputs(facts: dict) -> dict:
    return {"faq_answer": facts.get("faq_answer") or "", "question": QUESTIONS[facts["question"]]}


def schema(facts: dict) -> dict:
    return reply_schema(MAX_CHARS)


def validate(output, facts: dict) -> tuple[str, bool, str]:
    reply, reason = basic_checks(output, MAX_CHARS)
    if reply is None:
        return template(facts), False, reason
    i = inputs(facts)
    if i["faq_answer"] and i["faq_answer"] not in reply:
        return template(facts), False, "faq_answer_altered"
    if i["question"] not in reply:
        return template(facts), False, "question_altered"
    return reply, True, "ok"


def template(facts: dict) -> str:
    i = inputs(facts)
    if i["faq_answer"]:
        return f"{i['faq_answer']} {i['question']}"
    return f"{NO_FAQ_LINE} {i['question']}"
