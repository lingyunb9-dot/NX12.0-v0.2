# Geometry acceptance

Use this reference when a result must be judged against its drawing: model dimensions, topology, structure, or drawing conformance. It defines how to build the acceptance conditions, how to judge each check, and how to reach an overall conclusion that does not overstate what was measured.

Read [drawing-reconstruction.md](drawing-reconstruction.md) for the reconstruction workflow itself, and [reconstruction-review-cases.md](reconstruction-review-cases.md) for worked situations. Organize the written result with [geometry-acceptance-report.md](../assets/templates/geometry-acceptance-report.md).

This reference describes a reporting discipline. It is not an automatic geometry checker, and it does not add one.

## Acceptance conditions come before the implementation's conclusion

Derive the critical acceptance conditions from the drawing before the model exists. Write down what would count as passing, and against which view, section, or dimension. Record whether the conditions were established **prospectively** or **retrospectively** — a plan-timing classification only, described below, and not a geometry check status.

The modeling journal may share the checked nominal parameters with the acceptance work. What it must not do is supply the acceptance reasoning. A check that reads its expected values out of the same construction code it is testing tests nothing: it restates the model's assumptions, and an assumption that was wrong at build time is wrong at check time too.

### Reviewing a model that already exists

A request to check an existing model is a normal task, and it does not require inventing a plan that was never written. For a retrospective review:

- Rebuild the acceptance conditions from the original drawing or from the applicable requirements — not from the model.
- Do not derive expected values only from the construction code under test or from the model being checked. A value read back out of the artifact proves the artifact equals itself.
- Where it is practical, organize the drawing's requirements **before** reading the construction implementation in detail. Once the implementation has been read, that ordering cannot be recreated.
- If the model or its code has already been seen when the conditions are written, disclose that plainly. Do not describe the work as blind testing.
- Record the actual time the check conditions were established. It is the retrospection date, not a backdated planning date.
- When the original drawing cannot be found, limited internal-consistency checks and checks against specified dimensions may still be run and reported. No full drawing-conformance claim may be made from them.

A new build keeps the ordinary requirement: conditions first, model second.

For drawing-based conditions, complete [mandatory cross-reading](cross-reading.md) before treating a feature interpretation as the expected geometry. For a retrospective review, keep the actual timing and prior exposure visible.

### What "independent" does and does not mean

- Running the check in a second process buys independence in **file reopen**, and only that.
- It does not buy independent drawing understanding, and it does not buy an independent algorithm.
- A second model and a second person are not required.
- The same executor may re-check the result against the original drawing using a different check method. That is a legitimate cross-check.
- A single self-review must never be described as blind testing.

## Acceptance layers

Record these separately. A pass in one layer never substitutes for another:

1. The file opens and reopens.
2. Units, solid body type, and body count.
3. Local dimensions and positions.
4. The topology and connectivity of holes, slots, ribs, and cavities.
5. Curve and surface law.
6. Correspondence with views and sections.
7. Any other delivery property the user explicitly required.

An unrelated layer may be recorded as `N/A`, but it states why.

## Check methods and their evidence boundaries

### Checks that distinguish feature interpretations

Choose checks that would reject the plausible wrong interpretation identified in cross-reading. Radius, axis and position of a cylindrical surface alone can fit both an external boss and an internal hole. Combine them with material-side evidence, axial extent and connectivity. If using a face normal, verify its orientation relative to the solid on the target binding; a raw parametric surface normal is not automatically the outward solid normal.

For asymmetric holes on a common axis, test the signed interval and entry side in the registered view frame. Pair checks at the required side with checks that would reject swapping the features to the opposite side. A radius and an infinite axis line can match both arrangements. Derive this side assignment from the source views rather than copying the construction code's sign convention.

For a boss or raised strip, check material within it and void in the surrounding relief. For a fork, distinguish both ears, the central gap and the transverse bore. For keys or feet, check preserved sectors, intervening gaps and axial levels. Derive locations from source dimensions, then sample on appropriate sides away from boundary/tolerance ambiguity. Choosing points after observing the model merely to obtain passes does not establish conformance. These samples remain local evidence; use sections or surface-deviation checks between samples where required.

When a corrected reading invalidates an old expectation, preserve that measurement with its original artifact, expected value and result. Separately explain the withdrawn basis or limited scope, map affected checks to replacement expectations, and rerun against the new version. Such explanations do not add to the five per-check statuses and do not convert historical results into measurements of the new model.

When a known wrong artifact or measurement set is available within the authorized review scope, apply the corrected discriminating conditions to it as well as the repaired result, or show why the recorded wrong geometry would fail them. Retain both outcomes, distinguishing an executed rejection from an analytical expectation. If both pass, the proposed check has not distinguished that defect. If this comparison cannot be performed, disclose the missing evidence; do not invent a counterexample or make it a prerequisite for unrelated settled work.

