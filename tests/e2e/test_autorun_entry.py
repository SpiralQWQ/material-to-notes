"""Tests for pipeline.autorun — the entry point that `material-to-notes run` drives."""

from pathlib import Path

import pytest

from _mocks import DOC_SPEC, MEDIA_SPEC, executors
from material_to_notes.contract import workdir as W
from material_to_notes.orchestrate import pipeline as PL
from material_to_notes.orchestrate import runner as OR

RUN = "run"


def test_document_line_stages_input_then_finishes(tmp_path):
    source = tmp_path / "教材.pdf"
    source.write_text("x", encoding="utf-8")
    root = tmp_path / RUN
    out = PL.autorun(root, [source], executors=executors(DOC_SPEC))
    assert out["report"].ok
    assert (root / W.INPUT_DIR / "教材.pdf").is_file()
    assert (root / "04_笔记" / "note.md").is_file()


def test_media_line_stages_and_reports_staged_path(tmp_path):
    source = tmp_path / "v.mp4"
    source.write_text("x", encoding="utf-8")
    root = tmp_path / RUN
    out = PL.autorun(root, [source], executors=executors(MEDIA_SPEC))
    assert out["report"].ok
    assert str(root / W.INPUT_DIR / "v.mp4") in [str(p) for p in out["staged"]]


def test_bare_term_without_kind_asks_user(tmp_path):
    out = PL.autorun(tmp_path / RUN, ["python 入门"], executors=executors({}))
    assert out["asked_user"] and out["report"] is None
    assert "不认识的输入" in out["reason"]


def test_explicit_terms_kind_skips_staging(tmp_path):
    terms = tmp_path / "words.txt"
    terms.write_text("python 入门\n", encoding="utf-8")
    out = PL.autorun(tmp_path / RUN, [str(terms)], kind="terms", terms_file=str(terms),
                     executors=executors({"fetch": ("01_取材", ["paper.pdf", "meta.json"]),
                                           **DOC_SPEC}))
    assert out["staged"] == ()
    assert [r.step for r in out["report"].records] == ["fetch", "document", "clean", "note"]


def test_links_line_is_reported_as_not_wired(tmp_path):
    out = PL.autorun(tmp_path / RUN, ["https://x/y"])
    assert out["asked_user"] and out["report"] is None
    assert "还没接" in out["reason"]


# A folder of images defaults to one album note, and a video/audio folder to
# one note per file (用户裁定 2026-10-21) — the explicit --album flag still
# overrides, and a mixed folder keeps asking because the readings truly differ.


def _album_dir(tmp_path, count=2):
    d = tmp_path / "课件图集"
    d.mkdir()
    for i in range(1, count + 1):
        (d / f"{i}.jpg").write_bytes(b"x")
    return d


def test_a_pure_image_folder_defaults_to_one_album(tmp_path):
    d = _album_dir(tmp_path)
    root = tmp_path / RUN
    out = PL.autorun(root, [d], executors=executors(MEDIA_SPEC))
    assert not out["asked_user"] and out["report"].ok
    assert (root / W.INPUT_DIR / "课件图集").is_dir()   # one: 整个文件夹进输入区


def test_album_one_says_one_note_for_the_whole_folder(tmp_path):
    d = _album_dir(tmp_path)
    out = PL.autorun(tmp_path / RUN, [d], album="one", executors=executors(MEDIA_SPEC))
    assert not out["asked_user"]
    assert out["report"].ok


def test_album_each_gets_its_own_workdir_under_the_same_root(tmp_path):
    d = _album_dir(tmp_path, count=3)
    root = tmp_path / RUN
    out = PL.autorun(root, [d], album="each", executors=executors(MEDIA_SPEC))
    assert out["report"].ok
    assert out["asked_user"] is False
    for i in (1, 2, 3):
        assert (root / f"图片{i}" / W.INPUT_DIR / f"{i}.jpg").is_file()
        assert (root / f"图片{i}" / "04_笔记" / "note.md").is_file()
    assert out["per_image_roots"] == tuple(str(root / f"图片{i}") for i in (1, 2, 3))


def test_album_each_refuses_an_empty_folder(tmp_path):
    d = tmp_path / "空图集"
    d.mkdir()
    out = PL.autorun(tmp_path / RUN, [d], album="each", executors=executors(MEDIA_SPEC))
    assert out["asked_user"] and out["report"] is None
    assert "没有可处理的素材" in out["reason"]


