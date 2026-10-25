"""Content gates for the note step: the checks the generic gate cannot make.

``machine.check`` only asks "is there an output file, is it decodable, is it
non-empty" for every step. The note has to satisfy more than that before it can
be delivered, and until now nothing in this pipeline checked it — the content
gate lived in mre and only the writing agent ran it, which means its verdict
was a self-report.

Two halves, deliberately not overlapping:

  structure (here, pure Python)  frontmatter / 篇内目录 / 专业词汇表 / 元信息
      Cheap to run and dependency-free. Covers the parts of the acceptance
      standard mre knows nothing about.
  mre's own gate (subprocess)    六件套 / 费曼示范 / 机械对账 / 丰富度
      Already implemented and battle-tested in the part; re-implementing it here
      would give two sources of truth that drift. We shell out instead, and we
      never pass ``--score`` (that is the third-party GLM grader, dropped by the
      execution model).

A gate that cannot run must never report green: a missing mre, a missing source,
or a crashed checker is a FAIL with the reason attached, not a silent pass.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from material_to_notes.contract import metadata as _meta
from material_to_notes.contract import runner as R
from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as _workdir
from material_to_notes.gates.machine import GateResult

MRE_ENV_KEY = "MRE_DIR"
MRE_PART = "md-rewrite-engine"
MRE_GATE_SCRIPT = Path("scripts") / "gate_check.py"

_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.M)

# Each item: label shown in the gate report, and what its heading must contain.
# The seven columns are the part's (configs/note_style_spec.yaml: summary /
# overview / toc / key_points / glossary / feynman / meta_footer). toc is left
# out on purpose — the part generates "## 📑 本篇目录" itself after the note is
# written, so a note that has not been through that pass yet is still valid.
_SECTIONS = (
    ("概述", ("概述", "在讲什么", "导读")),
    ("核心知识点", ("核心知识点",)),
    ("专业词汇表", ("词汇表", "术语表", "术语速查")),
    ("自测题", ("自测题", "费曼思考题", "费曼题")),
    ("元信息", ("元信息",)),
)
_SUMMARY_LINE = re.compile(r"^>[ \t]*.*一句话总结", re.M)

# The part fixes the frontmatter to these eight fields, in this order
# (configs/note_style_spec.yaml). Extra OKF fields may follow them.
_FRONTMATTER_FIELDS = ("title", "source", "author", "duration", "word_count",
                       "created", "tags", "type")
_FM_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):", re.M)


def _frontmatter_keys(note: str) -> list:
    block = _FRONTMATTER.match(note)
    return _FM_KEY.findall(block.group(0)) if block else []


def _headings(note: str) -> list:
    return [m.group(1).strip() for m in _HEADING.finditer(note)]


# The note's shape is the part's, not ours: gate_check.py parses knowledge
# points with "### 知识点 <digits> · <title>" and counts six pieces / Feynman
# angles per point. Writing our own tolerant variant of that pattern was the
# original mistake — it let our notes drift off-spec, and the part's checks then
# ran against an empty set and reported ✅ on notes that had no Feynman at all.
# So: mirror the part's shape exactly, and refuse an empty set (the one case the
# part scores as a pass). Counting the six pieces and the angles stays the
# part's job — we shell out to it (mre_check) rather than keep a second
# implementation that can drift.
_KP_HEADING = re.compile(r"^###[ \t]*知识点[ \t]*[0-9][0-9.]*[ \t]*·", re.M)
_DEMO_LABEL = re.compile(r"^[ \t]*[-*][ \t]*\*\*❓[ \t]*示范角度", re.M)


def knowledge_checks(note: str) -> list:
    """Shape guards the part's gate cannot give us. Returns (name, ok, detail)."""
    points = len(_KP_HEADING.findall(note))
    demos = len(_DEMO_LABEL.findall(note))
    return [
        ("note-knowledge-points", points > 0,
         f"{points} 个知识点小节（`### 知识点 N.M · 标题`）" if points else
         "找不到 `### 知识点 N.M · 标题` 形状的知识点小节（照这个形状，mre 自己的门禁会对着空集判过）"),
        ("note-demo-per-point", points > 0 and demos >= points,
         f"{demos} 处 `❓ 示范角度` / {points} 个知识点"),
    ]


# `cases` / `aligned` 里每行写一个 `&`，行与行之间用 `\\` 分隔。
# 写成 `\ `（LaTeX 的控制空格）当分隔符，所有分支会挤在同一行、整条公式读不出来。
# 2026-10-16 实测：一份笔记里同时存在写法正确的与写坏的，人在长文里发现不了——
# 这是确定性检查，归门禁，不归审核方抽查。
_FORMULA_ENV = re.compile(r"\\begin\{(cases|aligned)\}(.*?)\\end\{\1\}", re.S)

