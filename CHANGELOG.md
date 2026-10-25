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
  inside a setup script is a supply-chain risk.
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
- **524 tests** (unit + e2e + exhaustive). They need only `pytest` and `pyyaml`:
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
