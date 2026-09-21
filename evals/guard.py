"""Held-out guard: no few-shot line in prompts/*/ may contain a held-out user utterance.

Compares normalised text. An utterance of four or more words that appears inside any prompt line,
or a prompt line of four or more words that appears inside an utterance, fails the run.
Prints counts and the offending prompt file and line number only, never the utterance.
Usage: uv run python -m evals.guard
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT.parent / "prompts"
MIN_WORDS = 4


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def heldout_utterances() -> list[str]:
    out = []
    for p in (ROOT / "transcripts" / "heldout").glob("*.json"):
        for tr in json.loads(p.read_text())["turns"]:
            u = norm(tr.get("user") or "")
            if len(u.split()) >= MIN_WORDS:
                out.append(u)
    return out


def prompt_lines() -> list[tuple[str, int, str]]:
    out = []
    for p in sorted(PROMPTS.rglob("*.md")):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            n = norm(line)
            if len(n.split()) >= MIN_WORDS:
                out.append((str(p.relative_to(ROOT.parent)), i, n))
    return out


def check() -> list[tuple[str, int]]:
    utts = heldout_utterances()
    hits = []
    for path, i, line in prompt_lines():
        if any(u in line or line in u for u in utts):
            hits.append((path, i))
    return hits


def main() -> None:
    hits = check()
    print(f"guard: heldout_utterances={len(heldout_utterances())} prompt_lines={len(prompt_lines())} hits={len(hits)}")
    for path, i in hits:
        print(f"  CONTAMINATED {path}:{i}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