# Matrix-family environments use `&` for *columns*, so the check above (which
# counts `&`) cannot judge them — a 4-column row legitimately has three of them.
# What goes wrong there is a *lone* backslash-space where a `\\` belongs: the
# same transcription slip, and it squeezes every row onto one line. 2026-10-17
# six such matrices sat in one note through several green gate runs, and were
# only found by a reader who could not read the matrix.
_MATRIX_ENV = re.compile(
    r"\\begin\{(array|matrix|pmatrix|bmatrix|vmatrix)\}(.*?)\\end\{\1\}", re.S)
_LONE_ESCAPE = re.compile(r"(?<!\\)\\[ \t]")


_ELLIPSIS_ROWS = frozenset(("\\dots", "\\cdots", "\\vdots", "\\ddots"))


def _column_counts(body: str) -> set:
    """Distinct `&` counts across a matrix body, ignoring ellipsis-only rows.

    An ellipsis row (``\\dots`` and friends) carries no columns of its own --
    counting it would make every matrix that abbreviates its middle rows look ragged.
    """
    counts = set()
    for row in body.split("\\\\"):
        if not row.strip():
            continue
        if row.replace("&", "").replace(" ", "") in _ELLIPSIS_ROWS:
            continue
        counts.add(row.count("&"))
    return counts


# 扫描公式之前先剥掉代码块与行内代码。元信息里会**合法地**用反引号引用 LaTeX
# （例如「41 处 `\\begin{array}` 已还原」那条），不剥的话扫描器会从一个行内代码里的
# `\\begin{bmatrix}` 一路吃到几段之后的结尾，把正文一起吞掉，报出一处根本不存在的坏矩阵。
# 2026-10-22 实测：第 4 章因此被误报一次。假红和假绿一样坏。
_FENCED = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def _strip_code(text: str) -> str:
    return _INLINE_CODE.sub("", _FENCED.sub("", text))


def formula_checks(note: str) -> list:
    """Formula environments whose rows are not separated by ``\\\\``."""
    note = _strip_code(note)
    broken = [m.group(1) for m in _FORMULA_ENV.finditer(note)
              if m.group(2).count("&") >= 2 and "\\\\" not in m.group(2)]
    squeezed = [m.group(1) for m in _MATRIX_ENV.finditer(note)
                if _LONE_ESCAPE.search(m.group(2))]
    # 各行的 `&` 数必须一致：矩阵的行靠两个反斜杠分隔，漏写一个就会把两行并成一行，
    # 渲染出来那一行突然比别的行宽。2026-10-22 实测：一张矩阵速查表里两处各漏一个分隔符，
    # 上面两条检查都看不见（不是写成了「反斜杠 + 空格」，而是根本没有），门禁照样全绿。
    ragged = [m.group(1) for m in _MATRIX_ENV.finditer(note)
              if len(_column_counts(m.group(2))) > 1]
    problems = []
    if broken:
        names = "/".join(sorted(set(broken)))
        problems.append(f"{len(broken)} 处 `{names}` 环境的分支行没被 `\\\\` 分隔——"
                        f"多半是把分隔符写成了 `\\ `，渲染时所有分支挤在一行")
    if squeezed:
        names = "/".join(sorted(set(squeezed)))
        problems.append(f"{len(squeezed)} 处 `{names}` 矩阵的行分隔符写成了单个 `\\ `"
                        f"（应为 `\\\\`）——渲染时整个矩阵会挤成一行")
    if ragged:
        names = "/".join(sorted(set(ragged)))
        problems.append(f"{len(ragged)} 处 `{names}` 矩阵各行的 `&` 数不一致——"
                        f"多半是漏了一个 `\\\\`，两行并进了一行")
    detail = "；".join(problems) if problems else "公式环境的分支行都按 `\\\\` 分隔"
    return [("note-formula-renders", not problems, detail)]


# The in-note TOC is the part's to generate (configs/note_style_spec.yaml: toc),
# as its own pass after the note is written — which is why _SECTIONS leaves that
# heading out: a note that has not been through `material-to-notes toc` yet is still fine.
# An *empty* TOC is a different state, not that one: the heading is there and
# nothing follows it, so nothing is coming to fill it. 2026-10-16 a rebuild
# dropped all 31 entries of a note while leaving the heading; the gate passed it
# and the handoff sheet recorded "七栏目齐 / exit=0".
_TOC_HEADING = re.compile(r"^##[ \t]*[^\n]*本篇目录[^\n]*$", re.M)
_TOC_ENTRY = re.compile(r"^[ \t]*-[ \t]*\[[^\]\n]+\]\(#[^)\n]*\)")


