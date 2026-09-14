"""extract_days: list of day terms plus an optional time preference. Used at ASK_DAYS.

Day terms are the enum the state machine passes in context (today, tomorrow, day_after_tomorrow,
weekday names). Code turns them into dates.
"""

VERSION = "1"
TIME_PREFS = ["morning", "afternoon", "evening"]
MAX_TOKENS = 64


def schema(context: dict) -> dict:
    return {
        "type": "object",
        # time_pref first: the model reads the whole reply before it lists days
        "properties": {
            "time_pref": {"type": ["string", "null"], "enum": TIME_PREFS + [None]},
            "days": {"type": "array", "items": {"type": "string", "enum": list(context["day_terms"])}, "maxItems": 7},
        },
        "required": ["time_pref", "days"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict) or not isinstance(output.get("days"), list):
        return fallback(context), False, "not_object"
    terms = set(context["day_terms"])
    days = []
    for d in output["days"]:
        if not isinstance(d, str) or d.lower() not in terms:
            return fallback(context), False, "day_not_in_enum"
        if d.lower() not in days:
            days.append(d.lower())
    if not days:
        return fallback(context), False, "no_days"
    pref = output.get("time_pref")
    if pref is not None and pref not in TIME_PREFS:
        return fallback(context), False, "time_pref_not_in_enum"
    return {"days": days, "time_pref": pref}, True, "ok"


def fallback(context: dict) -> dict:
    return {"days": [], "time_pref": None}
