# Eval findings log

Running notes for the write-up. One entry per generation or scoring run. Product findings here are observations from reading dev transcripts; the E3 scorer confirms or refutes them with counts. Held-out transcripts are never read, so nothing here comes from held-out.

Where things live:

- Methodology: `eval_design_v1.md` (design and amendments), `eval_phases_v1.md` (phases and checks)
- Personas and scenarios: `evals/personas/`, `evals/scenarios/`; sampled cards in `evals/cards/{dev,heldout}/`
- Simulator brief: `evals/briefs/simulator.md`; CLI `evals/send_turn.py`; gate `evals/fidelity.py`
- Transcripts: `evals/transcripts/{dev,heldout,discarded}/`; rejected dev runs kept in `evals/transcripts/rejected_dev/` for the article
- Product JSONL logs from generation: `logs/eval_gen_*.jsonl`

## 2026-09-18, E2 dev generation, baseline prompts, qwen3.5-0.8b-q8, simulator claude-sonnet-5

Numbers: 20 cards, 25 runs, 20 kept, 0 discarded after reruns. 16 booked, 3 hand-off, 1 gave up. About 51k tokens and 2 to 4 minutes per card, three product servers in parallel.

Simulator lessons (each became a rule or a check):
- Proficient personas typed one slot number and recorded another three times. Now refused by the CLI before sending.
- Volunteered details were labelled as answers once. Brief: only the asked field is an answer.
- Bookings persist in the product process; servers restart before each card.
- Scripted events at SHOW_SLOTS never fire; moved to CAPTURE_CHOICE.
- Hand-off scenarios needed fallback facts because the product proceeded where it should have re-asked.
- A looping product left one transcript unfinished; loops are now `gave_up`, kept and scored as failures.

Product observations (dev only, unconfirmed until E3 scores them):
- Anxiety symptom descriptions routed to the stress/sleep doctor on 4 cards (B5 x2, D4, one more). Consistent, not noise.
- Questions asked at ASK_DAYS were read as a day ("today") or produced a slot list on 5 cards. The FAQ detour never fired once.
- The correction classifier fired on off-topic remarks ("is this a real person", "my sleep has been bad") and rewound state on 3 cards.
- "The later one" was read as wants-other every time; one agitated persona looped four times and gave up.
- Two bookings landed on a slot the persona did not pick (B4 "2 in the afternoon" booked 15:00; D3 booked from a non-answer).
- The same D1 sentence, "I can't sleep since my father died", went to grief once and to sleep once, depending on the words around it.
- Phone, problem, and doctor corrections worked end to end when the classifier fired on a real correction (B3, B4, C3).
- Depression shortlist pick chose Khan both times (A3).

## 2026-09-18, E2 held-out generation, baseline prompts, qwen3.5-0.8b-q8, simulator claude-sonnet-5

Numbers: 61 cards, 63 runs, 61 kept, 2 discarded and regenerated (3.2 percent first-run discard). 54 booked, 6 hand-off, 1 gave up. Under the 10 percent ceiling.

Discard causes, from sidecar metadata only, no transcript text read:
- One persona recorded "any" for days on a card that had a day. Brief now says "any" is only for an empty days list.
- One persona reverted to the original card values after a scripted correction, when the product rewound to an earlier question. Brief now says the corrected value is the fact for the rest of the conversation.

Held-out is closed to readers. The observations above come from the ended kind and sidecar fields, which are metadata the gate already prints. Product findings on held-out come only from the E3 scorer.

Outcome kinds visible from metadata: all three Sunday-only cards (C1) ended in hand-off as designed; all three C2 cards booked instead of handing off, matching the dev finding that a non-answer at ASK_PROBLEM is accepted; one held-out B10 card gave up in a slot-description loop, matching dev.

## 2026-09-21, E3 scoring of the E2 generation run, baseline prompts, qwen3.5-0.8b-q8

Results file: `evals/results/generation_baseline_qwen3.5-0.8b-q8_set1_*.json`. Replay of the 20 dev transcripts against the same product version agreed on 177 of 177 turns and 20 of 20 endings, so the harness is a faithful regression instrument.

Session pass rate: dev 12/20, held-out 42/61. Held-out failure reasons: wrong doctor 8, wrong slot 6, wrong day 5, product-caused hand-off 3, gave up 1 (some sessions carry two reasons).

