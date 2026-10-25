"""Shared mock helpers for the closed-loop and exhaustive tests.

The real tools need the local environment; these mocks let the wiring be
exercised deterministically.
"""

from pathlib import Path

from material_to_notes.orchestrate import runner as OR

STEPS = ("fetch", "document", "media", "clean", "note")


def write(root, subdir, name, content="x"):
    base = Path(root) / subdir
    base.mkdir(parents=True, exist_ok=True)
    (base / name).write_text(content, encoding="utf-8")


def executors(spec, fail=(), behaviour=None):
    """spec: {step: (subdir, name | [names])} — the mock writes those and reports ok.

    fail: step ids that always fail. behaviour: {step: callable(root) -> Outcome}.
    """
    behaviour = behaviour or {}

    def make(step_id):
        def run(root):
            if step_id in behaviour:
                return behaviour[step_id](root)
            if step_id in fail:
                return OR.Outcome(False, f"{step_id} boom")
            target = spec.get(step_id)
            if target:
                subdir, names = target
                for name in ([names] if isinstance(names, str) else names):
                    write(root, subdir, name)
            return OR.Outcome(True)

        return run

    return {step: make(step) for step in STEPS}


MEDIA_SPEC = {
    "media": ("02_转md", "v_clean.md"),
    "clean": ("03_清洗", ["v.txt", "v.meta.json"]),
    "note": ("04_笔记", "note.md"),
}
DOC_SPEC = {
    "document": ("02_转md", "full.md"),
    "clean": ("03_清洗", ["full.txt", "full.meta.json"]),
    "note": ("04_笔记", "note.md"),
}
FETCH_MEDIA_SPEC = {"fetch": ("01_取材", ["v.mp4", "meta.json"]), **MEDIA_SPEC}
FETCH_DOC_SPEC = {"fetch": ("01_取材", ["paper.pdf", "meta.json"]), **DOC_SPEC}
