---
name: Bug report
about: Something does not work the way the README says it should
title: "[BUG] "
labels: bug
---

**Describe the bug**
A clear and concise description of what is wrong.

**To reproduce**
The exact command you ran, and the input you gave it. If the input is a file,
describe it (format, size, page count) rather than attaching private material.

**What you expected to happen**

**What actually happened**
Paste the output. If it is long, the first and last 20 lines plus the error.

**Environment**
- OS:
- Python version (`python --version`):
- Which line you ran: document / media / fetch / clean
- Engine status — paste the output of `python scripts/setup_engines.py --check`
- Pinned part versions — paste the output of `python scripts/setup_parts.py --check`

**Checklist**
- [ ] I ran `python scripts/setup_parts.py` before `pytest`
- [ ] I ran `python scripts/privacy_check.py` and it is clean
- [ ] I searched existing issues and this is not a duplicate
