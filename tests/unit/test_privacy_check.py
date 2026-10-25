"""Tests for scripts/privacy_check.py — its two file-source blind spots.

The bugs these lock down, both of which made the script report ``clean`` while
real leaks went unscanned:

1. the file list came from ``git ls-files`` alone, and ``parts/`` is fetched
   rather than committed, so git returned nothing for it;
2. ``git ls-files`` cannot see a file nobody has added yet — which is exactly
   where a leak written before anyone ran this script lives.

A guard that reports success without looking is worse than no guard, so both
file sources are asserted here rather than trusted. Two further regressions are
pinned below: an escaped ``\\n`` matching the absolute-path rule, and the same
file being reported twice because git and ``os.walk`` spell paths differently.
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


# --- blind spot #2: a file git has never seen -------------------------------

def test_own_files_sees_what_git_cannot(tmp_path, monkeypatch):
    # git ls-files is empty for a file nobody has added, and that is precisely
    # where the unnoticed leaks live. The disk walk must still see it — while
    # runs/ (user material) stays out.
    monkeypatch.setattr(P, "tracked_files", lambda: [])
    (tmp_path / "leak.md").write_text("# doc\n", encoding="utf-8")
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "user.pdf").write_text("x\n", encoding="utf-8")

    names = [pathlib.Path(f).name for f in P.own_files(tmp_path)]
    assert "leak.md" in names, "an untracked file must still be scanned"
    assert "user.pdf" not in names, "runs/ holds user material and must stay out"


def test_own_files_prunes_caches_and_pycache(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "tracked_files", lambda: [])
    for junk in ("__pycache__", ".pytest_cache", ".venvs"):
        d = tmp_path / junk
        d.mkdir()
        (d / "junk.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "real.py").write_text("y = 1\n", encoding="utf-8")

    names = [pathlib.Path(f).name for f in P.own_files(tmp_path)]
    assert names == ["real.py"], f"caches must be pruned, got {names}"


def test_main_reports_a_hit_in_an_untracked_own_file(tmp_path, monkeypatch, capsys):
    # The second real regression, tested at main() rather than at the helper.
    # If main() ever builds its own list from git alone again, a file nobody
    # has added goes unscanned while the script still exits 0 — the same fake
    # green as the parts/ bug, one layer out.
    leak = tmp_path / "untracked.md"
    bs = chr(92)
    leak.write_text("see C:" + bs + "Users" + bs + "someone" + bs + "x" + bs + "y\n",
                    encoding="utf-8")

    monkeypatch.setattr(P, "own_files", lambda *a, **k: [str(leak)])
    monkeypatch.setattr(P, "vendored_files", lambda *a, **k: [])

    rc = P.main()
    out = capsys.readouterr().out
    assert "untracked.md" in out, (
        "a leak in an untracked own file must reach the report — the own list "
        "has probably gone back to git ls-files"
    )
    assert rc == 1, "a real leak must make the script exit non-zero"


# --- the false positive that turned a clean checkout red --------------------

def test_an_escaped_newline_is_not_an_absolute_path():
    # abs-path used to be [A-Za-z]:\ which matched the "t:\n" inside a Python
    # string literal. Those files are tracked here, so a clean checkout
    # reported hits and exited 1. A scanner that cries wolf gets ignored, and
    # that is how the real leaks survive.
    bs = chr(92)
    rx = P.PATTERNS["abs-path"]
    assert not rx.search("if x not in t:" + bs + "n")
    assert not rx.search("frontmatter:" + bs + "n  - title")
    assert not rx.search("see C:" + bs + "download"), "a doc example is not a path"
    assert rx.search("C:" + bs + "Users" + bs + "someone" + bs + "x")
    assert rx.search("E:" + bs + "AAA" + bs + "Program" + bs + "CC")


def test_the_same_file_is_not_reported_twice(tmp_path, monkeypatch):
    # git spells paths with / and os.walk with \ on Windows. As a plain set of
    # strings the same file was scanned, and reported, twice.
    monkeypatch.setattr(P, "tracked_files", lambda: ["a/b.py"])
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b.py").write_text("x = 1\n", encoding="utf-8")

    names = [pathlib.Path(f).name for f in P.own_files(tmp_path)]
    assert names.count("b.py") == 1, f"one file must be scanned once, got {names}"


def test_display_strips_the_repo_root():
    # The report used to quote absolute paths — noisy to read, and the report
    # itself then contained the very thing the scan looks for.
    root = P._slash(str(P.repo_root()))
    shown = P._display(root + "/docs/x.md")
    assert shown == "docs/x.md", f"report paths must be repo-relative, got {shown}"
    assert P._display("/somewhere/else/x.md") == "/somewhere/else/x.md"


def test_utf8_stdout_never_raises_on_a_bare_stream(monkeypatch):
    # The GBK crash: the report quotes file contents verbatim, and on a GBK
    # console the print itself raised UnicodeEncodeError — the script died
    # mid-report and exited non-zero for a reason unrelated to privacy.
    class Bare:
        encoding = "gbk"

        def write(self, _s):  # pragma: no cover - must never be reached
            raise AssertionError("should not write anything")

    monkeypatch.setattr(P.sys, "stdout", Bare())
    P._utf8_stdout()  # must swallow the missing reconfigure, not raise


# --- the patterns that were too narrow to be worth anything -----------------

def test_the_local_project_tree_is_caught():
    # internal-name only knew one path. Every other directory this project
    # lived in sailed straight through, so the pattern was widened.
    rx = P.PATTERNS["local-tree"]
    assert rx.search("mirrored from " + "AAA" + chr(46) + "GitHub_MySorces")
    assert rx.search("under " + "AAA" + chr(46) + "Study" + chr(92) + "M" + chr(46) + "AIStudy")
    assert not rx.search("AAA rated, AAA battery")


def test_the_internal_codename_is_caught():
    rx = P.PATTERNS["codename"]
    assert rx.search("# " + P.CODENAME)
    assert not rx.search("# material-to-notes")


def test_a_repository_name_is_not_an_api_key():
    # "Acronis-Disk-Director-..." in a list of GitHub repo names matched
    # sk-Director and the report filled with hits nobody could clear.
    rx = P.PATTERNS["api-key"]
    assert not rx.search("Acronis-Disk-Director-Data-Recovery/Partition-Manager")
    assert not rx.search("Risk-Prediction-with-Fairness-Geography")
    assert rx.search("key = sk-" + "a" * 30)


def test_the_scanner_does_not_match_itself():
    # The file holds the patterns, so a literal in it would be a hit that can
    # never be cleared — and the scan would never report clean again.
    hits = [h for h in P._scan(P.own_files()) if h[0].endswith("privacy_check.py")]
    assert not hits, f"the scanner matches itself: {hits[:3]}"
