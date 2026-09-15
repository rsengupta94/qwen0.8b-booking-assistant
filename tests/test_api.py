import json

import pytest
from fastapi.testclient import TestClient

from app import api, llm_client
from app.tools import mock_backend


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKING_LOG_PATH", str(tmp_path / "calls.jsonl"))
    monkeypatch.setattr(mock_backend, "now", lambda: __import__("datetime").datetime(2026, 9, 21, 8, 0))
    mock_backend.reset()
    api.store._sessions.clear()
    return TestClient(api.app)


def scripted(answers: dict[str, str]):
    """Fake complete(): answer per prompt name, detected from the schema's property names."""
    def _complete(model_id, prompt, schema, params):
        props = set(schema["properties"])
        if props == {"reply"}:
            raw = '{"reply": "Is this your first consultation with us?"}'  # fails most NLG validators -> template
            return {"output": json.loads(raw), "raw": raw, "latency_ms": 3, "logprobs": []}
        for name, raw in answers.items():
            if props == set(json.loads(raw)):
                return {"output": json.loads(raw), "raw": raw, "latency_ms": 3, "logprobs": []}
        raise AssertionError(f"no scripted answer for schema {props}")
    return _complete


def post(client, text, session="s1"):
    r = client.post("/message", json={"session_id": session, "model_id": "m", "prompt_version": "baseline", "text": text})
    assert r.status_code == 200, r.text
    return r.json()


def test_returning_patient_books_over_http(client, monkeypatch):
    monkeypatch.setattr(llm_client, "complete", scripted({
        "yes_no": '{"intent": "no"}',
        "extract_phone": '{"digits": "9876543210"}',
        "session_type": '{"type": "followup"}',
        "extract_days": '{"time_pref": "morning", "days": ["monday"]}',
        "slot_choice": '{"choice_index": 1, "wants_other": false, "other": null}',
        "turn_classifier": '{"is_correction": false, "correction_field": null, "new_value": null}',
    }))
    states = [post(client, t)["state"] for t in ["hi", "no", "9876543210", "follow up", "monday morning"]]
    assert states == ["ASK_FIRST_CONSULT", "ASK_PHONE", "ASK_SESSION_TYPE", "ASK_DAYS", "CAPTURE_CHOICE"]
    last = post(client, "1")
    assert last["state"] == "END"
    assert "Dr. Meera Rao" in last["reply"] and "Monday 21 September" in last["reply"] and "10:00" in last["reply"]
    assert last["debug"]["nlg"]["prompt_name"] == "confirm_booking"
    assert last["debug"]["reply_facts"]["kind"] == "confirm_booking"
    assert last["debug"]["reply_facts"]["booking"]["start"] == "2026-09-21T10:00"
    assert [c["prompt_name"] for c in last["debug"]["validator_results"]] == ["turn_classifier", "slot_choice"]
    assert last["debug"]["correction"] is None
    assert last["debug"]["latency_ms"] == 9  # classifier + one NLU call + one NLG call


def test_fallback_is_reported_in_debug(client, monkeypatch):
    monkeypatch.setattr(llm_client, "complete", scripted({"yes_no": '{"intent": "yes"}', "extract_problem": '{"category": "nope", "summary": "x"}'}))
    post(client, "hi"); post(client, "yes")
    r = post(client, "I feel anxious")
    assert r["state"] == "ASK_DOCTOR_PREF"
    assert r["debug"]["fallback_used"] is True
    assert r["debug"]["validator_results"][0]["reason_code"] == "category_not_in_enum"


def test_unknown_prompt_version_is_400(client):
    r = client.post("/message", json={"session_id": "x", "model_id": "m", "prompt_version": "nope", "text": "hi"})
    assert r.status_code == 400


def test_ui_models_prompts_endpoints(client):
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert 'id="model"' in r.text and 'id="prompt_version"' in r.text and 'id="debug"' in r.text
    models = client.get("/models").json()
    assert models and {"model_id", "quant", "available"} <= set(models[0])
    assert isinstance(models[0]["available"], bool)
    assert "baseline" in client.get("/prompts").json()


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_stream_emits_one_call_event_per_model_call_then_done(client, monkeypatch):
    monkeypatch.setattr(llm_client, "complete", scripted({
        "yes_no": '{"intent": "no"}',
        "extract_phone": '{"digits": "9876543210"}',
        "session_type": '{"type": "followup"}',
        "turn_classifier": '{"is_correction": false, "correction_field": null, "new_value": null}',
    }))
    post(client, "hi", session="st"); post(client, "no", session="st"); post(client, "9876543210", session="st")
    r = client.post("/message/stream", json={"session_id": "st", "model_id": "m", "prompt_version": "baseline", "text": "follow up"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = _events(r.text)
    assert [e for e, _ in ev] == ["start", "call", "call", "call", "done"]
    assert [d["prompt_name"] for e, d in ev if e == "call"] == ["turn_classifier", "session_type", "ask_question"]
    done = ev[-1][1]
    assert done["state"] == "ASK_DAYS" and set(done) == {"reply", "state", "debug"}
    assert [c["prompt_name"] for c in done["debug"]["validator_results"]] == ["turn_classifier", "session_type"]


def test_stream_unknown_prompt_version_is_400(client):
    r = client.post("/message/stream", json={"session_id": "x", "model_id": "m", "prompt_version": "nope", "text": "hi"})
    assert r.status_code == 400


def test_stream_model_error_still_completes(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("gguf on fire")
    monkeypatch.setattr(llm_client, "complete", boom)
    r = client.post("/message/stream", json={"session_id": "se", "model_id": "m", "prompt_version": "baseline", "text": "hi"})
    ev = _events(r.text)
    assert [e for e, _ in ev] == ["start", "call", "done"]  # greeting NLG call falls back to the template
    assert ev[-1][1]["debug"]["fallback_used"] is True and "Willow Lane" in ev[-1][1]["reply"]
