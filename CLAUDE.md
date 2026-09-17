# CLAUDE.md

Appointment booking assistant for a fictional mental health clinic, run on a 0.8B Qwen model with prompting only. Read `docs/qwen0.8b_booking_assistant_v1_design.md` (called "design.md" below) before starting any task. It is the source of truth; if a task conflicts with it, stop and ask. For eval work, `docs/eval_design_v1.md` (design) and `docs/eval_phases_v1.md` (phases E1 to E5, checks in `checks/eval_N.sh`) are the source of truth alongside it.

## Stack

- Python 3.12, `uv` for dependencies and running (`uv run ...`). Never `pip install` directly.
- FastAPI + uvicorn. One process serves the API and the static UI.
- llama-cpp-python loading GGUF files listed in `models/registry.json`. No Ollama, no transformers.
- pytest for tests. Every validator has its own test file.
- Docker for deploy to Hugging Face Spaces. The same Dockerfile runs locally.

## Architecture rules

These are not preferences. Do not deviate without asking.

1. The state machine in `app/state_machine.py` owns workflow, session state, and all tool calls. The model never sees tool schemas and never decides state transitions.
2. One model call does one job. NLU prompts classify or extract into a JSON schema. NLG prompts phrase a reply from facts passed in by code. No prompt does both.
3. Every NLU call uses constrained decoding from its JSON schema. No free-text parsing of model output.
4. Every model output passes a deterministic validator before use. On failure, use the template or safe default for that state. Never crash, never show the user a fact the model produced.
5. Facts (doctors, slots, dates, phone) come from code and fixtures. NLG wraps them; validators confirm they were not altered.
6. Every model call writes one JSONL log line with the fields in design.md section 7, including `prompt_version` and `validator_version`.
7. All model calls go through `app/llm_client.complete(model_id, prompt, schema, params)`. No other module imports llama-cpp-python.
8. Eval code is isolated from the product. `app/` never imports from the eval package. The eval package reaches the product only over `/message` and by reading its JSONL and results files. Held-out persona cards and their transcripts are never opened while writing prompts, and no few-shot copies a held-out utterance.

## Layout

Follow the repo layout in design.md section 10 exactly. Prompts are markdown files in `prompts/{version}/nlu/` and `prompts/{version}/nlg/`, one per prompt, one directory per prompt version (`baseline` first, `persona` later). A session picks one version; `prompt_version` in the log line is that directory name. Never embed prompt text in Python. Validators are one module each in `app/nlu/` and `app/nlg/`, each exporting `VERSION`, `validate()`, and (for NLG) `template()`.

## How we work

- One phase per session, from design.md section 11. Implement only the phase asked for.
- First task of a phase: write `checks/phase_N.sh`. The phase is complete only when `bash checks/phase_N.sh` and `bash checks/all.sh` both exit 0 and their full output is pasted in the response. A phase without green check output is not done, regardless of what the code looks like.
- Before writing code for a phase, list the files you will create or change and wait for confirmation.
- Give exact sequential commands with the directory they run in and the expected output. No "run the tests" without the command.
- If a phase check fails, show the failure, propose one fix, apply it, rerun. Do not silently restructure.
- Do not add features, abstractions, or "while I'm here" refactors outside the phase scope.
- Commit at each passing phase check with message `phase N: <what>`.

## Things not in v1

Do not implement or scaffold any of these, even as stubs: safety or distress handling, multilingual input, fine-tuning, logprob-based confidence, booking for someone else. They are listed in the design.md appendix and will get their own design pass. Evals and the simulator are designed in `docs/eval_design_v1.md` and are built only in the eval phases, when asked.

## End-of-phase report

End every phase session with this, in this order:

1. Files created or changed (paths)
2. Prompts added or changed (name, version, one line on what it asks)
3. Validators added or changed (name, version, one line on what it checks)
4. Full output of `checks/phase_N.sh` and `checks/all.sh`
5. Anything you were unsure about or deviated from design.md

## Review points

The human reviews every prompt file and every validator before the phase is committed. When you create or change one, say so explicitly and summarize what it checks or asks.
