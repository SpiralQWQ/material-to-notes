"""Tests for contract.validate — output shape checking."""

import pytest

from material_to_notes.contract import steps as S
from material_to_notes.contract import validate as V


def _step(**kw):
    base = dict(id="t", name="t", tool="x", accepts=("a",),
                produces=("out.md",), workdir_subdir="01_取材")
    base.update(kw)
    return S.Step(**base)


def _put(root, step, files):
    base = root / step.workdir_subdir
    base.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_ok_when_literal_output_present(tmp_path):
    step = _step(produces=("out.md",))
    _put(tmp_path, step, {"out.md": "hello"})
    V.check_step_output(tmp_path, step)


def test_missing_literal_file_raises(tmp_path):
    step = _step(produces=("out.md",))
    _put(tmp_path, step, {"other.md": "x"})
    with pytest.raises(V.ContractError):
        V.check_step_output(tmp_path, step)


def test_empty_literal_file_raises(tmp_path):
    step = _step(produces=("out.md",))
    _put(tmp_path, step, {"out.md": ""})
    with pytest.raises(V.ContractError):
        V.check_step_output(tmp_path, step)


def test_missing_dir_raises(tmp_path):
    step = _step(produces=("images/",))
    _put(tmp_path, step, {"out.md": "x"})
    with pytest.raises(V.ContractError):
        V.check_step_output(tmp_path, step)


def test_dir_present_passes(tmp_path):
    step = _step(produces=("images/",))
    _put(tmp_path, step, {"images/a.png": "x"})
    V.check_step_output(tmp_path, step)


def test_stem_glob_passes(tmp_path):
    step = _step(produces=("{stem}_clean.md",))
    _put(tmp_path, step, {"a_clean.md": "x"})
    V.check_step_output(tmp_path, step)


def test_stem_glob_without_match_raises(tmp_path):
    step = _step(produces=("{stem}_clean.md",))
    _put(tmp_path, step, {"unrelated.md": "x"})
    with pytest.raises(V.ContractError):
        V.check_step_output(tmp_path, step)


def test_stem_glob_all_empty_raises(tmp_path):
    step = _step(produces=("{stem}_clean.md",))
    _put(tmp_path, step, {"a_clean.md": ""})
    with pytest.raises(V.ContractError):
        V.check_step_output(tmp_path, step)


def test_recursive_glob_ok(tmp_path):
    step = _step(produces=("**/meta.json",))
    _put(tmp_path, step, {"term/site/meta.json": "{}"})
    V.check_step_output(tmp_path, step)


def test_missing_step_dir_raises(tmp_path):
    with pytest.raises(V.ContractError):
        V.check_step_output(tmp_path, _step())


def test_error_message_names_the_step(tmp_path):
    step = _step(id="fetch", produces=("out.md",))
    with pytest.raises(V.ContractError) as exc:
        V.check_step_output(tmp_path, step)
    assert "fetch" in str(exc.value)


# --- structure fidelity ----------------------------------------------------
# A real run caught this: cleaning exited 0 while deleting every HTML table and
# every $$ formula block. The loss was invisible, so the contract must see it.

_RICH = (
    "# 标题一\n\n正文段落。\n\n"
    "## 标题二\n\n<table><tr><td>a</td><tr><td>b</td></table>\n\n"
    "公式 $$E=mc^2$$ 与 $$\\alpha$$。\n\n"
    "```python\nprint(1)\n```\n\n第五行。\n"
)


def test_structure_profile_counts_markers():
    profile = V.structure_profile(_RICH)
    assert profile["headings"] == 2
    assert profile["table_cells"] == 2
    assert profile["formulas"] == 4          # two $$ pairs
    assert profile["code_fences"] == 2
    assert profile["lines"] == 15


def test_no_loss_reported_when_nothing_is_lost():
    assert V.structure_loss(_RICH, _RICH) == []


def test_collapsed_structure_lists_every_lost_marker():
    lost = V.structure_loss(_RICH, "标题一 正文段落 标题二")
    names = [item.split(" ")[0] for item in lost]
    assert sorted(names) == sorted(
        ["lines", "headings", "table_cells", "formulas", "code_fences"])
    # Each entry carries both counts, so a failure sheet says what actually went.
    assert any("table_cells 2->0" in item for item in lost)


def test_partial_loss_over_threshold_is_reported():
    # Dropping one of two headings keeps 50%, below the 90% floor.
    assert V.structure_loss(_RICH, _RICH.replace("## 标题二\n\n", ""))


def test_loss_under_threshold_is_tolerated():
    # One heading in twenty is 5% lost, inside the floor.
    doc = "\n".join(f"# 小节 {i}\n\n内容。" for i in range(20))
    assert V.structure_loss(doc, doc.replace("# 小节 7\n\n", "", 1)) == []


def test_markers_absent_upstream_are_never_reported():
    # A plain-text document has no tables to lose, so it can never fail on that.
    assert V.structure_loss("一段纯文本，没有结构。", "一段纯文本没有结构") == []


def test_ratio_is_configurable():
    one = _RICH.replace("## 标题二\n\n", "")
    assert V.structure_loss(_RICH, one, ratio=0.4) == []          # 50% clears 40%
    assert V.structure_loss(_RICH, one, ratio=1.0)               # exact-only does not


