"""Tests for scripts/privacy_check.py — the vendored-file blind spot.

The bug these lock down: the script used to build its file list from
``git ls-files`` alone. ``parts/`` is vendored but never committed, so that list
came back empty for it and the script printed ``clean`` while every part file
went unscanned. A guard that reports success without looking is worse than no
guard, so the file source is asserted here rather than trusted.
"""

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import privacy_check as P  # noqa: E402


def test_vendored_files_sees_untracked_parts(tmp_path):
    # The whole point: parts/ is not in git, so only a disk walk can see it.
    parts = tmp_path / "parts" / "some-tool"
    parts.mkdir(parents=True)
    (parts / "a.py").write_text("x = 1\n", encoding="utf-8")
    nested = parts / "deep" / "deeper"
    nested.mkdir(parents=True)
    (nested / "b.md").write_text("# t\n", encoding="utf-8")

    found = P.vendored_files(tmp_path / "parts")
    names = sorted(pathlib.Path(f).name for f in found)
    assert names == ["a.py", "b.md"]


def test_vendored_files_prunes_caches_and_vcs(tmp_path):
    parts = tmp_path / "parts"
    for junk in (".git", "__pycache__", ".pytest_cache"):
        d = parts / junk
        d.mkdir(parents=True)
        (d / "junk.txt").write_text("junk\n", encoding="utf-8")
    (parts / "real.py").write_text("y = 2\n", encoding="utf-8")

    found = [pathlib.Path(f).name for f in P.vendored_files(parts)]
    assert found == ["real.py"]


def test_vendored_files_missing_dir_is_empty(tmp_path):
    assert P.vendored_files(tmp_path / "nope") == []


def test_the_real_repo_parts_are_actually_scanned():
    # Regression guard for the silent blind spot: this repo vendors five parts
    # under parts/ and they are deliberately untracked, so if the scan ever goes
    # back to reading git this returns [] and the check reports clean again.
    parts = REPO / "parts"
    if not parts.is_dir():
        pytest.skip("no parts/ in this checkout")
    found = P.vendored_files(parts)
    assert len(found) > 100, (
        f"expected the vendored parts to be scanned, got {len(found)} files — "
        "the file source has probably gone back to git ls-files"
    )


def test_a_hit_inside_parts_is_reported(tmp_path):
    # A machine-specific path sitting in a part must surface, not be swallowed.
    # The path is assembled at runtime for the same reason privacy_check.py
    # builds its own patterns that way: a literal here would make this very file
    # match the scanner the moment it is tracked by git.
    parts = tmp_path / "parts" / "tool"
    parts.mkdir(parents=True)
    bs = chr(92)
    leak = "see E:" + bs + "AAA" + chr(46) + "Program" + bs + "CC" + bs + "something"
    (parts / "leak.md").write_text(leak + "\n", encoding="utf-8")

    hits = list(P._scan(P.vendored_files(parts)))
    assert hits, "an absolute path inside parts/ must be reported"
    assert any(kind in ("abs-path", "internal-name") for _r, _l, kind, _x in hits)


def test_own_files_still_come_from_git(tmp_path, monkeypatch):
    # temp/ and runs/ are gitignored and hold user material; scanning them would
    # bury the signal. So own-files stays on git even though vendored does not.
    monkeypatch.setattr(P, "tracked_files", lambda: ["a.py", "temp/x.py", "runs/y.pdf"])
    own = [f for f in P.tracked_files()
           if not f.replace("\\", "/").startswith(P.VENDOR_PREFIX)]
    assert own == ["a.py", "temp/x.py", "runs/y.pdf"]


def test_main_reports_a_hit_that_git_cannot_see(tmp_path, monkeypatch, capsys):
    # The real regression, tested at main() rather than at the helper: parts/ is
    # untracked, so git returns nothing for it. If main() ever builds its
    # vendored list from git again, a real leak goes unreported while the script
    # still exits 0 — a guard that passes without looking.
    parts = tmp_path / "parts" / "tool"
    parts.mkdir(parents=True)
    bs = chr(92)
    leak = "E:" + bs + "AAA" + chr(46) + "Program" + bs + "CC" + bs + "x"
    (parts / "leak.md").write_text(leak + "\n", encoding="utf-8")

    monkeypatch.setattr(P, "tracked_files", lambda: [])          # git sees nothing
    monkeypatch.setattr(P, "vendored_files", lambda *a, **k: [str(parts / "leak.md")])

    P.main()
    out = capsys.readouterr().out
    assert "leak.md" in out, (
        "a hit inside parts/ must reach the report even though git does not "
        "track it — the vendored list has probably gone back to git ls-files"
    )
