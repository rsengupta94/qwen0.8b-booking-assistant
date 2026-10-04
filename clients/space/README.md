---
title: Booking assistant on a 0.8B model
emoji: 📅
colorFrom: blue
colorTo: gray
sdk: static
app_file: index.html
pinned: false
short_description: Prompt-only booking assistant on a 0.8B model, with evals
---

# Booking assistant on a 0.8B model

Demo of a booking assistant for a fictional clinic. All conversations are simulated. This is not a mental-health service. If you need help, contact your local emergency number or a crisis line.

## What it is

An appointment booking assistant for a fictional mental health clinic, run on a 0.8B model (`{{model_id}}`) with prompting only. Code owns the workflow. The model only reads each patient message into a fixed JSON shape and phrases replies from facts the code passes in. Every model output is checked by code, and a fixed template takes over when a check fails.

## What this page shows

Nothing here runs a model. It shows recorded runs.

- **Conversations:** simulated patients booking with the assistant, replayed turn by turn. The debug panel shows every model call, whether its check passed, and the raw output.
- **Evals:** results for prompt version `{{prompt_version}}`. On the held-out set, {{passed}} of {{sessions}} simulated conversations ended correctly (the booking the patient asked for, or a hand-off the patient caused), and an LLM judge marked {{fits_no}} of {{replies}} bot replies as not fitting the patient's message. The heatmap shows where each model call landed: correct, caught by a check, silently wrong, or not scored.
