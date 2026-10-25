"""The dispatch brief must describe the shape the part actually parses.

Two halves, and both matter.

*Disciplines* come from the local dispatch spec
(``_md_rewrite_tools/docs/agent-dispatch-spec.md``) that produced the 75 notes
already in the library; we built our own brief without reading it and paid for it
(see ``docs/补丁重构计划报告.md`` §四).

*Shape* is no longer written down here at all. 2026-10-15, seven notes came out
in a shape this project invented, because the brief was a hand transcription of
the part's spec that nobody ever compared against the spec itself
(``orchestrate/spec.py``). The brief now reads the part at dispatch time; these
tests pin the invariants that make "derived" mean "cannot drift".
"""
import pathlib
import re

from material_to_notes.orchestrate import pipeline as P
from material_to_notes.orchestrate import spec as S

# The real path. We once wrote it one directory short
# (parts/md-rewrite-engine/configs/…) and every sheet pointed at a dead file.
SPEC_PATH = "parts/md-rewrite-engine/src/md_rewrite_engine/configs/note_style_spec.yaml"


def _brief(env=None) -> str:
    return "\n".join(P.note_brief(env))


# --- 形状段确实是从零件现读的 ----------------------------------------------

def test_every_frontmatter_field_the_spec_lists_reaches_the_brief():
    spec = S.load_spec()
    brief = _brief()
    for name in S.frontmatter_fields(spec):
        assert f"`{name}`" in brief, f"派活单没告诉写手 frontmatter 要有 {name}"


def test_every_body_column_the_spec_lists_reaches_the_brief():
    spec = S.load_spec()
    brief = _brief()
    for _key, heading in S.columns(spec):
        assert heading in brief, f"派活单没告诉写手要写 {heading}"


def test_every_piece_label_the_spec_lists_reaches_the_brief():
    for label in S.pieces(S.load_spec()):
        assert label in _brief(), label


def test_brief_points_at_the_real_spec_path():
    brief = _brief()
    assert SPEC_PATH in brief
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    assert (repo_root / SPEC_PATH).is_file(), "派活单指的规范文件必须真的存在"


# --- 示范角度该写成什么：读规范自己的话，别手抄 --------------------------------
# 2026-10-16：对 10 份已有笔记做可读性实测（只喂笔记、禁读原文），四批测试者各自独立报出
# 同一个毛病——「通俗类比」与「示范角度①」讲的是同一件事，常常几乎逐字相同；10 份全中。
# 根因是派活单同时要求这两条、却没说清分工。规范里其实写着它俩该各干什么。

def test_the_brief_reads_what_the_spec_says_the_angles_are_for():
    # 规范在 feynman_per_kp 上方那条注释里定了性：教学留白、不写满教学稿
    assert "不写满教学稿" in _brief(), \
        "规范自己写的『示范角度是留白、不写满教学稿』没进派活单"


def test_editing_that_spec_comment_changes_the_next_brief(tmp_path):
    real = S.spec_path().read_text(encoding="utf-8")
    edited = real.replace("不写满教学稿", "每条不超过二十字")
    assert edited != real

    brief = _brief(_fake_part(tmp_path, edited))
    assert "每条不超过二十字" in brief
    assert "不写满教学稿" not in brief


def test_the_brief_forbids_restating_the_analogy_or_the_pitfalls():
    brief = _brief()
    assert "不许复述" in brief
    assert "通俗类比" in brief and "易错点" in brief


def test_the_brief_tells_the_writer_how_to_self_check_a_demo_line():
    assert "原文里没有的新信息" in _brief()


# --- 不许注水（2026-10-16 拿 10 份已有笔记做可读性实测，学来的七条）----------
# 2026-10-17 追加四条（用户拍板，见 docs/Task清单.md §9.15）：重复的判据要写清 /
# 示范角度不许与自测题同题 / 实用提示搬到易错点或元信息 / 版面数字不必塞 /
# 源文缺的操作环节要点名。

def test_brief_carries_the_no_padding_rules():
    brief = _brief()
    # 2026-10-21 用户二轮裁定：补充不再要求「笔记补充」标注，边界说明只进元信息；
    # 注水七条其余口径不变。
    for token in ("同一件事全篇只详述一次", "改成指路", "不许复述前文",
                  "只放「读者真的会犯的错」", "一处编号只许一套体系",
                  "附录紧跟核心知识点、排在 `📖 专业词汇表` 之前",
                  "边界说明只进元信息"):
        assert token in brief, token


def test_the_duplication_rule_says_what_counts_as_duplication():
    # 收官实测报的 7 处"凑字数"，抽查后发现全落在同一个知识点的六件套里——
    # 那是规范规定的形状。判据不写清，写手会为了"不重复"把同一个点的六件套削残。
    brief = _brief()
    assert "六件套各说一次不算重复" in brief
    assert "不同知识点之间" in brief