def test_album_each_refuses_a_folder_beside_other_materials(tmp_path):
    other = tmp_path / "v.mp4"
    other.write_text("x", encoding="utf-8")
    out = PL.autorun(tmp_path / RUN, [_album_dir(tmp_path), other], album="each",
                     executors=executors(MEDIA_SPEC))
    assert out["asked_user"] and out["report"] is None
    assert "只能单独跑" in out["reason"]  # 目录素材只接受单个文件夹


def test_album_option_is_ignored_when_no_folder_is_given(tmp_path):
    source = tmp_path / "v.mp4"
    source.write_text("x", encoding="utf-8")
    out = PL.autorun(tmp_path / RUN, [source], album="each", executors=executors(MEDIA_SPEC))
    assert not out["asked_user"] and out["report"].ok


def test_album_each_is_not_ok_when_an_image_fails(tmp_path):
    d = _album_dir(tmp_path, count=2)
    base = executors(MEDIA_SPEC)

    def media(root):
        if Path(root).name == "图片2":   # 最后一张持续失败（单次失败会被重试兜住）
            return OR.Outcome(False, "media boom")
        return base["media"](root)

    out = PL.autorun(tmp_path / RUN, [d], album="each", executors={**base, "media": media})
    assert len(out["reports"]) == 2
    assert out["per_image_all_ok"] is False
    assert out["needs_agent"] == ""      # 没跑通就不该说"交给子 agent 写"


def test_album_each_does_not_claim_a_handoff_when_the_note_actually_ran(tmp_path):
    # 注入执行器时 note 是真跑的（与单素材路径同一口径），不该说"交给子 agent 写"。
    out = PL.autorun(tmp_path / RUN, [_album_dir(tmp_path)], album="each",
                     executors=executors(MEDIA_SPEC))
    assert out["report"].ok
    assert out["needs_agent"] == ""


