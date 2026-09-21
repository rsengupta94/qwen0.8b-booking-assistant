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