### Holes

Check the diameter, the axis and its position, the depth, whether it is through or blind, any step or counterbore, and the repeat count and angular spacing for a pattern.

A point at a hole centre reading "outside the solid" proves exactly that: that this sample point is not inside the material. It does not establish the diameter and it does not establish the depth. A hole whose centre point is empty may be the wrong size, the wrong depth, blind where it should be through, or a different feature entirely.

### Slots, ribs, and cavities

Check the cross-section shape, the width and depth, the end profile, the position, whether material was kept or removed, and how the cavity connects to the rest of the part.

### Fillets and chamfers

Check whether the drawing requires them, whether a general note applies to this edge, their size, and which edges they actually act on. An operation that produced no NX error message is not evidence that a fillet was created.

### Rotationally repeated features

Check the count, the angular spacing, the phase, the shape of a single instance, and how each instance joins the main body. Counting outlines in a single projected view is not the same as measuring the pattern.

### Free-form surfaces

Check the parameter interval, the sections, the twist law, the deviation at intermediate positions, the extremes, the local thickness, and any self-intersection or unexpected bulge.

Any finite sampling states the range it covered. It is never described as a full mathematical proof over the whole surface.

### Bounding box

A bounding box proves the axis-aligned overall extents and nothing else. It does not prove a diameter, a local dimension, a position, or a surface deviation.

