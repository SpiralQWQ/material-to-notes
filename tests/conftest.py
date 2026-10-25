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


def _announce(config):
    """Print the preflight banner where the user will actually see it.

    A module-level print() does not work here: pytest captures stdout for the
    whole session, so the banner was swallowed and a fresh clone showed nothing
    but ``524 skipped`` and exit 1 -- no hint of what to run, which is the exact
    thing this preflight exists to provide. The terminal reporter writes
    straight to the terminal and bypasses that capture.
    """
    reporter = config.pluginmanager.getplugin("terminalreporter")
    if reporter is None:  # pragma: no cover - terminalreporter is always there
        return
    reporter.write_sep("!", "parts/ is incomplete — missing: "
                       + ", ".join(MISSING))
    reporter.write_line("")
    reporter.write_line("  Run:  python scripts/setup_parts.py")
    reporter.write_line("")
    reporter.write_line("The suite reads the parts' files (the note style spec, the")
    reporter.write_line("gate labels), so without them it fails with FileNotFoundError")
    reporter.write_line("instead of a readable reason. That is what this replaces.")


def pytest_collection_modifyitems(config, items):
    """Turn "parts were never fetched" into a skip that says what to do."""
    if not MISSING:
        return
    _announce(config)
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
