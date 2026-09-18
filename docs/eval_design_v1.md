# Eval Design v1

Companion to `qwen0.8b_booking_assistant_v1_design.md` (design.md). Decisions from the eval brainstorm, 2026-09-17. Open items are listed at the end and get their own design pass before implementation.

## 1. Purpose

Measure whether the booking assistant makes the right decisions, not whether it says specific words. Evals are the showpiece of the project. They appear in the web UI as a viewer over results that the eval runner writes.

## 2. Gold

Gold is derived, not hand-written.

- A persona card fixes the facts: patient type, phone, problem and intended category, doctor preference, days, slot rule, any scripted correction or FAQ interruption.
- An independent path table in the eval package derives the expected trajectory from the card: per-turn NLU fields, next state, tool calls, and the final booking record.
- The simulator emits a per-turn structured sidecar alongside the utterance: the act this turn (answer, repeat, faq_question, correction, non_answer) and the intended field values. Turn gold is the sidecar, checked against the card. This catches simulator infidelity (card says Wednesday, simulator writes Tuesday) before it is blamed on the product model.
- Persona behavior is not scripted. How many times a persona repeats, hedges, or ignores the question is left to the simulator in character. The path table therefore derives the expected next state turn by turn from the sidecar act sequence, not from a pre-fixed trajectory. A hand-off is a pass when the sidecar shows the persona caused it (three non-answers in one state, or three no-slot rounds on Sunday-only days) and a fail otherwise.
- The path table never calls `state_machine.py`. It duplicates roughly 15 lines of routing logic on purpose, so routing bugs cannot become gold.

## 3. Outcome classes per model call

Three, not two.

| Class | Validator | Matches gold | Note |
|---|---|---|---|
| pass | ok | yes | |
| rescued | failed | n/a | code fell back to template or re-ask; session can still succeed |
| silent-wrong | ok | no | invisible in the JSONL log today; produces wrong bookings |

Silent-wrong is the class the eval exists to expose.

## 4. Hierarchy

Session pass/fail is the first metric, derived from the final booking record versus the card. Failed sessions drill to turns, turns to model calls. Session level has no separate workstream.

## 5. Trace sources

Simulated and human, labeled by source in every trace.

- Simulated traces get full gold from the card.
- Human traces have no gold. They report pass, rescued, and hand-off rate only.
- Divergence between sources is a reported signal.

This phase runs the eval on simulated traces only.

## 5a. Cards: persona x scenario

A card is one persona paired with one scenario. Personas are the full cross product of three dimensions (12). Scenarios are designed for branch and phenomenon coverage, not cross-producted. Cards are sampled so that every scenario runs under at least 3 personas and every persona appears in at least 5 scenarios. Coverage is checked with a table.

### Persona dimensions

Each value compiles to observable text behaviors so runs are comparable across simulator models. Draft, to be finalised with the simulator design.

| Dimension | Value | Observable behaviors |
|---|---|---|
| tech proficiency | proficient | terse, picks slots by index, packs several fields into one turn |
| | not proficient | phone with spaces or +91, never picks by number, asks meta questions ("is this a person?"), full sentences |
| personality | patient | baseline, answers what was asked |
| | agitated | short, demands, skips pleasantries, repeats the request when re-asked |
| | inattentive | answers a different question than asked, ignores offered slots and names another time |
| clarity | some idea | uses a lay term a patient would say ("panic attacks", "can't stop drinking") or names a doctor |
| | no idea | describes symptoms and life events only, says you-decide on doctor |

Problem turns are symptom descriptions for every persona. The simulator knows the category so it stays faithful, the sidecar declares it, and the utterance never contains the enum label. Clinical labels (perinatal, geriatric, OCD as self-diagnosis) are out for all personas. An automated check flags a card when the ASK_PROBLEM utterance contains the category label verbatim; anxiety, depression, stress, and sleep are ordinary English and are allowed for "some idea" personas only.

Some scenarios test the phrasing itself (D1 ambiguity, D2b misspelling, B8 relative dates, D3 phone formats). For those, the card holds the exact sentence the persona must use on that turn. Everywhere else the card holds facts and the persona phrases them freely.

Overlaps sharpened on purpose: inattentive is about answering the wrong question, not proficient is about format and meta questions. "No idea" correlates with you-decide, so the you-decide branch must also appear under "some idea" personas.

Change of mind is a scripted scenario event, never a persona trait, because a free-will correction has no gold. Booking for someone else and mixed-language input are parked in the design appendix and excluded.

### Scenarios

