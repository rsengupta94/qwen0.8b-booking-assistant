# Eval Build Phases v1

Phase plan for `eval_design_v1.md` (called "eval design" below). Same rules as design.md section 11: each phase has an executable check, written first, and the phase is done when it and `checks/all.sh` exit 0. Eval phases are numbered E1 to E5 and their checks are `checks/eval_N.sh`, kept separate from product phases.

Two phases (E2, E4) have a manual step where Claude Code sub-agents run. The check for those phases validates the artifacts the sub-agents wrote; it does not run them.

## Layout

One package at repo root, never imported by `app/`.

```
evals/
  personas/          12 persona files
  scenarios/         27 scenario files, each with expected outcome and prompts exercised
  cards/
    dev/             sampled cards, readable while writing prompts
    heldout/         sampled cards, opened only by scripts
  transcripts/
    dev/  heldout/   one file per card: turns, sidecar inline, footer
    discarded/       failed fidelity gate, with reason
  verdicts/          judge output, one file per run
  calibration/       human labels for the judge
  results/           one results file per scoring run
  sample_cards.py    persona x scenario sampler and pool split
  fidelity.py        gate from eval design 5c stage 3
  path_table.py      expected next state and fields from sidecar acts; never imports app.state_machine
  score.py           trajectory scoring, session outcome, results file
  replay.py          re-sends saved user turns; renders slot choice from rule
  guard.py           held-out guard over prompts/*/
  briefs/            simulator and judge sub-agent briefs (markdown, versioned)
```

## E1: cards

Persona files from eval design 5a with behavior lines. Scenario files for A1 to D5 with facts, scripted events, verbatim phrases, `stop_after`, expected outcome, prompts exercised. Sampler produces about 20 dev and 60 held-out cards under the coverage rule and stamps `eval_set_version: 1`.

`checks/eval_1.sh`: runs the sampler, then asserts every scenario appears under at least 3 personas, every persona in at least 5 scenarios, no card id in both pools, every card has all fields from eval design 5a, and no card file contains the expected outcome.

Human review: every persona and scenario file before commit.

## E2: generation and fidelity gate

Simulator brief in `briefs/simulator.md`: receives one card, the behavior table, the `/message` URL; plays to `stop_after`; writes one transcript with a sidecar per turn. `fidelity.py` implements the gate: sidecar matches card, no enum label in the problem utterance, verbatim phrases present, turn cap, scripted event reached or card marked "scenario not exercised".

Manual: a Claude Code session spawns one sub-agent per card on a mid-tier model against the local product. Dev pool first, then held-out. The human reads the ambiguous-category audit sample from dev transcripts only.

`checks/eval_2.sh`: runs the gate over both transcript pools, asserts every card has a transcript or a discard record, prints discard rate per pool, and fails if held-out discard rate is above 10 percent. Prints nothing from held-out transcripts beyond counts.

## E3: path table, scoring, replay, guard

`path_table.py` as a small table, state x act to next state and expected fields, with pytest over hand-built sidecar sequences for every scenario group. `score.py` joins transcripts to the product JSONL by session and turn, assigns pass, rescued, silent-wrong per call, session outcome per card, persona-caused hand-off as pass, and writes a results file keyed by `prompt_version`, `validator_version`, `model_id`, `eval_set_version`. `replay.py` re-sends saved user turns, rendering slot choice from the rule. `guard.py` fails when any few-shot in `prompts/*/` matches a held-out utterance.

`checks/eval_3.sh`: pytest on the path table; runs the guard; replays all dev transcripts against the current product version and asserts the replay JSONL matches the generation JSONL on state and validator outcome per turn; runs the scorer over both pools and asserts a results file with non-empty counts in all three outcome classes or an explicit zero.

### E3 notes (2026-09-20)

- `app/tools/mock_backend.now()` honours a `BOOKING_CLOCK` environment variable so the replay harness can pin the calendar to a transcript's generation date. Off by default; the only product touch in the eval phases.
- Backend reset stays outside the product: the replay harness starts a fresh server per card.
- Transcripts now record the booking record on confirm turns. For the 81 E2 transcripts the scorer recovers doctor and start from the confirmation reply, which the confirm_booking validator guarantees to contain them.
- `doctor_pick` is judged against the category the product actually extracted, so a wrong category is charged to extract_problem once, not twice.
- The product's shortlist pick is used for slot routing only, never for the expected-doctor set.
- Product logs from generation live in `evals/product_logs/` because `logs/` is gitignored.

