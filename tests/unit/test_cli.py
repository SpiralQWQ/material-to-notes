"""Tests for cli.main."""

import pytest

from material_to_notes.cli import main as CLI


def test_version_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as exc:
        CLI.main(["--version"])
    assert exc.value.code == 0


def test_init_creates_workdir(tmp_path):
    assert CLI.main(["init", str(tmp_path)]) == CLI.EXIT_OK
    assert (tmp_path / "_state" / "run_state.json").is_file()


def test_route_known(capsys):
    assert CLI.main(["route", "a.mp4"]) == CLI.EXIT_OK
    assert "media" in capsys.readouterr().out


def test_route_unknown_returns_needs_user(capsys):
    assert CLI.main(["route", "a.exe"]) == CLI.EXIT_NEEDS_USER
    assert "不认识的输入" in capsys.readouterr().out


def test_gate_fails_when_no_output(tmp_path):
    assert CLI.main(["gate", str(tmp_path), "note"]) == CLI.EXIT_RUN_FAILED


def test_gate_passes_when_output_present(tmp_path):
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "note.md").write_text("hi", encoding="utf-8")
    assert CLI.main(["gate", str(tmp_path), "note", "--contract-only"]) == CLI.EXIT_OK


def test_gate_note_now_also_checks_the_content(tmp_path, capsys):
    # "hi" satisfies the output contract but is not a note: the note step's gate
    # is no longer just "a file exists".
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "note.md").write_text("hi", encoding="utf-8")
    assert CLI.main(["gate", str(tmp_path), "note"]) == CLI.EXIT_RUN_FAILED
    out = capsys.readouterr().out
    assert "note-frontmatter" in out and "内容门禁" not in out


def _stub_mre(tmp_path, exit_code):
    tool = tmp_path / "mre"
    (tool / "scripts").mkdir(parents=True)
    (tool / "scripts" / "gate_check.py").write_text(
        f"import sys\nsys.exit({exit_code})\n", encoding="utf-8")
    return tool


_NOTE = (
    "---\ntitle: t\nsource: full.txt\nauthor: a\nduration: 1\nword_count: 10\n"
    "created: 2026-10-15\ntags: [t]\ntype: note\n---\n\n# t\n\n"
    "> 一句话总结：只讲甲。\n\n## 📚 概述\n\n- 讲甲。\n\n"
    "## 🧠 核心知识点\n\n### 知识点 1.1 · 甲\n\n"
    "- **定义**：a\n- **类比**：b\n- **原理**：c\n"
    "- **示例**：d\n- **为什么**：e\n- **易错点**：f\n"
    "- **❓ 示范角度**：①（复述）甲是什么？②（挑错）甲等于乙，错在哪？\n\n"
    "## 📖 专业词汇表\n\n| a | b |\n\n## ❓ 自测题\n\n1. 甲？\n\n## 📌 元信息\n\n1. **x**：y\n"
)


def test_gate_note_passes_with_a_real_structure_and_a_passing_content_gate(tmp_path, monkeypatch):
    (tmp_path / "03_清洗").mkdir(parents=True)
    (tmp_path / "03_清洗" / "full.txt").write_text("# 源\n\n正文 42\n", encoding="utf-8")
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "full.md").write_text(_NOTE, encoding="utf-8")
    monkeypatch.setenv("MRE_DIR", str(_stub_mre(tmp_path, 0)))
    assert CLI.main(["gate", str(tmp_path), "note"]) == CLI.EXIT_OK


def test_gate_note_fails_when_the_content_gate_fails(tmp_path, monkeypatch, capsys):
    (tmp_path / "03_清洗").mkdir(parents=True)
    (tmp_path / "03_清洗" / "full.txt").write_text("# 源\n\n正文 42\n", encoding="utf-8")
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "full.md").write_text(_NOTE, encoding="utf-8")
    monkeypatch.setenv("MRE_DIR", str(_stub_mre(tmp_path, 1)))
    assert CLI.main(["gate", str(tmp_path), "note"]) == CLI.EXIT_RUN_FAILED
    assert "content-gate" in capsys.readouterr().out


def test_gate_note_fails_when_mre_is_unavailable(tmp_path, monkeypatch, capsys):
    (tmp_path / "03_清洗").mkdir(parents=True)
    (tmp_path / "03_清洗" / "full.txt").write_text("# 源\n\n正文 42\n", encoding="utf-8")
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "full.md").write_text(_NOTE, encoding="utf-8")
    monkeypatch.delenv("MRE_DIR", raising=False)
    # The parts live in parts/ now, so "unavailable" means neither the env
    # override nor the in-repo copy resolves.
    monkeypatch.setenv("MATERIAL_TO_NOTES_PARTS_DIR", str(tmp_path / "no-parts"))
    assert CLI.main(["gate", str(tmp_path), "note"]) == CLI.EXIT_RUN_FAILED
    assert "content gate unavailable" in capsys.readouterr().out


def test_gate_rejects_unknown_step(tmp_path, capsys):
    assert CLI.main(["gate", str(tmp_path), "nope"]) == CLI.EXIT_NEEDS_USER
    assert "unknown step id" in capsys.readouterr().out


