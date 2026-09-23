# Eval decision log

Why the eval is built the way it is. Written 2026-09-22 from the design and build sessions of 18 to 22 September, while the arguments were still recoverable. The other docs record what was decided; this one records what it was decided *against* and on what grounds.

Companion to `eval_design_v1.md` (the rules), `eval_phases_v1.md` (the phases), `eval_findings_log.md` (the runs).

---

## A. What gets measured

### A1. Gold is a trajectory of decisions, not a set of expected replies
**Decided:** Gold is the expected NLU field values, next state, and final booking record. Never the expected reply text.
**Why:** In this product, facts come from code and the wording comes from the model. There is no single correct sentence, so a text comparison would be noise. The decisions, by contrast, are exactly determined.
**Rejected:** Writing a gold response per case, the intuitive reading of "gold set". It would have measured phrasing, which the validators already cover, and missed routing, which nothing covers.

### A2. Three outcome classes per model call, not two
**Decided:** pass, rescued, silent-wrong.
**Why:** A validator that passes does not mean the answer was right. `extract_days` returning a legal weekday for the wrong day looks identical to success in the product's own log. That class produces wrong bookings and is invisible without gold, so it is the whole reason the eval exists.
**Rejected:** Pass/fail against the validator. That is just a re-read of the existing JSONL log and would have reported a high pass rate while wrong slots were being booked.
**Result:** 168 of 1051 scored calls were silent-wrong, 16 percent, none of them visible in the product log.

### A3. Session pass/fail is a derived metric, not a workstream
**Decided:** Session verdict falls out of the trajectory gold. Failed sessions drill to turns, turns to calls.
**Why:** Once per-call gold exists, the session verdict is a comparison of the final booking to the card. Building it separately would have duplicated the same facts in two places.

### A4. The heatmap is prompt × outcome class
**Decided:** Rows are model jobs, columns are pass / rescued / silent-wrong, cells are rates over calls made.
**Why:** Code owns every state transition here; the model never chooses one. A from-state × to-state matrix, which suits an agent that picks its own next step, would mostly be structurally impossible cells. Prompt × outcome answers "which job is failing".
**Kept anyway:** Per-turn routing correctness is still recorded, because a mis-route is the visible consequence of a silent-wrong and makes the drill-down concrete.
**Note:** Cells must be rates, not counts. Every session visits ASK_FIRST_CONSULT and few reach PICK_DOCTOR, so raw counts would rank by traffic rather than by failure.

---

## B. Where gold comes from

### B1. Gold is derived from persona cards, not hand-written per case
**Decided:** A card fixes the facts; an independent path table computes the expected trajectory from those facts plus the sidecar.
**Why:** The workflow is fixed and the facts come from code, so the expected path is computable. Hand-writing 81 expectation files would cost days and drift from the cards the moment either changed.
**Human effort instead goes to:** auditing a sample of generated utterances and calibrating the judge, roughly 80 items once, rather than authoring 81 expectations.

### B2. The path table must not import `state_machine.py`
**Decided:** The eval keeps its own ~15-line model of the workflow, deliberately duplicated.
**Why:** Deriving expectations from the product tests the code against itself. Every routing bug would silently become gold and the eval would report perfect routing forever.
**Accepted cost:** The table can drift from the product. There is no automated guard; it is kept small and reviewed when the workflow changes. This is the weakest point in the design and is recorded as such.

### B3. The simulator emits a per-turn sidecar; gold is derived turn by turn from it
**Decided:** Each turn records the act taken (answer, repeat, faq_question, correction, non_answer, wants_other) and the intended values.
**Why:** Two reasons converged. First, a simulator can drift from its card, and the sidecar-versus-card check catches that before the product is blamed. Second, once persona behaviour was left unscripted (C1), no fixed trajectory can be written in advance, so the act sequence becomes the only thing gold can be computed from.

### B4. Facts, not sentences, except where the sentence is the test
**Decided:** Cards carry facts the persona phrases freely, plus a verbatim override for a few turns.
**Why:** If the simulator invents its own wording for D1, "can't sleep since my father died" becomes "I'm grieving", the ambiguity disappears and the scenario tests nothing. Same for the misspelled doctor name and the relative-date phrases. Everywhere else, free phrasing is the point.

### B5. Patients describe symptoms; the category word never appears
**Decided:** No utterance contains its own category label. An automated check flags violations.
**Why:** If "anxiety" appears in the text, `extract_problem` is doing keyword matching and the call is not a test. It also happens to be how real patients talk.
**Exception:** anxiety, depression, stress and sleep are ordinary English, allowed only for personas who are meant to have some idea what is wrong.

---

## C. Who the simulated patients are

### C1. Persona and scenario are separate layers
**Decided:** 12 personas (proficiency × personality × clarity) crossed with 27 scenarios, sampled rather than fully crossed.
**Why:** The three persona dimensions all describe *how* a person talks. None of them decide which branch of the workflow runs. Cross-producting style alone would have produced 12 ways of walking the same happy path. Branch and phenomenon coverage has to be carried by something else, so scenarios carry it.
**Sampling rule:** every scenario under at least 3 personas, every persona in at least 5 scenarios.

