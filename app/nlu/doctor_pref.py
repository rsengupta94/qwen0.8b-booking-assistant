"""doctor_pref: named / you_decide / other, plus the name as said. Used at ASK_DOCTOR_PREF."""

VERSION = "1"
MODES = ["named", "you_decide", "other"]
MAX_TOKENS = 48


def schema(context: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": MODES},
            "doctor_name": {"type": ["string", "null"], "maxLength": 60},
        },
        "required": ["mode", "doctor_name"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict) or output.get("mode") not in MODES:
        return fallback(context), False, "mode_not_in_enum"
    name = output.get("doctor_name")
    if output["mode"] == "named":
        if not isinstance(name, str) or not name.strip():
            return fallback(context), False, "named_without_name"
        return {"mode": "named", "doctor_name": name.strip()}, True, "ok"
    return {"mode": output["mode"], "doctor_name": None}, True, "ok"


def fallback(context: dict) -> dict:
    return {"mode": "other", "doctor_name": None}