def test_gate_note_records_the_note_row_in_the_progress_sheet(tmp_path, monkeypatch):
    """笔记由 agent 手写、不走 `pipeline step`，跑完那条链的进度单里从来没有它那一行。

    门禁通过是"这一步确实成了"的认证点，此刻把它补进进度单——否则进度单与磁盘
    对不上（SOP §六 / T58）。
    """
    (tmp_path / "03_清洗").mkdir(parents=True)
    (tmp_path / "03_清洗" / "full.txt").write_text("# 源\n\n正文 42\n", encoding="utf-8")
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "full.md").write_text(_NOTE, encoding="utf-8")
    (tmp_path / "进度单.md").write_text(
        "# 总进度单\n\n| 步骤 | 状态 | 产物 |\n|---|---|---|\n"
        "| clean | 完成 | 03_清洗/full.txt |\n\n", encoding="utf-8")
    monkeypatch.setenv("MRE_DIR", str(_stub_mre(tmp_path, 0)))

    assert CLI.main(["gate", str(tmp_path), "note"]) == CLI.EXIT_OK
    sheet = (tmp_path / "进度单.md").read_text(encoding="utf-8")
    assert "| note | 完成 |" in sheet
    assert "04_笔记/full.md" in sheet
    assert sheet.count("| note |") == 1


def test_a_failing_gate_does_not_claim_the_note_is_done(tmp_path, monkeypatch):
    (tmp_path / "03_清洗").mkdir(parents=True)
    (tmp_path / "03_清洗" / "full.txt").write_text("# 源\n\n正文 42\n", encoding="utf-8")
    base = tmp_path / "04_笔记"
    base.mkdir(parents=True)
    (base / "full.md").write_text(_NOTE, encoding="utf-8")
    (tmp_path / "进度单.md").write_text(
        "# 总进度单\n\n| 步骤 | 状态 | 产物 |\n|---|---|---|\n\n", encoding="utf-8")
    monkeypatch.setenv("MRE_DIR", str(_stub_mre(tmp_path, 1)))

    assert CLI.main(["gate", str(tmp_path), "note"]) == CLI.EXIT_RUN_FAILED
    assert "| note |" not in (tmp_path / "进度单.md").read_text(encoding="utf-8")


def test_checklist_prints(capsys):
    assert CLI.main(["checklist", "note"]) == CLI.EXIT_OK
    assert "G2" in capsys.readouterr().out


def test_checklist_rejects_unknown_step(capsys):
    assert CLI.main(["checklist", "nope"]) == CLI.EXIT_NEEDS_USER


def test_assign_unknown_step_needs_user(tmp_path):
    assert CLI.main(["assign", str(tmp_path), "nope"]) == CLI.EXIT_NEEDS_USER


def test_assign_prints_a_dispatch_sheet(tmp_path, capsys):
    assert CLI.main(["assign", str(tmp_path), "note"]) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert "任务单" in out and "由你亲自写笔记" in out


def test_step_reports_a_clear_failure(tmp_path):
    # no 02_转md output -> the clean step has nothing to read -> handled, not crashed
    assert CLI.main(["step", str(tmp_path / "run"), "clean"]) == CLI.EXIT_RUN_FAILED


def test_step_accepts_force_flag(tmp_path):
    # The flag has to parse and reach the orchestrator, not blow up argparse.
    assert CLI.main(["step", str(tmp_path / "run"), "clean", "--force"]) == CLI.EXIT_RUN_FAILED


def test_run_accepts_force_flag(tmp_path):
    assert CLI.main(["run", str(tmp_path / "run"), "a.exe", "--force"]) == CLI.EXIT_NEEDS_USER


def test_run_accepts_deep_clean_flag(tmp_path):
    assert CLI.main(["run", str(tmp_path / "run"), "a.exe", "--deep-clean"]) == CLI.EXIT_NEEDS_USER


def test_run_accepts_album_flag(tmp_path):
    # Parses and reaches the orchestrator instead of blowing up argparse.
    assert CLI.main(["run", str(tmp_path / "run"), "a.exe", "--album", "one"]) == CLI.EXIT_NEEDS_USER


def test_run_refuses_an_unknown_album_value(tmp_path):
    with pytest.raises(SystemExit) as exc:
        CLI.main(["run", str(tmp_path / "run"), "a.exe", "--album", "maybe"])
    assert exc.value.code == 2  # argparse 的用法错误码


def test_run_runs_a_folder_of_one_image_as_that_file(tmp_path, capsys):
    # 一个媒体文件没有 one/each 歧义（T109 口径修订）：按单文件直接跑，不问。
    # 真实执行器会接着跑 media 并在假图上失败（EXIT_RUN_FAILED），
    # 但关键口径是「不询问、输入已被留底」——itizer 停在门口反而是错的。
    d = tmp_path / "图集"
    d.mkdir()
    (d / "1.jpg").write_bytes(b"x")
    code = CLI.main(["run", str(tmp_path / "run"), str(d)])
    out = capsys.readouterr().out
    assert code != CLI.EXIT_NEEDS_USER
    assert "停下问用户" not in out or "停止批处理" in out
    assert (tmp_path / "run" / "00_输入" / "1.jpg").is_file()


# --- run ---------------------------------------------------------------

def test_run_unknown_input_needs_user(tmp_path, capsys):
    assert CLI.main(["run", str(tmp_path / "run"), "a.exe"]) == CLI.EXIT_NEEDS_USER
    assert "停下问用户" in capsys.readouterr().out


def test_run_missing_input_needs_user(tmp_path, capsys):
    code = CLI.main(["run", str(tmp_path / "run"), str(tmp_path / "ghost.pdf")])
    assert code == CLI.EXIT_NEEDS_USER
    assert "输入读不到" in capsys.readouterr().out


def test_run_links_line_reports_not_wired(tmp_path, capsys):
    code = CLI.main(["run", str(tmp_path / "run"), "https://x/y"])
    assert code == CLI.EXIT_NEEDS_USER
    assert "还没接" in capsys.readouterr().out


def test_run_defaults_to_cloud_mode():
    parser_flags = CLI._build_parser()
    args = parser_flags.parse_args(["run", "wd", "a.pdf"])
    assert args.mode == "cloud"


def test_no_command_prints_help(capsys):
    assert CLI.main([]) == CLI.EXIT_OK
    assert "usage" in capsys.readouterr().out.lower()
