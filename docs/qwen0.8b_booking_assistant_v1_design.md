# Design and Implementation

Appointment booking assistant for a fictional mental health clinic, run on a 0.8B Qwen model with prompting only (no fine-tuning). Goal of v1: get the small model to do the basics reliably, with logging in place for the eval suite that follows.

## 1. Architecture

A state machine in code owns the workflow. The model handles one narrow task per call.

```
user text
  -> turn classifier (correction)
  -> NLU prompt for current state -> validator
  -> state update, tool calls, next state (code)
  -> NLG prompt for next state -> validator
  -> reply, or template fallback
```

Why split it this way: a 0.8B model cannot hold a multi-step workflow, decide when to call tools, and write replies in one prompt. It skips steps and invents slots. Code keeps the workflow; the model classifies, extracts, and phrases.

Rules that hold everywhere:

- One served model, many prompts. No per-stage model instances.
- Model never sees tool schemas. Code calls tools at state transitions.
- Facts (doctors, slots, dates) come from code. NLG only wraps them.
- Every model output passes a deterministic validator. Failure means a template or safe default, never a crash or a wrong fact shown to the user.
- Every validator decision is logged. That log is the eval dataset.

## 2. Workflow

```
GREET
ASK_FIRST_CONSULT
  yes -> ASK_PROBLEM -> ASK_DOCTOR_PREF
           named      -> CAPTURE_DOCTOR
           you_decide -> PICK_DOCTOR (shortlist)
  no  -> ASK_PHONE -> [fetch_patient] -> ASK_SESSION_TYPE
ASK_DAYS -> [fetch_availability]
  no slots -> ASK_DAYS (max 3 loops, then hand off)
SHOW_SLOTS -> CAPTURE_CHOICE -> [create_booking] -> CONFIRM -> END
```

Session state: `patient_type`, `problem`, `category`, `doctor_id`, `phone`, `session_type`, `days`, `offered_slots`, `chosen_slot`, `loop_counts` (one field holding re-ask counts per state, detour used per state, and correction count; reset rules live in `state_machine.py`).

Session type (therapy/follow-up) is a booking field only. It does not change doctor or slot length in v1.

Tools, all mocked against local fixtures: `fetch_patient(phone)`, `fetch_availability(doctor_id, days)`, `create_booking(...)`.

Hand-off: after 3 failed re-asks in one state, or 3 rounds with no slots, the session ends. The reply is a fixed template: the bot did not understand the request, and the user can call customer care at the clinic phone number. The number is a dummy value from `fixtures/clinic.json`. No transfer, ticket, or notification in v1. Every hand-off is logged with its reason.

## 3. Global intent: correction

Runs on every turn before state-specific NLU. If the user changes an earlier answer ("actually Wednesday", "I meant Dr. Rao"), code rewinds to the state that owns that field, clears downstream state (offered and chosen slots), and re-runs from there.

Classifier output: `{is_correction: bool, correction_field: doctor|days|session_type|phone|problem|null, new_value: string|null}`

The rewind map is a dict from field to state. Corrections are capped at 3 per session to prevent wandering.

## 4. Prompts

### 4.1 NLU (one prompt per job, not per state)

| Prompt | States | Output schema |
|---|---|---|
| `turn_classifier` | every turn | is_correction, correction_field, new_value |
| `yes_no` | ASK_FIRST_CONSULT, "other slots?" | intent: yes/no/other |
| `extract_problem` | ASK_PROBLEM | summary, category (enum from fixtures) |
| `doctor_pref` | ASK_DOCTOR_PREF | mode: named/you_decide/other, doctor_name |
| `doctor_pick` | PICK_DOCTOR | doctor_id (enum = shortlist), reason |
| `extract_phone` | ASK_PHONE | digits |
| `session_type` | ASK_SESSION_TYPE | type: therapy/followup/other |
| `extract_days` | ASK_DAYS | days[], time_pref |
| `slot_choice` | CAPTURE_CHOICE | choice_index, wants_other, other |
| `off_script` | any state on intent=other | is_question, topic |

Prompts live in prompts/{version}/, one directory per version, all NLU and NLG prompts together. A session picks one version. Each prompt is a markdown file with: role line, the question the bot asked, the user turn, output schema, 3 to 5 few-shot examples. Instructions do little for a model this size; few-shots do most of the work.

### 4.2 NLG (one prompt per reply type)

| Prompt | Inputs from code | Validator |
|---|---|---|
| `ask_question` | question intent, optional acknowledgement text | length cap, contains question |
| `present_slots` | doctor name, slot list | every slot present, no extra times |
| `no_slots` | days tried | length cap, contains re-ask |
| `confirm_booking` | booking record | all fields present, no extra fields |
| `clarify` | expected answer, FAQ hit if any | length cap |

## 5. Doctor matching (shortlist pick)

