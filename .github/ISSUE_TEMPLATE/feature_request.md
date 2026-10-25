---
name: Feature request
about: Suggest an idea for this project
title: "[FEATURE] "
labels: enhancement
---

**Is your feature request related to a problem?**
A clear description of what the problem is. E.g. "I always have to ... when ..."

**Describe the solution you would like**
What you want to happen, concretely enough to act on.

**Describe alternatives you have considered**
Other ways to solve it, and why you did not pick them.

**Which layer does this touch?**
- [ ] `contract/` — steps, workdir layout, validation
- [ ] `steps/` — an adapter for one of the five parts
- [ ] `gates/` — machine checks or the review checklist
- [ ] `orchestrate/` — routing, resume, failure handling
- [ ] `report/` — progress, logs, snapshots
- [ ] `cli/` — commands and exit codes
- [ ] `scripts/` — setup, privacy, verification
- [ ] docs only

**Does it need a new engine?**
If this requires a tool we do not already wrap, say what it is, how big it is,
and whether it conflicts with the ones already installed. The installer keeps
one environment per engine on purpose — see the README.

**Additional context**
