"""CLI client for the booking assistant API.

Interactive:  uv run python clients/cli.py --model qwen3.5-0.8b-q8 --prompt-version baseline
Scripted:     uv run python clients/cli.py ... --script checks/conversations/new_patient.txt [--json]
"""

import argparse
import json
import sys
import uuid

import httpx


def send(client: httpx.Client, url: str, session_id: str, model: str, version: str, text: str) -> dict:
    r = client.post(f"{url}/message", json={
        "session_id": session_id, "model_id": model, "prompt_version": version, "text": text,
    }, timeout=300)
    r.raise_for_status()
    return r.json()


def show(text: str, resp: dict) -> None:
    d = resp["debug"]
    print(f"you:  {text}")
    print(f"bot:  {resp['reply'] or json.dumps(d['reply_facts'])}")
    calls = ", ".join(f"{c['prompt_name']}{'' if c['ok'] else ' FALLBACK:' + c['reason_code']}" for c in d["validator_results"])
    print(f"      [{resp['state']}] {calls} ({d['latency_ms']} ms)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--model", required=True)
    p.add_argument("--prompt-version", required=True)
    p.add_argument("--session", default=None)
    p.add_argument("--script", default=None, help="file with one user turn per line")
    p.add_argument("--json", action="store_true", help="print one JSON object per turn")
    a = p.parse_args()
    session_id = a.session or f"cli_{uuid.uuid4().hex[:8]}"

    if a.script:
        turns = [l.strip() for l in open(a.script) if l.strip()]
    else:
        turns = None

    with httpx.Client() as client:
        if turns is not None:
            for text in turns:
                resp = send(client, a.url, session_id, a.model, a.prompt_version, text)
                if a.json:
                    print(json.dumps({"session_id": session_id, "text": text, **resp}), flush=True)
                else:
                    show(text, resp)
            return
        print(f"session {session_id}. Type a message; Ctrl-D to quit.")
        for line in sys.stdin:
            text = line.strip()
            if not text:
                continue
            resp = send(client, a.url, session_id, a.model, a.prompt_version, text)
            show(text, resp)
            if resp["state"] == "END":
                break


if __name__ == "__main__":
    main()
