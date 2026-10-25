"""Adapter for tce (text-cleaning-engine): content-noise cleaning, one file at a time.

Two modes, chosen by what the material is:

  watermark (default)  ``clean_md <file> --output <path> --watermark-only``
      Strips channel watermarks only. Safe for markdown that a document or media
      pipeline already structured — headings, tables and formulas all survive.
  deep                 ``clean_md <file> --output <path>``
      The full rule set including the trafilatura gateway. Only right for
      noise-heavy web/OCR text; on MinerU markdown it deletes every HTML table
      and, without the gateway, every $$ formula block. Measured on a real
      28-page paper: trafilatura 1118->1 lines and <td> 18->0; plain $$ 88->0.

Whichever runs, the cleaned file is checked by ``structure_loss`` — a cleaning
that quietly eats the content is rejected rather than published. ``deep`` gets no
exemption: asking for the full rule set is not authorisation to lose content.
Losses are also recorded in the step's meta as ``structure_lost``.

The batch entry point is deliberately not used: it writes into tce's own repo.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from material_to_notes.contract import metadata as _meta
from material_to_notes.contract import runner as R
from material_to_notes.contract import steps as _steps
from material_to_notes.contract import validate as _validate
from material_to_notes.contract import workdir as W

TOOL = "tce"
ENV_KEY = "TCE_DIR"
PART = "text-cleaning-engine"
MODULE = "cleaner.clean_md"

# dtmd's embed_notes heads each embedded figure note with the image's sha256:
#     ## 插图笔记：<64 hex>
# That is our pipeline's internal identifier — the reader cannot use it, and it
# must not reach the deliverable. It also poisons mre's numeric reconciliation:
# the gate skips "very long pure numbers" but a hash fragments into ordinary
# numbers (01814, 0531994, …), which it then demands the note preserve. So
# whoever deletes the hash fails the gate. Neither side is wrong; the id simply
# should not be in the text we hand downstream.
# [ \t] rather than \s throughout: \s matches the newline too, so "\s*$" would
# swallow the line break and merge the heading with the next line — which the
# structure-fidelity gate then (correctly) rejects as a lost line.
_FIGURE_ID_HEADING = re.compile(r"^##[ \t]*插图笔记：[ \t]*[0-9a-fA-F]{32,}[ \t]*$", re.M)


def strip_internal_ids(text: str) -> tuple:
    """Drop our own figure-note identifiers from the text. Returns (text, count)."""
    cleaned, count = _FIGURE_ID_HEADING.subn("## 插图笔记", text)
    return cleaned, count


def build_command(src_file, out_file, *, deep=False, python=None) -> list:
    argv = [python or sys.executable, "-m", MODULE, R.abspath(src_file),
            "--output", R.abspath(out_file)]
    if not deep:
        argv.append("--watermark-only")
    return argv


def _stats(stdout: str) -> dict:
    """Keep only the statistics from tce's stdout summary.

    tce echoes the whole cleaned text in ``cleaned_text`` — the .txt file already
    holds it, so copying it into the record would double the run on disk.
    Unparseable output is truncated, never dumped.
    """
    raw = (stdout or "").strip()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {"ok": False, "raw_stdout": raw[:500]}
    if isinstance(data, dict):
        data.pop("cleaned_text", None)
        return data
    return {"ok": True, "stdout": str(data)[:500]}


def _relative(root, path) -> str:
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return Path(path).name


def run(root, *, src_file, name=None, deep=False, env=None, timeout=None, runner=None, python=None):
    step = _steps.get_step("clean")
    out = W.step_dir(root, step)
    # Keyed by the *source*, not by the user's display name: an intermediate is
    # internal, and letting a rename change it would leave the old file behind —
    # the next step globs this folder and would then see two materials where
    # there is one. The display name is applied where it matters, to the note.
    name = name or W.safe_filename(W.source_name(src_file))
    out_txt = out / f"{name}.txt"

    outcome = R.execute(
        step, build_command(src_file, out_txt, deep=deep, python=python), root,
        cwd=R.part_tool(ENV_KEY, PART, env),
        env=R.tool_env(R.part_tool(ENV_KEY, PART, env), base=env),
        timeout=timeout, runner=runner, check_outputs=False,
    )
    if not outcome.ok:
        _meta.record_step(root, name, step.id, ok=False, error=outcome.error,
                          outputs=[_relative(root, out_txt)])
        return outcome

    # Strip our own figure-note ids before anything downstream sees the text.
    stripped = 0
    try:
        raw = out_txt.read_text(encoding="utf-8", errors="replace")
        text, stripped = strip_internal_ids(raw)
        if stripped:
            out_txt.write_text(text, encoding="utf-8")
    except OSError as exc:
        _meta.record_step(root, name, step.id, ok=False, error=f"internal-id strip: {exc}")
        return R.StepOutcome(step.id, False, outcome.run, error=f"internal-id strip: {exc}")

    # The fidelity gate applies in both modes and `deep` is no exemption: a step
    # that reports success while gutting the document is the exact failure this
    # adapter exists to catch. The loss is recorded, so it stays visible when the
    # failure gets retried or handed to the user.
    try:
        lost = tuple(_validate.structure_loss(
            Path(src_file).read_text(encoding="utf-8", errors="replace"),
            out_txt.read_text(encoding="utf-8", errors="replace"),
        ))
    except OSError as exc:
        _meta.record_step(root, name, step.id, ok=False, error=f"structure check: {exc}")
        return R.StepOutcome(step.id, False, outcome.run, error=f"structure check: {exc}")

    stats = _stats(outcome.run.stdout)
    if stripped:
        stats["internal_ids_stripped"] = stripped
    if lost:
        stats["structure_lost"] = list(lost)
    _meta.record_step(root, name, step.id, ok=not lost, stats=stats,
                      outputs=[_relative(root, out_txt)],
                      error=("structure collapsed while cleaning: " + "; ".join(lost)) if lost else "")
    if lost:
        return R.StepOutcome(step.id, False, outcome.run,
                             error="structure check: structure collapsed while cleaning: "
                                   + "; ".join(lost))

    try:
        _validate.check_step_output(root, step)
    except _validate.ContractError as exc:
        return R.StepOutcome(step.id, False, outcome.run, error=str(exc))
    return R.StepOutcome(step.id, True, outcome.run)
