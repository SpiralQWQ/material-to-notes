"""Tests for gates.review."""

import pytest

from material_to_notes.gates import review as RV


def test_checklist_for_known_step():
    data = RV.checklist("note")
    assert data["step"] == "note" and data["specific"] and data["global"]


def test_checklist_rejects_unknown_step():
    with pytest.raises(KeyError):
        RV.checklist("nope")


def test_render_has_global_checks():
    text = RV.render("clean")
    assert "G1" in text and "G2" in text and "clean" in text


def test_render_includes_flags():
    text = RV.render("note", flagged=["第 3 节疑似幻觉"])
    assert "疑似幻觉" in text and "已标记" in text


def test_collect_flags_drops_falsy():
    assert RV.collect_flags(["a", "", None, "b"]) == ("a", "b")


def test_note_checklist_covers_the_two_pre_submit_slips():
    # 2026-10-22：撞题与台账两处都是"写手自述没问题、审核抓回"的类型。
    # 审核单必须逐条点到，否则下一位审核者照着单子走还会漏。
    items = " ".join(RV.checklist("note")["specific"])
    assert "撞题" in items
    assert "元信息" in items and "正文" in items
