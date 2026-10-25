"""Resume: decide which steps still need to run.

A step counts as done only when the state says so AND the input fingerprint is
unchanged. Change the input and the step runs again.
"""

from __future__ import annotations

import hashlib
import os


def fingerprint(path) -> str:
    """Cheap fingerprint of a file/dir: size + mtime. Empty string if unreadable."""
    try:
        st = os.stat(os.fspath(path))
    except OSError:
        return ""
    digest = hashlib.sha1()
    digest.update(f"{st.st_size}:{st.st_mtime_ns}".encode("utf-8"))
    return digest.hexdigest()[:16]


def is_done(state, step_id: str, fp: str) -> bool:
    """True only when the step finished before on this exact input."""
    record = ((state or {}).get("steps") or {}).get(step_id)
    return bool(record) and record.get("status") == "done" and record.get("fp") == fp


def mark_done(state, step_id: str, fp: str) -> dict:
    """Return a copy of the state with the step recorded as done."""
    updated = dict(state or {})
    steps = dict(updated.get("steps") or {})
    steps[step_id] = {"status": "done", "fp": fp}
    updated["steps"] = steps
    return updated


def pending(state, chain, fingerprints) -> tuple:
    """Steps in ``chain`` that still need to run for the given fingerprints."""
    return tuple(s for s in chain if not is_done(state, s, fingerprints.get(s, "")))
