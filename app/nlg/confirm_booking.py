"""confirm_booking: state the booking. All record fields present, no other times or numbers."""

import re

from app.nlg import basic_checks, format_date, format_time, reply_schema, session_label, time_tokens

VERSION = "1"
MAX_CHARS = 320
MAX_TOKENS = 128


def inputs(facts: dict) -> dict:
    b = facts["booking"]
    return {
        "doctor_name": b["doctor_name"],
        "date": format_date(b["start"]),
        "time": format_time(b["start"]),
        "session": session_label(b["session_type"]),
        "booking_id": b["booking_id"],
    }


def schema(facts: dict) -> dict:
    return reply_schema(MAX_CHARS)


def validate(output, facts: dict) -> tuple[str, bool, str]:
    reply, reason = basic_checks(output, MAX_CHARS)
    if reply is None:
        return template(facts), False, reason
    i = inputs(facts)
    for key in ("doctor_name", "date", "time", "session", "booking_id"):
        if i[key] not in reply:
            return template(facts), False, f"{key}_missing"
    if time_tokens(reply) - {i["time"]}:
        return template(facts), False, "extra_time"
    allowed_digits = " ".join([i["date"], i["time"], i["booking_id"]])
    for run in re.findall(r"\d+", reply):
        if run not in allowed_digits:
            return template(facts), False, "extra_number"
    return reply, True, "ok"


def template(facts: dict) -> str:
    i = inputs(facts)
    return (f"You're booked with {i['doctor_name']} on {i['date']} at {i['time']} for a {i['session']}. "
            f"Your booking reference is {i['booking_id']}.")
