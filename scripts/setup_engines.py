#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the Python environments this pipeline's parts need, and record them.

Run from anywhere. Builds one virtual environment per engine under
``.venvs/`` and writes the resolved paths into ``.env``.

    python scripts/setup_engines.py                    # the pipeline env only
    python scripts/setup_engines.py --line document     # + what the doc line needs
    python scripts/setup_engines.py --line media        # + what the media line needs
    python scripts/setup_engines.py --all               # everything (5-8 GB)
    python scripts/setup_engines.py --check             # report only, install nothing
    python scripts/setup_engines.py --only asr ffmpeg   # named engines

Why one environment per engine, and not one big one: the engines' dependencies
fight each other. ``torch`` and ``funasr`` pin a numpy that ``opencv`` rejects,
``crawl4ai`` wants playwright, ``presidio`` wants spaCy with a downloaded model.
A single environment resolves to a version set that satisfies nobody. The parts
are built for this — each heavy engine is invoked through a bridge script whose
interpreter comes from an env var (``ASR_PY``, ``CRAWL4AI_PY``, ...), so a
separate venv is the design, not a workaround.

The pipeline's own environment is the exception: all five parts run under the
interpreter that drives them (the adapters use ``sys.executable``), so their
light dependencies belong there.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Sizes are what this project measured on Windows; they are estimates, and the
# truth depends on your platform and whether a wheel is cached.
GB = 1024 * 1024 * 1024


@dataclass(frozen=True)
class Engine:
    """One installable environment: what it is for and what goes in it."""

    key: str
    env_var: str          # written into .env; "" for the pipeline env itself
    packages: tuple       # pip install targets; empty for a binary
    line: str             # which pipeline line needs it
    note: str = ""
    size_gb: float = 0.0
    kind: str = "venv"    # "venv" or "binary"
    recommended: bool = True
    extra: tuple = ()     # shell commands to run inside the venv afterwards


# The pipeline's own environment. All five parts are driven by the interpreter
# that runs the orchestrator, so their light dependencies live here. The heavy
# ones deliberately do not: they belong to the engines below.
PIPELINE = Engine(
    key="main",
    env_var="",
    packages=(
        "PyYAML>=6.0", "requests>=2.31", "python-dotenv>=1.0",
        "sentencex>=1.0.0", "jsonschema>=4.26.0",
        # dtmd imports these lazily inside its quality gates and its slicer.
        "pymupdf>=1.24.0", "mistune>=3.0.0", "pikepdf>=10.0.0",
    ),
    line="all",
    note="主管线环境。五个零件都由驱动编排层的那个解释器运行，所以它们的轻依赖放这里。",
    size_gb=0.1,
)

ENGINES = (
    PIPELINE,
    Engine("asr", "ASR_PY",
           ("funasr>=1.0", "torch>=2.0", "soundfile>=0.12", "numpy>=1.24",
            "pypinyin>=0.51", "rapidfuzz>=3.0"),
           "media", "语音转写。最大的一块，torch 是大头。", size_gb=3.0),
    Engine("ocr", "OCR_PY",
           ("rapidocr-onnxruntime>=1.3", "opencv-python>=4.8", "numpy>=1.24"),
           "media", "图片文字识别。", size_gb=0.6),
    Engine("crawl4ai", "CRAWL4AI_PY",
           ("crawl4ai>=0.9",),
           "fetch", "网页抓取。装完还要下浏览器，见 extra。", size_gb=0.5,
           extra=(("playwright", "install", "chromium"),)),
    Engine("ytdlp", "DD_YTDLP", ("yt-dlp",), "fetch",
           "视频下载。", size_gb=0.05),
    Engine("trafilatura", "TRAFILATURA_PY", ("trafilatura>=2.2",), "clean",
           "网页正文提取。", size_gb=0.1),
    Engine("presidio", "PRESIDIO_PY",
           ("presidio-analyzer>=2.2", "spacy>=3.8"),
           "clean", "个人信息脱敏。装完还要下 spaCy 模型，见 extra。", size_gb=1.2,
           extra=(("spacy", "download", "en_core_web_lg"),)),
    Engine("pix2text", "DTM_PIX2TEXT_ENV", ("pix2text",), "document",
           "公式 OCR。文档线走云端时不需要。", size_gb=1.5),
    # Local MinerU is the one thing this project recommends against: the doc
    # line is built for the cloud API, and the local engine is gigabytes of
    # models for the same job. It stays installable, and clearly marked.
    Engine("mineru-local", "", ("mineru[all]>=2.0.0",), "document",
           "本地 MinerU。不推荐——文档线默认走云端 API，这个只为 --mode local 准备。",
           size_gb=3.0, recommended=False),
)

