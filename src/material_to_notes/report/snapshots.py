"""Snapshots of a step's output, taken before it is handed to an agent again.

The project rule is "原件留底绝不覆盖", but it only ever covered *input* material.
Our own artifacts had no history: when the note was revised, there was no
before-copy, so "I only changed these four places" could not be checked by diff —
only by counting things and hoping. That is exactly the wrong place to be unable
to prove a claim.

A snapshot is taken at dispatch time: that is the moment an agent is about to
write into the step's directory, and therefore the last moment the previous
version still exists. Snapshots live under ``_state/快照/<step>/<timestamp>/``,
inside the run workdir (gitignored), and are never pruned automatically —
they are evidence, and silently deleting evidence is the thing this file exists
to prevent.
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as _workdir

SNAPSHOT_DIR = "快照"


def root_for(root, step_id: str) -> Path:
    return Path(root) / _workdir.STATE_DIR / SNAPSHOT_DIR / step_id


def _live_dir(root, step_id: str) -> Path:
    return _workdir.step_dir(root, _steps.get_step(step_id))


def take(root, step_id: str, *, now=None) -> Path:
    """Copy the step's current output aside. Returns the snapshot path, or None.

    Returns None when there is nothing to keep (first dispatch, empty directory):
    an empty snapshot would suggest a revision happened when none did.
    """
    live = _live_dir(root, step_id)
    if not live.is_dir() or not any(live.rglob("*")):
        return None
    stamp = (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")
    target = root_for(root, step_id) / stamp
    if target.exists():                      # two dispatches inside one second
        target = target.with_name(f"{stamp}-{len(list(target.parent.glob(stamp + '*'))) + 1}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(live, target)
    return target


def listing(root, step_id: str) -> tuple:
    """Snapshot directories for a step, oldest first."""
    base = root_for(root, step_id)
    if not base.is_dir():
        return ()
    return tuple(sorted(p for p in base.iterdir() if p.is_dir()))


def relpath(root, path: Path) -> str:
    """Workdir-relative, forward-slashed — for printing, never an absolute path."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
