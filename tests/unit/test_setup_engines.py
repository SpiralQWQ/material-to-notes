"""Tests for scripts/setup_engines.py — the .env merge and the line choices.

Two things are worth guarding here. ``write_env`` edits a file that holds real
API keys, so "rewrite it from what I parsed" is how a person loses a key they
did not back up. And the line definitions encode a decision the project made
deliberately — the document line runs on MinerU's cloud API, so the local
engine must stay opt-in rather than being quietly pulled in by ``--all``.
"""

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import setup_engines as S  # noqa: E402


def test_write_env_creates_the_file_when_missing(tmp_path):
    S.write_env({"ASR_PY": "/x/python.exe"}, root=tmp_path)
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "ASR_PY=/x/python.exe" in text


def test_write_env_keeps_comments_and_untouched_keys(tmp_path):
    # The comments in .env are what tell the next reader what each variable is
    # for. Dropping them to rewrite the file is not an improvement.
    (tmp_path / ".env").write_text(
        "# 引擎路径\nASR_PY=/old/python.exe\n\n# 数据根\nKC_BASE=/data\n",
        encoding="utf-8")

    S.write_env({"ASR_PY": "/new/python.exe"}, root=tmp_path)
    text = (tmp_path / ".env").read_text(encoding="utf-8")

    assert "ASR_PY=/new/python.exe" in text
    assert "KC_BASE=/data" in text, "an unrelated key must survive"
    assert "# 引擎路径" in text and "# 数据根" in text, "comments must survive"


def test_write_env_replaces_rather_than_duplicates(tmp_path):
    (tmp_path / ".env").write_text("ASR_PY=/old\n", encoding="utf-8")
    S.write_env({"ASR_PY": "/new"}, root=tmp_path)
    S.write_env({"ASR_PY": "/newer"}, root=tmp_path)
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert text.count("ASR_PY=") == 1, f"the key was duplicated:\n{text}"
    assert "ASR_PY=/newer" in text


def test_write_env_appends_a_new_key_after_a_blank_line(tmp_path):
    (tmp_path / ".env").write_text("ASR_PY=/old\n", encoding="utf-8")
    S.write_env({"OCR_PY": "/ocr"}, root=tmp_path)
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "ASR_PY=/old" in text and "OCR_PY=/ocr" in text
    assert "\n\nOCR_PY=" in text, "a new key should not be glued to the last line"


def test_read_env_missing_file_is_empty(tmp_path):
    assert S.read_env(root=tmp_path) == {}


def test_read_env_ignores_comments_and_blanks(tmp_path):
    (tmp_path / ".env").write_text("# c\n\nA=1\nB=\n", encoding="utf-8")
    assert S.read_env(root=tmp_path) == {"A": "1", "B": ""}


# --- the cloud-first decision, pinned --------------------------------------

def test_the_document_line_does_not_pull_the_local_engine():
    # The document line is built for MinerU's cloud API. Bundling 3 GB of local
    # models into the default would quietly override that recommendation.
    assert S.LINES["document"] == ("main",)
    assert "mineru-local" not in S.LINES["document"]
    assert "pix2text" not in S.LINES["document"]


def test_all_excludes_everything_not_recommended():
    not_recommended = [e.key for e in S.ENGINES if not e.recommended]
    assert not_recommended, "something must be marked not recommended"
    for key in not_recommended:
        assert key not in S.LINES["all"], (
            f"{key} is not recommended but --all installs it anyway")


def test_the_local_variant_is_opt_in_and_named_for_what_it_is():
    assert "mineru-local" in S.LINES["document-local"]
    assert "document-local" in S.LINES, "the opt-in path must be reachable"


def test_every_engine_env_var_is_distinct():
    # Two engines writing the same variable would silently overwrite each other.
    used = [e.env_var for e in S.ENGINES if e.env_var]
    assert len(used) == len(set(used)), f"duplicate env vars: {used}"


def test_every_engine_key_is_distinct():
    keys = [e.key for e in S.ENGINES] + [S.FFMPEG.key]
    assert len(keys) == len(set(keys)), f"duplicate keys: {keys}"


