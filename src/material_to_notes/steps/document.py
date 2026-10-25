"""Adapter for dtmd (document-to-markdown): PDF / Word / PPT / HTML to markdown.

The document line has four phases, all inside dtmd:

    python -m dtmd plan <dir>              # scan, write plan.json
    python -m dtmd convert --mode cloud 1  # per-day; mirrors into DTM_OUTPUT_ROOT
    python -m dtmd merge <mineru_dir>      # only for a book sliced into blocks
    <repo>/scripts/enrich_subset.py <mineru_dir>   # figure notes -> embed into full.md

The third one matters because dtmd slices any document over MinerU's 200-page
per-file limit into ``p{start}-{end}/`` blocks, and ``convert`` does not stitch
them back: without merge there is no ``full.md`` at the dir root, so enrich finds
nothing and a book silently loses every figure note.

The last one is the step the first real run proved we were missing: MinerU
leaves illustrations in ``images/`` and full.md keeps only dead ``![](…)``
references, so every figure's content is invisible to the note. It calls dtmd's
own functions against only the referenced images, so dtmd stays untouched.

``embed_notes`` overwrites full.md in place, so we snapshot it first — the
project never destroys an original. Default mode is ``cloud``: this deployment
has no MinerU install.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

from material_to_notes.contract import runner as R
from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as W

TOOL = "dtmd"
ENV_KEY = "DTMD_DIR"
PART = "document-to-markdown"
MODULE = "dtmd"
MODES = ("local", "cloud")
DEFAULT_MODE = "cloud"
BACKUP_SUFFIX = ".bak"
MINERU_DIR_SUFFIX = "_mineru"


def build_plan_command(src_dir, *, python=None) -> list:
    return [python or sys.executable, "-m", MODULE, "plan", R.abspath(src_dir)]


def build_convert_command(*, mode=DEFAULT_MODE, day=1, python=None) -> list:
    if mode not in MODES:
        raise ValueError(f"unknown dtmd mode: {mode!r} (expected one of {MODES})")
    day = int(day)
    if day < 1:
        raise ValueError(f"dtmd day must be >= 1, got {day}")
    return [python or sys.executable, "-m", MODULE, "convert", "--mode", mode, str(day)]


def build_merge_command(mineru_dir, *, python=None) -> list:
    """Stitch a sliced book's blocks back into one full.md at the dir root.

    Only run when ``has_slices`` says so: dtmd's merge exits 1 when there is
    nothing to merge ("无事发生也提示用户"), which would fail every ordinary
    single-block document.
    """
    return [python or sys.executable, "-m", MODULE, "merge", R.abspath(mineru_dir)]


SLICE_DIR_RE = re.compile(r"^p\d+-\d+$")


def has_slices(mineru_dir) -> bool:
    """Whether dtmd wrote ``p{start}-{end}/`` blocks here (a book over 200 pages)."""
    base = Path(mineru_dir)
    if not base.is_dir():
        return False
    return any(p.is_dir() and SLICE_DIR_RE.match(p.name) and (p / "full.md").is_file()
               for p in base.iterdir())


def build_enrich_command(mineru_dir, *, glm=True, python=None) -> list:
    python = python or sys.executable
    argv = [python, str(_subset_script()), R.abspath(mineru_dir)]
    if not glm:
        argv.append("--no-glm")
    return argv


def _subset_script() -> Path:
    """The in-repo selection script (repo root / scripts / enrich_subset.py)."""
    return Path(__file__).resolve().parents[3] / "scripts" / "enrich_subset.py"


def plan_path(tool_path, env=None):
    """Where dtmd keeps plan.json (its own gitignored _data dir)."""
    source = os.environ if env is None else env
    base = source.get("DTM_TOOLS") or tool_path
    return Path(base) / "_data" / "plan.json"


def plan_day_count(tool_path, env=None) -> int:
    """How many days the last plan produced. Falls back to 1 if unreadable."""
    try:
        data = json_loads_safe(plan_path(tool_path, env))
    except OSError:
        return 1
    days = data.get("days_normal") or data.get("days") or []
    return max(1, len(days))


def json_loads_safe(path: Path) -> dict:
    import json

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def discover_mineru_dirs(root, step) -> tuple:
    """Every ``*_mineru`` directory that holds a full.md, in stable order."""
    base = W.step_dir(root, step)
    if not base.is_dir():
        return ()
    found = [d for d in base.rglob(f"*{MINERU_DIR_SUFFIX}")
             if d.is_dir() and (d / "full.md").is_file()]
    return tuple(sorted(found))


def all_mineru_dirs(root, step) -> tuple:
    """Every ``*_mineru`` directory, whether or not it already holds a full.md.

    A sliced book has no full.md at its root until merge runs, so the discovery
    used for merging cannot require one.
    """
    base = W.step_dir(root, step)
    if not base.is_dir():
        return ()
    return tuple(sorted(d for d in base.rglob(f"*{MINERU_DIR_SUFFIX}") if d.is_dir()))


def backup_full_md(mineru_dir) -> Path:
    """Snapshot full.md before embed overwrites it. Keeps the first snapshot."""
    live = Path(mineru_dir) / "full.md"
    snapshot = live.with_name(live.name + BACKUP_SUFFIX)
    if not snapshot.exists():
        shutil.copy2(live, snapshot)
    return snapshot


def run(root, *, src_dir, mode=DEFAULT_MODE, day=None, enrich=True, glm=True,
        env=None, timeout=None, runner=None, python=None):
    step = _steps.get_step("document")
    tool = R.part_tool(ENV_KEY, PART, env)
    child = R.tool_env(tool, base=env, extra={"DTM_OUTPUT_ROOT": str(W.step_dir(root, step))})

    planned = R.execute(
        step, build_plan_command(src_dir, python=python), root,
        cwd=tool, env=child, timeout=timeout, runner=runner, check_outputs=False,
    )
    if not planned.ok:
        return planned

    days = [int(day)] if day is not None else range(1, plan_day_count(tool, env) + 1)
    outcome = planned
    for index in days:
        outcome = R.execute(
            step, build_convert_command(mode=mode, day=index, python=python), root,
            cwd=tool, env=child, timeout=timeout, runner=runner,
        )
        if not outcome.ok:
            return outcome

    # A book over MinerU's 200-page limit arrives as p{start}-{end}/ blocks and
    # convert does not stitch them. Merge first: without a root full.md, enrich
    # finds no image references and the whole book silently loses its figures.
    for mineru_dir in all_mineru_dirs(root, step):
        if not has_slices(mineru_dir):
            continue
        outcome = R.execute(
            step, build_merge_command(mineru_dir, python=python), root,
            cwd=tool, env=child, timeout=timeout, runner=runner, check_outputs=False,
        )
        if not outcome.ok:
            return outcome

    if not enrich:
        return outcome

    for mineru_dir in discover_mineru_dirs(root, step):
        backup_full_md(mineru_dir)
        outcome = R.execute(
            step, build_enrich_command(mineru_dir, glm=glm, python=python), root,
            cwd=tool, env=child, timeout=timeout, runner=runner, check_outputs=False,
        )
        if not outcome.ok:
            return outcome
    return outcome