def test_the_demo_angle_must_not_repeat_the_self_test():
    assert "不许与文末" in _brief() and "自测题" in _brief()


def test_brief_carries_the_edit_discipline():
    # 三条改稿纪律，每条各对应一次真实返工：一处译反有 4 个落点、把内部文件路径
    # 写进了交付物、改了元信息条数却没同步概述里的"共 N 条"。
    brief = _brief()
    for token in ("改一处说法，先搜「孪生句」",
                  "只许指向交付物内部的真实位置",
                  "改了任何「数目」都要全文同步"):
        assert token in brief, token


def test_the_brief_says_where_a_useful_tip_belongs():
    # 示范角度里不许夹带讲解；真有用的提示放易错点/元信息并标注，不是删掉了事。
    brief = _brief()
    assert "易错点" in brief and "元信息" in brief
    assert "别把提示删掉了事" in brief


def test_the_brief_stops_writers_padding_layout_numbers():
    # B-6：对账拿源文全部数字当必留，写手只好把坐标轴刻度、文献页码塞进笔记。
    # 现在缺口有 _元数据/照录/ 兜底（验收标准 B-2），写手不必再塞。
    brief = _brief()
    assert "版面数字" in brief
    assert "照录" in brief


def test_the_brief_asks_writers_to_name_the_source_gaps():
    # 收官实测点名 9 处"只能靠猜"。原规范只要求登记不许补；2026-10-21 用户裁定改为
    # 允许补且更好的是直接写落点进正文；同日二轮裁定：补充不再要标注、免责句全清。
    brief = _brief()
    assert "源文缺" in brief and "元信息" in brief
    assert "背景知识补充纪律" in brief
    assert "不许是错误信息" in brief
    assert "不能顶替对账" in brief
    # 2026-10-21 用户三次强调「禁止瞎编」：没根据就不补、不许编像样答案。
    # 第四轮裁定：顺便知识允许（不许跑太偏 + 及时回归正题）；原文有错须查证裁决。
    assert "有根据、贴题目" in brief
    assert "宁可不写" in brief
    assert "编一个像样的答案" in brief
    assert "顺便知识允许写" in brief
    assert "不许跑太偏" in brief
    assert "及时回归正题" in brief
    assert "先查证、后裁决" in brief
    assert "查不动才把两者并列保留" in brief
    assert "缺口要有落点" in brief
    assert "免责句全清" in brief
    assert "正文出现的新词必须入册" in brief
    # 二轮裁定后，旧标注要求与正文「源文没写」句型必须不再作为要求出现。
    assert "（笔记补充：…）" not in brief
    assert "「笔记补充：…」" not in brief


def test_the_brief_warns_that_one_backslash_breaks_a_cases_block():
    # 实测踩过：源文用文字描述、写手自己改写成 \begin{cases} 时把分支换行写成 `\ `，
    # 两个分支挤成一行、整条公式读不出来。
    brief = _brief()
    assert "cases" in brief
    assert "双反斜杠" in brief


# --- 改规范 → 派活单跟着变（Task-11 的目的本身）---------------------------

def _fake_part(tmp_path, spec_text):
    """A throwaway parts tree holding the edited spec and the real gate script."""
    root = tmp_path / "parts" / "md-rewrite-engine"
    (root / "src" / "md_rewrite_engine" / "configs").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "src/md_rewrite_engine/configs/note_style_spec.yaml").write_text(
        spec_text, encoding="utf-8")
    (root / "scripts/gate_check.py").write_text(
        S.gate_path().read_text(encoding="utf-8"), encoding="utf-8")
    return {"MATERIAL_TO_NOTES_PARTS_DIR": str(tmp_path / "parts")}


def test_editing_the_spec_edits_the_next_brief(tmp_path):
    real = S.spec_path().read_text(encoding="utf-8")
    edited = real.replace("frontmatter:\n  - title        # 标题",
                          "frontmatter:\n  - sources      # 溯源\n  - title        # 标题")
    edited = edited.replace("feynman_per_kp: 2-4", "feynman_per_kp: 5-6")
    assert edited != real

    brief = _brief(_fake_part(tmp_path, edited))
    assert "`sources`" in brief
    assert "5-6" in brief
    assert "2-4" not in brief


def test_a_new_column_in_the_spec_is_an_error_not_a_silent_omission(tmp_path):
    real = S.spec_path().read_text(encoding="utf-8")
    edited = real.replace("  - meta_footer      # 元信息尾部",
                          "  - meta_footer      # 元信息尾部\n  - changelog        # 变更记录")
    env = _fake_part(tmp_path, edited)
    try:
        P.note_brief(env)
    except S.SpecUnavailable as exc:
        assert "changelog" in str(exc)
    else:
        raise AssertionError("规范新增栏目却被静默跳过 —— 这正是'漏读规范'的老路")


