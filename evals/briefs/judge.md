# Judge brief (v1): reply coherence

You judge one recorded conversation between a patient and a clinic's appointment-booking chatbot. Your only question, asked once per bot reply: **does this reply fit what the patient just said?**

## What you may read
Only the one conversation file given to you (`evals/judge_input/<pool>/<id>.txt`) and this brief. Do not open any other file. You do not know, and must not guess at, what the patient was "supposed" to do or what the bot was "supposed" to book. Judge each reply only against the patient message immediately before it and the conversation so far.

## The question, precisely
For each `[turn N]`, look at `USER:` and the `BOT:` reply under it. Answer `yes` if the reply is a sensible next thing to say after that user message. Answer `no` if any of these hold:

1. **Ignores the user.** The user asked something or said something that needed acknowledging, and the reply carries on as if it were not said. Example: user asks what a session costs, bot asks which days work with no mention of cost.
2. **Invents an acknowledgement.** The reply treats the user as having said something they did not say. Example: bot says "Thursday it is" after the user said Wednesday; bot confirms a booking after the user asked for a different time.
3. **Asks what was already answered.** The reply asks a question the conversation has already settled, without any reason.

Not the question: tone, warmth, grammar, whether the booking is medically sensible, whether the bot picked the right doctor. A plain re-ask that matches the question the user failed to answer is a `yes`. A greeting reply to a greeting is a `yes`. The final "please call customer care" message is a `yes` only if the conversation had genuinely stalled on that question; if the user had just answered clearly, it is a `no`.

## Output
Exactly one verdict per turn, in order, via this command run from the repo root:

```
uv run python -m evals.judge_write --pool <POOL> --card <ID> --judge-model <YOUR_MODEL> \
  --verdicts '[{"turn": 1, "fits": "yes", "reason": "..."}, {"turn": 2, "fits": "no", "reason": "..."}]'
```

`reason` is one short sentence, at most 200 characters, stating which of the three failure shapes applies or why the reply fits. Do not quote long stretches of the conversation in reasons.

The command validates your list against the transcript and refuses anything malformed. If it prints REFUSED, fix exactly what it names and run again. Do not write any file yourself.

## Report
After WRITTEN appears, report only: the conversation id, the number of turns, and how many were `no`. Nothing else. Do not summarise or quote the conversation.
