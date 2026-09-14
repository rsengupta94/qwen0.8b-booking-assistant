"""yes_no: intent yes/no/other. Used at ASK_FIRST_CONSULT."""

VERSION = "1"
INTENTS = ["yes", "no", "other"]
MAX_TOKENS = 16


def schema(context: dict) -> dict:
    return {
        "type": "object",
        "properties": {"intent": {"type": "string", "enum": INTENTS}},
        "required": ["intent"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict) or output.get("intent") not in INTENTS:
        return fallback(context), False, "intent_not_in_enum"
    return {"intent": output["intent"]}, True, "ok"


def fallback(context: dict) -> dict:
    return {"intent": "other"}
