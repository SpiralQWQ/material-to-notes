"""Wire the pieces: input -> route -> serial chain -> progress.

Only this module knows how the layers fit together. The layers stay clean:
adapters run tools, gates judge, report records, orchestrate sequences.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from material_to_notes.contract import metadata as _metadata
from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as _workdir
from material_to_notes.gates import machine as _machine
from material_to_notes.orchestrate import discipline as _discipline
from material_to_notes.orchestrate import failures as _failures
from material_to_notes.orchestrate import resume as _resume
from material_to_notes.orchestrate import router as _router
from material_to_notes.orchestrate import runner as _runner
from material_to_notes.orchestrate import spec as _spec
from material_to_notes.orchestrate import staging as _staging
from material_to_notes.orchestrate import workspace as _workspace
from material_to_notes.report import logs as _logs
from material_to_notes.report import progress as _progress
from material_to_notes.report import snapshots as _snapshots

# Which upstream output a step reads, relative to the workdir — the relay contract.
# Patterns are specific on purpose. Three things in 02_转md are not upstream output:
# enrich writes images_notes/*.md and backs up full.md as *.md.bak; and a book over
# 200 pages keeps its p{start}-{end} blocks after `dtmd merge` stitches them into
# the dir root, so a bare "**/full.md" would hand the next step the merged file and
# every slice at once. "producers" guards against stale input: see relay_guard.
RELAY = {
    "clean": {"dir": "02_转md", "patterns": ("**/*_mineru/full.md", "**/*_clean.md"),
              "producers": ("document", "media")},
    "note": {"dir": "03_清洗", "patterns": ("**/*.txt",), "producers": ("clean",)},
}

# Writing the note is an agent's job, not a headless subprocess's (SOP §一).
NOTE_STEP = "note"

# 派活单上写"产物文件名"时要补的扩展名（名字本身是词干）。
PRODUCT_SUFFIX = {NOTE_STEP: ".md", "clean": ".txt", "document": ".md", "media": ".md"}
ASSIGN_FILE = "任务单-note.md"


@dataclass(frozen=True)
class Plan:
    kind: str
    chain: tuple
    needs_user: bool = False


def plan(target, kind=None) -> Plan:
    """What will run for this input.

    ``kind`` overrides the guess: a bare search term looks exactly like an
    unknown path, so the caller must be able to say "this is a term".
    An unknown input asks the user instead.
    """
    resolved = kind or _router.classify(target)
    chain = _router.route(resolved)
    return Plan(resolved, chain, needs_user=not chain)


def relay_sources(root, step_id: str) -> tuple:
    """Every file this step reads from upstream, in stable order."""
    spec = RELAY.get(step_id)
    if spec is None:
        return ()
    base = Path(root) / spec["dir"]
    if not base.is_dir():
        return ()
    found = set()
    for pattern in spec["patterns"]:
        found.update(p for p in base.glob(pattern) if p.is_file())
    return tuple(sorted(found))


def producers_recorded(root, step_id: str, state=None) -> bool:
    """Whether at least one producer of this step is recorded done in the state."""
    spec = RELAY.get(step_id)
    if not spec or not spec.get("producers"):
        return True
    state = _workspace.load(root) if state is None else state
    steps = (state or {}).get("steps") or {}
    return any((steps.get(name) or {}).get("status") == "done" for name in spec["producers"])


def relay_source(root, step_id: str):
    """The single upstream file, or None. Use ``relay_sources`` to detect multiples."""
    found = relay_sources(root, step_id)
    return found[0] if found else None


def relay_guard(step_id: str, sources: tuple, root=None, names=None):
    """An Outcome when the relay is unusable, else None.

    Blocks three things rather than quietly proceeding: no upstream file, a
    **name collision** (two sources that would write over each other), and — the
    subtle one — upstream files left behind by a *failed* producer, which would
    feed the note stale content with no error anywhere.

    More than one source is no longer a block: the step loops over them.
    """
    if not sources:
        subdir = RELAY.get(step_id, {}).get("dir", "?")
        return _runner.Outcome(False, f"{step_id}: {subdir} 下没有可读的上游产物")
    if names is not None and len(set(names)) != len(names):
        seen, clashes = set(), []
        for name in names:
            (clashes.append(name) if name in seen else seen.add(name))
        return _runner.Outcome(
            False,
            f"{step_id}: 两份素材会写成同一个名字（{'、'.join(sorted(set(clashes)))}），"
            f"先改名再跑 —— 停下问用户",
        )
    if root is not None and not producers_recorded(root, step_id):
        return _runner.Outcome(
            False,
            f"{step_id}: 上游那一步并未记录完成，现有产物是上一轮遗留的，"
            f"直接读会拿到陈旧内容 —— 停下问用户",
        )
    return None


def source_names(root, step_id: str) -> tuple:
    """Every upstream source paired with the name its outputs will carry.

    The name is the user's intake override when there is one, else the source's
    own name — never the step's, or two sources would collide.
    """
    sheet = _metadata.load_sheet(root)
    return tuple((path, _metadata.name_for(sheet, _workdir.source_name(path),
                                           _workdir.source_name(path)))
                 for path in relay_sources(root, step_id))


def fetched_kinds(root) -> tuple:
    """Input kinds present under 01_取材 — decides what runs after fetch."""
    base = Path(root) / "01_取材"
    if not base.is_dir():
        return ()
    kinds = {_router.classify(p) for p in base.rglob("*") if p.is_file() and p.suffix}
    kinds.discard(_router.UNKNOWN)
    return tuple(sorted(kinds))


def default_executors(params: dict) -> dict:
    """The real adapters, wired to the workdir relay."""
    from material_to_notes.steps import clean, document, fetch, media, note

    def run_fetch(root):
        return fetch.run(root, terms=params.get("terms", ""), sites=params.get("sites", ""))

    def run_document(root):
        return document.run(root, src_dir=params.get("src_dir", ""),
                            mode=params.get("mode", "cloud"),
                            enrich=params.get("enrich", True),
                            glm=params.get("enrich_glm", True))

    def run_media(root):
        return media.run(root, sources=params.get("sources", ()), glm=params.get("glm", "no"))

    def run_clean(root):
        pairs = source_names(root, "clean")
        # No collision check here: intermediates are keyed by the source name,
        # which is unique by construction.
        blocked = relay_guard("clean", tuple(p for p, _n in pairs), root)
        if blocked is not None:
            return blocked
        outcome = None
        for src_file, _name in pairs:
            # Intermediates are keyed by the source, so no name is passed.
            outcome = clean.run(root, src_file=src_file, deep=params.get("deep_clean", False))
            if not outcome.ok:
                return outcome
        return outcome

    def run_note(root):
        pairs = source_names(root, "note")
        # Here the names ARE the deliverables, so two materials resolving to one
        # name would overwrite each other.
        blocked = relay_guard("note", tuple(p for p, _n in pairs), root,
                              names=[n for _p, n in pairs])
        if blocked is not None:
            return blocked
        outcome = None
        for src_md, name in pairs:
            outcome = note.run(root, src_md=src_md, name=name)
            if not outcome.ok:
                return outcome
        return outcome

    return {
        "fetch": run_fetch, "document": run_document, "media": run_media,
        "clean": run_clean, "note": run_note,
    }


def _source_fingerprint(root, step_id: str, target) -> str:
    """What this step reads: every upstream output, else the run target.

    Covers all of them so a change in any one invalidates the cached step.
    """
    sources = relay_sources(root, step_id)
    if not sources:
        return _resume.fingerprint(target)
    return "|".join(_resume.fingerprint(path) for path in sources)


def _segment(root, chain, target, executors, gates, review, max_attempts, on_progress,
             force=False):
    state = _workspace.load(root) or {}

    def is_done(step_id):
        # ``force`` re-runs the step even though the input fingerprint is
        # unchanged — the only way to redo a step after changing its *code*
        # rather than its input, which resume cannot see.
        if force:
            return False
        return _resume.is_done(state, step_id, _source_fingerprint(root, step_id, target))

    def mark_done(step_id):
        nonlocal state
        state = _resume.mark_done(state, step_id, _source_fingerprint(root, step_id, target))
        _workspace.save(root, state)

    def wrapped_review(step_id, root_):
        if not gates:
            return True, ""
        gate = _machine.check(step_id, root_)
        if not gate.passed:
            return False, gate.raw
        if review is not None:
            return review(step_id, root_)
        return True, ""

    def log_progress(step_id, status):
        _logs.record(root, step=step_id, level="info", message=_progress.line(step_id, status))
        if on_progress is not None:
            on_progress(step_id, status)

    def call(step_id, root_):
        """Keep the previous output, then let the step overwrite it.

        Dispatch time is the last moment the old version still exists, so this is
        where a snapshot has to happen — otherwise a later revision cannot be
        diffed and "I only changed these lines" is unprovable.
        """
        _snapshots.take(root, step_id)
        return executors[step_id](root_)

    # The command itself is logged by contract.runner.execute, which is the only
    # layer that sees every command a step runs (document runs three).
    return _runner.run_chain(
        root, chain,
        execute=call,
        review=wrapped_review, max_attempts=max_attempts,
        is_done=is_done, mark_done=mark_done, on_progress=log_progress,
    )


def _sheet_records(root, records):
    """This run's records, plus every step the state already has, in step order.

    ``pipeline step`` runs one step at a time, so building the sheet from that
    run alone would overwrite the record of the steps that ran before it — the
    sheet would show one row while three steps are actually done.
    """
    state = _workspace.load(root) or {}
    done = {name for name, rec in (state.get("steps") or {}).items()
            if (rec or {}).get("status") == "done"}
    seen = {record.step for record in records}
    extra = [_runner.StepRecord(step_id, _runner.DONE)
             for step_id in _steps.step_ids() if step_id in done and step_id not in seen]
    if not extra:
        return list(records)
    order = {step_id: index for index, step_id in enumerate(_steps.step_ids())}
    return sorted(list(records) + extra, key=lambda r: order.get(r.step, len(order)))


def _wrap_up(root, records, stopped_at):
    """Write the failure sheet (if stopped) and always the progress sheet.

    A run that ends without stopping clears any hand-off sheet left by an
    earlier run: otherwise the workdir claims both "clean failed" and "clean
    done", and the next agent cannot tell which sheet is current.
    """
    if stopped_at:
        record = next((r for r in records if r.step == stopped_at), None)
        if record is not None:
            _failures.write(root, _failures.Failure(
                step=stopped_at, error=record.error, attempts=record.attempts,
                artifacts=_progress.artifacts(root, stopped_at),
            ))
    else:
        _failures.clear(root)
    _progress.write(root, _progress.build(_sheet_records(root, records), root))


def run(root, target, *, executors, kind=None, gates=True, review=None,
        max_attempts=_failures.DEFAULT_MAX_ATTEMPTS, on_progress=None,
        handoff_note=False, force=False) -> dict:
    """Run the whole chain for one input: serially, with resume and gates.

    With ``handoff_note`` the trailing note step is not executed: writing the
    note is an agent's job (per SOP), so it is left for the main conversation to
    dispatch instead of being shelled out to a headless subprocess.
    """
    result = {"plan": plan(target, kind=kind), "report": None, "gates": (),
              "asked_user": False, "needs_agent": ""}
    # Absolute: adapters run tools with cwd set to the tool repo, so a relative
    # workdir would resolve against the wrong directory inside the child. Only
    # resolve a target that actually is a path — a term or URL must stay as-is.
    root = Path(root).resolve()
    if str(target) and Path(target).exists():
        target = str(Path(target).resolve())
    if result["plan"].needs_user:
        result["asked_user"] = True
        return result

    _workspace.init(root, input_kind=result["plan"].kind, inputs=[str(target)])
    records = []
    chain = tuple(result["plan"].chain)

    if chain == ("fetch",):
        segment = _segment(root, ("fetch",), target, executors, gates, review, max_attempts,
                           on_progress, force=force)
        records.extend(segment.records)
        if segment.stopped_at:
            _wrap_up(root, records, segment.stopped_at)
            result["report"] = _runner.RunReport(records, segment.stopped_at)
            return result
        chain = _router.route_after_fetch(fetched_kinds(root))
        if not chain:
            result["asked_user"] = True
            _wrap_up(root, records, "")
            result["report"] = _runner.RunReport(records, "")
            return result

    handoff = bool(handoff_note and chain and chain[-1] == NOTE_STEP)
    if handoff:
        chain = chain[:-1]
        result["needs_agent"] = NOTE_STEP

    segment = _segment(root, chain, target, executors, gates, review, max_attempts,
                       on_progress, force=force)
    records.extend(segment.records)
    _wrap_up(root, records, segment.stopped_at)
    result["report"] = _runner.RunReport(records, segment.stopped_at)
    result["gates"] = _machine.check_all(root, chain) if gates else ()

    # 任务单**在上游跑完之后**才写：它要列出"每份素材 → 笔记叫什么名字"，
    # 而那些名字来自清洗产物——先写单子的话那份清单是空的，写手连该产出哪几个
    # 文件都不知道（2026-10-15 实跑踩到：单子上"输入：（原始输入）"，一个文件名都没有）。
    if handoff and not segment.stopped_at:
        write_text(root, ASSIGN_FILE, assign_sheet(root, NOTE_STEP))
    return result


# Inputs that arrive as text rather than files on disk: nothing to stage.
NON_FILE_KINDS = ("terms", "links")

# The fetch adapter models "vocabulary file + sites", not an arbitrary page URL.
# A bare link therefore cannot run end to end yet, so say so rather than fire a
# command that would quietly crawl the wrong thing.
UNWIRED_KINDS = ("links",)
UNWIRED_REASON = "这条线还没接：取材适配器目前只支持「词汇文件 + 站点」，不接单个网页链接"


def first_known_kind(targets) -> str:
    """The first target whose shape we recognise; UNKNOWN when none do."""
    for target in targets:
        kind = _router.classify(target)
        if kind != _router.UNKNOWN:
            return kind
    return _router.UNKNOWN


ALBUM_MODES = ("one", "each")

# A folder is one material, so handing it in beside other inputs would make it
# impossible to say which note belongs to which material.
FOLDER_ALONE_ASK = ("目录素材只能单独跑：请一次只传那一个文件夹（和别的素材混在一起传时，"
                    "没法说清哪份笔记对应哪份素材）。停下问用户。")

# Never materials: OS clutter and hidden files (anything dot-prefixed).
IGNORED_NAMES = {"thumbs.db", "desktop.ini"}


def scan_folder(folder) -> dict:
    """What sits directly inside ``folder``, split by kind. Read-only.

    One level only — the same depth the media adapter uses when it expands a
    folder, so "how many notes" here and "which files" there agree. A nested
    folder is reported as a subdir rather than walked, because m2m would drop it
    too and counting it here would promise notes nobody writes.

    Keys: ``images`` / ``videos`` / ``audios`` / ``subdirs`` / ``others``, each a
    list of paths in name order.
    """
    found = {"images": [], "videos": [], "audios": [], "subdirs": [], "others": []}
    for entry in sorted(Path(folder).iterdir(), key=lambda p: p.name):
        if entry.name.startswith(".") or entry.name.lower() in IGNORED_NAMES:
            continue
        if entry.is_dir():
            found["subdirs"].append(entry)
            continue
        ext = entry.suffix.lower()
        if ext in _router.IMAGE:
            found["images"].append(entry)
        elif ext in _router.VIDEO:
            found["videos"].append(entry)
        elif ext in _router.AUDIO:
            found["audios"].append(entry)
        else:
            found["others"].append(entry)
    return found


def _folder_counts(found) -> str:
    """“图片 2 张、视频 1 个” — only the kinds actually present."""
    bits = []
    if found["images"]:
        bits.append(f"图片 {len(found['images'])} 张")
    if found["videos"]:
        bits.append(f"视频 {len(found['videos'])} 个")
    if found["audios"]:
        bits.append(f"音频 {len(found['audios'])} 个")
    return "、".join(bits)


def _name_list(paths, limit=5) -> str:
    names = "、".join(p.name for p in paths[:limit])
    return names + (f" 等 {len(paths)} 个" if len(paths) > limit else "")


def _folder_plan(folder, found, album) -> dict:
    """What a folder means, given what it actually holds and ``album``.

    Exactly one of these shapes comes back:
      ``{"ask": reason}`` / ``{"refuse": reason}`` — stop, change nothing;
      ``{"materials": [(path, kind), ...], "pure_images": bool}`` — one workdir each;
      ``{"file": (path, kind)}`` — a lone media file, staged as a file;
      ``{"folder": path}`` — pure images under ``one``, staged as a folder.

    Nothing here touches the disk: every question is decided from the scan, so a
    run that stops has not staged or created anything yet.
    """
    images, videos, audios = found["images"], found["videos"], found["audios"]

    if found["subdirs"] or found["others"]:
        have = _folder_counts(found) or "没有可处理的素材"
        extra = []
        if found["subdirs"]:
            extra.append(f"子文件夹 {len(found['subdirs'])} 个（{_name_list(found['subdirs'])}）")
        if found["others"]:
            extra.append(f"其他文件 {len(found['others'])} 个（{_name_list(found['others'])}）")
        return {"ask": (
            f"文件夹 {folder.name} 里有{have}，另有{'、'.join(extra)}。"
            f"第一层只认图片/视频/音频，子文件夹和其他文件既不递归、也不静默丢掉。"
            f"停下问用户：先把它们清理或移走，再重跑。")}

    materials = sorted(
        [(p, "image") for p in images] + [(p, "video") for p in videos]
        + [(p, "audio") for p in audios], key=lambda pair: pair[0].name)
    if not materials:
        return {"ask": f"目录里没有可处理的素材（{folder}）：没有图片、视频或音频。停下问用户。"}

    # A lone media file is unambiguous no matter its kind: there is no one/each
    # question to ask, so stage the file itself, not the folder.
    if len(materials) == 1:
        return {"file": materials[0]}

    pure_images = not videos and not audios
    if pure_images:
        if album is None:
            album = "one"                    # 用户裁定（2026-10-21）：纯图片默认合成一份
        if album == "one":
            return {"folder": folder}          # the historical folder-as-album run
        return {"materials": materials, "pure_images": True}

    # Video/audio only, or images mixed with them. one cannot merge video/audio,
    # so per-material is the only reading those folders have; mixed folders keep
    # both readings (split them, or one note each) and still ask.
    counts = _folder_counts(found)
    if album is None and not images:
        album = "each"                   # 用户裁定（2026-10-21）：音视频默认一份素材一份笔记
    if album is None:
        return {"ask": (
            f"输入是一个文件夹，里面有{counts}（共 {len(materials)} 份素材）："
            f"图片可以合成图集，也可以全部逐份写（--album each），两条路不一样。"
            f"停下问用户：拆开跑，或明确传 --album。")}
    if album == "each":
        return {"materials": materials, "pure_images": False}
    if images:
        return {"refuse": (
            f"文件夹里有{counts}（共 {len(materials)} 份素材），合成一份做不到："
            f"m2m 会把图片合成图集、对视频/音频却是逐个输出，混在一起只会悄悄少笔记。"
            f"停下问用户：把图片和音视频拆开再跑，或用 --album each 每份素材各一份。")}
    return {"refuse": (
        f"文件夹里有{counts}（共 {len(materials)} 份素材），m2m 对视频/音频是逐个处理、"
        f"不能合成一份笔记（--album one 只对纯图片文件夹有效）。"
        f"停下问用户：用 --album each 每份素材各一份，或只传一个文件。")}


def autorun(root, targets, *, kind=None, mode="cloud", glm="no", terms_file="", sites="",
            enrich=True, deep_clean=False, executors=None, gates=True, review=None,
            handoff_note=None,
            max_attempts=_failures.DEFAULT_MAX_ATTEMPTS, on_progress=None,
            force=False, album=None) -> dict:
    """Stage the inputs, work out the route, then run the chain end to end.

    This is what ``pipeline run`` drives. Pass ``executors`` to run the chain
    against something other than the real tools (tests, dry runs).

    A folder is scanned before anything is decided, because what it holds changes
    the answer: pure images can be one album or one note each, while video/audio
    are processed file by file and cannot be merged into one note. ``album``
    settles it — ``one`` means a single note (pure images only), ``each`` gives
    every material its own workdir under ``root`` (``图片N`` for a pure image
    folder, ``素材N`` otherwise). Left unset, folder contents that allow more
    than one reading stop and ask; so do subfolders and non-media files, which
    are never silently dropped.
    """
    items = [str(targets)] if isinstance(targets, (str, Path)) else [str(t) for t in targets]
    resolved = kind or first_known_kind(items)
    route = _router.route(resolved)

    def blocked(reason, kind=None):
        return {"plan": plan("", kind=kind or resolved), "report": None, "gates": (),
                "asked_user": True, "reason": reason, "staged": (),
                "per_image_roots": (), "per_material_roots": ()}

    # A folder cannot share a run with other inputs: the result would not say
    # which note belongs to which material. Checked before the route, because a
    # file listed first would otherwise hide the folder behind its own kind.
    if album is not None and album not in ALBUM_MODES:
        return blocked(f"--album 只认 {'/'.join(ALBUM_MODES)}，收到 {album!r}：停下问用户")
    folders = [Path(i) for i in items if Path(i).is_dir()]
    if folders and len(items) > 1:
        return blocked(FOLDER_ALONE_ASK, kind="album")
    if not route:
        return blocked(f"不认识的输入（{resolved}）：停下问用户，不猜")
    if resolved in UNWIRED_KINDS and executors is None:
        return blocked(UNWIRED_REASON)

    if resolved == "album":
        if not folders:
            return blocked("--album 只对文件夹有意义：这个输入不是文件夹。停下问用户。")
        # Scan first: the folder's actual contents decide the question. Nothing
        # past this point may touch the disk before the user has answered.
        found = scan_folder(folders[0])
        decision = _folder_plan(folders[0], found, album)
        if "ask" in decision:
            return blocked(decision["ask"])
        if "refuse" in decision:
            return blocked(decision["refuse"])
        if "materials" in decision:
            return _autorun_each_material(
                root, decision["materials"], pure_images=decision["pure_images"],
                mode=mode, glm=glm, enrich=enrich, deep_clean=deep_clean,
                executors=executors, gates=gates, review=review,
                handoff_note=handoff_note, max_attempts=max_attempts,
                on_progress=on_progress, force=force)
        if "file" in decision:
            lone, lone_kind = decision["file"]
            items = [str(lone)]
            resolved = lone_kind
            route = _router.route(resolved)
        # "folder": pure images with --album one — stage the folder as before.

    staged = () if resolved in NON_FILE_KINDS else _staging.stage(root, items)
    params = {
        "src_dir": str(Path(root) / _workdir.INPUT_DIR),
        "sources": [str(path) for path in staged],
        "mode": mode,
        "glm": glm,
        "terms": terms_file,
        "sites": sites,
        "enrich": enrich,
        "deep_clean": deep_clean,
    }
    chosen = executors if executors is not None else default_executors(params)
    probe = str(staged[0]) if staged else (terms_file or (items[0] if items else ""))

    # Real runs hand the note to an agent; injected executors (tests, dry runs) do not.
    handoff = executors is None if handoff_note is None else handoff_note
    out = run(root, probe, kind=resolved, executors=chosen, gates=gates, review=review,
              max_attempts=max_attempts, on_progress=on_progress, handoff_note=handoff,
              force=force)
    out["staged"] = staged
    out["per_image_roots"] = ()
    out["per_material_roots"] = ()
    out["reason"] = "取材没取到可用素材，需人工确认走哪条线" if out["asked_user"] else ""
    return out


def _autorun_each_material(root, materials, *, pure_images, **kw) -> dict:
    """One workdir per material, under ``root`` — a folder read as "one note each".

    Each file is staged into its own workdir and run with its **own** kind
    (image / video / audio), so a mixed folder asks the adapter per file instead
    of guessing one kind for the whole batch. Directories are numbered by
    position: a pure image folder keeps the historical ``图片N``, everything else
    uses ``素材N``. Each file is copied under its own name into its own workdir,
    so two files sharing a name still get separate notes.
    """
    root = Path(root)
    prefix = "图片" if pure_images else "素材"

    reports, roots, staged_all, handed_off = [], [], [], False
    for position, (path, kind) in enumerate(materials, 1):
        sub = root / f"{prefix}{position}"
        sub.mkdir(parents=True, exist_ok=True)
        staged = _staging.stage(sub, [path])
        params = {
            "src_dir": str(sub / _workdir.INPUT_DIR),
            "sources": [str(p) for p in staged],
            "mode": kw["mode"], "glm": kw["glm"], "terms": "", "sites": "",
            "enrich": kw["enrich"], "deep_clean": kw["deep_clean"],
        }
        chosen = kw["executors"] if kw["executors"] is not None else default_executors(params)
        handoff = (kw["executors"] is None if kw["handoff_note"] is None
                   else kw["handoff_note"])
        out = run(sub, str(staged[0]), kind=kind, executors=chosen, gates=kw["gates"],
                  review=kw["review"], max_attempts=kw["max_attempts"],
                  on_progress=kw["on_progress"], handoff_note=handoff, force=kw["force"])
        reports.append(out["report"])
        roots.append(str(sub))
        staged_all.extend(staged)
        handed_off = handed_off or bool(out.get("needs_agent"))
        if out["asked_user"] or out["report"] is None or not out["report"].ok:
            break  # 一份没跑通就停：后面的结论都不可信

    # 每份都跑到了才算整批完成——只看最后一份会把"最后一份失败"当成成功。
    all_ok = bool(reports) and all(r is not None and r.ok for r in reports)
    return {
        "plan": plan("", kind="album"),
        "report": reports[-1] if reports else None,
        "reports": tuple(reports),
        "gates": (),
        "asked_user": False,
        "needs_agent": NOTE_STEP if (all_ok and handed_off) else "",
        "reason": "",
        "staged": tuple(staged_all),
        "per_image_roots": tuple(roots) if pure_images else (),
        "per_material_roots": tuple(roots),
        "per_image_all_ok": all_ok,
        "stopped_early": not all_ok and len(reports) < len(materials),
    }



def write_text(root, name: str, text: str) -> Path:
    """Write a run artifact into the workdir (workdir is never committed)."""
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def staged_inputs(root) -> tuple:
    """Whatever was staged under 00_输入, in stable order."""
    base = Path(root) / _workdir.INPUT_DIR
    if not base.is_dir():
        return ()
    return tuple(sorted(p for p in base.iterdir()))


ASSIGN_RULES = (
    "只报告，不修改任何代码（包括五个零件）。",
    "每条结论给证据：文件路径、行号，或门禁的原始输出。",
    "没发现问题就写「未发现」，不许为了交差编造问题。",
    "失败原样回报，不美化；重试次数由主对话掌握（单步共 3 次）。",
)

_BRIEF_HEAD = (
    "**由你亲自写笔记**，不是 shell 调 mre 再让它去找模型。",
    "**frontmatter 的 `word_count` 填源文（`03_清洗/<名>.txt`）的字符数（含换行），不是笔记自己写了多少字**："
    "已交付的笔记一律是这个口径，用来记「这份素材有多大」；填成笔记长度会和源文规模对不上。"
    "**笔记改完之后要重填一次**——每次写盘或跑 `pipeline toc` 都会改动文件，字数跟着变。",
    "**上面列了几份素材，就写几份笔记**，一份一个文件、文件名严格用上面给的名字，"
    "每份笔记只讲它自己那份素材（不要串味、不要合并成一份）。",
)

_BRIEF_TAIL = (
    "源文里形如 `## 插图笔记：<64位十六进制>` 的小节，那串十六进制是**流水线内部的图片编号**"
    "（图片文件的 sha256），不是论文内容；读者拿不到它也用不上它，**任何地方都不许抄**——"
    "包括文末索引表与「元信息」：要指图就用**图号或图的内容**（如「Figure 3 的 K-means 散点图」），"
    "那才是读者能在原文里找到的东西。",
    "写完跑两道门禁，各管不同的事。① 内容门禁（确定性脚本，不调模型）："
    "`python \"parts/md-rewrite-engine/scripts/gate_check.py\" <笔记.md> --src <该份素材清洗后的原文>` "
    "—— **先给这条命令设 `PYTHONIOENCODING=utf-8`**，否则它打印的 ✅ 会让子进程崩掉、"
    "看着像门禁坏了；而且那个崩发生在**打印阶段**、退出码仍是 0，只看退出码会被骗过去。"
    "各 shell 写法不同：cmd `set PYTHONIOENCODING=utf-8`、Git Bash `export PYTHONIOENCODING=utf-8`、"
    "PowerShell `$env:PYTHONIOENCODING=\"utf-8\"`。"
    "查机械对账 ≥90% / 六件套齐 / 费曼 ≥2 / 膨胀率过线；**禁止加 `--score`**（那是 GLM 评分，"
    "按 SOP 已由独立审核子 agent 取代）。每份笔记都要跑，且 `--src` 必须是它自己那份原文。",
    "② 产物契约：`pipeline gate <工作目录> note` —— 由主对话跑，会逐份核对。",
    "语义对账、幻觉、六件套是否名副其实，由**另一个独立审核子 agent** 按 `pipeline checklist note` 判。",
)


def note_brief(env=None) -> tuple:
    """The note-writing brief for one dispatch.

    Its **shape half is read out of the part right now** (``orchestrate/spec.py``)
    rather than transcribed here: the 2026-10-15 incident was a brief that had
    quietly drifted from the spec it claimed to describe, and no test could catch
    it because the same drift lived on both sides. The fixed halves are the
    disciplines that have nothing to do with the note's shape.
    """
    return (_BRIEF_HEAD + _spec.shape_lines(env) + _discipline.discipline_lines()
            + _BRIEF_TAIL)


def assign_sheet(root, step_id: str, *, env=None) -> str:
    """The dispatch sheet handed to a fresh sub-agent for exactly one step.

    ``env`` reaches the note brief's spec projection; leaving it out is the normal
    case (the part lives in ``parts/``).
    """
    step = _steps.get_step(step_id)
    base = Path(root)
    pairs = source_names(base, step.id)
    out_dir = _workdir.step_dir(base, step)
    lines = [
        f"# 任务单 · {step.name}（{step.id}）",
        "",
        "- 执行者：主对话开启的**执行子 agent**（一次一个，严格串行，禁止并行）",
        f"- 用哪个零件：`{step.tool}`",
    ]
    if pairs:
        # 名字是**词干**（`W.source_name` 会剥掉扩展名），产物得带扩展名才算说清；
        # 只写词干会让写手产出 `v` 而不是 `v.md`，门禁按 `*.md` 找不到文件。
        suffix = PRODUCT_SUFFIX.get(step.id, "")
        lines.append(f"- 输入（上游素材 {len(pairs)} 份），以及每份产物的文件名：")
        lines += [f"  - `{src}` → `{name}{suffix}`" for src, name in pairs]
        lines.append(f"- 产物必须写到：`{out_dir}/`，**每份素材一个文件，文件名就是上面那个**")
    else:
        lines.append(f"- 输入：{base / _workdir.INPUT_DIR}（原始输入）")
        lines.append(f"- 产物必须写到：`{out_dir}`")
    if step.id == NOTE_STEP:
        # **不要**在这张单子上写 `pipeline step … note`：那条命令会 shell 调 mre
        # **重新生成** `04_笔记/<名>.md`，把 agent 手写的产物顶掉（有快照可回溯，
        # 但极易照单执行而误覆盖——T57）。写笔记的人只需要：读单子 → 手写 → 自跑门禁。
        lines.append("- 执行：**由你亲自写笔记**（见下）。**不要**跑 `pipeline step … note` —— 它会用零件重新生成笔记、覆盖你刚写的产物。")
    else:
        lines.append(f"- 执行：`pipeline step {base} {step.id}`")
    lines += [
        "",
        "## 这一步要做的事",
    ]
    lines += [f"- {item}" for item in (note_brief(env) if step.id == NOTE_STEP
                                       else (f"调用零件 `{step.tool}` 完成本步；失败即报，不吞错、不改代码。",))]
    lines += ["", "## 回报格式", "做没做完 + 产物在哪 + 遇到的问题（原始错误照贴）。",
              "", "## 硬规则"] + [f"- {rule}" for rule in ASSIGN_RULES] + [""]
    return "\n".join(lines)


def step(root, step_id, *, mode="cloud", glm="no", enrich=True, deep_clean=False,
         terms_file="", sites="",
         executors=None, gates=True, review=None,
         max_attempts=_failures.DEFAULT_MAX_ATTEMPTS, on_progress=None, force=False):
    """Run exactly one step of an initialised workdir.

    This is what lets the main conversation dispatch a fresh sub-agent per step
    instead of driving the whole chain inside one process.
    """
    step_obj = _steps.get_step(step_id)
    root = Path(root).resolve()
    state = _workspace.load(root) or {}
    inputs = state.get("inputs") or [""]
    staged = staged_inputs(root)
    chosen = executors if executors is not None else default_executors({
        "src_dir": str(Path(root) / _workdir.INPUT_DIR),
        "sources": [str(p) for p in staged],
        "mode": mode,
        "glm": glm,
        "terms": terms_file,
        "sites": sites,
        "enrich": enrich,
        "deep_clean": deep_clean,
    })
    outcome = _segment(root, (step_obj.id,), inputs[0], chosen, gates, review, max_attempts,
                       on_progress, force=force)
    _wrap_up(root, outcome.records, outcome.stopped_at)
    return outcome