# --- the pipeline env must land in the interpreter that drives the parts ----
#
# The bug this pins: `main` used to be modelled as a venv engine, so the default
# `setup_engines.py` built `.venvs/main` and installed the pipeline's own
# dependencies into it — a venv nothing ever uses. The adapters run every part
# under `sys.executable`, so a separate venv leaves the driving interpreter
# without `yaml` and the pipeline dies on `import yaml` while the setup script
# reports success and tells the user to run the tests.

def test_the_pipeline_env_is_not_a_throwaway_venv():
    assert S.PIPELINE.kind == "interpreter", (
        "the parts run under sys.executable, so the pipeline's own dependencies "
        "must be installed into that interpreter — a venv of their own would be "
        "built and never used"
    )


def test_installing_the_pipeline_env_creates_no_venv(monkeypatch):
    # Proven empirically: with the old behaviour a bare interpreter ran the
    # suite into 10 collection errors (`No module named 'yaml'`) and the CLI
    # could not even print --version, while setup_engines.py reported success
    # and told the user to run the tests.
    calls = []

    class FakeRun:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(argv, cwd=None):
        calls.append(list(argv))
        return FakeRun()

    monkeypatch.setattr(S, "_run", fake_run)

    ok, detail = S.install(S.PIPELINE)
    assert ok, detail
    assert calls, "the interpreter install must actually invoke pip"
    assert any("install" in argv for argv in calls), (
        f"the pipeline env must pip-install its packages, got {calls}"
    )

    # Not "no argv contains the substring venv". The first version of this
    # assertion said exactly that and failed on a checkout whose interpreter
    # lived at .../ciprobe/venv/Scripts/python.exe — which is where anyone who
    # follows the instructions puts one. What must not happen is *creating* a
    # venv, so check the invocation, not the path spelling.
    for argv in calls:
        assert argv[1:3] != ["-m", "venv"], f"must not create a venv: {argv}"
        assert "venv" not in argv[1:], f"no bare 'venv' argument: {argv}"


def test_the_pipeline_env_status_probes_the_interpreter(monkeypatch):
    # engine_status() must not consult `.venvs/main` — that directory does not
    # exist under the fixed design, so a venv-shaped check would report MISSING
    # on a working installation.
    #
    # Asserted at the mechanism level, deliberately. The first version asserted
    # that the ambient interpreter reads "ok", which is true on a developer
    # machine and false in CI, where only pytest and pyyaml are installed on
    # purpose. A test whose result depends on what happens to be pip-installed
    # is a test that goes red somewhere you are not looking.
    calls = []

    class Ok:
        returncode = 0
        stderr = ""
        stdout = ""

    class Fail:
        returncode = 1
        stderr = "ModuleNotFoundError: No module named 'requests'"
        stdout = ""

    def consult_venv(*a, **k):
        raise AssertionError("the interpreter probe must not consult the venv dir")

    monkeypatch.setattr(S, "venvs_root", consult_venv)
    monkeypatch.setattr(S, "_run",
                        lambda argv, cwd=None: (calls.append(list(argv)), Ok())[1])
    assert S.engine_status(S.PIPELINE) == "ok"

    monkeypatch.setattr(S, "_run",
                        lambda argv, cwd=None: (calls.append(list(argv)), Fail())[1])
    assert "missing" in S.engine_status(S.PIPELINE)

    assert calls, "the probe must actually run something"
    for argv in calls:
        assert argv[1] == "-c", f"the probe must import in a subprocess: {argv}"
        assert any(a.startswith("import ") for a in argv), f"probe must import: {argv}"