Facts and scripted events per scenario. Expected outcomes derive from the path table plus the sidecar. Prompts listed for heatmap coverage.

**A. Branch coverage**

| # | Scenario | Facts | Prompts |
|---|---|---|---|
| A1 | New, named doctor | first consult yes, anxiety, "Dr. Meera Rao", Wed afternoon, first slot | yes_no, extract_problem, doctor_pref (code path), extract_days, slot_choice |
| A2 | New, you-decide, single candidate | sleep -> only Iyer matches, doctor_pick skipped by code | extract_problem, doctor_pref |
| A3 | New, you-decide, real judgment | depression -> shortlist Rao and Khan, doctor_pick chooses, tag overlap checked | doctor_pick |
| A4 | Returning, therapy | first consult no, fixture phone, therapy, days, slot | extract_phone, session_type |
| A5 | Returning, follow-up | as A4 with followup | session_type |
| A6 | Returning, unknown phone | phone not in fixtures, re-ask, hand-off after 3 | extract_phone, hand-off |

**B. One phenomenon on a happy path**

| # | Phenomenon | Scripted event | Expected |
|---|---|---|---|
| B1 | Correction: days | at SHOW_SLOTS, "actually Thursday" | rewind to ASK_DAYS, offered_slots cleared |
| B2 | Correction: doctor | at ASK_DAYS, "I meant Dr. Khan" | rewind to ASK_DOCTOR_PREF, downstream cleared |
| B3 | Correction: phone | at ASK_SESSION_TYPE, different number | rewind to ASK_PHONE, refetch patient |
| B4 | Correction: problem | at ASK_DOCTOR_PREF, different problem | rewind to ASK_PROBLEM, category changes |
| B5 | FAQ detour: fees | at ASK_DAYS, ask about cost | clarify with fee, re-ask days, state unchanged |
| B6 | FAQ detour: hours | at ASK_FIRST_CONSULT, ask about weekend | clarify with hours, re-ask |
| B7 | Second question in same state | two FAQ questions back to back | first gets clarify, second gets plain re-ask |
| B8 | Relative dates | "day after tomorrow", "next week", "this weekend" | extract_days resolves to concrete dates |
| B9 | Multi-field turn | at ASK_DOCTOR_PREF, "Wednesday afternoon with Dr. Khan" | Khan captured by code, days ignored, ASK_DAYS asked next |
| B10 | Slot by description | "the later one", "3pm" | slot_choice maps to index |
| B11 | Wants other slots | at CAPTURE_CHOICE, none work | wants_other, re-ask days, no_slots count increments |

**C. Limits and hand-off**

| # | Scenario | Expected |
|---|---|---|
| C1 | Sunday only, three rounds | no_slots x3, hand-off with clinic phone |
| C2 | Non-answers x3 in one state | 3 re-asks, hand-off; pass because sidecar shows persona caused it |
| C3 | Four corrections | fourth is taken as an answer, classifier not called |
| C4 | Out-of-roster doctor | "Dr. Sharma" -> named removed from enum, treated as other, re-ask |

**D. Ambiguity and surface noise**

| # | Scenario | Expected |
|---|---|---|
| D1 | Ambiguous category | "can't sleep since my father died", card fixes grief; the fidelity-audit case |
| D2a | Ambiguous surname | "Rao" -> code detects tie, re-asks naming both; "Meera" resolves; zero model calls for the name |
| D2b | Misspelled name | "Dr Roa" -> zero roster hits, model sees only you-decide/other, re-ask; known product gap, kept as probe |
| D3 | Phone with noise | "+91 98xxx xxxxx", dashes, spaces -> digits |
| D4 | Problem stated in greeting | "hi I need help with anxiety" -> greet path unchanged, problem not consumed early |
| D5 | Hedged yes/no | "I think so", "not really", "umm no I came last year" |

27 scenarios. Verified against `state_machine.py` on 2026-09-17: doctor resolution at ASK_DOCTOR_PREF is code over the full roster, days given early are ignored, every doctor re-ask counts toward the 3-loop hand-off.

### Card fields

- Identity: `card_id`, `persona_id`, `scenario_id`, `pool` (dev or held-out).
- Persona: the three dimension values plus their behavior lines copied in, so the sub-agent needs no lookup.
- Facts: `patient_type`, `phone` or null, `problem_category`, `symptom_brief` (two or three symptom phrases as raw material, never the label), `doctor_pref` (named with the name, or you_decide), `session_type`, `days` as weekday names or relative terms, `time_pref`, `slot_rule` (first, last, first_afternoon, none_work_once).
- Scripted events: list of `{at_state, act, payload}`, empty for happy paths.
- Verbatim: map of state to exact sentence, phrasing-sensitive scenarios only.
- `stop_after`: booking_confirmed or handoff.

