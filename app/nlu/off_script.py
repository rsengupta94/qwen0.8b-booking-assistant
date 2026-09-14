"""off_script: is the user asking the clinic a question instead of answering? Wired in Phase 5."""

VERSION = "1"
MAX_TOKENS = 32


def schema(context: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "is_question": {"type": "boolean"},
            "topic": {"type": ["string", "null"], "maxLength": 40},
        },
        "required": ["is_question", "topic"],
        "additionalProperties": False,
    }


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict) or not isinstance(output.get("is_question"), bool):
        return fallback(context), False, "not_object"
    topic = output.get("topic")
    if topic is not None and not isinstance(topic, str):
        return fallback(context), False, "topic_not_string"
    if not output["is_question"]:
        return fallback(context), True, "ok"
    return {"is_question": True, "topic": (topic or "").strip().lower() or None}, True, "ok"


def fallback(context: dict) -> dict:
    return {"is_question": False, "topic": None}
