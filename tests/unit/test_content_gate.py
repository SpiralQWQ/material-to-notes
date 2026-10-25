"""Tests for gates.content — the note step's own content gate."""

from types import SimpleNamespace

from material_to_notes.gates import content as C

GOOD_SOURCE = """# 源文

这是清洗后的原文，含数字 42。
"""

GOOD_NOTE = """---
title: 测试笔记
source: full.txt
author: 测试
duration: 1
word_count: 100
created: 2026-10-15
tags: [test]
type: teaching-note
---

# 测试笔记

> 一句话总结：这一篇只讲一件事——甲和丙各是什么。

## 📚 概述

- 讲什么：甲、乙、丙、丁四件事。

---

## 🧠 核心知识点

### 知识点 1.1 · 甲与乙

- **定义**：甲
- **类比**：乙
- **原理**：丙
- **示例**：丁
- **为什么**：戊
- **易错点**：己
- **❓ 示范角度**：①（复述）甲是什么？②（挑错）有人说甲就是乙，错在哪？

### 知识点 1.2 · 丙与丁

- **定义**：丙
- **类比**：丁
- **原理**：戊
- **示例**：己
- **为什么**：庚
- **易错点**：辛
- **❓ 示范角度**：①（复述）丙是什么？②（应用）丙怎么用？

## 📖 专业词汇表

| 术语 | 通俗解释 |
|---|---|
| alpha | 甲 |

## ❓ 自测题

1. 甲是什么？

## 📌 元信息

1. **源文有个错字**：无伤大雅。
"""


