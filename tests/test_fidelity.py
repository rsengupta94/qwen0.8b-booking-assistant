"""One test per fidelity gate rule, pass and fail, on synthetic cards and transcripts."""
import copy

from evals.fidelity import check

CARD = {
    "card_id": "T__p", "pool": "dev", "eval_set_version": 1,
    "persona": {"proficiency": "proficient", "personality": "patient", "clarity": "no_idea", "behaviors": []},
    "facts": {"patient_type": "new", "phone": None, "problem_category": "grief",
              "symptom_brief": ["x"], "doctor_pref": {"mode": "you_decide"}, "session_type": None,
              "days": ["saturday"], "time_pref": None, "slot_rule": "first"},
    "scripted_events": [], "verbatim": {}, "stop_after": "booking_confirmed",
}


def turn(n, state, text, act="answer", field=None, value=None, slot_rule=None, bot_state="X", offered=None):
    return {"turn": n, "answering_state": state, "user": text,
            "sidecar": {"act": act, "field": field, "value": value, "slot_rule": slot_rule},
            "bot": {"reply": "...", "state": bot_state, "kind": None, "offered_slots": offered}}


OFFERED = ["2026-09-19T11:00:00", "2026-09-19T12:00:00", "2026-09-26T11:00:00"]


GOOD = {
    "ended": "booking_confirmed",
    "turns": [
        turn(1, "GREET", "hi", "answer"),
        turn(2, "ASK_FIRST_CONSULT", "yes first time", "answer", "patient_type", "new"),
        turn(3, "ASK_PROBLEM", "my father died and I lie awake", "answer", "problem", "grief"),
        turn(4, "ASK_DOCTOR_PREF", "you pick", "answer", "doctor", None),
        turn(5, "ASK_DAYS", "saturday", "answer", "days", "saturday", offered=OFFERED),
        turn(6, "CAPTURE_CHOICE", "the first one", "answer", "slot", "1", "first"),
    ],
}


def test_good_transcript_kept():
    assert check(CARD, GOOD) == []


def test_not_ended_discarded():
    t = copy.deepcopy(GOOD); t["ended"] = None
    assert any(r.startswith("not_ended") for r in check(CARD, t))


def test_handoff_and_gave_up_are_kept_not_discarded():
    for kind in ("handoff", "gave_up", "turn_cap"):
        t = copy.deepcopy(GOOD); t["ended"] = kind
        assert check(CARD, t) == [], kind


def test_label_in_utterance_flagged_for_no_idea():
    t = copy.deepcopy(GOOD); t["turns"][2]["user"] = "I have grief since my father died"
    assert any(r.startswith("label_in_utterance") for r in check(CARD, t))


def test_ordinary_label_allowed_for_some_idea_only():
    c = copy.deepcopy(CARD); c["facts"]["problem_category"] = "sleep"
    t = copy.deepcopy(GOOD); t["turns"][2]["user"] = "I cannot sleep"; t["turns"][2]["sidecar"]["value"] = "sleep"
    assert any(r.startswith("label_in_utterance") for r in check(c, t))
    c["persona"]["clarity"] = "some_idea"
    assert check(c, t) == []


def test_days_and_phone_mismatch():
    t = copy.deepcopy(GOOD); t["turns"][4]["sidecar"]["value"] = "tuesday"
    assert any(r.startswith("days_mismatch") for r in check(CARD, t))
    c = copy.deepcopy(CARD); c["facts"]["phone"] = "9876543210"
    t2 = copy.deepcopy(GOOD); t2["turns"].insert(2, turn(3, "ASK_PHONE", "+91 98765 43210", "answer", "phone", "+91 98765 43210"))
    assert not any(r.startswith("phone_mismatch") for r in check(c, t2))
    t2["turns"][2]["sidecar"]["value"] = "9000000000"
    assert any(r.startswith("phone_mismatch") for r in check(c, t2))


