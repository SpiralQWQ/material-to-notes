## What this changes

One or two sentences. If it fixes an issue, link it: `Fixes #123`.

## Why

The reason this change is needed. If the reason is not worth writing down, the
change may not be worth making.

## How it was verified

What you actually ran and what it printed. "Tests pass" is not evidence; the
command and its output are.

- [ ] `python -m pytest -q` — expected **514 passed**
- [ ] `python scripts/privacy_check.py` — must print `clean` and exit 0
- [ ] `CHANGELOG.md` and `CHANGELOG_zh.md` updated under `[Unreleased]`

## Checklist

- [ ] I did **not** edit anything under `parts/` — part bugs go upstream, and
      the pin is bumped afterwards (see `docs/UPSTREAM.md` §三)
- [ ] No absolute paths, usernames, the internal codename, or keys
- [ ] Tests added for the change; a change with no test is a change nobody can
      trust later
- [ ] README updated if behaviour a user would notice changed
- [ ] English and Chinese README still agree
