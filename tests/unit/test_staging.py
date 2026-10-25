"""Tests for orchestrate.staging — copying inputs in without ever clobbering."""

import pytest

from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate import staging as ST


def test_stage_copies_file_into_input_dir(tmp_path):
    source = tmp_path / "教材.pdf"
    source.write_text("x", encoding="utf-8")
    root = tmp_path / "run"
    staged = ST.stage(root, [source])
    assert staged == (root / W.INPUT_DIR / "教材.pdf",)
    assert staged[0].is_file()


def test_stage_never_clobbers_an_existing_copy(tmp_path):
    source = tmp_path / "a.md"
    source.write_text("one", encoding="utf-8")
    root = tmp_path / "run"
    ST.stage(root, [source])
    target = root / W.INPUT_DIR / "a.md"
    target.write_text("edited by hand", encoding="utf-8")
    source.write_text("two", encoding="utf-8")
    ST.stage(root, [source])
    assert target.read_text(encoding="utf-8") == "edited by hand"


def test_stage_directory(tmp_path):
    folder = tmp_path / "pics"
    folder.mkdir()
    (folder / "1.png").write_bytes(b"x")
    root = tmp_path / "run"
    staged = ST.stage(root, [folder])
    assert (staged[0] / "1.png").is_file()


def test_stage_missing_input_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ST.stage(tmp_path / "run", [tmp_path / "ghost.pdf"])


def test_stage_empty_list_still_creates_input_dir(tmp_path):
    root = tmp_path / "run"
    assert ST.stage(root, []) == ()
    assert (root / W.INPUT_DIR).is_dir()
