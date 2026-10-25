"""S2-③ 终点一致性：殊途同归必须同果。

分组见 docs/穷举测试方案.md 第四节。任一不一致即 bug。
"""

import pytest

from _mocks import DOC_SPEC, FETCH_DOC_SPEC, FETCH_MEDIA_SPEC, MEDIA_SPEC, executors
from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate import pipeline as PL

ARTIFACTS = ("02_转md/v_clean.md", "03_清洗/v.txt", "04_笔记/note.md")


def _sheet(root):
    return (root / W.PROGRESS_FILE).read_text(encoding="utf-8")


def _sheet_shape(text):
    """Column shape only — the row contents differ, the structure must not."""
    return [len(line.split("|")) for line in text.splitlines() if line.startswith("| ")]


def _labels(text):
    return [line.split("：")[0] for line in text.splitlines() if line.startswith("- ")]


# --- G-A 媒体线到笔记（直给媒体 vs 爬来的媒体） ---------------------------

@pytest.mark.parametrize("target,kind,spec", [
    ("v.mp4", None, MEDIA_SPEC),
    ("a.mp3", None, MEDIA_SPEC),
    ("img.png", None, MEDIA_SPEC),
    ("https://x/v", None, FETCH_MEDIA_SPEC),
    ("python 入门", "terms", FETCH_MEDIA_SPEC),
])
def test_group_a_paths_share_one_endpoint(tmp_path, target, kind, spec):
    assert PL.run(tmp_path, target, kind=kind, executors=executors(spec))["report"].ok
    assert (tmp_path / "04_笔记" / "note.md").is_file()


# --- G-B 文档线到笔记 ------------------------------------------------------

@pytest.mark.parametrize("target,kind,spec", [
    ("a.pdf", None, DOC_SPEC),
    ("a.docx", None, DOC_SPEC),
    ("https://x/p", None, FETCH_DOC_SPEC),
])
def test_group_b_paths_share_one_endpoint(tmp_path, target, kind, spec):
    assert PL.run(tmp_path, target, kind=kind, executors=executors(spec))["report"].ok
    assert (tmp_path / "04_笔记" / "note.md").is_file()


def test_group_a_and_group_b_have_the_same_sheet_shape(tmp_path):
    media, document = tmp_path / "media", tmp_path / "doc"
    PL.run(media, "v.mp4", executors=executors(MEDIA_SPEC))
    PL.run(document, "a.pdf", executors=executors(DOC_SPEC))
    assert _sheet_shape(_sheet(media)) == _sheet_shape(_sheet(document))


# --- G-C 停下问人 ----------------------------------------------------------

@pytest.mark.parametrize("target", ["", "a.exe", "a.zip", "   "])
def test_group_c_ask_user_leaves_nothing_behind(tmp_path, target):
    result = PL.run(tmp_path, target, executors=executors({}))
    assert result["asked_user"]
    assert not (tmp_path / W.FAILURE_FILE).exists()
    assert not (tmp_path / W.PROGRESS_FILE).exists()


# --- G-D 失败交班（四要素标签必须逐字一致） -------------------------------

EXPECTED_LABELS = ["- 卡在哪步", "- 报什么错", "- 试过什么", "- 产物在哪"]


@pytest.mark.parametrize("step", ["media", "clean", "note"])
def test_group_d_failure_sheets_share_the_same_labels(tmp_path, step):
    PL.run(tmp_path, "v.mp4", executors=executors(MEDIA_SPEC, fail=(step,)), max_attempts=2)
    assert _labels((tmp_path / W.FAILURE_FILE).read_text(encoding="utf-8")) == EXPECTED_LABELS


def test_group_d_the_two_sheets_agree_on_whether_the_run_stopped(tmp_path):
    """两张单必须同口径：停下了才有失败单，跑通了就不该留着。

    真跑踩到过两者并存——失败单说 clean 挂了，进度单说 clean 完成。
    ARTIFACTS 里没有失败单，所以这条一致性此前无人照看。
    """
    stopped = tmp_path / "stopped"
    PL.run(stopped, "v.mp4", executors=executors(MEDIA_SPEC, fail=("clean",)), max_attempts=1)
    assert (stopped / W.FAILURE_FILE).is_file()

    straight = tmp_path / "straight"
    PL.run(straight, "v.mp4", executors=executors(MEDIA_SPEC))
    assert not (straight / W.FAILURE_FILE).exists()

    recovered = tmp_path / "recovered"
    PL.run(recovered, "v.mp4", executors=executors(MEDIA_SPEC, fail=("clean",)), max_attempts=1)
    PL.run(recovered, "v.mp4", executors=executors(MEDIA_SPEC))
    assert not (recovered / W.FAILURE_FILE).exists()
    assert (recovered / W.PROGRESS_FILE).is_file()



# --- G-E 续跑收敛（与不中断直跑逐字节一致） -------------------------------

def test_group_e_resumed_matches_straight_through(tmp_path):
    straight, resumed = tmp_path / "straight", tmp_path / "resumed"
    PL.run(straight, "v.mp4", executors=executors(MEDIA_SPEC))
    PL.run(resumed, "v.mp4", executors=executors(MEDIA_SPEC, fail=("note",)), max_attempts=1)
    PL.run(resumed, "v.mp4", executors=executors(MEDIA_SPEC))
    for rel in ARTIFACTS:
        assert (resumed / rel).read_bytes() == (straight / rel).read_bytes(), rel
