import json
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app import llm_client, prompts
from app.nlg.runner import render_reply
from app.nlu.runner import NLURunner
from app.session import SessionStore
from app.state_machine import step

UI_FILE = Path(__file__).resolve().parent.parent / "clients" / "ui" / "index.html"

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


@app.get("/")
def ui() -> FileResponse:
    return FileResponse(UI_FILE, media_type="text/html")


@app.get("/models")
def models() -> list[dict]:
    """Registry entries for the UI dropdown. `available` is whether the GGUF is on disk."""
    return [
        {"model_id": mid, "quant": m.get("quant"), "available": (llm_client.REPO_ROOT / m["path"]).is_file()}
        for mid, m in llm_client._load_registry().items()
    ]


@app.get("/prompts")
def prompt_versions() -> list[str]:
    return prompts.versions()


def _run_turn(msg: MessageIn, on_call=None) -> dict:
    """One user turn: state machine, NLG, and the response body. `on_call(prompt_name)` fires before each model call."""
    session = store.get_or_create(msg.session_id)
    nlu = NLURunner(msg.model_id, msg.prompt_version, on_call=on_call)
    nlu.start_turn()
    result = step(session, msg.text, nlu)
    reply, nlg_debug = render_reply(result.reply, session, msg.model_id, msg.prompt_version, on_call=on_call)
    calls = nlu.turn_debug + ([nlg_debug] if nlg_debug else [])
    return {
        "reply": reply,
        "state": str(result.state),
        "debug": {
            "reply_facts": result.reply,
            "nlu_output": result.nlu_output,
            "validator_results": nlu.turn_debug,
            "nlg": nlg_debug,
            "correction": result.correction,
            "fallback_used": any(not d["ok"] for d in calls),
            "latency_ms": sum(d["latency_ms"] for d in calls),
        },
    }


def _check_version(msg: MessageIn) -> None:
    if msg.prompt_version not in prompts.versions():
        raise HTTPException(400, f"unknown prompt_version {msg.prompt_version!r}; have {prompts.versions()}")


@app.post("/message")
def message(msg: MessageIn) -> dict:
    _check_version(msg)
    return _run_turn(msg)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/message/stream")
def message_stream(msg: MessageIn) -> StreamingResponse:
    """Same turn as /message, as Server-Sent Events: `start`, one `call` event as each model call
    starts, then `done` carrying the /message body. On an unexpected error, an `error` event."""
    _check_version(msg)
    events: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            body = _run_turn(msg, on_call=lambda name: events.put(("call", {"prompt_name": name})))
            events.put(("done", body))
        except Exception as e:  # never leave the stream open
            events.put(("error", {"error": f"{type(e).__name__}: {e}"[:200]}))

    def generate():
        yield _sse("start", {"session_id": msg.session_id})
        threading.Thread(target=work, daemon=True).start()
        while True:
            event, data = events.get()
            yield _sse(event, data)
            if event in ("done", "error"):
                return

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
