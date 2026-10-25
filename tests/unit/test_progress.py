"""Tests for report.progress."""

from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate.runner import StepRecord
from material_to_notes.report import progress as P


def test_line_labels():
    assert P.line("note", "done") == "[完成] note"
    assert P.line("media", "skipped") == "[跳过] media"


def test_artifacts_lists_files(tmp_path):
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "note.md").write_text("x", encoding="utf-8")
    assert P.artifacts(tmp_path, "note") == ("04_笔记/note.md",)


def test_build_has_a_row_per_step(tmp_path):
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "note.md").write_text("x", encoding="utf-8")
    text = P.build([StepRecord("note", "done")], tmp_path)
    assert "note" in text and "04_笔记/note.md" in text


def test_inconsistent_flags_done_without_artifact(tmp_path):
    assert P.inconsistent([StepRecord("note", "done")], tmp_path) == ("note",)


def test_failed_step_does_not_present_leftovers_as_this_runs_output(tmp_path):
    stale = tmp_path / "03_清洗"
    stale.mkdir()
    (stale / "full.txt").write_text("old", encoding="utf-8")
    text = P.build([StepRecord("clean", "failed")], tmp_path)
    assert "不可信" in text
    assert "full.txt" not in text


def test_a_skipped_step_with_artifacts_does_not_read_as_never_done(tmp_path):
    """"跳过"孤零零一个词会被读成"这一步没做"——它其实是"上轮做过、本轮没重跑"。"""
    base = tmp_path / "03_清洗"
    base.mkdir()
    (base / "full.txt").write_text("x", encoding="utf-8")
    text = P.build([StepRecord("clean", "skipped")], tmp_path)
    assert "| clean | 完成（本轮未重跑） |" in text


def test_a_skipped_step_without_artifacts_stays_plain(tmp_path):
    text = P.build([StepRecord("clean", "skipped")], tmp_path)
    assert "| clean | 跳过 |" in text


def test_the_note_row_can_be_added_to_an_existing_sheet(tmp_path):
    """笔记由 agent 手写、不走 `pipeline step`，进度单里原本没有它那一行（T58）。"""
    sheet = P.build([StepRecord("clean", "done")], tmp_path)
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "n.md").write_text("x", encoding="utf-8")
    out = P.with_note_row(sheet, tmp_path, "note")
    assert "| note | 完成 | 04_笔记/n.md |" in out
    assert "| clean |" in out                      # 原有行保留
    assert out.index("| clean |") < out.index("| note |")   # note 在最后


def test_write_lands_in_workdir(tmp_path):
    path = P.write(tmp_path, "hello")
    assert path == tmp_path / W.PROGRESS_FILE
    assert path.read_text(encoding="utf-8") == "hello"
