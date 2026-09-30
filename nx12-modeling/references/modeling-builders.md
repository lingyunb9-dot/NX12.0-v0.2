# Modeling builder discipline

Use this reference for creating or editing NX features. It describes lifecycle rules rather than asserting unverified feature-specific members.

## Builder lifecycle

Follow this order unless a same-version Journal proves a different requirement:

1. Resolve or create the owning part and input objects.
2. Create the builder from the appropriate NX 12 collection.
3. Register the builder for cleanup immediately.
4. Configure units, expressions, tolerances, sections, limits, directions, and boolean options.
5. Validate required selections and input geometry.
6. Commit once.
7. Resolve the committed object or created feature using the NX 12-confirmed return pattern.
8. Destroy the builder.
9. Update or rename objects only through separately verified calls.

Do not reuse a destroyed builder or assume a builder can be committed repeatedly.

Every member in this sequence needs evidence. `NXOpen.Builder.Commit` and `NXOpen.Builder.Destroy` are documented on the base type for every builder, so a builder created from a specific collection still needs its own factory method verified — `NXOpen.Features.ExtrudeBuilder` being documented does not by itself establish that `Features.CreateExtrudeBuilder` exists in your installation.

## Cleanup by ownership, not by guesswork

Destroy the builders this journal created, and nothing else.

- Do not call `Destroy()` on arbitrary NXOpen objects on the assumption that everything temporary needs one. Most NXOpen objects are owned by the part and are not destroyed by journals.
- Never destroy the session, the work part, the display part, or a committed result that belongs to the model.
- An undo mark id is a value, not a resource. It is restored with `UndoToMark`, never destroyed.
- If an API genuinely requires an explicit release, verify that requirement first and record it as evidence.

`scripts/validate-journal.py` reports a builder that is committed without a matching `Destroy()` as an error in `ready` mode, and reports "could not determine" when the builder escapes into a helper or a loop.

## Recorded selection rules

Recorded rules often encode transient topology. Prefer design intent in this order:

- Explicit user-selected object supplied to the journal.
- Stable name or attribute controlled by the workflow.
- Feature relationship or geometric query validated on the target part.
- Recorded object handle only as a last-resort diagnostic, never as reusable automation.

Document what happens when zero, one, or multiple objects match.

## Dimensions and expressions

- Confirm part units before creating literal values.
- Reuse a user-owned expression only when its semantic role matches.
- Use a unique, documented prefix for journal-owned expressions and features.

When a symbolic thread changes its supporting geometry or readback conflicts with the intended representation, use [runtime-observations.md](runtime-observations.md#symbolic-thread-changes-and-readback). Check the saved geometry and feature association rather than trusting the designation alone.

**Temporary expressions require care in both directions.** The recorder typically creates expressions, uses them, and deletes them on exit. Two mistakes are common:

- Deleting every expression the recording deletes, including ones a surviving builder still references. This breaks the feature.
- Deleting an expression the journal did not create. This damages the user's model.

Establish ownership and lifetime before deleting anything. Keep any expression a builder depends on. Never delete a pre-existing expression merely because a builder no longer needs it, and do not assume the recorded cleanup order is safe once the journal body has been edited.

## Booleans and design intent

A boolean that committed proves the tool body combined with the target. It does not prove the combination was the intended one, and no error message reports a combination that was wrong but valid. Check:

- The material the drawing says must remain, not only the material that was removed.
- That the target is still the body the design expects. A unite or subtract can leave a different live body tag, produce an extra body, or open a cavity where a wall was required.
- Connectivity. A cut meant to break through can instead leave a thin membrane that commits without complaint.
- That nothing was consumed that a later feature depends on.

A clean feature-error count describes the features that exist. A required feature that was never created produces no error, so the drawing's feature list is checked against the model rather than the model against itself.

For a drawing-driven build, zero wall thickness, unexpected breakthrough or negative remaining thickness triggers the [cross-reading failure review](cross-reading.md#5-revisit-the-interpretation-when-new-evidence-conflicts) after logging and cleanup/rollback. The failure describes the submitted construction; verify its material and dimension premises before changing nominal geometry to make a boolean succeed.

## Drawing-driven builds

When the geometry comes from an engineering drawing, each feature carries its ledger entry: the `feature_id` it implements, its basis class, and the acceptance items that judge it. Build from [drawing-reconstruction.md](drawing-reconstruction.md), and judge the result with [geometry-acceptance.md](geometry-acceptance.md). Recording the basis beside the feature is what keeps a later check traceable to a printed dimension instead of to this code.

## Safe iteration

Validate a new builder sequence in a new blank part first, then against a representative copy. Keep the first execution to one feature or one edit so rollback and comparison stay practical.
