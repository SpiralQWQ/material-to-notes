"""Tests for the five step adapters — command shape and failure reporting."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from material_to_notes.steps import clean, document, fetch, media, note


class FakeRunner:
    """Stands in for subprocess.run: records argv, can fail, can write outputs."""

    def __init__(self, returncode=0, stdout="", stderr="", timeout=False, on_call=None):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timeout = timeout
        self.on_call = on_call
        self.calls = []
        self.envs = []

    def __call__(self, argv, **kwargs):
        self.calls.append(tuple(argv))
        self.envs.append(kwargs.get("env"))
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
        if self.on_call is not None:
            self.on_call(argv, kwargs)
        return SimpleNamespace(returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


def _norm(p):
    return str(p).replace("\\", "/")


# --- fetch -----------------------------------------------------------------

def test_fetch_builds_expected_flags():
    argv = fetch.build_command("X:/wkc", out_dir="X:/run/01_取材", terms="t.txt", sites="arxiv", python="py")
    assert argv[0] == "py"
    assert _norm(argv[1]).endswith("app/crawl_all.py")
    assert argv[2:] == ["--out-dir", "X:/run/01_取材", "--terms", "t.txt", "--sites", "arxiv"]


def test_fetch_omits_empty_optional_flags():
    argv = fetch.build_command("X:/wkc", out_dir="X:/run/01_取材", python="py")
    assert argv[2:] == ["--out-dir", "X:/run/01_取材"]


def test_fetch_run_success(tmp_path):
    def make(argv, kw):
        d = tmp_path / "01_取材" / "term" / "site"
        d.mkdir(parents=True, exist_ok=True)
        (d / "meta.json").write_text("{}", encoding="utf-8")

    out = fetch.run(tmp_path, terms="t.txt", env={"WKC_DIR": "X:/wkc"}, runner=FakeRunner(on_call=make))
    assert out.ok and out.step == "fetch"


def test_fetch_run_reports_nonzero(tmp_path):
    out = fetch.run(tmp_path, env={"WKC_DIR": "X:/wkc"}, runner=FakeRunner(returncode=2, stderr="boom"))
    assert not out.ok and "exit code 2" in out.error


def test_fetch_run_reports_timeout(tmp_path):
    out = fetch.run(tmp_path, env={"WKC_DIR": "X:/wkc"}, runner=FakeRunner(timeout=True))
    assert not out.ok and "timeout" in out.error


def test_fetch_run_reports_missing_output(tmp_path):
    out = fetch.run(tmp_path, env={"WKC_DIR": "X:/wkc"}, runner=FakeRunner())
    assert not out.ok and "missing output dir" in out.error


# --- document --------------------------------------------------------------

def test_document_commands():
    plan = document.build_plan_command("srcdir", python="py")
    assert plan[1:4] == ["-m", "dtmd", "plan"]
    assert plan[4].endswith("srcdir")
    # convert takes a bare positional day number; omitting it makes dtmd exit 1
    assert document.build_convert_command(mode="cloud", day=2, python="py")[1:] == [
        "-m", "dtmd", "convert", "--mode", "cloud", "2"]


def test_document_rejects_bad_day():
    import pytest

    with pytest.raises(ValueError):
        document.build_convert_command(day=0)


def test_merge_command_shape():
    argv = document.build_merge_command("X:/run/02_转md/book_mineru", python="py")
    assert argv[1:4] == ["-m", "dtmd", "merge"]
    assert argv[4].endswith("book_mineru")


def test_has_slices_sees_a_sliced_book(tmp_path):
    d = tmp_path / "book_mineru"
    (d / "p001-200").mkdir(parents=True)
    (d / "p001-200" / "full.md").write_text("part one", encoding="utf-8")
    assert document.has_slices(d)


def test_has_slices_is_false_for_an_ordinary_document(tmp_path):
    d = tmp_path / "paper_mineru"
    d.mkdir()
    (d / "full.md").write_text("one block", encoding="utf-8")
    (d / "images").mkdir()
    assert not document.has_slices(d)
    assert not document.has_slices(tmp_path / "nope")


def _fake_dtmd_sliced(tmp_path):
    """A book over 200 pages: convert leaves p-blocks, merge stitches them.

    Directory names follow the real run: dtmd writes ``p1-199`` / ``p200-210``
    with no zero padding.
    """
    tool = tmp_path / "dtmd"
    (tool / "_data").mkdir(parents=True)
    (tool / "_data" / "plan.json").write_text('{"days_normal": [{"blocks": []}]}', encoding="utf-8")
    root = tmp_path / "run"
    book = root / "02_转md" / "book_mineru"
    calls = []

    def make(argv, kw):
        calls.append([str(a) for a in argv])
        if str(argv[1]).endswith("enrich_subset.py"):
            return
        if "merge" in argv:
            (book / "full.md").write_text("part one\n\npart two", encoding="utf-8")
            return
        (book / "p1-199").mkdir(parents=True, exist_ok=True)
        (book / "p1-199" / "full.md").write_text("part one", encoding="utf-8")
        (book / "p200-210").mkdir(parents=True, exist_ok=True)
        (book / "p200-210" / "full.md").write_text("part two", encoding="utf-8")

    return tool, root, calls, make


def test_a_sliced_book_is_merged_before_enrich(tmp_path):
    # Without merge there is no full.md at the dir root: enrich would find no
    # image references and the book would silently lose every figure note.
    tool, root, calls, make = _fake_dtmd_sliced(tmp_path)
    out = document.run(root, src_dir="X:/in", env={"DTMD_DIR": str(tool)},
                       runner=FakeRunner(on_call=make))
    assert out.ok, out.error
    kinds = [c[3] for c in calls if c[1:3] == ["-m", "dtmd"]]
    assert kinds == ["plan", "convert", "merge"]
    assert (root / "02_转md" / "book_mineru" / "full.md").is_file()
    # And the enrich phase still ran, on the merged document.
    assert any(c[1].endswith("enrich_subset.py") for c in calls)


def test_an_ordinary_document_is_never_merged(tmp_path):
    # dtmd merge exits 1 when there is nothing to merge, so calling it on a
    # single-block document would fail every normal run.
    tool, root, calls, make = _fake_dtmd(tmp_path)
    out = document.run(root, src_dir="X:/in", env={"DTMD_DIR": str(tool)},
                       runner=FakeRunner(on_call=make))
    assert out.ok, out.error
    assert not [c for c in calls if "merge" in c]


def test_a_failed_merge_stops_the_step(tmp_path):
    tool, root, calls, make = _fake_dtmd_sliced(tmp_path)

    class MergeFails(FakeRunner):
        def __call__(self, argv, **kwargs):
            if "merge" in argv:
                self.calls.append(tuple(argv))
                self.envs.append(kwargs.get("env"))
                return SimpleNamespace(returncode=1, stdout="", stderr="merge blew up")
            return super().__call__(argv, **kwargs)

    out = document.run(root, src_dir="X:/in", env={"DTMD_DIR": str(tool)},
                       runner=MergeFails(on_call=make))
    assert not out.ok
    assert "merge blew up" in out.error
    # Enrich must not run on an unmerged book.
    assert not any(c[1].endswith("enrich_subset.py") for c in calls)



# --- enrich: the figure step the first real run proved was missing ---------

def test_enrich_command_targets_the_subset_script():
    argv = document.build_enrich_command("mineru", python="py")
    assert argv[0] == "py"
    assert argv[1].replace("\\", "/").endswith("scripts/enrich_subset.py")
    assert argv[2].endswith("mineru")
    assert "--no-glm" not in argv
    assert "--no-glm" in document.build_enrich_command("X:/d", glm=False, python="py")


def test_subset_script_exists():
    assert document._subset_script().is_file()


def _fake_dtmd(tmp_path):
    tool = tmp_path / "dtmd"
    (tool / "_data").mkdir(parents=True)
    (tool / "_data" / "plan.json").write_text('{"days_normal": [{"blocks": []}]}', encoding="utf-8")
    root = tmp_path / "run"
    calls = []

    def make(argv, kw):
        calls.append([str(a) for a in argv])
        if str(argv[1]).endswith("enrich_subset.py"):
            return
        d = root / "02_转md" / "paper_mineru"
        d.mkdir(parents=True, exist_ok=True)
        (d / "full.md").write_text("body before embed", encoding="utf-8")

    return tool, root, calls, make


def test_document_enriches_each_mineru_dir(tmp_path):
    tool, root, calls, make = _fake_dtmd(tmp_path)
    document.run(root, src_dir="X:/in", env={"DTMD_DIR": str(tool)}, runner=FakeRunner(on_call=make))
    enrich = [c for c in calls if c[1].endswith("enrich_subset.py")]
    assert len(enrich) == 1
    assert str(root / "02_转md" / "paper_mineru") in enrich[0][2]


def test_document_snapshots_full_md_before_enrich(tmp_path):
    tool, root, _calls, make = _fake_dtmd(tmp_path)
    document.run(root, src_dir="X:/in", env={"DTMD_DIR": str(tool)}, runner=FakeRunner(on_call=make))
    live = root / "02_转md" / "paper_mineru" / "full.md"
    assert (live.parent / "full.md.bak").read_text(encoding="utf-8") == "body before embed"
    assert live.is_file()


def test_snapshot_keeps_the_first_pre_enrich_copy(tmp_path):
    d = tmp_path / "paper_mineru"
    d.mkdir()
    (d / "full.md").write_text("original", encoding="utf-8")
    document.backup_full_md(d)
    (d / "full.md").write_text("enriched", encoding="utf-8")
    document.backup_full_md(d)
    assert (d / "full.md.bak").read_text(encoding="utf-8") == "original"


def test_document_can_skip_enrich(tmp_path):
    tool, root, calls, make = _fake_dtmd(tmp_path)
    document.run(root, src_dir="X:/in", env={"DTMD_DIR": str(tool)},
                 runner=FakeRunner(on_call=make), enrich=False)
    assert not [c for c in calls if c[1].endswith("enrich_subset.py")]


def test_plan_day_count_reads_plan_and_falls_back(tmp_path):
    plan = tmp_path / "_data" / "plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text('{"days_normal": [{"blocks": []}, {"blocks": []}]}', encoding="utf-8")
    assert document.plan_day_count(str(tmp_path), env={}) == 2
    assert document.plan_day_count(str(tmp_path / "nope"), env={}) == 1
    plan.write_text("{ broken", encoding="utf-8")
    assert document.plan_day_count(str(tmp_path), env={}) == 1


def test_document_converts_every_planned_day(tmp_path):
    tool = tmp_path / "dtmd"
    (tool / "_data").mkdir(parents=True)
    (tool / "_data" / "plan.json").write_text(
        '{"days_normal": [{"blocks": []}, {"blocks": []}, {"blocks": []}]}', encoding="utf-8")
    root = tmp_path / "run"

    def make_output(argv, kw):
        # The gate after each convert needs the declared output to exist.
        _write(root / "02_转md", "full.md", "x")

    runner = FakeRunner(on_call=make_output)
    document.run(root, src_dir="X:/in", env={"DTMD_DIR": str(tool)}, runner=runner, enrich=False)
    days = [call[-1] for call in runner.calls[1:]]
    assert days == ["1", "2", "3"]


def _write(base, name, content):
    base.mkdir(parents=True, exist_ok=True)
    (base / name).write_text(content, encoding="utf-8")


def test_document_run_sets_output_root_and_runs_twice(tmp_path):
    runner = FakeRunner()
    document.run(tmp_path, src_dir="X:/src", env={"DTMD_DIR": "X:/dtmd"}, runner=runner, enrich=False)
    assert len(runner.calls) == 2
    assert _norm(tmp_path) in _norm(runner.envs[0]["DTM_OUTPUT_ROOT"])


def test_src_layout_tools_get_their_src_on_pythonpath(tmp_path):
    # md_rewrite_engine / media_to_markdown live under <repo>/src, so cwd alone
    # cannot import them. This is what the real launch check caught.
    tool = tmp_path / "tool"
    (tool / "src" / "pkg").mkdir(parents=True)
    source = tmp_path / "a.md"
    source.write_text("x", encoding="utf-8")
    root = tmp_path / "run"

    for adapter, kwargs, env_key in (
        (note, {"src_md": str(source)}, "MRE_DIR"),
        (media, {"sources": [str(source)]}, "M2M_DIR"),
        (clean, {"src_file": str(source)}, "TCE_DIR"),
    ):
        runner = FakeRunner()
        adapter.run(root, env={env_key: str(tool)}, runner=runner, **kwargs)
        pythonpath = _norm(runner.envs[0]["PYTHONPATH"])
        assert _norm(tool / "src") in pythonpath, adapter.__name__


def test_adapters_do_not_leak_partial_env_to_child(tmp_path):
    # env is only for resolving the tool dir; the child must inherit the real env.
    runner = FakeRunner()
    fetch.run(tmp_path, env={"WKC_DIR": "X:/wkc"}, runner=runner)
    assert runner.envs[0] is None


def test_document_run_stops_when_plan_fails(tmp_path):
    runner = FakeRunner(returncode=1)
    out = document.run(tmp_path, src_dir="X:/src", env={"DTMD_DIR": "X:/dtmd"}, runner=runner)
    assert not out.ok and len(runner.calls) == 1


# --- media -----------------------------------------------------------------

def test_media_builds_command():
    argv = media.build_command(["a.mp4", "b.mp3"], glm="yes", python="py")
    assert argv[1:3] == ["-m", "media_to_markdown"]
    assert argv[3].endswith("a.mp4") and argv[4].endswith("b.mp3")
    assert argv[5:] == ["--glm", "yes"]


def test_media_collect_lifts_note_into_step_dir(tmp_path):
    def make(argv, kw):
        d = tmp_path / "02_转md" / "output" / "cache" / "v"
        d.mkdir(parents=True, exist_ok=True)
        (d / "v_clean.md").write_text("x", encoding="utf-8")

    out = media.run(tmp_path, sources=["v.mp4"], env={"M2M_DIR": "X:/m2m"}, runner=FakeRunner(on_call=make))
    assert out.ok
    assert (tmp_path / "02_转md" / "v_clean.md").is_file()


def test_media_run_fails_when_nothing_collected(tmp_path):
    out = media.run(tmp_path, sources=["v.mp4"], env={"M2M_DIR": "X:/m2m"}, runner=FakeRunner())
    assert not out.ok


# m2m folds every image *file* it is handed into ONE album md named after the
# first, and writes a directory's images as one md per image *beside the sources*
# instead. So a directory has to be expanded into its images before the call.


def _album(tmp_path, *names):
    d = tmp_path / "00_输入" / "课件图集"
    d.mkdir(parents=True, exist_ok=True)
    for name in names:
        (d / name).write_bytes(b"x")
    return d


def test_media_expands_an_album_directory_into_its_images(tmp_path):
    d = _album(tmp_path, "b.jpg", "a.jpg")
    (d / "说明.txt").write_bytes(b"x")  # 非图片不该被带上
    runner = FakeRunner()
    media.run(tmp_path, sources=[str(d)], env={"M2M_DIR": "X:/m2m"}, runner=runner)
    argv = runner.calls[0]
    passed = [p for p in argv if p.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))]
    assert [Path(p).name for p in passed] == ["a.jpg", "b.jpg"]
    assert not any(Path(p).resolve() == d.resolve() for p in argv)  # 传的是图，不是目录


def test_media_names_the_album_after_the_directory(tmp_path):
    d = _album(tmp_path, "a.jpg", "b.jpg")

    def make(argv, kwargs):
        cache = tmp_path / "02_转md" / "output" / "cache" / "图片"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "a_clean.md").write_text("x", encoding="utf-8")  # 零件按第一张图命名

    out = media.run(tmp_path, sources=[str(d)], env={"M2M_DIR": "X:/m2m"},
                    runner=FakeRunner(on_call=make))
    assert out.ok
    assert (tmp_path / "02_转md" / f"{d.name}_clean.md").is_file()
    assert not (tmp_path / "02_转md" / "a_clean.md").exists()


def test_media_sorts_multi_image_files_by_name(tmp_path):
    # 终点一致性（T110 用户裁定 A）：直传多图与文件夹 --album one 同一条零件路，
    # 块序必须同为文件名序 —— 传参顺序不该影响笔记阅读顺序。
    runner = FakeRunner()
    sources = [str(tmp_path / n) for n in ("04.jpg", "01.jpg", "03.jpg", "02.jpg")]
    media.run(tmp_path, sources=sources, env={"M2M_DIR": "X:/m2m"}, runner=runner)
    argv = runner.calls[0]
    passed = [p for p in argv if p.lower().endswith(".jpg")]
    assert passed == [str(tmp_path / n) for n in ("01.jpg", "02.jpg", "03.jpg", "04.jpg")]


def test_media_refuses_an_album_alongside_other_materials(tmp_path):
    d = _album(tmp_path, "a.jpg")
    runner = FakeRunner()
    out = media.run(tmp_path, sources=[str(d), "v.mp4"], env={"M2M_DIR": "X:/m2m"}, runner=runner)
    assert not out.ok
    assert runner.calls == []  # 不跑零件，直接停下
    assert "停下问用户" in out.error


def test_media_refuses_an_album_directory_without_images(tmp_path):
    d = tmp_path / "00_输入" / "空目录"
    d.mkdir(parents=True)
    (d / "readme.txt").write_bytes(b"x")
    runner = FakeRunner()
    out = media.run(tmp_path, sources=[str(d)], env={"M2M_DIR": "X:/m2m"}, runner=runner)
    assert not out.ok
    assert runner.calls == []
    assert "停下问用户" in out.error


# --- clean -----------------------------------------------------------------

def test_clean_builds_command():
    argv = clean.build_command("in.md", "out.txt", python="py")
    assert argv[1:3] == ["-m", "cleaner.clean_md"]
    assert argv[3].endswith("in.md")
    assert argv[4] == "--output" and argv[5].endswith("out.txt")


def test_clean_defaults_to_watermark_only():
    # Measured on a real paper: the full rule set eats the document — trafilatura
    # 1118->1 lines and <td> 18->0, plain mode $$ 88->0. Watermark-only keeps all.
    assert clean.build_command("in.md", "out.txt", python="py")[-1] == "--watermark-only"


def test_clean_deep_mode_drops_the_watermark_flag():
    argv = clean.build_command("in.md", "out.txt", deep=True, python="py")
    assert "--watermark-only" not in argv


def test_clean_writes_text_and_meta(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("raw", encoding="utf-8")

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("cleaned", encoding="utf-8")

    runner = FakeRunner(stdout='{"ok": true}', on_call=make)
    out = clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"}, runner=runner)
    assert out.ok
    assert (tmp_path / "03_清洗" / "a.txt").read_text(encoding="utf-8") == "cleaned"
    # Statistics live in the source's record under _元数据/, never beside the text.
    record = json.loads((tmp_path / "_元数据" / "a.json").read_text(encoding="utf-8"))
    assert record["steps"]["clean"]["ok"] is True
    assert record["steps"]["clean"]["stats"] == {"ok": True}
    assert not list((tmp_path / "03_清洗").glob("*.json"))


def test_clean_rejects_output_that_collapsed_the_structure(tmp_path):
    # The tool exited 0 and still deleted every table and formula; the step must
    # not be recorded done, or the note is written from a gutted document.
    src = tmp_path / "a.md"
    src.write_text("# 标题\n\n<table><tr><td>a</td></table>\n\n$$E=mc^2$$\n", encoding="utf-8")

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("标题 a E=mc2", encoding="utf-8")

    out = clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"},
                    runner=FakeRunner(stdout='{"ok": true}', on_call=make))
    assert not out.ok
    assert "structure check" in out.error
    assert "table_cells" in out.error


def test_clean_accepts_output_that_preserves_the_structure(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("# 标题\n\n<table><tr><td>a</td></table>\n\n$$E=mc^2$$\n", encoding="utf-8")

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("# 标题\n\n<table><tr><td>a</td></table>\n\n$$E=mc^2$$\n",
                            encoding="utf-8")

    out = clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"},
                    runner=FakeRunner(stdout='{"ok": true}', on_call=make))
    assert out.ok, out.error


def test_clean_gate_blocks_deep_mode_too(tmp_path):
    # Opting into the full rule set is not a licence to lose content: the gate
    # has no exemption, or it reopens the exact hole it was added to close.
    src = tmp_path / "a.md"
    src.write_text("# 标题\n\n<table><tr><td>a</td></table>\n\n$$E=mc^2$$\n", encoding="utf-8")

    def make(argv, kw):
        assert "--watermark-only" not in argv
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("标题 a E=mc2", encoding="utf-8")

    out = clean.run(tmp_path, src_file=src, deep=True, env={"TCE_DIR": "X:/tce"},
                    runner=FakeRunner(stdout='{"ok": true}', on_call=make))
    assert not out.ok
    assert "structure check" in out.error


def test_clean_records_the_loss_in_the_meta_sheet(tmp_path):
    # A failed attempt still has to show what went missing, or the retry loop
    # and the failure sheet both say only "exit code 0 but rejected".
    src = tmp_path / "a.md"
    src.write_text("# 标题\n\n<table><tr><td>a</td></table>\n\n$$E=mc^2$$\n", encoding="utf-8")

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("标题 a E=mc2", encoding="utf-8")

    clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"},
              runner=FakeRunner(stdout='{"ok": true, "engine": "watermark"}', on_call=make))
    meta = (tmp_path / "_元数据" / "a.json").read_text(encoding="utf-8")
    assert "structure_lost" in meta
    assert "table_cells" in meta and "engine" in meta


def test_clean_meta_unchanged_when_nothing_is_lost(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("# 标题\n", encoding="utf-8")

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("# 标题\n", encoding="utf-8")

    clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"},
              runner=FakeRunner(stdout='{"ok": true}', on_call=make))
    assert "structure_lost" not in (tmp_path / "_元数据" / "a.json").read_text(encoding="utf-8")




def test_clean_wraps_non_json_stdout(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("raw", encoding="utf-8")

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("cleaned", encoding="utf-8")

    out = clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"},
                    runner=FakeRunner(stdout="not json", on_call=make))
    assert out.ok
    assert "raw_stdout" in (tmp_path / "_元数据" / "a.json").read_text(encoding="utf-8")


def test_clean_meta_does_not_duplicate_the_cleaned_text(tmp_path):
    # Real run caught this: tce echoes the whole text in cleaned_text, so a
    # verbatim dump stored the document twice and made the meta useless.
    src = tmp_path / "a.md"
    src.write_text("raw", encoding="utf-8")
    payload = '{"ok": true, "engine": "plain", "stats": {"raw_len": 3, "clean_len": 2},' \
              ' "cleaned_text": "' + "x" * 4000 + '"}'

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("cleaned", encoding="utf-8")

    clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"},
              runner=FakeRunner(stdout=payload, on_call=make))
    meta = (tmp_path / "_元数据" / "a.json").read_text(encoding="utf-8")
    assert "cleaned_text" not in meta
    assert "raw_len" in meta and "engine" in meta
    assert len(meta) < 500


# --- note ------------------------------------------------------------------

def test_note_builds_command():
    argv = note.build_command("in.md", "out.md", python="py")
    assert argv[1:3] == ["-m", "md_rewrite_engine"]
    assert argv[3].endswith("in.md")
    assert argv[4] == "--output" and argv[5].endswith("out.md")


def test_paths_handed_to_tools_are_absolute():
    # Adapters run tools with cwd set to the tool repo; a relative path would
    # resolve somewhere else and the tool reports "file not found".
    import os

    argv = clean.build_command("in.md", "out.txt", python="py")
    assert os.path.isabs(argv[3]) and os.path.isabs(argv[5])


def test_note_writes_note_md(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("clean", encoding="utf-8")

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("note", encoding="utf-8")

    out = note.run(tmp_path, src_md=src, env={"MRE_DIR": "X:/mre"}, runner=FakeRunner(on_call=make))
    assert out.ok
    assert (tmp_path / "04_笔记" / "a.md").read_text(encoding="utf-8") == "note"


def test_note_reports_missing_output(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("clean", encoding="utf-8")
    out = note.run(tmp_path, src_md=src, env={"MRE_DIR": "X:/mre"}, runner=FakeRunner())
    assert not out.ok


def test_document_defaults_to_cloud():
    assert document.build_convert_command(python="py")[1:] == [
        "-m", "dtmd", "convert", "--mode", "cloud", "1"]
    assert document.DEFAULT_MODE == "cloud"


def test_document_rejects_unknown_mode():
    import pytest

    with pytest.raises(ValueError):
        document.build_convert_command(mode="magic")


# --- our own figure-note ids must not reach the deliverable -----------------

_HASH = "dad01814bec2cdf7a5d24538f66f70f3b43525021e5803543ddc0531994cd3c6"


def test_strip_internal_ids_rewrites_the_heading():
    text, count = clean.strip_internal_ids(f"前言\n\n## 插图笔记：{_HASH}\n\n图意\n")
    assert count == 1
    assert _HASH not in text and "## 插图笔记" in text
    assert "图意" in text


def test_strip_internal_ids_leaves_a_meaningful_heading_alone():
    # Only OUR ids (dtmd heads a figure note with the image sha256). A heading
    # that already says which figure it is must survive untouched.
    for heading in ("## 插图笔记：图 3", "## 插图笔记：Figure 3 的散点图", "## 插图笔记"):
        text, count = clean.strip_internal_ids(heading + "\n")
        assert count == 0 and text == heading + "\n"


def test_strip_internal_ids_leaves_body_text_alone():
    text, count = clean.strip_internal_ids(f"正文提到 {_HASH} 这个串\n")
    assert count == 0 and text == f"正文提到 {_HASH} 这个串\n"


def test_clean_strips_ids_from_its_output(tmp_path):
    src = tmp_path / "a.md"
    src.write_text(f"# 标题\n\n## 插图笔记：{_HASH}\n\n图意\n", encoding="utf-8")

    def make(argv, kw):
        out_file = Path(argv[argv.index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(f"# 标题\n\n## 插图笔记：{_HASH}\n\n图意\n", encoding="utf-8")

    out = clean.run(tmp_path, src_file=src, env={"TCE_DIR": "X:/tce"},
                    runner=FakeRunner(stdout='{"ok": true}', on_call=make))
    assert out.ok, out.error
    delivered = (tmp_path / "03_清洗" / "a.txt").read_text(encoding="utf-8")
    assert _HASH not in delivered
    record = json.loads((tmp_path / "_元数据" / "a.json").read_text(encoding="utf-8"))
    assert record["steps"]["clean"]["stats"]["internal_ids_stripped"] == 1
