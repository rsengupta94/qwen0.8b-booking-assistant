"""session_type: therapy / followup / other. Used at ASK_SESSION_TYPE (returning patients)."""

VERSION = "1"
TYPES = ["therapy", "followup", "other"]
MAX_TOKENS = 16


def schema(context: dict) -> dict:
    return {
        "type": "object",
        "properties": {"type": {"type": "string", "enum": TYPES}},
        "required": ["type"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict) or output.get("type") not in TYPES:
        return fallback(context), False, "type_not_in_enum"
    return {"type": output["type"]}, True, "ok"


def fallback(context: dict) -> dict:
    return {"type": "other"}