# What each line actually needs. The document line is cloud-only on purpose:
# MinerU's API does the parsing, so the local engine (gigabytes of models) and
# pix2text are opt-in, not part of the default. That is this project's
# recommendation, and the installer should not quietly override it.
LINES = {
    "document": ("main",),
    "document-local": ("main", "pix2text", "mineru-local"),
    "media": ("main", "asr", "ocr"),
    "fetch": ("main", "crawl4ai", "ytdlp"),
    "clean": ("main", "trafilatura", "presidio"),
    "all": tuple(e.key for e in ENGINES if e.recommended),
}

# ffmpeg is a binary, not a package: it is installed system-wide and pointed at
# with FFMPEG. It is deliberately not downloaded here — fetching an executable
# from the internet inside a setup script is a supply-chain risk, and the
# supported ways to get it (winget, a package manager, a build you chose) all
# leave the user in control of what lands on their machine.
FFMPEG = Engine("ffmpeg", "FFMPEG", (), "media",
                "音视频处理。系统级二进制，不随脚本下载。", kind="binary")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def venvs_root() -> Path:
    return repo_root() / ".venvs"


def venv_python(venv: Path) -> Path:
    """The interpreter inside a venv, on either platform."""
    win = venv / "Scripts" / "python.exe"
    return win if win.is_file() else venv / "bin" / "python"


