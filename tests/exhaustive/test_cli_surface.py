# -*- coding: utf-8 -*-
"""S2-① 的 CLI 面：把「五步 × 命令行」这条轴补齐。

``test_paths.py`` 走的是编排层入口；这一份走**用户真正敲的命令行**，覆盖
``docs/穷举测试方案.md`` §七 闭包表里此前没有格子的那几行：

* 清洗两档（默认只剥水印 / ``--deep-clean`` 全规则）——以及**保真门禁两档都不豁免**；
* ``material-to-notes toc`` 这条命令本身（此前只有 ``refresh_tocs`` 的单元测试）。

CLI 的其余格子（init/intake/deliver/gate/assign/run/step/checklist）已在
``tests/unit/test_cli.py``、``tests/unit/test_intake.py``、``tests/e2e/`` 里各有点名，
闭包表把它们逐格指了过去。
"""
import pathlib
from types import SimpleNamespace

import pytest

from material_to_notes.cli import main as CLI
from material_to_notes.steps import clean as C

# 结构标记密集的源文：清洗后必须基本原样留下（structure_loss 默认留存线 90%）
FAITHFUL = "# 标题\n\n" + "".join(f"## 小节 {i}\n\n正文 {i}\n\n" for i in range(1, 11))
LOSSY = "# 标题\n\n## 小节 1\n\n只剩一行\n"


class _Tool:
    """替身：不真跑零件，只按 --output 落盘指定内容，并把 argv 留下来。"""

    def __init__(self, emit):
        self.argv = None
        self.emit = emit

    def __call__(self, argv, **kw):
        self.argv = [str(a) for a in argv]
        out = pathlib.Path(self.argv[self.argv.index("--output") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.emit, encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")


def _workdir(tmp_path):
    (tmp_path / "03_清洗").mkdir(parents=True, exist_ok=True)
    (tmp_path / "_元数据").mkdir(parents=True, exist_ok=True)


# --- 清洗两档 --------------------------------------------------------------

def test_watermark_only_is_the_default_command():
    argv = C.build_command("in.md", "out.txt")
    assert "--watermark-only" in argv


def test_deep_clean_drops_the_watermark_only_switch():
    argv = C.build_command("in.md", "out.txt", deep=True)
    assert "--watermark-only" not in argv
    # 两档的差别就该只有这一个开关
    assert set(C.build_command("in.md", "out.txt")) - set(argv) == {"--watermark-only"}


@pytest.mark.parametrize("deep", [False, True])
def test_a_faithful_clean_passes_in_both_modes(tmp_path, deep):
    _workdir(tmp_path)
    src = tmp_path / "in.md"
    src.write_text(FAITHFUL, encoding="utf-8")
    tool = _Tool(FAITHFUL)
    outcome = C.run(tmp_path, src_file=str(src), name="v", deep=deep, runner=tool)
    assert outcome.ok, outcome.error
    assert ("--watermark-only" in tool.argv) is (not deep)


@pytest.mark.parametrize("deep", [False, True])
def test_the_fidelity_gate_is_not_exempted_by_deep_clean(tmp_path, deep):
    """深洗不是"吃掉正文"的许可证：两档都得被保真门禁拦住。"""
    _workdir(tmp_path)
    src = tmp_path / "in.md"
    src.write_text(FAITHFUL, encoding="utf-8")
    outcome = C.run(tmp_path, src_file=str(src), name="v", deep=deep, runner=_Tool(LOSSY))
    assert not outcome.ok
    assert "collapsed" in outcome.error


# --- pipeline toc 这条命令 -------------------------------------------------

def _stub_toc_part(tmp_path):
    tool = tmp_path / "mre"
    (tool / "scripts").mkdir(parents=True, exist_ok=True)
    (tool / "scripts" / "toc_gen.py").write_text(
        "import sys, pathlib\n"
        "p = pathlib.Path(sys.argv[1])\n"
        "t = p.read_text(encoding='utf-8')\n"
        "if '本篇目录' not in t:\n"
        "    t = t.replace('# 标题\\n',"
        " '# 标题\\n\\n## \\U0001F4D1 本篇目录\\n\\n- [甲](#甲)\\n')\n"
        "    p.write_text(t, encoding='utf-8')\n",
        encoding="utf-8")
    return tool


def test_toc_cli_writes_the_table_of_contents(tmp_path, monkeypatch, capsys):
    root = tmp_path / "run"
    (root / "04_笔记").mkdir(parents=True)
    (root / "04_笔记" / "a.md").write_text("# 标题\n\n正文\n", encoding="utf-8")
    monkeypatch.setenv("MRE_DIR", str(_stub_toc_part(tmp_path)))

    assert CLI.main(["toc", str(root)]) == CLI.EXIT_OK
    assert "本篇目录" in (root / "04_笔记" / "a.md").read_text(encoding="utf-8")
    assert "a.md" in capsys.readouterr().out


def test_toc_cli_without_a_part_reports_instead_of_writing(tmp_path, monkeypatch, capsys):
    root = tmp_path / "run"
    (root / "04_笔记").mkdir(parents=True)
    original = "# 标题\n\n正文\n"
    (root / "04_笔记" / "a.md").write_text(original, encoding="utf-8")
    monkeypatch.delenv("MRE_DIR", raising=False)
    monkeypatch.setenv("MATERIAL_TO_NOTES_PARTS_DIR", str(tmp_path / "no-parts"))

    assert CLI.main(["toc", str(root)]) != CLI.EXIT_OK
    assert (root / "04_笔记" / "a.md").read_text(encoding="utf-8") == original
    assert "toc 脚本缺失" in capsys.readouterr().out
