"""Propose, validate, fallback, log. One model call per invocation.

NLURunner is the `nlu` callable the state machine receives. For each call it renders the
prompt for `prompt_version`, runs constrained decoding against the module's schema,
validates the output, substitutes the module's fallback on failure, and writes one JSONL
log line. Per-turn debug info accumulates in `turn_debug` for the API response.
"""

import time
from types import ModuleType

from app import llm_client, logging, prompts
from app.nlu import (
    doctor_pick, doctor_pref, extract_days, extract_phone, extract_problem,
    off_script, session_type, slot_choice, turn_classifier, yes_no,
)
from app.session import Session

MODULES: dict[str, ModuleType] = {
    "yes_no": yes_no,
    "extract_problem": extract_problem,
    "doctor_pref": doctor_pref,
    "doctor_pick": doctor_pick,
    "extract_phone": extract_phone,
    "session_type": session_type,
    "extract_days": extract_days,
    "slot_choice": slot_choice,
    "turn_classifier": turn_classifier,
    "off_script": off_script,
}


class NLURunner:
    def __init__(self, model_id: str, prompt_version: str):
        self.model_id = model_id
        self.prompt_version = prompt_version
        self.turn_debug: list[dict] = []

    def start_turn(self) -> None:
        self.turn_debug = []

    def __call__(self, prompt_name: str, session: Session, text: str, context: dict) -> dict:
        module = MODULES[prompt_name]
        ctx = {**context, "user_text": text, "category": session.category}
        prompt = prompts.render(self.prompt_version, "nlu", prompt_name, **ctx)
        schema = module.schema(ctx)

        raw, output, latency_ms, error = "", None, 0, None
        started = time.perf_counter()
        try:
            r = llm_client.complete(self.model_id, prompt, schema, {"max_tokens": module.MAX_TOKENS})
            raw, output, latency_ms = r["raw"], r["output"], r["latency_ms"]
        except Exception as e:  # model or parse failure: never crash, fall back
            latency_ms = int((time.perf_counter() - started) * 1000)
            error = f"{type(e).__name__}: {e}"[:200]

        if error:
            result, ok, reason = module.fallback(ctx), False, "model_error"
        else:
            result, ok, reason = module.validate(output, ctx)

        logging.write({
            "session_id": session.session_id,
            "turn": session.turn,
            "state": str(session.state),
            "model_id": self.model_id,
            "prompt_name": prompt_name,
            "prompt_version": self.prompt_version,
            "validator_version": module.VERSION,
            "ok": ok,
            "reason_code": reason,
            "raw_output": raw if not error else error,
            "latency_ms": latency_ms,
        })
        self.turn_debug.append({
            "prompt_name": prompt_name, "ok": ok, "reason_code": reason,
            "raw_output": raw, "result": result, "latency_ms": latency_ms,
        })
        return result
