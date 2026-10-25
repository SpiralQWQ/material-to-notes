# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-25

First public release, dual-licensed under AGPL-3.0 plus a commercial license.

### Added

- **`scripts/setup_parts.py`** — fetches the five parts on first use, pinned to a
  known-good commit. `--check` reports what is missing, `--update` re-applies the
  pins, `--mirror` routes through a China mirror.
- **`scripts/setup_engines.py`** — builds one virtual environment per engine and
  records the paths in `.env`, installed per pipeline line rather than all at
  once: `--line document` ~0.1 GB (parsing goes to the MinerU cloud API),
  `--line fetch` ~0.7 GB, `--line clean` ~1.4 GB, `--line media` ~3.7 GB,
  `--all` ~7 GB. Local MinerU is opt-in and marked not recommended; ffmpeg is
  detected but never downloaded, because fetching an executable from the internet
  inside a setup script is a supply-chain risk. The pipeline's own environment is
  the one exception to the venv-per-engine rule: the adapters launch every part
  under `sys.executable`, so its dependencies are installed into that interpreter
  rather than into a venv nothing would read.
- **`pyproject.toml` declares the pipeline's real dependencies.** They used to be
  an empty list, which left `pip install -e .` unable to `import yaml`. A test
  now asserts that this list and `setup_engines.py`'s pipeline package list stay
  the same fact, so the two cannot drift apart again.
- **`scripts/privacy_check.py`** — scans for absolute paths, usernames, the
  internal codename, and keys. Wired into CI. It reads both git and a bounded
  disk walk, so a file nobody has added yet is still scanned, and it works on a
  `git archive` export with no git at all.
- **`docs/UPSTREAM.md`** — where the five parts come from, which commits are
  pinned, under what license, and the two rules that go with bumping a pin.
- **`THIRD_PARTY.md`** — third-party components and licenses. Three of them
  matter: mineru uses a custom (non-OSI) license, pymupdf is
  AGPL-or-Artifex-commercial, and torch carries BSL-1.0 among its licenses.
- **Community files** — `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  issue and pull-request templates, and CI.
- **`.env.example` names every key the pipeline reads**, `MINERU_API_TOKEN`
  included. It used to omit the one token the default document line cannot run
  without, so a user following the README hit "MINERU_API_TOKEN is not set" with
  nothing in the template to copy.
- **`pyproject.toml` carries the metadata the open-source gate names** — license,
  author, readme, keywords, classifiers, and project URLs. No author email on
  purpose: an address in a published file is a spam magnet.
- **README sections the gate names** — Features, FAQ, and Roadmap, in both
  languages. The FAQ leads with "the pipeline stopped at the note step", because
  this project is semi-automatic on purpose and a reader who does not know that
  will assume it is broken.
- **A lint job in CI** (ruff). The rule set is pinned in `pyproject.toml` rather
  than taken from ruff's defaults, which moved between versions and would turn
  CI red on upgrade for reasons unrelated to any commit.
- **`tests/unit/test_open_source_gate.py`** — 45 tests that assert the gate
  itself: both READMEs carry every required section, the table of contents
  matches the headings, the changelog has an Unreleased slot, the license carries
  the standard AGPL markers, CI runs pytest *and* a linter, and no script is
  stranded in the repository root. Every one of those was true on the day it was
  written and is lost to a later edit otherwise.
- **575 tests** (unit + e2e + exhaustive). They need only `pytest` and `pyyaml`:
  the suite reads the parts' files, it does not import them, so no engine has to
  be installed to run it.

### Changed

- **The five parts are fetched, not vendored.** Copying them into this repository
  created two authoritative copies that drift apart silently, and made the
  repository read as an aggregation rather than a project. A lock table plus
  `docs/UPSTREAM.md` replace the copies.
- **The command is `material-to-notes`** — repository name, distribution name,
  CLI command, and import name are one name, matching the other repositories in
  this family.

### Notes

- **This changelog covers this repository only.** Changes to the five parts
  belong to their own changelogs; this repository consumes them through pinned
  commits. The internal development log is not published here.
- **A fresh clone was verified end to end** before this release: clone,
  `setup_parts.py`, `pytest -q` → 575 passed, exit 0, and `ruff check` clean. Four things that made the
  README's three steps fail on a clean machine were found and fixed that way, not
  by reading the code: the pipeline environment installing into a venv nothing
  reads, the empty dependency list above, the missing `.env` key, and a CI step
  whose exit-code guard went red precisely when everything was fine.
- **The suite never reports green without looking.** With `parts/` absent it
  skips everything, prints the command that fixes it, and exits 1 — a run that
  verified nothing must not read as success to anything watching the exit code.
- The document line runs against the MinerU **cloud API** by default. The local
  engine is available (`--mode local`) and deliberately not recommended.
- **The note-writing step is intentionally not automated.** See the README
  section "It is semi-automatic, not automatic" and [`docs/SOP.md`](docs/SOP.md).

## [0.1.0] - 2026-10-07

Internal first version, never released publicly: the contract, adapter,
orchestration, gate, and reporting layers, plus 188 tests. Kept here for
provenance; the useful description of what this project is now is the 1.0.0
entry above.

[Unreleased]: https://github.com/SpiralQWQ/material-to-notes/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/SpiralQWQ/material-to-notes/releases/tag/v1.0.0
[0.1.0]: https://github.com/SpiralQWQ/material-to-notes/releases/tag/v0.1.0
