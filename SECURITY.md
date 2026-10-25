# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Please **do not** open a public issue for security vulnerabilities.

Use GitHub's **private vulnerability reporting** on this repository instead:
`Settings → Security → Vulnerability alerting → Report a vulnerability`
(or open the "Security" tab and click "Report a vulnerability").

Include:

- A description of the vulnerability and its impact
- Steps to reproduce, or a minimal proof of concept
- Affected versions and, if possible, a suggested fix

We will acknowledge reports within **3 business days** and aim to ship a
fix or release within **7 days** for critical issues.

## Scope notes specific to this project

This repository is an orchestration layer. It runs external tools as
subprocesses and calls third-party APIs, so a report may well belong to one of
those rather than to us:

| Component | Where to report |
|---|---|
| The five parts (parsing, transcription, cleaning, rewriting) | each part's own repository — see [`docs/UPSTREAM.md`](docs/UPSTREAM.md) |
| MinerU, GLM, FunASR, ffmpeg, yt-dlp, spaCy, and other dependencies | the upstream project for that dependency |
| This repository: adapters, gates, orchestration, the setup scripts | here |

`scripts/setup_engines.py` deliberately does **not** download ffmpeg or any
other executable from the internet — that is a supply-chain risk, not a
shortcut. If you believe that decision should change, argue it in an issue
rather than a pull request.
