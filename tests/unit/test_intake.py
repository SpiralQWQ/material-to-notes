"""Tests for the intake sheet, per-source naming, multi-source steps and delivery.

The user's requirement, in their words: when several materials are dropped in,
ask once (a name, where the notes go, who they are for), keep the answers, reuse
them — and keep metadata in its own folder, never mixed with the notes.
"""

import json

from material_to_notes.cli import main as CLI
from material_to_notes.contract import metadata as MD
from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate import pipeline as PL


def _doc(root, name):
    d = root / "02_转md" / f"{name}_mineru"
    d.mkdir(parents=True, exist_ok=True)
    (d / "full.md").write_text("x", encoding="utf-8")


# --- the layout -------------------------------------------------------------

def test_metadata_has_its_own_folder():
    assert W.META_DIR in W.subdirs()
    assert W.meta_dir("X:/run").name == W.META_DIR


def test_source_name_reduces_a_document_path():
    assert W.source_name("02_转md/C2021_mineru/full.md") == "C2021"


def test_source_name_reduces_a_media_path():
    assert W.source_name("02_转md/lecture_clean.md") == "lecture"


def test_source_name_falls_back_to_the_stem():
    assert W.source_name("some/odd/file.txt") == "file"


# --- the intake sheet -------------------------------------------------------

def test_sheet_defaults_need_no_answers(tmp_path):
    # Dropping files in and saying nothing must still work.
    sheet = MD.load_sheet(tmp_path)
    assert sheet["audience"] == MD.DEFAULT_AUDIENCE
    assert sheet["deliver_dir"] == ""
    assert sheet["names"] == {}


def test_sheet_round_trips(tmp_path):
    MD.save_sheet(tmp_path, audience="复习资料", deliver_dir="X:/notes",
                  names={"paper": "我的论文"})
    sheet = MD.load_sheet(tmp_path)
    assert sheet["audience"] == "复习资料"
    assert sheet["deliver_dir"] == "X:/notes"
    assert sheet["names"] == {"paper": "我的论文"}


def test_sheet_rejects_unknown_fields(tmp_path):
    import pytest

    with pytest.raises(KeyError):
        MD.save_sheet(tmp_path, nope="x")


def test_a_corrupt_sheet_falls_back_to_defaults(tmp_path):
    MD.sheet_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    MD.sheet_path(tmp_path).write_text("{ not json", encoding="utf-8")
    assert MD.load_sheet(tmp_path)["audience"] == MD.DEFAULT_AUDIENCE


def test_name_for_uses_the_override_then_the_source_name(tmp_path):
    sheet = {"names": {"paper": "我的论文"}}
    assert MD.name_for(sheet, "paper", "paper") == "我的论文"
    assert MD.name_for(sheet, "other", "other") == "other"


def test_name_for_sanitises_the_override(tmp_path):
    sheet = {"names": {"p": 'a/b:c*d?'}}
    assert "/" not in MD.name_for(sheet, "p", "p")


def test_intake_cli_writes_and_shows_the_sheet(tmp_path, capsys):
    assert CLI.main(["intake", str(tmp_path), "--audience", "复习资料"]) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert "复习资料" in out and "投料单" in out
    assert json.loads(MD.sheet_path(tmp_path).read_text(encoding="utf-8"))["audience"] == "复习资料"


def test_intake_cli_renames_a_material(tmp_path, capsys):
    assert CLI.main(["intake", str(tmp_path), "--name", "paper=我的论文"]) == CLI.EXIT_OK
    capsys.readouterr()
    assert MD.load_sheet(tmp_path)["names"] == {"paper": "我的论文"}


def test_intake_cli_rejects_a_malformed_rename(tmp_path, capsys):
    assert CLI.main(["intake", str(tmp_path), "--name", "没等号"]) == CLI.EXIT_NEEDS_USER
    assert "素材名" in capsys.readouterr().out


def test_intake_with_no_flags_only_shows(tmp_path, capsys):
    CLI.main(["intake", str(tmp_path)])
    capsys.readouterr()
    assert not MD.sheet_path(tmp_path).is_file()   # asking is not answering


# --- per-source naming through the relay ------------------------------------

def test_source_names_defaults_to_the_materials_own_name(tmp_path):
    _doc(tmp_path, "paper")
    _doc(tmp_path, "essay")
    pairs = PL.source_names(tmp_path, "clean")
    assert sorted(name for _p, name in pairs) == ["essay", "paper"]


def test_source_names_honours_an_intake_rename(tmp_path):
    _doc(tmp_path, "paper")
    MD.save_sheet(tmp_path, names={"paper": "我的论文"})
    assert PL.source_names(tmp_path, "clean") == ((tmp_path / "02_转md" / "paper_mineru" / "full.md",
                                                   "我的论文"),)


# --- multi-source steps -----------------------------------------------------