### C2. Persona behaviour is unscripted
**Decided:** How often a persona repeats, hedges or ignores a question is left to the simulator in character. Only facts and specific events are scripted.
**Why (the user's call, and correct):** You cannot write a rule for how many times a human repeats themselves without making them stop being human.
**Consequence accepted:** The expected trajectory cannot be fixed up front. Gold became sidecar-driven (B3), and a hand-off counts as a pass only when the sidecar shows the persona caused it.

### C3. Change of mind is a scenario event, never a persona trait
**Decided:** Corrections are scripted at a named state.
**Why:** A persona free to change its mind produces a correction with no gold, because nothing says what it changed to. Scripting the event keeps the correction testable while leaving the wording free.

### C4. When a scripted event is never reached, skip it
**Decided:** If persona behaviour ends the session before the event's state, the event does not fire and the card is discarded as "scenario not exercised".
**Why:** Forcing the event would break character exactly at the moment being tested. Better to lose the card and resample.

---

## D. Keeping the eval honest

### D1. Dev and held-out pools, although nothing is being trained
**Decided:** 20 dev cards readable while writing prompts, 61 held-out cards never opened. Reported numbers come only from held-out.
**Why:** For a 0.8B model, few-shot examples are the entire mechanism, and the model matches surface form. The persona prompt version will be written by reading failures. If those failures come from the same cards that produce the score, the score rises because the model saw near-copies. That is fitting to the test set with a human doing the fitting instead of gradient descent.
**Rejected:** "It's evals, not training, so no split is needed." True of the mechanism, false of the effect.

### D2. One held-out set, frozen, grown upward, never forked
**Decided:** The same held-out set scores every product version. Harder cases are added and `eval_set_version` is bumped; all versions are re-run.
**Why:** Comparison requires the same set. Baseline 71 on set A against persona 84 on set B says nothing. And "a stricter set per version" recurs forever: the moment you read the persona version's failures, set B is contaminated and you need set C.
**Rejected:** A dedicated harder eval set for the few-shot version, which was the initial instinct. It solves contamination once and breaks comparison permanently.

### D3. Isolation is three separate problems
**Decided:** (a) one-way dependency, the eval calls the product over `/message`; (b) independent path table (B2); (c) dev/held-out split (D1).
**Why:** "Keep evals isolated" hides three leaks with different fixes. Only the third one, example contamination, is fatal, and a directory boundary does nothing about it.

### D4. The assistant is a prompt author, so held-out is closed to it too
**Decided:** Dev transcripts were read and hand-reviewed. Held-out transcripts were never read; only gate counts, sidecar metadata and aggregate scores.
**Why:** The same contamination argument applies to whoever writes the few-shots, and in this project that is Claude. Two held-out discards were diagnosed from sidecar fields alone rather than by reading the conversation.

### D5. An automated contamination guard, not discipline
**Decided:** A check fails the run if any few-shot line in `prompts/*/` matches a held-out utterance.
**Why:** The failure mode is a tired human copying a good example into a prompt at midnight. A rule that depends on remembering is not a rule.

---

## E. How runs are produced

### E1. Claude Code generates once; Python replays forever
**Decided:** Sub-agents play each card through the live product one turn at a time and write a transcript. Regression on a new version replays the saved user turns with a small Python harness, no model in the loop.
**Why:** There is no API, so the simulator is a Claude Code sub-agent. A sub-agent cannot be part of a repeatable regression run: no seed, no scripted loop, and a human needed at the keyboard. Separating generation from replay buys determinism, a frozen set, and zero model dependency at run time.
**Crux handled:** Slot choice is the one turn that depends on what the bot offered. The sidecar records the rule so the harness can re-render it.

### E2. One sub-agent per whole conversation, not per turn
**Decided:** The sub-agent plays the entire session.
**Why:** Stateless-call-per-turn is the shape an API harness would use, and with sub-agents it buys nothing while costing character consistency across 6 to 15 turns.

### E3. A CLI owns the transcript format; the sub-agent only chooses words
**Decided:** `send_turn.py` posts the message, assigns the session id, records the reply and state, and detects the end.
**Why:** If sub-agents wrote files, 81 transcripts would have 81 shapes. It also became the place to enforce correctness: the CLI refuses a slot pick whose digit disagrees with its recorded index, which is a mistake the simulator made three times.

### E4. Sonnet simulates, Opus judges
**Decided:** Mid-tier model for the simulator, strongest available for the judge.
**Why:** Asymmetry of safety nets. A simulator error is caught by the fidelity gate and the card is regenerated. A judge error is caught by nothing except the calibration set. Put the strength where the net is missing.
**Evidence it held:** held-out simulator discard rate 3.2 percent, well under the 10 percent ceiling; Sonnet twice flagged its own mistakes unprompted.

### E5. The fidelity gate judges the simulator, never the product
**Decided:** Discard only for simulator drift, unfinished sessions and unexercised scenarios. A hand-off, a wrong booking or a loop is kept and scored.
**Why:** The gate's question is "did the persona stay faithful to its card", not "did the bot do well". Conflating the two would throw away exactly the transcripts worth scoring.

### E6. A looping product is a `gave_up` session, not a discard
**Decided:** After three identical faithful answers get the same re-ask, the simulator closes the transcript as `gave_up`. Those transcripts are kept and score as failures.
**Why:** The original rule discarded anything that did not end, which would have deleted a real defect: an agitated persona saying "the later one please" four times and never being booked. Found on a dev card, confirmed on a held-out card.

### E7. Clean fixtures and a pinned clock per card
**Decided:** A fresh product server per card, with `BOOKING_CLOCK` set to the transcript's local generation time.
**Why:** Bookings persist in the product process, so the second run of a card saw different slots. And replaying on a later date changes what "today" means and which dates are in the 14-day horizon, so a replay mismatch could be a product change or just the calendar. Pinning removes the calendar as a variable.
**Cost accepted:** Four lines of product code, inert unless the variable is set. The only product touch in the whole eval.

---

## F. The judge

### F1. One binary question, one dimension
**Decided:** Does this reply fit the previous user message? Yes or no, with a one-line reason.
**Why:** The calibration set is 40 turns. Agreement on a 1-to-5 scale needs far more labels before it means anything. Binary agreement on 40 is a number that can be defended.
**Rejected:** Tone, helpfulness, grammar. In a template-heavy system where code supplies the facts, those mostly grade the templates. Coherence with the previous turn is the dimension the model actually controls.

### F2. The judge sees the conversation and nothing else
**Decided:** Plain user/bot text, stripped of cards, sidecars, scenarios and internal state, in a fresh context.
**Why:** A judge that knows what the patient was "supposed" to do stops judging coherence and starts judging conformance, which the deterministic scorer already does better.

### F3. A validating writer, not free-form output
**Decided:** The judge calls a CLI that checks one verdict per turn, correct turn numbers, legal labels, and a reason of 1 to 200 characters. Nothing is written on refusal.
**Why:** 61 sub-agents writing JSON by hand will produce malformed files. Refusing at the boundary keeps every verdict file structurally trustworthy. All 61 held-out files aligned with their transcripts on the first pass.

### F4. Human labels before the judge runs
**Decided:** The 40-row sheet goes to the human with no judge output on it.
**Why:** Seeing the judge's answers first pulls your labels toward them and the agreement number stops measuring anything.

### F5. Dev transcripts only for calibration
**Why:** The person labelling is also the person who reviews prompts (D1, D4).

### F6. One judge model, self-reported, for calibration and scoring alike
**Decided:** The judge passes the model id stated in its own system prompt. Every verdict in a run must name the same model, and the E4 check fails otherwise.
**Why:** Calibration measures one specific judge. When held-out was scored on one Opus version and dev calibrated on a newer one, re-judging on the calibrated model changed 33 of 488 held-out verdicts and moved the headline by about 4 points. An agreement number that describes a different judge than the one that produced the scores describes nothing.
**Rejected:** Letting the orchestrator type the model label. It was wrong without anyone noticing, because the sub-agent tool picks "the latest Opus", which changed between runs.

### F7. The brief is frozen once human labels exist
**Decided:** After reading the human labels and notes, the judge brief was not edited before the dev run or after the agreement result.
**Why:** Editing the brief to match the calibration labels tunes the judge to the calibration set, and the agreement number then measures the tuning rather than the judge. If agreement had fallen below the floor, the right move would have been a fresh calibration sample after the edit, not a rerun on the same 40.

---

## G. Scoring judgment calls

### G1. `doctor_pick` is scored against the category the product extracted
**Decided:** Not against the card's category.
**Why:** Otherwise a wrong category is charged twice, once to `extract_problem` and again to `doctor_pick`, and the shortlist prompt looks broken when it faithfully served bad input. Its 7 held-out silent-wrongs are genuine shortlist misses.

### G2. The product's shortlist pick never enters the expected-doctor set
**Decided:** Expected doctors come from the card and the extracted category; the product's choice is used only to know which doctor's slots to expect.
**Why:** A bug found during E3. Letting the pick define the expectation made every pick correct by construction. It flipped several sessions from pass to fail once fixed.

### G3. "One of" for the depression scenario
**Decided:** A3 passes if the booking names either doctor tagged with depression.
**Why:** It is the only scenario with a real shortlist judgment. A single expected id would make half the correct answers fail.

### G4. A non-answer at ASK_PROBLEM scores silent-wrong, though the schema cannot express "not a problem"
**Decided:** Gold is "no category". Every forced pick counts against the model.
**Flagged as arguable:** This charges a schema design choice to the model, and it inflates `extract_problem`'s count. Kept because the alternative, excusing the call, would hide the finding that the state can never re-ask and the hand-off limit there is unreachable.

---

## H. Open

- The calibration set is 40 replies from one labeller. Agreement between two humans on the same 40 would say how much of the judge's 10 percent disagreement is judge error and how much is labeller variance.

- The path table has no automated guard against drifting from the product (B2).
- The E3 check replays dev only; held-out replay is supported but doubles runtime.
- Human traces have no gold, so they will report validator-level statistics only.
- The comparison view exists in the results format but is unbuilt until a second prompt version exists.
