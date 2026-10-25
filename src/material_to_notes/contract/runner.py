"""Run an external tool and turn the outcome into a structured result.

A failing tool is reported, never raised: the pipeline must be able to say
"this step failed, here is why" without blowing up.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from material_to_notes.contract import validate as _validate


@dataclass(frozen=True)
class RunResult:
    argv: tuple
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.error


@dataclass(frozen=True)
class StepOutcome:
    step: str
    ok: bool
    run: RunResult
    error: str = ""


def abspath(target) -> str:
    """Absolute path string — adapters run tools with cwd set to the tool repo,
    so any path we hand over must be absolute or it resolves somewhere else."""
    return str(Path(os.fspath(target)).resolve())


def tool_dir(env_key: str, env=None, default: str = "") -> str:
    """Location of an external tool, read from the given env (or os.environ)."""
    source = os.environ if env is None else env
    return source.get(env_key) or default


# The five parts live in ``parts/`` inside this repo since 2026-10-15, so a
# fresh checkout runs without any machine-specific path in .env. The per-part
# env keys stay as an escape hatch (and are what the unit tests point at).
PARTS_ENV_KEY = "MATERIAL_TO_NOTES_PARTS_DIR"
_PARTS_DIRNAME = "parts"


def parts_root(env=None) -> Path:
    """Where the in-repo part copies live: ``<repo>/parts`` unless overridden."""
    source = os.environ if env is None else env
    override = source.get(PARTS_ENV_KEY)
    if override:
        return Path(override)
    # src/material_to_notes/contract/runner.py -> parents[3] is the repo root.
    return Path(__file__).resolve().parents[3] / _PARTS_DIRNAME


def part_dir(name: str, env=None) -> str:
    """Directory of one in-repo part copy, e.g. ``part_dir("md-rewrite-engine")``."""
    return os.fspath(parts_root(env) / name)


def part_tool(env_key: str, part: str, env=None) -> str:
    """Where a step runs a part from: an env override wins, else ``parts/<part>``.

    The override exists for testing and for the (now unusual) case of running
    against a part checkout outside this repo.
    """
    source = os.environ if env is None else env
    return source.get(env_key) or part_dir(part, env)


def child_env(overrides=None, base=None) -> dict:
    """Environment for a child process: the current env plus overrides."""
    env = dict(os.environ if base is None else base)
    if overrides:
        env.update({k: str(v) for k, v in overrides.items()})
    return env


def tool_env(tool_path, base=None, extra=None) -> dict:
    """Full child env with the tool's own import dirs on PYTHONPATH.

    Flat repos expose their packages at the repo root; src-layout repos at
    ``<repo>/src``. Setting cwd alone is not enough for ``python -m <pkg>`` in
    the src-layout case unless the tool happens to be installed already, so we
    always add both. Returns the complete environment, never a partial one.
    """
    env = child_env(extra, base=base)
    paths = []
    root = os.fspath(tool_path) if tool_path else ""
    if root:
        paths.append(root)
        src = os.path.join(root, "src")
        if os.path.isdir(src):
            paths.append(src)
    existing = env.get("PYTHONPATH", "")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    # Windows consoles fall back to a legacy codepage, and mre's gate prints an
    # emoji in its report — without this the child dies with UnicodeEncodeError
    # and a perfectly good gate looks broken (scripts/gate_check.py's own docs
    # carry the same rule).
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_command(argv, *, cwd=None, env=None, timeout=None, encoding="utf-8", runner=None) -> RunResult:
    """Run argv; report failure instead of raising."""
    argv = tuple(str(a) for a in argv)
    invoke = runner or subprocess.run
    try:
        proc = invoke(
            list(argv), cwd=cwd, env=env, timeout=timeout,
            capture_output=True, text=True, encoding=encoding, errors="replace",
        )
    except subprocess.TimeoutExpired:
        return RunResult(argv, -1, timed_out=True, error=f"timeout after {timeout}s")
    except FileNotFoundError:
        return RunResult(argv, -1, error=f"tool not found: {argv[0]}")
    except OSError as exc:
        return RunResult(argv, -1, error=f"cannot run tool: {exc}")
    return RunResult(argv, proc.returncode, proc.stdout or "", proc.stderr or "")


def _failure_note(result: RunResult, limit: int = 400) -> str:
    """A one-line diagnosis that keeps the tool's own complaint.

    "exit code 1" alone is useless on a hand-off sheet — the human would have to
    re-run the step to learn anything, which defeats the point of the sheet.
    """
    tail = (result.stderr or result.stdout or "").strip().replace("\n", " ")
    if len(tail) > limit:
        tail = "…" + tail[-limit:]
    return f"exit code {result.returncode}: {tail}" if tail else f"exit code {result.returncode}"


def _log_command(step, root, result) -> None:
    """Record the command that ran, at the moment it ran.

    Logged here rather than in the orchestrator on purpose: one step can shell
    out more than once — document runs plan, then convert, then enrich — and the
    orchestrator only ever sees the last result the adapter returns. This layer
    sees every command, so the interface spec can be written from all of them.

    The import is local because the report layer sits above this one; importing
    it at module scope would invert the package's stated layering.
    """
    from material_to_notes.report import logs

    logs.record(root, step=step.id, level="info" if result.ok else "error",
                message="executed" if result.ok else "command failed", argv=result.argv)


def execute(step, argv, root, *, cwd=None, env=None, timeout=None, runner=None,
            collect=None, check_outputs=True) -> StepOutcome:
    """Run one step's command, then check its declared outputs against the contract.

    ``collect`` (optional) runs after a successful process and before the output
    check — used by adapters whose tool writes somewhere other than the step dir.
    """
    result = run_command(argv, cwd=cwd, env=env, timeout=timeout, runner=runner)
    _log_command(step, root, result)
    if not result.ok:
        return StepOutcome(step.id, False, result, error=result.error or _failure_note(result))
    if collect is not None:
        try:
            collect()
        except Exception as exc:  # noqa: BLE001 - collect is caller-supplied
            return StepOutcome(step.id, False, result, error=f"collect failed: {exc}")
    if check_outputs:
        try:
            _validate.check_step_output(root, step)
        except _validate.ContractError as exc:
            return StepOutcome(step.id, False, result, error=str(exc))
    return StepOutcome(step.id, True, result)
