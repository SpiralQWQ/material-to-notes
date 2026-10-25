"""Run a step chain serially: execute -> review -> approve -> next step.

Never parallel. A step that is not approved blocks the rest of the chain.
Nothing here edits code: when a step exhausts its attempts the run stops and
hands off to a human.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from material_to_notes.orchestrate import failures as _failures

DONE = "done"
SKIPPED = "skipped"
FAILED = "failed"


@dataclass(frozen=True)
class StepRecord:
    step: str
    status: str
    attempts: int = 0
    error: str = ""


@dataclass(frozen=True)
class Outcome:
    """Minimal shape an executor returns. Adapters return a richer StepOutcome."""

    ok: bool
    error: str = ""


@dataclass
class RunReport:
    records: list = field(default_factory=list)
    stopped_at: str = ""

    @property
    def ok(self) -> bool:
        return not self.stopped_at and all(r.status in (DONE, SKIPPED) for r in self.records)

    def status_of(self, step_id: str) -> str:
        for record in self.records:
            if record.step == step_id:
                return record.status
        return ""


def run_chain(root, chain, *, execute, review=None, max_attempts=_failures.DEFAULT_MAX_ATTEMPTS,
              is_done=None, mark_done=None, on_progress=None) -> RunReport:
    """Execute each step in order until one cannot be approved.

    execute(step_id, root)  -> outcome with ``.ok`` and ``.error``
    review(step_id, root)   -> (approved: bool, notes: str); default: approve
    is_done(step_id)        -> bool; resume hook, skips finished steps
    mark_done(step_id)      -> called after a step is approved
    on_progress(step_id, status) -> progress callback
    """
    attempts = _failures.Attempts(max_attempts=max_attempts)
    report = RunReport()

    for step_id in chain:
        if is_done is not None and is_done(step_id):
            report.records.append(StepRecord(step_id, SKIPPED))
            if on_progress is not None:
                on_progress(step_id, SKIPPED)
            continue

        last_error = ""
        while True:
            used = attempts.record(step_id)
            try:
                outcome = execute(step_id, root)
            except Exception as exc:  # noqa: BLE001 - a crashing adapter must not kill the run
                outcome = Outcome(False, f"execute crashed: {type(exc).__name__}: {exc}")
            if not outcome.ok:
                last_error = outcome.error or "step failed"
            else:
                try:
                    approved, notes = (True, "") if review is None else review(step_id, root)
                except Exception as exc:  # noqa: BLE001 - same for the reviewer
                    approved, notes = False, f"review crashed: {type(exc).__name__}: {exc}"
                if approved:
                    if mark_done is not None:
                        mark_done(step_id)
                    report.records.append(StepRecord(step_id, DONE, used))
                    if on_progress is not None:
                        on_progress(step_id, DONE)
                    break
                last_error = notes or "review rejected"

            if attempts.exhausted(step_id):
                report.records.append(StepRecord(step_id, FAILED, used, last_error))
                report.stopped_at = step_id
                if on_progress is not None:
                    on_progress(step_id, FAILED)
                return report

    return report
