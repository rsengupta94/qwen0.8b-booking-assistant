"""Score transcripts against the path table and the product's JSONL log.

Per model call: pass (validator ok, matches gold), rescued (validator failed, product fell back),
silent_wrong (validator ok, does not match gold), unscored (no gold for this call, e.g. NLG phrasing).
Per turn: routing_ok when the product's next state matches the path table.
Per session: booking matches the card (doctor in the acceptable set, day in the effective days,
slot equals the rule's pick from the offered list); hand-off passes only when the persona caused it;
gave_up and turn_cap fail.

Usage: uv run python -m evals.score --pool all [--transcripts evals/transcripts] [--logs evals/product_logs] [--source generation]
Writes evals/results/<run_id>.json and prints aggregates only. Never prints utterances.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from evals import path_table as pt

ROOT = Path(__file__).resolve().parent
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}
GOLD_PROMPTS = {"turn_classifier", "yes_no", "extract_problem", "doctor_pref", "doctor_pick",
                "extract_phone", "session_type", "extract_days", "slot_choice", "off_script"}


def load_logs(log_dir: Path) -> dict[str, dict[int, list[dict]]]:
    by: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for p in sorted(log_dir.glob("*.jsonl")):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            by[d["session_id"]][int(d["turn"])].append(d)
    return by


def parse_raw(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}


def match(expected, actual) -> bool:
    if isinstance(expected, set):
        return actual in expected
    if isinstance(expected, list):
        return sorted(str(x).lower() for x in (actual or [])) == sorted(str(x).lower() for x in expected)
    return actual == expected


def booking_from_reply(reply: str, year: int) -> dict | None:
    """Recover doctor and start from a validated confirm_booking reply."""
    doc = next((d for d in pt.DOCTORS if d["name"].lower() in reply.lower()), None)
    m = re.search(r"(\d{1,2}) ([A-Za-z]+)\b.*?(\d{1,2}):(\d{2})", reply)
    if not doc or not m or m.group(2).lower() not in MONTHS:
        return None
    start = datetime(year, MONTHS[m.group(2).lower()], int(m.group(1)), int(m.group(3)), int(m.group(4)))
    return {"doctor_id": doc["id"], "start": start.isoformat(timespec="seconds")}


def persona_caused_handoff(turns: list[dict], walk: pt.Walk) -> bool:
    last_state = turns[-1]["answering_state"] if turns else None
    dodges = sum(1 for t in turns if t["answering_state"] == last_state
                 and (t.get("sidecar") or {}).get("act") in ("non_answer", "repeat", "faq_question"))
    sunday_only = all(d.lower() == "sunday" for d in walk.card["facts"].get("days") or []) and bool(walk.card["facts"].get("days"))
    return dodges >= pt.MAX_REASKS or (sunday_only and last_state == "ASK_DAYS")


def score_transcript(card: dict, t: dict, logs: dict[int, list[dict]]) -> dict:
    gen_local = (datetime.strptime(t["run"]["generated_at"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                 .astimezone().replace(tzinfo=None))
    today = gen_local.date()
    walk = pt.Walk(card, today, now=gen_local)
    calls, turns_out = [], []
    last_category = None
    for tr in t["turns"]:
        n = tr["turn"]
        lines = logs.get(n, [])
        picked = next((parse_raw(l["raw_output"]).get("doctor_id") for l in lines if l["prompt_name"] == "doctor_pick" and l["ok"]), None)
        cat = next((parse_raw(l["raw_output"]).get("category") for l in lines if l["prompt_name"] == "extract_problem" and l["ok"]), None)
        if cat is None:
            cat = last_category
        else:
            last_category = cat
        exp = walk.expect(tr, picked_doctor=picked, extracted_category=cat)
        # Product's offered slots take precedence for the slot expectation when present.
        if tr["bot"].get("offered_slots"):
            walk.last_offered = tr["bot"]["offered_slots"]
        actual_state = tr["bot"]["state"]
        actual_end = t["ended"] if actual_state == "END" else None
        exp_next = exp["next"]
        routing_ok = (actual_state in exp_next) if isinstance(exp_next, set) else (actual_state == exp_next)
        if exp_next == "END" and routing_ok and exp.get("end") and actual_end and actual_end != exp["end"]:
            routing_ok = False
        for l in lines:
            name = l["prompt_name"]
            out = parse_raw(l["raw_output"])
            gold = exp["nlu"].get(name)
            if not l["ok"]:
                cls = "rescued"
            elif name not in GOLD_PROMPTS or gold is None:
                cls = "unscored"
            else:
                cls = "pass" if all(match(v, out.get(k)) for k, v in gold.items()) else "silent_wrong"
            calls.append({"turn": n, "state": l["state"], "prompt": name, "ok": l["ok"], "reason_code": l["reason_code"],
                          "outcome": cls, "gold": {k: (sorted(v) if isinstance(v, set) else v) for k, v in (gold or {}).items()},
                          "actual": {k: out.get(k) for k in (gold or {})}})
        turns_out.append({"turn": n, "answering_state": tr["answering_state"], "act": (tr.get("sidecar") or {}).get("act"),
                          "expected_next": sorted(exp_next) if isinstance(exp_next, set) else exp_next,
                          "actual_next": actual_state, "routing_ok": routing_ok, "note": exp.get("note")})
    # Session outcome.
    ended = t["ended"]
    session = {"ended": ended, "pass": False, "reason": ""}
    if ended == "booking_confirmed":
        last = t["turns"][-1]
        booking = last["bot"].get("booking") or booking_from_reply(last["bot"]["reply"], today.year)
        if booking is None:
            session["reason"] = "booking_unreadable"
        else:
            docs = pt.expected_doctors(walk)
            days = pt.resolve_days(walk.facts.get("days") or [], today)
            start = booking["start"][:16]
            d_ok = booking["doctor_id"] in docs
            day_ok = (not days) or date.fromisoformat(start[:10]) in days
            rule = walk.card["facts"].get("slot_rule")
            offered = next((x["bot"]["offered_slots"] for x in reversed(t["turns"]) if x["bot"].get("offered_slots")), None)
            slot_ok = True
            if rule and offered:
                idx = {"first": 1, "last": len(offered)}.get(rule)
                if rule == "first_afternoon":
                    idx = next((i for i, s in enumerate(offered, 1) if int(s[11:13]) >= 12), 1)
                if rule == "none_work_once":
                    idx = 1
                slot_ok = idx is not None and offered[idx - 1][:16] == start
            picked = (last.get("sidecar") or {}).get("field") == "slot"
            session["pass"] = bool(d_ok and day_ok and slot_ok and picked)
            session["reason"] = "ok" if session["pass"] else ",".join(k for k, v in (
                ("wrong_doctor", not d_ok), ("wrong_day", not day_ok), ("wrong_slot", not slot_ok),
                ("booked_without_pick", not picked)) if v)
            session["booking"] = booking
    elif ended == "handoff":
        caused = persona_caused_handoff(t["turns"], walk)
        session["pass"] = caused
        session["reason"] = "handoff_persona_caused" if caused else "handoff_product_caused"
    else:
        session["reason"] = ended or "not_ended"
    return {"card_id": t["card_id"], "persona_id": t["persona_id"], "scenario_id": t["scenario_id"], "pool": t["pool"],
            "session": session, "turns": turns_out, "calls": calls}


def aggregate(results: list[dict]) -> dict:
    by_prompt: dict[str, Counter] = defaultdict(Counter)
    routing = Counter()
    sessions = Counter()
    by_scenario: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        sessions["pass" if r["session"]["pass"] else "fail"] += 1
        sessions[r["session"]["reason"]] += 1
        by_scenario[r["scenario_id"]]["pass" if r["session"]["pass"] else "fail"] += 1
        for c in r["calls"]:
            by_prompt[c["prompt"]][c["outcome"]] += 1
        for tr in r["turns"]:
            routing["ok" if tr["routing_ok"] else "misrouted"] += 1
    return {"sessions": dict(sessions), "routing": dict(routing),
            "by_prompt": {k: dict(v) for k, v in sorted(by_prompt.items())},
            "by_scenario": {k: dict(v) for k, v in sorted(by_scenario.items())}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="all", choices=["dev", "heldout", "all"])
    ap.add_argument("--transcripts", default=str(ROOT / "transcripts"))
    ap.add_argument("--logs", default=str(ROOT / "product_logs"))
    ap.add_argument("--source", default="generation")
    ap.add_argument("--out", default=str(ROOT / "results"))
    a = ap.parse_args()
    logs = load_logs(Path(a.logs))
    pools = ["dev", "heldout"] if a.pool == "all" else [a.pool]
    results, meta = [], {}
    for pool in pools:
        for p in sorted(Path(a.transcripts, pool).glob("*.json")):
            t = json.loads(p.read_text())
            card = json.loads((ROOT / "cards" / pool / p.name).read_text())
            meta = {"prompt_version": t["run"]["prompt_version"], "model_id": t["run"]["model_id"],
                    "eval_set_version": t["eval_set_version"], "simulator_model": t["run"]["simulator_model"]}
            results.append(score_transcript(card, t, logs.get(t["run"]["session_id"], {})))
    vv = sorted({l.get("validator_version") for s in logs.values() for ls in s.values() for l in ls if l.get("validator_version")})
    run_id = f"{a.source}_{meta.get('prompt_version','?')}_{meta.get('model_id','?')}_set{meta.get('eval_set_version','?')}_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    agg = {"run_id": run_id, "source": a.source, **meta, "validator_versions": vv, "pools": pools,
           "n_sessions": len(results), "aggregate": aggregate(results),
           "per_pool": {pool: aggregate([r for r in results if r["pool"] == pool]) for pool in pools}}
    Path(a.out).mkdir(exist_ok=True)
    (Path(a.out) / f"{run_id}.json").write_text(json.dumps({**agg, "sessions": results}, indent=2) + "\n")
    print(f"run_id={run_id} sessions={len(results)}")
    for pool in pools:
        pa = agg["per_pool"][pool]
        print(f"{pool}: sessions={pa['sessions']} routing={pa['routing']}")
        for k, v in pa["by_prompt"].items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
