from evals import guard


def test_norm_and_overlap_logic(tmp_path, monkeypatch):
    assert guard.norm("  I can't sleep, since my FATHER died! ") == "i can t sleep since my father died"
    monkeypatch.setattr(guard, "heldout_utterances", lambda: ["i want an appointment with dr roa"])
    monkeypatch.setattr(guard, "prompt_lines", lambda: [("prompts/x.md", 3, "reply i want an appointment with dr roa please")])
    assert guard.check() == [("prompts/x.md", 3)]
    monkeypatch.setattr(guard, "prompt_lines", lambda: [("prompts/x.md", 3, "reply i would like to book something")])
    assert guard.check() == []
