"""no_slots: say the doctor has nothing on the days tried and ask for other days."""

from app.nlg import basic_checks, format_date, reply_schema
from app.tools import fixtures

VERSION = "1"
MAX_CHARS = 240
MAX_TOKENS = 96


def inputs(facts: dict) -> dict:
    doctor = fixtures.doctor_by_id(facts["doctor_id"]) if facts.get("doctor_id") else None
    return {
        "doctor_name": doctor["name"] if doctor else "the doctor",
        "days": [format_date(d) for d in facts["days"]],
    }


def schema(facts: dict) -> dict:
    return reply_schema(MAX_CHARS)


def validate(output, facts: dict) -> tuple[str, bool, str]:
    reply, reason = basic_checks(output, MAX_CHARS)
    if reply is None:
        return template(facts), False, reason
    if "?" not in reply:
        return template(facts), False, "no_question"
    i = inputs(facts)
    if i["doctor_name"] not in reply:
        return template(facts), False, "doctor_missing"
    for day in i["days"]:
        if day not in reply:
            return template(facts), False, "day_missing"
    return reply, True, "ok"


def template(facts: dict) -> str:
    i = inputs(facts)
    days = " or ".join(i["days"]) if len(i["days"]) <= 2 else ", ".join(i["days"][:-1]) + " or " + i["days"][-1]
    return f"Sorry, {i['doctor_name']} has no free slots on {days}. Would another day work for you?"