class _Runner:
    def __init__(self, returncode=0, stdout="判定: PASS", stderr=""):
        self.calls = []
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, argv, **kw):
        self.calls.append([str(a) for a in argv])
        self.env = kw.get("env")
        return SimpleNamespace(returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


def _workdir(tmp_path, note=GOOD_NOTE, source=GOOD_SOURCE):
    (tmp_path / "03_清洗").mkdir(parents=True, exist_ok=True)
    (tmp_path / "03_清洗" / "full.txt").write_text(source, encoding="utf-8")
    (tmp_path / "04_笔记").mkdir(parents=True, exist_ok=True)
    (tmp_path / "04_笔记" / "full.md").write_text(note, encoding="utf-8")
    return tmp_path


def _mre(tmp_path):
    tool = tmp_path / "mre"
    (tool / "scripts").mkdir(parents=True, exist_ok=True)
    (tool / "scripts" / "gate_check.py").write_text("# stub", encoding="utf-8")
    return tool


# --- structure checks (the four items this pipeline owns) ------------------

def test_structure_checks_pass_on_a_well_formed_note():
    checks = C.structure_checks(GOOD_NOTE)
    assert [name for name, _ok, _d in checks] == [
        "note-frontmatter", "note-frontmatter-fields", "note-一句话总结",
        "note-概述", "note-核心知识点", "note-专业词汇表", "note-自测题", "note-元信息"]
    assert all(ok for _n, ok, _d in checks), checks


def test_structure_checks_flag_a_missing_frontmatter():
    checks = dict((name, ok) for name, ok, _ in C.structure_checks("# 标题\n\n正文\n"))
    assert checks["note-frontmatter"] is False


def test_structure_checks_flag_the_wrong_frontmatter_fields():
    # The part fixes eight field names in order; the old four-field header is
    # exactly what let our notes drift off-spec.
    note = GOOD_NOTE.replace("author: 测试\n", "").replace("duration: 1\n", "")
    checks = dict((name, ok) for name, ok, _ in C.structure_checks(note))
    assert checks["note-frontmatter"] is True
    assert checks["note-frontmatter-fields"] is False


def test_structure_checks_flag_a_missing_summary_line():
    note = GOOD_NOTE.replace("> 一句话总结：这一篇只讲一件事——甲和丙各是什么。", "先读一遍。")
    checks = dict((name, ok) for name, ok, _ in C.structure_checks(note))
    assert checks["note-一句话总结"] is False


def test_structure_checks_flag_missing_sections():
    note = GOOD_NOTE.replace("## 📖 专业词汇表", "## 随便一节").replace("## 📌 元信息", "## 尾注")
    checks = dict((name, ok) for name, ok, _ in C.structure_checks(note))
    assert checks["note-专业词汇表"] is False
    assert checks["note-元信息"] is False
    assert checks["note-概述"] is True


def test_structure_checks_accept_the_alternate_headings():
    # The same five columns under the names the已入库 notes actually use
    # (📚 本组在讲什么 / 📖 高频术语速查 / ❓ 自测题（面试模拟）) must pass too —
    # the part's spec names the columns, the notes spell them their own way.
    note = (GOOD_NOTE.replace("## 📚 概述", "## 📚 本组在讲什么")
                    .replace("## 📖 专业词汇表", "## 📖 高频术语速查")
                    .replace("## ❓ 自测题", "## ❓ 自测题（面试模拟）"))
    assert all(ok for _n, ok, _d in C.structure_checks(note))


def test_knowledge_points_are_counted_in_the_parts_shape():
    checks = dict((name, ok) for name, ok, _ in C.knowledge_checks(GOOD_NOTE))
    assert checks["note-knowledge-points"] is True
    assert checks["note-demo-per-point"] is True


def test_a_note_in_the_old_shape_fails_the_knowledge_point_check():
    # "## 知识点一 甲" is the shape the part's gate cannot parse — the whole
    # reason our notes drifted. It must not pass here either.
    note = GOOD_NOTE.replace("### 知识点 1.1 · 甲与乙", "## 知识点一 甲与乙")
    checks = dict((name, ok) for name, ok, _ in C.knowledge_checks(note))
    assert checks["note-knowledge-points"] is True   # one point still parses
    assert checks["note-demo-per-point"] is True


def test_a_knowledge_point_without_a_demo_angle_fails():
    note = GOOD_NOTE.replace(
        "- **❓ 示范角度**：①（复述）甲是什么？②（挑错）有人说甲就是乙，错在哪？\n", "")
    checks = dict((name, ok) for name, ok, _ in C.knowledge_checks(note))
    assert checks["note-demo-per-point"] is False


def test_zero_knowledge_points_is_a_failure():
    # The one case the part's own gate scores as a pass.
    checks = dict((name, ok) for name, ok, _ in C.knowledge_checks("# 标题\n\n正文\n"))
    assert checks["note-knowledge-points"] is False


# --- the mre content gate --------------------------------------------------

def test_mre_gate_runs_the_script_from_the_part(tmp_path):
    _workdir(tmp_path)
    tool = _mre(tmp_path)
    runner = _Runner()
    ok, detail = C.mre_check(tmp_path, env={"MRE_DIR": str(tool)}, runner=runner)
    assert ok and "PASS" in detail
    argv = runner.calls[0]
    assert argv[1].replace("\\", "/").endswith("scripts/gate_check.py")
    assert argv[2].endswith("full.md")
    assert argv[3] == "--src" and argv[4].endswith("full.txt")
    # --score is the third-party GLM grader; the execution model dropped it.
    assert "--score" not in argv


def test_mre_gate_failure_is_a_failure(tmp_path):
    _workdir(tmp_path)
    tool = _mre(tmp_path)
    ok, detail = C.mre_check(tmp_path, env={"MRE_DIR": str(tool)},
                             runner=_Runner(returncode=1, stdout="判定: FAIL 六件套缺失"))
    assert not ok and "FAIL" in detail


def test_missing_mre_is_a_failure_not_a_silent_pass(tmp_path):
    # A gate that cannot run must never report green.
    _workdir(tmp_path)
    ok, detail = C.mre_check(tmp_path, env={"MATERIAL_TO_NOTES_PARTS_DIR": str(tmp_path / "no-parts")})
    assert not ok and "MRE_DIR" in detail


def test_missing_gate_script_is_a_failure(tmp_path):
    _workdir(tmp_path)
    ok, detail = C.mre_check(tmp_path, env={"MRE_DIR": str(tmp_path / "empty")})
    assert not ok and "missing" in detail


def test_a_note_without_its_own_source_is_a_failure(tmp_path):
    # Checking a note against someone else's baseline would report phantom gaps.
    (tmp_path / "03_清洗").mkdir(parents=True)
    (tmp_path / "03_清洗" / "other.txt").write_text(GOOD_SOURCE, encoding="utf-8")
    (tmp_path / "04_笔记").mkdir(parents=True)
    (tmp_path / "04_笔记" / "full.md").write_text(GOOD_NOTE, encoding="utf-8")
    tool = _mre(tmp_path)
    ok, detail = C.mre_check(tmp_path, env={"MRE_DIR": str(tool)}, runner=_Runner())
    assert not ok and "no material maps to this name" in detail


def test_check_note_combines_both_halves(tmp_path):
    _workdir(tmp_path)
    tool = _mre(tmp_path)
    result = C.check_note(tmp_path, env={"MRE_DIR": str(tool)}, runner=_Runner())
    assert result.passed
    names = [name for name, _ok, _d in result.checks]
    assert "note-frontmatter [full.md]" in names
    assert "note-content-gate (mre)" in names


def test_check_note_fails_when_the_structure_is_wrong(tmp_path):
    _workdir(tmp_path, note="# 光秃秃的标题\n\n没有 frontmatter\n")
    tool = _mre(tmp_path)
    result = C.check_note(tmp_path, env={"MRE_DIR": str(tool)}, runner=_Runner())
    assert not result.passed
    assert any(name.startswith("note-frontmatter") for name in result.failed())


def test_check_note_without_any_note_is_a_failure(tmp_path):
    (tmp_path / "03_清洗").mkdir(parents=True)
    (tmp_path / "03_清洗" / "full.txt").write_text(GOOD_SOURCE, encoding="utf-8")
    tool = _mre(tmp_path)
    result = C.check_note(tmp_path, env={"MRE_DIR": str(tool)}, runner=_Runner())
    assert not result.passed


def test_a_material_without_a_note_fails_the_gate(tmp_path):
    # The real trap: with two materials and one note, every other check passes —
    # the missing note is simply absent, and "a .md exists" is satisfied.
    cleaned = tmp_path / "03_清洗"
    cleaned.mkdir(parents=True)
    (cleaned / "a.txt").write_text("源文 A\n", encoding="utf-8")
    (cleaned / "b.txt").write_text("源文 B\n", encoding="utf-8")
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text(GOOD_NOTE, encoding="utf-8")
    tool = _mre(tmp_path)

    result = C.check_note(tmp_path, env={"MRE_DIR": str(tool)}, runner=_Runner())
    assert not result.passed
    coverage = [c for c in result.checks if c[0] == "note-every-material-covered"][0]
    assert coverage[1] is False and "b.md" in coverage[2]


def test_all_materials_covered_passes(tmp_path):
    cleaned = tmp_path / "03_清洗"
    cleaned.mkdir(parents=True)
    for name in ("a.txt", "b.txt"):
        (cleaned / name).write_text("源文\n", encoding="utf-8")
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    for name in ("a.md", "b.md"):
        (notes / name).write_text(GOOD_NOTE, encoding="utf-8")
    tool = _mre(tmp_path)

    result = C.check_note(tmp_path, env={"MRE_DIR": str(tool)}, runner=_Runner())
    assert result.passed, result.raw


# --- pipeline-internal identifiers must not reach the deliverable -----------
# dtmd's embed_notes writes "## 插图笔记：<image sha256>". A reader learns nothing
# from that hash, but it flows into full.md and from there into the note.

def test_a_note_quoting_an_internal_hash_fails(tmp_path):
    cleaned = tmp_path / "03_清洗"
    cleaned.mkdir(parents=True)
    (cleaned / "a.txt").write_text("源文\n", encoding="utf-8")
    mineru = tmp_path / "02_转md" / "a_mineru" / "images_notes"
    mineru.mkdir(parents=True)
    (mineru / "dad01814bec2cdf7a5d24538f66f70f3b43525021e5803543ddc0531994cd3c6.md").write_text(
        "图意", encoding="utf-8")
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text(
        GOOD_NOTE + "\n见 ## 插图笔记：dad01814bec2cdf7a5d24538f66f70f3b43525021e5803543ddc0531994cd3c6\n",
        encoding="utf-8")

    result = C.check_note(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))}, runner=_Runner())
    check = [c for c in result.checks if c[0] == "note-no-internal-ids"][0]
    assert check[1] is False and "dad01814bec2" in check[2]


