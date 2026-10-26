"""Tests for contract.runner — running a tool and reporting the outcome."""

import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from material_to_notes.contract import runner as R
from material_to_notes.contract import steps as S


class _Fake:
    def __init__(self, returncode=0, stdout="", stderr="", timeout=False):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timeout = timeout

    def __call__(self, argv, **kw):
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        return SimpleNamespace(returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


def test_run_command_ok():
    res = R.run_command(["echo", "hi"], runner=_Fake(stdout="hi"))
    assert res.ok and res.stdout == "hi"


def test_run_command_nonzero_is_not_ok():
    res = R.run_command(["false"], runner=_Fake(returncode=3, stderr="nope"))
    assert not res.ok and res.returncode == 3 and res.stderr == "nope"


def test_run_command_timeout_is_reported():
    res = R.run_command(["sleep"], timeout=1, runner=_Fake(timeout=True))
    assert not res.ok and res.timed_out and "timeout" in res.error


def test_run_command_missing_tool_is_reported():
    def boom(argv, **kw):
        raise FileNotFoundError(argv[0])

    res = R.run_command(["nope"], runner=boom)
    assert not res.ok and "not found" in res.error


def test_child_env_overrides_without_dropping_base():
    env = R.child_env({"A": 1}, base={"A": "0", "B": "keep"})
    assert env["A"] == "1" and env["B"] == "keep"


def test_tool_dir_reads_env():
    assert R.tool_dir("WKC_DIR", {"WKC_DIR": "X:/w"}) == "X:/w"
    assert R.tool_dir("WKC_DIR", {}) == ""


def test_tool_env_adds_repo_root_and_src(tmp_path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    env = R.tool_env(str(tmp_path), base={})
    parts = env["PYTHONPATH"].split(__import__("os").pathsep)
    assert str(tmp_path) in parts
    assert str(tmp_path / "src") in parts


def test_tool_env_skips_missing_src(tmp_path):
    env = R.tool_env(str(tmp_path), base={})
    assert env["PYTHONPATH"] == str(tmp_path)


def test_tool_env_keeps_existing_pythonpath_and_is_never_partial():
    env = R.tool_env("", base={"A": "1", "PYTHONPATH": "keep"})
    assert env["A"] == "1"
    assert env["PYTHONPATH"].endswith("keep")


def test_tool_env_without_tool_path_returns_full_env():
    # The name promised this for a long time without asserting it. `base` used
    # to *replace* the environment rather than add to it, so a caller passing
    # {"MRE_DIR": ...} handed the child nothing else at all -- and on Windows
    # the child lost SYSTEMROOT and died at startup. Assert the promise, not a
    # single key that passes under both readings.
    sentinel = "MTN_CHILD_ENV_SENTINEL"
    os.environ[sentinel] = "keep-me"
    try:
        env = R.tool_env("", base={"PATH": "x"})
        assert env["PATH"] == "x"
        assert env[sentinel] == "keep-me", (
            "tool_env must add to the ambient environment, not replace it"
        )
    finally:
        os.environ.pop(sentinel, None)


@pytest.mark.skipif(os.name != "nt", reason="the failure mode is Windows-only")
def test_tool_env_keeps_systemroot_on_windows():
    # Without SYSTEMROOT CPython cannot finish initialising: it dies with
    # "Fatal Python error: _Py_HashRandomization_Init" and "Python runtime
    # state: preinitialized" before running a line of the tool. 3.11 and newer
    # tolerate its absence, 3.10 does not -- which is why this only ever showed
    # up as one red job out of nine, and never on a developer machine.
    assert os.environ.get("SYSTEMROOT"), "this runner should have SYSTEMROOT"
    env = R.tool_env("", base={})
    assert env.get("SYSTEMROOT") == os.environ["SYSTEMROOT"]


def test_a_child_spawned_through_tool_env_actually_starts(tmp_path):
    # The end-to-end guard for the same bug. Every earlier version of these
    # assertions passed while the child could not start, because they only
    # looked at the dict. This one runs a real interpreter with the env
    # tool_env produced and requires it to reach the last line.
    script = tmp_path / "speak.py"
    script.write_text("print('child-ran-ok')" + chr(10), encoding="utf-8")
    result = R.run_command([sys.executable, str(script)],
                           env=R.tool_env("", base={"MRE_DIR": str(tmp_path)}))
    assert result.ok, f"the child died at startup: {result.error}"
    assert "child-ran-ok" in result.stdout


def test_execute_reports_exit_code(tmp_path):
    out = R.execute(S.get_step("fetch"), ["tool"], tmp_path, runner=_Fake(returncode=2))
    assert not out.ok and "exit code 2" in out.error


def test_execute_error_keeps_the_tool_own_complaint(tmp_path):
    # A hand-off sheet that only says "exit code 1" forces a re-run to learn
    # anything, which defeats its purpose.
    out = R.execute(S.get_step("document"), ["tool"], tmp_path,
                    runner=_Fake(returncode=1, stderr="用法: convert --mode cloud <DayN>"))
    assert "DayN" in out.error and "exit code 1" in out.error


def test_execute_checks_outputs(tmp_path):
    out = R.execute(S.get_step("fetch"), ["tool"], tmp_path, runner=_Fake())
    assert not out.ok and "missing output dir" in out.error


def test_execute_reports_collect_failure(tmp_path):
    def bad_collect():
        raise RuntimeError("boom")

    out = R.execute(S.get_step("fetch"), ["tool"], tmp_path, runner=_Fake(), collect=bad_collect)
    assert not out.ok and "collect failed" in out.error


# --- the command log -------------------------------------------------------
# Logged at this layer, not in the orchestrator: a step can shell out several
# times (document runs plan, convert, enrich) and the orchestrator only sees
# the last result the adapter hands back.

def _logged(tmp_path):
    from material_to_notes.report import logs

    return [entry for entry in logs.read(tmp_path) if "argv" in entry]


def test_execute_logs_the_command_it_ran(tmp_path):
    R.execute(S.get_step("clean"), ["py", "-m", "cleaner.clean_md", "a.md"],
              tmp_path, runner=_Fake(), check_outputs=False)
    entry = _logged(tmp_path)[0]
    assert entry["step"] == "clean"
    assert entry["message"] == "executed" and entry["level"] == "INFO"
    assert entry["argv"] == ["py", "-m", "cleaner.clean_md", "a.md"]


def test_a_failing_command_is_logged_too(tmp_path):
    # The command that failed is the one worth knowing about.
    R.execute(S.get_step("clean"), ["py", "-m", "boom"], tmp_path,
              runner=_Fake(returncode=1), check_outputs=False)
    entry = _logged(tmp_path)[0]
    assert entry["argv"] == ["py", "-m", "boom"]
    assert entry["level"] == "ERROR" and entry["message"] == "command failed"


def test_every_command_of_a_multi_command_step_is_logged(tmp_path):
    R.execute(S.get_step("document"), ["plan"], tmp_path, runner=_Fake(), check_outputs=False)
    R.execute(S.get_step("document"), ["convert"], tmp_path, runner=_Fake(), check_outputs=False)
    R.execute(S.get_step("document"), ["enrich"], tmp_path, runner=_Fake(), check_outputs=False)
    assert [e["argv"][0] for e in _logged(tmp_path)] == ["plan", "convert", "enrich"]


def test_part_tool_defaults_to_the_in_repo_copy():
    # The five parts live in parts/ since 2026-10-15: a fresh checkout must
    # resolve them with no machine-specific path in .env.
    tool = R.part_tool("MRE_DIR", "md-rewrite-engine", env={})
    assert tool.replace("\\", "/").endswith("/parts/md-rewrite-engine")
    assert (R.parts_root(env={}) / "md-rewrite-engine").is_dir()


def test_part_tool_env_override_wins():
    # The per-part env keys stay as an escape hatch (unit tests point at them).
    assert R.part_tool("MRE_DIR", "md-rewrite-engine", env={"MRE_DIR": "X:/mre"}) == "X:/mre"


def test_parts_root_can_be_redirected_for_tests():
    assert R.part_tool(
        "MRE_DIR", "md-rewrite-engine",
        env={"MATERIAL_TO_NOTES_PARTS_DIR": "X:/nowhere"},
    ).replace("\\", "/") == "X:/nowhere/md-rewrite-engine"


def test_child_env_forces_utf8_so_the_gate_report_does_not_crash():
    env = R.tool_env("X:/tool", base={})
    assert env["PYTHONIOENCODING"] == "utf-8"