def toc_checks(note: str) -> list:
    """A TOC that exists must list something. Returns (name, ok, detail)."""
    head = _TOC_HEADING.search(note)
    if not head:
        return [("note-toc-filled", True,
                 "没有篇内目录标题（尚未跑 `material-to-notes toc`，按规范不算错）")]
    entries = 0
    for line in note[head.end():].splitlines():
        if not line.strip():
            continue
        if _TOC_ENTRY.match(line):
            entries += 1
            continue
        break
    return [("note-toc-filled", entries > 0,
             f"篇内目录有 {entries} 条条目" if entries else
             "篇内目录只有标题、一条条目都没有——多半是重写完笔记后没跑 `material-to-notes toc`")]


def structure_checks(note: str) -> list:
    """The structural items this pipeline owns. Returns (name, ok, detail)."""
    headings = _headings(note)
    keys = _frontmatter_keys(note)
    expected = list(_FRONTMATTER_FIELDS)
    checks = [
        ("note-frontmatter", bool(_FRONTMATTER.match(note)),
         "YAML frontmatter present" if _FRONTMATTER.match(note) else "no frontmatter block"),
        ("note-frontmatter-fields", keys[:len(expected)] == expected,
         f"前 {len(expected)} 个字段 = {keys[:len(expected)]}" if keys else
         f"frontmatter 的字段名不是规范的英文名 {expected[:3]}…（旧式中文字段名不算）"),
        ("note-一句话总结", bool(_SUMMARY_LINE.search(note)),
         "found `> 一句话总结：…`" if _SUMMARY_LINE.search(note) else
         "没有 `> 一句话总结：…` 那一行（规范 structure.summary）"),
    ]
    for label, needles in _SECTIONS:
        found = next((h for h in headings if any(n in h for n in needles)), "")
        checks.append((
            f"note-{label}",
            bool(found),
            f"found heading {found!r}" if found else f"no heading containing {'/'.join(needles)}",
        ))
    return checks


def _gate_command(note_path, src_path, tool, *, python=None) -> list:
    return [python or sys.executable, str(Path(tool) / MRE_GATE_SCRIPT),
            str(note_path), "--src", str(src_path)]


def _notes(root) -> list:
    base = _workdir.step_dir(root, _steps.get_step("note"))
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.md") if p.is_file())


def note_targets(root) -> dict:
    """{note file name: the cleaned text it must be checked against}.

    Intermediates are keyed by the source and deliverables by the name the user
    chose, so the two are matched through the intake sheet rather than by
    assuming they are spelled the same.
    """
    from material_to_notes.orchestrate import pipeline as _pipeline

    sheet = _meta.load_sheet(root)
    targets = {}
    for path in _pipeline.relay_sources(root, "note"):
        key = _workdir.source_name(path)
        targets[f"{_meta.name_for(sheet, key, key)}.md"] = path
    return targets


def _figure_note_stems(root, source_path) -> set:
    """The internal identifiers of the figure notes embedded into this source.

    dtmd's ``embed_notes`` writes ``## 插图笔记：<image sha256>``. The hash is a
    file identifier, not content — a reader learns nothing from it — so it must
    not reach the deliverable. These are the exact strings, so the check is a
    lookup rather than "looks like a hash".
    """
    name = _workdir.source_name(source_path)
    mineru = _workdir.step_dir(root, _steps.get_step("document")) / f"{name}_mineru"
    notes_dir = mineru / "images_notes"
    if not notes_dir.is_dir():
        return set()
    return {p.stem for p in notes_dir.glob("*.md")}


def _leaked_hashes(root, targets: dict) -> list:
    leaked = []
    for note in _notes(root):
        source = targets.get(note.name)
        if source is None:
            continue
        text = note.read_text(encoding="utf-8", errors="replace")
        for stem in _figure_note_stems(root, source):
            if stem in text:
                leaked.append(f"{note.name} 抄了内部编号 {stem[:12]}…")
    return leaked


def _stale_notes(root, targets: dict) -> list:
    """Notes sitting in 04_笔记 that no material maps to — usually a rename's leftovers."""
    return [note.name for note in _notes(root) if note.name not in targets]


