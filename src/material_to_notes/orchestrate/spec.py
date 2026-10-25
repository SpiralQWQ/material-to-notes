# -*- coding: utf-8 -*-
"""The note brief is *read out of the part*, not transcribed from it.

Why this module exists (2026-10-15, ``docs/补丁重构计划报告.md`` §四):

Seven notes came out in a shape this project invented. The brief looked
reasonable, but it was a hand-written description of the part's style written
long before anyone opened the part's own spec — so nothing in the pipeline ever
compared the two, and the drift only surfaced when the part's gate parsed our
notes and found zero knowledge points. A transcription drifts silently; a
projection cannot.

So every fact the writer is told about the note's *shape* now comes from the
part at dispatch time:

* ``configs/note_style_spec.yaml`` — frontmatter fields and their order, the
  body columns and their order, the six pieces, the demo-count range, and where
  the full transcript goes;
* ``scripts/gate_check.py`` — the labels and the heading shape the content gate
  actually parses (read with :mod:`ast`, so the file is never executed).

If the part changes either file, the next sheet changes with it. If neither can
be read, :func:`note_brief` raises instead of shipping a sheet with a guessed
shape — a guessed shape is the exact failure this module exists to prevent.

Two things are deliberately *not* derived, and both are covered by tests that
would fail if they stopped being true:

* the exact wording of each column heading — the spec states those in YAML
  **comments** (``# ❓ 费曼思考题（按重要程度配题）``), which describe the column
  rather than prescribe its text; ``_COLUMN_HEADING`` records the wording the
  seven notes already in this project use;
* the knowledge-point heading template — ``_KP_TEMPLATE`` is a template whose
  instantiation is asserted to match the part's own ``_KP_HEADING`` pattern.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

from material_to_notes.contract import runner as R

PART = "md-rewrite-engine"
ENV_KEY = "MRE_DIR"
SPEC_REL = ("src", "md_rewrite_engine", "configs", "note_style_spec.yaml")
GATE_REL = ("scripts", "gate_check.py")

# ── 规范 structure 里的栏目 key → 正文那一行怎么写 ─────────────────────────
# 这是**命名先例**（本项目已入库的 7 份笔记就是这么写的），不是规范事实：
# 什么写法算合规由门禁决定，`tests/unit/test_dispatch_brief.py` 会断言门禁确实认它。
_COLUMN_HEADING = {
    "summary": "> 一句话总结：…",
    "overview": "## 📚 概述",
    "toc": "## 📑 本篇目录",
    "key_points": "## 🧠 核心知识点",
    "glossary": "## 📖 专业词汇表",
    "feynman": "## ❓ 自测题",
    "meta_footer": "## 📌 元信息",
}

# 规范里 `appendix: full_original_external`：这些栏目**不进正文**。
_EXTERNAL_COLUMNS = {"transcript"}

# 知识点小节形状：模板 + 用来验证它的那个实例（见 test_brief_matches_the_parts_parser）。
_KP_TEMPLATE = "### 知识点 <编号> · <标题>"
_KP_EXAMPLE = "### 知识点 2.1 · 甲与乙\n\n- **定义**：甲。\n"
_KP_OLD_SHAPE = "## 知识点一 甲与乙\n\n- **定义**：甲。\n"
_DEMO_TEMPLATE = "- **❓ 示范角度**："


class SpecUnavailable(RuntimeError):
    """The part's spec or gate could not be read — there is no brief to hand out."""


def part_root(env=None) -> Path:
    return Path(R.part_tool(ENV_KEY, PART, env))


def spec_path(env=None) -> Path:
    return part_root(env).joinpath(*SPEC_REL)


def gate_path(env=None) -> Path:
    return part_root(env).joinpath(*GATE_REL)


# ── 读规范文件 ────────────────────────────────────────────────────────────

_ITEM = re.compile(r"^\s*-\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:#\s*(.*))?$")
_SECTION = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?:#.*)?$")


def _commented_items(text: str, section: str) -> list:
    """``- key  # 说明`` 这类条目，按出现顺序返回 ``[(key, 说明), ...]``。

    YAML 的注释在 ``safe_load`` 之后就不见了，而这些注释正是规范对每个字段/
    栏目唯一的说明文字，所以这里直接按行读原文件。
    """
    items, current = [], None
    for line in text.splitlines():
        head = _SECTION.match(line)
        if head:
            current = head.group(1)
            continue
        entry = _ITEM.match(line)
        if entry and current == section:
            items.append((entry.group(1), (entry.group(2) or "").strip()))
    return items


