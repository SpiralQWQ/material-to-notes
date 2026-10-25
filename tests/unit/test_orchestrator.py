"""Tests for orchestrate.runner — the serial chain."""

from types import SimpleNamespace

from material_to_notes.orchestrate import runner as OR


def _ok(step, root):
    return SimpleNamespace(ok=True, error="")


def _fail(step, root):
    return SimpleNamespace(ok=False, error=f"{step} boom")


def test_chain_runs_in_order(tmp_path):
    seen = []

    def execute(step, root):
        seen.append(step)
        return _ok(step, root)

    report = OR.run_chain(tmp_path, ("a", "b", "c"), execute=execute)
    assert seen == ["a", "b", "c"]
    assert report.ok
    assert [r.status for r in report.records] == ["done", "done", "done"]


def test_chain_stops_at_first_failure(tmp_path):
    seen = []

    def execute(step, root):
        seen.append(step)
        return _ok(step, root) if step != "b" else _fail(step, root)

    report = OR.run_chain(tmp_path, ("a", "b", "c"), execute=execute, max_attempts=3)
    assert seen == ["a", "b", "b", "b"]
    assert not report.ok and report.stopped_at == "b"
    assert report.status_of("c") == ""


def test_review_rejection_retries_then_stops(tmp_path):
    report = OR.run_chain(tmp_path, ("a",), execute=_ok,
                          review=lambda s, r: (False, "rejected"), max_attempts=2)
    assert not report.ok
    assert report.records[0].attempts == 2
    assert "rejected" in report.records[0].error


def test_review_approval_marks_done(tmp_path):
    marked = []
    report = OR.run_chain(tmp_path, ("a",), execute=_ok,
                          review=lambda s, r: (True, ""), mark_done=marked.append)
    assert report.ok and marked == ["a"]


def test_is_done_skips_finished_steps(tmp_path):
    report = OR.run_chain(tmp_path, ("a", "b"), execute=_ok, is_done=lambda s: s == "a")
    assert [r.status for r in report.records] == ["skipped", "done"]


def test_progress_callback_fires(tmp_path):
    events = []
    OR.run_chain(tmp_path, ("a",), execute=_ok, on_progress=lambda s, st: events.append((s, st)))
    assert events == [("a", "done")]


def test_execute_crash_is_recorded_not_raised(tmp_path):
    def boom(step, root):
        raise RuntimeError("kaboom")

    report = OR.run_chain(tmp_path, ("a",), execute=boom, max_attempts=2)
    assert not report.ok
    assert report.records[0].status == "failed"
    assert "kaboom" in report.records[0].error


def test_review_crash_retries_then_stops(tmp_path):
    def boom_review(step, root):
        raise RuntimeError("reviewer down")

    report = OR.run_chain(tmp_path, ("a",), execute=_ok, review=boom_review, max_attempts=2)
    assert not report.ok and "review crashed" in report.records[0].error

