"""Command-line entry point.

Thin: parse arguments, call into the layers, map the outcome onto an exit code.
No business logic lives here.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from material_to_notes.contract import __version__
from material_to_notes.contract import metadata as _metadata
from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as _workdir
from material_to_notes.gates import content as _content
from material_to_notes.gates import machine as _machine
from material_to_notes.gates import review as _review
from material_to_notes.orchestrate import pipeline as _pipeline
from material_to_notes.orchestrate import router as _router
from material_to_notes.orchestrate import workspace as _workspace
from material_to_notes.report import progress as _progress
from material_to_notes.report import snapshots as _snapshots
from material_to_notes.steps import note as _note

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_NEEDS_USER = 3
EXIT_HANDED_OFF = 4


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="material-to-notes", description="五工具流水线编排层")
    parser.add_argument("--version", action="version", version=f"material-to-notes {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    p_init = sub.add_parser("init", help="初始化一个工作目录")
    p_init.add_argument("workdir")
    p_init.add_argument("--kind", default=None, help="输入类型")
    p_init.add_argument("--input", action="append", default=[], help="输入路径（可多次）")
    p_init.add_argument("--force", action="store_true", help="覆盖已有状态")

    p_route = sub.add_parser("route", help="看一个输入会走哪条线")
    p_route.add_argument("target")

    p_run = sub.add_parser("run", help="把一条线端到端跑起来（自检/冒烟路径；note 步交子 agent）")
    p_run.add_argument("workdir")
    p_run.add_argument("target", nargs="+", help="输入文件或目录；词汇线配 --terms-file 用")
    p_run.add_argument("--kind", default=None, help="显式声明输入类型（如 terms）；不填按输入猜")
    p_run.add_argument("--mode", default="cloud", choices=list(_document_modes()),
                       help="文档线转换模式，默认 cloud（本机没有本地 MinerU）")
    p_run.add_argument("--glm", default="no", choices=["yes", "no"], help="媒体线是否开画面理解")
    p_run.add_argument("--no-enrich", dest="enrich", action="store_false",
                       help="跳过插图融合（默认执行：OCR+视觉理解后内嵌回 full.md）")
    p_run.add_argument("--terms-file", default="", help="词汇线：词汇文件路径")
    p_run.add_argument("--sites", default="", help="词汇线：站点子集，逗号分隔")
    p_run.add_argument("--deep-clean", action="store_true",
                       help="清洗走全规则含 trafilatura（仅适合网页/OCR 噪音素材）")
    p_run.add_argument("--force", action="store_true",
                       help="忽略续跑记录，重跑整条线（改了某步代码但输入没变时用）")
    p_run.add_argument("--album", default=None, choices=["one", "each"],
                       help="文件夹怎么算笔记：one=纯图片文件夹合成一份（纯图片默认）；"
                            "each=每份素材各一份（视频/音频默认，图片逐张、视频/音频逐个）。"
                            "图片+视频混合文件夹会停下问你")

    p_step = sub.add_parser("step", help="只跑一步（供主对话派给子 agent）")
    p_step.add_argument("workdir")
    p_step.add_argument("step")
    p_step.add_argument("--mode", default="cloud", choices=list(_document_modes()))
    p_step.add_argument("--glm", default="no", choices=["yes", "no"])
    p_step.add_argument("--no-enrich", dest="enrich", action="store_false")
    p_step.add_argument("--deep-clean", action="store_true",
                        help="清洗走全规则含 trafilatura（仅适合网页/OCR 噪音素材）")
    p_step.add_argument("--terms-file", default="")
    p_step.add_argument("--sites", default="")
    p_step.add_argument("--force", action="store_true",
                        help="忽略续跑记录，强制重跑这一步（改了这步代码但输入没变时用）")

    p_intake = sub.add_parser("intake", help="看/写投料单（初始化时问的那三件，答一次就够）")
    p_intake.add_argument("workdir")
    p_intake.add_argument("--audience", default=None, help="笔记给谁看 / 干什么用")
    p_intake.add_argument("--deliver-dir", default=None, help="笔记产出目录（不填＝就地放工作目录）")
    p_intake.add_argument("--name", action="append", default=[],
                          help="给某份素材改名，格式 <素材名>=<想要的名字>，可重复")

    p_deliver = sub.add_parser("deliver", help="把笔记拷到投料单指定的交付目录")
    p_deliver.add_argument("workdir")

    p_assign = sub.add_parser("assign", help="打印某步的任务单（派发用；会先给上一版产物留底）")
    p_assign.add_argument("workdir")
    p_assign.add_argument("step")

    p_snaps = sub.add_parser("snapshots", help="列出某步留底过的产物版本")
    p_snaps.add_argument("workdir")
    p_snaps.add_argument("step")

    p_gate = sub.add_parser("gate", help="跑某步的机器门禁")
    p_gate.add_argument("workdir")
    p_gate.add_argument("step")
    p_gate.add_argument("--contract-only", action="store_true",
                        help="只跑通用产物契约（产物存在/非空/编码），跳过 note 的内容门禁")

    p_toc = sub.add_parser("toc", help="用零件给笔记补/刷新篇内目录（写完笔记、跑门禁之前跑）")
    p_toc.add_argument("workdir")

    p_check = sub.add_parser("checklist", help="打印某步的审核检查单")
    p_check.add_argument("step")

    return parser


def _document_modes() -> tuple:
    from material_to_notes.steps import document as _document

    return _document.MODES


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.cmd == "init":
        path = _workspace.init(args.workdir, input_kind=args.kind,
                               inputs=args.input, overwrite=args.force)
        print(f"工作目录已就绪：{path}")
        return EXIT_OK

    if args.cmd == "route":
        kind = _router.classify(args.target)
        chain = _router.route(kind)
        if not chain:
            print(f"不认识的输入（{kind}）：停下问用户，不猜。")
            return EXIT_NEEDS_USER
        print(f"输入类型 {kind} → " + " → ".join(chain))
        return EXIT_OK

    if args.cmd == "run":
        return _do_run(args)

    if args.cmd == "step":
        return _do_step(args)

    if args.cmd == "intake":
        return _do_intake(args)

    if args.cmd == "deliver":
        return _do_deliver(args)

    if args.cmd == "assign":
        try:
            # Dispatching is the last moment the previous output still exists —
            # take the snapshot here so a later revision can be diffed at all.
            taken = _snapshots.take(args.workdir, args.step)
            print(_pipeline.assign_sheet(args.workdir, args.step))
            if taken is not None:
                print(f"（已留底上一版产物：{_snapshots.relpath(Path(args.workdir), taken)}）")
        except KeyError as exc:
            print(f"停下问用户：{exc}")
            return EXIT_NEEDS_USER
        return EXIT_OK

    if args.cmd == "snapshots":
        try:
            _steps.get_step(args.step)
        except KeyError as exc:
            print(f"停下问用户：{exc}")
            return EXIT_NEEDS_USER
        found = _snapshots.listing(args.workdir, args.step)
        if not found:
            print(f"{args.step}: 没有留底（只在下一次派活时才会留上一版）")
            return EXIT_OK
        for path in found:
            print(_snapshots.relpath(Path(args.workdir), path))
        return EXIT_OK

    if args.cmd == "gate":
        try:
            result = _machine.check(args.step, args.workdir)
        except KeyError as exc:
            print(f"停下问用户：{exc}")
            return EXIT_NEEDS_USER
        print(result.raw)
        passed = result.passed
        # The note is the deliverable, and its content gate lives in mre. Run it
        # here so the verdict comes from the pipeline rather than from whichever
        # agent wrote the note.
        if args.step == _pipeline.NOTE_STEP and not args.contract_only:
            content = _content.check_note(args.workdir)
            print(content.raw)
            passed = passed and content.passed
            if passed:
                # 笔记由 agent 手写、不走 `material-to-notes step`，所以跑完那条链的进度单
                # 里没有它那一行；门禁通过就是"这一步确实成了"的认证点，补上它，
                # 免得进度单与磁盘对不上（SOP §六 / T58）。
                sheet = Path(args.workdir) / _workdir.PROGRESS_FILE
                if sheet.is_file():
                    sheet.write_text(
                        _progress.with_note_row(sheet.read_text(encoding="utf-8"),
                                                Path(args.workdir), _pipeline.NOTE_STEP),
                        encoding="utf-8")
        return EXIT_OK if passed else EXIT_RUN_FAILED

    if args.cmd == "toc":
        # 目录是标题的确定性副产品；零件自己会生成（规范：AI 无需手写）。
        ok, detail = _note.refresh_tocs(args.workdir)
        print(detail)
        return EXIT_OK if ok else EXIT_RUN_FAILED

    if args.cmd == "checklist":
        try:
            print(_review.render(args.step))
        except KeyError as exc:
            print(f"停下问用户：{exc}")
            return EXIT_NEEDS_USER
        return EXIT_OK

    parser.print_help()
    return EXIT_OK


def _source_keys(root) -> tuple:
    """The materials staged under 00_输入, by the name their outputs will carry."""
    base = Path(root) / _workdir.INPUT_DIR
    if not base.is_dir():
        return ()
    return tuple(sorted(_workdir.source_name(p) for p in base.rglob("*") if p.is_file()))


def _intake_notice(root) -> str:
    """One line saying whether this run is on defaults, so it is never silent."""
    sheet = _metadata.load_sheet(root)
    stored = _metadata.sheet_path(root).is_file()
    if not stored:
        return "投料单：还没有 —— 本次全部用默认（素材名当笔记名、就地放 04_笔记/、按教学素材库写）"
    custom = []
    if sheet["audience"] != _metadata.DEFAULT_AUDIENCE:
        custom.append(f"受众={sheet['audience']}")
    if sheet["deliver_dir"]:
        custom.append(f"交付目录={sheet['deliver_dir']}")
    if sheet["names"]:
        custom.append(f"改名 {len(sheet['names'])} 处")
    return "投料单：" + ("、".join(custom) if custom else "存在但全是默认值")


def _do_intake(args) -> int:
    root = Path(args.workdir)
    try:
        _workdir.ensure(root)
    except OSError as exc:
        print(f"停下问用户：建不出工作目录 —— {exc}")
        return EXIT_NEEDS_USER

    fields = {}
    if args.audience is not None:
        fields["audience"] = args.audience
    if args.deliver_dir is not None:
        fields["deliver_dir"] = args.deliver_dir
    if args.name:
        names = dict(_metadata.load_sheet(root).get("names") or {})
        for item in args.name:
            key, sep, value = item.partition("=")
            if not sep or not key.strip():
                print(f"停下问用户：改名要写成 <素材名>=<想要的名字>，收到的是 {item!r}")
                return EXIT_NEEDS_USER
            names[key.strip()] = value.strip()
        fields["names"] = names

    try:
        if fields:
            _metadata.save_sheet(root, **fields)
        sheet = _metadata.load_sheet(root)
    except (KeyError, OSError) as exc:
        print(f"停下问用户：{exc}")
        return EXIT_NEEDS_USER

    print(_metadata.render_sheet(sheet, source_keys=_source_keys(root)))
    return EXIT_OK


def _do_deliver(args) -> int:
    """Copy the notes to wherever intake said they belong.

    A copy, never a move: the workdir keeps its own record of what was produced,
    so a delivery folder can be re-made or pointed somewhere else later.
    """
    root = Path(args.workdir).resolve()
    notes = sorted(p for p in (root / "04_笔记").glob("*.md") if p.is_file())
    if not notes:
        print("停下问用户：04_笔记/ 里还没有笔记，先让 note 步产出")
        return EXIT_NEEDS_USER

    sheet = _metadata.load_sheet(root)
    target = (sheet.get("deliver_dir") or "").strip()
    if not target:
        print(f"投料单没指定交付目录 —— 笔记就在 `{root / '04_笔记'}`（就地，这是默认）：")
        for note in notes:
            print(f"  - {note.name}")
        return EXIT_OK

    dest = Path(target)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for note in notes:
            shutil.copy2(note, dest / note.name)
            print(f"已交付：{dest / note.name}")
    except OSError as exc:
        print(f"停下问用户：交付目录写不进去 —— {exc}")
        return EXIT_NEEDS_USER
    return EXIT_OK


def _do_run(args) -> int:
    print(_intake_notice(args.workdir))
    try:
        outcome = _pipeline.autorun(
            args.workdir, args.target, kind=args.kind, mode=args.mode, glm=args.glm,
            terms_file=args.terms_file, sites=args.sites, enrich=args.enrich,
            deep_clean=args.deep_clean, force=args.force, album=args.album,
            on_progress=lambda step, status: print(_progress.line(step, status)),
        )
    except OSError as exc:
        print(f"停下问用户：输入读不到 —— {exc}")
        return EXIT_NEEDS_USER

    report = outcome["report"]
    if report is None:
        print(f"停下问用户：{outcome['reason']}")
        return EXIT_NEEDS_USER

    per_material = (outcome.get("per_material_roots")
                    or outcome.get("per_image_roots") or ())
    if per_material:
        # 每份素材一个工作目录：进度单/任务单各自在各自的目录里，不能只报根目录那一个。
        for sub in per_material:
            print(f"总进度单：{Path(sub) / _workdir.PROGRESS_FILE}")
        if not outcome.get("per_image_all_ok"):
            print(f"停下问用户：有一份没跑通 —— 见各目录的{_workdir.FAILURE_FILE}")
            return EXIT_RUN_FAILED
        if outcome.get("needs_agent"):
            print(f"机械步骤已完成（共 {len(per_material)} 份素材）；`{outcome['needs_agent']}` "
                  f"交给子 agent 写，任务单在各自目录：{_pipeline.ASSIGN_FILE}")
            return EXIT_HANDED_OFF
        return EXIT_OK

    print(f"总进度单：{Path(args.workdir) / _workdir.PROGRESS_FILE}")
    if outcome["asked_user"]:
        print(f"停下问用户：{outcome['reason']}")
        return EXIT_NEEDS_USER
    if not report.ok:
        print(f"失败单：{Path(args.workdir) / _workdir.FAILURE_FILE}")
        return EXIT_RUN_FAILED
    if outcome.get("needs_agent"):
        print(f"机械步骤已完成；`{outcome['needs_agent']}` 交给子 agent 写，任务单："
              f"{Path(args.workdir) / _pipeline.ASSIGN_FILE}")
        return EXIT_HANDED_OFF
    return EXIT_OK


def _do_step(args) -> int:
    print(_intake_notice(args.workdir))
    try:
        outcome = _pipeline.step(
            args.workdir, args.step, mode=args.mode, glm=args.glm, enrich=args.enrich,
            deep_clean=args.deep_clean, force=args.force,
            terms_file=args.terms_file, sites=args.sites,
            on_progress=lambda step, status: print(_progress.line(step, status)),
        )
    except (KeyError, OSError) as exc:
        print(f"停下问用户：{exc}")
        return EXIT_NEEDS_USER
    print(f"总进度单：{Path(args.workdir) / _workdir.PROGRESS_FILE}")
    if outcome.stopped_at:
        print(f"失败单：{Path(args.workdir) / _workdir.FAILURE_FILE}")
        return EXIT_RUN_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
