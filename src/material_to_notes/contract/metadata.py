"""Everything machine-readable about a run: the intake sheet and per-source records.

Two files, both under ``_元数据/`` and never beside a deliverable:

  投料单.json      what the user answered at intake — audience, delivery folder,
                  and any per-source name overrides. Answered once, reused
                  afterwards; a change is an explicit edit, not a new interview.
  <名字>.json      one record per source: where it came from, what each step
                  produced, when, and the statistics the step reported.

The user's words: metadata gets its own folder, kept apart from the produced
markdown. So a notes folder holds notes.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
from pathlib import Path

from material_to_notes.contract import workdir as _workdir

SHEET_NAME = "投料单.json"
DEFAULT_AUDIENCE = "教学素材库"

# The three things intake asks; anything else is a default the user never sees
# unless they go looking.
SHEET_KEYS = ("audience", "deliver_dir", "names")


def _base(root) -> Path:
    return _workdir.meta_dir(root)


def sheet_path(root) -> Path:
    return _base(root) / SHEET_NAME


def record_path(root, name: str) -> Path:
    return _base(root) / f"{_workdir.safe_filename(name)}.json"


def _write_json(path: Path, data) -> Path:
    """Atomic: an interrupted write never leaves a half-file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# --- the intake sheet -------------------------------------------------------

def defaults() -> dict:
    """What every unanswered question falls back to. Never empty."""
    return {"version": 1, "audience": DEFAULT_AUDIENCE, "deliver_dir": "", "names": {}}


def load_sheet(root) -> dict:
    """The sheet, with defaults filled in. A missing or corrupt sheet is not an error."""
    data = defaults()
    stored = _read_json(sheet_path(root))
    for key in SHEET_KEYS:
        if key in stored:
            data[key] = stored[key]
    if not isinstance(data.get("names"), dict):
        data["names"] = {}
    return data


def save_sheet(root, **fields) -> Path:
    """Merge the given answers into the sheet and write it back."""
    data = load_sheet(root)
    for key, value in fields.items():
        if key not in SHEET_KEYS:
            raise KeyError(f"unknown intake field: {key!r} (expected one of {SHEET_KEYS})")
        data[key] = value
    data["version"] = 1
    return _write_json(sheet_path(root), data)


def name_for(sheet: dict, source_key: str, fallback: str) -> str:
    """The output name for a source: the user's override, else the source's own name."""
    wanted = (sheet.get("names") or {}).get(source_key, "")
    return _workdir.safe_filename(wanted or fallback)


def render_sheet(sheet: dict, *, source_keys=()) -> str:
    """A human-readable view. Says plainly which values are still defaults."""
    lines = ["# 投料单", ""]
    lines.append(f"- 给谁看 / 干什么用：{sheet['audience']}"
                 + ("" if sheet["audience"] != DEFAULT_AUDIENCE else "（默认）"))
    lines.append(f"- 笔记放哪：{sheet['deliver_dir'] or '工作目录的 04_笔记/（默认，就地）'}")
    lines.append("")
    lines.append("## 每份素材的名字")
    names = sheet.get("names") or {}
    if not source_keys:
        lines.append("（还不知道有哪些素材；投料后这里会列出来）")
    for key in source_keys:
        wanted = names.get(key, "")
        lines.append(f"- {key} → {wanted or key + '（默认，用素材自己的名字）'}")
    return "\n".join(lines)


# --- the per-source record --------------------------------------------------

def load_record(root, name: str) -> dict:
    return _read_json(record_path(root, name))


def update_record(root, name: str, **fields) -> Path:
    """Merge fields into a source's record and stamp the time."""
    data = load_record(root, name)
    data.setdefault("name", name)
    for key, value in fields.items():
        data[key] = value
    data["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    return _write_json(record_path(root, name), data)


def record_step(root, name: str, step_id: str, *, ok: bool,
                outputs=(), stats=None, error: str = "") -> Path:
    """Write one step's outcome into the source's record.

    One record per source, one entry per step — so the whole history of a
    material sits in a single file instead of being scattered as side-cars next
    to each deliverable.
    """
    data = load_record(root, name)
    steps = dict(data.get("steps") or {})
    steps[step_id] = {
        "ok": bool(ok),
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "outputs": [str(o) for o in outputs],
        "stats": dict(stats or {}),
    }
    if error:
        steps[step_id]["error"] = error
    return update_record(root, name, steps=steps)


def note_stats(record: dict) -> str:
    """One line for the progress sheet: what is recorded about a source."""
    if not record:
        return "（无记录）"
    steps = record.get("steps") or {}
    done = ",".join(sorted(steps)) or "无"
    return f"记录在 _元数据/{record.get('name', '?')}.json（含 {done}）"
