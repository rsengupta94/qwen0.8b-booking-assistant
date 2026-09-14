"""Loads the JSON fixtures once. All facts about doctors, patients and slot patterns come from here."""

import json
from functools import lru_cache
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


@lru_cache(maxsize=None)
def _load(name: str) -> list[dict]:
    with (FIXTURES_DIR / f"{name}.json").open() as f:
        return json.load(f)


def doctors() -> list[dict]:
    return _load("doctors")


def patients() -> list[dict]:
    return _load("patients")


def slot_patterns() -> list[dict]:
    """Weekly recurring pattern: {doctor_id, weekday, times}. mock_backend expands it to real dates."""
    return _load("slots")


def categories() -> list[str]:
    """Sorted union of doctor category tags. This is the enum for extract_problem."""
    return sorted({c for d in doctors() for c in d["categories"]})


def doctor_by_id(doctor_id: str) -> dict | None:
    return next((d for d in doctors() if d["id"] == doctor_id), None)


def clinic() -> dict:
    with (FIXTURES_DIR / "clinic.json").open() as f:
        return json.load(f)
