"""Adapter for m2m (media-to-markdown): video / audio / album / image to timeline markdown.

m2m writes outside the step dir and exposes no flag to move its output, so we run
it with cwd set to the step dir and lift the finished ``*_clean.md`` up; its
intermediate files stay behind as evidence. Where it writes depends on the input:

  video / audio file   ``<cwd>/output/cache/<name>/<name>_clean.md``
  image file(s)        ``<cwd>/output/cache/图片/<first image>_clean.md``
  directory            ``<dir>/images_notes/<image>.md``, one per image

The last one is why a directory cannot simply be handed over. m2m folds every
image *file* it is given into one album md, but a directory's images it writes as
one md per image beside the sources — never a ``_clean.md`` for us to collect. So
a directory is expanded into its image files and m2m's own album assembly does the
merging; the result is then keyed to the directory's name, which is what the
material was staged under.

That expansion also decides the only shape we can support: because m2m merges all
image files into a single album, a directory alongside other materials would turn
two materials into one note with nothing reporting it. We stop and ask instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

from material_to_notes.contract import runner as R
from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as W

TOOL = "m2m"
ENV_KEY = "M2M_DIR"
PART = "media-to-markdown"
MODULE = "media_to_markdown"

# The same list m2m classifies by, so a directory is expanded exactly as it
# would have walked it.
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")


def image_files(directory) -> list:
    """The image files directly inside ``directory``, in name order.

    Not recursive: m2m's own directory branch reads its folder the same way, so
    a nested folder would be dropped there too.
    """
    return sorted((p for p in Path(directory).iterdir()
                   if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
                  key=lambda p: p.name)


def build_command(sources, *, glm="no", python=None) -> list:
    argv = [python or sys.executable, "-m", MODULE]
    argv += [R.abspath(s) for s in sources]
    argv += ["--glm", glm]
    return argv


def _refused(step, reason):
    """A step that stops before running anything — the log must not claim a call."""
    return R.StepOutcome(step.id, False, R.RunResult(argv=(), returncode=-1, error=reason),
                         error=reason)


def run(root, *, sources, glm="no", env=None, timeout=None, runner=None, python=None):
    step = _steps.get_step("media")
    out = W.step_dir(root, step)

    srcs = [Path(s) for s in sources]
    album = [p for p in srcs if p.is_dir()]
    name = ""  # the album's own name, empty for every other kind of input
    if album:
        if len(srcs) > 1:
            return _refused(step, "media: 目录素材只能单独跑 —— m2m 会把传给它的所有图片文件"
                                  "合成一份图集，和别的素材一起传会让两份素材悄悄变成一份笔记"
                                  "（停下问用户）")
        files = image_files(album[0])
        if not files:
            return _refused(step, f"media: 目录里没有图片（{album[0]}）——停下问用户")
        name = album[0].name
        srcs = files
    elif len(srcs) > 1 and all(p.suffix.lower() in IMAGE_EXTS for p in srcs):
        # m2m folds all image files into one album in argv order, so the note's
        # block order would follow the caller's typing order. Sort, so a direct
        # multi-image run matches the folder-as-album run it mirrors in name and
        # in body — only the name differs, by design.
        srcs = sorted(srcs, key=lambda p: p.name)

    def collect():
        cache = out / "output" / "cache"
        if cache.is_dir():
            for md in cache.rglob("*_clean.md"):
                target = out / md.name
                if md.resolve() != target.resolve():
                    md.replace(target)
        if name:
            produced = out / f"{W.source_name(srcs[0])}_clean.md"
            wanted = out / f"{name}_clean.md"
            if produced.is_file() and produced.resolve() != wanted.resolve():
                produced.replace(wanted)

    argv = build_command(srcs, glm=glm, python=python)
    return R.execute(
        step, argv, root, cwd=out, env=R.tool_env(R.part_tool(ENV_KEY, PART, env), base=env),
        timeout=timeout, runner=runner, collect=collect,
    )
