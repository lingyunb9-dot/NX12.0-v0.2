# Reconstruction and acceptance review cases

This is a set of **rule behaviour review cases**. It is not an automated test suite, it is not a substitute for tests, and it is not completed blind testing. Each case states the facts, the decision the rules require, the conclusions that must not be drawn, and where the governing rule lives.

The cases are synthetic and deliberately generic. They exist to make the rules checkable by a reader. They are not a library of solved drawings, and no specific real part's dimensions or solution belong here as general knowledge.

Case format:

- **Input facts** — what is known.
- **Required decision** — what the rules say must be done.
- **Forbidden conclusions** — what must not be reported.
- **Rule location** — where the requirement is written.

The rule locations are:

- `SKILL.md` — *Gate drawing-driven reconstruction*, gates 1–8, and *Scope of `result-confirmed`*.
- `references/drawing-reconstruction.md` — the reconstruction sections.
- `references/geometry-acceptance.md` — the acceptance sections.
- [drawing-feature-ledger.md](../assets/templates/drawing-feature-ledger.md) and [geometry-acceptance-report.md](../assets/templates/geometry-acceptance-report.md) — the record templates those rules are written into.

## R-01 — Reopen succeeds and the bounding box matches, but the hole pattern is wrong

**Input facts.** The part reopens without unloaded components, contains one solid body, and its overall bounding box matches the drawing to 0.000 mm. The drawing shows three radial holes on a 120° pattern. The model has four radial holes on a 90° pattern, drilled at the same diameter and depth.

**Required decision.** Judge the hole features `FAIL`: the quantity and the angular spacing conflict with the drawing. Record the defect as a non-conformance. The overall conclusion for the drawing requirement set is `FAILED`, because an applicable required check has failed.

**Forbidden conclusions.** "The model matches the drawing." "The part passed." Any overall `PASSED`. Restoring a matching bounding box, a single body, or a clean reopen does not restore the pattern, and the passing layers do not substitute for the failing one.

**Rule location.** `SKILL.md` gate 6 and *Scope of `result-confirmed`*; `references/geometry-acceptance.md` § *Acceptance layers*, § *Check methods and their evidence boundaries* (rotationally repeated features), § *Overall conclusion*.

## R-02 — The hole centre point is empty, but the diameter and depth were never measured

**Input facts.** A probe point on the axis of a nominal bore reports "outside the solid". No diameter, depth, through/blind state, or step geometry was measured.

**Required decision.** Report exactly what was established: the sampled point is not inside material. Record the diameter and depth checks as `NOT_RUN` or `BLOCKED`. The overall conclusion is at most `PARTIAL`.

**Forbidden conclusions.** "The hole diameter and depth are acceptable." "The bore is correct." An empty centre point is compatible with a wrong diameter, a wrong depth, a blind hole where a through hole was required, or entirely different geometry.

**Rule location.** `references/geometry-acceptance.md` § *Check methods and their evidence boundaries* (holes, point containment); `SKILL.md` gate 6.

## R-03 — One correct feature sets the envelope while another is clearly undersized

**Input facts.** A correctly modelled bottom flange defines the maximum width of the part, so the overall bounding box matches the drawing. An upper blade is visibly too small against its section, but it sits inside the envelope.

**Required decision.** Measure the blade against its own drawing dimensions and judge it on those, independently of the bounding box. The bounding-box check passes for what it covers and the blade check `FAIL`s its own scope.

**Forbidden conclusions.** "The overall envelope is correct, so the part is correct." A bounding box is a max/min over the whole body: a correct feature can carry it while every other feature is wrong.

**Rule location.** `references/geometry-acceptance.md` § *Check methods and their evidence boundaries* (bounding box); `SKILL.md` gate 6.

## R-04 — A radial Ø10H7 is rebuilt as an M10, or moved to the axial direction

**Input facts.** The drawing calls out a radial `Ø10H7` fit hole. The model contains a `M10` threaded feature at that location, or a `Ø10H7` drilled along the part axis instead of radially.

**Required decision.** Re-check the feature type, its position, and its direction against the drawing. Treat the type, the axis, and the position as three separate checks. The feature fails until all three agree.

**Forbidden conclusions.** "Both are 10, so it is equivalent." An `M10` and a `Ø10H7` are different feature types with different function, and a radial hole and an axial hole at the same nominal size are different features in different places.

**Rule location.** `references/drawing-reconstruction.md` § *Separate the confusions that get modelled wrong*; `references/geometry-acceptance.md` § *Check methods and their evidence boundaries* (holes).