1. `extract_problem` gives a category.
2. Code filters doctor profiles by category tag to 2 or 3 candidates.
3. `doctor_pick` receives only those profiles (YoE, degree, skills writeup) and outputs `doctor_id` from a constrained enum, plus a `reason`.
4. Validator checks the chosen doctor's tags overlap the category. Mismatch falls back to code's top candidate.

The filter step has a flag. Turning it off gives full ranking over all doctors, kept as an eval-phase experiment.

### 5.1 Fixture sizing

- **Doctors: 7**, each with a subspecialty, category tags, a `conditions` list of common presenting problems, and a one-line skills summary. Subspecialties: general adult, mood/trauma/loss, stress and sleep, child and adolescent, de-addiction, geriatric, perinatal. Every category tag maps to exactly one doctor except `depression`, shared by two, so `doctor_pick` has one real judgment call and every other shortlist is a single candidate.
- **Categories: 12** (`extract_problem` enum, derived from the doctor tags): anxiety, depression, ocd, grief, trauma, relationships, stress, sleep, addiction, child_adolescent, geriatric, perinatal.
- **Slots: 4 working days per doctor, 2 to 3 slots per day, 13 to 16 per week.** Monday to Saturday within clinic hours, Sunday closed for everyone so the no-slots hand-off stays reachable. Patterns differ across doctors so morning, afternoon, and evening preferences matter.
- **Returning patients: 8**, at least one per doctor.
- **FAQ: 3 entries** (fees, hours, first visit).

## 6. Off-script handling

Default: re-ask the question. Exception: if `off_script` says `is_question`, allow one detour. `clarify` answers from a small FAQ fixture (hours, fees, what counts as a first visit) and re-asks. One detour per state.

## 7. Propose, validate, fallback

Every model call follows this shape:

```python
result, ok, reason = validate(complete(prompt, schema), state)
if not ok:
    result = fallback(state)
log(session_id, turn, state, prompt_name, ok, reason, raw_output)
```

Validators are deterministic: enum membership, regex (phone), set containment (slots in reply), length caps, tag overlap (doctor). Fallbacks are hand-written templates or a safe default (re-ask).

Narrow before you ask. Before each NLU call, code removes from the schema whatever it already knows to be impossible, and skips the call when it already knows the answer. Examples: `doctor_pref` loses the `named` mode when no roster name appears in the user text, and is not called at all when one does; `off_script` is only called when the text is shaped like a question and the state's own NLU passed validation. Schema field order puts evidence before labels (`doctor_name` before `mode`, `time_pref` before `days`). The model only decides what code cannot.

Log line per call, JSONL:
`{session_id, turn, state, model_id, prompt_name, prompt_version, validator_version, ok, reason_code, raw_output, latency_ms}`

`prompt_version` is the prompt directory in use; every validator module carries a VERSION constant. Both are stamped into each log line so eval-phase queries can compare `extract_days` v1 against v2 without reconstructing which commit was live.

Reading this file after 200 simulated sessions tells you which task the model fails most, how often code rescues it, and whether a prompt change helped. Formal evals build on top of this file.

Confidence: validator-only in v1. Logprobs are a v2 experiment; `complete()` returns an optional `logprobs` field so nothing downstream changes when added.

## 8. Serving

- llama-cpp-python loading a GGUF of the 0.8B Qwen in-process. Thinking mode off. Metal on the M4 locally, CPU on Hugging Face Spaces, same code.
- Constrained decoding via a grammar built from each NLU JSON schema. This zeroes out tokens that would break the schema, so output always parses and enums always match. It fixes format errors, not judgment errors.
- All calls go through `llm_client.complete(model_id, prompt, schema, params)`. `model_id` maps to a GGUF path in `models/registry.json`, so a fine-tuned or larger model is a registry entry, not a code change.
- llama-cpp-python exposes logprobs. v1 still uses validator-only confidence, but `complete()` returns them so the experiment needs no restructuring.

Why not Ollama: same llama.cpp underneath, but it needs a daemon a Space cannot run, and it hides logprobs. Running llama.cpp directly keeps dev and deploy on one path.

## 9. Interfaces

Bot is an HTTP API. Everything else is a client.

`POST /message {session_id, model_id, prompt_version, text}` returns `{reply, state, debug: {nlu_output, validator_results, fallback_used, latency_ms}}`

`model_id` selects the served model per session so the UI can put prompt-only, fine-tuned, and baseline models side by side. `prompt_version` selects the prompt directory, so the Space can pair any prompt version with any model.

Build order: CLI client, then a thin web UI with model and prompt-version dropdowns and the debug field shown in a side panel. The UI is one static HTML file with vanilla JS, served by FastAPI from the same process as the API. No frontend build step. On CPU each turn takes 3 to 4 model calls at 2 to 5 seconds each, so the UI streams per-call progress (classifying, extracting, writing reply). The wait should read as a debugger, not a stalled chat.

## 10. Repo layout

