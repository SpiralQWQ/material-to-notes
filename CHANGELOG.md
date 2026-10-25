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
  pins, `--force` re-clones, `--mirror` routes through a China mirror (the
  `gh-proxy` preset was verified on 2026-10-25; presets go stale, so any full URL
  prefix works too).
- **`scripts/setup_engines.py`** — builds one virtual environment per engine and
  records the paths in `.env`. Installs per pipeline line rather than all at once:
  `--line document` is ~0.1 GB (parsing goes to the MinerU cloud API),
  `--line fetch` ~0.7 GB, `--line clean` ~1.4 GB, `--line media` ~3.7 GB,
  `--all` ~7 GB. Local MinerU is deliberately opt-in via `--line document-local`
  and marked not recommended. ffmpeg is detected but never downloaded — fetching
  an executable from the internet inside a setup script is a supply-chain risk.
- **`docs/UPSTREAM.md`** — where the five parts come from, which commits are
  pinned, under what license, and the two rules that go with bumping a pin.
- **`THIRD_PARTY.md`** — third-party components and licenses, and three things
  that matter: mineru uses a custom (non-OSI) license, pymupdf is
  AGPL-or-Artifex-commercial, and torch carries BSL-1.0 among its licenses.
- **Community files** — `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  issue and pull-request templates, and a CI workflow that fetches the parts,
  runs the suite, and runs the privacy scan.
- **`tests/conftest.py`** — a preflight that turns "the parts were never fetched"
  from 39 `FileNotFoundError`s into one skip that names the command to run, and
  forces a non-zero exit so a run that verified nothing is never reported green.
- **Test suite: 514 tests** (unit + e2e + exhaustive). It needs only `pytest` and
  `pyyaml` — it reads the parts' files, it does not import them, so none of the
  engines are required to run it.

### Changed

- **The five parts are fetched, not vendored.** Copying them into this repository
  created two authoritative copies that drift apart silently, and made the
  repository read as an aggregation rather than a project. The lock table in
  `setup_parts.py` plus `docs/UPSTREAM.md` replace the copies.
- **`privacy_check.py` no longer has two blind spots that made it lie.** It used
  to build its file list from `git ls-files` alone, so a file nobody had added
  yet — exactly where an unnoticed leak lives — was never scanned while the
  script still printed `clean`. It now uses git *and* a bounded disk walk, which
  also makes it work on a `git archive` export with no git at all. It also no
  longer dies on a GBK console: the report quotes file contents verbatim, and a
  character the console could not encode used to raise `UnicodeEncodeError` and
  exit non-zero for a reason unrelated to privacy.
- **Its pattern set is wider.** It checked four shapes and missed the internal
  project codename, the local directory tree, and a user profile on any drive
  other than `C:`. Those are now covered, and the absolute-path rule requires two
  path components so an escaped `\n` inside a Python string literal is not
  reported as a path.
- **The command is `material-to-notes`.** The repository, the distribution name,
  the CLI command, and the import name are one name, matching the other
  repositories in this family.

### Fixed

- Gate messages and dispatch sheets told the user to run `pipeline toc`,
  `pipeline step`, `pipeline gate`, `pipeline run`, and `pipeline checklist` —
  commands that no longer exist after the rename. Every one of those strings is
  now the real command name.
- `argparse` still reported the program as `pipeline` in usage text and
  `--version`.
- `write_env` in `setup_engines.py` edits `.env`, which holds real API keys. It
  now edits lines in place and appends only genuinely new keys, rather than
  rewriting the file from what it parsed — the latter drops comments and any key
  it did not recognise, which is how a person loses a key they did not back up.
- The absolute-path rule used to match `Di` + `sk-` inside a GitHub repository
  name such as `Acronis-Disk-Director-...`, filling the report with hits nobody
  could clear. It now requires a word boundary.

### Notes

- **This changelog is scoped to this repository.** It does not record changes made
  to the five parts: those belong to their own changelogs, and this repository
  consumes them through pinned commits. The detailed internal development log,
  including per-part fixes and the 51 rounds of acceptance that produced them,
  stays in the source project and is not published here.
- The document line runs against the MinerU **cloud API** by default. The local
  engine is available (`--mode local`) and deliberately not recommended.
- The note-writing step is intentionally not automated. See the README section
  "It is semi-automatic, not automatic" and [`docs/SOP.md`](docs/SOP.md).

## [0.1.0] - 2026-10-07

First version: an orchestration layer chaining five open-source tools into one
material to study-notes pipeline.

### Added

- **Contract layer** `contract/` — step definitions (single source of truth),
  workdir layout, output validation, external command runner.
- **Adapter layer** `steps/` — one thin adapter per part (wkc / dtmd / m2m / tce / mre).
- **Orchestration layer** `orchestrate/` — workspace init, routing, serial runner,
  resume, failure handling, assembly.
- **Gate layer** `gates/` — machine gates that keep their raw evidence, plus the
  review checklist (with three global items: semantic fidelity, hallucination, cost).
- **Reporting layer** `report/` — progress sheet, JSONL run logs.
- **CLI** `cli/` — `init` / `route` / `gate` / `checklist`.
- **Documentation** `docs/` — architecture and directory contract, exhaustive test
  plan, SOP.
- **Tests** — unit + e2e + exhaustive, 188 in total.

### Notes

- The five parts stay independent; this tool uses them only through file hand-off
  and command-line invocation.
- Running against the real parts needs a local environment; what was not covered
  at the time is recorded in the source project, not here.

[Unreleased]: https://github.com/SpiralQWQ/material-to-notes/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/SpiralQWQ/material-to-notes/releases/tag/v1.0.0
[0.1.0]: https://github.com/SpiralQWQ/material-to-notes/releases/tag/v0.1.0