_MISSING_TOKENS = re.compile(r"缺失\[(.*?)\]")
SIDECAR_DIR = ("_元数据", "照录")


def _problem_lines(output: str) -> list:
    return [line.strip() for line in output.splitlines()
            if line.strip().startswith("- ") and "→" not in line]


def _missing_tokens(output: str) -> list:
    """The numbers the part's reconciliation pass could not find in the note."""
    m = _MISSING_TOKENS.search(output)
    if not m:
        return []
    return [t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()]


def _explainable_reason(output: str, note, root) -> tuple:
    """``(放行?, 说明)`` —— 说明在放行与不放行两种情况下都要能讲清理由。

    只有一种情形可放行：**对账缺口能逐个解释**（验收标准 B-2）。自 Task-14 起，
    照录的表格/代码按规范（`appendix: full_original_external`）外置到
    `_元数据/照录/<素材>_照录对账材料.md`，所以"缺口有解释"＝**每个缺失数字都能在
    那份材料里找到**；只要有一个数字**哪儿都找不到**，就如实判 FAIL。

    零件报的**每一条**问题都必须落在这一种情形里，否则 FAIL 照旧。

    （原先还有第二处绕行——"知识点覆盖不足"判定与规范冲突——2026-10-15 已从零件侧
    修好：覆盖条件的分母改成与逐单元条件同尺的"够格的源单元"，不再把标题残段算成
    待覆盖单元，见 `docs/回灌清单.md` B-4。绕行一并删除：留着它会把真正的覆盖不足
    也静默放行。）
    """
    problems = _problem_lines(output)
    if not problems:
        return False, ""
    reasons = []
    for problem in problems:
        if "机械对账" in problem:
            missing = _missing_tokens(problem) or _missing_tokens(output)
            sidecar = Path(root).joinpath(*SIDECAR_DIR) / f"{note.stem}_照录对账材料.md"
            if not (missing and sidecar.is_file()):
                return False, ""
            hay = sidecar.read_text(encoding="utf-8", errors="replace")
            left = [t for t in missing if t not in hay]
            if left:
                return False, (f"数字缺口里有 {len(left)} 个不在照录材料里：{left[:5]}"
                               f"（缺口未解释，按 B-2 判 FAIL）")
            reasons.append(f"数字缺口 {len(missing)} 个已全部对上"
                           f"（均在 _元数据/照录/{note.stem}_照录对账材料.md，验收标准 B-2）")
            continue
        return False, ""
    return True, "；".join(reasons)


# mre's reconciliation baseline is its own extract_speech(): every 🎤 line and
# nothing from the 🖼 blocks. On a screen recording the frames *are* the lesson,
# so ①机械对账 and ⑤丰富度 can go green while most of the source is never looked
# at — measured on `runs/vid5`: 610 of 7314 characters. Mirrors the regex in
# parts/md-rewrite-engine/scripts/gate_check.py::extract_speech; if that one
# changes, this measurement changes with it.
_SPEECH_LINE = re.compile(r"\[\d+:\d+\] 🎤 (.+)")
_FRAME_BLOCK = re.compile(r"^🖼 ", re.M)


def media_basis_warning(source_text) -> str:
    """What mre's ①⑤ cannot see, when the source is a timeline markdown.

    Empty for anything that is not a 🎤-and-🖼 timeline (an ordinary document, or
    audio with no frames — there the speech really is the whole material).
    Reported, never failed: keeping frames out of the numeric baseline is
    defensible for a document with embedded figure OCR, it just is not enough
    for this line, and a silent green is exactly how that gets forgotten.
    """
    text = source_text or ""
    if not _FRAME_BLOCK.search(text):
        return ""
    speech = _SPEECH_LINE.findall(text)
    if not speech:
        return ""
    seen = sum(len(part) for part in speech)
    return (f"⚠️ 源文是时间轴形态：mre 的 ①机械对账/⑤丰富度 只按 🎤 语音行算"
            f"（{seen}/{len(text)} 字符），🖼 画面文字**不参与对账** —— "
            f"这两项过线说明不了内容完整性，媒体线必须另做全文（语音+画面）语义复核")