```
qwen0.8b-booking-assistant/
  app/
    api.py              FastAPI, /message
    state_machine.py    states, transitions, rewind map
    session.py          session store (in-memory dict, v1)
    llm_client.py       complete(model_id, prompt, schema, params) over llama-cpp-python
    nlu/                one module per NLU prompt + validator
    nlg/                one module per NLG prompt + validator + template
    tools/              mock_backend.py, fixtures loader
    logging.py          JSONL writer
  prompts/
    baseline/nlu/{name}.md
    baseline/nlg/{name}.md
    persona/...           same prompts, examples written in persona voice (later)
  fixtures/
    doctors.json, patients.json, slots.json, clinic.json, faq.json
  models/
    registry.json       model_id -> GGUF path, quant, source
    (GGUF files gitignored, pulled from Hugging Face at startup)
  clients/
    cli.py
    ui/
  tests/
  checks/
    phase_0.sh ... phase_7.sh   one executable check per phase, exit 0 on pass
    all.sh                      runs every phase check in order
  Dockerfile            Spaces deploy, same image runs locally
  pyproject.toml        uv
```

## 11. Build phases (Claude Code)

Each phase has an executable check in `checks/phase_N.sh`. The first task of every phase is to write that script; the phase is complete when it exits 0 and `checks/all.sh` still passes. The human runs both locally before the commit.

**Phase 0: scaffold**
uv project, FastAPI skeleton, `/health`, GGUF pulled into `models/`, registry with one entry, `llm_client.complete()` returning schema-valid JSON for a toy prompt.
`checks/phase_0.sh`: curls `/health`, runs a one-line script asserting a constrained yes/no parses and returns latency and logprobs.

**Phase 1: state machine without a model**
All states, transitions, session store, mock tools, fixtures. NLU stubbed to return hard-coded answers.
`checks/phase_1.sh`: pytest walks both workflows end to end with stubbed NLU and asserts a booking record exists.

**Phase 2: NLU**
Ten NLU prompts, schemas, validators with version constants, JSONL logging, template fallbacks for NLU failures.
`checks/phase_2.sh`: replays two scripted CLI conversations (one per workflow), asserts a booking, and asserts the JSONL log has one line per model call with all required fields.

**Phase 3: NLG**
Five NLG prompts with validators and templates.
`checks/phase_3.sh`: replays a scripted conversation through NLG; pytest injects a fake slot into `present_slots` output and asserts the template is used and logged as a fallback.

**Phase 4: correction intent**
Turn classifier, rewind map, downstream clearing.
`checks/phase_4.sh`: scripted conversation changes the doctor at SHOW_SLOTS; asserts state rewinds, offered slots clear, and availability is re-fetched for the new doctor.

**Phase 5: off-script and shortlist pick**
`off_script` prompt, FAQ fixture, `clarify`; `doctor_pick` with filter flag.
`checks/phase_5.sh`: scripted "what are your fees?" at ASK_FIRST_CONSULT asserts a FAQ answer plus re-ask in one reply and state unchanged; scripted "you decide" asserts a doctor_id from the shortlist with a non-empty reason.

**Phase 6: UI**
Thin web UI with model and prompt-version dropdowns, debug panel, per-call progress. `/models` and `/prompts` endpoints to populate dropdowns.
`checks/phase_6.sh`: curls `/`, `/models`, `/prompts`; asserts the static file is served and both lists are non-empty.

**Phase 7: Spaces deploy**
Dockerfile, GGUF download at startup, Space secrets if any, README model card.
`checks/phase_7.sh`: builds the Docker image locally, starts it, runs `checks/phase_2.sh` against the container. Manual: open the Space URL, pick a model, book an appointment.

Eval phases (cards, transcript generation, fidelity gate, scoring and replay, judge, Evals tab) follow Phase 7. Their design is `eval_design_v1.md`; their phase numbers and checks are added here when that work starts.

## 11a. Hugging Face Spaces

Free tier is 2 vCPU, 16GB RAM, no GPU. A 0.8B GGUF at Q8 is about 1GB, so two or three models fit in memory at once. Expect 2 to 5 seconds per model call, 10 to 15 seconds per turn.

What the Space is for: letting a reviewer type a query and watch the NLU output, validator result, and fallback decision per turn, and switch between prompt-only and fine-tuned models on the same conversation. It is a debugger with a chat window, not a product demo.

Adding a fine-tuned model later: train with TRL, convert to GGUF with the llama.cpp convert script, quantize, add a registry entry, redeploy.

## Appendix: parked for later

- Simulator, persona cards, and eval suite: designed in `eval_design_v1.md` (2026-09-17). No longer parked. Eval build phases will be added to section 11 when the eval phase starts.
- Safety and distress handling, designed from scratch
- Child and adolescent bookings: the caller is a parent, but v1 treats the caller as the patient. Needs a "booking for someone else" field
- Full-ranking doctor matching (filter flag exists, experiment later)
- Logprob-based confidence (returned by `complete()`, unused in v1)
- Fine-tuning path (TRL to GGUF) and side-by-side model comparison on the Space
- Results writeup and publishing the simulated conversation set as a Hugging Face dataset
