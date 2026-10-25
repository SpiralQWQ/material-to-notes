"""Preflight: this suite reads the five parts' files, so they must be fetched.

``python -m pytest`` on a fresh clone used to fail with 39
``FileNotFoundError``s pointing at ``parts/md-rewrite-engine/...`` — real, but
useless: the reader cannot tell a missing setup step from a broken repo. The
suite only ever *reads* the parts (``configs/note_style_spec.yaml``,
``scripts/gate_check.py``), it never imports them, so a missing part is a setup
problem and is reported as one.

CI fetches the parts before running the suite, so CI never sees this skip. A
skip here means "run setup_parts.py", never "all good".
"""

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

PARTS = (
    "web-knowledge-crawler",
    "document-to-markdown",
    "media-to-markdown",
    "text-cleaning-engine",
    "md-rewrite-engine",
)

MISSING = [name for name in PARTS if not (REPO / "parts" / name).is_dir()]

if MISSING:
    print("\n" + "!" * 72)
    print(f"parts/ is incomplete — missing: {', '.join(MISSING)}")
    print()
    print("  Run:  python scripts/setup_parts.py")
    print()
    print("The suite reads the parts' files (the note style spec, the gate")
    print("labels), so without them it fails with FileNotFoundError instead of")
    print("a readable reason. That is what this preflight replaces.")
    print("!" * 72 + "\n")


def pytest_collection_modifyitems(config, items):
    """Turn "parts were never fetched" into a skip that says what to do."""
    if not MISSING:
        return
    reason = ("parts/ is missing ({}) — run `python scripts/setup_parts.py` "
              "first; the suite reads the parts' files".format(", ".join(MISSING)))
    marker = pytest.mark.skip(reason=reason)
    for item in items:
        if "needs_parts" not in item.keywords:
            item.add_marker(marker)

def pytest_sessionfinish(session, exitstatus):
    """A run that skipped everything verified nothing, so it must not be green.

    Skips alone leave pytest exiting 0, which reads as "all good" to anything
    that only looks at the exit code — a shell script, a CI step, a person
    skimming. CI fetches the parts first and never reaches this branch.
    """
    if MISSING and exitstatus == 0:
        session.exitstatus = 1