## R-05 — The formula matches, but the angular unit or the parameter interval is undecided

**Input facts.** A curve is specified by a sine expression. The drawing does not make clear whether the argument is in degrees or radians, and the interval over which the curve applies is not stated. The model was built with one reading.

**Required decision.** Treat the curve's construction and its acceptance as `BLOCKED` on the missing information. Record the two possible readings and why they differ, and resolve the ambiguity before the feature is finalized. Continue with unrelated features if the task allows.

**Forbidden conclusions.** "The curve matches, because the expression is the same." The same `sin` expression with a different unit or interval is a different space curve. Silently choosing a default is the failure this case exists to prevent.

**Rule location.** `references/drawing-reconstruction.md` § *Curves and surfaces*; § *Handle ambiguity explicitly*; `SKILL.md` gate 4.

## R-06 — A mid-span bulge is removed by shrinking a control radius until the envelope passes

**Input facts.** A lofted surface bulges between its sections and pushes the overall envelope past the drawing's diameter. The control radius was reduced, with no basis in the drawing, until the bounding box came back within range.

**Required decision.** Require independent surface-deviation evidence: sample between the sections over a stated interval, compare against the drawing's intended law, and report the deviation and the interval covered. The bounding box is not that evidence. The adjusted control radius is an unsupported deviation from the drawing and is recorded as such.

**Forbidden conclusions.** "The envelope now matches, so the surface conforms." A change made only to satisfy an overall size check is not a drawing-based correction, and it must not be reported as conforming to the original drawing.

**Rule location.** `references/drawing-reconstruction.md` § *Curves and surfaces*; `references/geometry-acceptance.md` § *Check methods and their evidence boundaries* (free-form surfaces, bounding box).

## R-07 — Thread expression is decided by the delivery requirement, not by a default

Thread questions take three different shapes, and they end differently. None of them is settled by the mere presence or absence of a solid helical form.

### R-07a — The requirement already allows a nominal or symbolic expression

**Input facts.** The established delivery requirement allows threads to be carried nominally, symbolically, or as thread attributes. The model retains the information that requirement needs, and the agreed expression has been verified against it. No solid helical form was required.

**Required decision.** The absence of a solid helical form is not, on its own, a non-conformance. Judge the thread by the actual requirement and the actual evidence, and report the result that the evidence supports. Nothing was lowered, so this is not recorded as a simplification.

**Forbidden conclusions.** "It does not conform, because no solid thread form exists." Also forbidden in the other direction: declaring a pass merely because the requirement was permissive. The case states the requirement, not the measurement — the conclusion must come from the actual evidence for the agreed expression.

**Rule location.** `references/drawing-reconstruction.md` § *Separate the confusions that get modelled wrong* (branches 1 and 3).

### R-07b — A requirement that was in force was approved away

**Input facts.** The drawing marks threads, and the original delivery required a particular expression. The user later approves omitting it.

**Required decision.** Record the specific original requirement, the specific approval, who gave it, and when. Evaluate the drawing requirement set and the approved delivery requirement set separately: the drawing conclusion remains `FAILED` if the drawing requires what the model does not carry, while the approved delivery set is judged on its own terms.

**Forbidden conclusions.** "The part fully conforms to the drawing." Also forbidden: deleting the original requirement from the drawing record because it was approved away, or refusing the user's approval and insisting on the original expression. The representation delivered must be the one actually agreed.

**Rule location.** `references/drawing-reconstruction.md` § *Separate the confusions that get modelled wrong* (branch 2); `references/geometry-acceptance.md` § *Drawing conformance and approved-scope conformance*; `SKILL.md` gate 7.

### R-07c — Only a plain pilot hole exists

**Input facts.** A threaded feature is required. The model contains a plain pilot hole. There is no evidence of the required thread information or of an agreed expression.

**Required decision.** The thread is not established by the pilot hole's presence. Determine `FAIL`, `NOT_RUN`, or `BLOCKED` from the evidence that actually exists, and check the drawing requirement against the model.

**Forbidden conclusions.** "The thread is done because the pilot hole is there." Also forbidden: inventing a thread specification, depth, hand, or attribute that was never verified. `NOT_RUN` and `BLOCKED` are honest outcomes here; a fabricated `PASS` is not.

**Rule location.** `references/drawing-reconstruction.md` § *Separate the confusions that get modelled wrong* (branch 3); `references/geometry-acceptance.md` § *Check methods and their evidence boundaries*.

## R-08 — No screenshot is available, but reliable dimension and section evidence is

