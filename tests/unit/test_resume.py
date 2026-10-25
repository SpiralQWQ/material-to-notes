"""Tests for orchestrate.resume — what still needs to run."""

from material_to_notes.orchestrate import resume as RS


def test_fingerprint_changes_with_content(tmp_path):
    target = tmp_path / "a.md"
    target.write_text("one", encoding="utf-8")
    first = RS.fingerprint(target)
    target.write_text("two-longer", encoding="utf-8")
    assert RS.fingerprint(target) != first


def test_fingerprint_missing_is_empty(tmp_path):
    assert RS.fingerprint(tmp_path / "nope") == ""


def test_is_done_requires_matching_fingerprint():
    state = {"steps": {"note": {"status": "done", "fp": "abc"}}}
    assert RS.is_done(state, "note", "abc")
    assert not RS.is_done(state, "note", "other")
    assert not RS.is_done(state, "clean", "abc")


def test_mark_done_is_pure():
    state = {"steps": {}}
    updated = RS.mark_done(state, "note", "abc")
    assert "note" not in state["steps"]
    assert updated["steps"]["note"]["status"] == "done"


def test_pending_lists_unfinished():
    state = {"steps": {"media": {"status": "done", "fp": "1"}}}
    fps = {"media": "1", "clean": "2", "note": "3"}
    assert RS.pending(state, ("media", "clean", "note"), fps) == ("clean", "note")
