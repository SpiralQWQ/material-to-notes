"""Tests for gates.machine."""

from material_to_notes.gates import machine as M


def _put(root, step_dir, files):
    base = root / step_dir
    base.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_passes_when_outputs_present(tmp_path):
    _put(tmp_path, "04_笔记", {"note.md": "hello"})
    result = M.check("note", tmp_path)
    assert result.passed and result.failed() == ()


def test_fails_when_output_missing(tmp_path):
    result = M.check("note", tmp_path)
    assert not result.passed and "output-contract" in result.failed()


def test_fails_on_undecodable_text(tmp_path):
    _put(tmp_path, "04_笔记", {"note.md": "hello"})
    (tmp_path / "04_笔记" / "bad.txt").write_bytes(b"\xff\xfe\x00bad")
    result = M.check("note", tmp_path)
    assert not result.passed and "utf8-decodable" in result.failed()


def test_bom_is_accepted(tmp_path):
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True, exist_ok=True)
    (base / "note.md").write_bytes("﻿hello".encode("utf-8"))
    assert M.check("note", tmp_path).passed


def test_fails_on_empty_file(tmp_path):
    _put(tmp_path, "04_笔记", {"note.md": "hello", "empty.json": ""})
    result = M.check("note", tmp_path)
    assert not result.passed and "no-empty-files" in result.failed()


def test_raw_evidence_is_kept(tmp_path):
    _put(tmp_path, "04_笔记", {"note.md": "hi"})
    assert "PASS" in M.check("note", tmp_path).raw


def test_check_all_covers_chain(tmp_path):
    _put(tmp_path, "04_笔记", {"note.md": "hi"})
    results = M.check_all(tmp_path, ("note", "media"))
    assert [r.step for r in results] == ["note", "media"]
