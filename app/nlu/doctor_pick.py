"""doctor_pick: choose a doctor_id from the shortlist with a reason. Used at PICK_DOCTOR.

design.md section 5: the chosen doctor's tags must overlap the category. The shortlist is
already filtered by category, so a mismatch can only happen when the filter fell back to
all doctors (no category). In that case any shortlist member is accepted.
"""

VERSION = "1"
MAX_TOKENS = 96


def schema(context: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "doctor_id": {"type": "string", "enum": [d["id"] for d in context["shortlist"]]},
            "reason": {"type": "string", "maxLength": 200},
        },
        "required": ["doctor_id", "reason"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    shortlist = context["shortlist"]
    by_id = {d["id"]: d for d in shortlist}
    if not isinstance(output, dict) or output.get("doctor_id") not in by_id:
        return fallback(context), False, "doctor_not_in_shortlist"
    category = context.get("category")
    if category and category not in by_id[output["doctor_id"]]["categories"]:
        return fallback(context), False, "category_mismatch"
    reason = output.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return fallback(context), False, "empty_reason"
    return {"doctor_id": output["doctor_id"], "reason": reason.strip()}, True, "ok"


def fallback(context: dict) -> dict:
    """Code's top candidate: first in the shortlist."""
    return {"doctor_id": context["shortlist"][0]["id"], "reason": None}
