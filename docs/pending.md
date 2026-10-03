# Pending tasks

Written 2026-10-02 from design.md, `eval_design_v1.md`, the E5 handoff in `eval_phases_v1.md`, and section H of `eval_decision_log.md`. Tick a box when the task is done and committed. "You" is the human owner; "I" is Claude Code.

## Step 1: before E5

- [x] **1. Health check after the break.** Run `bash checks/all.sh` from the repo root (phases 0 to 6, then E1 to E4) and confirm it ends with `all: PASS`.
  - Your input: approve the run. It loads the model and takes several minutes. The E3 check inside it writes one more results file (see task 3).
  - Done 2026-10-03, partial. Phases 0 to 6, E1, E2 and the E3 tests and guard passed. The run hit a 1-hour limit during the dev replay. The 14 of 20 replays that finished matched the saved ones apart from session ids and timestamps. Not reached: 6 replays, E3 scoring, E4. Nothing had changed product code, transcripts or verdicts since the last green run. The full run is deferred to the end of E5, where it is required anyway (about 75 minutes at today's speed). The leftover replay files were reverted and the partial log deleted.

- [x] **2. Simulator audit.** Owed since E2 (eval design section 7). I build a sheet of about 20 problem descriptions, one per dev conversation, from dev transcripts only. You mark each one: would a reasonable receptionist land on the card's category? Yes, no, or unsure.
  - Your input: the labels. A decision: are unfaithful cards only reported, or also excluded from the `extract_problem` score?
  - Done 2026-10-03. Blind design: you picked a category per message without seeing the card's. Simulator wording faithful on 15 of 17, both misses on the anxiety/stress line; card-verbatim D1 sentence 2 of 2. Report only, no exclusion (decision log E9). Findings in `eval_findings_log.md` 2026-10-03; open items added to decision log section H.

- [x] **3. Results-file pile-up.** Every E3 check run writes a new file in `evals/results/`. Flagged as unaddressed in the E5 handoff.
  - Your input: overwrite, keep the latest per setup, or leave as is.
  - Done 2026-10-03. The scorer skips the write when the latest file for the same setup holds the same scores, and reports that file's run_id instead (decision log E10). The two 2026-09-21 files, identical to the 2026-09-23 file apart from run_id and judge data, were deleted; they remain in git history.

## Step 2: E5, the Evals tab

- [ ] **4. Settle the four open questions** from the E5 handoff. My recommendations in brackets.
  - [ ] a. Held-out drill-down: what can it show? (Structured fields only, never conversation text.)
  - [ ] b. Run list: which runs does it show? (Latest per prompt version, model and eval set.)
  - [ ] c. Rule 8 in `CLAUDE.md`: may the product read `evals/results/*.json`? (Yes as data files; never import from the `evals` package.)
  - [ ] d. Headline view: which pool is the default? (Held-out; dev available but labelled as dev.)
  - Your input: a decision on each.

- [ ] **5. Build E5.** I list the files and wait for your OK, write `checks/eval_5.sh` first, then build `/evals/runs`, `/evals/runs/{id}` and the tab. The tab must reproduce the handoff numbers: 42 of 61 held-out sessions passed; calls 805 / 78 / 168 / 629; judge agreement 0.9; 152 of 488 held-out replies not fitting.
  - Your input: approve the file list, review the tab, approve the commit.

- [ ] **6. Log entries for the article.** A dated entry in `eval_findings_log.md`, and any new decisions with their rejected alternatives in `eval_decision_log.md`.
  - Your input: review the entries.

## Step 3: Phase 7, deploy to Hugging Face Spaces

- [ ] **7. Deploy setup.** Dockerfile, model download at startup, README model card, `checks/phase_7.sh`.
  - Your input: your Hugging Face account and Space name, which models to ship, whether Docker is installed locally, and explicit approval before anything is published.

- [ ] **8. Public or private Space.** This is a mental-health chatbot with no distress handling, which v1 deliberately excludes. If the Space is public, anyone can type a crisis message into it.
  - Your input: a private Space, or a public one with a fixed banner text written in code, not by the model. Check with the right team before anything goes public.

## Step 4: the next prompt version

- [ ] **9. Design what v2 changes.** design.md only says `persona/`: the same prompts, with examples written in persona voice. Most of the top baseline failures look like code or schema problems, not wording problems:
  - The problem schema has no "not a problem" option (decision G4).
  - The days step (ASK_DAYS) never asks again.
  - The turn classifier rewinds on off-topic remarks.
  - The model-written slot list fails its own fact check on 50 of 89 held-out calls.
  - Your input: decide what v2 is meant to fix, and in what scope.

- [ ] **10. Build v2, rerun the evals, compare against baseline.** Depends on task 9.
  - Your input: review the prompts and validators, as for every phase.

- [ ] **11. Comparison view in the Evals tab.** Built only once v2 exists.

## Optional: strengthen the eval

- [ ] **12. Pick which, if any, are worth doing** (from `eval_decision_log.md` section H):
  - A second person labels the same 40 calibration replies, to separate judge error from labeller variance.
  - An automatic guard so the scorer's path table can't drift from `app/state_machine.py`.
  - Run held-out replay in the E3 check. This doubles the runtime.
  - Your input: your choice.

## Not pending: parked outside v1

Each needs its own design pass first: safety and distress handling, booking for someone else, multilingual input, fine-tuning, logprob-based confidence, full-ranking doctor matching, and publishing the simulated conversation set.