Per model call, both pools (1051 scored calls): pass 805, rescued 78, silent-wrong 168. Silent-wrong by prompt on held-out:
- slot_choice 26 of 79 scored: described-time picks ("the later one", "2 in the afternoon") map to the wrong index or to wants-other.
- extract_days 23 of 104: questions and remarks at ASK_DAYS become "today" or a weekday; no re-ask ever happens at that state.
- turn_classifier 40 of 288: off-topic remarks read as corrections and rewind state.
- extract_problem 13 of 51: anxiety symptom descriptions land on stress; fee questions become a category because the schema has no "not a problem" option.
- doctor_pick 7 of 38: judged against the extracted category, so these are genuine shortlist misses.

Rescued (validator caught it, template used): present_slots 50 of 89 on held-out. The NLG slot list fails its own fact check more than half the time and the template carries the product.

Routing: 60 of 488 held-out turns went to a state the path table did not expect. Every one traces to a silent-wrong above.

Harness lessons this phase (each now a rule or code):
- Replay must pin local wall-clock time, not just the date: the product drops past slots on "today".
- Re-render a slot pick only when the persona typed a bare number; descriptive picks keep their words or the phenomenon disappears.
- Never replay against a fixed port: a stale server answers /health with old bookings and the wrong clock. Fresh port per card, and refuse a port with a listener.
- Killing a `uv run` wrapper leaves uvicorn alive with the model loaded. Kill the process group.
- The product's shortlist pick is used for slot routing only; expected doctors come from the card.

## 2026-09-23, E4 judge: reply coherence, calibrated on 40 human labels

Judge: `claude-opus-5-5`, one sub-agent per conversation, reading the stripped conversation only. 81 conversations, 665 bot replies.

Calibration on 40 dev replies labelled by the human before any dev verdict existed: agreement 36 of 40, 90 percent, floor 75 percent. All four disagreements were human yes, judge no. The judge caught every one of the 16 human no's. Of the four, one matched a pattern the human had marked no elsewhere (a time of day the patient never asked for), one was a question the patient had already answered, and two were hand-offs, where the judge applies the brief's "hand-off after a clear answer is a no" rule more strictly than the human did. The brief and labels were not edited after the comparison.

Held-out coherence: 152 of 488 replies judged as not fitting the previous patient message, 31 percent.

Model pinning finding: the first held-out judging ran on the Opus model current at the time and was labelled `claude-opus-5` by the orchestrator, not by the judge. The dev calibration ran on `claude-opus-5-5`. Re-judging held-out on the calibrated model changed 33 of 488 verdicts (26 yes to no, 7 no to yes) and moved the not-fitting count from 133 to 152. Agreement between the two judge versions was 93 percent. Old verdicts remain in git at 7c42fa1.

Harness lessons:
- The judge must report its own model id from its system prompt; an orchestrator-typed label is not evidence.
- The E4 check now fails if verdict files name more than one judge model.
- Excel re-saves integer columns as decimals; the merge reads turn numbers through float first.

## 2026-10-03, E2 follow-up: simulator-fidelity audit, 19 dev problem descriptions, one human labeller

The audit owed since E2 (eval design section 7). Every dev patient message that describes the problem: 17 first answers at ASK_PROBLEM and 2 later problem corrections. One non-answer at ASK_PROBLEM was left out. Blind: the human saw shuffled messages with no card id and picked the category they would file each under, with an optional second choice. Sheet `evals/calibration/audit.xlsx`, key `audit_key.json`, scored by `evals/audit_merge.py`.

Numbers:
- Simulator wording: 15 of 17 faithful (88 percent). 14 plain matches, 1 match where the human also named a second choice. 2 unfaithful, 0 can't tell.
- Card-verbatim wording (the D1 sentence written into the card): 2 of 2 faithful, both with a second choice.
- Counting hesitations, 5 of 19 rows show real category overlap.

Where the human and the card disagreed:
- D4, card anxiety: "I feel keyed up before work and I just cannot relax at home". Human: stress. The product also said stress. The scorer counts this as an `extract_problem` silent-wrong, but it is simulator wording, not a model error. It is the same anxiety-to-stress pattern behind most of the 13 held-out `extract_problem` silent-wrongs, so part of that count is likely simulator noise. How much cannot be read off 17 dev rows.
- C3, card stress: "Deadlines keep me all wound up lately and I grind my teeth at night". Human: anxiety. The product said stress, so it scores as a pass. The line is fuzzy in both directions: the simulator anchors both categories in work and tension.
- Second choices on matching rows: B4's changed description, addiction then stress (the persona switches from a stress problem); both D1 rows, grief then sleep (the sentence is ambiguous by design).

