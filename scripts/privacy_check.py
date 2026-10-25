# -*- coding: utf-8 -*-
"""Scan the repo for absolute paths / internal names / key patterns.

Run from the repo root. Prints nothing when clean.

Two file lists, deliberately:

* **own** — this repo's own files, taken from ``git ls-files``. Using git here
  is what keeps ``temp/`` and ``runs/`` out: both are gitignored and hold user
  material plus scratch scripts, and scanning them would bury the real signal.
* **vendored** — ``parts/``, walked from disk instead of read from git.

That second list is the fix for a silent blind spot. ``parts/`` is vendored but
was never committed, so ``git ls-files`` returned nothing for it and this script
reported ``clean`` while 843 part files went unscanned. Git is the wrong source
for a directory that is intentionally untracked; walk the disk for it.
"""
import os
import pathlib
import re
import subprocess

BS = chr(92)
# Built at runtime so this file does not match its own pattern (same reason the
# upstream privacy guards exclude the file that holds the patterns).
INTERNAL_NAME = "AAA" + chr(46) + "Program"
PATTERNS = {
    "abs-path": re.compile(r"[A-Za-z]:" + re.escape(BS)),
    "internal-name": re.compile(re.escape(INTERNAL_NAME)),
    "user-dir": re.compile(re.escape("C:" + BS + "Users")),
    "api-key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
}
SKIP_SUFFIX = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".db"}


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    return [p for p in out.split("\0") if p]


# Never worth reading: VCS internals and Python/pytest caches.
PRUNE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def vendored_files(root="parts"):
    """Every file under ``parts/``, read from disk rather than from git.

    ``parts/`` holds vendored copies that are deliberately untracked (they carry
    machine-specific run state such as dtmd's ``_data/``), so git cannot be the
    source of truth for them. Walking is the only way to see what is actually
    there — which is the whole point, since this script exists to report what is
    actually there.
    """
    base = pathlib.Path(root)
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
# gets registered in docs/回灌清单.md instead. So they are scanned separately
# and never count as this repo's own hit.
VENDOR_PREFIX = "parts/"


def _scan(rel_paths):
    """Yield (rel, lineno, kind, line) for every pattern hit."""
    for rel in rel_paths:
        path = pathlib.Path(rel)
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
    own = [f for f in tracked_files()
           if not f.replace("\\", "/").startswith(VENDOR_PREFIX)]
    vendored = vendored_files()

    hits = 0
    for rel, lineno, name, line in _scan(own):
        hits += 1
        print(f"{rel}:{lineno}  [{name}]  {line}")
    print("clean" if not hits else f"{hits} hit(s)")

    upstream = list(_scan(vendored))
    if upstream:
        print(f"\n-- 上游零件自身（{len(upstream)} 处，不修改这里，请回灌到各自仓库）--")
        for rel, lineno, name, line in upstream:
            print(f"{rel}:{lineno}  [{name}]  {line}")
    else:
        print(f"-- 上游零件自身：clean（扫了 {len(vendored_files())} 个文件）--")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
