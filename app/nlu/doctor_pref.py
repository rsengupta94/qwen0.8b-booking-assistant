"""doctor_pref: named / you_decide / other, plus the name as said. Used at ASK_DOCTOR_PREF.

v2: the schema is narrowed by what code already knows. `doctor_name` comes before `mode` so the
model writes the evidence before the label, and "named" is only in the enum when the state
machine found a roster name in the user text (context["name_in_text"]). Constrained decoding then
cannot produce "named" with no name.
"""

VERSION = "2"
MODES = ["named", "you_decide", "other"]
MAX_TOKENS = 48


def _allowed_modes(context: dict) -> list[str]:
    return MODES if context.get("name_in_text", True) else [m for m in MODES if m != "named"]


def schema(context: dict) -> dict:
    return {
        "type": "object",
        # doctor_name first: the model states the name (or null) before it picks the mode
        "properties": {
            "doctor_name": {"type": ["string", "null"], "maxLength": 60},
            "mode": {"type": "string", "enum": _allowed_modes(context)},
        },
        "required": ["doctor_name", "mode"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict) or output.get("mode") not in _allowed_modes(context):
        return fallback(context), False, "mode_not_in_enum"
    name = output.get("doctor_name")
    if output["mode"] == "named":
        if not isinstance(name, str) or not name.strip():
            return fallback(context), False, "named_without_name"
        return {"mode": "named", "doctor_name": name.strip()}, True, "ok"
    return {"mode": output["mode"], "doctor_name": None}, True, "ok"


def fallback(context: dict) -> dict:
    return {"mode": "other", "doctor_name": None}