An ordinary box may be a loose enclosure. Before interpreting a discrepancy as a shape defect, consult [runtime-observations.md](runtime-observations.md#loose-bounding-boxes-around-spline-geometry) and verify the query's geometry and frame.

### Point containment

Choose sample points from the feature's own target boundaries: both sides of the boundary where useful, near the hole wall, near the hole bottom, and in material that the drawing says must remain. A fixed count of points is not a proof about the geometry, and the sample set must be reported so a reader can see what was and was not covered.

Do not write an NXOpen API example here from memory. Verify any call used for these checks through the normal evidence path in `SKILL.md` first.

### Volume

Volume is useful as a supporting indicator, from an independent derivation or a trustworthy reference. Equal volumes do not prove equal shapes.

### Views and sections

Check the key orthographic views and the related sections. When screenshots are unavailable, that does not make all geometry verification impossible: verified analytic faces, dimensions, and section evidence can still be used, and the visual confirmation that did not happen is stated as not done. A screenshot on its own does not prove that a hidden internal cavity is correct.

At the first complete build, use the [cross-reading review](cross-reading.md#5-revisit-the-interpretation-when-new-evidence-conflicts) to inspect high-risk material relationships in the actual model. Select views that expose the features rather than requiring the same screenshot set for every part.

Match the source and model plane origin/offset, normal, viewing direction, screen axes and compared line type before computing a deviation. Test cut material, projected rear edges and silhouettes with their corresponding geometry; a complete cut-plane material mask still says nothing about a rear edge it never samples. Record offsets used to avoid boundary ambiguity and distinguish nominal intersections from chamfered or inset sections.

### Completed measurements and comparable results

Before using an output file as evidence, reconcile its schema, expected and actual records, sampled planes/levels/ranges, and terminal application result. A process exit code or a nonempty file does not establish completion. For interrupted work, retain the partial file and log, identify complete and incomplete subsets from the data, and report uncompleted required checks using the existing statuses. A later successful run replaces only the measurements it actually repeated; it does not complete a different interrupted scan.

Version the expectations and measurement outputs when a scan window, source-point set, coordinate registration, method or threshold changes. Preserve the earlier failure with its original conditions. Explain a corrected condition from the source rather than expanding a window merely to obtain a pass. Compare errors or pass rates across runs only on matched datasets and criteria; state the optimization objective when quoting a best candidate. Curve serialization, sampled inverse-motion agreement and mesh distance each establish their own limited properties, not source conformity of a whole surface.

## Tolerances

Keep these four apart:

- The manufacturing tolerance stated on the drawing.
- The requirement that a CAD model be nominal.
- Measurement and algorithm error.
- Uncertainty from reading an image.

Do not widen a tolerance so that a check passes. A manufacturing tolerance permits a real part to deviate; it is not permission for the nominal CAD model to drift. A size estimated from a low-resolution image is not presented as a precise measurement.

## Status of each check

| Status | Meaning |
| --- | --- |
| `PASS` | Suitable evidence for this item exists and the condition is met. |
| `FAIL` | Actual evidence conflicts with the condition. |
| `NOT_RUN` | Not executed. |
| `BLOCKED` | Cannot be decided because specific information or a tool is missing. |
| `N/A` | Not applicable, with the reason written down. |

- A planned check is not an executed check.
- A blank is not a `PASS`.
- A simulated value is not a measured value.
- A test fixture's fake data is not NX measurement evidence.

## Requirement sets

Every overall conclusion belongs to exactly one requirement set. Three sets are involved, and conflating them is the defect this section exists to prevent:

| Set | What it is | What it is not |
| --- | --- | --- |
| **Drawing requirement set** | The applicable requirements for the part or object the user named, in the drawing the user named, fixed **before** any simplification approval is applied. | Not every object on the sheet, and not parts the user never asked about. |
| **Approved delivery requirement set** | The drawing requirement set after traceable user approvals explicitly exclude, replace, or add requirements. | Not a re-reading of the drawing. An approved omission changes the delivery, not what the drawing says. |
| **Stated confirmation scope** | The features, dimensions, or properties that one `result-confirmed` claim explicitly covers. | Not the whole part by default, and not a summary of whatever happened to pass. |

Rules that hold for the drawing requirement set:

- A requirement that does not apply is recorded as non-applicable **with its reason**.
- A requirement is never removed from this set because it was done wrong, or because it could not be checked. Failing and unverified requirements stay in it.
- An approved omission removes a requirement from the approved delivery set only. The requirement remains visible in the drawing set, marked as omitted by approval.

A request to build or continue a candidate authorizes that work; it changes a conformance requirement only if the user actually approves that specific change. Keep candidate execution, drawing failures and any explicit delivery exclusions distinct.

These are documentation concepts. They add no script field and no JSON contract.

## Overall conclusion

Judge **each requirement set separately**, in this order:

1. Any applicable required check has `FAIL` → `FAILED`.
2. No `FAIL`, and no effective geometry check has been run → `NOT_ASSESSED`.
3. Some effective checks exist, but required items remain unexecuted, blocked, or without evidence → `PARTIAL`.
4. Every applicable required item has valid passing evidence, and no critical ambiguity is unresolved → `PASSED`.

| Conclusion | Meaning |
| --- | --- |
| `NOT_ASSESSED` | No effective geometry check has been run for this set. |
| `FAILED` | At least one applicable required check in this set has a `FAIL`. Unchecked items do not hide it. |
| `PARTIAL` | No such `FAIL`, but required items in this set are still unchecked, blocked, or lack evidence. |
| `PASSED` | Every applicable required item in this set has valid passing evidence, and no critical ambiguity remains. |

Ways this conclusion gets abused, and the rule that closes each:

- Reclassifying a failing item as `N/A` to reach `PASSED` is not allowed. `N/A` states why the item does not apply; inability to measure is not non-applicability.
- A pass rate or a majority does not offset a critical failure.
- An empty checklist is not a `PASSED`. A list of nothing but `N/A` entries is not a measurement either: a hollow checklist does not certify the part.
- An artificially trimmed checklist — requirements dropped because they were inconvenient rather than because they do not apply — is the empty-checklist case in disguise.
- With the original drawing missing or the acceptance conditions incomplete, the set cannot reach `PASSED`.

### Drawing conformance and approved-scope conformance

When the user approved a simplification, report **two** conclusions, each against its own set:

- conformance to the **drawing requirement set**; and
- conformance to the **approved delivery requirement set**.

Both are legitimate, and they may differ. A drawing conclusion of `FAILED` together with an approved-delivery conclusion of `PASSED` is a normal and expected pair when a required feature was knowingly dropped: the drawing still requires it, and the approved delivery does not. Write both out; neither is a waiver of the other.

What must not happen:

- The approved delivery set is never substituted for the drawing set. A pass on the reduced scope is not a pass on the drawing.
- The pair is never summarized as "the whole part fully conforms to the drawing".
- The approval basis and the excluded requirements stay in the record; they are not deleted once the delivery closes.

`result-confirmed` is used only when its scope is stated and the corresponding acceptance conditions are met. The per-check and overall vocabulary above is a task-report convention: it does not change any script's JSON output, and no existing script grants it automatically.

## Bind the evidence to the delivery

An acceptance result is attached to specific artifacts. Record:

- The model path, and the saved version or hash.
- The drawing source, with page and view.
- The modeling code version or hash, when there is one.
- The construction provenance and input artifact, for a rebuild, code reuse or local repair.
- The check code version or hash, when there is one.
- The expectation dataset/version, coordinate registration and actual completed coverage.
- The actual time the check ran.
- The actual result.
- Where the logs, screenshots, or measurement records are.

When the evidence describes only an in-memory model or an earlier file version, say so explicitly. It does not transfer automatically to a newer delivery artifact.

Record user acceptance with its time, source, artifact and stated scope, separately from measured conformance. A later user acceptance can complete the requested delivery while documented surface/manufacturing limits remain. Preserve earlier awaiting-acceptance records as history and report the latest confirmation; do not present the old stage as the current task status or silently upgrade unmeasured requirements to `PASS`.