def _run(argv, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _have_python() -> bool:
    return shutil.which("python") is not None or shutil.which("python3") is not None


def _python_exe() -> str:
    return sys.executable or "python"


def read_env(root=None) -> dict:
    """Current .env as a dict. Missing file is an empty dict, not an error."""
    path = (Path(root) if root is not None else repo_root()) / ".env"
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def write_env(values: dict, root=None) -> Path:
    """Merge ``values`` into .env, keeping every other line and comment.

    Rewriting the file from the parsed dict would drop the comments that tell
    the next reader what each variable is for — and this file holds real API
    keys, so "rewrite it from what I parsed" is how a person loses a key they
    did not back up. Existing lines are edited in place; only genuinely new
    keys are appended.
    """
    path = (Path(root) if root is not None else repo_root()) / ".env"
    lines = (path.read_text(encoding="utf-8", errors="ignore").splitlines()
             if path.is_file() else [])
    remaining = dict(values)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    for key, value in remaining.items():
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def engine_status(engine: Engine) -> str:
    """Whether an engine is ready: its venv exists and holds an interpreter."""
    if engine.kind == "binary":
        configured = read_env().get(engine.env_var, "")
        if configured and Path(configured).is_file():
            return "ok"
        found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        return "ok (on PATH)" if found else "MISSING"
    venv = venvs_root() / engine.key
    if not venv_python(venv).is_file():
        return "MISSING"
    configured = read_env().get(engine.env_var, "")
    if engine.env_var and not configured:
        return "venv exists, .env not set"
    return "ok"


def _create_venv(engine: Engine) -> str:
    venv = venvs_root() / engine.key
    venvs_root().mkdir(parents=True, exist_ok=True)
    if venv_python(venv).is_file():
        return ""  # already there; --force is what re-creates it
    out = _run([_python_exe(), "-m", "venv", str(venv)])
    if out.returncode != 0:
        return "venv creation failed: " + (out.stderr or out.stdout).strip()[:160]
    return ""


def _pip_install(engine: Engine, py: Path) -> str:
    if not engine.packages:
        return ""
    out = _run([str(py), "-m", "pip", "install", "--quiet", *engine.packages])
    if out.returncode != 0:
        tail = (out.stderr or out.stdout).strip().splitlines()
        return "pip install failed: " + (tail[-1] if tail else "?")[:160]
    return ""


def _run_extra(engine: Engine, py: Path) -> list:
    """Post-install steps (playwright browser, spaCy model). Returns failures."""
    failures = []
    for cmd in engine.extra:
        out = _run([str(py), "-m", *cmd])
        if out.returncode != 0:
            tail = (out.stderr or out.stdout).strip().splitlines()
            failures.append(f"{' '.join(cmd)} failed: " + (tail[-1] if tail else "?")[:140])
    return failures


def install(engine: Engine, force: bool = False) -> tuple:
    """Install one engine. Returns (ok, message)."""
    if engine.kind == "binary":
        return _install_ffmpeg()

    venv = venvs_root() / engine.key
    if force and venv.is_dir():
        shutil.rmtree(venv)

    reason = _create_venv(engine)
    if reason:
        return False, reason
    py = venv_python(venv)

    reason = _pip_install(engine, py)
    if reason:
        return False, reason
    failures = _run_extra(engine, py)
    if failures:
        return False, "; ".join(failures)

    if engine.env_var:
        write_env({engine.env_var: str(py)})
    return True, str(py)


def _install_ffmpeg() -> tuple:
    """ffmpeg cannot be pip-installed, so detect it and explain the rest."""
    for name in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(name)
        if found:
            write_env({"FFMPEG": found})
            return True, f"found on PATH -> {found}"
    return False, ("ffmpeg is a system binary and is not downloaded by this "
                   "script on purpose. Install it (Windows: winget install "
                   "Gyan.FFmpeg), then either put it on PATH or set FFMPEG in .env")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Create the Python environments the parts need.")
    parser.add_argument("--check", action="store_true",
                        help="report what is ready; install nothing")
    parser.add_argument("--line", choices=sorted(LINES),
                        help="install what one pipeline line needs")
    parser.add_argument("--only", nargs="+", metavar="ENGINE",
                        help="named engines: " + ", ".join(
                            e.key for e in ENGINES) + ", ffmpeg")
    parser.add_argument("--all", action="store_true",
                        help="install every engine (5-8 GB, 20-40 minutes)")
    parser.add_argument("--force", action="store_true",
                        help="discard existing venvs and rebuild them")
    args = parser.parse_args(argv)

    if not _have_python():
        print("python was not found on PATH.")
        print("Install Python 3.10 or newer first: https://www.python.org/downloads/")
        return 2

    by_key = {e.key: e for e in ENGINES}
    if args.check:
        env = read_env()
        print(f"pipeline python: {_python_exe()}")
        print(f"venvs root:      {venvs_root()}")
        print(f".env:            {'present' if env else 'not created yet'}"
              f" ({len(env)} variable(s))")
        for engine in ENGINES:
            mark = "ok  " if engine_status(engine).startswith("ok") else "MISS"
            size = f"~{engine.size_gb:.1f} GB" if engine.size_gb else "small"
            flag = "" if engine.recommended else "  [not recommended]"
            print(f"  {mark} {engine.key:<14} {engine.line:<9} {size:<10}"
                  f"{engine_status(engine)}{flag}")
        print(f"  {'ok  ' if engine_status(FFMPEG).startswith('ok') else 'MISS'} "
              f"{'ffmpeg':<14} {'media':<9} {'binary':<10}{engine_status(FFMPEG)}")
        return 0

    if args.all:
        keys = list(LINES["all"]) + ["ffmpeg"]
    elif args.line:
        keys = list(LINES[args.line]) + ["ffmpeg"]
    elif args.only:
        keys = list(args.only)
        unknown = [k for k in keys if k not in by_key and k != "ffmpeg"]
        if unknown:
            print(f"unknown engine(s): {', '.join(unknown)}")
            print("known: " + ", ".join(list(by_key) + ["ffmpeg"]))
            return 2
    else:
        keys = ["main"]

    todo = [by_key[k] if k in by_key else FFMPEG for k in keys]
    total = sum(e.size_gb for e in todo)
    print(f"installing {len(todo)} environment(s)"
          + (f", roughly {total:.1f} GB" if total > 0.2 else ""))
    if total > 1.0:
        print("this will take a while — torch is the bulk of it.\n")

    failures = []
    for engine in todo:
        print(f"[{engine.key}] {engine.note or engine.line}")
        ok, detail = install(engine, force=args.force)
        if ok:
            print(f"  ok -> {detail}\n")
        else:
            print(f"  FAILED: {detail}\n")
            failures.append(engine.key)

    if failures:
        print(f"{len(failures)} of {len(todo)} failed: {', '.join(failures)}")
        return 1

    print("done. Next:")
    print("  python scripts/setup_parts.py      # fetch the five parts")
    print("  python -m pytest -q                # 514 tests, all green")
    if "main" in keys and len(keys) == 1:
        print("\nOnly the pipeline environment was installed. To run a line, add")
        print("what it needs — sizes are what this project measured on Windows:")
        for line, members in LINES.items():
            if line in ("all", "document-local"):
                continue
            extra = [k for k in members if k != "main"]
            gb = sum(by_key[k].size_gb for k in extra)
            print(f"  --line {line:<9} + {', '.join(extra):<24} ~{gb:.1f} GB")
        print("  --all                  everything recommended, ~5 GB")
        print("  --line document-local  local MinerU instead of the cloud API")
        print("                          (3 GB of models this project does not")
        print("                          recommend; the cloud API does the same job)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