def _comment_above(text: str, key: str) -> str:
    """The ``#`` comment block sitting immediately above ``<key>:`` in the spec.

    Some of the spec's most load-bearing guidance lives in a comment rather than
    in a value — e.g. what the demo angles are *for*: "教学留白：给 AI 考察线索，
    AI 可自行展开，**不写满教学稿**". Reading it out keeps that guidance in the
    brief without transcribing it here (a transcription is what drifts).
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}\s*:", line):
            out = []
            j = i - 1
            while j >= 0 and lines[j].lstrip().startswith("#"):
                out.insert(0, lines[j].lstrip().lstrip("#").strip())
                j -= 1
            return " ".join(out).strip()
    return ""


def feynman_policy(spec: dict) -> str:
    """What the spec says the demo angles are FOR (its own wording, or "")."""
    return _comment_above(spec["text"], "feynman_per_kp")


def load_spec(env=None) -> dict:
    """The part's note spec: raw text, parsed YAML, and comment-carried labels."""
    path = spec_path(env)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecUnavailable(f"读不到零件规范 {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise SpecUnavailable(f"零件规范不是合法 YAML（{path}）: {exc}") from exc
    return {"path": path, "text": text, "yaml": data,
            "frontmatter": _commented_items(text, "frontmatter"),
            "structure": _commented_items(text, "structure"),
            "density": _commented_items(text, "info_density")}


def frontmatter_fields(spec: dict) -> list:
    """The eight field names, in the order the spec fixes them."""
    fields = [key for key, _ in spec["frontmatter"]]
    if not fields:
        raise SpecUnavailable("规范里 frontmatter 一节是空的，无法派生字段表")
    return fields


def columns(spec: dict) -> list:
    """The body columns that belong in the note, in order: ``[(key, 那一行怎么写), ...]``。

    规范新增栏目而我们不知道该写成什么标题时**直接报错**——静默跳过正是"漏读规范"
    的老路。
    """
    out = []
    for key, _comment in spec["structure"]:
        if key in _EXTERNAL_COLUMNS:
            continue
        if key not in _COLUMN_HEADING:
            raise SpecUnavailable(
                f"规范新增了栏目 `{key}`，派活单还不知道该写成什么标题——"
                f"补 spec.py 的 _COLUMN_HEADING（并确认门禁认它）再派活")
        out.append((key, _COLUMN_HEADING[key]))
    if not out:
        raise SpecUnavailable("规范里 structure 一节是空的，无法派生正文章节表")
    return out


def pieces(spec: dict) -> list:
    """六件套的**标签写法**（定义 / 通俗类比 / …），取自规范 info_density 的注释。"""
    labels = [comment for _key, comment in spec["density"] if comment]
    if not labels:
        raise SpecUnavailable("规范里 info_density 一节是空的，无法派生六件套标签")
    return [text.split("（")[0].split("/")[0].strip() for text in labels]


def feynman_range(spec: dict) -> str:
    value = spec["yaml"].get("feynman_per_kp")
    if value is None:
        raise SpecUnavailable("规范里没有 feynman_per_kp，无法派生示范角度数量")
    return str(value)


def transcript_policy(spec: dict) -> str:
    return str(spec["yaml"].get("appendix", ""))


# ── 读门禁脚本（不执行它）────────────────────────────────────────────────

def gate_constants(env=None) -> dict:
    """Literals assigned in the part's gate script: plain assigns and ``re.compile``.

    Read with :mod:`ast` so importing (and therefore running) part code stays out
    of our process; a gate we cannot read is a hard error, not a fallback.
    """
    path = gate_path(env)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecUnavailable(f"读不到零件门禁 {path}: {exc}") from exc
    out = {}
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SpecUnavailable(f"零件门禁不是合法 Python（{path}）: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
            args = [a for a in value.args if isinstance(a, ast.Constant)]
            if args:
                out[target.id] = args[0].value      # re.compile("…") → "…"
            continue
        try:
            out[target.id] = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            continue
    return out


def gate_six_labels(env=None) -> tuple:
    labels = gate_constants(env).get("_SIX")
    if not labels:
        raise SpecUnavailable("零件门禁里找不到 _SIX（六件套标签），派活单没法定六件套写法")
    return tuple(labels)


def gate_kp_pattern(env=None) -> str:
    pattern = gate_constants(env).get("_KP_HEADING")
    if not pattern:
        raise SpecUnavailable("零件门禁里找不到 _KP_HEADING，派活单没法定知识点标题形状")
    return pattern


def gate_feynman_marks(env=None) -> str:
    pattern = gate_constants(env).get("_FEYNMAN_MARK")
    if not pattern:
        raise SpecUnavailable("零件门禁里找不到 _FEYNMAN_MARK，派活单没法定示范角度怎么写")
    return pattern


_REGEX_FLAGS = {"S": re.S, "DOTALL": re.S, "M": re.M, "MULTILINE": re.M,
                "I": re.I, "IGNORECASE": re.I, "X": re.X, "VERBOSE": re.X}


def _flag_value(node: ast.AST) -> int:
    """``re.S`` / ``re.S | re.M`` → the int flags; anything else → 0."""
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "re"):
        return _REGEX_FLAGS.get(node.attr, 0)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flag_value(node.left) | _flag_value(node.right)
    return 0


def gate_kp_flags(env=None) -> int:
    """The flags the gate passes wherever it applies ``_KP_HEADING``.

    The pattern alone is not the contract: the gate calls
    ``re.finditer(_KP_HEADING, note_text, re.S)``, and without ``re.S`` the
    pattern does not even match its own example. Read from the call site so the
    flags cannot rot away from the pattern.
    """
    path = gate_path(env)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecUnavailable(f"读不到零件门禁 {path}: {exc}") from exc
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == "re"):
            continue
        if any(isinstance(a, ast.Name) and a.id == "_KP_HEADING" for a in node.args):
            flags = 0
            for arg in node.args:
                flags |= _flag_value(arg)
            return flags
    raise SpecUnavailable("零件门禁里找不到使用 _KP_HEADING 的调用点，拿不到它的匹配标志")


