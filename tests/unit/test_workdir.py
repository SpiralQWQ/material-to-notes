"""Tests for contract.workdir — layout creation and filename safety."""

from material_to_notes.contract import steps as S
from material_to_notes.contract import workdir as W


def test_ensure_creates_full_layout(tmp_path):
    W.ensure(tmp_path)
    for name in W.subdirs():
        assert (tmp_path / name).is_dir(), name
    assert W.missing(tmp_path) == []


def test_ensure_is_idempotent_and_keeps_content(tmp_path):
    W.ensure(tmp_path)
    marker = tmp_path / "01_取材" / "keep.txt"
    marker.write_text("x", encoding="utf-8")
    W.ensure(tmp_path)
    assert marker.read_text(encoding="utf-8") == "x"


def test_missing_reports_absent(tmp_path):
    not_there = tmp_path / "does-not-exist"
    assert W.missing(not_there) == ["<workdir>"]
    assert W.missing(tmp_path) != []
    W.ensure(tmp_path)
    assert W.missing(tmp_path) == []


def test_chinese_and_space_path(tmp_path):
    root = tmp_path / "我的 工作目录"
    W.ensure(root)
    assert (root / "01_取材").is_dir()


def test_safe_filename_strips_illegal_chars():
    assert W.safe_filename('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"


def test_safe_filename_guards_reserved_names():
    assert W.safe_filename("con").startswith("_")
    assert W.safe_filename("NUL.txt").startswith("_")
    assert W.safe_filename("com7").startswith("_")


def test_safe_filename_caps_length_keeping_extension():
    out = W.safe_filename("y" * 300 + ".md")
    assert len(out) <= W._MAX_NAME
    assert out.endswith(".md")


def test_safe_filename_empty_becomes_placeholder():
    assert W.safe_filename("   ") == "_"
    assert W.safe_filename("") == "_"


def test_step_dir_matches_step():
    assert W.step_dir("/tmp/run", S.get_step("note")).name == "04_笔记"
    assert W.step_dir("/tmp/run", S.get_step("fetch")).name == "01_取材"
