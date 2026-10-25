"""Tests for contract.steps — the single source of truth."""

from material_to_notes.contract import steps as S


def test_all_five_steps_present_in_order():
    assert S.step_ids() == ("fetch", "document", "media", "clean", "note")


def test_every_step_has_required_fields():
    for step in S.STEPS:
        assert isinstance(step.id, str) and step.id
        assert isinstance(step.name, str) and step.name
        assert isinstance(step.tool, str) and step.tool
        assert isinstance(step.accepts, tuple) and step.accepts
        assert isinstance(step.produces, tuple) and step.produces
        assert isinstance(step.workdir_subdir, str) and step.workdir_subdir


def test_step_ids_are_unique():
    ids = [s.id for s in S.STEPS]
    assert len(ids) == len(set(ids))


def test_tools_are_distinct():
    tools = [s.tool for s in S.STEPS]
    assert len(tools) == len(set(tools))


def test_get_step_returns_matching_step():
    assert S.get_step("note").tool == "mre"
    assert S.get_step("fetch").tool == "wkc"


def test_get_step_unknown_raises_with_hint():
    try:
        S.get_step("nope")
    except KeyError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("expected KeyError for an unknown step id")


def test_steps_for_kind():
    assert S.steps_for("video") == (S.get_step("media"),)
    assert S.get_step("fetch") in S.steps_for("links")
    assert S.steps_for("nothing-uses-this-kind") == ()


def test_workdir_subdirs_match_contract_layout():
    subs = {s.workdir_subdir for s in S.STEPS}
    assert subs == {"01_取材", "02_转md", "03_清洗", "04_笔记"}


def test_only_clean_is_optional():
    assert [s.id for s in S.STEPS if s.optional] == ["clean"]
