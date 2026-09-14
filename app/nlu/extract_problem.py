"""extract_problem: one-line summary plus a category from the fixture enum. Used at ASK_PROBLEM."""

VERSION = "1"
MAX_SUMMARY_CHARS = 200
MAX_TOKENS = 96


def schema(context: dict) -> dict:
    return {
        "type": "object",
        # category first: the model decides the category before it writes the summary
        "properties": {
            "category": {"type": "string", "enum": list(context["categories"])},
            "summary": {"type": "string", "maxLength": MAX_SUMMARY_CHARS},
        },
        "required": ["category", "summary"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict):
        return fallback(context), False, "not_object"
    summary = output.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return fallback(context), False, "empty_summary"
    if len(summary) > MAX_SUMMARY_CHARS:
        return fallback(context), False, "summary_too_long"
    if output.get("category") not in context["categories"]:
        return fallback(context), False, "category_not_in_enum"
    return {"summary": summary.strip(), "category": output["category"]}, True, "ok"


def fallback(context: dict) -> dict:
    """Keep the user's own words as the summary; no category means the shortlist is every doctor."""
    return {"summary": context.get("user_text", "")[:MAX_SUMMARY_CHARS], "category": None}