def test_slot_rule_mismatch():
    t = copy.deepcopy(GOOD); t["turns"][5]["sidecar"]["slot_rule"] = "last"
    assert any(r.startswith("slot_rule_mismatch") for r in check(CARD, t))


def test_slot_pick_must_match_rule():
    t = copy.deepcopy(GOOD); t["turns"][5]["sidecar"]["value"] = "2"
    assert any(r.startswith("slot_pick_mismatch") for r in check(CARD, t))
    t["turns"][5]["sidecar"]["value"] = None
    assert any(r.startswith("slot_value_missing") for r in check(CARD, t))
    t = copy.deepcopy(GOOD); t["turns"][5]["user"] = "2"
    assert any(r.startswith("slot_text_value_conflict") for r in check(CARD, t))
    c = copy.deepcopy(CARD); c["facts"]["slot_rule"] = "first_afternoon"
    t = copy.deepcopy(GOOD); t["turns"][5]["sidecar"].update(slot_rule="first_afternoon", value="2")
    assert check(c, t) == []
    c["facts"]["slot_rule"] = "last"; t["turns"][5]["sidecar"].update(slot_rule="last", value="3")
    assert check(c, t) == []


def test_verbatim_required_in_state():
    c = copy.deepcopy(CARD); c["verbatim"] = {"ASK_PROBLEM": "I can't sleep since my father died"}
    assert any(r.startswith("verbatim_missing") for r in check(c, GOOD))
    t = copy.deepcopy(GOOD); t["turns"][2]["user"] = "Honestly, I can't sleep since my father died."
    assert check(c, t) == []


def test_scripted_event_fired_missed_or_unreached():
    c = copy.deepcopy(CARD)
    c["scripted_events"] = [{"at_state": "ASK_DAYS", "act": "faq_question", "payload": {"topic": "fees"}}]
    assert any(r.startswith("event_missed") for r in check(c, GOOD))
    t = copy.deepcopy(GOOD); t["turns"].insert(4, turn(5, "ASK_DAYS", "how much is it?", "faq_question", "topic", "fees"))
    assert check(c, t) == []
    short = copy.deepcopy(GOOD); short["turns"] = short["turns"][:3]; short["ended"] = "handoff"
    assert "scenario_not_exercised" in check(c, short)


def test_correction_tracks_effective_fact_and_rejects_unscripted():
    c = copy.deepcopy(CARD)
    c["scripted_events"] = [{"at_state": "SHOW_SLOTS", "act": "correction", "payload": {"field": "days", "new_value": "thursday"}}]
    t = copy.deepcopy(GOOD)
    t["turns"].insert(5, turn(6, "SHOW_SLOTS", "actually thursday", "correction", "days", "thursday"))
    t["turns"].insert(6, turn(7, "ASK_DAYS", "thursday", "answer", "days", "thursday", offered=OFFERED))
    assert check(c, t) == []
    assert any(r.startswith("unscripted_correction") for r in check(CARD, t))


def test_two_corrections_same_field_consumed_in_order():
    c = copy.deepcopy(CARD)
    c["scripted_events"] = [
        {"at_state": "CAPTURE_CHOICE", "act": "correction", "payload": {"field": "days", "new_value": "thursday"}},
        {"at_state": "CAPTURE_CHOICE", "act": "correction", "payload": {"field": "days", "new_value": "saturday"}},
    ]
    t = copy.deepcopy(GOOD)
    t["turns"] = t["turns"][:5] + [
        turn(6, "CAPTURE_CHOICE", "actually thursday", "correction", "days", "thursday", offered=OFFERED),
        turn(7, "ASK_DAYS", "thursday", "answer", "days", "thursday", offered=OFFERED),
        turn(8, "CAPTURE_CHOICE", "no wait, saturday", "correction", "days", "saturday", offered=OFFERED),
        turn(9, "ASK_DAYS", "saturday", "answer", "days", "saturday", offered=OFFERED),
        turn(10, "CAPTURE_CHOICE", "1", "answer", "slot", "1", "first"),
    ]
    assert check(c, t) == []
