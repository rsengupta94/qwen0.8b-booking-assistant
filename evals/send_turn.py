"""Send one simulated user turn to the product and append it to the card's transcript.

The simulator sub-agent decides the words and the sidecar; this script owns the file format,
the session id, and the end-of-session detection. Usage:

  uv run python -m evals.send_turn --card evals/cards/dev/A1__x.json --server http://127.0.0.1:8791 \
      --model-id qwen3.5-0.8b-q8 --prompt-version baseline --simulator-model claude-sonnet-5 \
      --text "hi, I need an appointment" --act answer [--field days --value wednesday] [--field slot --value 2 --slot-rule first]

Prints the bot reply, the state the bot is now in, and ENDED:<kind> when the session is over.
Refuses to send after the session ended or past TURN_CAP. `--give-up` closes a looping session as
gave_up; that transcript is kept and scored as a product failure, not discarded.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parent
TURN_CAP = 25
ACTS = ("answer", "repeat", "faq_question", "correction", "non_answer", "wants_other")
END_KINDS = {"confirm_booking": "booking_confirmed", "handoff": "handoff"}


def transcript_path(card: dict) -> Path:
    return ROOT / "transcripts" / card["pool"] / f"{card['card_id']}.json"


def new_transcript(card: dict, a: argparse.Namespace) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "card_id": card["card_id"],
        "persona_id": card["persona_id"],
        "scenario_id": card["scenario_id"],
        "pool": card["pool"],
        "eval_set_version": card["eval_set_version"],
        "run": {
            "model_id": a.model_id,
            "prompt_version": a.prompt_version,
            "simulator_model": a.simulator_model,
            "session_id": f"{card['card_id']}__{stamp}",
            "generated_at": stamp,
        },
        "turns": [],
        "ended": None,
    }


def post(server: str, body: dict) -> dict:
    req = request.Request(f"{server}/message", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--card", required=True)
    p.add_argument("--server", required=True)
    p.add_argument("--model-id", required=True)
    p.add_argument("--prompt-version", required=True)
    p.add_argument("--simulator-model", required=True)
    p.add_argument("--text", default=None)
    p.add_argument("--act", default=None, choices=ACTS)
    p.add_argument("--give-up", action="store_true", help="close the transcript as gave_up without sending; use when the bot loops")
    p.add_argument("--field", default=None)
    p.add_argument("--value", default=None)
    p.add_argument("--slot-rule", default=None)
    a = p.parse_args()

    card = json.loads(Path(a.card).read_text())
    path = transcript_path(card)
    t = json.loads(path.read_text()) if path.exists() else new_transcript(card, a)
    if t["ended"]:
        sys.exit(f"REFUSED: session already ended ({t['ended']})")
    if a.give_up:
        t["ended"] = "gave_up"
        path.write_text(json.dumps(t, indent=2) + "\n")
        print("ENDED:gave_up")
        return
    if a.text is None or a.act is None:
        sys.exit("REFUSED: --text and --act are required unless --give-up")
    if len(t["turns"]) >= TURN_CAP:
        t["ended"] = "turn_cap"
        path.write_text(json.dumps(t, indent=2) + "\n")
        sys.exit("REFUSED: turn cap reached; transcript closed as turn_cap")

    if a.field == "slot":
        said = re.fullmatch(r"\W*(?:number|option|slot)?\s*(\d+)\W*", a.text.strip().lower())
        if said and (a.value is None or not str(a.value).isdigit() or int(said.group(1)) != int(a.value)):
            sys.exit(f"REFUSED (not sent): your text says slot {said.group(1)} but --value is {a.value}. "
                     "Make them the same number, then resend.")
        if a.value is None or not str(a.value).isdigit():
            sys.exit("REFUSED (not sent): a slot pick needs --value <number of the offered slot you took>.")
    prev_state = t["turns"][-1]["bot"]["state"] if t["turns"] else "GREET"
    t0 = time.time()
    resp = post(a.server, {"session_id": t["run"]["session_id"], "model_id": a.model_id,
                           "prompt_version": a.prompt_version, "text": a.text})
    facts = (resp.get("debug") or {}).get("reply_facts") or {}
    kind = facts.get("kind")
    offered = [sl["start"] for sl in facts.get("slots", [])] if kind == "present_slots" else None
    booking = facts.get("booking") if kind == "confirm_booking" else None
    turn = {
        "turn": len(t["turns"]) + 1,
        "answering_state": prev_state,
        "user": a.text,
        "sidecar": {"act": a.act, "field": a.field, "value": a.value, "slot_rule": a.slot_rule},
        "bot": {"reply": resp["reply"], "state": resp["state"], "kind": kind, "offered_slots": offered, "booking": booking,
                "fallback_used": resp["debug"]["fallback_used"], "latency_ms": int((time.time() - t0) * 1000)},
    }
    t["turns"].append(turn)
    if kind in END_KINDS:
        t["ended"] = END_KINDS[kind]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(t, indent=2) + "\n")

    print(f"TURN {turn['turn']} | bot state now: {resp['state']}")
    print(f"BOT: {resp['reply']}")
    if t["ended"]:
        print(f"ENDED:{t['ended']}")


if __name__ == "__main__":
    main()