# ── 拼派活单正文 ──────────────────────────────────────────────────────────

def shape_lines(env=None) -> tuple:
    """The shape half of the note brief, built from the part right now."""
    spec = load_spec(env)
    fields = frontmatter_fields(spec)
    cols = columns(spec)
    labels = pieces(spec)
    six = gate_six_labels(env)

    lines = [
        f"**笔记形状照零件的规范来**（`{spec['path'].name}`，就在 `{_short(spec['path'])}`）——"
        "本流水线不另立标准；下面几条都是**派活时从那份规范里现读出来的**，不是手抄的：",
        f"  ① **frontmatter 固定 {len(fields)} 字段、顺序不变**："
        + " / ".join(f"`{name}`" for name in fields) + "。",
        f"  ② **正文 {len(cols)} 栏，按此顺序**：" + " → ".join(heading for _key, heading in cols) + "。"
        "（`toc` 那一栏由脚本自动生成，你可留空；完整原文按规范外置，正文不放。）",
        f"  ③ **每个知识点写成** `{_KP_TEMPLATE}`（编号形如 `2.1`，标题前用 `·` 分隔），"
        f"节内六件套各写成一行粗体标签：" + " ".join(f"`- **{text}** …`" for text in labels) + "；"
        f"门禁按 " + " / ".join(f"`{label}`" for label in six) + " 找它们，**别换同义词**。",
        f"  ④ **费曼示范写在知识点内部**，作为第七项：`{_DEMO_TEMPLATE}` 后接 "
        f"**{feynman_range(spec)} 个角度**，用圈数字 ① ② ③ ④ ⑤ 标号（门禁按这些标号计数），"
        "角度从「复述 / 类比 / 应用 / 挑错」里选、**必须真的不同**。"
        + (f"规范的定位是「**{feynman_policy(spec)}**」——" if feynman_policy(spec) else "")
        + "**所以每条只写一两句「从哪个角度考自己」的线索，不要把概念再讲一遍**："
        "`通俗类比` 那一栏才是把概念讲明白的地方，示范角度**不许复述它**，"
        "**也不许复述 `原理` / `易错点` 里已经说过的话**。"
        "（写完之后逐点自检：这条示范角度有没有提供「原文里没有的新信息」？没有就是重复，删短或换角度。）",
        "事实信息（数字、公式、代码、专名）原样保留；源里没有的内容不许添加。",
    ]
    return tuple(lines)


def _short(path: Path) -> str:
    """A repo-relative spelling when we are inside the repo, else the absolute path."""
    try:
        return path.relative_to(Path(__file__).resolve().parents[3]).as_posix()
    except ValueError:
        return str(path)


__all__ = [
    "SpecUnavailable", "part_root", "spec_path", "gate_path", "load_spec",
    "frontmatter_fields", "columns", "pieces", "feynman_range", "feynman_policy",
    "transcript_policy",
    "gate_constants", "gate_six_labels", "gate_kp_pattern", "gate_kp_flags",
    "gate_feynman_marks", "shape_lines",
]