Expected outcome (final booking fields or handoff, prompts exercised) lives in the scenario file, not the card, so the simulator cannot read it.

If persona behavior ends the session before a scripted event's `at_state` is reached (for example, three non-answers at ASK_PROBLEM cause hand-off before a correction at SHOW_SLOTS), the event is skipped. The fidelity gate marks the card "scenario not exercised," it counts as a discard for coverage, and the sampler draws a replacement. Events never override persona behavior.

## 5b. Generation and replay

There is no API access. Claude Code is the generator, never the runtime.

- **Generate once.** A Claude Code session, using sub-agents on a cheaper model as the simulator, walks each persona card through the live product over `/message`, one turn at a time. It writes the transcript and per-turn sidecar to a file. This runs once per card.
- **Freeze into scripted replays.** The saved user turns are the held-out set. Regression on a new product version replays the same user turns from the file with a small Python harness. No Claude in the loop. This gives determinism, the frozen held-out set from section 10, and zero API dependency at run time.
- **Judge in a fresh sub-agent.** A separate sub-agent on the strongest model reads transcript files and writes verdicts to a file. The eval runner reads the verdict file.
- **Slot choice is the one bot-dependent turn.** "I'll take the 3pm" is wrong if a new version offers 2pm and 4pm. The sidecar records the rule (for example, first afternoon slot) and the replay harness renders the utterance from the rule against the slots actually offered. All other turns replay verbatim: facts come from the card, and corrections and FAQ detours are scripted by the card.
- **Messiness is a card dimension.** Terse, verbose, typos, formal are set on the card, not left to the simulator model, so a model swap does not change eval difficulty.

Isolation holds: the eval package is Python that reads transcript, sidecar, and verdict files. Claude Code never appears inside it.

## 5c. Pipeline

Six stages. Each writes a file the next reads.

1. **Author cards.** Persona and scenario files drafted from section 5a, reviewed by the human. A script samples cards under the coverage rule and splits them into dev and held-out pools. Held-out is frozen and stamped `eval_set_version`. Default sizes: about 20 dev, 60 held-out.
2. **Generate transcripts.** One sub-agent per card on a mid-tier model. Input: the card, the persona behavior table, the `/message` URL, and nothing about gold or what is measured. Output: one transcript file, sidecar inline, played to the card's `stop_after` condition (booking confirmed or hand-off received). Runs once per product version that needs fresh generation.
3. **Fidelity gate.** Python. Sidecar values match the card, no enum label in the problem utterance, verbatim phrases present where required, turn count under a cap. Failures go to a discard file with a reason; discard rate is reported. The human reads the ambiguous-category audit sample. Failed cards are regenerated, not edited.
4. **Score.** Python, no Claude. Trajectory scoring derives expected next state and NLU fields from each sidecar act via the path table and compares with the product JSONL, assigning pass, rescued, or silent-wrong per call. Session outcome is the booking record versus the card. Replay re-sends the saved user turns through the harness, slot-choice rendered from the rule; the first replay runs against the generating version and both logs must agree. The held-out guard runs here.
5. **Judge.** Fresh sub-agents on the strongest model read transcripts only and write a verdict file: per bot turn, coherent or not, one-line reason. Reported with judge-versus-human agreement on the calibration set.
6. **Results and UI.** One results file per run keyed by `prompt_version`, `validator_version`, `model_id`, `eval_set_version`. An Evals tab in the web UI reads results files: session pass rate, prompt x outcome heatmap with drill-down, discard rate, judge agreement, source divergence when human traces exist. Comparison view is in the results format now and built later.

Known weak point: the path table duplicates routing on purpose and has no automated guard against drifting from `state_machine.py`. Keep it small and review it when the workflow changes.

### Amendments from the E2 dev run (2026-09-18)

