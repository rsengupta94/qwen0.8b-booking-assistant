"""Scorer: outcome classes per call and session verdicts on a synthetic transcript and log."""
import copy

from evals import score

CARD = {"card_id": "t", "facts": {"patient_type": "new", "phone": None, "problem_category": "grief", "symptom_brief": [],
        "doctor_pref": {"mode": "you_decide"}, "session_type": None, "days": ["saturday"], "time_pref": None, "slot_rule": "first"},
        "scripted_events": [], "verbatim": {}, "stop_after": "booking_confirmed"}
OFFERED = ["2026-09-19T11:00", "2026-09-19T12:00", "2026-09-26T11:00"]


def tr(n, state, text, act="answer", field=None, value=None, slot_rule=None, bot_state="X", kind=None, offered=None, booking=None, reply="..."):
    return {"turn": n, "answering_state": state, "user": text, "sidecar": {"act": act, "field": field, "value": value, "slot_rule": slot_rule},
            "bot": {"reply": reply, "state": bot_state, "kind": kind, "offered_slots": offered, "booking": booking}}


T = {"card_id": "t", "persona_id": "p", "scenario_id": "D1", "pool": "dev", "eval_set_version": 1,
     "run": {"session_id": "s1", "generated_at": "20260918T100000Z", "model_id": "m", "prompt_version": "baseline", "simulator_model": "x"},
     "ended": "booking_confirmed",
     "turns": [tr(1, "GREET", "hi", bot_state="ASK_FIRST_CONSULT"),
               tr(2, "ASK_FIRST_CONSULT", "yes", "answer", "patient_type", "new", bot_state="ASK_PROBLEM"),
               tr(3, "ASK_PROBLEM", "father died, cannot sleep", "answer", "problem", "grief", bot_state="ASK_DOCTOR_PREF"),
               tr(4, "ASK_DOCTOR_PREF", "you pick", "answer", "doctor", None, bot_state="ASK_DAYS"),
               tr(5, "ASK_DAYS", "saturday", "answer", "days", "saturday", bot_state="CAPTURE_CHOICE", kind="present_slots", offered=OFFERED),
               tr(6, "CAPTURE_CHOICE", "1", "answer", "slot", "1", "first", bot_state="END", kind="confirm_booking",
                  booking={"doctor_id": "d_khan", "start": "2026-09-19T11:00:00"})]}


def log(turn, state, prompt, raw, ok=True):
    return {"session_id": "s1", "turn": turn, "state": state, "prompt_name": prompt, "ok": ok, "reason_code": "ok" if ok else "bad",
            "raw_output": raw, "validator_version": "1"}


LOGS = {2: [log(2, "ASK_FIRST_CONSULT", "yes_no", '{"intent": "yes"}')],
        3: [log(3, "ASK_PROBLEM", "extract_problem", '{"category": "sleep", "summary": "x"}')],
        4: [log(4, "ASK_DOCTOR_PREF", "turn_classifier", '{"is_correction": false}'),
            log(4, "ASK_DOCTOR_PREF", "doctor_pref", '{"mode": "you_decide", "doctor_name": null}'),
            log(4, "PICK_DOCTOR", "doctor_pick", '{"doctor_id": "d_iyer", "reason": "r"}')],
        5: [log(5, "ASK_DAYS", "extract_days", '{"days": ["saturday"], "time_pref": null}'),
            log(5, "CAPTURE_CHOICE", "present_slots", '{"reply": "..."}', ok=False)],
        6: [log(6, "CAPTURE_CHOICE", "slot_choice", '{"choice_index": 1, "wants_other": false}')]}


def outcomes(r, prompt):
    return [c["outcome"] for c in r["calls"] if c["prompt"] == prompt]


def test_call_outcomes():
    r = score.score_transcript(CARD, T, LOGS)
    assert outcomes(r, "yes_no") == ["pass"]
    assert outcomes(r, "extract_problem") == ["silent_wrong"]      # grief expected, sleep returned
    assert outcomes(r, "doctor_pick") == ["pass"]                  # judged against the extracted category (sleep -> Iyer)
    assert outcomes(r, "present_slots") == ["rescued"]
    assert outcomes(r, "slot_choice") == ["pass"]


def test_session_fails_on_wrong_doctor_but_passes_when_right():
    r = score.score_transcript(CARD, T, LOGS)
    assert r["session"]["pass"] is True  # booking names Khan, the grief doctor, first offered slot
    t2 = copy.deepcopy(T); t2["turns"][-1]["bot"]["booking"] = {"doctor_id": "d_iyer", "start": "2026-09-19T11:00:00"}
    r2 = score.score_transcript(CARD, t2, LOGS)
    assert r2["session"]["pass"] is False and "wrong_doctor" in r2["session"]["reason"]
    t3 = copy.deepcopy(T); t3["turns"][-1]["bot"]["booking"] = {"doctor_id": "d_khan", "start": "2026-09-19T12:00:00"}
    assert "wrong_slot" in score.score_transcript(CARD, t3, LOGS)["session"]["reason"]


def test_booking_recovered_from_reply_when_record_missing():
    t = copy.deepcopy(T); t["turns"][-1]["bot"]["booking"] = None
    t["turns"][-1]["bot"]["reply"] = "Your first consultation with Dr. Sana Khan is confirmed for Saturday 19 September at 11:00. Ref b0001."
    r = score.score_transcript(CARD, t, LOGS)
    assert r["session"]["pass"] is True and r["session"]["booking"]["doctor_id"] == "d_khan"


def test_handoff_verdicts_and_gave_up():
    t = copy.deepcopy(T); t["ended"] = "handoff"
    t["turns"] = t["turns"][:2] + [tr(3, "ASK_PROBLEM", "?", "non_answer", bot_state="ASK_PROBLEM"),
                                   tr(4, "ASK_PROBLEM", "?", "non_answer", bot_state="ASK_PROBLEM"),
                                   tr(5, "ASK_PROBLEM", "?", "non_answer", bot_state="END", kind="handoff")]
    r = score.score_transcript(CARD, t, {})
    assert r["session"]["pass"] is True and r["session"]["reason"] == "handoff_persona_caused"
    t2 = copy.deepcopy(T); t2["ended"] = "handoff"; t2["turns"][-1]["bot"].update(kind="handoff", booking=None)
    assert score.score_transcript(CARD, t2, {})["session"]["reason"] == "handoff_product_caused"
    t3 = copy.deepcopy(T); t3["ended"] = "gave_up"
    assert score.score_transcript(CARD, t3, {})["session"]["pass"] is False


def test_routing_flags_product_advancing_on_non_answer():
    t = copy.deepcopy(T)
    t["turns"][2] = tr(3, "ASK_PROBLEM", "how much is it?", "non_answer", bot_state="ASK_DOCTOR_PREF")
    r = score.score_transcript(CARD, t, LOGS)
    assert r["turns"][2]["routing_ok"] is False and r["turns"][2]["expected_next"] == "ASK_PROBLEM"
    assert outcomes(r, "extract_problem") == ["silent_wrong"]
