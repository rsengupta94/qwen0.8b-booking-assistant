"""Fidelity gate: keep only transcripts where the simulator stayed faithful to its card.

This gate judges the simulator, never the product. A hand-off or a wrong booking is kept and
scored later; only simulator drift, unfinished sessions, and unexercised scenarios are discarded.
Usage: uv run python -m evals.fidelity [--pool dev|heldout|all] [--dry-run]
Prints counts and reason histograms per pool. Never prints held-out utterances.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ACTS = {"answer", "repeat", "faq_question", "correction", "non_answer", "wants_other"}
ORDINARY_LABELS = {"anxiety", "depression", "stress", "sleep"}
END_OK = {"booking_confirmed", "handoff", "gave_up", "turn_cap"}  # the last two are product failures, kept for scoring


def _digits(s: str | None) -> str:
    """Digits only, last 10 so a +91 prefix still matches the card."""
    return re.sub(r"\D", "", s or "")[-10:]


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _expected_index(rule: str, offered: list[str]) -> int | None:
    if not offered:
        return None
    if rule == "first":
        return 1
    if rule == "last":
        return len(offered)
    if rule == "first_afternoon":
        for i, start in enumerate(offered, 1):
            if int(start[11:13]) >= 12:
                return i
        return 1
    return None


def _check_slot_pick(tr: dict, turns: list[dict], rule: str | None) -> list[str]:
    """The sidecar value is the 1-based number of the offered slot the persona picked."""
    prev = next((x for x in reversed(turns) if x["turn"] < tr["turn"]), None)
    offered = (prev or {}).get("bot", {}).get("offered_slots")
    value = (tr.get("sidecar") or {}).get("value")
    if not value or not str(value).strip().isdigit():
        return [f"slot_value_missing:{tr['turn']}"]
    said = re.fullmatch(r"\W*(?:number|option|slot)?\s*(\d+)\W*", (tr.get("user") or "").strip().lower())
    if said and int(said.group(1)) != int(value):
        return [f"slot_text_value_conflict:{tr['turn']}"]
    want = _expected_index(rule or "", offered or [])
    if want is None:
        return [f"slot_offer_unknown:{tr['turn']}"]
    if int(value) != want:
        return [f"slot_pick_mismatch:{tr['turn']}"]
    return []


def check(card: dict, t: dict) -> list[str]:
    """Return discard reasons; empty list means keep."""
    reasons: list[str] = []
    turns = t.get("turns", [])
    facts = card["facts"]
    persona = card["persona"]

    if t.get("ended") not in END_OK:
        reasons.append(f"not_ended:{t.get('ended')}")

    # Effective facts drift with scripted corrections; track them in order.
    effective = dict(facts)
    pending_corrections = [e for e in card.get("scripted_events", []) if e["act"] == "correction"]
    for tr in turns:
        sc = tr.get("sidecar") or {}
        act, field, value = sc.get("act"), sc.get("field"), sc.get("value")
        if act not in ACTS:
            reasons.append(f"bad_act:{tr['turn']}")
            continue
        if act == "correction":
            ev = next((e for e in pending_corrections if e["payload"]["field"] == field), None)
            if ev is None:
                reasons.append(f"unscripted_correction:{tr['turn']}:{field}")
                continue
            pending_corrections.remove(ev)
            nv = ev["payload"]["new_value"]
            if field == "days":
                effective["days"] = nv if isinstance(nv, list) else [nv]
            elif field == "doctor":
                effective["doctor_pref"] = {"mode": "named", "name": nv}
            elif field == "phone":
                effective["phone"] = nv
            elif field == "problem":
                effective["problem_category"] = nv["problem_category"]
            continue
        if act != "answer":
            continue
        # Answer: value must match the effective card fact.
        if field == "phone" and _digits(value) != _digits(effective.get("phone")):
            reasons.append(f"phone_mismatch:{tr['turn']}")
        elif field == "days":
            allowed = {_norm(d) for d in effective.get("days", [])}
            given = {_norm(v) for v in re.split(r"[,;]", value or "") if v.strip()}
            if not given or not given <= allowed:
                reasons.append(f"days_mismatch:{tr['turn']}")
        elif field == "doctor":
            want = (effective.get("doctor_pref") or {}).get("name")
            if want and _norm(value) != _norm(want):
                reasons.append(f"doctor_mismatch:{tr['turn']}")
        elif field == "session_type" and _norm(value) != _norm(effective.get("session_type")):
            reasons.append(f"session_type_mismatch:{tr['turn']}")
        elif field == "problem":
            if _norm(value) != _norm(effective.get("problem_category")):
                reasons.append(f"category_mismatch:{tr['turn']}")
            label = _norm(effective.get("problem_category"))
            text = _norm(tr.get("user"))
            if label and re.search(rf"\b{re.escape(label)}\b", text):
                if not (label in ORDINARY_LABELS and persona["clarity"] == "some_idea"):
                    reasons.append(f"label_in_utterance:{tr['turn']}")
        elif field == "slot":
            if _norm(sc.get("slot_rule")) != _norm(facts.get("slot_rule")):
                reasons.append(f"slot_rule_mismatch:{tr['turn']}")
            else:
                reasons.extend(_check_slot_pick(tr, turns, facts.get("slot_rule")))
        elif field == "patient_type" and _norm(value) != _norm(facts.get("patient_type")):
            reasons.append(f"patient_type_mismatch:{tr['turn']}")

    # Verbatim sentences must appear in a turn answering that state.
    for state, sentence in (card.get("verbatim") or {}).items():
        hit = any(tr.get("answering_state") == state and _norm(sentence) in _norm(tr.get("user")) for tr in turns)
        if not hit:
            reasons.append(f"verbatim_missing:{state}")

    # Scripted events must fire in their state, unless the session ended first.
    for ev in card.get("scripted_events", []):
        fired = any((tr.get("sidecar") or {}).get("act") == ev["act"] and tr.get("answering_state") == ev["at_state"] for tr in turns)
        if not fired:
            reached = any(tr.get("answering_state") == ev["at_state"] for tr in turns)
            reasons.append("scenario_not_exercised" if not reached else f"event_missed:{ev['at_state']}:{ev['act']}")
    return reasons


def run(pool: str, dry_run: bool) -> tuple[int, int, Counter]:
    cards = {p.stem: json.loads(p.read_text()) for p in (ROOT / "cards" / pool).glob("*.json")}
    tdir = ROOT / "transcripts" / pool
    kept = discarded = 0
    hist: Counter = Counter()
    for cid, card in sorted(cards.items()):
        path = tdir / f"{cid}.json"
        if not path.exists():
            hist["missing_transcript"] += 1
            continue
        t = json.loads(path.read_text())
        reasons = check(card, t)
        if not reasons:
            kept += 1
            continue
        discarded += 1
        hist.update(r.split(":")[0] for r in reasons)
        if not dry_run:
            t["discard_reasons"] = reasons
            dest = ROOT / "transcripts" / "discarded" / f"{cid}.json"
            dest.write_text(json.dumps(t, indent=2) + "\n")
            path.unlink()
    return kept, discarded, hist


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pool", default="all", choices=["dev", "heldout", "all"])
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    for pool in (["dev", "heldout"] if a.pool == "all" else [a.pool]):
        kept, disc, hist = run(pool, a.dry_run)
        total = kept + disc
        rate = (disc / total * 100) if total else 0.0
        print(f"{pool}: kept={kept} discarded={disc} missing={hist.pop('missing_transcript', 0)} discard_rate={rate:.1f}%")
        for k, v in sorted(hist.items()):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
