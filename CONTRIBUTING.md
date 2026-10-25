# Contributing to material-to-notes

Thanks for taking the time to contribute!

These are guidelines, not rules — use your best judgment, and feel free to
propose changes to this document in a pull request.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [What should I know before getting started?](#what-should-i-know-before-getting-started)
- [How can I contribute?](#how-can-i-contribute)
  - [Reporting bugs](#reporting-bugs)
  - [Suggesting enhancements](#suggesting-enhancements)
  - [Your first code contribution](#your-first-code-contribution)
  - [Pull requests](#pull-requests)
- [Two rules specific to this project](#two-rules-specific-to-this-project)
  - [Never edit anything under `parts/`](#never-edit-anything-under-parts)
  - [Never commit a machine-specific path or a key](#never-commit-a-machine-specific-path-or-a-key)
- [Styleguides](#styleguides)
  - [Git commit messages](#git-commit-messages)
  - [Python styleguide](#python-styleguide)
  - [Documentation styleguide](#documentation-styleguide)

## Code of Conduct

This project and everyone participating in it is governed by our
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to
uphold this code.

## What should I know before getting started?

`material-to-notes` is an **orchestration layer** over five separate open-source
tools. It contains no parsing, transcription, cleaning, or rewriting capability
of its own — all of that lives in the parts, which are fetched on first use
rather than vendored here.

Skim the [README](README.md) first, then these:

| Read | For |
|---|---|
| [`docs/UPSTREAM.md`](docs/UPSTREAM.md) | where the five parts come from, which commits are pinned, and why |
| [`docs/架构与目录契约.md`](docs/架构与目录契约.md) | architecture and directory layout (in Chinese) |
| [`docs/contracts/接口契约.md`](docs/contracts/接口契约.md) | the exact command each step runs, and where its output lands (in Chinese) |
| [`docs/SOP.md`](docs/SOP.md) | the human/AI working agreement (in Chinese) |

The layers, in dependency order:

- `contract/` — single source of truth for steps, workdir layout, validation
- `steps/` — one thin adapter per part; builds argv and runs it as a subprocess
- `gates/` — machine-checkable acceptance plus the review checklist
- `orchestrate/` — routing, serial runner, resume, failure handling
- `report/` — progress sheet, logs, snapshots
- `cli/` — argument parsing and exit-code mapping

## How can I contribute?

### Reporting bugs

Open an issue with the template provided. Before filing:

- Search existing issues to avoid duplicates.
- Include a **minimal reproduction**: the input (or a snippet), the exact
  command, and the full output.
- State your environment: OS, Python version, and which engines you installed
  (`python scripts/setup_engines.py --check` output is ideal).
- Say whether you ran with `--line document`, `--mode cloud`, and so on — the
  document line has two very different code paths.

### Suggesting enhancements

Open an issue labeled `enhancement`. Describe the problem you are solving and a
concrete sketch of the change. If the change is about *how a note reads*, note
that the writing step is deliberately left to an agent — see
[`docs/SOP.md`](docs/SOP.md).

### Your first code contribution

Good first issues are labeled `good first issue`. If you are unsure where to
start, ask in the issue — maintainers are happy to guide.

### Pull requests

1. Fork the repo and create your branch from `master`.
2. Fetch the parts and confirm the suite is green *before* you change anything:
   ```bash
   python scripts/setup_parts.py
   python -m pytest -q            # 514 passed
   ```
3. Make your change. The test suite needs only `pytest` and `pyyaml` — it reads
   the parts' files, it does not import them, so you do not need the engines.
4. Add tests. A change with no test is a change nobody can trust later.
5. Confirm the privacy scan is clean:
   ```bash
   python scripts/privacy_check.py   # must print "clean" and exit 0
   ```
6. Update `CHANGELOG.md` and `CHANGELOG_zh.md` under `[Unreleased]`.
7. Update the README if behaviour a user would notice changed.
8. Open the PR. Reference any related issue.

---

## Two rules specific to this project

### Never edit anything under `parts/`

`parts/` holds fetched snapshots of the five upstream repositories. It is
gitignored, and editing it produces a copy nobody will ever merge.

If you find a bug in a part:

1. File it against **that part's own repository** (see
   [`docs/UPSTREAM.md`](docs/UPSTREAM.md) for the links).
2. Once the fix lands upstream, bump the pinned commit in
   `scripts/setup_parts.py` and run the end-to-end check in
   [`docs/UPSTREAM.md`](docs/UPSTREAM.md) §三 before committing.

Bumping a pin is not a formality: the adapters hard-code the parts' entry
points (`python -m dtmd`, `app/crawl_all.py`), and `orchestrate/spec.py` reads
the note style spec and gate labels straight out of `md-rewrite-engine`. A part
that renames a module or rewrites its spec breaks the pipeline **silently**.

### Never commit a machine-specific path or a key

This repository is public. Absolute paths, your username, the internal project
codename, and API keys are all out. The scan in `scripts/privacy_check.py`
checks for them and exits non-zero when it finds one:

```bash
python scripts/privacy_check.py
```text
It is also wired into CI, so a PR that leaks will fail there. Two things it
deliberately does *not* scan: `runs/` (your own material) and `temp/` (scratch
and evidence sheets, which legitimately quote the source repo's path). Anything
you mean to keep goes in the repo, not in those two.

---

## Styleguides

### Git commit messages

- Conventional commits prefix: `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`,
  `test:`, `chore:`.
- Subject line ≤ 72 chars, imperative mood ("add", not "added").
- The body explains the *why*, not just the *what*. If the reason is not worth
  writing down, the change is probably not worth making.

### Python styleguide

- Python 3.10+, follow [PEP 8](https://peps.python.org/pep-0008/).
- English docstrings and comments, matching the rest of `src/`.
- Keep functions small and single-purpose; no magic numbers — use named
  constants.
- Resolve paths through `contract/runner.py`, never by hand. `repo_root()` and
  `part_tool()` exist so a script behaves the same wherever it is invoked from.
- A step that fails is *reported*, never raised: the pipeline has to be able to
  say what went wrong and stop, not crash.

### Documentation styleguide

- [Keep a Changelog](https://keepachangelog.com/) format for the changelogs.
- Keep the English and Chinese README in sync when you change either.
- Tables over prose for structured information (files, env vars, commands,
  sizes).
- State measured numbers as measured. If you estimated, say so. A README that
  promises "installs in 30 seconds" when it takes forty minutes costs more trust
  than it buys convenience.
