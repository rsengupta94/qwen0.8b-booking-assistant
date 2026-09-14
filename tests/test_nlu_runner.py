import json

import pytest

from app import llm_client, logging as applog
from app.nlu.runner import NLURunner
from app.session import Session


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("BOOKING_LOG_PATH", str(path))
    return path


def fake_complete(raw: str):
    def _complete(model_id, prompt, schema, params):
        return {"output": json.loads(raw), "raw": raw, "latency_ms": 7, "logprobs": []}
    return _complete


def test_valid_output_is_returned_and_logged(monkeypatch, log_file):
    monkeypatch.setattr(llm_client, "complete", fake_complete('{"intent": "no"}'))
    s = Session("s1", state="ASK_FIRST_CONSULT", turn=2)
    r = NLURunner("m", "baseline")
    assert r("yes_no", s, "nope", {}) == {"intent": "no"}
    line = json.loads(log_file.read_text().splitlines()[0])
    assert set(line) == set(applog.FIELDS)
    assert line["ok"] is True and line["prompt_name"] == "yes_no" and line["prompt_version"] == "baseline"
    assert line["validator_version"] == "1" and line["state"] == "ASK_FIRST_CONSULT" and line["turn"] == 2
    assert r.turn_debug[0]["result"] == {"intent": "no"}


def test_invalid_output_falls_back_and_logs_reason(monkeypatch, log_file):
    monkeypatch.setattr(llm_client, "complete", fake_complete('{"digits": "9000000000"}'))
    s = Session("s2", state="ASK_PHONE")
    out = NLURunner("m", "baseline")("extract_phone", s, "my number is 9876543210", {})
    assert out == {"digits": ""}
    line = json.loads(log_file.read_text())
    assert line["ok"] is False and line["reason_code"] == "digits_not_in_text" and line["raw_output"] == '{"digits": "9000000000"}'


def test_model_exception_falls_back_and_never_raises(monkeypatch, log_file):
    def boom(*a, **k):
        raise RuntimeError("gguf on fire")
    monkeypatch.setattr(llm_client, "complete", boom)
    s = Session("s3", state="ASK_SESSION_TYPE")
    out = NLURunner("m", "baseline")("session_type", s, "follow up", {})
    assert out == {"type": "other"}
    line = json.loads(log_file.read_text())
    assert line["ok"] is False and line["reason_code"] == "model_error" and "gguf on fire" in line["raw_output"]


def test_every_prompt_renders_for_every_module(monkeypatch, log_file):
    """All ten baseline prompts exist and fill from the context the state machine provides."""
    from app.nlu.runner import MODULES
    from app.state_machine import DAY_TERMS
    from app.tools import fixtures
    seen = []
    def capture(model_id, prompt, schema, params):
        seen.append(prompt); raise RuntimeError("stop")
    monkeypatch.setattr(llm_client, "complete", capture)
    docs = fixtures.doctors()
    ctx = {"categories": fixtures.categories(), "shortlist": docs[:2], "day_terms": DAY_TERMS,
           "offered_slots": [{"weekday": "monday", "start": "2026-09-21T10:00"}]}
    s = Session("s4")
    r = NLURunner("m", "baseline")
    for name in MODULES:
        r(name, s, "hello there", ctx)
    assert len(seen) == len(MODULES) == 10
    assert all("hello there" in p for p in seen)
