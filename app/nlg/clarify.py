"""clarify: answer a FAQ question verbatim, then re-ask the pending question. Wired in Phase 5."""

from app.nlg import basic_checks, reply_schema

VERSION = "1"
MAX_CHARS = 320
MAX_TOKENS = 128


def inputs(facts: dict) -> dict:
    return {"faq_answer": facts.get("faq_answer") or "", "question": facts["question"]}


def schema(facts: dict) -> dict:
    return reply_schema(MAX_CHARS)


def validate(output, facts: dict) -> tuple[str, bool, str]:
    reply, reason = basic_checks(output, MAX_CHARS)
    if reply is None:
        return template(facts), False, reason
    i = inputs(facts)
    if i["faq_answer"] and i["faq_answer"] not in reply:
        return template(facts), False, "faq_answer_altered"
    if "?" not in reply:
        return template(facts), False, "no_question"
    return reply, True, "ok"


def template(facts: dict) -> str:
    i = inputs(facts)
    if i["faq_answer"]:
        return f"{i['faq_answer']} {i['question']}"
    return f"I can only help with booking appointments here. {i['question']}"
