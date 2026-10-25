"""Initialize a run: create the workdir layout and its state file.

The state file is written atomically (temp file + os.replace) so an interrupted
run never leaves a half-written state behind.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from material_to_notes.contract import workdir as W

STATE_NAME = "run_state.json"
STATE_VERSION = 1


def state_path(root) -> Path:
    return Path(root) / W.STATE_DIR / STATE_NAME


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        # The temp file may already be gone; that is not worth masking the
        # original failure for, so the cleanup failure is suppressed and the
        # real exception still propagates.
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def init(root, *, input_kind=None, inputs=(), overwrite=False) -> Path:
    """Create the workdir and a fresh state file.

    Idempotent: an existing state file is kept unless ``overwrite`` is set, so
    re-entering a run never destroys what is already there.
    """
    W.ensure(root)
    path = state_path(root)
    if path.exists() and not overwrite:
        return path
    _write_atomic(path, {
        "version": STATE_VERSION,
        "input_kind": input_kind,
        "inputs": [str(i) for i in inputs],
        "steps": {},
    })
    return path


def load(root):
    """Return the run state, or None when missing/corrupt (never raises)."""
    path = state_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def save(root, state: dict) -> None:
    _write_atomic(state_path(root), state)
