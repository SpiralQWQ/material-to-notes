"""Per-step run log: JSON lines with timestamp, level, input fingerprint and argv.

The argv matters: without the command that actually ran, there is no measured
record to write an interface spec from — only what the code says it would do.
Absolute paths stay here because ``_logs/`` sits inside the run workdir, which
is gitignored; the privacy scan guards whatever gets copied into tracked docs.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from material_to_notes.contract import workdir as _workdir

LOG_NAME = "run.log"


def path(root) -> Path:
    return Path(root) / _workdir.LOGS_DIR / LOG_NAME


def record(root, *, step: str, level: str, message: str, fingerprint: str = "",
           argv=()) -> Path:
    """Append one log entry. Returns the log file path."""
    entry = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "step": step,
        "level": level.upper(),
        "message": message,
        "fp": fingerprint,
    }
    if argv:
        entry["argv"] = [str(a) for a in argv]
    target = path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return target


def read(root) -> list:
    """All log entries; unreadable log yields an empty list."""
    target = path(root)
    if not target.is_file():
        return []
    entries = []
    for raw in target.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        try:
            entries.append(json.loads(raw))
        except ValueError:
            continue
    return entries
