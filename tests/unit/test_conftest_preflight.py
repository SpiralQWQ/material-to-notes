"""Tests for tests/conftest.py — the preflight that keeps a fresh clone readable.

The failure this locks down: on a fresh clone the suite used to fail with 39
``FileNotFoundError``s pointing into ``parts/``. Real, but useless — a reader
cannot tell a missing setup step from a broken repo. The preflight turns that
into a skip that names the command, and forces a non-zero exit so a run that
verified nothing is never reported as green.

The realistic regression is not someone deleting the file. It is someone adding
a sixth part to the lock table in ``setup_parts.py`` and forgetting that the
preflight lists the parts by hand. So that list is asserted against the lock
table rather than trusted.
"""

import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

import conftest as C  # noqa: E402
import setup_parts as SP  # noqa: E402


def test_the_preflight_knows_every_part_in_the_lock_table():
    # Adding a part to setup_parts.py without adding it here means a fresh
    # clone skips the new part's tests with a reason that does not mention it.
    locked = {p.name for p in SP.PARTS}
    known = set(C.PARTS)
    assert locked == known, (
        f"parts in the lock table but not the preflight: {sorted(locked - known)}; "
        f"parts in the preflight but not the lock table: {sorted(known - locked)}"
    )


def test_the_preflight_reports_each_missing_part_by_name():
    assert C.MISSING == [n for n in C.PARTS if not (REPO / "parts" / n).is_dir()]


def test_the_preflight_defines_both_hooks():
    # Without the skip hook a fresh clone gets FileNotFoundError; without the
    # session hook the run exits 0 and reads as "all good".
    assert callable(C.pytest_collection_modifyitems)
    assert callable(C.pytest_sessionfinish)


def test_the_session_hook_fails_a_run_that_skipped_everything(monkeypatch):
    # MISSING is computed from the real checkout at import time, so it is set
    # explicitly here — otherwise this test only passes on a clone that happens
    # to be missing its parts, which is the opposite of what it is checking.
    monkeypatch.setattr(C, "MISSING", ["md-rewrite-engine"])

    class FakeSession:
        exitstatus = 0

    session = FakeSession()
    C.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 1, (
        "a run where every test was skipped verified nothing and must not exit 0"
    )


def test_the_session_hook_leaves_a_real_failure_alone(monkeypatch):
    # Only the all-skipped case is rewritten. A run that actually failed must
    # keep the exit code pytest gave it.
    monkeypatch.setattr(C, "MISSING", ["md-rewrite-engine"])

    class FakeSession:
        exitstatus = 1

    session = FakeSession()
    C.pytest_sessionfinish(session, 1)
    assert session.exitstatus == 1


def test_the_session_hook_does_nothing_when_the_parts_are_there(monkeypatch):
    # With the parts present the hook must not touch the exit code at all —
    # rewriting it would mask a genuine green run as a failure.
    monkeypatch.setattr(C, "MISSING", [])

    class FakeSession:
        exitstatus = 0

    session = FakeSession()
    C.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 0


# --- the banner has to survive pytest's capture ----------------------------
#
# The banner used to be a module-level print(). pytest captures stdout for the
# whole session, so it was swallowed: a fresh clone printed nothing but
# `524 skipped` and exit 1, with no hint of what to run. The preflight's whole
# reason to exist is to give a readable reason, so a banner nobody can see is
# the failure mode, not a cosmetic issue.
#
# Testing that `_announce` was *called* would not catch that. This runs pytest
# for real in a checkout with no parts/ and asserts the text reaches stdout.

def test_the_banner_reaches_the_user_on_a_fresh_clone(tmp_path):
    conftest = REPO / "tests" / "conftest.py"
    if not conftest.is_file():  # pragma: no cover
        pytest.skip("no conftest.py beside this test")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text(
        conftest.read_text(encoding="utf-8"), encoding="utf-8")
    # A test that does nothing but exist, so there is something to skip.
    (tmp_path / "tests" / "test_nothing.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8")

    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=str(tmp_path), capture_output=True, text=True,
        encoding="utf-8", errors="replace")

    assert out.returncode == 1, (
        f"a run that skipped everything must not exit 0, got {out.returncode}"
    )
    assert "setup_parts.py" in out.stdout, (
        "the preflight banner must reach stdout under default pytest capture. "
        f"Got instead:\n{out.stdout[:800]}"
    )
    assert "parts/ is incomplete" in out.stdout


def test_no_banner_when_the_parts_are_present(tmp_path):
    # The banner is for a missing setup step. Printing it on a healthy checkout
    # trains people to ignore it.
    parts = tmp_path / "parts"
    parts.mkdir()
    for name in C.PARTS:
        (parts / name).mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text(
        (REPO / "tests" / "conftest.py").read_text(encoding="utf-8"),
        encoding="utf-8")
    (tmp_path / "tests" / "test_nothing.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8")

    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=str(tmp_path), capture_output=True, text=True,
        encoding="utf-8", errors="replace")

    assert out.returncode == 0, out.stdout[-800:]
    assert "parts/ is incomplete" not in out.stdout
