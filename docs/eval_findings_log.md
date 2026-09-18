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