def test_a_note_referring_to_a_figure_by_number_passes(tmp_path):
    cleaned = tmp_path / "03_清洗"
    cleaned.mkdir(parents=True)
    (cleaned / "a.txt").write_text("源文\n", encoding="utf-8")
    mineru = tmp_path / "02_转md" / "a_mineru" / "images_notes"
    mineru.mkdir(parents=True)
    (mineru / "dad01814bec2cdf7a5d24538f66f70f3b43525021e5803543ddc0531994cd3c6.md").write_text(
        "图意", encoding="utf-8")
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text(GOOD_NOTE + "\n见 Figure 3 的散点图\n", encoding="utf-8")

    result = C.check_note(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))}, runner=_Runner())
    assert [c for c in result.checks if c[0] == "note-no-internal-ids"][0][1] is True


# --- knowledge-point structure, in the part's shape -------------------------
# The shape is the part's: "### 知识点 N.M · <标题>" is what gate_check.py parses.
# We count it here only to refuse an empty set — the one case the part scores as
# a pass. The six pieces and the Feynman angles per point stay the part's job.


def test_the_parts_shape_is_the_only_shape_that_counts():
    # "## 知识点一 甲" (our old shape) must NOT count: the part cannot parse it,
    # and counting it here is exactly what let seven notes drift off-spec.
    old = (GOOD_NOTE.replace("### 知识点 1.1 · 甲与乙", "## 知识点一 甲与乙")
                    .replace("### 知识点 1.2 · 丙与丁", "## 知识点二 丙与丁"))
    assert dict((n, ok) for n, ok, _ in C.knowledge_checks(old))["note-knowledge-points"] is False


