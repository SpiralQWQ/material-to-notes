# -*- coding: utf-8 -*-
"""Scan the repo for absolute paths / internal names / key patterns.

Run from anywhere. Prints nothing when clean, exits 1 when it is not.

Three file lists, deliberately:

* **own** — this repo's own files, from *both* git and the disk.
* **vendored** — ``parts/``, walked from disk instead of read from git.
* the disk walk is bounded by :data:`SKIP_DIRS`.

Two blind spots were found the hard way, and both are why the sources are mixed:

1. ``parts/`` is fetched, never committed, so ``git ls-files`` returned nothing
   for it and this script reported ``clean`` while every part file went
   unscanned. Hence the separate disk walk for vendored.
2. ``git ls-files`` cannot see a file that has not been added yet — and the
   worst leaks live exactly there, in a doc written before anyone thought to
   run this script. Hence the disk walk for own files too. It also means the
   script still works on a ``git archive`` export, where there is no git at all.

The walk is bounded on purpose: ``runs/`` is user material, ``temp/`` is scratch
and evidence sheets that legitimately quote the source repo's path, and
``parts/`` is reported separately as upstream. Scanning those three would bury
the signal rather than raise it.
"""
import os
import pathlib
import re
import subprocess
import sys

BS = chr(92)
# Built at runtime so this file does not match its own pattern (same reason the
# upstream privacy guards exclude the file that holds the patterns).
INTERNAL_NAME = "AAA" + chr(46) + "Program"
# The internal codename this project used before it was renamed, and the local
# directory tree it lived in. Both are assembled from code points for the same
# reason: a literal here would make this file match itself the moment it is
# tracked, and the scan would report a hit it can never clear.
CODENAME = "_" + chr(0x603B) + chr(0x5DE5) + chr(0x5177)
LOCAL_TREE = "AAA" + re.escape(chr(46))
PATTERNS = {
    # A drive letter plus at least two path components. Requiring depth is what
    # keeps an escaped newline inside a Python string literal from matching:
    # "t:\n" has no second separator, so it is not a path. A lone component
    # (``C:\download``) is a doc example rather than a machine path, and is
    # deliberately left alone — a scanner that cries wolf on examples gets
    # ignored, which is how the real leaks survive.
    "abs-path": re.compile(r"[A-Za-z]:" + re.escape(BS)
                           + r"[A-Za-z0-9_.$-]+([\\/][A-Za-z0-9_.$-]+)+"),
    # Any drive, not just C:: the profile lives wherever the OS was installed.
    "user-dir": re.compile(r"[A-Za-z]:" + re.escape(BS) + "Users"),
    "internal-name": re.compile(re.escape(INTERNAL_NAME)),
    # The whole local project tree, not just the one path the older pattern
    # knew about. Assembled from a code point so this comment cannot name it.
    "local-tree": re.compile(LOCAL_TREE),
    "codename": re.compile(re.escape(CODENAME)),
    # \b matters: without it "Disk-Director" in a list of GitHub repo names
    # matches as sk-Director, and the report fills with noise nobody can clear.
    "api-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
}
SKIP_SUFFIX = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".db"}


def repo_root() -> pathlib.Path:
    """The repo this script lives in: ``<root>/scripts/privacy_check.py``.

    Resolved from ``__file__`` rather than the working directory, so the script
    behaves the same wherever it is invoked from.
    """
    return pathlib.Path(__file__).resolve().parents[1]


