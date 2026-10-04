"""Build the static Hugging Face Space (design.md 11a, phase 7).

Copies the static page (clients/space/) and the shared Evals script (clients/ui/evals.js), fills the Space
card's numbers, and writes the data the page reads:
  data/evals/runs.json, data/evals/runs/<run_id>.json   the eval server's two endpoint payloads, as files
  data/conversations.json                              the dev conversations with per-turn log lines
Held-out appears only as the eval server already shapes it: structured fields, no text (eval decision log I1).
After writing, every exported string is scanned for held-out-only utterances; any hit fails the export and
prints the file name only. Dev pool only for conversations.
Usage: uv run python -m evals.export_space [--out space_build]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from evals import guard, server

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
MARKER = ".space_build"  # only a folder carrying this marker is ever wiped


def conversations(verdicts: dict[str, dict]) -> list[dict]:
    logs = server.dev_logs()
    out = []
    for p in sorted((ROOT / "transcripts" / "dev").glob("*.json")):
        t = json.loads(p.read_text())
        scenario = json.loads((ROOT / "scenarios" / f"{t['scenario_id']}.json").read_text())
        by_turn = logs.get(t["run"]["session_id"], {})
        out.append({
            "card_id": t["card_id"], "scenario_id": t["scenario_id"], "scenario_title": scenario["title"],
            "persona_id": t["persona_id"], "session": verdicts.get(t["card_id"], {}),
            "turns": [{"turn": tr["turn"], "user": tr["user"], "reply": tr["bot"]["reply"], "state": tr["bot"]["state"],
                       "kind": tr["bot"].get("kind"), "fallback_used": tr["bot"].get("fallback_used"),
                       "log": [{k: l.get(k) for k in ("state", "prompt_name", "ok", "reason_code", "raw_output", "latency_ms")}
                               for l in by_turn.get(tr["turn"], [])]}
                      for tr in t["turns"]],
        })
    return out


def strings(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [s for x in v.values() for s in strings(x)]
    if isinstance(v, list):
        return [s for x in v for s in strings(x)]
    return []


def heldout_only() -> list[str]:
    """Held-out utterances whose wording appears in no dev patient message. Short remarks shared by both
    pools are dev's own text too, so exporting them shows nothing that only held-out contains."""
    dev = " | ".join(guard.norm(tr.get("user") or "") for p in (ROOT / "transcripts" / "dev").glob("*.json")
                     for tr in json.loads(p.read_text())["turns"])
    return [u for u in guard.heldout_utterances() if u not in dev]


def heldout_leaks(out: Path) -> list[str]:
    """Exported files containing a held-out-only utterance. File names only."""
    only_heldout = heldout_only()
    hits = []
    for f in sorted(out.rglob("*")):
        if not f.is_file() or f.name == MARKER:
            continue
        texts = strings(json.loads(f.read_text())) if f.suffix == ".json" else [f.read_text()]
        blob = " | ".join(guard.norm(s) for s in texts)
        if any(u in blob for u in only_heldout):
            hits.append(str(f.relative_to(out)))
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "space_build"))
    out = Path(ap.parse_args().out)
    if out.exists():
        if not (out / MARKER).exists() and any(out.iterdir()):
            sys.exit(f"refusing to wipe {out}: not a space build folder")
        shutil.rmtree(out)
    (out / "data" / "evals" / "runs").mkdir(parents=True)
    (out / MARKER).write_text("")

    for name in ("index.html", "replay.js"):
        shutil.copy(REPO / "clients" / "space" / name, out / name)
    shutil.copy(REPO / "clients" / "ui" / "evals.js", out / "evals.js")

    runs = server.runs()
    (out / "data" / "evals" / "runs.json").write_text(json.dumps(runs, indent=1))
    payloads = {}
    for r in runs:
        payloads[r["run_id"]] = server.run(r["run_id"])
        (out / "data" / "evals" / "runs" / f"{r['run_id']}.json").write_text(json.dumps(payloads[r["run_id"]]))

    # Conversation verdicts come from the run scored on the same prompt version and model as the transcripts.
    gen = json.loads(next((ROOT / "transcripts" / "dev").glob("*.json")).read_text())["run"]
    match = next(r for r in runs if (r["prompt_version"], r["model_id"]) == (gen["prompt_version"], gen["model_id"]))
    results = server.load(server.latest_per_setup()[match["run_id"]])
    verdicts = {s["card_id"]: s["session"] for s in results["sessions"] if s["pool"] == "dev"}
    convs = conversations(verdicts)
    (out / "data" / "conversations.json").write_text(json.dumps(convs))

    held = payloads[match["run_id"]]["pools"]["heldout"]
    card = (REPO / "clients" / "space" / "README.md").read_text()
    for k, v in {"{{prompt_version}}": match["prompt_version"], "{{model_id}}": match["model_id"],
                 "{{passed}}": held["sessions"]["passed"], "{{sessions}}": held["sessions"]["n"],
                 "{{fits_no}}": held["coherence"]["fits_no"], "{{replies}}": held["coherence"]["replies"]}.items():
        card = card.replace(k, str(v))
    (out / "README.md").write_text(card)

    leaks = heldout_leaks(out)
    if leaks:
        sys.exit(f"FAIL: held-out utterances found in {leaks}")
    print(f"wrote {out}: {len(runs)} run(s), {len(convs)} conversations; held-out scan clean")


if __name__ == "__main__":
    main()
