"""End-to-end closed loops with mock tools (T21-T26).

The real tools need the local environment (five repos, model keys). These tests
exercise the wiring that surrounds them: the relay, resume, failure hand-off,
and idempotency. Real runs are on the manual checklist.
"""

from pathlib import Path

from _mocks import DOC_SPEC, FETCH_DOC_SPEC, FETCH_MEDIA_SPEC, MEDIA_SPEC
from _mocks import executors as _executors
from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate import pipeline as PL
from material_to_notes.report import logs as _logs

# --- T21 video line --------------------------------------------------------

def test_video_line_end_to_end(tmp_path):
    result = PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC))
    assert result["report"].ok
    assert (tmp_path / "04_笔记" / "note.md").is_file()
    assert (tmp_path / W.PROGRESS_FILE).is_file()
    assert [r.step for r in result["report"].records] == ["media", "clean", "note"]


# --- T22 document line -----------------------------------------------------

def test_document_line_end_to_end(tmp_path):
    result = PL.run(tmp_path, "a.pdf", executors=_executors(DOC_SPEC))
    assert result["report"].ok
    assert (tmp_path / "04_笔记" / "note.md").is_file()


# --- T23 fetch line --------------------------------------------------------

def test_fetch_line_continues_into_media(tmp_path):
    result = PL.run(tmp_path, "https://x/v", executors=_executors(FETCH_MEDIA_SPEC))
    assert result["report"].ok
    assert [r.step for r in result["report"].records] == ["fetch", "media", "clean", "note"]


def test_fetch_line_continues_into_document(tmp_path):
    result = PL.run(tmp_path, "python 入门", kind="terms", executors=_executors(FETCH_DOC_SPEC))
    assert result["report"].ok
    assert [r.step for r in result["report"].records] == ["fetch", "document", "clean", "note"]


def test_bare_term_without_kind_asks_user(tmp_path):
    # A bare word is indistinguishable from an unknown path — never guess.
    assert PL.run(tmp_path, "python 入门", executors=_executors({}))["asked_user"]


def test_fetch_with_nothing_usable_asks_user(tmp_path):
    result = PL.run(tmp_path, "https://x/v", executors=_executors({"fetch": ("01_取材", "meta.json")}))
    assert result["asked_user"]
    assert not (tmp_path / W.FAILURE_FILE).exists()   # nothing failed; we just need the user


# --- unknown input ---------------------------------------------------------

def test_unknown_input_asks_user(tmp_path):
    result = PL.run(tmp_path, "a.exe", executors=_executors({}))
    assert result["asked_user"] and result["report"] is None


# --- T24 resume ------------------------------------------------------------

def test_resume_skips_finished_steps(tmp_path):
    execs = _executors(MEDIA_SPEC)
    assert PL.run(tmp_path, "v.mp4", executors=execs)["report"].ok
    second = PL.run(tmp_path, "v.mp4", executors=execs)["report"]
    assert [r.status for r in second.records] == ["skipped", "skipped", "skipped"]


def test_changed_input_reruns_step(tmp_path):
    execs = _executors(MEDIA_SPEC)
    PL.run(tmp_path, "v.mp4", executors=execs)
    (tmp_path / "02_转md" / "v_clean.md").write_text("changed", encoding="utf-8")
    second = PL.run(tmp_path, "v.mp4", executors=execs)["report"]
    assert second.records[0].status == "skipped"          # media: target unchanged
    assert second.status_of("note") in ("done", "skipped")


# --- T25 failure hand-off --------------------------------------------------

def test_failure_writes_handoff_sheet(tmp_path):
    result = PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC, fail=("clean",)), max_attempts=3)
    assert not result["report"].ok and result["report"].stopped_at == "clean"
    sheet = (tmp_path / W.FAILURE_FILE).read_text(encoding="utf-8")
    for label in ("卡在哪步", "报什么错", "试过什么", "产物在哪"):
        assert label in sheet
    assert result["report"].records[-1].attempts == 3


def test_failure_stops_before_later_steps(tmp_path):
    result = PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC, fail=("clean",)))
    assert result["report"].status_of("note") == ""


def test_a_successful_rerun_clears_the_stale_handoff_sheet(tmp_path):
    # A real run left 失败单.md saying "clean failed" next to a 进度单.md saying
    # "clean 完成" — two sheets contradicting each other in the same workdir.
    PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC, fail=("clean",)), max_attempts=1)
    assert (tmp_path / W.FAILURE_FILE).is_file()

    result = PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC))
    assert result["report"].ok
    assert not (tmp_path / W.FAILURE_FILE).exists()
    assert (tmp_path / W.PROGRESS_FILE).is_file()


