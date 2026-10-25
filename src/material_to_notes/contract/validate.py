"""Validate that a step's output matches the contract.

Deterministic checks only: existence, non-emptiness, basic shape. Content
quality belongs to the gate layer, not here.
"""

from __future__ import annotations

import re
from pathlib import Path


class ContractError(Exception):
    """A step's output does not satisfy the contract."""


_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S", re.M)
_CODE_FENCE = re.compile(r"^\s*```", re.M)

# How much of each structural marker must survive a cleaning pass.
RETAIN_RATIO = 0.9


def _hits(base: Path, pattern: str) -> list:
    return [p for p in base.glob(pattern) if p.is_file()]


def check_step_output(root, step, *, min_bytes: int = 1) -> None:
    """Raise ContractError if any declared output of ``step`` is missing or empty.

    A declared output is one of:
      - a literal path relative to the step dir (``full.md``);
      - a directory, written with a trailing slash (``images/``);
      - a glob, when it contains ``*`` or the ``{stem}`` placeholder
        (``{stem}_clean.md``), matched relative to the step dir.
    """
    base = Path(root) / step.workdir_subdir
    if not base.is_dir():
        raise ContractError(f"step {step.id!r}: missing output dir {base}")

    for name in step.produces:
        if "*" in name or "{stem}" in name:
            pattern = name.replace("{stem}", "*")
            found = _hits(base, pattern)
            if not found:
                raise ContractError(f"step {step.id!r}: nothing matches {name!r} in {base}")
            if all(p.stat().st_size < min_bytes for p in found):
                raise ContractError(f"step {step.id!r}: every match of {name!r} is empty")
            continue

        target = base / name
        if name.endswith("/"):
            if not target.is_dir():
                raise ContractError(f"step {step.id!r}: missing dir {name!r}")
            continue
        if not target.is_file():
            raise ContractError(f"step {step.id!r}: missing file {name!r}")
        if target.stat().st_size < min_bytes:
            raise ContractError(f"step {step.id!r}: empty file {name!r}")


def structure_profile(text: str) -> dict:
    """Counts of the markers that must survive a cleaning pass."""
    return {
        "lines": text.count("\n"),
        "headings": len(_HEADING.findall(text)),
        "formulas": text.count("$$"),
        "table_cells": text.count("<td"),
        "code_fences": len(_CODE_FENCE.findall(text)),
    }


def structure_loss(before: str, after: str, *, ratio: float = RETAIN_RATIO) -> list:
    """Structural markers that did not survive, as ``"name src->cleaned"`` strings.

    A cleaning tool that exits 0 while deleting every table, formula or heading
    is worse than one that crashes: the loss is invisible. Callers treat a non-empty
    result as a failed step. Markers absent upstream are skipped, so this never
    reports the loss of something there was none of to begin with.
    """
    source = structure_profile(before)
    cleaned = structure_profile(after)
    return [f"{name} {src}->{cleaned[name]}"
            for name, src in source.items()
            if src and cleaned[name] < src * ratio]
