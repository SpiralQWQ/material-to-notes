"""Tests for .github/workflows/ci.yml — the guard that guarded nothing.

The bug this pins: a step meant to tolerate either exit code was written as

    python scripts/setup_engines.py --check || code=$?
    if [ "$code" != "0" ] && [ "$code" != "1" ]; then ... exit 1; fi

``--check`` is report-only and exits 0 on a healthy *and* on an empty checkout.
When it succeeds the ``||`` short-circuits, ``code`` is never assigned, and
``[ "" != "0" ]`` is true — so the step exited 1 precisely when everything was
fine. A guard that fails on success is worse than no guard, because the next
person to see red will assume the repo is broken.

These tests read the workflow as data rather than re-running it, so they catch
the same class of mistake without needing a CI run to notice.
"""

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
CI = REPO / ".github" / "workflows" / "ci.yml"

yaml = pytest.importorskip("yaml")


def _load():
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _steps(job):
    return _load()["jobs"][job]["steps"]


def test_the_workflow_is_valid_yaml():
    # A syntax error here takes the whole repo's CI down, and nothing else in
    # the suite would notice.
    assert _load()["jobs"], "ci.yml must define at least one job"


def test_the_test_job_fetches_the_parts_before_running_them():
    # The suite reads note_style_spec.yaml and the gate labels out of
    # md-rewrite-engine. Without the parts it fails with FileNotFoundError;
    # conftest.py turns that into a skip locally, and a CI that skipped
    # everything would be worse than no CI.
    names = [s.get("run", "") or "" for s in _steps("test")]
    fetch = next(i for i, r in enumerate(names)
                 if "setup_parts.py" in r and "--check" not in r)
    # Match the run, not the install line: `pip install pytest` also contains
    # "pytest" and sits earlier in the job, which would make this assertion
    # fail for the wrong reason.
    run = next(i for i, r in enumerate(names) if "-m pytest" in r)
    assert fetch < run, "the parts must be fetched before the suite runs"


def test_no_step_guards_on_an_unset_variable():
    # The exact shape that failed on success: capture `$?` only in the failure
    # branch, then compare the never-assigned variable against 0.
    for job, spec in _load()["jobs"].items():
        for step in spec["steps"]:
            run = step.get("run", "") or ""
            assert "|| code=$?" not in run, (
                f"job {job!r} step {step.get('name')!r} captures $? only on "
                "failure and then compares the empty variable — it will fail "
                "on success"
            )


def test_the_check_step_lets_a_report_only_script_exit_zero():
    # --check installs nothing and reports; it exits 0 on both a healthy and an
    # empty checkout. Wrapping it in a tolerance check can only invent failures.
    for step in _steps("setup-scripts"):
        run = step.get("run", "") or ""
        if "--check" in run:
            assert "if [" not in run, (
                "a report-only --check must not be wrapped in an exit-code "
                "tolerance check"
            )
            assert "||" not in run, "same reason: it cannot fail by design"


def test_ci_does_not_install_the_engines():
    # torch/funasr/opencv/crawl4ai/spacy are what make a full install 5-8 GB.
    # The suite reads the parts' files, it does not import them, so CI stays at
    # roughly a minute. If someone "helpfully" adds them here, CI goes from one
    # minute to twenty and nobody will run it.
    installs = [s.get("run", "") for s in _steps("test")
                if "pip install" in (s.get("run", "") or "")]
    assert installs, "the test job must install its test dependencies"
    for line in installs:
        for heavy in ("torch", "funasr", "opencv", "crawl4ai", "spacy",
                      "presidio", "mineru"):
            assert heavy not in line, (
                f"CI installs {heavy}; the suite does not import the engines"
            )
