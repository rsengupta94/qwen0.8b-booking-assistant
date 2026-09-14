"""NLG modules: one per reply kind. Shared formatting lives here so the prompt, the
template and the validator all see the same strings for the same fact."""

import re
from datetime import datetime

# Any time-like token: 14:00, 2.30, 2pm, 2 pm, 10am
TIME_TOKEN_RE = re.compile(r"\b\d{1,2}[:.]\d{2}\b|\b\d{1,2}\s?(?:am|pm)\b", re.IGNORECASE)

SESSION_LABELS = {"first_consultation": "first consultation", "therapy": "therapy session", "followup": "follow-up"}


def format_date(iso: str) -> str:
    """'2026-09-16' or '2026-09-16T14:00' -> 'Wednesday 16 September'."""
    d = datetime.fromisoformat(iso)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def format_time(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%H:%M")


def format_slot(slot: dict) -> str:
    return f"{format_date(slot['start'])}, {format_time(slot['start'])}"


def session_label(session_type: str | None) -> str:
    return SESSION_LABELS.get(session_type or "", session_type or "session")


def time_tokens(text: str) -> set[str]:
    return {t.lower().replace(" ", "").replace(".", ":") for t in TIME_TOKEN_RE.findall(text)}


def reply_schema(max_chars: int) -> dict:
    return {
        "type": "object",
        "properties": {"reply": {"type": "string", "maxLength": max_chars}},
        "required": ["reply"],
        "additionalProperties": False,
    }


def basic_checks(output, max_chars: int) -> tuple[str | None, str]:
    """Shared shape checks. Returns (reply, 'ok') or (None, reason)."""
    if not isinstance(output, dict) or not isinstance(output.get("reply"), str):
        return None, "not_string"
    reply = output["reply"].strip()
    if not reply:
        return None, "empty"
    if len(reply) > max_chars:
        return None, "too_long"
    return reply, "ok"
