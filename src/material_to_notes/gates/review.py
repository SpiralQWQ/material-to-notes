"""The checklist handed to the review agent — the AI-judged part.

Machine gates decide pass/fail on their own. This is what a *fresh* reviewer is
asked to look at, and anything it flags must surface on the progress sheet —
soft means "does not block", never "may be dropped".
"""

from __future__ import annotations

from material_to_notes.contract import steps as _steps

_PER_STEP = {
    "fetch": (
        "每个数据文件是否都有配套 meta.json，且字段可解析",
        "有没有半截文件（.part / .tmp / .crdownload）",
    ),
    "document": (
        "full.md 与源文档是否对得上（页数、章节、图片引用）",
        "有没有整章丢失或明显错位",
    ),
    "media": (
        "时间轴是否连续、有无整段丢失",
        "画面文字与语音是否对得上",
    ),
    "clean": (
        "清洗前后内容量是否骤降（保留率异常）",
        "有没有把教学内容一起洗掉",
    ),
    "note": (
        "六件套是否齐全、费曼示范是否真的换了角度",
        "示范角度有没有与文末自测题撞题（问法不同但答案相同也算撞）",
        "元信息里「已写入正文」类的声称，逐条回正文搜关键词，能不能真找到对应内容",
        "有没有元评论（'根据原文' / '我重排了'）混进正文",
    ),
}

GLOBAL = (
    ("G1", "语义保真：关键事实点有没有被改写或丢失（对照源逐点核）"),
    ("G2", "幻觉检测：笔记里每个事实点必须在源里有出处；凭空添加即问题"),
    ("G4", "成本追踪：记录 token / 耗时 / 调用次数"),
)


def checklist(step_id: str) -> dict:
    _steps.get_step(step_id)  # raises for an unknown step
    return {"step": step_id, "specific": _PER_STEP.get(step_id, ()), "global": GLOBAL}


def render(step_id: str, *, flagged=()) -> str:
    data = checklist(step_id)
    lines = [f"# 审核检查单 · {step_id}", "", "## 本步专查"]
    lines += [f"- {item}" for item in data["specific"]] or ["- （无）"]
    lines += ["", "## 全局必查"]
    lines += [f"- [{code}] {text}" for code, text in data["global"]]
    if flagged:
        lines += ["", "## 已标记（必须浮到总进度单，需人过目）"]
        lines += [f"- {item}" for item in flagged]
    lines += ["", "> 只报告，不修改产物；每条给证据；没找到就写「未发现」。", ""]
    return "\n".join(lines)


def collect_flags(entries) -> tuple:
    """Keep only the truthy entries — flagged items must not be silently dropped."""
    return tuple(entry for entry in entries if entry)
