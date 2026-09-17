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

## E4: judge

Judge brief in `briefs/judge.md`: binary coherence per bot turn with the three failure shapes from eval design 6, one-line reason, reads transcripts only. Verdict file format. Calibration set: the human labels 30 to 50 bot turns from dev transcripts before the judge runs.

Manual: a Claude Code session spawns fresh sub-agents on the strongest model over both pools.

`checks/eval_4.sh`: asserts a verdict for every bot turn in every kept transcript, computes judge-versus-human agreement on the calibration set, fails below 80 percent agreement, and merges verdict counts into the results file.

## E5: Evals tab

An Evals tab in the web UI reading `evals/results/`. Views: session pass rate, prompt x outcome-class heatmap with rates and hover counts, click-through from cell to turns to JSONL lines, discard rate, judge agreement. Comparison view: results format supports two runs side by side; the view is built when a second `prompt_version` exists. `/evals/runs` and `/evals/runs/{id}` endpoints.

`checks/eval_5.sh`: curls both endpoints, asserts the run list is non-empty and a run payload has heatmap cells for every NLU and NLG prompt name in `prompts/baseline/`.

## Out of these phases

Human trace labeling by source, comparison view, publishing transcripts as a dataset. Human traces already carry a source label from the product log; nothing to build until a second version or real users exist.
