"""The in-note TOC refresh: the part generates it, we only prepare the ground.

Two things this must never do again: eat the intro blockquote that follows the
TOC (that happened once — round_44), and leave a note without its TOC when the
part's tool fails.

Refreshing is the part's job since 2026-10-15 (``toc_gen.py --apply`` rebuilds an
existing TOC). Our side used to strip the old block first, and that line walk
stopped before the block's own ``---`` terminator — so every refresh left a stray
``---`` in the note. The pre-strip is gone; what is left to test here is what we
still own: absolute paths, and writing the file back when the tool fails.
"""
import pathlib

from material_to_notes.steps import note


def _stub_part(tmp_path, returncode=0):
    tool = tmp_path / "mre"
    (tool / "scripts").mkdir(parents=True, exist_ok=True)
    script = tool / "scripts" / "toc_gen.py"
    if returncode == 0:
        script.write_text(
            "import sys, pathlib\n"
            "p = pathlib.Path(sys.argv[1])\n"
            "p.write_text(p.read_text(encoding='utf-8')"
            " + '## \\U0001F4D1 本篇目录\\n\\n  - [甲](#甲)\\n', encoding='utf-8')\n",
            encoding="utf-8")
    else:
        script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    return tool


def test_refresh_tocs_hands_each_note_to_the_parts_tool(tmp_path):
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text("# 甲\n\n> 一句话总结：x\n", encoding="utf-8")
    tool = _stub_part(tmp_path, 0)
    ok, detail = note.refresh_tocs(tmp_path, env={"MRE_DIR": str(tool)})
    assert ok and "a.md: OK" in detail
    assert "本篇目录" in (notes / "a.md").read_text(encoding="utf-8")


def test_refresh_tocs_uses_absolute_paths(tmp_path, monkeypatch):
    # The child runs with cwd set to the part repo, so a relative note path
    # resolves there and misses. This is a documented pitfall of the project.
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text("# 甲\n", encoding="utf-8")
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return _FakeResult()

    class _FakeResult:  # noqa: D401
        ok = True
        returncode = 0
        stdout = "[OK] stub\n"
        stderr = ""
        timed_out = False
        error = ""

    tool = _stub_part(tmp_path, 0)
    note.refresh_tocs(tmp_path, env={"MRE_DIR": str(tool)}, runner=fake_run)
    assert pathlib.Path(seen["argv"][2]).is_absolute()


def test_refresh_tocs_restores_the_note_when_the_tool_fails(tmp_path):
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    original = "# 甲\n\n## 📑 本篇目录\n\n  - [旧](#旧)\n\n> 一句话总结：x\n"
    (notes / "a.md").write_text(original, encoding="utf-8")
    tool = _stub_part(tmp_path, 1)
    ok, _detail = note.refresh_tocs(tmp_path, env={"MRE_DIR": str(tool)})
    assert not ok
    assert (notes / "a.md").read_text(encoding="utf-8") == original


def test_refresh_tocs_reports_a_missing_tool(tmp_path):
    notes = tmp_path / "04_笔记"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text("# 甲\n", encoding="utf-8")
    ok, detail = note.refresh_tocs(tmp_path, env={"MATERIAL_TO_NOTES_PARTS_DIR": str(tmp_path / "none")})
    assert not ok and "toc 脚本缺失" in detail