def test_a_still_failing_rerun_keeps_the_handoff_sheet(tmp_path):
    execs = _executors(MEDIA_SPEC, fail=("clean",))
    PL.run(tmp_path, "v.mp4", executors=execs, max_attempts=1)
    PL.run(tmp_path, "v.mp4", executors=execs, max_attempts=1)
    assert (tmp_path / W.FAILURE_FILE).is_file()



# --- T26 idempotency -------------------------------------------------------

def test_rerun_skips_everything_and_keeps_artifacts(tmp_path):
    execs = _executors(MEDIA_SPEC)
    PL.run(tmp_path, "v.mp4", executors=execs)
    before = (tmp_path / "04_笔记" / "note.md").read_text(encoding="utf-8")
    second = PL.run(tmp_path, "v.mp4", executors=execs)
    assert [r.status for r in second["report"].records] == ["skipped"] * 3
    assert (tmp_path / "04_笔记" / "note.md").read_text(encoding="utf-8") == before


def test_progress_sheet_matches_disk(tmp_path):
    from material_to_notes.report import progress as P

    result = PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC))
    assert P.inconsistent(result["report"].records, tmp_path) == ()


def test_run_is_logged(tmp_path):
    PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC))
    steps = [entry["step"] for entry in _logs.read(tmp_path)]
    assert steps == ["media", "clean", "note"]


def test_step_mode_sheet_keeps_the_steps_that_already_ran(tmp_path):
    # `material-to-notes step` is the main path now (one sub-agent per step). Building
    # the sheet from that run alone would erase the steps before it: the sheet
    # showed one row while two steps were actually done.
    execs = _executors(DOC_SPEC)
    PL.step(tmp_path, "document", executors=execs)
    PL.step(tmp_path, "clean", executors=execs)
    sheet = (tmp_path / W.PROGRESS_FILE).read_text(encoding="utf-8")
    assert "| document | 完成 |" in sheet
    assert "| clean | 完成 |" in sheet
    assert sheet.index("| document |") < sheet.index("| clean |")


def _counting_executors(spec, calls):
    """The mock executors, plus a note of every step that actually ran."""
    execs = _executors(spec)

    def wrap(step_id):
        def run(root):
            calls.append(step_id)
            return execs[step_id](root)
        return run

    return {step_id: wrap(step_id) for step_id in execs}


def test_step_skips_a_step_already_done(tmp_path):
    calls = []
    execs = _counting_executors(DOC_SPEC, calls)
    PL.step(tmp_path, "document", executors=execs)
    PL.step(tmp_path, "clean", executors=execs)
    assert calls.count("clean") == 1
    PL.step(tmp_path, "clean", executors=execs)
    assert calls.count("clean") == 1          # resumed, not re-run


def test_step_force_reruns_a_step_that_resume_would_skip(tmp_path):
    # The real need: a step's *code* changed but its input fingerprint did not,
    # so resume cannot tell it needs redoing. Two runs this session hit this.
    calls = []
    execs = _counting_executors(DOC_SPEC, calls)
    PL.step(tmp_path, "document", executors=execs)
    PL.step(tmp_path, "clean", executors=execs)
    PL.step(tmp_path, "clean", executors=execs, force=True)
    assert calls.count("clean") == 2


def test_run_force_reruns_the_whole_chain(tmp_path):
    calls = []
    execs = _counting_executors(MEDIA_SPEC, calls)
    PL.run(tmp_path, "v.mp4", executors=execs)
    assert calls == ["media", "clean", "note"]
    PL.run(tmp_path, "v.mp4", executors=execs, force=True)
    assert calls == ["media", "clean", "note"] * 2





def test_the_command_that_ran_is_logged(tmp_path):
    # The interface spec gets written from measured argv, not from what the
    # adapter claims it would build. The entry is written by
    # contract.runner.execute — the only layer that sees every command a step
    # runs (document shells out three times; the orchestrator sees one result).
    from types import SimpleNamespace

    from material_to_notes.steps import clean

    src = tmp_path / "a.md"
    src.write_text("# 标题\n", encoding="utf-8")

    class Writing:
        def __call__(self, argv, **kw):
            out = Path(argv[argv.index("--output") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("# 标题\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")

    clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"}, runner=Writing())
    logged = [e["argv"] for e in _logs.read(tmp_path) if "argv" in e]
    assert len(logged) == 1
    assert logged[0][1:3] == ["-m", "cleaner.clean_md"]
    assert logged[0][-1] == "--watermark-only"


def test_a_step_that_never_shelled_out_logs_no_command(tmp_path):
    # The chain-level mocks write files without running anything; the log must
    # not invent a command for them.
    PL.run(tmp_path, "v.mp4", executors=_executors(MEDIA_SPEC))
    assert not [e for e in _logs.read(tmp_path) if "argv" in e]