def test_a_note_with_no_knowledge_points_fails_rather_than_passing_vacuously():
    checks = dict((n, ok) for n, ok, _ in C.knowledge_checks("# 光标题\n\n正文\n"))
    assert checks["note-knowledge-points"] is False
    # Every count-based check must fail too, not silently pass on an empty set.
    assert all(ok is False for ok in checks.values())


# --- the coverage condition is no longer shimmed (回灌清单 B-4, fixed 2026-10-15)
# The part used to score the note's *any* #{2,3} heading count against the
# source's numbered-section count. Because the spec folds the Feynman demo into
# each knowledge point, a compliant note had fewer headings and looked
# under-covered — so we downgraded that one sub-condition to a pass. The part's
# denominator now counts only substantive source units, so a coverage failure is
# a real one and must stand.

_COVERAGE_FAIL_OUT = """=== 门禁检查: full.md ===
① 机械对账(数字): 100% ✅ 缺失[]
② 6 件套: ✅ 全部完整
③ 费曼示范: ✅ 每点≥2
⑤ 丰富度(膨胀率): 70% ❌ [豁免] 膨胀率 70% 在豁免区 [30%~80%)，知识点覆盖不足（12/40=30% < 80%）——疑似偷工
判定: ❌ FAIL
   - 丰富度不达标（膨胀率 70%）：膨胀率 70% 在豁免区 [30%~80%)，知识点覆盖不足（12/40=30% < 80%）——疑似偷工
   → 打回：按上述问题清单针对性修补
"""


def test_a_coverage_failure_is_no_longer_downgraded(tmp_path):
    _workdir(tmp_path)
    ok, detail = C.mre_check(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))},
                             runner=_Runner(returncode=1, stdout=_COVERAGE_FAIL_OUT))
    assert not ok and "FAIL" in detail


def test_the_gate_subprocess_gets_a_utf8_environment(tmp_path):
    # mre's report prints an emoji ("✅"); on a legacy console codepage the child
    # dies with UnicodeEncodeError and a perfectly good gate looks broken (T59).
    _workdir(tmp_path)
    runner = _Runner()
    C.mre_check(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))}, runner=runner)
    assert runner.env["PYTHONIOENCODING"] == "utf-8"
    # 必须是**完整**环境（含 PATH），不能只把那个 env 映射丢给子进程
    assert runner.env.get("PATH")
    assert str(_mre(tmp_path)) in runner.env["PYTHONPATH"]


def test_a_normal_failure_is_not_downgraded(tmp_path):
    _workdir(tmp_path)
    ok, _detail = C.mre_check(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))},
                              runner=_Runner(returncode=1, stdout="判定: FAIL 六件套缺失"))
    assert not ok


# --- 公式环境的分支行必须按 \\ 分隔（2026-10-16）-----------------------------
# 实测：同一份笔记里既有写法正确的 cases、也有把分隔符写成 `\ ` 的；
# 后者渲染时所有分支挤在一行，整条公式读不出来。人在长文里发现不了，所以交给门禁。

_BAD_CASES = "$x=\\begin{cases} 1, & \\text{甲} \\ 0, & \\text{否则} \\end{cases}$"
_GOOD_CASES = "$x=\\begin{cases} 1, & \\text{甲} \\\\ 0, & \\text{否则} \\end{cases}$"


def _formula(note):
    return dict((n, ok) for n, ok, _d in C.formula_checks(note))["note-formula-renders"]


def test_a_cases_block_missing_its_row_separator_fails():
    assert _formula(_BAD_CASES) is False


def test_a_cases_block_with_the_right_separator_passes():
    assert _formula(_GOOD_CASES) is True


