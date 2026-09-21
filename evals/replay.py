"""Replay saved user turns against a product version and compare with the generating run.

For each transcript: start a fresh product server (clean fixtures, clock pinned to the transcript's
generation date, its own JSONL log), re-send the user turns in order, and record the product's
state, kind, offered slots and booking. Slot-pick turns are re-rendered from the card's rule when
the offered list differs from the original; otherwise the original words are sent so the phrasing
phenomenon is preserved. Writes evals/transcripts/replay/<pool>/ and prints per-turn agreement
(state and kind) with the generation transcript. Never prints utterances.

Usage: uv run python -m evals.replay --pool dev [--limit N] [--port 8801] [--model-id ...] [--prompt-version ...]
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def free_port() -> int:
    """A port nobody is listening on. A stale server on a fixed port would answer /health with the
    wrong clock and old bookings, so every card gets a fresh port."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port: int, clock: str, log_path: Path) -> subprocess.Popen:
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(f"port {port} already has a listener; refusing to replay against a stale server")
    env = {**os.environ, "BOOKING_CLOCK": clock, "BOOKING_LOG_PATH": str(log_path)}
    # start_new_session so the whole process group (uv wrapper + uvicorn child) can be killed together;
    # killing only the wrapper leaves a live server holding the model.
    proc = subprocess.Popen(["uv", "run", "uvicorn", "app.api:app", "--port", str(port), "--log-level", "warning"],
                            cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(120):
        try:
            request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read()
            return proc
        except (error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    stop_server(proc)
    raise SystemExit(f"server on {port} did not come up")


def stop_server(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def post(port: int, body: dict) -> dict:
    req = request.Request(f"http://127.0.0.1:{port}/message", data=json.dumps(body).encode(),
                          headers={"content-type": "application/json"})
    with request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def rule_index(rule: str | None, offered: list[str]) -> int | None:
    if not offered or not rule:
        return None
    if rule in ("first", "none_work_once"):
        return 1
    if rule == "last":
        return len(offered)
    if rule == "first_afternoon":
        return next((i for i, s in enumerate(offered, 1) if int(s[11:13]) >= 12), 1)
    return None


def replay_one(card: dict, gen: dict, port: int | None, model_id: str, prompt_version: str, log_path: Path) -> tuple[dict, Counter]:
    port = port or free_port()
    # generated_at is UTC; the product compares slots against local wall-clock time, so pin local time.
    clock = (datetime.strptime(gen["run"]["generated_at"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
             .astimezone().replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S"))
    proc = start_server(port, clock, log_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {**{k: gen[k] for k in ("card_id", "persona_id", "scenario_id", "pool", "eval_set_version")},
           "run": {"model_id": model_id, "prompt_version": prompt_version, "simulator_model": "replay",
                   "session_id": f"{gen['card_id']}__replay__{stamp}", "generated_at": stamp,
                   "replay_of": gen["run"]["session_id"], "clock": clock},
           "turns": [], "ended": None}
    agree = Counter()
    offered_now: list[str] | None = None
    try:
        for tr in gen["turns"]:
            sc = tr["sidecar"]
            text = tr["user"]
            # Re-render a slot pick only when the persona typed a bare number and the offered list moved;
            # descriptive picks ("the later one", "2 in the afternoon") keep their words so the phrasing
            # phenomenon survives the replay.
            if sc.get("field") == "slot" and offered_now is not None and str(text).strip().isdigit():
                gen_offered = next((x["bot"].get("offered_slots") for x in reversed(gen["turns"]) if x["turn"] < tr["turn"] and x["bot"].get("offered_slots")), None)
                if gen_offered != offered_now:
                    idx = rule_index(sc.get("slot_rule"), offered_now)
                    text = str(idx) if idx else text
                    sc = {**sc, "value": str(idx) if idx else sc.get("value"), "rendered": True}
            resp = post(port, {"session_id": out["run"]["session_id"], "model_id": model_id, "prompt_version": prompt_version, "text": text})
            facts = (resp.get("debug") or {}).get("reply_facts") or {}
            kind = facts.get("kind")
            offered_now = [s["start"] for s in facts.get("slots", [])] if kind == "present_slots" else offered_now
            bot = {"reply": resp["reply"], "state": resp["state"], "kind": kind,
                   "offered_slots": [s["start"] for s in facts.get("slots", [])] if kind == "present_slots" else None,
                   "booking": facts.get("booking") if kind == "confirm_booking" else None,
                   "fallback_used": resp["debug"]["fallback_used"]}
            out["turns"].append({"turn": tr["turn"], "answering_state": tr["answering_state"], "user": text, "sidecar": sc, "bot": bot})
            agree["state_ok" if bot["state"] == tr["bot"]["state"] else "state_diff"] += 1
            agree["kind_ok" if kind == tr["bot"].get("kind") else "kind_diff"] += 1
            if kind in ("confirm_booking", "handoff"):
                out["ended"] = "booking_confirmed" if kind == "confirm_booking" else "handoff"
                break
            if resp["state"] == "END":
                break
        if out["ended"] is None:
            out["ended"] = gen["ended"] if gen["ended"] in ("gave_up", "turn_cap") else "diverged"
    finally:
        stop_server(proc)
    agree["ended_ok" if out["ended"] == gen["ended"] else "ended_diff"] += 1
    return out, agree


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="dev", choices=["dev", "heldout", "all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--port", type=int, default=0, help="fixed port; default picks a free port per card")
    ap.add_argument("--model-id", default="qwen3.5-0.8b-q8")
    ap.add_argument("--prompt-version", default="baseline")
    a = ap.parse_args()
    pools = ["dev", "heldout"] if a.pool == "all" else [a.pool]
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    total = Counter()
    for pool in pools:
        outdir = ROOT / "transcripts" / "replay" / pool
        outdir.mkdir(parents=True, exist_ok=True)
        log_path = ROOT / "product_logs" / f"replay_{pool}_{a.prompt_version}_{stamp}.jsonl"
        files = sorted((ROOT / "transcripts" / pool).glob("*.json"))
        if a.limit:
            files = files[: a.limit]
        for p in files:
            gen = json.loads(p.read_text())
            card = json.loads((ROOT / "cards" / pool / p.name).read_text())
            out, agree = replay_one(card, gen, a.port or None, a.model_id, a.prompt_version, log_path)
            (outdir / p.name).write_text(json.dumps(out, indent=2) + "\n")
            total.update(agree)
            print(f"{pool} {gen['card_id']}: turns={len(out['turns'])} ended={out['ended']} "
                  f"state_diff={agree['state_diff']} kind_diff={agree['kind_diff']}")
    n_turns = total["state_ok"] + total["state_diff"]
    print(f"replay: turns={n_turns} state_agree={total['state_ok']} state_diff={total['state_diff']} "
          f"kind_diff={total['kind_diff']} ended_ok={total['ended_ok']} ended_diff={total['ended_diff']}")
    sys.exit(0 if total["state_diff"] == 0 else 2)


if __name__ == "__main__":
    main()
