"""E1 check: coverage, disjoint pools, complete card fields, no expected outcome in cards."""
import json
from collections import Counter
from pathlib import Path

from evals import sample_cards as sc

PERSONAS = sc.load_dir(sc.PERSONAS)
SCENARIOS = sc.load_dir(sc.SCENARIOS)
CARDS = {pool: sc.load_dir(sc.CARDS / pool) for pool in ("dev", "heldout")}
ALL = CARDS["dev"] + CARDS["heldout"]


def test_inputs_present():
    assert len(PERSONAS) == 12
    assert len(SCENARIOS) == 27
    assert len(ALL) == 27 * sc.CARDS_PER_SCENARIO


def test_every_scenario_under_enough_personas():
    per = Counter(c["scenario_id"] for c in ALL)
    for s in SCENARIOS:
        assert per[s["scenario_id"]] >= 3, s["scenario_id"]


def test_every_persona_in_enough_scenarios():
    per = Counter(c["persona_id"] for c in ALL)
    for p in PERSONAS:
        assert per[p["persona_id"]] >= sc.MIN_SCENARIOS_PER_PERSONA, (p["persona_id"], per[p["persona_id"]])


def test_pools_disjoint_and_sized():
    dev = {c["card_id"] for c in CARDS["dev"]}
    held = {c["card_id"] for c in CARDS["heldout"]}
    assert not dev & held
    assert len(dev) == sc.DEV_SIZE
    assert len(held) >= 50


def test_card_fields_complete_and_no_expected():
    for c in ALL:
        for k in sc.CARD_FIELDS:
            assert k in c, (c["card_id"], k)
        for k in sc.SCENARIO_ONLY:
            assert k not in c, (c["card_id"], k)
        assert c["pool"] in ("dev", "heldout")
        assert c["eval_set_version"] == sc.EVAL_SET_VERSION
        text = json.dumps(c)
        assert "expected" not in text.lower(), c["card_id"]


def test_persona_and_scenario_shapes():
    for p in PERSONAS:
        assert p["proficiency"] in ("proficient", "not_proficient")
        assert p["personality"] in ("patient", "agitated", "inattentive")
        assert p["clarity"] in ("some_idea", "no_idea")
        assert len(p["behaviors"]) >= 3
    for s in SCENARIOS:
        assert s["stop_after"] in ("booking_confirmed", "handoff")
        assert s["expected"]["outcome"] in ("booking", "handoff")
        assert s["prompts_exercised"]
        f = s["facts"]
        assert f["patient_type"] in ("new", "returning")
        for ev in s.get("scripted_events", []):
            assert set(ev) >= {"at_state", "act", "payload"}
            assert ev["act"] in ("correction", "faq_question", "non_answer", "wants_other")


def test_card_compatibility_respected():
    by_id = {s["scenario_id"]: s for s in SCENARIOS}
    for c in ALL:
        allowed = by_id[c["scenario_id"]].get("allowed_clarity")
        if allowed:
            assert c["persona"]["clarity"] in allowed, c["card_id"]
