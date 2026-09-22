"""Merge judge verdicts into a results file and compute judge-versus-human agreement.

Agreement is over rows in evals/calibration/labels.csv whose label is yes or no (unsure excluded),
matched to verdicts by card_id and turn. Fails below the floor.
Usage: uv run python -m evals.judge_merge [--results <path>] [--floor 0.75]
Prints counts only.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_verdicts() -> dict[str, dict]:
    out = {}
    for p in (ROOT / "verdicts").glob("*/*.json"):
        v = json.loads(p.read_text())
        out[v["card_id"]] = v
    return out


def read_labels(labels_path: Path) -> list[dict]:
    """labels.xlsx (sheet 'labels') wins when present next to labels.csv; the CSV is the fallback."""
    xlsx = labels_path.with_suffix(".xlsx")
    if xlsx.exists():
        from openpyxl import load_workbook
        ws = load_workbook(xlsx, read_only=True)["labels"]
        it = ws.iter_rows(values_only=True)
        hdr = [str(h) for h in next(it)]
        return [{k: ("" if v is None else str(v)) for k, v in zip(hdr, r)} for r in it if r and r[1]]
    return list(csv.DictReader(labels_path.open()))


def agreement(labels_path: Path, verdicts: dict[str, dict]) -> dict:
    rows = read_labels(labels_path)
    labelled = [r for r in rows if r["label"].strip().lower() in ("yes", "no")]
    unsure = sum(1 for r in rows if r["label"].strip().lower() == "unsure")
    agree = 0
    matched = 0
    confusion = Counter()
    for r in labelled:
        v = verdicts.get(r["card_id"])
        if not v:
            continue
        j = next((x["fits"] for x in v["verdicts"] if x["turn"] == int(r["turn"])), None)
        if j is None:
            continue
        matched += 1
        h = r["label"].strip().lower()
        confusion[f"human_{h}/judge_{j}"] += 1
        agree += (h == j)
    return {"rows": len(rows), "labelled": len(labelled), "unsure": unsure, "matched": matched,
            "agree": agree, "rate": (agree / matched) if matched else None, "confusion": dict(confusion)}


def coherence_counts(verdicts: dict[str, dict], sessions: list[dict]) -> dict:
    """Per pool and per bot reply kind, yes/no counts. Kind comes from the transcript."""
    by = defaultdict(Counter)
    for s in sessions:
        v = verdicts.get(s["card_id"])
        if not v:
            by[s["pool"]]["missing_verdict_file"] += 1
            continue
        t = json.loads((ROOT / "transcripts" / s["pool"] / f"{s['card_id']}.json").read_text())
        kinds = {tr["turn"]: tr["bot"].get("kind") or "unknown" for tr in t["turns"]}
        for x in v["verdicts"]:
            by[s["pool"]][f"{kinds.get(x['turn'], 'unknown')}/{x['fits']}"] += 1
            by[s["pool"]][x["fits"]] += 1
    return {k: dict(v) for k, v in by.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=None)
    ap.add_argument("--labels", default=str(ROOT / "calibration" / "labels.csv"))
    ap.add_argument("--floor", type=float, default=0.75)
    a = ap.parse_args()
    results_path = Path(a.results) if a.results else Path(sorted(glob.glob(str(ROOT / "results" / "generation_*.json")))[-1])
    r = json.loads(results_path.read_text())
    verdicts = load_verdicts()
    agr = agreement(Path(a.labels), verdicts)
    coh = coherence_counts(verdicts, r["sessions"])
    r["judge"] = {"model": next((v["judge_model"] for v in verdicts.values()), None), "n_verdict_files": len(verdicts),
                  "agreement": agr, "coherence": coh, "floor": a.floor}
    results_path.write_text(json.dumps(r, indent=2) + "\n")
    print(f"verdict_files={len(verdicts)} labelled={agr['labelled']} unsure={agr['unsure']} matched={agr['matched']} "
          f"agree={agr['agree']} rate={agr['rate'] if agr['rate'] is None else round(agr['rate'], 3)}")
    for pool, c in coh.items():
        print(f"{pool}: yes={c.get('yes', 0)} no={c.get('no', 0)} missing_files={c.get('missing_verdict_file', 0)}")
    if agr["rate"] is None or agr["rate"] < a.floor:
        sys.exit(f"FAIL: agreement {agr['rate']} below floor {a.floor}")


if __name__ == "__main__":
    main()