Product observations (dev only):
- The D1 sentence "I can't sleep since my father died" was categorised as trauma in every dev generation call: both kept transcripts plus two earlier D1 prof sessions that were not kept. That is neither the card's category nor either of the human's picks. The summary invented a symptom: "persistent insomnia and intrusive flashbacks following...". The summary is the input text to `doctor_pick`, so an invented detail can steer the shortlist pick.
- Correction to the 2026-09-18 dev entry, which said this sentence "went to grief once and to sleep once". That reading came from the doctor offered, not the logged category. In D1 prof, trauma led to Dr. Sana Khan, who also covers grief. In D1 noprof, the next message, a non-answer at ASK_DOCTOR_PREF, was classified by `turn_classifier` as a problem correction (its new value began "real person") and re-extracted as stress, which led to Dr. Arjun Iyer (stress and sleep). That is the known `turn_classifier` rewind on off-topic remarks, not two readings of the sentence.

Coverage observation: the 27 scenarios fix 8 of the 12 categories, anxiety in 10 of them. child_adolescent is out by design (booking for someone else is parked). ocd, perinatal and geriatric are never tested, and no decision records why. The rule in eval design 5a bans those words as self-diagnosis, not the categories. The `extract_problem` numbers say nothing about these four, and this audit covers the 7 categories present in dev.

Harness lessons:
- A dry run of the merge on the unlabelled sheet printed the key, row by row. The merge now prints the row list only once every row has a pick. The sheet was reshuffled with a new seed before labelling, and no row kept its position. The leaked output also showed the per-category counts, so a mild anchoring effect cannot be ruled out.
- The first merge ignored a second choice whenever the first pick matched the card, so three second choices went unreported until the labeller noticed. It now counts `faithful_second` separately.
- Rows whose wording comes from the card's verbatim sentence are reported apart from simulator rows: they audit the card author, not the simulator.

## 2026-10-03, E5 Evals tab, baseline prompts, qwen3.5-0.8b-q8

Built: an eval server (`evals/server.py`, its own port) and an Evals tab in the product UI that reads from it. The tab shows four headline tiles, a prompt × outcome heatmap with rates over calls made and counts on hover, a held-out / dev toggle, and a drill-down from cell to calls. On dev, a call expands to the patient message, the bot reply and the product's log lines. On held-out it stays structured fields only.

Numbers shown, matching the E5 handoff exactly:
- Held-out sessions passed: 42 of 61. Dev: 12 of 20.
- Calls, both pools: pass 805, rescued 78, silent-wrong 168, unscored 629.
- Judge agreement: 36 of 40 (0.9). Held-out replies judged not fitting: 152 of 488. Dev: 75 of 177.
- Discarded by the fidelity gate: held-out 2 of 63 runs (3.2 percent), dev 0 of 20.

Reading the heatmap (held-out, share of calls made):
- Silent-wrong is the column that stands out: slot_choice 33 percent (26 of 79), extract_days 22 percent (23 of 104), extract_problem 20 percent (13 of 64), doctor_pick 17 percent (7 of 42), turn_classifier 14 percent (40 of 288).
- Rescued: present_slots 56 percent (50 of 89), extract_phone 25 percent (6 of 24).
- Every NLG prompt except present_slots is 100 percent unscored, because NLG phrasing has no gold. Its quality shows up only through the validator (rescued) and the judge tile.
- The rates are over calls made, as eval design section 8 asks, so they read lower than the E3 entry's "of scored" fractions. extract_problem is 13 of 64 here and 13 of 51 there. One correction to that entry: slot_choice had 77 scored calls, not 79.

Harness lessons:
- Filter held-out on the server, not in the page. Held-out text never reaches the browser. The first draft of the server read the held-out generation logs through the scorer's shared log loader; that was caught before the first run, and the server now opens only the `eval_gen_dev*` logs and never a held-out transcript.
- On the lightest ramp step, a zero cell looked the same as a 1 to 8 percent cell. Zero cells now render blank, which is what makes the silent-wrong column legible.
- One step of the reference blue ramp (450) fails 4.5:1 text contrast with both dark and white text, so it is left out of the cell colours.
- Observation, not fixed: `checks/eval_2.sh` prints a held-out discard rate of 0.0 percent today, because discarded transcripts were already moved out of the pool directory. Its 10 percent ceiling can no longer fail after regeneration. The tab computes the rate from the discard files instead.