## E4: judge

Judge brief in `briefs/judge.md`: binary coherence per bot turn with the three failure shapes from eval design 6, one-line reason, reads transcripts only. Verdict file format. Calibration set: the human labels 30 to 50 bot turns from dev transcripts before the judge runs.

Manual: a Claude Code session spawns fresh sub-agents on the strongest model over both pools.

`checks/eval_4.sh`: asserts a verdict for every bot turn in every kept transcript, computes judge-versus-human agreement on the calibration set, fails below 75 percent agreement, and merges verdict counts into the results file.

### E4 notes (2026-09-23)

- The judge self-reports its model id; the E4 check fails if verdict files name more than one model. Held-out was re-judged once to meet this after calibration ran on a newer Opus.
- The labelling sheet is `evals/calibration/labels.xlsx` (labels sheet plus a full-conversation trace sheet); the merge reads it directly, with the CSV as fallback.
- Result: 90 percent agreement on 40 dev replies; 152 of 488 held-out replies judged as not fitting.

## Handoff for E5 (written 2026-09-23)

**Status.** E1 to E4 are done and green: `4dfe1f7`, `becb861`, `ce386c2`, `d105f5c`. E5 is next. Start it the usual way: list the files to create or change and wait for confirmation, then write `checks/eval_5.sh` first.

**Current results file:** `evals/results/generation_baseline_qwen3.5-0.8b-q8_set1_20260923T230445.json`. It is the only one with a `judge` section. The two 2026-09-21 files are earlier E3 runs with identical scoring numbers and no judge data. Each E3 check run writes another results file; that accumulation is known and not yet addressed.

**Numbers the UI must reproduce**, as a correctness check on the tab:

| Metric | Value |
|---|---|
| Held-out sessions passed | 42 of 61 |
| Calls, both pools: pass / rescued / silent-wrong / unscored | 805 / 78 / 168 / 629 |
| Judge agreement on 40 human labels | 0.9 |
| Held-out replies judged as not fitting | 152 of 488 |

**Open questions to settle before building.** Recommendations are mine; the decisions are the user's.

1. *Held-out drill-down.* The spec says a heatmap cell opens its turns and log lines. For held-out cards that puts held-out conversations on screen, which breaks the rule that held-out text is never read while writing prompts (CLAUDE.md rule 8, decision log D1 and D4). **Recommended:** dev drill-down shows everything; held-out drill-down shows structured fields only (prompt, expected versus actual value, outcome, reason code) and never user or bot text. Contamination is about phrasing, so this keeps the headline clickable without leaking it.
2. *Which runs the run list shows.* **Recommended:** the latest run per (`prompt_version`, `model_id`, `eval_set_version`), which today is one run. Older runs stay on disk.
3. *Rule 8 and the new routes.* E5 adds `/evals/runs` and `/evals/runs/{id}` to the product. **Recommended wording:** the product may read `evals/results/*.json` as data files; it must not import anything from the `evals` package. The eval code writes results; the product only reads JSON.
4. *Which pool the headline shows.* The design says reported numbers come only from held-out. **Recommended:** held-out is the default view; dev is available but labelled as dev.

**Before drawing the heatmap:** load the `dataviz` skill; cells are rates over calls made, with counts on hover (eval design section 8).

**Working norm for the article.** At the end of every eval phase, add a dated entry to `docs/eval_findings_log.md` (numbers, harness lessons, product observations) and add any decision with its rejected alternative to `docs/eval_decision_log.md`. The user is writing an article from these two files.

## E5: Evals tab

An Evals tab in the web UI reading `evals/results/`. Views: session pass rate, prompt x outcome-class heatmap with rates and hover counts, click-through from cell to turns to JSONL lines, discard rate, judge agreement. Comparison view: results format supports two runs side by side; the view is built when a second `prompt_version` exists. `/evals/runs` and `/evals/runs/{id}` endpoints.

`checks/eval_5.sh`: curls both endpoints, asserts the run list is non-empty and a run payload has heatmap cells for every NLU and NLG prompt name in `prompts/baseline/`.

## Out of these phases

Human trace labeling by source, comparison view, publishing transcripts as a dataset. Human traces already carry a source label from the product log; nothing to build until a second version or real users exist.
