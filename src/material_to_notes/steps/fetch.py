"""Adapter for wkc (web-knowledge-crawler): fetch raw material by terms or links.

wkc writes into ``--out-dir/{term}/{type}/{site}/`` and never parses, so this
adapter only has to point --out-dir at the workdir step dir.
"""

from __future__ import annotations

import os
import sys

from material_to_notes.contract import runner as R
from material_to_notes.contract import steps as _steps
from material_to_notes.contract import workdir as W

TOOL = "wkc"
ENV_KEY = "WKC_DIR"
PART = "web-knowledge-crawler"
SCRIPT_REL = os.path.join("app", "crawl_all.py")


def build_command(tool_path, *, out_dir, terms="", sites="", python=None) -> list:
    """argv for one crawl run."""
    argv = [python or sys.executable, os.path.join(str(tool_path), SCRIPT_REL),
            "--out-dir", str(out_dir)]
    if terms:
        argv += ["--terms", str(terms)]
    if sites:
        argv += ["--sites", str(sites)]
    return argv


def run(root, *, terms="", sites="", env=None, timeout=None, runner=None, python=None):
    step = _steps.get_step("fetch")
    argv = build_command(
        R.part_tool(ENV_KEY, PART, env), out_dir=W.step_dir(root, step),
        terms=terms, sites=sites, python=python,
    )
    return R.execute(step, argv, root, timeout=timeout, runner=runner)
