"""slot_choice: 1-based index into the offered slots, or a request for other slots. Used at CAPTURE_CHOICE."""

VERSION = "1"
MAX_TOKENS = 48


def schema(context: dict) -> dict:
    n = max(len(context["offered_slots"]), 1)
    return {
        "type": "object",
        "properties": {
            "choice_index": {"type": ["integer", "null"], "minimum": 1, "maximum": n},
            "wants_other": {"type": "boolean"},
            "other": {"type": ["string", "null"], "maxLength": 100},
        },
        "required": ["choice_index", "wants_other", "other"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict):
        return fallback(context), False, "not_object"
    n = len(context["offered_slots"])
    idx = output.get("choice_index")
    wants_other = output.get("wants_other")
    if not isinstance(wants_other, bool):
        return fallback(context), False, "wants_other_not_bool"
    if idx is not None:
        if isinstance(idx, bool) or not isinstance(idx, int) or not (1 <= idx <= n):
            return fallback(context), False, "index_out_of_range"
        if wants_other:
            return fallback(context), False, "index_and_wants_other"
    other = output.get("other")
    if other is not None and not isinstance(other, str):
        return fallback(context), False, "other_not_string"
    return {"choice_index": idx, "wants_other": wants_other, "other": other}, True, "ok"


def fallback(context: dict) -> dict:
    """No choice, no request: the state machine re-presents the same slots."""
    return {"choice_index": None, "wants_other": False, "other": None}
