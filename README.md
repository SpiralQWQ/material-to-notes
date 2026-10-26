# material-to-notes

<p align="center">
  <kbd>English</kbd> · <kbd><a href="README_zh.md">简体中文</a></kbd>
</p>

<p align="center">
  <a href="https://github.com/SpiralQWQ/material-to-notes/releases"><img src="https://img.shields.io/github/v/tag/SpiralQWQ/material-to-notes?label=version" alt="version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL%203.0%20%7C%20Commercial-blue" alt="license"></a>
  <a href="https://github.com/SpiralQWQ/material-to-notes/stargazers"><img src="https://img.shields.io/github/stars/SpiralQWQ/material-to-notes?style=social" alt="stars"></a>
</p>

## Table of Contents

- [Features](#features)
- [It is semi-automatic, not automatic](#it-is-semi-automatic-not-automatic)
- [Installation](#installation)
- [Running it](#running-it)
- [FAQ](#faq)
- [Roadmap](#roadmap)
- [Documentation](#documentation)
- [License](#license)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [Support](#support)

---

An **orchestration layer** that chains five open-source tools into one
material to study-notes pipeline.

| Part | What it does |
|---|---|
| [web-knowledge-crawler](https://github.com/SpiralQWQ/web-knowledge-crawler) | fetch material (crawl by terms + sites) |
| [document-to-markdown](https://github.com/SpiralQWQ/document-to-markdown) | documents to Markdown (PDF/Word/PPT) |
| [media-to-markdown](https://github.com/SpiralQWQ/media-to-markdown) | media to Markdown (video/audio/albums) |
| [text-cleaning-engine](https://github.com/SpiralQWQ/text-cleaning-engine) | clean (strip watermarks, denoise) |
| [md-rewrite-engine](https://github.com/SpiralQWQ/md-rewrite-engine) | rewrite into teaching notes |

This repository does the **orchestration only**. It contains no parsing,
transcription, cleaning, or rewriting capability of its own — all of that lives
in the parts.

**The code of the parts is not published with this repository.** They each have
their own release cadence, changelog, and license, and copying them in would
create two authoritative copies that drift apart silently. So this repository
carries a **lock table** instead, and one command fetches them on first use:

```bash
python scripts/setup_parts.py          # into parts/<name>/, pinned to a commit
python scripts/setup_parts.py --check  # report only, fetch nothing
```text
Where they come from, which commits are pinned, and under what license:
[`docs/UPSTREAM.md`](docs/UPSTREAM.md).

---

## Features

**One pipeline out of five tools.** `material-to-notes run` chains fetch, convert,
clean, and rewrite in one go. You do not learn five CLIs; you learn one command
and a route table.

**`route` tells you what will happen before it happens.** Point it at a PDF, a
video link, a folder of images, or a terms file, and it reports which line that
input takes and which parts will be invoked. Nothing is downloaded until you say
so.

**Install only the line you run.** The document line needs ~0.1 GB because parsing
goes to the MinerU cloud API. The media line, which downloads torch, is the
expensive one. `--line` picks; `--all` is opt-in, not the default.

**Machine gates, not vibes.** Format, structure, and word count are checked
mechanically, and `scripts/verify_fidelity.py` sends every informative number in
a note back to its source. The one thing no script can judge — whether the note
actually teaches — is left to a reviewer, deliberately.

**Pinned parts, one command.** `setup_parts.py` fetches the five parts at commits
this repository is known to work with. Upgrading a pin is a documented procedure
(`docs/UPSTREAM.md`), not a silent `git pull`.

**A privacy scanner wired into CI.** Absolute paths, usernames, the internal
codename this project used before it was renamed, and key-shaped strings all fail
the build. It reads the disk as well as git, so a file nobody has added yet is
still scanned.

**Honest test results.** With the parts missing the suite skips everything, prints
the command that fixes it, and exits 1 — it never reports green without looking.

---

## It is semi-automatic, not automatic

Read this before installing, or you will finish setup, watch the last step stop,
and conclude the project is broken.

```text
What the machine does (fully automatic)     What a person / AI must do
─────────────────────────────────────       ─────────────────────────────
crawl the web                                write the note
convert to Markdown
clean
format to spec                               judge whether it actually teaches
check format / structure / word count        review quality
                                             decide rework or pass
```text
**Writing the note is deliberately not automated.** Format can be checked, word
count can be checked, structure can be checked — but whether it explains the
material is a judgement only a mind can make. So the code stops at that step and
prints a task sheet — what to write, which spec to follow, where it goes — and
hands it to you, or to an AI assistant you drive.

After that, machine gates take over: format, structure, word count, and whether
every informative number in the note traces back to the source. Passing the gates
is what "done" means.

The full working agreement is in [`docs/SOP.md`](docs/SOP.md) (Chinese only): who
dispatches, how work is handed off, what happens when something fails, and why the
reviewer must be someone who **did not write the note** — reviewing your own work
finds typos, not the places where you failed to explain anything.

---

## Installation

Three steps, in this order.

### Step 1: install the engines

```bash
python scripts/setup_engines.py --check    # see what is missing first
```text
By default this installs the **pipeline environment only** (~0.1 GB, under a
minute). Then add what the line you want to run needs:

| Command | Adds | Measured size |
|---|---|---|
| `--line document` | pipeline env only (parsing goes to the MinerU cloud API) | ~0.1 GB |
| `--line fetch` | crawl4ai + yt-dlp | ~0.7 GB |
| `--line clean` | trafilatura + presidio | ~1.4 GB |
| `--line media` | funasr + torch + rapidocr | ~3.7 GB |
| `--all` | everything except local MinerU | ~7.0 GB |

**The honest number**: installing everything downloads **5–8 GB** and takes
**20–40 minutes**, most of it torch. Installing per line skips nearly all of
that — the document line alone is 0.1 GB.

Why one environment per engine instead of one big one: torch/funasr and opencv
disagree about numpy, crawl4ai wants playwright, presidio wants spaCy plus a
model. One environment resolves to a version set that satisfies nobody. The parts
are built for this — each heavy engine runs through a bridge script whose
interpreter comes from an environment variable.

The pipeline environment is the exception to the one-venv-per-engine rule: it is
installed **into the interpreter you run this script with**, because the
adapters launch every part under that same interpreter. `pip install -e .`
installs the same set (`pyproject.toml` declares them), so either path leaves you
able to `import yaml`.

**Local MinerU is not recommended.** The document line is built for the MinerU
cloud API; the local engine is gigabytes of models doing the same job. If you
really need `--mode local`: `--line document-local` (~4.6 GB, includes pix2text
for formula OCR).

**ffmpeg is not downloaded automatically.** Fetching an executable from the
internet inside a setup script is a supply-chain risk, so it only checks PATH and
tells you how to install it (Windows: `winget install Gyan.FFmpeg`), after which
you set `FFMPEG` yourself.

Keys are yours to provide, in `.env` (gitignored): a MinerU cloud API token, a
Zhipu GLM key, optionally DeepSeek / Anthropic. The template is
[`.env.example`](.env.example) and **every value in it is empty**.

`MINERU_API_TOKEN` is the one the default document line cannot run without — the
free tier at [mineru.net](https://mineru.net/) is enough to try it. The rest are
optional and only needed for quality scoring and image understanding.

### Step 2: fetch the parts

```bash
python scripts/setup_parts.py
```text
Slow network in China: add `--mirror gh-proxy` (verified working 2026-10-25;
these mirrors do not last, so pass a full URL prefix once that one has gone).

### Step 3: verify

```bash
python -m pytest -q        # 578 passed
```text
---

## Running it

```bash
pip install -e .                                   # gives you the material-to-notes command
material-to-notes --version

# or without installing, put src on the path for one command
PYTHONPATH=src python -m material_to_notes.cli.main --version
```text
Eleven subcommands:

| Command | What it does |
|---|---|
| `init` | initialise a work directory |
| `route` | see which line an input takes |
| `run` | run one line end to end (the note-writing step is handed to you) |
| `step` | run a single step (so one step can be handed to an AI assistant) |
| `intake` | read/write the work sheet (what to process, where it goes) |
| `deliver` | copy notes to the delivery directory named in the work sheet |
| `assign` | print the task sheet for a step (backs up the previous output first) |
| `snapshots` | list the versions a step has backed up |
| `gate` | run a step's machine checks (format / structure / word count / number tracing) |
| `toc` | add/refresh the in-document table of contents of a note |
| `checklist` | print the review checklist for a step |

---

## FAQ

**The pipeline stopped at the note step and did nothing. Is it broken?**

No — that is the design. Format, structure, and word count are things a script can
check; "does this actually teach the material" is not. So the code stops there,
prints a task sheet, and hands the step to a reviewer. See
[It is semi-automatic, not automatic](#it-is-semi-automatic-not-automatic) and
[`docs/SOP.md`](docs/SOP.md). If you want a fully unattended rewrite, this is not
that tool.

**Do I have to install all 5–8 GB?**

No, and you should not. `--line document` is ~0.1 GB because parsing goes to the
MinerU cloud API. Add a line only when you run it. See the table under
[Installation](#installation).

**Why one virtual environment per engine?**

Because their dependencies fight. `torch` and `funasr` pin a numpy that `opencv`
rejects; `crawl4ai` wants playwright; `presidio` wants spaCy plus a downloaded
model. One environment resolves to a version set that satisfies nobody. The parts
are built for this — each heavy engine is invoked through a bridge script whose
interpreter comes from an env var, so separate venvs are the design, not a
workaround.

**Cloud MinerU or local?**

Cloud. The document line is built for the cloud API; the local engine is several
gigabytes of models doing the same job. It stays installable as
`--line document-local`, and it is marked not recommended. You need
`MINERU_API_TOKEN` in `.env` for the cloud path — the free tier at
[mineru.net](https://mineru.net/) is enough to try it.

**`pytest` skipped everything and exited 1.**

You have not fetched the parts. Run `python scripts/setup_parts.py`. The suite
reads the parts' files (the note style spec, the gate labels) but does not import
them, so a missing part is a setup problem and is reported as one rather than as
39 `FileNotFoundError`s.

**Can I use this commercially?**

The orchestration layer is dual-licensed: AGPL-3.0, or a commercial license if
AGPL's network clause does not fit your use. See [`LICENSE`](LICENSE) and
[`COMMERCIAL.md`](COMMERCIAL.md). Note that the five parts carry their own
licenses and are **not** covered by a commercial license to this repository.

**Git is slow in China.**

`python scripts/setup_parts.py --mirror gh-proxy`. That preset was verified
working on 2026-10-25; mirror sites do not live long, and when it dies you can
pass a full URL prefix instead of a preset name.

**A part is behaving wrongly. Where do I fix it?**

Not in `parts/` — that directory is a fetched snapshot, and editing it produces a
copy nobody will ever merge. File it against the part's own repository, then bump
the pin and re-verify. `docs/UPSTREAM.md` has the procedure.

---

## Roadmap

This repository is feature-complete for what it sets out to do. The list below is
what is honestly known to be missing, not a wish list.

- **`setup_engines.py --check` should name the missing keys, not just count
  them.** Today it reports "3 variable(s)" and leaves you to work out that
  `MINERU_API_TOKEN` is the one the document line needs. The template and both
  READMEs already say so; the check itself does not yet.
- **A part's spec change should be loud.** If `md-rewrite-engine` changes its
  note style spec in a way this repository cannot read, the pipeline reports
  `SpecUnavailable` and stops — correct, but the message could name which file
  and which expectation failed.
- **No first-run smoke test for the cloud path.** The document line is only
  verified end to end against the real MinerU API by a human today. A
  `--selftest` that posts a two-page PDF and checks the shape of the result would
  catch an upstream API change before a user does.

Not on the roadmap, on purpose: automating the note-writing step. That is the
project's premise, not a gap.

---

## Documentation

| File | For |
|---|---|
| [`docs/SOP.md`](docs/SOP.md) | the AI working agreement: dispatch, gates, 4-round review, evidence sheets |
| [`docs/架构与目录契约.md`](docs/架构与目录契约.md) | architecture and directory layout |
| [`docs/contracts/接口契约.md`](docs/contracts/接口契约.md) | the exact command each step runs and where its output lands |
| [`docs/穷举测试方案.md`](docs/穷举测试方案.md) | path exhaustion, strict boundaries, endpoint consistency |
| [`docs/acceptance/每步验收标准.md`](docs/acceptance/每步验收标准.md) | per-step commands, hard and soft checks |
| [`docs/UPSTREAM.md`](docs/UPSTREAM.md) | the five parts: source, pinned commits, license, two hard rules |
| [`THIRD_PARTY.md`](THIRD_PARTY.md) | third-party components and licenses; three things to watch |

> The documents under `docs/` are written in Chinese. `README.md` (English) and
> `README_zh.md` (Chinese) are kept in sync; the rest are Chinese-only.

---

## License

**Dual-licensed**: [AGPL-3.0](LICENSE) for open source, plus a
[commercial license](COMMERCIAL.md). Copyright (c) 2026 Spiral QWQ.

The AGPL network clause means that anyone who takes this code, changes it, and
distributes the result — **including running it as a website for other people** —
must publish their changes under AGPL too. If that is not acceptable, use the
commercial license.

Third-party components and licenses: [`THIRD_PARTY.md`](THIRD_PARTY.md). Two of
them matter if you are buying a commercial license: mineru uses a custom license,
and pymupdf is AGPL-or-Artifex-commercial — neither is covered by a license to
this repository.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Two rules specific to this project:
never edit anything under `parts/` (part bugs go upstream, then the pin is
bumped), and never commit a machine-specific path, a username, the internal
codename, or a key.

## Changelog

[CHANGELOG.md](CHANGELOG.md) (English) ·
[CHANGELOG_zh.md](CHANGELOG_zh.md) (Chinese).

## Support

If this project helps you, feel free to buy me a coffee. Donation is entirely
optional — the project stays free and open source forever.

<p align="center">
  <img src="assets/donate_wechat.jpg" alt="WeChat Pay" width="200">
  <img src="assets/donate_alipay.jpg" alt="Alipay" width="200">
</p>
