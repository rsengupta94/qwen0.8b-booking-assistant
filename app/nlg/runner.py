"""Propose, validate, fallback, log for NLG. One model call per reply, or none for template-only kinds."""

import time

from app import llm_client, logging, prompts
from app.nlg import ask_question, clarify, confirm_booking, handoff, no_slots, present_slots
from app.session import Session

MODULES = {
    "ask_question": ask_question,
    "present_slots": present_slots,
    "no_slots": no_slots,
    "confirm_booking": confirm_booking,
    "clarify": clarify,
}
TEMPLATE_ONLY = {"handoff", "ended"}


def render_reply(facts: dict, session: Session, model_id: str, prompt_version: str) -> tuple[str, dict | None]:
    """Returns (reply_text, debug). debug is None for template-only kinds."""
    kind = facts["kind"]
    if kind in TEMPLATE_ONLY:
        return handoff.template(facts), None
    module = MODULES[kind]
    inputs = module.inputs(facts)
    prompt = prompts.render(prompt_version, "nlg", kind, **inputs)

    raw, output, latency_ms, error = "", None, 0, None
    started = time.perf_counter()
    try:
        r = llm_client.complete(model_id, prompt, module.schema(facts), {"max_tokens": module.MAX_TOKENS})
        raw, output, latency_ms = r["raw"], r["output"], r["latency_ms"]
    except Exception as e:
        latency_ms = int((time.perf_counter() - started) * 1000)
        error = f"{type(e).__name__}: {e}"[:200]

    if error:
        reply, ok, reason = module.template(facts), False, "model_error"
    else:
        reply, ok, reason = module.validate(output, facts)

    logging.write({
        "session_id": session.session_id,
        "turn": session.turn,
        "state": str(session.state),
        "model_id": model_id,
        "prompt_name": kind,
        "prompt_version": prompt_version,
        "validator_version": module.VERSION,
        "ok": ok,
        "reason_code": reason,
        "raw_output": raw if not error else error,
        "latency_ms": latency_ms,
    })
    return reply, {"prompt_name": kind, "ok": ok, "reason_code": reason, "raw_output": raw, "latency_ms": latency_ms}
