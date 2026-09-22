import csv
import json

from evals import judge_merge, judge_write

T = {"card_id": "c1", "run": {"session_id": "s"}, "turns": [{"turn": 1}, {"turn": 2}, {"turn": 3}]}


def test_writer_validation():
    ok = [{"turn": 1, "fits": "yes", "reason": "r"}, {"turn": 2, "fits": "no", "reason": "r"}, {"turn": 3, "fits": "yes", "reason": "r"}]
    assert judge_write.validate(T, ok) == []
    assert judge_write.validate(T, ok[:2])                      # missing turn
    assert judge_write.validate(T, ok + [ok[0]])                # duplicate turn
    bad = [dict(v) for v in ok]; bad[0]["fits"] = "maybe"
    assert judge_write.validate(T, bad)
    bad = [dict(v) for v in ok]; bad[1]["reason"] = "x" * 201
    assert judge_write.validate(T, bad)


def test_agreement_excludes_unsure_and_counts_confusion(tmp_path):
    labels = tmp_path / "labels.csv"
    with labels.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["card_id", "turn", "prior_bot", "user", "bot_reply", "label"]); w.writeheader()
        for turn, lab in ((1, "yes"), (2, "no"), (3, "unsure"), (4, "no")):
            w.writerow({"card_id": "c1", "turn": turn, "prior_bot": "", "user": "", "bot_reply": "", "label": lab})
    verdicts = {"c1": {"card_id": "c1", "judge_model": "m", "verdicts": [
        {"turn": 1, "fits": "yes"}, {"turn": 2, "fits": "yes"}, {"turn": 3, "fits": "no"}, {"turn": 4, "fits": "no"}]}}
    a = judge_merge.agreement(labels, verdicts)
    assert a["labelled"] == 3 and a["unsure"] == 1 and a["matched"] == 3
    assert a["agree"] == 2 and abs(a["rate"] - 2 / 3) < 1e-9
    assert a["confusion"] == {"human_yes/judge_yes": 1, "human_no/judge_yes": 1, "human_no/judge_no": 1}
