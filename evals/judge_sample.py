"""Sample bot turns from dev transcripts for human labelling of reply coherence.

Writes evals/calibration/labels.csv with: card_id, turn, prior_bot, user, bot_reply, label (empty).
Stratified so every scenario group and a spread of bot reply kinds appear. Fixed seed.
Usage: uv run python -m evals.judge_sample [--n 40]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEED = 20260921


def rows_from(t: dict) -> list[dict]:
    out = []
    prior = ""
    for tr in t["turns"]:
        out.append({"card_id": t["card_id"], "turn": tr["turn"], "kind": tr["bot"].get("kind") or "",
                    "prior_bot": prior, "user": tr["user"], "bot_reply": tr["bot"]["reply"]})
        prior = tr["bot"]["reply"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    rng = random.Random(SEED)
    pool = []
    for p in sorted((ROOT / "transcripts" / "dev").glob("*.json")):
        pool.extend(rows_from(json.loads(p.read_text())))
    # Stratify by reply kind so the sample is not all ask_question re-asks.
    by_kind = defaultdict(list)
    for r in pool:
        by_kind[r["kind"]].append(r)
    kinds = sorted(by_kind)
    picked, i = [], 0
    while len(picked) < a.n and any(by_kind.values()):
        k = kinds[i % len(kinds)]
        if by_kind[k]:
            picked.append(by_kind[k].pop(rng.randrange(len(by_kind[k]))))
        i += 1
    picked.sort(key=lambda r: (r["card_id"], r["turn"]))
    out = ROOT / "calibration" / "labels.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["card_id", "turn", "prior_bot", "user", "bot_reply", "label"])
        w.writeheader()
        for r in picked:
            w.writerow({k: r[k] for k in ("card_id", "turn", "prior_bot", "user", "bot_reply")} | {"label": ""})
    print(f"wrote {len(picked)} rows to {out.relative_to(ROOT.parent)}; kinds: {sorted({r['kind'] for r in picked})}")


if __name__ == "__main__":
    main()
