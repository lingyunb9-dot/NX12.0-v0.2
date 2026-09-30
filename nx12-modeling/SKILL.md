---
name: nx12-modeling
metadata:
  version: "0.2"
description: Develop, review, and validate Siemens NX 12 NXOpen journals and utilities in Python or C# for modeling, drafting, and drawing automation, and reconstruct NX 12 3D models from dimensioned engineering drawings. Use when the task involves writing or debugging NXOpen code, cleaning up a recorded journal, choosing builder call order, checking whether a specific NXOpen member exists in NX 12, rebuilding a part from a dimensioned drawing, section view, or image, or reviewing whether a reconstructed model matches its drawing. Do not use for general NX 12 usage, user-interface, installation, or licensing questions, and do not treat it as authority for NX 1847 or any later release. Drawing interpretation stays user-reviewed; this skill does not understand an arbitrary complex drawing on its own.
---

# Siemens NX 12 NXOpen automation

Iteration 0.2 — mandatory cross-reading for drawing-driven reconstruction.

Generate NXOpen automation that is version-locked, evidence-backed, and safe to test.

## Support boundary

In scope:

- NXOpen Python journals and utilities, including the `NXOpen.UF` Python wrapper. The UF wrapper is a Python binding over the UFUN library and is covered; C++ UFUN development is not.
- NXOpen .NET C# journals and compiled utilities.

Out of scope unless the user explicitly expands the task: C++ UFUN, CAM, CAE, Teamcenter, and release migration. This skill has not verified those areas, and modeling experience does not transfer to them. Say so instead of extrapolating.

## Follow the workflow

1. Establish the task: language, operation, unit system, work part, and whether the user wants generation, review, validation, or execution. Infer these from the existing code, files, and environment. Ask only when a missing detail changes the implementation.
2. Read [references/nx12-environment.md](references/nx12-environment.md) when locating or configuring NX, and run `scripts/inspect-nx-installation.ps1` when the installation is unknown.
3. Read [references/api-validation.md](references/api-validation.md) before introducing or changing any NXOpen type, member, enum, or builder sequence.
4. Load only the task-specific reference:
   - Python journals: [references/nxopen-python-patterns.md](references/nxopen-python-patterns.md)
   - C# journals: [references/nxopen-csharp-patterns.md](references/nxopen-csharp-patterns.md)
   - Feature creation and editing: [references/modeling-builders.md](references/modeling-builders.md)
   - Creating or editing 2D drawings, views, and annotations: [references/drawing-and-drafting.md](references/drawing-and-drafting.md)
   - Reconstructing 3D geometry from an existing engineering drawing: [references/drawing-reconstruction.md](references/drawing-reconstruction.md) and [references/cross-reading.md](references/cross-reading.md) — read both **before** fixing feature interpretations or writing the model.
   - Deciding whether a model matches its drawing, or checking its dimensions, topology, or structure: [references/geometry-acceptance.md](references/geometry-acceptance.md) — read it **before** reporting a result, and write the outcome up with [assets/templates/geometry-acceptance-report.md](assets/templates/geometry-acceptance-report.md).
   - Worked reconstruction and acceptance situations: [references/reconstruction-review-cases.md](references/reconstruction-review-cases.md)
   - Symbolic-thread geometry/readback or bounding-box discrepancies: [references/runtime-observations.md](references/runtime-observations.md) — local observations and the checks needed before relying on them.

   Route by what the task actually is. A task that only looks up an API member, debugs a journal locally, or applies a simple operation to dimensions the user already supplied does not load the reconstruction or acceptance protocol below, and keeps its parameters and check record in a proportionate form — the conversation, a short table, or the code's own configuration — rather than a separate ledger file. Reconstructing 3D geometry from a drawing and creating a 2D drawing or annotation are different workflows: they share the drawing, not the procedure. A read-only task may use the record templates to organize its answer; reading a template does not authorize writing a new report into the user's directories.