def test_album_each_asks_when_the_target_is_not_a_folder(tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    out = PL.autorun(tmp_path / RUN, [f], kind="album", album="each",
                     executors=executors(MEDIA_SPEC))
    assert out["asked_user"] and out["report"] is None


# --- folder contents decide the question -----------------------------------
# A folder used to be assumed to be an image album. Video/audio folders were
# refused, and a mixed folder silently lost its videos (the media adapter only
# picks images). The scan now runs first, and nothing is written before the ask.

def _material_dir(tmp_path, name, filenames):
    d = tmp_path / name
    d.mkdir()
    for fname in filenames:
        (d / fname).write_bytes(b"x")
    return d


def test_a_folder_of_videos_defaults_to_one_note_each(tmp_path):
    d = _material_dir(tmp_path, "课程视频", ["1.mp4", "2.mp4"])
    root = tmp_path / RUN
    out = PL.autorun(root, [d], executors=executors(MEDIA_SPEC))
    assert out["report"].ok and out["asked_user"] is False
    assert (root / "素材2" / W.INPUT_DIR / "2.mp4").is_file()   # each: 一个视频一份


def test_album_one_refuses_several_videos(tmp_path):
    # m2m handles video/audio one file at a time; it cannot merge them, so
    # claiming "one note for the folder" would be a lie.
    d = _material_dir(tmp_path, "课程视频", ["1.mp4", "2.mp4"])
    out = PL.autorun(tmp_path / RUN, [d], album="one", executors=executors(MEDIA_SPEC))
    assert out["asked_user"] and out["report"] is None
    assert "不能合成一份" in out["reason"]
    assert not (tmp_path / RUN).exists()


def test_album_each_gives_every_video_its_own_workdir(tmp_path):
    d = _material_dir(tmp_path, "课程视频", ["1.mp4", "2.mp4"])
    root = tmp_path / RUN
    out = PL.autorun(root, [d], album="each", executors=executors(MEDIA_SPEC))
    assert out["report"].ok and out["asked_user"] is False
    for i in (1, 2):
        assert (root / f"素材{i}" / W.INPUT_DIR / f"{i}.mp4").is_file()
        assert (root / f"素材{i}" / "04_笔记" / "note.md").is_file()
    assert out["per_material_roots"] == tuple(str(root / f"素材{i}") for i in (1, 2))
    assert out["per_image_roots"] == ()             # 只有纯图片才用这个旧键


def test_a_folder_holding_one_video_runs_as_that_file(tmp_path):
    # 一个文件没有歧义：按单文件跑，不进目录分支。
    d = _material_dir(tmp_path, "课程视频", ["1.mp4"])
    root = tmp_path / RUN
    out = PL.autorun(root, [d], album="one", executors=executors(MEDIA_SPEC))
    assert not out["asked_user"] and out["report"].ok
    assert (root / W.INPUT_DIR / "1.mp4").is_file()
    assert (root / "04_笔记" / "note.md").is_file()
    assert not (root / W.INPUT_DIR / "课程视频").exists()


def test_a_mixed_folder_asks_with_counts(tmp_path):
    d = _material_dir(tmp_path, "混合", ["1.jpg", "2.mp4"])
    out = PL.autorun(tmp_path / RUN, [d], executors=executors(MEDIA_SPEC))
    assert out["asked_user"] and out["report"] is None
    assert "图片" in out["reason"] and "视频" in out["reason"]
    assert not (tmp_path / RUN).exists()


def test_album_one_refuses_a_mixed_folder(tmp_path):
    d = _material_dir(tmp_path, "混合", ["1.jpg", "2.mp4"])
    out = PL.autorun(tmp_path / RUN, [d], album="one", executors=executors(MEDIA_SPEC))
    assert out["asked_user"] and out["report"] is None
    assert "拆开" in out["reason"] and "--album each" in out["reason"]


def test_album_each_runs_every_material_in_a_mixed_folder(tmp_path):
    d = _material_dir(tmp_path, "混合", ["1.jpg", "2.mp4"])
    root = tmp_path / RUN
    out = PL.autorun(root, [d], album="each", executors=executors(MEDIA_SPEC))
    assert out["report"].ok and out["asked_user"] is False
    assert (root / "素材1" / W.INPUT_DIR / "1.jpg").is_file()
    assert (root / "素材2" / W.INPUT_DIR / "2.mp4").is_file()
    for i in (1, 2):
        assert (root / f"素材{i}" / "04_笔记" / "note.md").is_file()


def test_a_folder_with_subfolders_asks_even_with_each(tmp_path):
    d = _material_dir(tmp_path, "带子目录", ["1.jpg"])
    (d / "更多素材").mkdir()
    out = PL.autorun(tmp_path / RUN, [d], album="each", executors=executors(MEDIA_SPEC))
    assert out["asked_user"] and out["report"] is None
    assert "子文件夹" in out["reason"] and "更多素材" in out["reason"]
    assert not (tmp_path / RUN).exists()


def test_a_folder_with_other_files_asks_even_with_one(tmp_path):
    # 不递归、不静默丢：readme.txt 不是素材，但也不能当没看见。
    d = _material_dir(tmp_path, "带杂项", ["1.jpg"])
    (d / "readme.txt").write_text("x", encoding="utf-8")
    out = PL.autorun(tmp_path / RUN, [d], album="one", executors=executors(MEDIA_SPEC))
    assert out["asked_user"] and out["report"] is None
    assert "其他文件" in out["reason"] and "readme.txt" in out["reason"]


def test_album_each_gives_every_audio_file_its_own_workdir(tmp_path):
    d = _material_dir(tmp_path, "录音", ["1.mp3", "2.wav"])
    root = tmp_path / RUN
    out = PL.autorun(root, [d], album="each", executors=executors(MEDIA_SPEC))
    assert out["report"].ok and out["asked_user"] is False
    for name, i in (("1.mp3", 1), ("2.wav", 2)):
        assert (root / f"素材{i}" / W.INPUT_DIR / name).is_file()
        assert (root / f"素材{i}" / "04_笔记" / "note.md").is_file()


def test_missing_input_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        PL.autorun(tmp_path / RUN, [tmp_path / "ghost.pdf"])


# --- relay: the first real run caught all of these ------------------------

def test_relay_finds_nested_upstream(tmp_path):
    # dtmd mirrors a document into <name>_mineru/full.md; a flat glob missed it.
    nested = tmp_path / RUN / "02_转md" / "C2021_mineru"
    nested.mkdir(parents=True)
    (nested / "full.md").write_text("x", encoding="utf-8")
    assert [p.name for p in PL.relay_sources(tmp_path / RUN, "clean")] == ["full.md"]


def test_relay_finds_flat_media_upstream(tmp_path):
    step = tmp_path / RUN / "02_转md"
    step.mkdir(parents=True)
    (step / "v_clean.md").write_text("x", encoding="utf-8")
    assert [p.name for p in PL.relay_sources(tmp_path / RUN, "clean")] == ["v_clean.md"]


def test_relay_ignores_enrich_notes_and_snapshots(tmp_path):
    # enrich writes images_notes/*.md and we snapshot full.md as *.md.bak; neither
    # is upstream, and matching them would trip the multi-source guard on every run.
    mineru = tmp_path / RUN / "02_转md" / "paper_mineru"
    (mineru / "images_notes").mkdir(parents=True)
    (mineru / "full.md").write_text("x", encoding="utf-8")
    (mineru / "full.md.bak").write_text("x", encoding="utf-8")
    (mineru / "images_notes" / "a1b2c3.md").write_text("x", encoding="utf-8")
    found = PL.relay_sources(tmp_path / RUN, "clean")
    assert [p.name for p in found] == ["full.md"]
    assert PL.relay_guard("clean", found) is None


def test_relay_allows_several_sources(tmp_path):
    # Several materials in one workdir are now the normal case: the step loops.
    for name in ("a_mineru", "b_mineru"):
        d = tmp_path / RUN / "02_转md" / name
        d.mkdir(parents=True)
        (d / "full.md").write_text("x", encoding="utf-8")
    found = PL.relay_sources(tmp_path / RUN, "clean")
    assert len(found) == 2
    assert PL.relay_guard("clean", found, names=["a", "b"]) is None


def test_relay_blocks_a_name_collision(tmp_path):
    # Two sources that would write to the same file must stop the run, not
    # silently overwrite each other.
    for name in ("a_mineru", "b_mineru"):
        d = tmp_path / RUN / "02_转md" / name
        d.mkdir(parents=True)
        (d / "full.md").write_text("x", encoding="utf-8")
    blocked = PL.relay_guard("clean", PL.relay_sources(tmp_path / RUN, "clean"),
                             names=["同一个名字", "同一个名字"])
    assert blocked is not None and not blocked.ok
    assert "同一个名字" in blocked.error and "停下问用户" in blocked.error


def test_relay_takes_the_merged_book_and_not_its_slices(tmp_path):
    # A real 210-page run: dtmd keeps p{start}-{end} blocks after merge stitches
    # them into the dir root, so a bare "**/full.md" picked up three files and the
    # guard stopped the run. Only the merged one is upstream output.
    book = tmp_path / RUN / "02_转md" / "book210_mineru"
    for rel in ("full.md", "p1-199/full.md", "p200-210/full.md"):
        target = book / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")

    found = PL.relay_sources(tmp_path / RUN, "clean")
    assert found == (book / "full.md",)
    assert PL.relay_guard("clean", found) is None



def test_relay_guard_blocks_empty_relay(tmp_path):
    (tmp_path / RUN / "02_转md").mkdir(parents=True)
    blocked = PL.relay_guard("clean", PL.relay_sources(tmp_path / RUN, "clean"))
    assert blocked is not None and "没有可读的上游产物" in blocked.error


def test_relay_guard_passes_single_source(tmp_path):
    step = tmp_path / RUN / "02_转md" / "paper_mineru"
    step.mkdir(parents=True)
    (step / "full.md").write_text("x", encoding="utf-8")
    assert PL.relay_guard("clean", PL.relay_sources(tmp_path / RUN, "clean")) is None


# --- T38: one step per sub-agent, note handed to an agent ------------------

def test_run_hands_the_note_step_to_an_agent(tmp_path):
    root = tmp_path / RUN
    out = PL.run(root, "v.mp4", executors=executors(MEDIA_SPEC), handoff_note=True)
    assert [r.step for r in out["report"].records] == ["media", "clean"]
    assert out["needs_agent"] == "note"
    assert (root / PL.ASSIGN_FILE).is_file()      # the dispatch sheet is written out


def test_the_sheet_written_by_run_lists_the_materials(tmp_path):
    """单子要能告诉写手"每份素材 → 笔记叫什么名字"。

    单子此前是在上游跑完**之前**写的，那时清洗产物还不存在，于是"输入"那栏
    是空的——写手连该产出哪几个文件都不知道（2026-10-15 实跑踩到）。
    """
    root = tmp_path / RUN
    PL.run(root, "v.mp4", executors=executors(MEDIA_SPEC), handoff_note=True)
    sheet = (root / PL.ASSIGN_FILE).read_text(encoding="utf-8")
    assert "原始输入" not in sheet, sheet
    assert "03_清洗/v.txt" in sheet.replace("\\", "/")
    assert "v.md" in sheet


def test_a_failed_upstream_run_writes_no_note_sheet(tmp_path):
    # 上游没跑通就别发写笔记的单子：写手会对着不存在的输入开工
    root = tmp_path / RUN
    PL.run(root, "v.mp4", executors=executors(MEDIA_SPEC, fail=("clean",)),
           handoff_note=True, max_attempts=1)
    assert not (root / PL.ASSIGN_FILE).exists()


def test_run_without_handoff_still_runs_the_note(tmp_path):
    out = PL.run(tmp_path / RUN, "v.mp4", executors=executors(MEDIA_SPEC))
    assert [r.step for r in out["report"].records] == ["media", "clean", "note"]
    assert out["needs_agent"] == ""


def test_step_runs_exactly_one_step(tmp_path):
    seen = []

    def make(step_id):
        def run(root_):
            seen.append(step_id)
            return OR.Outcome(True)

        return run

    exes = {name: make(name) for name in ("fetch", "document", "media", "clean", "note")}
    outcome = PL.step(tmp_path / RUN, "media", executors=exes, gates=False)
    assert seen == ["media"]                      # only the media step, nothing else
    assert [r.step for r in outcome.records] == ["media"]


def test_step_only_touches_the_named_step(tmp_path):
    seen = []

    def make(step_id):
        def run(root_):
            seen.append(step_id)
            return OR.Outcome(True)

        return run

    exes = {name: make(name) for name in ("fetch", "document", "media", "clean", "note")}
    PL.step(tmp_path / RUN, "clean", executors=exes)
    # clean has no upstream -> the gate rejects it and it retries, but no other
    # step is ever entered.
    assert set(seen) == {"clean"}


def test_step_rejects_unknown_step(tmp_path):
    with pytest.raises(KeyError):
        PL.step(tmp_path / RUN, "nope")


def test_assign_sheet_carries_what_a_fresh_agent_needs(tmp_path):
    root = tmp_path / RUN
    step_dir = root / "02_转md" / "paper_mineru"
    step_dir.mkdir(parents=True)
    (step_dir / "full.md").write_text("x", encoding="utf-8")
    sheet = PL.assign_sheet(root, "clean")
    for key in ("任务单", "执行子 agent", "输入", "产物必须写到", "禁止并行", "不修改任何代码", "full.md"):
        assert key in sheet


def test_assign_sheet_for_note_tells_the_agent_to_write_it(tmp_path):
    sheet = PL.assign_sheet(tmp_path / RUN, "note")
    assert "由你亲自写笔记" in sheet and "六件套" in sheet
    assert "子 agent" in sheet and "gate" in sheet


def test_note_brief_sets_the_encoding_var_for_every_shell():
    # 原来只写 `set VAR=...`（cmd 语法），Git Bash 下照抄必崩：门禁脚本打印 ✅ 时
    # UnicodeEncodeError，而且崩在打印阶段、退出码仍是 0 —— 只看退出码会被骗过去。
    brief = "\n".join(PL.note_brief())
    assert "PYTHONIOENCODING=utf-8" in brief
    assert "export PYTHONIOENCODING" in brief      # bash
    assert "$env:PYTHONIOENCODING" in brief        # PowerShell


# --- stale upstream: the trap the first failed clean run exposed -----------

def test_relay_guard_rejects_stale_upstream(tmp_path):
    # 03_清洗 still holds an earlier run's output while clean is not recorded
    # done; note must refuse instead of quietly writing from stale text.
    root = tmp_path / RUN
    (root / "03_清洗").mkdir(parents=True)
    (root / "03_清洗" / "full.txt").write_text("stale", encoding="utf-8")
    blocked = PL.relay_guard("note", PL.relay_sources(root, "note"), root)
    assert blocked is not None and "陈旧" in blocked.error


def test_relay_guard_allows_upstream_once_producer_is_done(tmp_path):
    from material_to_notes.orchestrate import workspace as WS

    root = tmp_path / RUN
    WS.init(root)
    WS.save(root, {"version": 1, "steps": {"clean": {"status": "done", "fp": "x"}}})
    (root / "03_清洗" / "full.txt").write_text("fresh", encoding="utf-8")
    assert PL.relay_guard("note", PL.relay_sources(root, "note"), root) is None
