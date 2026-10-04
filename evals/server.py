"""Eval server: serves scoring runs to the Evals tab in the product UI (eval design 5c stage 6, decision log I).

A separate process from the product, so the product never reads results files (rule 8). Reads
evals/results/*.json, dev transcripts and the product's JSONL logs for dev sessions. Held-out data leaves this
server only as structured fields (prompt, expected and actual enum values, outcome, reason code): it never
opens a held-out transcript or log and never sends patient or bot text for held-out (decision log I1).
Usage: uv run uvicorn evals.server:app --port 8001
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RESULTS = ROOT / "results"
OUTCOMES = ["pass", "rescued", "silent_wrong", "unscored"]
POOLS = ["heldout", "dev"]
CALL_FIELDS = ("card_id", "scenario_id", "turn", "state", "prompt", "ok", "reason_code", "outcome", "gold", "actual")

app = FastAPI(title="eval server")
# The Evals tab is served by the product on another local port; allow it to read.
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?", allow_methods=["GET"])


def setup(r: dict) -> tuple:
    return (r["source"], r["prompt_version"], r["model_id"], r["eval_set_version"])


@lru_cache(maxsize=8)
def _load(path: Path, mtime: float) -> dict:
    return json.loads(path.read_text())


def load(path: Path) -> dict:
    return _load(path, path.stat().st_mtime)


def latest_per_setup() -> dict[str, Path]:
    """run_id -> file, keeping only the newest file per setup (decision log I2). Names sort by timestamp."""
    newest: dict[tuple, Path] = {}
    for p in sorted(RESULTS.glob("*.json")):
        newest[setup(load(p))] = p
    return {p.stem: p for p in newest.values()}


def prompt_rows(version: str) -> list[tuple[str, str]]:
    return [(p.stem, kind) for kind in ("nlu", "nlg") for p in sorted((REPO / "prompts" / version / kind).glob("*.md"))]


def discards(pool: str, kept: int) -> dict:
    """Fidelity-gate discards for this pool, matched by file name to the pool's cards; files are not opened."""
    cards = {p.stem for p in (ROOT / "cards" / pool).glob("*.json")}
    n = sum(1 for p in (ROOT / "transcripts" / "discarded").glob("*.json") if p.name.split(".")[0] in cards)
    return {"discarded": n, "runs": kept + n}


def dev_logs() -> dict[str, dict[int, list[dict]]]:
    """session_id -> turn -> log lines, from the dev generation logs only; held-out log files are never opened."""
    by: dict[str, dict[int, list[dict]]] = {}
    for p in sorted((ROOT / "product_logs").glob("eval_gen_dev*.jsonl")):
        for line in p.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                by.setdefault(d["session_id"], {}).setdefault(int(d["turn"]), []).append(d)
    return by


def dev_turns(card_ids: set[str]) -> dict:
    """card_id -> turn -> patient text, bot reply and the product's log lines. Dev pool, generation runs only."""
    logs = dev_logs()
    out = {}
    for cid in sorted(card_ids):
        t = json.loads((ROOT / "transcripts" / "dev" / f"{cid}.json").read_text())
        by_turn = logs.get(t["run"]["session_id"], {})
        out[cid] = {tr["turn"]: {"state": tr["answering_state"], "user": tr["user"], "reply": tr["bot"]["reply"],
                                 "log": [{k: l.get(k) for k in ("state", "prompt_name", "ok", "reason_code", "raw_output", "latency_ms")}
                                         for l in by_turn.get(tr["turn"], [])]}
                    for tr in t["turns"]}
    return out


def pool_view(r: dict, pool: str) -> dict:
    agg = r["per_pool"].get(pool)
    if agg is None:
        return {}
    sessions = [s for s in r["sessions"] if s["pool"] == pool]
    heatmap = []
    for name, kind in prompt_rows(r["prompt_version"]):
        counts = {o: agg["by_prompt"].get(name, {}).get(o, 0) for o in OUTCOMES}
        heatmap.append({"prompt": name, "kind": kind, "calls": sum(counts.values()), "counts": counts})
    calls = [{"card_id": s["card_id"], "scenario_id": s["scenario_id"], **c} for s in sessions for c in s["calls"]]
    coherence = (r.get("judge") or {}).get("coherence", {}).get(pool, {})
    view = {
        "sessions": {"n": len(sessions), "passed": agg["sessions"].get("pass", 0)},
        "discard": discards(pool, len(sessions)),
        "routing": agg["routing"],
        "coherence": {"fits_no": coherence.get("no", 0), "replies": coherence.get("yes", 0) + coherence.get("no", 0)},
        "heatmap": heatmap,
        "calls": [{k: c.get(k) for k in CALL_FIELDS} for c in calls],
    }
    if pool == "dev":
        view["turns"] = dev_turns({s["card_id"] for s in sessions})
    return view


@app.get("/evals/runs")
def runs() -> list[dict]:
    out = []
    for run_id, p in sorted(latest_per_setup().items()):
        r = load(p)
        out.append({"run_id": run_id, "source": r["source"], "prompt_version": r["prompt_version"], "model_id": r["model_id"],
                    "eval_set_version": r["eval_set_version"], "simulator_model": r.get("simulator_model"),
                    "n_sessions": r["n_sessions"], "judge_model": (r.get("judge") or {}).get("model")})
    return out


@app.get("/evals/runs/{run_id}")
def run(run_id: str) -> dict:
    files = {p.stem: p for p in RESULTS.glob("*.json")}
    if run_id not in files:
        raise HTTPException(404, f"no run {run_id}")
    r = load(files[run_id])
    agreement = (r.get("judge") or {}).get("agreement") or {}
    return {
        "run_id": run_id, "source": r["source"], "prompt_version": r["prompt_version"], "model_id": r["model_id"],
        "eval_set_version": r["eval_set_version"], "validator_versions": r.get("validator_versions"),
        "outcomes": OUTCOMES,
        "judge": {"model": (r.get("judge") or {}).get("model"), "agree": agreement.get("agree"),
                  "matched": agreement.get("matched"), "rate": agreement.get("rate"), "floor": (r.get("judge") or {}).get("floor")},
        "pools": {pool: pool_view(r, pool) for pool in POOLS},
    }
