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
