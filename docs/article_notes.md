# Article source notes: building on a 0.8B model

Distilled 2026-10-04 from the Claude Code session transcripts (14 Sep to 4 Oct 2026), the design and eval docs, the decision and findings logs, and the scored results file. These are notes for writing, not the article. Every point carries a source so it can be checked.

**How to use these notes**
- Sources in brackets: a date and time is a transcript message (local archive `session_archive/condensed/`, not in git); `decision log X1` is `docs/eval_decision_log.md`; `findings` is `docs/eval_findings_log.md`; `design` is `docs/qwen0.8b_booking_assistant_v1_design.md`; a 7-character hash is a git commit.
- "Probe" numbers come from tiny test sets the assistant wrote itself while tuning (8 to 11 inputs). They show direction, not accuracy. "Eval" numbers come from the scored run of 81 simulated conversations.
- All quoted patient messages are from the dev pool. Held-out conversations are never quoted; only their counts appear.

---

## 1. The project in one paragraph

An appointment-booking assistant for a fictional mental-health clinic, run on Qwen3.5 0.8B (Q8 GGUF, about 834 MB, the llama.cpp maintainers' own conversion) through llama-cpp-python on a Mac with Metal, prompting only, no fine-tuning. A state machine in code owns the whole workflow and every tool call. The model does one narrow job per call: ten NLU prompts that classify or extract into a JSON schema with constrained decoding, and five NLG prompts that phrase a reply from facts the code passes in. Every model output passes a deterministic validator; on failure the code uses a fixed template or re-asks. An eval harness then measured it: 12 personas × 27 scenarios, 81 simulated patients (Claude Sonnet sub-agents) split 20 dev / 61 held-out, gold derived from the cards, three outcome classes per model call, and an Opus judge calibrated against human labels. [design §1, §4; 14 Sep 04:24; findings]

## 2. Candidate takeaways (ranked by evidence)

1. **A 0.8B model cannot run a workflow, but it can fill narrow slots if code shrinks every choice first.** The design premise: one prompt doing workflow, tools and replies "skips steps and invents slots". Code owns the flow; the model classifies, extracts and phrases. [design §1]
2. **Constrained decoding guarantees the format, not the answer, and creates a new failure class: wrong but legal.** With no "none of these" option, a fee question at "what would you like help with?" became the category *stress* on every card, and the validator could not object because the answer was in the enum. 168 of 1,051 scored calls (16%) were silently wrong, invisible in the product's own logs. [20 Sep 05:52; decision log A2, G4; findings 21 Sep]
3. **"Narrow before you ask" beat prompt work.** Code removes impossible options from each call's schema and skips the call when it already knows the answer. Dropping `named` from the doctor-preference enum when no doctor name is in the text made one error impossible without a single new example. [16 Sep 11:13, 11:31; design §7]
4. **Small details of how the model writes JSON matter more than instructions.** Field order changed results sharply (probe: 3/8 → 8/8), a too-wide `other` label pulled answers toward it (probe: 5/10 → 10/10 once narrowed), and example JSON had to use the grammar's key order. [14 Sep 06:34; 16 Sep 11:31]
5. **The model is weakest where meaning is fuzzy or relational:** anxiety vs stress, off-topic remarks vs corrections, "the later one", "day after tomorrow 10am", and keeping every fact when writing a slot list (fails its own fact check 56% of the time on held-out). [findings; heatmap]
6. **Templates carry the product where the model is weak.** The slot-list prompt failed validation on 50 of 89 held-out calls; the template replaced it and the user still saw correct slots. [findings 21 Sep]
7. **Measuring a small model needs more care than building it.** The hardest bugs were in the eval harness, not the product: a scorer that made every doctor pick correct by construction, replay mismatches that were all harness bugs, a judge labelled with the wrong model id, a simulated patient whose wording did not match its card. [decision log G2, F6; 20 to 23 Sep; audit 3 Oct]

---

## 3. Architecture: putting a small model in a box

- **Workflow in code, one job per call.** user text → turn classifier (correction?) → NLU prompt for the current state → validator → state update and tool calls (code) → NLG prompt → validator → reply or template. The model never sees tool schemas and never decides transitions. [design §1]
- **Facts never come from the model.** Doctors, slots, dates and the clinic phone come from fixtures; one code function formats a slot ("Wednesday 16 September, 14:00") and feeds the prompt, the template and the validator. [design §1; 14 Sep 06:49]
- **The state machine returns reply facts, not text** (`{"kind": "present_slots", ...}`); NLG wraps them and validators check against the same facts. [14 Sep 05:26]
- **Built and tested with stubbed NLU first.** Phase 1 proved the workflow with hard-coded answers and no model. The assistant noted this proves nothing about whether the model can give those answers. [14 Sep 05:34]
- **Code does the fuzzy lookups, not the model:** doctor-name matching on any name token (a surname tie re-asks naming both, zero model calls), time-of-day slot filtering, rolling 14-day dates, hiding slots that already started. [14 Sep 05:33, 06:35; 16 Sep 11:31]
- **Hand-off is a template.** After 3 failed re-asks in a state or 3 rounds with no slots, the session ends with a fixed message and the clinic number. [design §2]
- **Corrections:** a turn classifier runs before state NLU; a map from field to owning state rewinds and clears downstream fields; capped at 3 per session. After a rewind, the owning state's NLU re-reads the full user text, not the classifier's `new_value`, so checks against the user's own words still work. [design §3; 15 Sep 15:38]
- **FAQ detour without model-written facts:** `off_script` only classifies "is this a question, about what"; code matches the topic to a fixture and the reply quotes the answer verbatim. One detour per state. [15 Sep 16:31]
- **Gate model calls with cheap code checks.** The FAQ detour runs only if the text is shaped like a question (a "?" or what/how/do/are/can), the state's own NLU passed, and the detour is unused. Reason: a validator fallback means the model failed, not that the user went off script. [16 Sep 11:13, 11:31]
- **"Wrong slot" was not hallucination.** A screenshot looked like an invented slot; the backend was right, the model had mis-extracted "day after tomorrow 10am" and the no-slots reply hid the time window. "More data does not fix extraction." [15 Sep 17:55]
- **Harness fix over prompt fix where the problem is structural:** when the preferred time window is empty, code re-fetches the whole day and offers it with a "no morning slots, but…" lead. [15 Sep 18:13; 3f5d8b1]
- **Thinking mode off, explicitly.** Qwen3.5's template defaults to thinking on. At first the JSON grammar's forced `{` blocked the thinking block "only by accident"; the fix renders the chat template with `enable_thinking=False`. [14 Sep 04:39, 04:48]
- **Every call logs one JSONL line** (session, turn, state, model, prompt, prompt version, validator version, ok, reason, raw output, latency). That log became the eval's data. [design §7]

## 4. What the 0.8B model did

### Where it held up (held-out eval, share of calls that passed)
yes/no 94% · doctor preference 96% · turn classifier 86% · extract_days 78% · doctor pick 74% · extract_phone 71% (+25% rescued by the validator) · session type 71% · slot choice 65% · extract_problem 59%. [results file, heldout by_prompt]
- Picking between two depression doctors, it gave a sensible reason: "Dr. Khan specializes in persistent or recurrent depression and grief…". [phase 5 check output]
- 5 of 5 turn-classifier calls right in the phase 4 check conversation. [15 Sep 16:03]

### Failure modes, with dev examples
- **Zero-shot, it said "yes" to everything,** including "no, I have been here before" and "what are your fees?". Few-shot examples carried the judgment. [14 Sep 04:39]
- **A broad catch-all label attracts answers.** Defining `other` as "anything else" pulled even "follow up" into `other`; narrowing it fixed the probe. [14 Sep 06:34]
- **Invented a time preference** for a bare weekday: "thursday" became `time_pref: "evening"`, which filtered out a real 14:00 slot. [15 Sep 16:03, 16:25]
- **Relative and clock times:** "day after tomorrow 10am" became tomorrow + afternoon, both wrong; two few-shots fixed it. [15 Sep 17:55, 18:13]
- **Wording outside its examples:** "please suggest one" became `mode: named` with no name, because no example used "suggest", though the bot's own question does. [16 Sep 11:10]
- **Chained errors:** the same message was then read by `off_script` as a question about first visits. A validator fallback in one step fed a wrong input to the next. [16 Sep 11:10]
- **Descriptive picks:** "the later one" was read as "show me other slots" every time; one agitated persona looped four times and gave up. A bare "3" worked. [findings 18 Sep; 20 Sep 18:13]
- **Booked the wrong slot without anyone noticing:** "the earliest one in the afternoon, the 2 o'clock" was confirmed at 15:00; the validator passed because 15:00 was an offered slot. [18 Sep 04:52]
- **Questions became dates:** questions asked at "which days?" were extracted as "today", so the FAQ detour never fired there. [findings 18 Sep]
- **Off-topic remarks read as corrections:** "is this a real person" rewound the conversation as a problem correction. 40 of 288 held-out turn-classifier calls were silently wrong. [findings; 3 Oct audit]
- **Anxiety vs stress:** anxiety descriptions landed on stress on four dev cards. Part of this is the simulated patient's wording (see §6). [findings 18 Sep; audit 3 Oct]
- **Grief read as trauma, with an invented symptom.** For the card sentence "I can't sleep since my father died" (gold: grief), the model chose trauma in every dev call, and its summary added a symptom the patient never mentioned: "persistent insomnia and intrusive flashbacks following…". The summary is the input to the doctor-pick step, so an invented detail can steer the pick. [findings 3 Oct]
  - Superseded reading: the 18 Sep notes said this sentence "went to grief once and to sleep once". That was read off which doctor was offered, not the logged category; corrected 3 Oct. [findings 3 Oct]
- **NLG: copied the wrong question.** It answered three turns with the greeting question instead of the one asked, and the first validator (length + "has a question") passed it. [14 Sep 07:39]
- **NLG: a false apology** ("I'm sorry, I didn't catch that") after a correct answer. [14 Sep 07:39]
- **NLG: a long note crowds out the question.** Given an unseen long note, it wrote only the note: `{"reply": "We suggest Dr. Sana Khan."}`, no question. [17 Sep 03:43]
- **NLG: dropping facts from a list.** With three Saturday slots it dropped one; on held-out the slot-list prompt failed its fact check on 50 of 89 calls. [16 Sep 04:51; findings]
- **Replies are terse and template-like** ("Great." plus the question). Judged by Opus on held-out: 101 of 324 re-asks, 40 of 89 slot lists, 6 of 54 confirmations, 3 of 11 no-slots replies and 0 of 4 FAQ answers did not fit the patient's last message. [results file, judge coherence]

## 5. Prompting a 0.8B model

- **Few-shots do the work; instructions do little.** Baseline prompt shape: role line, the bot's question, 5 or 6 examples, the user turn. [design §4.1; 14 Sep 06:19]
- **Field order is a lever, and the right order depends on the task.** The model writes JSON left to right and cannot revise.
  - extract_problem: with the summary first it labelled almost everything *stress*; category first went 3/8 → 8/8 (probe). [14 Sep 06:34]
  - extract_days: time preference before days, 6/10 → 10/10 (probe). [14 Sep 06:19]
  - doctor_pref: doctor name before mode ("evidence before label"); reasoning stated, not separately measured. [16 Sep 11:13; design §7]
- **Example JSON must match the grammar's key order.** After harness fixes the model still said `other` for "please suggest one" until the examples used the schema's key order. [16 Sep 11:31]
- **Narrow catch-all labels.** `other` limited to "a question or unrelated reply": session_type 5/10 → 10/10 (probe). [14 Sep 06:34]
- **Few-shots for the exact failing shape** fixed extraction ("day after tomorrow, around 10am"; bare weekday with null time). [15 Sep 18:13]
- **Wording can beat examples for NLG.** "It must begin with X. It must end with Y." failed on unseen notes; "the message has two parts in this order… not complete until the question has been asked" fixed all six note types with no new examples. [17 Sep 03:58; 274634a]
- **Give each NLU prompt the bot's question.** `off_script` lacked it and could not tell "answer to this question" from "something else". [16 Sep 11:13]
- **Put the target after the examples** for NLG: the copied-greeting failure went 6/11 → 10/11 (probe) when the question to ask was stated explicitly after the examples. [14 Sep 07:39]
- **A grammar backstop was deliberately not used.** A `minLength` on the reply alone fixed the note-crowding cases, but was left out so the eval measures the prompt, not the grammar. [17 Sep 03:58]
- **Thinking off** was a deliberate choice; a 3-input probe (1/3 off vs 2/3 on) was "far too small to conclude anything". [14 Sep 04:48]
- **Where prompting stops helping.** Most top eval failures are schema or code problems: no "not a problem" option, a days step that never re-asks, a classifier with no off-topic escape, a slot list that loses facts. A "persona-voice examples" v2 alone may not fix them. [2 Oct 18:28]

## 6. Validators, fallbacks and the wrong-but-legal problem

- **Validators are deterministic:** enum membership, regex (phone), set containment (slots in reply), length caps, tag overlap (doctor vs category). [design §7]
- **NLU guards against invented facts:** the extracted phone digits must appear in the user's own text. [14 Sep 05:49]
- **Thin NLG validators let wrong replies through.** "Length cap + contains a question" passed the wrong question; validators now require the facts verbatim, and for slots and confirmations, exact containment plus a sweep for any extra time or digit run. [14 Sep 07:39]
- **A template was the safe answer but not the accepted one.** The template for "suggest a doctor" was correct; the user rejected leaving it to the template and had the prompt fixed instead. [17 Sep 03:43, 03:46]
- **Membership checks cannot see wrong-but-legal answers.** At "what would you like help with?" the validator only checks the category is in the enum, which constrained decoding already guarantees, so it can never fail. The state can never re-ask and its hand-off rule is unreachable. "Wherever the schema has no 'none of these' option and the handler has no rejection path, a wrong answer is indistinguishable from a right one." [20 Sep 05:52]
- **The fallback chain can hide failures:** the FAQ detour only runs on the re-ask path after the state's own NLU passed; where NLU always passes, the detour is unreachable. [20 Sep 05:52]
- **Model text that feeds another model is a fact-leak path** (the invented "flashbacks" summary into doctor pick). Not traced to a user-visible reply. [3 Oct]

## 7. Measuring it: eval methodology

- **Gold is decisions, not replies.** Expected NLU fields, next state and final booking; never expected reply text, because wording is the model's and facts are code's. Rejected: a gold reply per case, which measures phrasing (validators already cover it) and misses routing. [decision log A1]
- **Three outcome classes per call:** pass, rescued (validator caught it, template used), silent-wrong (validator passed, answer wrong). Silent-wrong is the reason the eval exists: it produces wrong bookings and is invisible in the product's own log. [decision log A2]
- **Gold is derived from persona cards, not hand-written.** A small path table, written separately from `state_machine.py` on purpose so routing bugs cannot become gold. [decision log B1, B2]
- **Persona × scenario.** Persona = how the patient talks (tech proficiency, temperament, how clearly they know their problem); scenario = which branch is tested. Rejected: crossing only persona traits, which gives 12 speaking styles on one default path. [decision log C1; 17 Sep 11:55]
- **Patients describe symptoms, never the label.** A check flags a problem message containing the category word. [decision log B5]
- **Generate once, replay forever.** Sonnet sub-agents played each card once; Python replays the saved patient turns against any product version, with no Claude at run time. Only slot picks are re-rendered from a rule. [decision log E1]
- **Greedy decoding made replay a real regression test:** 177 of 177 turns and 20 of 20 endings matched, and model outputs were byte-identical at divergent turns once the harness was fixed. [21 Sep 04:52; checks 3 to 4 Oct]
- **Replay needed a pinned clock.** Replaying on a later day changes "today" and the 14-day window; one product touch, a `BOOKING_CLOCK` variable, off by default. [decision log E7]
- **A fidelity gate checks the simulator, never the product.** Sidecar matches the card, no label word, verbatim phrases present, turn cap. Loops are kept and scored as failures, not discarded; otherwise the looping "later one" transcript would have been thrown away. Held-out discard: 2 of 63 runs. [decision log E5, E6; findings]
- **A blind human audit of the simulated patients.** The labeller saw only the patient's problem description, shuffled, and picked a category without seeing the card's. 15 of 17 simulator descriptions matched the card (88%); both misses were on the anxiety/stress line, one each way. On D4 ("I feel keyed up before work and I just cannot relax at home", card: anxiety) the human and the model both said stress, so the scorer's "error" was the simulator's wording. Some of the 13 held-out extract_problem errors are likely simulator noise; the share cannot be scaled from 17 dev rows. Rejected: showing the card's category and asking yes/no, which anchors the labeller. [decision log E8, E9; findings 3 Oct]
- **Eval coverage gap.** The 27 scenarios test 8 of 12 categories, anxiety in 10 of them; ocd, perinatal, geriatric and child_adolescent never appear. extract_problem numbers say nothing about those four. [findings 3 Oct]
- **LLM judge for reply fit.** One binary question per bot reply: does it fit the patient's last message? Three failure shapes: ignores the user, acknowledges something unsaid, asks what was already answered. Rejected: tone, helpfulness, a 1–5 scale (helpfulness would grade the templates; a scale needs far more labels). [17 Sep 16:48; decision log F1]
- **Calibrate the judge before trusting it.** 40 dev replies labelled by the human before any judge output existed; agreement 36 of 40 (0.9) against a 75% floor; all four disagreements were human yes, judge no. The brief was frozen after reading the labels so the number is not tuned to them. [decision log F4, F7]
- **Dev vs held-out is about the prompt author, not training.** Held-out is closed to whoever writes prompts, including the assistant, because a human fitting few-shots to failures they have read is fitting to the test set. A guard checks every few-shot line against held-out messages: 400 messages, 222 prompt lines, 0 hits. [decision log D1, D4, D5]
- **Heatmap: rates over calls made.** Rows are prompts, columns are outcome classes. Absolute counts mislead because every session visits the first question and few visit doctor pick. A state-transition matrix was dropped because code owns every transition. [eval design §8; 17 Sep 05:00]

## 8. Results (baseline prompts, eval set 1)

| What | Value | Note |
|---|---|---|
| Held-out sessions passed | 42 of 61 (69%) | Dev: 12 of 20 |
| Held-out failure reasons | wrong doctor 8, wrong slot 6, wrong day 5, product-caused hand-off 3, gave up 1 | Some sessions carry two reasons |
| Scored model calls, both pools | 805 pass, 78 rescued, 168 silent-wrong (16%) | 629 more calls unscored (NLG phrasing has no gold) |
| Held-out silent-wrong by prompt | turn_classifier 40/288, slot_choice 26/79, extract_days 23/104, extract_problem 13/64, doctor_pick 7/42 | Rates over calls made |
| Held-out rescued | present_slots 50/89 (56%), extract_phone 6/24 | Template carried the reply |
| Misrouted turns, held-out | 60 of 488 | Each traces to a silent-wrong |
| Judge: replies not fitting, held-out | 152 of 488 (31%) | Dev: 75 of 177 |
| Judge vs human agreement | 36 of 40 (0.9) | Floor 0.75 |
| Simulator fidelity (blind audit, dev) | 15 of 17 (88%) | Plus 2 of 2 card-fixed sentences |
| Replay agreement | 177 of 177 turns, 20 of 20 endings | Greedy decoding, pinned clock |
| Latency, local Mac (Metal) | about 1.4 to 1.5 s per constrained yes/no; about 4 s per NLG reply; about 5.7 s for a two-call turn | Single runs; first figure may include warm-up (unclear) |
| Simulator cost | about 50k tokens and 2 to 4 minutes per card (Sonnet) | 81 cards |

[findings 21 to 23 Sep, 3 Oct; results file; 14 Sep 04:39; 15 Sep 17:13]

## 9. Surprises, mistakes and corrections

- **The scorer made every doctor pick correct by construction:** the product's own pick leaked into the expected-doctor set. Fixing it flipped several sessions from pass to fail. [decision log G2]
- **Replay mismatches looked like product drift and were all harness bugs:** UTC vs local clock, re-rendering descriptive slot picks as bare numbers, a stale server on a fixed port answering as "fresh", and a teardown that left the model server running. [20 to 21 Sep]
- **The judge's model id was a label the orchestrator typed,** not one the judge reported. Re-judging held-out on the calibrated model changed 33 of 488 verdicts and moved "not fitting" from 133 to 152. A check now requires one self-reported judge model across all verdicts. [decision log F6]
- **The simulated patient made the same mistake three times** (typed "2", recorded slot 1) and reported it unprompted; the fix moved from the brief into the CLI, which now refuses a mismatched pick. [18 Sep 04:58, 05:23]
- **A schema choice was charged to the model.** A non-answer at the problem question scores silent-wrong because the schema cannot say "not a problem"; kept, and flagged as inflating extract_problem's count. [decision log G4]
- **A design default slipped through on a bare "go":** new patients were silently given session type "therapy"; caught in review and changed. [14 Sep 05:26, 05:31]
- **A known prompt weakness was worked around in the check scripts** (writing "afternoon" after a weekday) instead of fixed, and later surfaced as a user-visible bug. [15 Sep 16:25, 17:48]
- **Blind-labelling discipline is easy to break:** a test run of the audit merge printed the answer key; the sheet was reshuffled before labelling. The merge also ignored second choices until the labeller pointed out three. [2 to 3 Oct]

## 10. Open questions and what is next

- What v2 should change. The evals point at slot_choice, extract_days, extract_problem and turn_classifier, plus the fuzzy anxiety/stress line; several fixes are schema or code, not prompt wording. [2 Oct 18:28]
- Whether to separate anxiety and stress in the simulator brief, or score either answer as correct. [decision log H]
- Closing the coverage gap for ocd, perinatal, geriatric, child_adolescent. [decision log H]
- A second human labeller for the judge calibration, to separate judge error from labeller variance. [decision log H]
- Logprob-based confidence (returned by the client, unused in v1) and fine-tuning are parked for later. [design appendix]

## 11. Working with Claude Code (separate topic; drop if out of scope)

- **Phase gates as executable checks.** Each phase begins by writing `checks/phase_N.sh`; it is done only when that and `checks/all.sh` exit 0 with output pasted. [CLAUDE.md]
- **"List files and wait" surfaced design questions before code,** but a bare "go" once approved defaults the user had not read. [14 Sep 05:26]
- **Asking "did you verify?" separated confirmed from assumed** and exposed what stubs could not test. [14 Sep 05:34]
- **Sub-agents as simulators and judges:** one sub-agent per whole conversation (rejected: one per turn, which loses character consistency); Sonnet simulates, Opus judges, because a simulator error is caught by the fidelity gate and a judge error only by calibration. [decision log E2, E4]
- **The assistant is a prompt author too,** so it read only counts and sidecar metadata for held-out. [decision log D4]
- **Pin and self-report the model** for any sub-agent whose output you calibrate. [decision log F6]
- **Write the "why" down while it is recoverable.** The decision log was written mid-project because the reasoning lived only in the chat; the session transcripts were later archived before automatic cleanup. [22 Sep 04:24]
- **Screenshots catch what tests miss:** two heatmap display bugs (zero cells looking like small rates, 3.2% shown as 3%) were found only by looking. [3 Oct]

## 12. Source map

- Design and rules: `docs/qwen0.8b_booking_assistant_v1_design.md`, `CLAUDE.md`
- Eval design and phases: `docs/eval_design_v1.md`, `docs/eval_phases_v1.md`
- Decisions with rejected alternatives: `docs/eval_decision_log.md` (A to I)
- Dated run findings: `docs/eval_findings_log.md`
- Scored results: `evals/results/generation_baseline_qwen3.5-0.8b-q8_set1_20260923T230445.json`
- Human labels: `evals/calibration/labels.xlsx` (judge), `evals/calibration/audit.xlsx` (simulator audit)
- Prompts: `prompts/baseline/nlu/`, `prompts/baseline/nlg/`
- Session extracts with full detail and timestamps (local only): `session_archive/extracts/A_phases_0-3.md`, `B_phases_4-6_tuning_eval_design.md`, `C_eval_build_E1-E4.md`, `D_audit_E5.md`
- Not covered by any transcript: how the design doc itself was drafted before 14 Sep.
