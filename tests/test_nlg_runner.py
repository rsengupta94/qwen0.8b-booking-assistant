"""design.md Phase 3 check: a fake slot in present_slots output -> template used and logged as fallback."""

import json

import pytest

from app import llm_client, logging as applog
from app.nlg.runner import render_reply
from app.session import Session

FACTS = {"kind": "present_slots", "doctor_name": "Dr. Meera Rao",
         "slots": [{"start": "2026-09-23T14:00"}, {"start": "2026-09-23T15:00"}]}


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("BOOKING_LOG_PATH", str(path))
    return path


def fake(raw):
    return lambda *a, **k: {"output": json.loads(raw), "raw": raw, "latency_ms": 5, "logprobs": []}


def test_fake_slot_uses_template_and_logs_fallback(monkeypatch, log_file):
    fake_reply = ("Dr. Meera Rao is available at:\\n1. Wednesday 23 September, 14:00\\n"
                  "2. Wednesday 23 September, 15:00\\n3. Thursday 24 September, 16:00\\nWhich one?")
    monkeypatch.setattr(llm_client, "complete", fake(json.dumps({"reply": fake_reply.replace("\\n", "\n")})))
    s = Session("n1", state="CAPTURE_CHOICE", turn=5)
    reply, debug = render_reply(FACTS, s, "m", "baseline")
    assert "Thursday" not in reply
    assert reply == ("Dr. Meera Rao is available at:\n1. Wednesday 23 September, 14:00\n"
                     "2. Wednesday 23 September, 15:00\nWhich one would you like?")
    assert debug["ok"] is False and debug["reason_code"] == "extra_time"
    line = json.loads(log_file.read_text())
    assert set(line) == set(applog.FIELDS)
    assert line["prompt_name"] == "present_slots" and line["ok"] is False and line["reason_code"] == "extra_time"
    assert line["state"] == "CAPTURE_CHOICE" and line["turn"] == 5 and line["prompt_version"] == "baseline"


def test_good_reply_is_used_and_logged_ok(monkeypatch, log_file):
    good = "Dr. Meera Rao can see you:\n1. Wednesday 23 September, 14:00\n2. Wednesday 23 September, 15:00\nWhich suits you?"
    monkeypatch.setattr(llm_client, "complete", fake(json.dumps({"reply": good})))
    reply, debug = render_reply(FACTS, Session("n2"), "m", "baseline")
    assert reply == good and debug["ok"] is True
    assert json.loads(log_file.read_text())["ok"] is True


def test_model_error_uses_template(monkeypatch, log_file):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(llm_client, "complete", boom)
    reply, debug = render_reply({"kind": "ask_question", "question": "days"}, Session("n3"), "m", "baseline")
    assert reply == "Which days work for you?" and debug["reason_code"] == "model_error"


def test_handoff_and_ended_make_no_model_call_and_no_log(monkeypatch, log_file):
    monkeypatch.setattr(llm_client, "complete", lambda *a, **k: pytest.fail("model must not be called"))
    reply, debug = render_reply({"kind": "handoff", "reason": "x"}, Session("n4"), "m", "baseline")
    assert "1800-000-0000" in reply and debug is None
    reply, debug = render_reply({"kind": "ended"}, Session("n4"), "m", "baseline")
    assert "ended" in reply and debug is None
    assert not log_file.exists()


def test_every_nlg_prompt_renders(monkeypatch, log_file):
    seen = []
    def capture(model_id, prompt, schema, params):
        seen.append(prompt); raise RuntimeError("stop")
    monkeypatch.setattr(llm_client, "complete", capture)
    s = Session("n5")
    render_reply({"kind": "ask_question", "question": "first_consult", "greeting": True}, s, "m", "baseline")
    render_reply(FACTS, s, "m", "baseline")
    render_reply({"kind": "no_slots", "doctor_id": "d_rao", "days": ["2026-09-27"]}, s, "m", "baseline")
    render_reply({"kind": "confirm_booking", "booking": {"booking_id": "b1", "doctor_name": "Dr. X", "start": "2026-09-23T14:00", "session_type": "therapy"}}, s, "m", "baseline")
    render_reply({"kind": "clarify", "faq_answer": "Fees are 1500.", "question": "Which days work for you?"}, s, "m", "baseline")
    assert len(seen) == 5 and all(p.rstrip().endswith("JSON:") for p in seen)
