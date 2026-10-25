"""The open-source gate, as a test.

The prompt this project was formalised against lists hard requirements: a src/
layout, a pyproject with version / dependencies / license / author, a bilingual
README with badges / features / install / usage / configuration / FAQ / roadmap,
a Keep-a-Changelog changelog, a license file, CONTRIBUTING, CODE_OF_CONDUCT, and
CI that runs the tests plus a lint pass.

Every one of those was true on the day it was written and is trivially lost to a
later edit — a section deleted during a rewrite, a CI job dropped to save a
minute. This file turns the list into assertions so the gate survives contact
with future changes instead of being a snapshot in a report nobody re-reads.
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]

# Sections the gate names explicitly. English heading -> Chinese heading; the two
# READMEs are meant to be the same document in two languages, so a section
# missing from either is a gap.
REQUIRED_SECTIONS = {
    "Features": "特性",
    "Installation": "安装",
    "Running it": "跑起来",
    "FAQ": "常见问题",
    "Roadmap": "路线图",
    "License": "许可",
    "Contributing": "贡献",
}

REQUIRED_FILES = [
    "README.md", "README_zh.md",
    "CHANGELOG.md", "CHANGELOG_zh.md",
    "LICENSE", "COMMERCIAL.md", "THIRD_PARTY.md",
    "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md",
    ".env.example", ".gitattributes",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
]


def _headings(text):
    return {m.strip() for m in re.findall(r"^##\s+(.+)$", text, re.M)}


def _anchors(text):
    return re.findall(r"\]\(#([^)]+)\)", text)


def _slug(heading):
    """GitHub's anchor rule: drop inline markup, lowercase, spaces to hyphens,
    and drop punctuation that is not a hyphen or underscore."""
    heading = re.sub(r"`([^`]*)`", r"\1", heading)
    heading = re.sub(r"\*\*|\*|__|_", "", heading)
    heading = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    out = []
    for ch in heading.strip().lower():
        if ch in "-_" or ch.isalnum():
            out.append(ch)
        elif ch.isspace():
            out.append("-")
    return "".join(out)


# --- the file list ---------------------------------------------------------

@pytest.mark.parametrize("rel", REQUIRED_FILES)
def test_the_gate_file_exists(rel):
    assert (REPO / rel).is_file(), f"{rel} is required by the open-source gate"


def test_no_script_is_stranded_in_the_repo_root():
    # "统一 src/ 布局，消灭根目录散落脚本" — a .py at the root is a script that
    # nobody will find, import, or test.
    stray = sorted(p.name for p in REPO.glob("*.py"))
    assert not stray, f"these scripts belong under src/ or scripts/: {stray}"


# --- the bilingual READMEs -------------------------------------------------

@pytest.mark.parametrize("readme,lang", [("README.md", "en"), ("README_zh.md", "zh")])
@pytest.mark.parametrize("en_heading,zh_heading", sorted(REQUIRED_SECTIONS.items()))
def test_both_readmes_carry_every_required_section(readme, lang, en_heading, zh_heading):
    # A section present in English only is a half-translated README, which is
    # what readers of the other language actually notice.
    want = en_heading if lang == "en" else zh_heading
    headings = _headings((REPO / readme).read_text(encoding="utf-8"))
    assert want in headings, (
        f"{readme} is missing the 「{want}」 section — the gate names it"
    )


@pytest.mark.parametrize("readme", ["README.md", "README_zh.md"])
def test_the_table_of_contents_matches_the_headings(readme):
    # A TOC entry that points nowhere is a link that 404s on the same page.
    text = (REPO / readme).read_text(encoding="utf-8")
    anchors = _anchors(text)
    assert anchors, f"{readme} has no table of contents"
    headings = {_slug(h) for h in _headings(text)}
    dead = [a for a in anchors if a not in headings]
    assert not dead, f"{readme} TOC points at missing headings: {dead}"


@pytest.mark.parametrize("readme", ["README.md", "README_zh.md"])
def test_the_readme_carries_badges(readme):
    text = (REPO / readme).read_text(encoding="utf-8")
    assert "img.shields.io" in text, f"{readme} has no badges"


@pytest.mark.parametrize("readme", ["README.md", "README_zh.md"])
def test_the_readme_links_the_other_language(readme):
    # Without the switcher, half the readers never learn the other version exists.
    other = "README_zh.md" if readme == "README.md" else "README.md"
    assert other in (REPO / readme).read_text(encoding="utf-8"), (
        f"{readme} does not link to {other}"
    )


def test_the_readme_ends_with_the_donation_codes():
    # The one piece of personal content the project deliberately keeps: the
    # author's donation QR codes, which the gate's privacy rules exempt.
    for readme in ("README.md", "README_zh.md"):
        text = (REPO / readme).read_text(encoding="utf-8")
        assert "assets/donate_wechat.jpg" in text, f"{readme} lost the WeChat code"
        assert "assets/donate_alipay.jpg" in text, f"{readme} lost the Alipay code"


# --- the changelog ---------------------------------------------------------

@pytest.mark.parametrize("cl", ["CHANGELOG.md", "CHANGELOG_zh.md"])
def test_the_changelog_has_an_unreleased_slot_and_a_release(cl):
    text = (REPO / cl).read_text(encoding="utf-8")
    assert "Keep a Changelog" in text or "Keep-a-Changelog" in text, (
        f"{cl} does not say it follows Keep a Changelog"
    )
    assert re.search(r"^## \[(Unreleased|未发布)\]", text, re.M), (
        f"{cl} has no Unreleased slot"
    )
    assert re.search(r"^## \[\d+\.\d+\.\d+\]", text, re.M), (
        f"{cl} has no released version"
    )


def test_the_two_changelogs_name_the_same_versions():
    # The bilingual pair drifting apart is how one language ends up promising a
    # release the other never mentions.
    en = set(re.findall(r"^## \[(\d+\.\d+\.\d+)\]",
                        (REPO / "CHANGELOG.md").read_text(encoding="utf-8"), re.M))
    zh = set(re.findall(r"^## \[(\d+\.\d+\.\d+)\]",
                        (REPO / "CHANGELOG_zh.md").read_text(encoding="utf-8"), re.M))
    assert en == zh, f"CHANGELOG versions differ: en={sorted(en)} zh={sorted(zh)}"


# --- license ---------------------------------------------------------------

def test_the_license_is_the_affero_gpl():
    text = (REPO / "LICENSE").read_text(encoding="utf-8")
    for marker in ("GNU AFFERO GENERAL PUBLIC LICENSE",
                   "Version 3, 19 November 2007",
                   "TERMS AND CONDITIONS"):
        assert marker in text, f"LICENSE is missing the standard marker {marker!r}"


def test_the_commercial_track_is_documented():
    # A dual license where only one half is written down is not a dual license.
    text = (REPO / "COMMERCIAL.md").read_text(encoding="utf-8")
    assert "AGPL" in text, "COMMERCIAL.md must say what the open half is"
    assert (REPO / "COMMERCIAL.md").stat().st_size > 500, "COMMERCIAL.md is a stub"


# --- CI --------------------------------------------------------------------

def _ci():
    try:
        import yaml
    except ImportError:  # pragma: no cover
        pytest.skip("pyyaml is not installed")
    return yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8"))


def test_ci_runs_the_tests():
    jobs = _ci()["jobs"]
    assert jobs, "ci.yml defines no jobs"
    runs_pytest = any("pytest" in (s.get("run") or "")
                      for j in jobs.values() for s in j["steps"])
    assert runs_pytest, "no CI step runs pytest"


def test_ci_runs_a_linter():
    # Named in the gate's bonus section. A lint job is the cheapest thing in CI
    # and the first thing dropped when someone is in a hurry.
    jobs = _ci()["jobs"]
    lints = [name for name in jobs if "lint" in name.lower()]
    assert lints, (
        f"CI has no lint job; jobs are {sorted(jobs)} — the gate names lint"
    )
    for name in lints:
        steps = jobs[name]["steps"]
        assert any("ruff" in (s.get("run") or "") or "flake8" in (s.get("run") or "")
                   for s in steps), f"the {name!r} job does not actually lint"