5. Prefer the call order recorded by the user's own NX 12 Journal recorder. Preserve the session, undo-mark, builder creation, property assignment, commit, and destroy order. Remove recorded object handles, selection indices, and machine-specific paths. Temporary expressions are not automatically removable: keep any expression a builder depends on, and delete one only after its ownership and lifetime are established.
6. Start generated code from `assets/templates/python-journal.py` or `assets/templates/csharp-journal.cs`, or render one with `scripts/create-journal-template.ps1`.
7. Validate in the order described under [Report verification honestly](#report-verification-honestly).
8. Report the API evidence used, what was actually verified, what was not, and whether the result is ready to run. Pass on the tools' own limits: a `missing-api-evidence` warning, an index that could not be loaded, and entries whose version, binding or source file did not match are all things the reader needs, and none of them may be reported as an API confirmation.

## Gate drawing-driven reconstruction

These gates apply when the task rebuilds 3D geometry from a drawing, a section view, or an image, and when it decides whether a model conforms to that drawing. Read the two references named above for the procedure; the rules below are the part that must not be skipped.

1. **Identify the task scope before doing it.** Reading and analyzing a drawing, proposing a modeling plan, building in NX, and accepting the finished model are four scopes to keep distinct — not four permissions to request one after another. Read the whole request first and treat the scopes it already covers as authorized: a user who asks for a model to be built, verified, and saved to a named target has authorized that flow, and reading the drawing, planning, modeling, and the verification the flow needs are part of it. Do not re-ask for each stage.

   Both directions of error matter. A request to look at, explain, or read-only review a drawing does not authorize modeling, saving, or export — do not start them because the drawing made a defect obvious. Equally, "do not re-ask" is not a licence to widen a request. Ask when the next step goes beyond what was authorized, when the target file or operation destination is unclear, when an object that is not authorized would be overwritten or modified, or when a key user choice changes the implementation. The part-protection and save/export rules under [Apply the execution safety gate](#apply-the-execution-safety-gate) are unchanged.

   A photo or a thumbnail is not dimension evidence on the same footing as a dimensioned drawing or a section view.
2. **Fix coordinates and cross-read before fixing features.** Record units, origin, axis directions, axial/radial/tangential sense, the observation direction of every principal view and section, the projection method only when the drawing gives evidence for it, the angular zero and positive direction, and any circumferential repeat count and spacing. Before choosing a feature type, dependent dimensions or construction operations, complete [mandatory cross-reading](references/cross-reading.md) for the relevant feature group. Record the views, material relationships, dimension ownership and datums, the interpretation supported, and a check that could expose the wrong interpretation. Critical unresolved contradictions block the affected feature; unrelated settled work may continue. For an existing-model review, do this retrospectively and record the actual timing. A drawing's clear requirement needs no additional user approval.

   Do not read four visible directions as four equal divisions, do not treat occlusion in an isometric view as absent geometry, and do not apply a left/right convention before the projection relationship is established.
3. **Record the basis, in proportion to the task.** For a complex reconstruction, keep a structured feature ledger built from [assets/templates/drawing-feature-ledger.md](assets/templates/drawing-feature-ledger.md), with each feature's source view, raw dimension or symbol, geometry type, quantity, position and direction, dependencies, and a basis class: `explicit`, `derived`, `user-confirmed`, or `unresolved`. "It looks like" is not `explicit`, and an `unresolved` guess cannot be the foundation of a `derived` entry. Repeated structures and sectioned features stay traceable item by item.

   A simple task whose dimensions the user already supplied may keep the same information in the conversation, a short table, or the code's own configuration rather than in a separate ledger file. The record is condensed, never absent: the applicable dimensions, units, and the scope actually verified are still written down. "Condensed" does not mean "unverified".
4. **An ambiguity that matters blocks the feature it touches.** A question affecting quantity, hole type, connectivity, a critical dimension, or helix hand blocks the final build and the acceptance of the features it governs. Isolate it and say so; never silently choose. Unrelated, settled work may continue. A requirement the drawing states clearly needs no confirmation from the user.
5. **Define the acceptance conditions from the drawing, not from the model.** For a new build, before the result exists. For a review of a model that already exists, rebuild the conditions from the drawing or the applicable requirements, record that the review is **retrospective**, disclose it if the model or its construction code has already been seen, and do not describe the work as blind testing or invent a pre-modeling plan that was never written. Either way, model construction may share the checked nominal parameters, but an acceptance check must not merely restate the assumptions of the code it is testing. Independent means independent of the model's own assumptions: a second process adds file-reopen independence only, not drawing-understanding or algorithmic independence.
6. **Know what does not prove geometry.** A matching overall bounding box, a single solid body, zero feature error messages, a few point-containment samples, a matching volume, a saved-and-reopened file, a screenshot, or an appearance-only approval each cover their own narrow scope. None of them substitutes for dimensional, positional, or topological checks.
7. **Report two conclusions when the user approved a simplification.** Drawing conformance and approved-scope conformance are recorded separately, each against its own requirement set — the **drawing requirement set** and the **approved delivery requirement set** — with the approval basis and the excluded requirements kept. They may legitimately differ: a `FAILED` drawing conclusion beside a `PASSED` approved scope is a normal pair when a required feature was knowingly dropped. Passing the approved, reduced scope is never reported as passing the original drawing.
8. **Do not promote the result by wording.** Execution success, save success, and reopen success are execution facts. A partial feature pass is a partial pass. Appearance approval is appearance approval. None of them becomes whole-part `result-confirmed`; see [Scope of `result-confirmed`](#scope-of-result-confirmed). The converse also holds: a stated confirmation scope whose applicable checks all pass may be reported as confirmed even when an independent feature elsewhere has failed — provided that failure stays prominently in the report and no unscoped "the model is confirmed" wording is used.

## Enforce NX 12 compatibility

- Positively verify every nontrivial NXOpen type, member, enum, and overload. A blacklist of later releases is only a secondary check.
- Prefer, in order: the local NX 12 XML/DLL index, NXOpen MCP results built from that installation, `nx12-nxopen-pyi` stubs, a Journal recorded in the same NX 12 installation, then a manually checked NX 12 example.
- Never infer availability from an example targeting NX 1847 or a later release.
- Evidence from the .NET XML or DLL files proves the **.NET binding** directly. Python names and overloads must additionally be checked against Python binding material or the target runtime: a C# signature is not automatically a Python signature. The shipped NXOpen XML is .NET documentation only — a name found in it is a .NET lead for Python code, never a Python confirmation. `scripts/check-api-evidence.py` reports a `binding=python` claim checked against that XML as unverified rather than rewriting the claim.
- A missing index entry means **not documented**, never **does not exist**. `member-not-documented` and `type-not-documented` are gaps in the evidence that need another source; do not report them as contradictions, and do not use contradiction wording just because the XML is incomplete.
- Mark unresolved calls as `UNVERIFIED` and keep them behind a clear TODO. Do not claim that unverified code is runnable.
- Record evidence beside important calls using the `NX12-API:` comment format defined in [references/api-validation.md](references/api-validation.md).

## Apply the execution safety gate

The gate applies when code or tools will actually modify NX state. Code generation and static review do not require it.

1. Establish the target explicitly. A brand-new blank part created for this test needs no backup, because it has no prior content to lose. An existing part needs a user-confirmed disposable copy or backup; do not invent a backup path on the user's behalf.
2. Refuse to run against an unsaved original or a production or managed part unless the user authorizes that exact target. Once the user has named and authorized a target, do not ask again.
3. Create a visible undo mark before the first mutation.
4. Release builders and other resources according to resource ownership and verified API requirements. Destroy the builders this journal created; do not call `Destroy()` on arbitrary NXOpen objects, and never destroy the session, the part, or committed results that belong to the model.
5. On failure, log the complete exception and attempt to return to the undo mark without hiding the original error. A logging or rollback failure must not replace the original exception. Report the rollback outcome that actually occurred — `not-attempted`, `succeeded`, or `failed` — and never claim a rollback that did not happen: a journal can fail before the undo mark exists, and the rollback itself can fail.
6. Do not save, Save As, close, delete, overwrite, export, submit, or batch-process files unless the user explicitly requests that operation and its destination.

## Keep outputs reviewable

- Separate configuration from modeling logic.
- Resolve objects by stable user-provided names, attributes, or geometric intent; do not depend on recorded tags or opaque journal identifiers.
- State unit assumptions and validate them before assigning dimensions.
- Make rerun behavior explicit. Avoid silently creating duplicate expressions, features, notes, or sheets.
- Keep the first version small enough to validate in a clean test part before extending it.
- Use [references/source-index.md](references/source-index.md) to separate verified facts from candidate references. Do not bundle Siemens binaries or proprietary documentation into this skill.

## Report verification honestly

These states are independent and can hold at the same time. Record them side by side; never collapse them into a single "verified".

| State | Meaning |
| --- | --- |
| `scaffold` | A template or unfinished code. |
| `static-checked` | The listed static checks passed via `scripts/validate-journal.py --mode ready`. It says nothing about NXOpen existing or the journal running. |
| `api-evidence-checked` | Key API evidence was resolved against a target-version index. **Not granted automatically by any script here** — see below. |
| `compiled` | C# compiled against the target installation's assemblies. Compiling is not executing. |
| `executed-in-nx12` | Ran in the target NX 12 environment. |
| `result-confirmed` | The model or drawing result was confirmed **within a stated scope**, against named evidence. It never covers more than the checks that were actually run. See below. |

Tools that produce each state:

- `scripts/inspect-nx-installation.ps1` — read-only installation and version evidence.
- `scripts/probe-nx12-api.py` — runs inside NX; runtime version evidence, Python runtime, and dotted-name resolution. It does not confirm overloads and never invokes the API it probes. A real NX 12 session reports `UGII_VERSION` as `v12`, which the probe parses. Its entry point returns naturally, because the NX 12 journal host treats `SystemExit` (even `sys.exit(0)`) as a journal error: read the logical status from the complete `PROBE-RESULT:` JSON record, never from the host process exit code.
- `scripts/check-api-evidence.py` — checks evidence comment structure and, with an index, whether each named member is documented.
- `scripts/validate-journal.py` — static checks in `scaffold` or `ready` mode.
- `scripts/validate-nx12-csharp.ps1` — C# compile check against the target assemblies.

### Scope of `result-confirmed`

`result-confirmed` is a claim about a scope, so it is only meaningful when that scope is written down: which features, which dimensions, which method, and which evidence. It is never granted to a whole part by default, and it is never reported without stating what it covers.

The threshold is **within the stated confirmation scope**: every applicable required check inside that scope must have a valid `PASS`. It is not a demand that every check anywhere in the drawing passed.

- A journal that executed, a save that completed, and a reopen that loaded the file establish that the file is readable and the code ran. None of them says the geometry is right, and none of them grants `result-confirmed` for the part.
- Features that passed acceptance are reported as those features passing. A partial pass is not promoted to the whole part.
- A `FAIL` outside the stated scope is retained and reported prominently. It must not be buried by a local confirmation, and it does not automatically cancel a different local scope that was independently and fully verified. With F001 fully passing and F002 failing, for example: F001's limited scope may be reported as confirmed, the whole-part drawing conclusion is still `FAILED`, and no unscoped "the model is confirmed" wording may be used.
- For a drawing-reconstruction task, the acceptance thresholds in [references/geometry-acceptance.md](references/geometry-acceptance.md) apply first, including its separate conclusions for the **drawing requirement set** and the **approved delivery requirement set**.
- A user who approves the visible appearance has approved the appearance. That does not extend to unmeasured internal cavities, unchecked hole diameters and depths, or dimensions nobody measured.
- A result that failed acceptance keeps its `executed-in-nx12` state. The execution happened and must not be hidden; it simply does not become `result-confirmed`.

The acceptance vocabulary in [references/geometry-acceptance.md](references/geometry-acceptance.md) — per-check `PASS`, `FAIL`, `NOT_RUN`, `BLOCKED`, `N/A`, and the overall `NOT_ASSESSED`, `PARTIAL`, `FAILED`, `PASSED` — is a **task-report convention**. It is a way to write an acceptance report down, not an output of this skill's scripts. No existing script emits it, none of them may be changed to grant it, and the `apiTruthChecked`, `callCoverageChecked` and JSON contracts above are unaffected by it.

What the two evidence tools actually report, and what they do not:

- Per-entry results: whether each `NX12-API` comment is well formed, and whether the member it names is documented in the index with a version, binding and source file that agree with it. `documentedEntryCount` counts **comments**, not calls. Neither tool maps a code call to an evidence entry, so **loading an index does not mean the file's calls were checked**.
- File-level `api-evidence-checked` and `apiTruthChecked` are therefore never granted by these tools: both are reported as `false`, together with `indexLoaded`, `evidenceEntryCount`, `documentedEntryCount` and `callCoverageChecked: false`. Record `api-evidence-checked` only as the conclusion of a separate human or sufficient verification process, and say which entries it covers.
- `validate-journal.py --mode ready` adds a `missing-api-evidence` warning when a file imports or calls NXOpen but carries no evidence comment at all, so silence cannot be read as a pass. That warning is derived from the parsed code, not from prose mentioning NXOpen.

A passed check proves only what that check covers. Static success does not prove a journal runs, a successful compile proves the source compiled and nothing about execution, and name resolution does not prove an overload. `executed-in-nx12` requires an actual run in NX 12, and it is the only state that speaks for the journal running at all.

## When the tooling is not available

Do not assume an index, MCP server, or local NX exists. Degrade explicitly:

- No local NX installation: complete all work that does not depend on it, and list the remaining on-machine checks. `scripts/validate-journal.py` still runs; report that API truth was not verified.
- No NXOpen XML index: `scripts/check-api-evidence.py` checks comment structure only and says so. Ask the user for a journal recorded in their NX 12 installation, or their local XML/DLL files.
- No C# compiler or assemblies: `scripts/validate-nx12-csharp.ps1` reports `skipped` rather than a false success. The journal stays `static-checked` at best.
- No NX session for the probe: version evidence comes from the process environment only, and the probe reports the environment as unverified rather than guessing.