**Input facts.** NX cannot produce a screenshot in this environment. Verified analytic faces, dimensions, and section evidence for the current model are available and bound to the current file version.

**Required decision.** Judge each check on the coverage of the evidence that does exist, and state explicitly that the visual confirmation was not performed. The overall conclusion follows the normal rules: it is `PARTIAL` if required items remain unchecked, and it is not automatically `FAILED` merely because screenshots are missing.

**Forbidden conclusions.** "Visual inspection passed." Screenshots were never taken, so no visual check may be reported. Also forbidden: "verification failed because no image could be produced" — the absence of screenshots is not by itself a geometry failure.

**Rule location.** `references/geometry-acceptance.md` § *Check methods and their evidence boundaries* (views and sections); `SKILL.md` gate 6.

## R-09 — A read-only review finds the model is wrong

**Input facts.** The task was a read-only review. The review finds a defect in the model geometry.

**Required decision.** Report the defect with its evidence. Do not start a repair, do not save a modified part, and do not silently fix the model as part of "reviewing" it. Return the finding and let the user authorize a corrective build.

**Forbidden conclusions.** "The model was corrected." Also: "the model is fine" because the defect is inconvenient. A review's finding is the deliverable, and the authorized scope did not include writing to the model.

**Rule location.** `SKILL.md` *Apply the execution safety gate*; `references/drawing-reconstruction.md` § *Task scope* (reading and analysis do not authorize modeling, saving, or export).

## R-10 — A simple box with known dimensions

**Input facts.** The task is a rectangular block with three given dimensions and no other features.

**Required decision.** Keep the parameters and the check record in proportion to the task: the conversation, a short table, or the code's own configuration is enough, and no separate ledger file is required. Record the applicable dimensions, the unit, and the scope actually verified. Do not load the helix, thread, complex-section, or surface procedures, because none of them apply.

**Forbidden conclusions.** That the full complex-drawing protocol is required for every part — but equally, that a simple part may omit the parameters and the verification basis the task needs. "Condensed" never means "unverified": it means the record lives somewhere proportionate to the task.

**Rule location.** `SKILL.md` gate 3 and the step 4 routing note; `references/drawing-reconstruction.md` § *Build the drawing feature ledger*; [geometry-acceptance-report.md](../assets/templates/geometry-acceptance-report.md) header note; `references/geometry-acceptance.md` § *Acceptance layers* (unrelated layers are `N/A` with a stated reason).

## R-11 — Two views disagree about the same dimension

**Input facts.** A dimension appears on the main view and on a section, with different values. A model has already been built using one of the two values.

**Required decision.** Record the conflict, with both readings and their sources, before anything else. Treat the features the dimension controls as blocked from final build and from acceptance until the conflict is resolved. If the task can continue elsewhere, continue there.

**Forbidden conclusions.** "The dimension is the one the model already uses." Resolving a view conflict in favour of the existing model makes the model the authority over the drawing, which inverts the entire point of the acceptance.

**Rule location.** `references/drawing-reconstruction.md` § *Handle ambiguity explicitly*; [drawing-feature-ledger.md](../assets/templates/drawing-feature-ledger.md) § 5 (conflict table); `references/geometry-acceptance.md` § *Overall conclusion*.

## R-12 — Zero feature errors, one solid body, and a required feature is simply absent

**Input facts.** The model has one solid body and zero feature error messages and zero warnings. A relief groove that the drawing requires is not present in the model at all.

**Required decision.** Check the drawing's feature list against the model feature by feature, and judge the missing groove `FAIL` on its own check. Confirm the presence of each required feature by measuring it, not by the absence of errors.

**Forbidden conclusions.** "No feature errors, so the model is complete." A feature that was never created cannot produce an error message. Zero errors describes the features that exist and says nothing about the ones that do not.

**Rule location.** `SKILL.md` gates 3 and 6; `references/geometry-acceptance.md` § *Acceptance layers*, § *Check methods and their evidence boundaries* (fillets and chamfers); `references/drawing-reconstruction.md` § *Build the drawing feature ledger*.

## R-13 — A required feature is knowingly dropped with approval

**Input facts.** The drawing requires a slot. The model does not have it. The user explicitly approves omitting that slot for this delivery. Every other check in the approved delivery requirement set passes.

**Required decision.** Report both requirement sets. The approved delivery requirement set may be `PASSED`; the drawing requirement set is `FAILED`, because the drawing requires the slot and the model does not carry it. Record the approval basis and the excluded requirement.