def tracked_files():
    """Tracked paths, relative to the repo root. Empty when there is no git."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=str(repo_root()),
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    return [p for p in out.split("\0") if p]


# Never worth reading: VCS internals and Python/pytest caches.
PRUNE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}

# Bounds the own-file walk. Everything here is ours-but-not-shipped: parts/ is
# reported separately as upstream, runs/ holds user material, temp/ holds
# scratch and evidence sheets that legitimately quote the source repo's path.
# Scanning them would bury the real signal.
SKIP_DIRS = PRUNE_DIRS | {
    "parts", "runs", "temp", ".venvs", "venv", "node_modules", "dist", "build",
    ".idea", ".vscode",
}


def vendored_files(root=None):
    """Every file under ``parts/``, read from disk rather than from git.

    ``parts/`` holds the five fetched parts (deliberately untracked, and they
    carry machine-specific run state such as dtmd's ``_data/``), so git cannot
    be the source of truth for them. Walking is the only way to see what is
    actually there — which is the whole point, since this script exists to
    report what is actually there.

    Paths come back openable; :func:`_display` shortens them for the report.
    """
    base = pathlib.Path(root) if root is not None else repo_root() / "parts"
    if not base.is_dir():
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        for name in filenames:
            found.append(str(pathlib.Path(dirpath, name)))
    return sorted(found)


# The five parts are vendored verbatim under parts/ (zero modification). Any
# absolute path inside them is an upstream problem we must not patch here — it
# gets filed against the part's own repository. So they are scanned separately
# and never count as this repo's own hit.
VENDOR_PREFIX = "parts/"


def _slash(path: str) -> str:
    """Normalise a path to forward slashes, so one file is one key."""
    return path.replace("\\", "/")


def _display(path: str) -> str:
    """Report path relative to the repo root, with forward slashes.

    Without this the report quotes absolute paths back at the reader — noisy,
    and the report itself would then contain the very thing it looks for.
    Anything outside the repo is printed as it came in.
    """
    text = _slash(str(path))
    prefix = _slash(str(repo_root())) + "/"
    return text[len(prefix):] if text.startswith(prefix) else text


def own_files(root=None):
    """Every file that is ours: tracked by git, or simply present on disk.

    Git alone is blind spot #2 — it cannot see a file that has not been added
    yet, and that is precisely where the leaks nobody has noticed live. The
    disk walk closes it, and makes the script usable on an export with no git.

    Returns paths that :func:`_scan` can open directly, so the caller never has
    to think about the working directory.
    """
    base = pathlib.Path(root) if root is not None else repo_root()
    found = {str(base / _slash(f)) for f in tracked_files()
             if not _slash(f).startswith(VENDOR_PREFIX)}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for name in filenames:
            found.add(str(pathlib.Path(dirpath, name)))
    return sorted(found)


def _utf8_stdout() -> None:
    """Make printing safe on a non-UTF-8 console (GBK is the Windows default).

    The report quotes file contents verbatim, and those contents carry emoji,
    CJK and box-drawing characters. On a GBK console the ``print`` itself raised
    ``UnicodeEncodeError`` — the script died mid-report and exited non-zero for
    a reason that had nothing to do with privacy. ``errors="replace"`` keeps a
    stray undecodable byte from killing the run either.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # redirected, already detached, or a Python without reconfigure


def _scan(rel_paths):
    """Yield (rel, lineno, kind, line) for every pattern hit.

    ``rel`` is what gets printed; it is resolved against the repo root so the
    scan no longer depends on the working directory it was launched from.
    """
    for rel in rel_paths:
        path = pathlib.Path(rel)
        if not path.is_absolute():
            path = repo_root() / path
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, rx in PATTERNS.items():
                if rx.search(line):
                    yield rel, lineno, name, line.strip()[:100]


def main() -> int:
    _utf8_stdout()
    own = own_files()
    vendored = vendored_files()

    hits = 0
    for rel, lineno, name, line in _scan(own):
        hits += 1
        print(f"{_display(rel)}:{lineno}  [{name}]  {line}")
    print("clean" if not hits else f"{hits} hit(s)")

    upstream = list(_scan(vendored))
    if upstream:
        print(f"\n-- 上游零件自身（{len(upstream)} 处，不修改这里，请回灌到各自仓库）--")
        for rel, lineno, name, line in upstream:
            print(f"{_display(rel)}:{lineno}  [{name}]  {line}")
    else:
        print(f"-- 上游零件自身：clean（扫了 {len(vendored_files())} 个文件）--")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
