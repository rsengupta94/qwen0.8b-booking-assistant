"""turn_classifier: is this turn a correction of an earlier answer? Runs before state NLU; see state_machine.step()."""

VERSION = "1"
FIELDS = ["doctor", "days", "session_type", "phone", "problem"]
MAX_TOKENS = 48


def schema(context: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "is_correction": {"type": "boolean"},
            "correction_field": {"type": ["string", "null"], "enum": FIELDS + [None]},
            "new_value": {"type": ["string", "null"], "maxLength": 100},
        },
        "required": ["is_correction", "correction_field", "new_value"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict) or not isinstance(output.get("is_correction"), bool):
        return fallback(context), False, "not_object"
    field = output.get("correction_field")
    value = output.get("new_value")
    if not output["is_correction"]:
        return fallback(context), True, "ok"
    if field not in FIELDS:
        return fallback(context), False, "field_not_in_enum"
    if not isinstance(value, str) or not value.strip():
        return fallback(context), False, "correction_without_value"
    return {"is_correction": True, "correction_field": field, "new_value": value.strip()}, True, "ok"


def fallback(context: dict) -> dict:
    """Safe default: treat the turn as a normal answer."""
    return {"is_correction": False, "correction_field": None, "new_value": None}
