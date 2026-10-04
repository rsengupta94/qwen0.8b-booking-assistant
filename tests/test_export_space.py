"""Static Space export: same run payloads as the eval server, dev conversations only, no held-out-only text."""
import json
import sys

import pytest

from evals import export_space, server


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    d = tmp_path_factory.mktemp("space") / "build"
    argv, sys.argv = sys.argv, ["export_space", "--out", str(d)]
    try:
        export_space.main()
    finally:
        sys.argv = argv
    return d


def test_run_files_match_the_eval_server(out):
    runs = json.loads((out / "data" / "evals" / "runs.json").read_text())
    assert runs == server.runs()
    for r in runs:
        exported = json.loads((out / "data" / "evals" / "runs" / f"{r['run_id']}.json").read_text())
        assert exported == json.loads(json.dumps(server.run(r["run_id"])))


def test_conversations_are_dev_only(out):
    convs = json.loads((out / "data" / "conversations.json").read_text())
    dev = {p.stem for p in (export_space.ROOT / "transcripts" / "dev").glob("*.json")}
    assert {c["card_id"] for c in convs} == dev
    assert all(c["session"] and c["turns"] for c in convs)


def test_no_heldout_only_utterance_is_exported(out):
    assert export_space.heldout_leaks(out) == []


def test_leak_scan_catches_a_planted_heldout_utterance(out, tmp_path):
    only = export_space.heldout_only()
    (tmp_path / "planted.json").write_text(json.dumps({"x": [only[0]]}))
    assert export_space.heldout_leaks(tmp_path) == ["planted.json"]


def test_card_is_a_static_space_with_numbers_filled(out):
    card = (out / "README.md").read_text()
    assert "\nsdk: static\n" in card and "{{" not in card


def test_refuses_to_wipe_a_folder_it_did_not_build(tmp_path, monkeypatch):
    (tmp_path / "keep.txt").write_text("x")
    monkeypatch.setattr("sys.argv", ["export_space", "--out", str(tmp_path)])
    with pytest.raises(SystemExit):
        export_space.main()
    assert (tmp_path / "keep.txt").exists()