def test_a_missing_part_is_an_error_not_a_guessed_shape(tmp_path):
    env = {"MATERIAL_TO_NOTES_PARTS_DIR": str(tmp_path / "nowhere")}
    try:
        P.note_brief(env)
    except S.SpecUnavailable:
        pass
    else:
        raise AssertionError("读不到零件规范不该照样发单")


# --- 派活单印出来的形状，零件门禁真的解析得出来 ----------------------------

def test_the_kp_heading_the_brief_prints_matches_the_parts_parser():
    # 光有图案不够：门禁是 re.finditer(_KP_HEADING, note, re.S) 调的，标志也得跟着读
    pattern, flags = S.gate_kp_pattern(), S.gate_kp_flags()
    assert re.search(pattern, S._KP_EXAMPLE, flags), \
        "派活单给的知识点标题形状，零件门禁解析不出来"
    assert not re.search(pattern, S._KP_OLD_SHAPE, flags), \
        "我们旧的错形状不该还能过门禁（那说明门禁松了，不是我们对了）"


def test_every_piece_label_the_brief_prints_is_one_the_gate_looks_for():
    brief = _brief()
    for label in S.gate_six_labels():
        assert label in brief, f"门禁按 {label} 找六件套，派活单却没提它"


def test_the_brief_names_every_demo_mark_the_gate_counts():
    brief = _brief()
    marks = S.gate_feynman_marks()
    assert marks, "门禁里应该有示范角度的标号类"
    for char in marks.strip("[]"):
        assert char in brief, f"门禁按 {char} 计数，派活单却没提它"


# --- 纪律段落（本地派活规范沉淀下来的）-------------------------------------

def test_brief_carries_the_self_added_content_rule():
    brief = _brief()
    assert "自加内容纪律" in brief
    assert "必须先自己实跑或复算" in brief
    assert "照抄源文结果、再补一段解释" in brief


def test_brief_carries_the_source_damage_checklist():
    brief = _brief()
    assert "源文破坏形态清单" in brief
    for token in ("缩进整体丢失", "行号污染", "LaTeX 假公式", "HTML 表格", "反转义残留", "边栏被当标题"):
        assert token in brief, token
    # 反向陷阱：看起来像错、其实是作者的设计，不许改
    assert "不许改" in brief


def test_brief_carries_the_version_drift_method():
    brief = _brief()
    assert "版本差异处理法" in brief
    assert "输出相同不代表东西相同" in brief


def test_brief_tells_the_writer_it_may_push_back():
    assert "不是圣旨" in _brief()


def test_brief_is_rendered_into_the_sheet(tmp_path):
    sheet = P.assign_sheet(tmp_path, "note")
    assert "自加内容纪律" in sheet
    assert "源文破坏形态清单" in sheet
    assert "版本差异处理法" in sheet
    assert S._KP_TEMPLATE.split(" ")[0] in sheet


def test_the_note_sheet_warns_against_the_overwriting_command(tmp_path):
    """`material-to-notes step … note` 会 shell 调 mre **重新生成**笔记，把 agent 手写的产物顶掉。

    这行命令此前就印在写笔记的任务单上，与同一张单"由你亲自写笔记"的说明自相矛盾，
    照单执行就会误覆盖（T57）。
    """
    sheet = P.assign_sheet(tmp_path, "note")
    assert "执行：`material-to-notes step" not in sheet
    assert "不要" in sheet and "覆盖" in sheet


def test_other_steps_still_print_their_own_command(tmp_path):
    # note 是特例；其余步骤本来就是让 agent 跑那条命令
    sheet = P.assign_sheet(tmp_path, "clean")
    assert "执行：`material-to-notes step" in sheet


# --- 交稿前自检三道（2026-10-22，图形学第 1/2 章实战）------------------------

def test_brief_carries_the_three_pre_submit_self_checks():
    # 三条原则本来都在上面的纪律里，缺的是"交稿前必须做完"的动作，所以这里测动作词：
    # ① 撞题——两章都栽，全靠审核抓回；② 台账——元信息声称已写、正文里没有；
    # ③ 规则句——第 2 章数字复算全对，三处错误级全在方向/符号/终止条件。
    brief = _brief()
    assert "交稿前自检三道" in brief
    assert "能不能直接回答那道自测题" in brief
    assert "去正文搜一次" in brief
    assert "每句代两组数字实推一遍" in brief


def test_the_self_check_evidence_goes_to_the_report_not_the_note():
    # 正文不许带解释尾巴（免责句全清），自检痕迹只能落在回报里。
    assert "结论与证据写进回报" in _brief()


def test_pre_submit_self_checks_reach_the_sheet(tmp_path):
    assert "交稿前自检三道" in P.assign_sheet(tmp_path, "note")
