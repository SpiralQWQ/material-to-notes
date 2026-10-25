"""Tests for report.logs."""

from material_to_notes.report import logs as L


def test_record_then_read(tmp_path):
    L.record(tmp_path, step="note", level="info", message="start", fingerprint="abc")
    L.record(tmp_path, step="note", level="error", message="boom")
    entries = L.read(tmp_path)
    assert len(entries) == 2
    assert entries[0]["step"] == "note" and entries[0]["level"] == "INFO"
    assert entries[0]["fp"] == "abc" and entries[0]["ts"]


def test_read_missing_is_empty(tmp_path):
    assert L.read(tmp_path) == []


def test_read_skips_broken_lines(tmp_path):
    L.record(tmp_path, step="a", level="info", message="ok")
    with L.path(tmp_path).open("a", encoding="utf-8") as handle:
        handle.write("{ not json\n")
    assert len(L.read(tmp_path)) == 1


def test_argv_omitted_when_not_given(tmp_path):
    L.record(tmp_path, step="clean", level="info", message="done")
    assert "argv" not in L.read(tmp_path)[0]


def test_argv_stored_as_strings(tmp_path):
    # Adapters hand Path objects; the log has to stay JSON-dumpable and readable.
    from pathlib import Path

    L.record(tmp_path, step="clean", level="info", message="executed",
             argv=["python", "-m", "cleaner.clean_md", Path("x") / "full.md"])
    argv = L.read(tmp_path)[0]["argv"]
    assert argv[:3] == ["python", "-m", "cleaner.clean_md"]
    assert isinstance(argv[3], str) and argv[3].endswith("full.md")
