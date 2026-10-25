"""Retry accounting and the failure hand-off sheet.

A failing step is retried a bounded number of times, then the run stops and
hands off to a human. Nothing here edits code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from material_to_notes.contract import workdir as W

DEFAULT_MAX_ATTEMPTS = 3


@dataclass
class Attempts:
    """Per-step attempt counter. Each step's budget is independent."""

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    counts: dict = field(default_factory=dict)

    def record(self, step_id: str) -> int:
        self.counts[step_id] = self.counts.get(step_id, 0) + 1
        return self.counts[step_id]

    def used(self, step_id: str) -> int:
        return self.counts.get(step_id, 0)

    def exhausted(self, step_id: str) -> bool:
        return self.used(step_id) >= self.max_attempts


@dataclass(frozen=True)
class Failure:
    step: str
    error: str
    attempts: int
    artifacts: tuple = ()


def render(failure: Failure) -> str:
    """The hand-off sheet: the same four elements, always in this order."""
    artifacts = "、".join(str(a) for a in failure.artifacts) or "（尚无产物）"
    return "\n".join([
        "# 失败交班单",
        "",
        f"- 卡在哪步：{failure.step}",
        f"- 报什么错：{failure.error}",
        f"- 试过什么：已尝试 {failure.attempts} 次，仍未通过",
        f"- 产物在哪：{artifacts}",
        "",
        "> 已停下等你检查。禁止自行修改代码。",
        "",
    ])


def write(root, failure: Failure) -> Path:
    path = Path(root) / W.FAILURE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(failure), encoding="utf-8")
    return path


def clear(root) -> bool:
    """Remove a stale hand-off sheet. True when one was there.

    A sheet left over from an earlier run contradicts the progress sheet that
    the current run just wrote — the workdir would say "clean failed" and
    "clean done" at the same time, and both the next agent and the human read
    these files. The two sheets must agree on whether the run stopped.
    """
    path = Path(root) / W.FAILURE_FILE
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True