def test_a_single_row_environment_is_not_flagged():
    # 只有一行就没有"行分隔符"可言，不该误报
    assert _formula("$x=\\begin{cases} 1, & \\text{甲} \\end{cases}$") is True


def test_an_array_with_several_columns_is_not_flagged():
    # array 的 `&` 是列分隔不是行分隔——这条检查只认 cases/aligned，避免误报
    assert _formula("$x=\\begin{array}{ccc} a & b & c \\end{array}$") is True


def test_the_failure_says_which_environment_and_why():
    detail = dict((n, d) for n, _ok, d in C.formula_checks(_BAD_CASES))["note-formula-renders"]
    assert "cases" in detail and "分隔" in detail


# --- 矩阵（array 一族）的行分隔符（2026-10-17）------------------------------
# 实测：一份笔记里 6 个 `\begin{array}` 矩阵的行分隔符全写成了单个 `\ `，
# 渲染时整个矩阵挤成一行。当时那条仅认 cases/aligned 的检查看不见它——
# 因为 array 的 `&` 是**列**分隔，用 `&` 计数判不出来（4 列的行天生就有 3 个 `&`）。

_BAD_MATRIX = "$A=\\begin{array}{cc} a & b \\ c & d \\end{array}$"
_GOOD_MATRIX = "$A=\\begin{array}{cc} a & b \\\\ c & d \\end{array}$"


def test_a_matrix_row_separator_written_as_a_lone_backslash_fails():
    assert _formula(_BAD_MATRIX) is False


def test_a_matrix_with_the_right_row_separator_passes():
    assert _formula(_GOOD_MATRIX) is True


def test_a_correct_array_is_still_not_flagged():
    # 新检查只盯"单个反斜杠 + 空格"，不该误伤写法正确的 array
    assert _formula("$x=\\begin{array}{ccc} a & b & c \\end{array}$") is True


def test_the_matrix_failure_names_the_environment():
    detail = dict((n, d) for n, _ok, d in C.formula_checks(_BAD_MATRIX))["note-formula-renders"]
    assert "array" in detail and "矩阵" in detail


# --- 篇内目录存在就必须有条目（2026-10-16）----------------------------------
# 实测：重写完笔记后整块目录没了、只留下标题，门禁照过——它只查"有没有这几个字"。
# "目录不存在"仍算通过（零件还没跑刷目录那一遍，原设计的容错保留）；
# "目录在、条目是 0 条"不算通过——那是坏掉的状态，不是"还没跑"。

_EMPTY_TOC = "# 标题\n\n## 📑 本篇目录\n\n---\n\n> 一句话总结: 甲。\n"


def _toc(note):
    return dict((n, ok) for n, ok, _d in C.toc_checks(note))["note-toc-filled"]


def test_a_toc_with_no_entries_fails():
    assert _toc(_EMPTY_TOC) is False


def test_a_toc_with_entries_passes():
    note = _EMPTY_TOC.replace(
        "---\n", "- [概述](#概述)\n  - [知识点 1.1](#知识点-11)\n\n---\n")
    assert _toc(note) is True


def test_a_note_without_a_toc_is_not_flagged():
    assert _toc("# 标题\n\n> 一句话总结: 甲。\n") is True


def test_the_empty_toc_failure_says_what_to_run():
    detail = dict((n, d) for n, _ok, d in C.toc_checks(_EMPTY_TOC))["note-toc-filled"]
    assert "material-to-notes toc" in detail


# --- the reconciliation shim (Task-14 / acceptance B-2) ---------------------
# B-2 lets a sub-90% number pass when every gap is accounted for. Since Task-14
# the copied tables live in _元数据/照录/<素材>_照录对账材料.md, so a gap is
# accounted for exactly when every missing number is in there.

_RECON_FAIL_OUT = """=== 门禁检查: full.md ===
① 机械对账(数字): 34% ❌ 缺失['111', '222']
② 6 件套: ✅ 全部完整
判定: ❌ FAIL
   - 机械对账 34% < 90%（缺 2 个数字）
   → 打回：按上述问题清单针对性修补
"""


def _sidecar(tmp_path, body):
    d = tmp_path / "_元数据" / "照录"
    d.mkdir(parents=True, exist_ok=True)
    (d / "full_照录对账材料.md").write_text(body, encoding="utf-8")


def test_reconciliation_gap_fully_in_the_sidecar_is_explained(tmp_path):
    _workdir(tmp_path)
    _sidecar(tmp_path, "| 表 | 值 |\n|---|---|\n| a | 111 |\n| b | 222 |\n")
    ok, detail = C.mre_check(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))},
                             runner=_Runner(returncode=1, stdout=_RECON_FAIL_OUT))
    assert ok and "缺口" in detail and "B-2" in detail


