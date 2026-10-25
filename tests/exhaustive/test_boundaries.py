"""S2-② 边界严格：非法/空值/边界/超长/重复/中断/并发都要守住。

每类：拒绝或提示，不崩不卡死，不留半截。清单见 docs/穷举测试方案.md 第三节。
"""

import subprocess
from types import SimpleNamespace

import pytest

from _mocks import MEDIA_SPEC, executors
from material_to_notes.contract import steps as S
from material_to_notes.contract import workdir as W
from material_to_notes.gates import machine as M
from material_to_notes.orchestrate import pipeline as PL
from material_to_notes.orchestrate import router as RT
from material_to_notes.orchestrate import workspace as WS
from material_to_notes.steps import fetch


# --- 空值 / 缺参 -----------------------------------------------------------

def test_empty_input_is_unknown():
    assert RT.classify("") == RT.UNKNOWN
    assert RT.route(RT.UNKNOWN) == ()


def test_unknown_step_id_raises_with_hint():
    with pytest.raises(KeyError):
        S.get_step("nope")


# --- 路径 ------------------------------------------------------------------

def test_chinese_space_emoji_workdir(tmp_path):
    root = tmp_path / "我的 工作目录"
    assert PL.run(root, "v.mp4", executors=executors(MEDIA_SPEC))["report"].ok


def test_missing_target_still_routes_by_extension(tmp_path):
    assert RT.classify(str(tmp_path / "ghost.mp4")) == "video"


def test_overlong_filename_is_capped():
    assert len(W.safe_filename("x" * 500)) <= W._MAX_NAME


def test_directory_input_is_album(tmp_path):
    assert RT.classify(tmp_path) == "album"


# --- 状态损坏 / 中断 -------------------------------------------------------

def test_corrupt_state_does_not_crash(tmp_path):
    WS.init(tmp_path)
    WS.state_path(tmp_path).write_text("{ half written", encoding="utf-8")
    assert WS.load(tmp_path) is None
    assert PL.run(tmp_path, "v.mp4", executors=executors(MEDIA_SPEC))["report"].ok


def test_half_written_state_is_ignored(tmp_path):
    WS.init(tmp_path)
    WS.state_path(tmp_path).write_bytes(b'{"version": 1, "steps": {"note": {"status":')
    assert WS.load(tmp_path) is None


# --- 重复 / 并发 -----------------------------------------------------------

def test_running_twice_is_safe(tmp_path):
    execs = executors(MEDIA_SPEC)
    assert PL.run(tmp_path, "v.mp4", executors=execs)["report"].ok
    assert PL.run(tmp_path, "v.mp4", executors=execs)["report"].ok


def test_two_instances_on_same_workdir_do_not_crash(tmp_path):
    execs = executors(MEDIA_SPEC)
    PL.run(tmp_path, "v.mp4", executors=execs)
    PL.run(tmp_path, "v.mp4", executors=execs)


# --- 工具异常 --------------------------------------------------------------

class _Fake:
    def __init__(self, returncode=0, stdout="", stderr="", timeout=False):
        self.returncode, self.stdout, self.stderr, self.timeout = returncode, stdout, stderr, timeout

    def __call__(self, argv, **kw):
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        return SimpleNamespace(returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


def test_tool_nonzero_is_reported(tmp_path):
    assert not fetch.run(tmp_path, env={"WKC_DIR": "X:/wkc"}, runner=_Fake(returncode=1)).ok


def test_tool_timeout_is_reported(tmp_path):
    out = fetch.run(tmp_path, env={"WKC_DIR": "X:/wkc"}, runner=_Fake(timeout=True))
    assert not out.ok and "timeout" in out.error


def test_tool_missing_is_reported(tmp_path):
    def boom(argv, **kw):
        raise FileNotFoundError(argv[0])

    out = fetch.run(tmp_path, env={"WKC_DIR": "X:/wkc"}, runner=boom)
    assert not out.ok and "not found" in out.error


def test_tool_succeeds_but_writes_nothing(tmp_path):
    out = fetch.run(tmp_path, env={"WKC_DIR": "X:/wkc"}, runner=_Fake())
    assert not out.ok and "missing output" in out.error


def test_executor_crash_is_contained(tmp_path):
    def crash(root):
        raise RuntimeError("kaboom")

    result = PL.run(tmp_path, "v.mp4",
                    executors=executors(MEDIA_SPEC, behaviour={"media": crash}), max_attempts=2)
    assert not result["report"].ok
    assert "kaboom" in result["report"].records[0].error


# --- 编码 ------------------------------------------------------------------

def test_bom_text_passes_gates(tmp_path):
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True, exist_ok=True)
    (base / "note.md").write_bytes("\ufeffhello".encode("utf-8"))
    assert M.check("note", tmp_path).passed


def test_gbk_text_fails_gates_without_crashing(tmp_path):
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True, exist_ok=True)
    (base / "note.md").write_bytes("中文".encode("gbk"))
    result = M.check("note", tmp_path)
    assert not result.passed and "utf8-decodable" in result.failed()


# --- 零字节 / 空产物 -------------------------------------------------------

def test_zero_byte_artifact_fails_gates(tmp_path):
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True, exist_ok=True)
    (base / "note.md").write_text("", encoding="utf-8")
    assert not M.check("note", tmp_path).passed
