"""Write plain-conversation inputs for the judge: user and bot lines only.

The judge must never see the card, the sidecar, the scenario, or the product's internal state, so
this script strips everything except turn number, user text and bot reply.
Usage: uv run python -m evals.judge_prepare [--pool dev|heldout|all]
Output: evals/judge_input/<pool>/<card_id>.txt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def render(t: dict) -> str:
    lines = [f"conversation_id: {t['card_id']}", f"turns: {len(t['turns'])}", ""]
    for tr in t["turns"]:
        lines.append(f"[turn {tr['turn']}]")
        lines.append(f"USER: {tr['user']}")
        lines.append(f"BOT: {tr['bot']['reply']}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="all", choices=["dev", "heldout", "all"])
    a = ap.parse_args()
    n = 0
    for pool in (["dev", "heldout"] if a.pool == "all" else [a.pool]):
        out = ROOT / "judge_input" / pool
        out.mkdir(parents=True, exist_ok=True)
        for p in sorted((ROOT / "transcripts" / pool).glob("*.json")):
            t = json.loads(p.read_text())
            (out / f"{t['card_id']}.txt").write_text(render(t))
            n += 1
    print(f"judge inputs written: {n}")


if __name__ == "__main__":
    main()
