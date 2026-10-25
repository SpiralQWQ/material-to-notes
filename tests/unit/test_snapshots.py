"""Tests for report.snapshots — keeping the previous output so a revision is diffable."""

from material_to_notes.orchestrate import pipeline as PL
from material_to_notes.report import snapshots as S


def _note(root, text="第一版"):
    base = root / "04_笔记"
    base.mkdir(parents=True, exist_ok=True)
    (base / "note.md").write_text(text, encoding="utf-8")


def test_nothing_to_keep_on_the_first_dispatch(tmp_path):
    # An empty snapshot would suggest a revision happened when none did.
    assert S.take(tmp_path, "note") is None
    assert S.listing(tmp_path, "note") == ()


def test_take_copies_the_current_output_aside(tmp_path):
    _note(tmp_path, "原版")
    taken = S.take(tmp_path, "note")
    assert taken is not None and (taken / "note.md").read_text(encoding="utf-8") == "原版"
    # The live file is untouched by the snapshot.
    assert (tmp_path / "04_笔记" / "note.md").read_text(encoding="utf-8") == "原版"


def test_a_revision_becomes_diffable(tmp_path):
    _note(tmp_path, "第一版")
    S.take(tmp_path, "note")
    _note(tmp_path, "第二版：改了两处")
    versions = S.listing(tmp_path, "note")
    assert len(versions) == 1
    assert (versions[0] / "note.md").read_text(encoding="utf-8") == "第一版"
    assert (tmp_path / "04_笔记" / "note.md").read_text(encoding="utf-8") == "第二版：改了两处"


def test_two_snapshots_in_one_second_do_not_collide(tmp_path):
    import datetime

    _note(tmp_path, "一")
    S.take(tmp_path, "note", now=datetime.datetime(2026, 10, 13, 12, 0, 0))
    _note(tmp_path, "二")
    S.take(tmp_path, "note", now=datetime.datetime(2026, 10, 13, 12, 0, 0))
    assert len(S.listing(tmp_path, "note")) == 2


def test_snapshots_stay_inside_the_workdir(tmp_path):
    _note(tmp_path)
    taken = S.take(tmp_path, "note")
    assert taken.is_relative_to(tmp_path / "_state")
    assert S.relpath(tmp_path, taken).startswith("_state/")


def test_dispatching_takes_a_snapshot_before_the_agent_overwrites(tmp_path):
    # `material-to-notes assign` is the dispatch point: the last moment the old version
    # exists. Without this, a revision round cannot be checked by diff at all.
    from material_to_notes.cli import main as CLI

    _note(tmp_path, "写好的第一版")
    assert CLI.main(["assign", str(tmp_path), "note"]) == CLI.EXIT_OK
    versions = S.listing(tmp_path, "note")
    assert len(versions) == 1
    assert (versions[0] / "note.md").read_text(encoding="utf-8") == "写好的第一版"


def test_assign_on_a_fresh_step_still_returns_a_sheet(tmp_path, capsys):
    from material_to_notes.cli import main as CLI

    assert CLI.main(["assign", str(tmp_path), "note"]) == CLI.EXIT_OK
    assert "任务单" in capsys.readouterr().out
    assert S.listing(tmp_path, "note") == ()


def test_snapshots_subcommand_lists_them(tmp_path, capsys):
    from material_to_notes.cli import main as CLI

    _note(tmp_path, "一")
    CLI.main(["assign", str(tmp_path), "note"])
    capsys.readouterr()
    assert CLI.main(["snapshots", str(tmp_path), "note"]) == CLI.EXIT_OK
    assert "_state/快照/note/" in capsys.readouterr().out


def test_snapshots_subcommand_reports_an_empty_history(tmp_path, capsys):
    from material_to_notes.cli import main as CLI

    assert CLI.main(["snapshots", str(tmp_path), "note"]) == CLI.EXIT_OK
    assert "没有留底" in capsys.readouterr().out


def test_running_a_step_also_snapshots_the_previous_output(tmp_path):
    from _mocks import MEDIA_SPEC
    from _mocks import executors as _executors

    _note(tmp_path, "上一轮的笔记")
    PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC))
    versions = S.listing(tmp_path, "note")
    assert len(versions) == 1
    assert (versions[0] / "note.md").read_text(encoding="utf-8") == "上一轮的笔记"
