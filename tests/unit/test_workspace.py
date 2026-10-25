"""Tests for orchestrate.workspace — run initialization and state I/O."""

from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate import workspace as WS


def test_init_creates_layout_and_state(tmp_path):
    WS.init(tmp_path, input_kind="video", inputs=["a.mp4"])
    assert W.missing(tmp_path) == []
    state = WS.load(tmp_path)
    assert state["input_kind"] == "video" and state["inputs"] == ["a.mp4"]


def test_init_is_idempotent_and_does_not_clobber(tmp_path):
    WS.init(tmp_path, input_kind="video")
    state = WS.load(tmp_path)
    state["steps"]["note"] = {"status": "done", "fp": "x"}
    WS.save(tmp_path, state)
    WS.init(tmp_path, input_kind="video")
    assert WS.load(tmp_path)["steps"]["note"]["status"] == "done"


def test_init_overwrite_replaces_state(tmp_path):
    WS.init(tmp_path, input_kind="video")
    WS.init(tmp_path, input_kind="pdf", overwrite=True)
    assert WS.load(tmp_path)["input_kind"] == "pdf"


def test_load_missing_returns_none(tmp_path):
    assert WS.load(tmp_path) is None


def test_load_corrupt_returns_none(tmp_path):
    W.ensure(tmp_path)
    WS.state_path(tmp_path).write_text("{ not json", encoding="utf-8")
    assert WS.load(tmp_path) is None


def test_save_leaves_no_temp_file(tmp_path):
    WS.init(tmp_path)
    WS.save(tmp_path, {"version": 1, "steps": {}})
    assert list((tmp_path / W.STATE_DIR).glob(".tmp-*")) == []


def test_save_then_load_roundtrip(tmp_path):
    WS.init(tmp_path)
    WS.save(tmp_path, {"version": 1, "steps": {"note": {"status": "done", "fp": "z"}}})
    assert WS.load(tmp_path)["steps"]["note"]["fp"] == "z"
