"""Machine gates: the deterministic checks, with raw evidence kept.

Keeping the raw lines matters: the main conversation judges from evidence, not
from any agent's summary of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from material_to_notes.contract import steps as _steps
from material_to_notes.contract import validate as _validate
from material_to_notes.contract import workdir as _workdir

_TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".csv"}


@dataclass(frozen=True)
class GateResult:
    step: str
    passed: bool
    checks: tuple
    raw: str = ""

    def failed(self) -> tuple:
        return tuple(name for name, ok, _ in self.checks if not ok)


def _text_files(base: Path) -> list:
    if not base.is_dir():
        return []
    return [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES]


def _empty_files(base: Path) -> list:
    if not base.is_dir():
        return []
    return [p.name for p in base.rglob("*") if p.is_file() and p.stat().st_size == 0]


def check(step_id: str, root) -> GateResult:
    """Run every deterministic check for one step; report all of them."""
    step = _steps.get_step(step_id)
    base = _workdir.step_dir(root, step)
    checks = []

    try:
        _validate.check_step_output(root, step)
        checks.append(("output-contract", True, "declared outputs present and non-empty"))
    except _validate.ContractError as exc:
        checks.append(("output-contract", False, str(exc)))

    files = _text_files(base)
    bad = []
    for path in files:
        try:
            path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError) as exc:
            bad.append(f"{path.name}: {exc}")
    checks.append(("utf8-decodable", not bad, "; ".join(bad) or f"{len(files)} text files ok"))

    empties = _empty_files(base)
    checks.append(("no-empty-files", not empties, "; ".join(empties) or "no zero-byte files"))

    raw = "\n".join(f"[{'PASS' if ok else 'FAIL'}] {step_id}/{name}: {detail}"
                    for name, ok, detail in checks)
    return GateResult(step_id, all(ok for _, ok, _ in checks), tuple(checks), raw)


def check_all(root, chain) -> tuple:
    return tuple(check(step_id, root) for step_id in chain)