**Forbidden conclusions.** Writing the drawing conclusion as `PASSED` because the delivery was approved without the slot. Also forbidden: deleting the slot requirement from the drawing record, and refusing the user's approval. The approved delivery set is never substituted for the drawing set.

**Rule location.** `SKILL.md` gate 7; [geometry-acceptance.md](geometry-acceptance.md) § *Requirement sets*, § *Drawing conformance and approved-scope conformance*; [geometry-acceptance-report.md](../assets/templates/geometry-acceptance-report.md) § 8 and § 9.

## R-14 — One feature is fully confirmed while an independent one has failed

**Input facts.** Every applicable required check on F001 passes. F002, an independent feature, has been confirmed as failing.

**Required decision.** Report F001's limited scope as confirmed, stating exactly what that scope covers. The whole-part drawing conclusion is `FAILED`. F002's failure stays prominent — in the non-conformance list, in the overall conclusion, and beside the confirmation.

**Forbidden conclusions.** "The model is confirmed", with no scope. Also forbidden in the other direction: withholding F001's legitimately verified local result merely because F002 failed, or letting the local confirmation bury the failure.

**Rule location.** [geometry-acceptance.md](geometry-acceptance.md) § *Requirement sets* (stated confirmation scope); `SKILL.md` gate 8 and *Scope of `result-confirmed`*; [geometry-acceptance-report.md](../assets/templates/geometry-acceptance-report.md) § 10.

## R-15 — A fully authorized end-to-end request

**Input facts.** The user asks for a part to be built from a drawing, verified, and saved to a named new file.

**Required decision.** Read the whole request and take the scopes it covers as authorized. Reading the drawing, planning, building, and the verification the flow needs proceed without asking for each stage over again. Ask only if the next step goes outside the request, if a target or destination is unclear, if an unauthorized object would be modified, or if a decision only the user can make changes the construction.

**Forbidden conclusions.** "Four separate authorizations are required, so modelling must wait for a further confirmation." Also forbidden in the other direction: reading a broad request as permission to overwrite an existing part, to export to an unnamed destination, or to skip the execution safety gate.

**Rule location.** `SKILL.md` gate 1 and *Apply the execution safety gate*; [drawing-reconstruction.md](drawing-reconstruction.md) § *Task scope*; [drawing-feature-ledger.md](../assets/templates/drawing-feature-ledger.md) § 1.

## R-16 — Read-only review of a model that already exists

**Input facts.** The user submits an existing model and asks for a read-only review. No drawing-based plan was ever written, and the model already exists.

**Required decision.** Rebuild the acceptance conditions from the original drawing or the applicable requirements, record that the review is retrospective together with the actual time, and disclose it if the model or its construction code had already been seen. Do not fabricate a pre-modeling plan. Do not modify or save the model. If the original drawing cannot be found, limited internal-consistency or specified-dimension checks may still be run and reported, without claiming full drawing conformance.

**Forbidden conclusions.** "A pre-modeling acceptance plan was followed", presented as if it had existed. Also forbidden: expected values read back out of the model or its construction code, a self-review described as blind testing, and starting a repair because the review found a defect.

**Rule location.** [drawing-reconstruction.md](drawing-reconstruction.md) § *Task scope*, § *Build the drawing feature ledger*; [geometry-acceptance.md](geometry-acceptance.md) § *Reviewing a model that already exists*; `SKILL.md` gate 5; [geometry-acceptance-report.md](../assets/templates/geometry-acceptance-report.md) § 2.

## R-17 — A closed remediation is not a re-check

**Input facts.** A check against the previous model version was `FAIL`. The model was then repaired. The remediation entry is marked `CLOSED`, but the check has not been re-run against the new version.

**Required decision.** Retain the old version's check as `FAIL`, together with its model version and evidence. For the new version, record `Check status: NOT_RUN`. Record `Remediation status: AWAITING_RECHECK`, explicitly noting that the previous `CLOSED` label was premature because no re-check had been performed. These are separate fields: neither the repair nor the remediation label establishes `PASS`. Determine the new version's overall conclusion from its own applicable checks; it must not reach `PASSED` while this required check remains unexecuted.

**Forbidden conclusions.** "Closing the remediation closed the failure." Also forbidden: overwriting the historical failure evidence with the new record, or treating the repair itself as evidence.

**Rule location.** [geometry-acceptance-report.md](../assets/templates/geometry-acceptance-report.md) § 6 and § 10; [geometry-acceptance.md](geometry-acceptance.md) § *Overall conclusion*.
