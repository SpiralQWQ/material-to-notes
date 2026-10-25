"""Stage run inputs into the workdir without ever clobbering what is there."""

from __future__ import annotations

import shutil
from pathlib import Path

from material_to_notes.contract import workdir as _workdir


def stage(root, targets) -> tuple:
    """Copy each input into 00_输入 and return the staged paths.

    Anything already present under that name is left alone — the originals are
    the last resort if a later step cleans too hard, so staging never overwrites.
    """
    base = Path(root) / _workdir.INPUT_DIR
    base.mkdir(parents=True, exist_ok=True)
    staged = []
    for target in targets:
        src = Path(target)
        if not src.exists():
            raise FileNotFoundError(f"input not found: {target}")
        dst = base / src.name
        if not dst.exists():
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        staged.append(dst)
    return tuple(staged)
