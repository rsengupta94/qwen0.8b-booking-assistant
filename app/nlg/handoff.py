"""handoff and ended: fixed templates, no model call (design.md section 2)."""

from app.tools import fixtures

VERSION = "1"


def template(facts: dict) -> str:
    if facts["kind"] == "ended":
        return "This conversation has ended. Please start a new session to book another appointment."
    phone = fixtures.clinic()["customer_care_phone"]
    return (f"Sorry, I wasn't able to understand your request. "
            f"Please call our customer care team on {phone} and they will help you book an appointment.")
