from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import prompts
from app.nlu.runner import NLURunner
from app.session import SessionStore
from app.state_machine import step

app = FastAPI(title="Booking assistant")
store = SessionStore()


class MessageIn(BaseModel):
    session_id: str
    model_id: str
    prompt_version: str
    text: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/message")
def message(msg: MessageIn) -> dict:
    if msg.prompt_version not in prompts.versions():
        raise HTTPException(400, f"unknown prompt_version {msg.prompt_version!r}; have {prompts.versions()}")
    session = store.get_or_create(msg.session_id)
    nlu = NLURunner(msg.model_id, msg.prompt_version)
    nlu.start_turn()
    result = step(session, msg.text, nlu)
    return {
        "reply": None,  # Phase 3 NLG fills this; until then clients render debug.reply_facts
        "state": str(result.state),
        "debug": {
            "reply_facts": result.reply,
            "nlu_output": result.nlu_output,
            "validator_results": nlu.turn_debug,
            "fallback_used": any(not d["ok"] for d in nlu.turn_debug),
            "latency_ms": sum(d["latency_ms"] for d in nlu.turn_debug),
        },
    }
