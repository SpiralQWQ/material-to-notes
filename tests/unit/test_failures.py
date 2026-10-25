"""Tests for orchestrate.failures — retry budget and hand-off sheet."""

from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate import failures as FL


def test_attempts_are_per_step():
    attempts = FL.Attempts(max_attempts=3)
    assert attempts.record("media") == 1
    assert attempts.record("media") == 2
    assert attempts.record("clean") == 1
    assert not attempts.exhausted("media")
    attempts.record("media")
    assert attempts.exhausted("media")
    assert not attempts.exhausted("clean")


def test_sheet_has_all_four_elements():
    text = FL.render(FL.Failure(step="media", error="exit code 2", attempts=3,
                                artifacts=("X:/run/02_转md",)))
    for label in ("卡在哪步", "报什么错", "试过什么", "产物在哪"):
        assert label in text
    assert "media" in text and "exit code 2" in text


def test_sheet_without_artifacts():
    text = FL.render(FL.Failure(step="fetch", error="timeout", attempts=3))
    assert "（尚无产物）" in text


def test_write_lands_in_workdir(tmp_path):
    path = FL.write(tmp_path, FL.Failure(step="note", error="boom", attempts=3))
    assert path == tmp_path / W.FAILURE_FILE
    assert path.read_text(encoding="utf-8").startswith("# 失败交班单")


def test_clear_removes_a_stale_sheet(tmp_path):
    FL.write(tmp_path, FL.Failure(step="clean", error="boom", attempts=3))
    assert FL.clear(tmp_path) is True
    assert not (tmp_path / W.FAILURE_FILE).exists()


def test_clear_is_a_no_op_when_there_is_none(tmp_path):
    assert FL.clear(tmp_path) is False
    assert not (tmp_path / W.FAILURE_FILE).exists()
