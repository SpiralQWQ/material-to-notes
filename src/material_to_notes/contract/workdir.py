"""Workdir layout: single source of truth for where a run writes.

A run gets one workdir. Every step writes inside it, and the source material is
kept untouched under 00_输入 so nothing is ever overwritten or lost.

One workdir handles *many* sources, so nothing may be named after the step: two
papers would both want ``full.txt``. Outputs are named after their source, and
everything machine-readable lives under ``_元数据/`` so a folder of deliverables
holds only deliverables.
"""

from __future__ import annotations

from pathlib import Path

INPUT_DIR = "00_输入"
META_DIR = "_元数据"
STATE_DIR = "_state"
LOGS_DIR = "_logs"
PROGRESS_FILE = "进度单.md"
FAILURE_FILE = "失败单.md"

_STEP_SUBDIRS = ("01_取材", "02_转md", "03_清洗", "04_笔记")

# dtmd mirrors a document into <name>_mineru/; m2m writes <name>_clean.md flat.
MINERU_SUFFIX = "_mineru"
MEDIA_SUFFIX = "_clean.md"

_ILLEGAL = '<>:"/\\|?*'
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {
    f"lpt{i}" for i in range(1, 10)
}
_MAX_NAME = 120


def safe_filename(name: str) -> str:
    """Make a name safe on Windows: drop illegal chars, guard reserved names, cap length."""
    cleaned = "".join("_" if (c in _ILLEGAL or ord(c) < 32) else c for c in name).strip(" .")
    if not cleaned:
        return "_"
    if cleaned.split(".")[0].lower() in _RESERVED:
        cleaned = "_" + cleaned
    if len(cleaned) > _MAX_NAME:
        root, dot, ext = cleaned.rpartition(".")
        if dot and len(ext) <= 10:
            cleaned = root[: _MAX_NAME - len(ext) - 1] + "." + ext
        else:
            cleaned = cleaned[:_MAX_NAME]
    return cleaned


def source_name(path) -> str:
    """The name a source's outputs are keyed by, derived from where it landed.

    ``02_转md/<名>_mineru/full.md`` and ``02_转md/<名>_clean.md`` both reduce to
    ``<名>``; anything else falls back to the file's stem. Callers pass the result
    through :func:`safe_filename` before using it as a path segment.
    """
    p = Path(path)
    if p.parent.name.endswith(MINERU_SUFFIX):
        return p.parent.name[: -len(MINERU_SUFFIX)]
    if p.name.endswith(MEDIA_SUFFIX):
        return p.name[: -len(MEDIA_SUFFIX)]
    return p.stem


def subdirs() -> tuple:
    """Every directory a run's workdir holds, in creation order."""
    return (INPUT_DIR, *_STEP_SUBDIRS, META_DIR, STATE_DIR, LOGS_DIR)


def ensure(root) -> Path:
    """Create the workdir layout under root (idempotent) and return it."""
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    for name in subdirs():
        (base / name).mkdir(exist_ok=True)
    return base


def missing(root) -> list:
    """Return the workdir entries that are absent (empty list means complete)."""
    base = Path(root)
    if not base.is_dir():
        return ["<workdir>"]
    return [name for name in subdirs() if not (base / name).is_dir()]


def step_dir(root, step) -> Path:
    """Directory a given step writes into, e.g. <root>/02_转md."""
    return Path(root) / step.workdir_subdir


def meta_dir(root) -> Path:
    """Where every machine-readable record lives — never beside the deliverables."""
    return Path(root) / META_DIR
