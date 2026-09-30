# NXOpen Python patterns for NX 12

Use conservative Python syntax. NX 12 embeds Python 3.6.1, so verify the runtime with `scripts/probe-nx12-api.py` before reaching for anything newer.

## Journal skeleton

Copy `assets/templates/python-journal.py` or render it with `scripts/create-journal-template.ps1`. Keep these invariants:

- Obtain `NXOpen.Session.GetSession()` once.
- Capture both work and display parts, and fail clearly when no work part is open.
- Create one visible undo mark before the first mutation.
- Register each builder the moment it is created, so a later failure cannot skip it.
- Destroy the builders this journal created, then restore the undo mark.
- Re-raise the original exception after logging and rollback attempts.
- Do not save, close, export, or submit in the generic template.

## Failure-handling contract

This is the part that is easy to get subtly wrong. Each rule exists because breaking it loses the real error:

- **Logging never raises.** A diagnostic that throws replaces the failure it was reporting. Wrap every write, and fall back to standard error when the Listing Window is unavailable.
- **Logging failure must not prevent rollback.** Rollback does not live after a logging call that can throw; both are independently guarded.
- **Rollback failure must not replace the original exception.** `UndoToMark` runs inside its own guarded helper, so a second failure is logged and discarded.
- **One builder's cleanup failure must not skip the others.** Destroy inside a loop that continues after a failure.
- **Cleanup failure must not mask the original exception.** Cleanup helpers never propagate.
- **Failure is never reported as success.** The original exception is re-raised; do not return a success code from a failed run.

Ordering: **destroy builders first, then restore the undo mark.** Every builder is created after the undo mark, so rolling back first can invalidate the objects cleanup still has to release. Pick one order and keep it consistent.

Ownership: only builders this journal created are destroyed. Committed results belong to the model. The session, the work part, and `UndoMarkId` — which is a value, not a resource — are never destroyed. Do not call `Destroy()` on an arbitrary NXOpen object.

## Recorded Journal cleanup

Retain:

- Builder creation and property-assignment order.
- Unit and expression setup the builder depends on.
- Section, selection-rule, tolerance, commit, and destroy order.
- Required update calls and undo-mark boundaries.

Replace or remove:

- Opaque `FindObject` handles and recorded tags.
- Hard-coded drive paths, part filenames, view names, and sheet names.
- UI-only calls that do not affect the result.
- Empty exception handlers and generated variable-number noise.

**Temporary expressions are not automatically removable.** The recorder often creates an expression, uses it, and deletes it. If a builder still depends on that expression, deleting it breaks the feature. Establish ownership and lifetime first, and never delete a pre-existing expression merely because the builder no longer needs it.

## Builder cleanup

Append each created builder to a cleanup list immediately. Destroy in reverse order. Guard cleanup so one failed `Destroy()` does not hide the modeling exception.

If a committed object must be cast to a feature, verify the exact return type and cast pattern against NX 12 evidence first.

`scripts/validate-journal.py` tracks builders through direct variable assignments. A builder stored in a collection or passed to a helper is reported as **undetermined** rather than as missing — that is a limit of the analysis, not a defect in the journal. It does not use regular expressions for Python; it parses the module with `ast`, so a call written inside a comment or a string is never mistaken for executed code.

## Units and identity

- Read the work-part unit system before assigning literal dimensions.
- Prefer user-supplied expressions and semantic names.
- Check whether a named expression or feature already exists before creating it.
- State whether rerunning the journal updates an existing object, creates another, or refuses to continue.

## Compatibility posture

Avoid assignment expressions, `match`, positional-only parameters, `from __future__ import annotations`, and modules added after Python 3.6. Do not use Python type-stub syntax inside executable journals merely because the `.pyi` files contain annotations.

`scripts/validate-journal.py` checks these against Python 3.6 explicitly and reports the host interpreter it parsed with alongside the target interpreter.