def test_reconciliation_gap_not_in_the_sidecar_still_fails(tmp_path):
    _workdir(tmp_path)
    _sidecar(tmp_path, "只有 111，没有另一个数\n")
    ok, detail = C.mre_check(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))},
                             runner=_Runner(returncode=1, stdout=_RECON_FAIL_OUT))
    assert not ok and "不在照录材料里" in detail


def test_reconciliation_gap_without_a_sidecar_still_fails(tmp_path):
    _workdir(tmp_path)
    ok, _detail = C.mre_check(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))},
                              runner=_Runner(returncode=1, stdout=_RECON_FAIL_OUT))
    assert not ok


# mre 的对账基准是 extract_speech()：源文里只要有 🎤 行，就只拿那些行当基准，
# 画面文字整段丢掉。屏幕录制型视频里画面才是主要信息源，于是"① 机械对账 100%"
# 说明不了内容完整性。不说出来就等于默认放行，所以每次跑都要把这条印在门禁结果里。


_TIMELINE_SOURCE = (
    "[00:00] 🎤 今天我们讲子网掩码。\n"
    "🖼 [00:00]\n什么是\n计算机网络？\n"
    "🖼 [00:01]\n子网掩码是\n255.255.255.0\n"
)


def test_the_media_basis_warning_names_what_the_gate_cannot_see():
    warning = C.media_basis_warning(_TIMELINE_SOURCE)
    assert "🎤" in warning and "画面" in warning
    assert str(len("今天我们讲子网掩码。")) in warning  # 基准只含语音这一部分
    assert str(len(_TIMELINE_SOURCE)) in warning       # 而源文是这么长


def test_the_media_basis_warning_is_empty_for_an_ordinary_source():
    assert C.media_basis_warning(GOOD_SOURCE) == ""


def test_the_media_basis_warning_is_empty_for_plain_media_without_frames():
    # 只有语音、没有画面帧的源文（如纯音频）不吃这个亏，不该报警。
    assert C.media_basis_warning("[00:00] 🎤 一句话。\n") == ""


def test_mre_check_reports_the_media_basis(tmp_path):
    _workdir(tmp_path, source=_TIMELINE_SOURCE)
    ok, detail = C.mre_check(tmp_path, env={"MRE_DIR": str(_mre(tmp_path))},
                             runner=_Runner(returncode=0))
    assert ok and "画面" in detail

# --- 矩阵各行的 `&` 数必须一致（2026-10-22）--------------------------------
# 实测：一张矩阵速查表里两处各漏一个行分隔符，两行并成一行、那一行比别的行宽。
# 上面两条检查都看不见它——分隔符不是写错成「反斜杠 + 空格」，而是根本没有，
# 所以门禁全绿、笔记交付时那两行矩阵是错的。

_RAGGED_MATRIX = r"$A=\begin{bmatrix} a & b \\ c & d & e \end{bmatrix}$"


def test_a_matrix_whose_rows_disagree_on_columns_fails():
    assert _formula(_RAGGED_MATRIX) is False


def test_a_matrix_with_equal_columns_passes():
    assert _formula(r"$A=\begin{bmatrix} a & b \\ c & d \end{bmatrix}$") is True


def test_a_single_row_matrix_is_not_flagged():
    # 一行就没有「各行一致」可言，行向量本身是合法的
    assert _formula(r"$A=\begin{bmatrix} a & b & c \end{bmatrix}$") is True

def test_an_ellipsis_row_does_not_make_a_matrix_look_ragged():
    # 用省略号省掉中间几行是常见写法，那一行本来就没有 `&`（doc3 那份笔记就有一处）
    assert _formula(r"$A=\begin{array}{cc} a & b \\ \dots \\ c & d \end{array}$") is True

def test_latex_quoted_in_inline_code_is_not_read_as_a_matrix():
    # 元信息里会**合法地**用反引号引用 LaTeX（如「41 处 `\begin{array}` 已还原」那条）。
    # 不剥行内代码，扫描器会从一处行内代码里的 begin 一路吃到几段之后的结尾，
    # 把正文一起吞掉，报出一处根本不存在的坏矩阵——2026-10-22 第 4 章实测。
    note = "登记：`\begin{bmatrix}` 与 `\end{bmatrix}` 只是引用，`\` 写法已全部还原。"
    assert _formula(note) is True
