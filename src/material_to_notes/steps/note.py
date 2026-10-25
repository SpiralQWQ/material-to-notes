"""Adapter for mre (md-rewrite-engine): cleaned markdown to a teaching note.

We never run mre's own rewrite/scoring executors: per SOP §一 the note is written
by a sub-agent, so ``run`` here exists only for the smoke path. What this adapter
actually provides is the part's *paths and tools* — the content gate
(``scripts/gate_check.py``, used by ``gates/content.py``) and the in-note TOC
generator (``scripts/toc_gen.py``, used by ``refresh_tocs``).
"""

from __future__ import annotations

import sys
from pathlib import Path

from material_to_notes.contract import runner as R
from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as W

TOOL = "mre"
ENV_KEY = "MRE_DIR"
PART = "md-rewrite-engine"
MODULE = "md_rewrite_engine"
TOC_SCRIPT = Path("scripts") / "toc_gen.py"


def refresh_tocs(root, *, env=None, runner=None, python=None, timeout=120) -> tuple:
    """Regenerate every note's ``📑 本篇目录`` with the part's own ``toc_gen``.

    Called by the main conversation between "the agent wrote the note" and "run
    the gate". Doing it here (not in the writer's brief) matches the spec's own
    note: the TOC is a deterministic by-product of the headings —
    "脚本后处理自动生成，AI 无需手写".

    The part's ``--apply`` rebuilds an existing TOC, so the refresh is entirely
    its job; we only supply the absolute path and restore the file if it fails.
    (Until 2026-10-15 the part only *inserted* when no TOC was present, so this
    side stripped the old block first — and its line walk stopped before the
    block's own ``---`` terminator, leaving a stray ``---`` behind on every
    refresh. That duplicate is gone now that the part replaces the block.)
    """
    base = W.step_dir(root, _steps.get_step("note"))
    if not base.is_dir():
        return False, f"没有笔记目录: {base}"
    tool = R.part_tool(ENV_KEY, PART, env)
    script = Path(tool) / TOC_SCRIPT
    if not script.is_file():
        return False, f"toc 脚本缺失: {script}"
    notes = sorted(p for p in base.glob("*.md") if p.is_file())
    if not notes:
        return False, "没有笔记可补目录"

    details, ok = [], True
    for note in notes:
        original = note.read_text(encoding="utf-8", errors="replace")
        result = R.run_command(
            # 路径必须绝对：子进程 cwd 是零件仓库，相对路径会在那里被解析到别处。
            [python or sys.executable, str(script), R.abspath(note), "--apply"],
            cwd=tool, env=R.tool_env(tool, base=env), timeout=timeout, runner=runner,
        )
        if not result.ok:
            # 工具失败就不该留下半改的笔记：原样写回。
            note.write_text(original, encoding="utf-8")
        ok = ok and result.ok
        tail = (result.stdout or result.stderr or "").strip().splitlines()
        summary = tail[-1].strip() if tail else ""
        details.append(f"{note.name}: {'OK' if result.ok else 'FAIL'} {summary}")
    return ok, "; ".join(details)


def build_command(src_md, out_md, *, python=None) -> list:
    return [python or sys.executable, "-m", MODULE, R.abspath(src_md), "--output", R.abspath(out_md)]


def out_path(root, src_md, name=None):
    """Where this source's note belongs: 04_笔记/<名字>.md."""
    stem = name or W.safe_filename(W.source_name(src_md))
    return W.step_dir(root, _steps.get_step("note")) / f"{stem}.md"


def run(root, *, src_md, name=None, env=None, timeout=None, runner=None, python=None):
    step = _steps.get_step("note")
    tool = R.part_tool(ENV_KEY, PART, env)
    out_md = out_path(root, src_md, name)
    argv = build_command(src_md, out_md, python=python)
    return R.execute(
        step, argv, root, cwd=tool, env=R.tool_env(tool, base=env),
        timeout=timeout, runner=runner,
    )
