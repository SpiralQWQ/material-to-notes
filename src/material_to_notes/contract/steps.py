"""Single source of truth for the five pipeline steps.

Nothing else in the project may hard-code a step's name, the inputs it accepts,
or where it writes. Change a step here and the whole project follows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    """One hop of the pipeline."""

    id: str
    name: str
    tool: str
    accepts: tuple
    produces: tuple
    workdir_subdir: str
    optional: bool = False


STEPS = (
    Step(
        id="fetch",
        name="取材",
        tool="wkc",
        accepts=("terms", "links"),
        produces=("**/meta.json",),
        workdir_subdir="01_取材",
    ),
    Step(
        id="document",
        name="文档转md",
        tool="dtmd",
        accepts=("pdf", "docx", "pptx", "html"),
        # Deliberately loose: the contract is checked after every phase, and for a
        # book sliced into p{start}-{end} blocks the phase before merge has no
        # full.md at the dir root yet. Narrowing this would fail the sliced path.
        # Picking the *merged* one is the relay's job (RELAY in orchestrate/pipeline).
        produces=("**/full.md",),
        workdir_subdir="02_转md",
    ),
    Step(
        id="media",
        name="媒体转md",
        tool="m2m",
        accepts=("video", "audio", "album", "image"),
        produces=("{stem}_clean.md",),
        workdir_subdir="02_转md",
    ),
    Step(
        id="clean",
        name="清洗",
        tool="tce",
        accepts=("markdown", "text"),
        # One file per source, named after the source — two papers in one workdir
        # would both want "full.txt". This step's statistics are not an output file
        # at all: they go into _元数据/<名>.json (contract/metadata.py).
        produces=("{stem}.txt",),
        workdir_subdir="03_清洗",
        optional=True,
    ),
    Step(
        id="note",
        name="写笔记",
        tool="mre",
        accepts=("markdown",),
        # Named after its source too, so a workdir can hold several notes.
        produces=("*.md",),
        workdir_subdir="04_笔记",
    ),
)

_BY_ID = {s.id: s for s in STEPS}


def get_step(step_id: str) -> Step:
    """Return the step with this id; raise KeyError listing the known ids."""
    try:
        return _BY_ID[step_id]
    except KeyError:
        known = ", ".join(sorted(_BY_ID))
        raise KeyError(f"unknown step id: {step_id!r} (known: {known})") from None


def step_ids() -> tuple:
    """All step ids, in pipeline order."""
    return tuple(s.id for s in STEPS)


def steps_for(kind: str) -> tuple:
    """Steps that accept this input kind, in pipeline order."""
    return tuple(s for s in STEPS if kind in s.accepts)
