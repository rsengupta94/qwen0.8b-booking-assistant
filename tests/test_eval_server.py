"""Eval server: one run per setup, a heatmap row per prompt, held-out without text, cross-origin reads from a local page."""
import json

from fastapi.testclient import TestClient

from evals import server

client = TestClient(server.app)


def results_file(tmp_path, run_id, by_prompt):
    r = {"run_id": run_id, "source": "generation", "prompt_version": "baseline", "model_id": "m", "eval_set_version": 1,
         "n_sessions": 1, "pools": ["heldout"],
         "per_pool": {"heldout": {"sessions": {"pass": 1}, "routing": {"ok": 1}, "by_prompt": by_prompt}},
         "sessions": [{"card_id": "c", "scenario_id": "A1", "pool": "heldout", "turns": [],
                       "calls": [{"turn": 3, "state": "ASK_PROBLEM", "prompt": "extract_problem", "ok": True, "reason_code": "ok",
                                  "outcome": "pass", "gold": {"category": "grief"}, "actual": {"category": "grief"}}]}]}
    (tmp_path / f"{run_id}.json").write_text(json.dumps(r))


def test_run_list_keeps_newest_per_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "RESULTS", tmp_path)
    results_file(tmp_path, "generation_baseline_m_set1_20260101T000000", {})
    results_file(tmp_path, "generation_baseline_m_set1_20260102T000000", {})
    assert [r["run_id"] for r in client.get("/evals/runs").json()] == ["generation_baseline_m_set1_20260102T000000"]


def test_heatmap_has_a_row_for_every_prompt_even_when_never_called(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "RESULTS", tmp_path)
    results_file(tmp_path, "generation_baseline_m_set1_20260101T000000", {"extract_problem": {"pass": 1}})
    rows = {r["prompt"]: r for r in client.get("/evals/runs/generation_baseline_m_set1_20260101T000000").json()["pools"]["heldout"]["heatmap"]}
    assert len(rows) == len(server.prompt_rows("baseline")) == 15
    assert rows["extract_problem"]["counts"]["pass"] == 1
    assert rows["clarify"]["calls"] == 0 and rows["clarify"]["kind"] == "nlg"


def test_heldout_carries_no_text_and_dev_does():
    run_id = client.get("/evals/runs").json()[0]["run_id"]
    pools = client.get(f"/evals/runs/{run_id}").json()["pools"]
    assert "turns" not in pools["heldout"]
    assert all(set(c) <= set(server.CALL_FIELDS) for c in pools["heldout"]["calls"])
    assert all(isinstance(v, dict) for c in pools["heldout"]["calls"] for v in (c["gold"], c["actual"]) if v is not None)
    some_card = next(iter(pools["dev"]["turns"].values()))
    assert {"user", "reply", "log"} <= set(next(iter(some_card.values())))


def test_unknown_run_is_404():
    assert client.get("/evals/runs/nope").status_code == 404
    assert client.get("/evals/runs/..%2Fresults").status_code == 404


def test_cross_origin_allowed_for_local_pages_only():
    ok = client.get("/evals/runs", headers={"Origin": "http://localhost:8000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:8000"
    other = client.get("/evals/runs", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in other.headers
