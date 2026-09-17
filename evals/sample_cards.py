"""Sample cards = persona x scenario, split into dev and held-out pools.

Deterministic (fixed seed). Every scenario gets CARDS_PER_SCENARIO personas chosen
greedily from the compatible ones with the fewest cards so far, so every persona
lands in at least MIN_SCENARIOS_PER_PERSONA scenarios. The expected outcome stays in
the scenario file and is never copied into a card. Run: uv run python -m evals.sample_cards
"""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PERSONAS = ROOT / "personas"
SCENARIOS = ROOT / "scenarios"
CARDS = ROOT / "cards"

EVAL_SET_VERSION = 1
SEED = 20260917
CARDS_PER_SCENARIO = 3
MIN_SCENARIOS_PER_PERSONA = 5
DEV_SIZE = 20

# Fields a card must carry. Checked by tests/test_sample_cards.py.
CARD_FIELDS = [
    "card_id", "persona_id", "scenario_id", "pool", "eval_set_version",
    "persona", "facts", "scripted_events", "verbatim", "stop_after",
]
# Scenario-only fields that must never appear in a card.
SCENARIO_ONLY = ["expected", "prompts_exercised"]


def load_dir(d: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]


def compatible(persona: dict, scenario: dict) -> bool:
    allowed = scenario.get("allowed_clarity")
    return not allowed or persona["clarity"] in allowed


def sample(personas: list[dict], scenarios: list[dict], rng: random.Random) -> list[dict]:
    counts = {p["persona_id"]: 0 for p in personas}
    cards = []
    for sc in scenarios:
        pool = [p for p in personas if compatible(p, sc)]
        if len(pool) < CARDS_PER_SCENARIO:
            raise SystemExit(f"{sc['scenario_id']}: only {len(pool)} compatible personas")
        rng.shuffle(pool)
        pool.sort(key=lambda p: counts[p["persona_id"]])
        for p in pool[:CARDS_PER_SCENARIO]:
            counts[p["persona_id"]] += 1
            cards.append(make_card(p, sc))
    return cards


def make_card(persona: dict, scenario: dict) -> dict:
    return {
        "card_id": f"{scenario['scenario_id']}__{persona['persona_id']}",
        "persona_id": persona["persona_id"],
        "scenario_id": scenario["scenario_id"],
        "pool": None,
        "eval_set_version": EVAL_SET_VERSION,
        "persona": {k: persona[k] for k in ("proficiency", "personality", "clarity", "behaviors")},
        "facts": scenario["facts"],
        "scripted_events": scenario.get("scripted_events", []),
        "verbatim": scenario.get("verbatim", {}),
        "stop_after": scenario["stop_after"],
    }


def split(cards: list[dict], rng: random.Random) -> None:
    order = cards[:]
    rng.shuffle(order)
    for i, c in enumerate(order):
        c["pool"] = "dev" if i < DEV_SIZE else "heldout"


def write(cards: list[dict]) -> None:
    for pool in ("dev", "heldout"):
        d = CARDS / pool
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    for c in cards:
        (CARDS / c["pool"] / f"{c['card_id']}.json").write_text(json.dumps(c, indent=2) + "\n")


def main() -> None:
    rng = random.Random(SEED)
    personas, scenarios = load_dir(PERSONAS), load_dir(SCENARIOS)
    cards = sample(personas, scenarios, rng)
    split(cards, rng)
    write(cards)
    dev = sum(c["pool"] == "dev" for c in cards)
    print(f"personas={len(personas)} scenarios={len(scenarios)} cards={len(cards)} dev={dev} heldout={len(cards) - dev}")


if __name__ == "__main__":
    main()
