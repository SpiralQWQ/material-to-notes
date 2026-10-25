#!/usr/bin/env python3
"""Fetch the five parts this pipeline drives, pinned to known-good commits.

Run from anywhere. Writes into ``<repo>/parts/<name>/`` and checks out the
pinned commit, so a fresh clone reproduces the exact tree the test suite was
validated against.

    python scripts/setup_parts.py                     # fetch whatever is missing
    python scripts/setup_parts.py --check             # report only, fetch nothing
    python scripts/setup_parts.py --update            # re-fetch and re-pin all
    python scripts/setup_parts.py --force             # discard and re-clone
    python scripts/setup_parts.py --mirror gh-proxy   # via a China mirror

The parts are separate repositories with their own licenses. They are fetched,
not vendored: this repo carries orchestration code only. See docs/UPSTREAM.md.

Why pins and not "latest master": a part is allowed to move under us. The
adapters call into fixed entry points (``python -m dtmd``, ``app/crawl_all.py``),
and ``orchestrate/spec.py`` reads the note style spec and the gate labels
straight out of md-rewrite-engine. A part that renames a module or rewrites its
spec breaks the pipeline silently, so a pin is bumped deliberately and the
end-to-end run is repeated before it lands.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Mirrors come and go constantly. This one was verified reachable on 2026-10-25;
# treat any preset as a convenience, never a guarantee. Pass an arbitrary prefix
# with ``--mirror <url>`` once the preset has gone stale.
MIRROR_PRESETS = {
    "gh-proxy": "https://gh-proxy.com/https://github.com",
}

GITHUB = "https://github.com"
ORG = "SpiralQWQ"


@dataclass(frozen=True)
class Part:
    """One part: where it lives, which commit is known good, and how we call it."""

    name: str
    commit: str
    branch: str
    # How the adapter invokes it: a module for ``python -m``, or a script path.
    entry: str
    kind: str  # "module" or "script"
    layout: str  # "src" or "flat" — decides what goes on PYTHONPATH
    license: str = "AGPL-3.0 + commercial (see the part's own LICENSE)"

    @property
    def url(self) -> str:
        return f"{GITHUB}/{ORG}/{self.name}.git"


PARTS = (
    Part("web-knowledge-crawler", "637115d5817de5e84f59ada9dff932137af6102e", "main",
         "app/crawl_all.py", "script", "flat"),
    Part("document-to-markdown", "ce7d42a6b59a2ade89ec045a16883edd60b58842", "master",
         "dtmd", "module", "src"),
    Part("media-to-markdown", "6c09e2006d41eaed90e2b76796c1a26ab21ea66b", "master",
         "media_to_markdown", "module", "src"),
    Part("text-cleaning-engine", "aa44c14db7cbcd79f6a115295381ff9a6da8510d", "master",
         "cleaner.clean_md", "module", "flat"),
    Part("md-rewrite-engine", "bbc8de76c715285b94c7c345c62682b3db1c2cf2", "master",
         "md_rewrite_engine", "module", "src"),
)


def repo_root() -> Path:
    """The repo this script lives in: ``<root>/scripts/setup_parts.py``."""
    return Path(__file__).resolve().parents[1]


def parts_root() -> Path:
    return repo_root() / "parts"


def _git(argv, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + argv, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _resolve_mirror(name: str) -> str:
    """Turn ``--mirror`` into a URL prefix, or explain why it cannot be one.

    A typo would otherwise become a relative path like ``ghporxy/SpiralQWQ/...``
    and surface as a confusing git error three steps later.
    """
    if not name:
        return ""
    if name in MIRROR_PRESETS:
        return MIRROR_PRESETS[name]
    if "://" not in name:
        raise SystemExit(
            f"--mirror {name!r} is neither a preset nor a URL.\n"
            f"Presets: {', '.join(sorted(MIRROR_PRESETS))}\n"
            f"Or pass a full prefix, e.g. --mirror https://example.com/https://github.com")
    return name.rstrip("/")


def _mirror_url(part: Part, mirror: str) -> str:
    """Prefix a mirror onto the GitHub URL, leaving everything else alone."""
    if not mirror:
        return part.url
    return part.url.replace(GITHUB, mirror.rstrip("/"), 1)


def _entry_path(part: Part, dest: Path) -> Path:
    """Where the adapter expects to find the part's entry point.

    A module entry can be either a package directory (``dtmd``) or a single
    module file (``cleaner.clean_md``), so accept both spellings before
    concluding it moved.
    """
    if part.kind == "script":
        return dest / part.entry
    top = dest / "src" if part.layout == "src" else dest
    base = top.joinpath(*part.entry.split("."))
    if base.is_dir():
        return base
    return base.with_suffix(".py")


def _pinned(dest: Path, part: Part) -> bool:
    """True when ``dest`` is checked out exactly at the pinned commit."""
    if not dest.is_dir():
        return False
    head = _git(["rev-parse", "HEAD"], cwd=dest)
    if head.returncode != 0:
        return False
    return head.stdout.strip() == part.commit


def _fetch(dest: Path, part: Part, mirror: str) -> str:
    """Fetch and check out the pinned commit. Returns "" on success, else a reason.

    Two attempts, because the fast one is not always allowed: GitHub serves
    ``fetch origin <sha>`` only for commits it considers reachable, which covers
    branch tips but not every historical commit. When the shallow fetch is
    refused, fall back to the branch with enough history to contain the pin.
    """
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = _mirror_url(part, mirror)

    if _git(["init", "-q", str(dest)]).returncode != 0:
        return "git init failed"
    if _git(["remote", "add", "origin", url], cwd=dest).returncode != 0:
        return "git remote add failed"

    shallow = _git(["fetch", "-q", "--depth", "1", "origin", part.commit], cwd=dest)
    if shallow.returncode == 0:
        _git(["checkout", "-q", "FETCH_HEAD"], cwd=dest)
        if _pinned(dest, part):
            return ""
        # The server answered, but with something other than the pin. Take the
        # branch tip instead and say so through _verify rather than pretending.
        _git(["fetch", "-q", "--depth", "1", "origin", part.branch], cwd=dest)
        _git(["checkout", "-q", "FETCH_HEAD"], cwd=dest)
        return "" if _pinned(dest, part) else "fetched but HEAD is not the pin"

    full = _git(["fetch", "-q", "origin", part.branch], cwd=dest)
    if full.returncode != 0:
        return "fetch failed: " + (full.stderr or full.stdout).strip()[:160]
    out = _git(["checkout", "-q", part.commit], cwd=dest)
    if out.returncode != 0:
        return f"checkout {part.commit[:8]} failed: " + (out.stderr or "").strip()[:160]
    return ""


def _verify(dest: Path, part: Part) -> str:
    """Confirm the entry point the adapter calls is actually there.

    This is the check that catches a part moving its own layout: the adapters
    hard-code ``python -m dtmd`` and ``app/crawl_all.py``, so a part that
    renames a package looks fine on disk and fails only at run time.
    """
    if not _pinned(dest, part):
        return "not at the pinned commit"
    entry = _entry_path(part, dest)
    if entry.exists():
        return ""
    return "entry point missing: " + str(entry.relative_to(repo_root()))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the five parts, pinned to known-good commits.")
    parser.add_argument("--check", action="store_true",
                        help="report what is present and what is missing; fetch nothing")
    parser.add_argument("--update", action="store_true",
                        help="re-fetch every part and re-apply its pin")
    parser.add_argument("--force", action="store_true",
                        help="discard existing copies and clone from scratch")
    parser.add_argument("--mirror", metavar="NAME_OR_URL", default="",
                        help="a preset name (e.g. gh-proxy) or a full URL prefix")
    args = parser.parse_args(argv)

    if shutil.which("git") is None:
        print("git was not found on PATH.")
        print("Install git first: https://git-scm.com/downloads")
        print("(On Windows, winget install Git.Git also works.)")
        return 2

    mirror = _resolve_mirror(args.mirror)
    root = parts_root()
    missing = [p for p in PARTS if not _pinned(root / p.name, p)]

    if args.check:
        print(f"parts root: {root}")
        for part in PARTS:
            if _pinned(root / part.name, part):
                print(f"  {part.name:<24} ok      ({part.commit[:8]})")
            else:
                why = ("not fetched yet" if not (root / part.name).is_dir()
                       else _verify(root / part.name, part))
                print(f"  {part.name:<24} MISSING ({part.commit[:8]})  <- {why}")
        print(f"{len(PARTS) - len(missing)}/{len(PARTS)} present")
        return 0 if not missing else 1

    if not args.update and not args.force and not missing:
        print(f"all {len(PARTS)} parts already at their pins. "
              "Use --update to re-fetch, --force to re-clone.")
        return 0

    todo = PARTS if (args.update or args.force) else missing
    failures = []
    for part in todo:
        dest = root / part.name
        action = "re-fetch" if (args.update or args.force) else "fetch"
        print(f"{action} {part.name} @ {part.commit[:8]}"
              + (f" via {mirror}" if mirror else ""))
        reason = _fetch(dest, part, mirror)
        if reason:
            failures.append((part, reason))
            print(f"  FAILED: {reason}")
            continue
        problem = _verify(dest, part)
        if problem:
            failures.append((part, problem))
            print(f"  FAILED: {problem}")
        else:
            print(f"  ok -> parts/{part.name}")

    if failures:
        print(f"\n{len(failures)} of {len(todo)} parts failed.")
        print("If the failure looks like a slow or blocked connection, retry with")
        print("--mirror gh-proxy (verified 2026-10-25; presets go stale, so pass a")
        print("full URL prefix instead if that one has gone too).")
        return 1
    print(f"\n{len(todo)} part(s) in place. Next: python scripts/setup_engines.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
