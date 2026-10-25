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

- [It is semi-automatic, not automatic](#it-is-semi-automatic-not-automatic)
- [Installation](#installation)
- [Running it](#running-it)
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
prints a line saying the `note` step goes to a sub-agent and where the task sheet
is, and then the main conversation takes over: read the sheet, dispatch an agent,
collect the work, review.

The working agreement lives in [`docs/SOP.md`](docs/SOP.md) (in Chinese): the
main conversation only dispatches, hands off between steps, watches for errors,
and decides retry-or-stop; each step gets one executing sub-agent and one
**independent** reviewing sub-agent that does not share the context of the
executor; every task goes through 4 rounds of review plus a four-part evidence
sheet; three failures and it stops and hands back to a human — the code never
routes around its own failure.

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
python -m pytest -q        # 514 passed
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
| `run` | run one line end to end (the `note` step goes to a sub-agent) |
| `step` | run a single step (for the main conversation to dispatch) |
| `intake` | read/write the intake sheet |
| `deliver` | copy notes to the delivery directory named in the intake sheet |
| `assign` | print the task sheet for a step (dispatches; snapshots the previous output first) |
| `snapshots` | list the versions a step has snapshotted |
| `gate` | run the machine gates for a step |
| `toc` | add/refresh the in-document table of contents of a note |
| `checklist` | print the review checklist for a step |

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
