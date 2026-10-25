# -*- coding: utf-8 -*-
"""Enrich only the images a document actually references, then embed them.

dtmd's own ``enrich_dir()`` walks every file in ``images/``. On a real 28-page
paper that is 61 images while only 15 are referenced by ``full.md`` — 46 paid
vision calls that embed into nothing. This script selects the referenced subset
and calls dtmd's own per-image function, so dtmd is not modified and no logic
is re-implemented here.

Run it as a subprocess with the dtmd repo's ``src`` on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

from dtmd.convert.enrich import count_images, embed_notes, enrich_image

try:  # reuse dtmd's own extension list when it exposes one
    from dtmd.convert.enrich import IMG_EXTS  # type: ignore
except ImportError:  # pragma: no cover - fallback only
    IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")

# Same shape dtmd uses inside embed_notes(), kept local so we only match real refs.
REFERENCE = re.compile(r"!\[[^\]]*\]\((?:[^)]*/)?images/([^)\s]+)\)")


def referenced_images(root: str) -> set:
    """Basenames of every image referenced by any full.md under root."""
    names = set()
    for base, _dirs, files in os.walk(root):
        if "full.md" not in files:
            continue
        path = os.path.join(base, "full.md")
        with open(path, encoding="utf-8", errors="replace") as handle:
            names.update(REFERENCE.findall(handle.read()))
    return names


def snapshot_full_md(root: str) -> list:
    """Copy every full.md to full.md.bak before embed overwrites it in place.

    Whoever destroys a file keeps the original, so this lives here and not only
    in the caller. An existing snapshot is never replaced: the first one is the
    true pre-enrich original.
    """
    made = []
    for base, _dirs, files in os.walk(root):
        if "full.md" not in files:
            continue
        live = os.path.join(base, "full.md")
        snapshot = live + ".bak"
        if not os.path.exists(snapshot):
            shutil.copy2(live, snapshot)
            made.append(snapshot)
    return made


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="enrich_subset", description=__doc__)
    parser.add_argument("dir", help="the *_mineru directory")
    parser.add_argument("--no-glm", action="store_true", help="OCR only, no vision model")
    parser.add_argument("--delay", type=float, default=5.0, help="seconds between vision calls")
    parser.add_argument("--limit", type=int, default=0,
                        help="enrich at most N referenced images (0 = all); for pilots")
    args = parser.parse_args(argv)

    referenced = referenced_images(args.dir)
    info = count_images(args.dir)
    stats = {
        "dir": args.dir,
        "images_present": info["count"],
        "images_referenced": len(referenced),
        "done": 0, "skipped": 0, "empty": 0, "not_referenced": 0, "over_limit": 0,
    }

    snapshot_full_md(args.dir)

    for images_dir in info["dirs"]:
        for name in sorted(os.listdir(images_dir)):
            if not name.lower().endswith(IMG_EXTS):
                continue
            if name not in referenced:
                stats["not_referenced"] += 1
                continue
            if args.limit and stats["done"] + stats["skipped"] >= args.limit:
                stats["over_limit"] += 1
                continue
            outcome = enrich_image(images_dir, name, glm=not args.no_glm, delay=args.delay)
            stats[outcome] = stats.get(outcome, 0) + 1

    stats["embed"] = embed_notes(args.dir)
    json.dump(stats, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
