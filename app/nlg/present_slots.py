"""present_slots: offer the numbered slots. Every slot must appear, no other times may."""

from app.nlg import basic_checks, format_date, format_slot, format_time, reply_schema, time_tokens

VERSION = "2"
MAX_CHARS = 400
MAX_TOKENS = 160


def _lead(facts: dict) -> str:
    """Sentence before the list. Empty when there is nothing to acknowledge."""
    if facts.get("reask"):
        return "Sorry, I didn't catch which one."
    if facts.get("time_pref_missed"):
        return f"There are no {facts['time_pref_missed']} slots on those days, but here is what is open."
    return ""


def inputs(facts: dict) -> dict:
    return {
        "doctor_name": facts["doctor_name"],
        "slots": [format_slot(s) for s in facts["slots"]],
        "lead": _lead(facts),
    }


def schema(facts: dict) -> dict:
    return reply_schema(MAX_CHARS)


def validate(output, facts: dict) -> tuple[str, bool, str]:
    reply, reason = basic_checks(output, MAX_CHARS)
    if reply is None:
        return template(facts), False, reason
    allowed = set()
    for s in facts["slots"]:
        if format_date(s["start"]) not in reply or format_time(s["start"]) not in reply:
            return template(facts), False, "slot_missing"
        allowed.add(format_time(s["start"]))
    if time_tokens(reply) - allowed:
        return template(facts), False, "extra_time"
    if facts["doctor_name"] not in reply:
        return template(facts), False, "doctor_missing"
    if "?" not in reply:
        return template(facts), False, "no_question"
    if facts.get("time_pref_missed") and facts["time_pref_missed"] not in reply.lower():
        return template(facts), False, "missed_window_not_mentioned"
    return reply, True, "ok"


def template(facts: dict) -> str:
    i = inputs(facts)
    lead = i["lead"] + " " if i["lead"] else ""
    lines = "\n".join(f"{n}. {s}" for n, s in enumerate(i["slots"], 1))
    return f"{lead}{i['doctor_name']} is available at:\n{lines}\nWhich one would you like?"