def mre_check(root, *, env=None, timeout=300, python=None, runner=None):
    """Run mre's content gate on every note, each against its own source.

    Shim (2026-10-15): ``core/verify._kp_cover`` counts *any* ``#{2,3}`` heading
    while the spec puts the Feynman demo *inside* each knowledge point — so a
    spec-compliant note has fewer headings and can fail the exemption's coverage
    test. Measured on one unchanged note: old (off-spec) shape 34/42 = 81% PASS
    → spec shape 27/42 = 64% FAIL. Until the part fixes its denominator
    (``docs/回灌清单.md`` B-4) we downgrade **that one sub-condition** to a
    warning, and only when it is the sole problem reported. Coverage itself is
    still watched — acceptance E-1/E-2 (every knowledge point traces to the
    source, every source chapter has a landing point) plus the independent
    reviewer. Delete this shim once the part is fixed.
    """
    tool = R.part_tool(MRE_ENV_KEY, MRE_PART, env)
    notes = _notes(root)
    targets = note_targets(root)
    if not Path(tool).is_dir():
        return False, (f"content gate unavailable: no part at {tool} "
                       f"(set {MRE_ENV_KEY} or place the part under parts/)")
    if not (Path(tool) / MRE_GATE_SCRIPT).is_file():
        return False, f"content gate script missing: {Path(tool) / MRE_GATE_SCRIPT}"
    if not notes:
        return False, "no note .md to check"

    details = []
    ok = True
    for note in notes:
        source = targets.get(note.name)
        if source is None:
            ok = False
            details.append(f"{note.name}: FAIL no material maps to this name "
                           f"(改名前的旧产物？不能拿别人的原文当基准)")
            continue
        result = R.run_command(_gate_command(note, source, tool, python=python),
                               timeout=timeout, runner=runner,
                               env=R.tool_env(tool, base=R.child_env(env)))
        passed = result.ok
        verdict = "PASS" if passed else "FAIL"
        output = result.stdout or result.stderr or ""
        tail = output.strip().splitlines()
        summary = tail[-1].strip() if tail else ""
        if not passed:
            stand_down, why = _explainable_reason(output, note, root)
            if stand_down:
                passed = True
                verdict = f"PASS(按验收标准 B-2 放行) {why}"
                # 零件那句收尾是"→ 打回：…"；既然我们放行了就别再抄一遍自相矛盾
                summary = ""
            elif why:
                verdict = f"FAIL {why}"
        ok = ok and passed
        line = f"{note.name}: {verdict} {summary}".rstrip()
        try:
            basis = media_basis_warning(Path(source).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            basis = ""
        if basis:
            line = f"{line}；{basis}"
        details.append(line)
    return ok, "; ".join(details)


def check_note(root, *, env=None, timeout=300, python=None, runner=None) -> GateResult:
    """The note step's full gate: our structure checks plus mre's content gate."""
    notes = _notes(root)
    targets = note_targets(root)
    checks = []
    passed = {}

    if not notes:
        checks.append(("note-structure", False, "no note .md found"))
    else:
        for note in notes:
            text = note.read_text(encoding="utf-8", errors="replace")
            note_checks = (structure_checks(text) + knowledge_checks(text)
                           + formula_checks(text) + toc_checks(text))
            checks.extend((f"{name} [{note.name}]", ok, detail) for name, ok, detail in note_checks)
            passed[note.stem] = all(ok for _n, ok, _d in note_checks)

    stale = _stale_notes(root, targets)
    checks.append(("note-no-orphans", not stale,
                   "；".join(stale) + "（没有素材对应，多半是改名前的旧产物）" if stale
                   else "每份笔记都能对上素材"))

    # Every material needs its own note. Without this, a step that wrote one of
    # two notes passes every other check — the missing one is simply absent.
    have = {note.name for note in notes}
    missing = sorted(name for name in targets if name not in have)
    checks.append(("note-every-material-covered", not missing,
                   ("缺 " + "、".join(missing)) if missing
                   else f"{len(targets)} 份素材各有笔记"))

    leaked = _leaked_hashes(root, targets)
    checks.append(("note-no-internal-ids", not leaked,
                   "；".join(leaked) if leaked else "没有把流水线内部编号抄进笔记"))

    ok, detail = mre_check(root, env=env, timeout=timeout, python=python, runner=runner)
    checks.append(("note-content-gate (mre)", ok, detail))

    # Record the verdict per source, so the record says what the pipeline decided
    # rather than what the writing agent reported.
    for note in notes:
        if note.name in targets:
            _meta.record_step(root, note.stem, "note",
                              ok=bool(passed.get(note.stem)) and ok,
                              outputs=[f"04_笔记/{note.name}"])

    raw = "\n".join(f"[{'PASS' if ok else 'FAIL'}] note/{name}: {detail}"
                    for name, ok, detail in checks)
    return GateResult("note", all(ok for _, ok, _ in checks), tuple(checks), raw)
