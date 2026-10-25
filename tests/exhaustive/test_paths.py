"""S2-① 路径穷举：每条「入口 → 操作序列 → 终点」都要可达且行为正确。

路径清单见 docs/穷举测试方案.md 第二节。
"""

import pytest

from _mocks import DOC_SPEC, FETCH_DOC_SPEC, FETCH_MEDIA_SPEC, MEDIA_SPEC
from _mocks import executors
from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate import pipeline as PL

NOTE = "04_笔记/note.md"


# --- 成功线 ----------------------------------------------------------------

@pytest.mark.parametrize("target,kind,spec,chain", [
    ("v.mp4", None, MEDIA_SPEC, ("media", "clean", "note")),
    ("a.mp3", None, MEDIA_SPEC, ("media", "clean", "note")),
    ("img.png", None, MEDIA_SPEC, ("media", "clean", "note")),
    ("a.pdf", None, DOC_SPEC, ("document", "clean", "note")),
    ("a.docx", None, DOC_SPEC, ("document", "clean", "note")),
    ("a.pptx", None, DOC_SPEC, ("document", "clean", "note")),
    ("a.html", None, DOC_SPEC, ("document", "clean", "note")),
    ("https://x/v", None, FETCH_MEDIA_SPEC, ("fetch", "media", "clean", "note")),
    ("https://x/p", None, FETCH_DOC_SPEC, ("fetch", "document", "clean", "note")),
    ("python 入门", "terms", FETCH_DOC_SPEC, ("fetch", "document", "clean", "note")),
])
def test_success_paths_reach_the_note(tmp_path, target, kind, spec, chain):
    result = PL.run(tmp_path, target, kind=kind, executors=executors(spec))
    assert result["report"].ok
    assert [r.step for r in result["report"].records] == list(chain)
    assert (tmp_path / NOTE).is_file()
    assert (tmp_path / W.PROGRESS_FILE).is_file()


def test_album_folder_path(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    assert PL.run(tmp_path, str(folder), executors=executors(MEDIA_SPEC))["report"].ok


# --- 停下问人线 ------------------------------------------------------------

@pytest.mark.parametrize("target,kind", [("", None), ("   ", None), ("a.exe", None), ("a.zip", None)])
def test_ask_user_paths(tmp_path, target, kind):
    result = PL.run(tmp_path, target, kind=kind, executors=executors({}))
    assert result["asked_user"] and result["report"] is None
    assert not (tmp_path / W.FAILURE_FILE).exists()


def test_bare_word_without_kind_asks_user(tmp_path):
    assert PL.run(tmp_path, "python 入门", executors=executors({}))["asked_user"]


# --- 失败交班线 ------------------------------------------------------------

@pytest.mark.parametrize("step", ["media", "clean", "note"])
def test_failure_paths_write_handoff(tmp_path, step):
    result = PL.run(tmp_path, "v.mp4", executors=executors(MEDIA_SPEC, fail=(step,)), max_attempts=3)
    assert not result["report"].ok and result["report"].stopped_at == step
    assert (tmp_path / W.FAILURE_FILE).is_file()


def test_failure_does_not_run_later_steps(tmp_path):
    result = PL.run(tmp_path, "v.mp4", executors=executors(MEDIA_SPEC, fail=("clean",)))
    assert result["report"].status_of("note") == ""


# --- 续跑线 ----------------------------------------------------------------

def test_interrupted_then_resumed(tmp_path):
    broken = executors(MEDIA_SPEC, fail=("note",))
    assert not PL.run(tmp_path, "v.mp4", executors=broken)["report"].ok
    resumed = PL.run(tmp_path, "v.mp4", executors=executors(MEDIA_SPEC))
    assert resumed["report"].ok
    assert [r.status for r in resumed["report"].records] == ["skipped", "skipped", "done"]


def test_corrupt_state_then_resumed(tmp_path):
    from material_to_notes.orchestrate import workspace as WS

    WS.init(tmp_path)
    WS.state_path(tmp_path).write_text("{ half", encoding="utf-8")
    assert PL.run(tmp_path, "v.mp4", executors=executors(MEDIA_SPEC))["report"].ok


def test_changed_input_reruns_only_that_step(tmp_path):
    execs = executors(MEDIA_SPEC)
    PL.run(tmp_path, "v.mp4", executors=execs)
    (tmp_path / "02_转md" / "v_clean.md").write_text("changed", encoding="utf-8")
    resumed = PL.run(tmp_path, "v.mp4", executors=execs)["report"]
    assert resumed.status_of("media") == "skipped"
    assert resumed.status_of("clean") == "done"
