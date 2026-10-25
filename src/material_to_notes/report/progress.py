"""Per-step progress lines and the final progress sheet."""

from __future__ import annotations

from pathlib import Path

from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as _workdir

LABEL = {"done": "完成", "skipped": "跳过", "failed": "失败", "blocked": "受阻"}


def line(step_id: str, status: str) -> str:
    """The one-line progress message for a step."""
    return f"[{LABEL.get(status, status)}] {step_id}"


def artifacts(root, step_id: str) -> tuple:
    """Files a step actually produced, as workdir-relative paths."""
    base = _workdir.step_dir(root, _steps.get_step(step_id))
    if not base.is_dir():
        return ()
    return tuple(sorted(p.relative_to(root).as_posix() for p in base.rglob("*") if p.is_file()))


def build(records, root) -> str:
    """The final progress sheet: one row per step, with where its output went.

    A failed step's row says so instead of listing files: whatever is in that
    directory may be left over from an earlier run, and presenting it as this
    run's output is how stale data quietly reaches the next step.
    """
    lines = ["# 总进度单", "", "| 步骤 | 状态 | 产物 |", "|---|---|---|"]
    for record in records:
        label = LABEL.get(record.status, record.status)
        if record.status in ("done", "skipped"):
            found = artifacts(root, record.step)
            if record.status == "skipped" and found:
                # "跳过"孤零零一个词会被读成"这一步没做"；它的意思其实是
                # "上一轮做过、本轮输入没变所以没重跑"。产物就在旁边，别让读者猜。
                label = f"{LABEL['done']}（本轮未重跑）"
            listing = "、".join(found) if found else "（无）"
        else:
            leftover = artifacts(root, record.step)
            listing = (f"（本步未产出；目录里有 {len(leftover)} 个上轮遗留文件，不可信）"
                       if leftover else "（无）")
        lines.append(f"| {record.step} | {label} | {listing} |")
    lines.append("")
    return "\n".join(lines)


def inconsistent(records, root) -> tuple:
    """Steps marked done but with no artifact on disk — the sheet must match reality."""
    bad = []
    for record in records:
        if record.status == "done" and not artifacts(root, record.step):
            bad.append(record.step)
    return tuple(bad)


def with_note_row(sheet: str, root, step_id: str) -> str:
    """Add (or refresh) the note step's row in an existing progress sheet.

    The note is written by an agent, not by ``pipeline step``, so the sheet built
    from a run's records never has a row for it — and the sheet then contradicts
    the disk, which SOP §六 forbids. The main conversation certifies the note by
    running ``pipeline gate <workdir> note``; that is the moment the row goes in.
    """
    found = artifacts(root, step_id)
    row = f"| {step_id} | {LABEL['done']} | " + ("、".join(found) if found else "（无）") + " |"
    lines = [ln for ln in sheet.splitlines() if not ln.startswith(f"| {step_id} |")]
    last = max((i for i, ln in enumerate(lines) if ln.startswith("| ")), default=len(lines) - 1)
    lines.insert(last + 1, row)
    return "\n".join(lines) + "\n"


def write(root, text: str) -> Path:
    path = Path(root) / _workdir.PROGRESS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