def test_no_test_needs_a_pipeline_dependency_at_import_time():
    # CI installs pytest and pyyaml and nothing else, because the suite reads
    # the parts' files rather than importing them. A test that imports one of
    # pyproject's six dependencies at module level passes on a developer
    # machine and fails in CI — found the hard way when two of these tests
    # went red in exactly that environment.
    import re
    heavy = {p.split(">=")[0].split(">")[0].split("=")[0].split("<")[0].strip().lower()
             for p in S.PIPELINE.packages}
    # yaml is the one CI installs, so it is not in this set.
    heavy.discard("pyyaml")
    offenders = []
    for path in sorted((REPO / "tests").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.split(chr(10)), 1):
            m = re.match(r"^\s*(?:import|from)\s+([a-zA-Z_][\w.]*)", line)
            if not m:
                continue
            top = m.group(1).split(".")[0].lower()
            if top in heavy:
                offenders.append(f"{path.relative_to(REPO)}:{i} imports {top}")
    assert not offenders, (
        "these tests import a pipeline dependency that CI does not install:"
        + chr(10).join(offenders)
    )



def _pyproject():
    """pyproject.toml parsed as TOML, not as text.

    The regex version of this test could not tell the difference between
    ``dependencies`` living under ``[project]`` and the same array sitting under
    ``[project.urls]`` -- a TOML table swallows every key beneath it until the
    next header. That mistake parses cleanly, breaks packaging, and leaves the
    test green. Reading it as TOML is the only way to assert the structure.
    """
    try:
        import tomllib
    except ImportError:  # pragma: no cover - Python < 3.11
        pytest.skip("tomllib needs Python 3.11+")
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_declares_what_the_pipeline_env_installs():
    # The coupling that let this ship: pyproject.toml said `dependencies = []`,
    # so `pip install -e .` installed nothing the pipeline imports. The two
    # lists are the same fact and must not drift apart again.
    import re
    project = _pyproject()["project"]
    declared = {re.split(r"[><=~\s]", d.strip().lower())[0]
                for d in project.get("dependencies", [])}
    names = {re.split(r"[><=~\s]", p.strip().lower())[0]
             for p in S.PIPELINE.packages}
    missing = names - declared
    assert not missing, (
        f"pyproject.toml does not declare {sorted(missing)} - `pip install -e .` "
        "would leave the pipeline unable to import them"
    )


def test_pyproject_metadata_is_complete():
    # The open-source gate asks for version / dependencies / license / author.
    # All four were missing or empty at some point; this pins them.
    project = _pyproject()["project"]
    assert project.get("version"), "version is required"
    assert project.get("dependencies"), "dependencies must not be an empty list"
    assert project.get("license"), "license is required by the open-source gate"
    assert project.get("authors"), "authors is required by the open-source gate"
    assert project.get("readme"), "readme is what PyPI renders on the project page"
    assert not any("@" in str(a) for a in project["authors"]), (
        "an author email in a published file is a spam magnet"
    )


def test_the_command_entry_point_survives():
    # `pip install -e .` is what puts `material-to-notes` on PATH, and the
    # README's quick-start tells the user to run it. A pyproject edit that
    # drops [project.scripts] takes the command away without failing anything.
    project = _pyproject()["project"]
    scripts = project.get("scripts", {})
    assert "material-to-notes" in scripts, (
        f"the CLI entry point is gone; scripts = {scripts}"
    )
    assert scripts["material-to-notes"].endswith(":main")


def test_urls_are_urls_and_nothing_else():
    # A TOML table swallows every key under it. Putting `dependencies` after
    # [project.urls] turns it into a URL: the file still parses, packaging
    # breaks, and a text-level test stays green.
    project = _pyproject()["project"]
    urls = project.get("urls", {})
    assert urls, "project.urls is what GitHub and PyPI link back to"
    for key, value in urls.items():
        assert isinstance(value, str), f"{key} must be a string, got {value!r}"
        assert value.startswith("http"), f"{key} is not a URL: {value!r}"
    assert "dependencies" not in urls, (
        "dependencies ended up inside [project.urls] - move it above that header"
    )



def test_no_dead_weight_in_the_pipeline_env():
    # sentencex and jsonschema were installed and imported by nobody. The
    # rewrite engine even documents a zero-dependency rule that says it does
    # not use jsonschema, so installing it was pure download cost.
    names = [p.split(">=")[0].split(">")[0].split("=")[0].split("<")[0].strip().lower()
             for p in S.PIPELINE.packages]
    for dead in ("sentencex", "jsonschema"):
        assert dead not in names, f"{dead} has no importer anywhere in the repo"