- **Loops are product failures, not discards.** A simulator that gets the same re-ask after three identical faithful answers closes the transcript as `gave_up` via the CLI. `gave_up` and `turn_cap` transcripts are kept and score as session failures. Only simulator drift, unfinished sessions, and unexercised scenarios are discarded.
- **Slot picks carry the index.** The CLI records the slots the product offered; the sidecar carries the 1-based index the persona took; the gate checks the index against the card's rule. The CLI refuses to send a slot turn whose bare digit in the text disagrees with the index.
- **Volunteered details are non-answers.** Only the field the bot's last question asked about is an `answer`.
- **SHOW_SLOTS is never an answering state.** The product presents slots and lands in CAPTURE_CHOICE in one step. Scripted events fire at CAPTURE_CHOICE.
- **Hand-off scenarios carry fallback facts** (days, slot rule) so a lenient product does not strand the persona. Expected outcome is still hand-off.
- **Clean fixtures per card.** Bookings persist in the product process, so a server is restarted before each card. The E3 replay harness needs the same reset.
- **Held-out is closed to the prompt author, including the assistant.** Hand review of transcripts happened on dev only. Held-out transcripts pass through the gate and the scorer, never a reader.
- **Held-out run numbers.** 61 cards on Sonnet, 63 runs, 61 kept, 2 regenerated. Discard causes were persona consistency (reverting to pre-correction facts) and a misread of the empty-days rule; both are now brief rules.
- **Dev run numbers.** 20 cards on Sonnet, 25 runs, 20 kept, 5 reruns. Rerun causes: 3 slot text/value conflicts (now blocked by the CLI), 1 volunteered detail labelled as answer, 1 scenario bug (SHOW_SLOTS). About 51k tokens and 2 to 4 minutes per card.

## 6. Deterministic checks and judge

- All NLU checks are deterministic against gold: field equality, next-state equality, booking record equality.
- LLM-as-judge is used in one place: NLG coherence with the preceding user turn. It ships with a judge-vs-human agreement number from a small calibration set. A judge without that number is decoration.
- Simulator and judge are different models. The judge gets the strongest model available because judge errors have no safety net except the calibration set. The simulator gets a mid-tier model because its errors are caught by the sidecar-versus-card check (section 2). The judge runs in a fresh context that sees only the transcript, never the card or simulator instructions.
- Judge rubric: one binary question per bot turn, does the reply fit the user's last message, with a one-line reason. It catches three failure shapes: the reply ignores what the user just said; the reply acknowledges something the user did not say (validators catch altered facts in slots and bookings, not invented acknowledgements in `ask_question`); the reply asks something the conversation already answered. Not tone, grammar, or helpfulness, because those mostly grade the templates. Binary because the calibration set is 30 to 50 turns and agreement on a scale needs far more labels to be credible.
- Sidecar discard rate is a reported metric. If it climbs past a few percent, the simulator model is too weak.

## 7. Human labeling budget

Roughly 50 to 80 items, once.

- Simulator-fidelity audit: a sample of generated utterances for ambiguous problem descriptions, marked card-faithful or not.
- Judge calibration set for NLG coherence.

## 8. Analysis view

Heatmap. Rows are prompts (model jobs). Columns are outcome classes from section 3. Cells are rates over calls made, with counts on hover. Absolute counts mislead because every session visits ASK_FIRST_CONSULT and few visit PICK_DOCTOR. Clicking a cell filters to the turns in it, then to the JSONL lines. The heatmap answers "where," not "why."

## 9. Comparison

Designed now, built when a second version exists (persona prompts, fine-tuned model).

- Results carry `prompt_version`, `validator_version`, `model_id`, `eval_set_version`.
- The core view is a diff between two runs on the same eval set.

## 10. Isolation

Three leaks, handled separately.

- Code dependency. One-way: the eval calls the product over `/message` and reads its JSONL. The product never imports eval code. The UI reads a results file the runner wrote.
- Fact leakage. Handled by the independent path table in section 2.
- Example contamination. Persona cards split into two pools. A dev pool prompt authors can read and debug against. A held-out pool nobody opens except the eval runner. Reported numbers come only from held-out.

Held-out rules:

1. One held-out set, frozen, scored on every product version. This is what makes comparison meaningful.
2. Grow it, never fork it. Harder cases (paraphrase-heavy, three phrasings of one intent) go into held-out and bump `eval_set_version`. Every product version is re-run on the new set.
3. An automated check fails the eval run if any few-shot example in `prompts/*/` matches an utterance in the held-out pool. Enforced by tooling, not discipline.

## 11. Decoding

`llm_client.complete` uses temperature 0. Replays are greedy and binary pass/fail. Expect rare flakes from Metal float math, not zero.

## 12. Not decided yet

Design is closed. The following are build-phase decisions, not product decisions:

- Card, transcript, sidecar, verdict, and results file formats
- Final wording of persona behavior lines
- Simulator and judge sub-agent model ids
- Slot-choice rule vocabulary for the replay harness
- Build phases and check scripts, to be added to design.md section 11 when the eval phase starts