def test_clean_runs_once_per_source(tmp_path, monkeypatch):
    calls = []
    from material_to_notes.steps import clean as clean_step

    def fake_run(root, *, src_file, **kw):
        calls.append(W.source_name(src_file))
        from material_to_notes.orchestrate.runner import Outcome
        return Outcome(True)

    monkeypatch.setattr(clean_step, "run", fake_run)
    _doc(tmp_path, "paper")
    _doc(tmp_path, "essay")
    # The relay refuses leftovers from a producer that never recorded success.
    from material_to_notes.orchestrate import workspace

    workspace.save(tmp_path, {"version": 1, "steps": {"document": {"status": "done", "fp": "x"}}})

    outcome = PL.default_executors({})["clean"](tmp_path)
    assert outcome.ok
    assert sorted(calls) == ["essay", "paper"]


def test_a_name_collision_stops_the_note_step(tmp_path, monkeypatch):
    # Intermediates are keyed by the source name (unique by construction), so a
    # collision can only happen on the deliverables — two materials resolving to
    # one note file would overwrite each other.
    from material_to_notes.steps import note as note_step

    monkeypatch.setattr(note_step, "run", lambda *a, **k: None)
    cleaned = tmp_path / "03_清洗"
    cleaned.mkdir(parents=True, exist_ok=True)
    (cleaned / "paper.txt").write_text("x", encoding="utf-8")
    (cleaned / "essay.txt").write_text("x", encoding="utf-8")
    (tmp_path / "_state").mkdir(exist_ok=True)
    from material_to_notes.orchestrate import workspace

    workspace.save(tmp_path, {"version": 1, "steps": {"clean": {"status": "done", "fp": "x"}}})
    MD.save_sheet(tmp_path, names={"paper": "同一个", "essay": "同一个"})

    outcome = PL.default_executors({})["note"](tmp_path)
    assert not outcome.ok and "同一个" in outcome.error


# --- delivery ---------------------------------------------------------------

def test_deliver_copies_the_notes_to_the_chosen_folder(tmp_path):
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "paper.md").write_text("笔记", encoding="utf-8")
    dest = tmp_path / "交付"
    MD.save_sheet(tmp_path, deliver_dir=str(dest))

    assert CLI.main(["deliver", str(tmp_path)]) == CLI.EXIT_OK
    assert (dest / "paper.md").read_text(encoding="utf-8") == "笔记"
    # A copy, never a move — the workdir keeps its own record.
    assert (notes / "paper.md").is_file()


def test_deliver_says_so_when_the_sheet_names_no_folder(tmp_path, capsys):
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "paper.md").write_text("笔记", encoding="utf-8")
    assert CLI.main(["deliver", str(tmp_path)]) == CLI.EXIT_OK
    assert "就地" in capsys.readouterr().out


def test_deliver_without_notes_asks_the_user(tmp_path):
    assert CLI.main(["deliver", str(tmp_path)]) == CLI.EXIT_NEEDS_USER


# --- the per-source record --------------------------------------------------

def test_record_step_accumulates_one_entry_per_step(tmp_path):
    MD.record_step(tmp_path, "paper", "clean", ok=True, stats={"raw_len": 10})
    MD.record_step(tmp_path, "paper", "note", ok=True, outputs=["04_笔记/paper.md"])
    record = MD.load_record(tmp_path, "paper")
    assert set(record["steps"]) == {"clean", "note"}
    assert record["steps"]["clean"]["stats"] == {"raw_len": 10}


def test_records_for_different_sources_do_not_share_a_file(tmp_path):
    MD.record_step(tmp_path, "a", "clean", ok=True)
    MD.record_step(tmp_path, "b", "clean", ok=True)
    assert MD.record_path(tmp_path, "a") != MD.record_path(tmp_path, "b")
    assert MD.load_record(tmp_path, "a")["name"] == "a"


# --- rename flows into the deliverable, not the intermediate ----------------

def test_a_rename_changes_the_note_name_not_the_intermediate(tmp_path):
    # Intermediates stay keyed by the source, so a rename never leaves a second
    # cleaned file behind (which the next step would read as a second material).
    cleaned = tmp_path / "03_清洗"
    cleaned.mkdir(parents=True)
    (cleaned / "paper.txt").write_text("x", encoding="utf-8")
    MD.save_sheet(tmp_path, names={"paper": "我的论文"})

    from material_to_notes.gates import content as C

    assert C.note_targets(tmp_path) == {"我的论文.md": cleaned / "paper.txt"}


def test_an_orphan_note_is_reported_not_silently_checked(tmp_path):
    # Usually a rename's leftover: it maps to no material, so there is no honest
    # baseline to check it against.
    cleaned = tmp_path / "03_清洗"
    cleaned.mkdir(parents=True)
    (cleaned / "paper.txt").write_text("x", encoding="utf-8")
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "纸.md").write_text("旧的", encoding="utf-8")

    from material_to_notes.gates import content as C

    assert C._stale_notes(tmp_path, C.note_targets(tmp_path)) == ["纸.md"]
