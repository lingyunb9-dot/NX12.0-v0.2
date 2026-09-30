# Mandatory cross-reading before drawing-driven modeling

Use this procedure for reconstruction from a drawing and for checking a model against that drawing. For a new build, complete it before fixing a feature's 3D interpretation, deriving dependent dimensions, or writing its construction operations. For an existing model, record a retrospective review with the actual review time. A simple operation on dimensions already supplied by the user does not acquire a drawing-reconstruction workflow.

## 1. Read related views together

For each feature or related feature group, locate its relevant principal, side, end and section views. Follow section arrows and establish the observation direction before transferring a position or angle. Use dimensioned views and sections to constrain geometry; use an isometric view to help check correspondence and visible topology.

Record what each relevant view contributes. Two crops of the same view are not two independent geometric constraints. When only one usable view exists, record the missing evidence and assess whether the available dimensions and material relationships determine the feature. Do not invent another view or stop a fully determined feature merely to reach a view count. A critical unresolved interpretation blocks the affected feature; unrelated, settled work may continue.

## 2. Establish material relationships before choosing operations

Determine which regions contain material and which are empty, then identify the feature and choose add/remove operations. A diameter symbol identifies a diameter; by itself it does not distinguish a boss from a hole. A closed narrow outline can represent a raised strip or a cut slot.

For a feature whose interpretation could change its topology, keep the plausible alternatives until the drawing evidence distinguishes them. Write the observation that supports each alternative and the observation that would reject it. Keep the question at the unresolved level: asking whether a hole is through or blind is premature while a solid boss remains plausible.

Check quantity, connectivity and material preserved around the feature. A distance between two walls in a section becomes a complete circular cavity only when the related end view and circumferential material distribution support that interpretation. Retain separate feet, keys and fork ears where the views require them.

## 3. Trace dimensions into a common coordinate system

For each controlling dimension, retain this chain:

`printed value/symbol -> dimension-line or leader endpoints -> owning edge/face -> direction and datum -> 3D feature -> acceptance item`

Record axial, radial and tangential quantities separately, including a hole's own axis. Transform each view into the model coordinates rather than sharing paper angles. Record the start and end references of position dimensions; a chosen model origin does not change the drawing's datum.

State whether a value controls a local span, a radius/diameter, a pitch circle or an overall extent. Bind a radius to its actual leader and edge. Nearby numbers and similar-looking arcs do not establish ownership. Keep the evidence class of the numeric reading separate from the evidence class of its interpretation: an explicit diameter can still have an unresolved owner.

For curves and surfaces, establish the generating rule as well as its parameters: section shape and correspondence, axis, interval, units, hand, phase, thickness and end treatment. A guide-line pitch alone does not define the complete swept or lofted surface. See [drawing-reconstruction.md](drawing-reconstruction.md#curves-and-surfaces). A candidate construction or vector-derived value retains its stated basis and uncertainty.

## 4. Record the decision and its falsification check

Use the feature ledger's cross-reading record, or an equivalent compact record for a small task. Name the relevant views and observations, the interpretation selected, rejected alternatives where applicable, remaining uncertainty, and the check that could expose the wrong interpretation.

This step is complete only when the selected interpretation accounts for the relevant views, material distribution, dimension ownership and coordinate relationships, and the critical contradictions have been resolved for the authorized scope. A note saying only "cross-reading completed" is insufficient. If the user explicitly chooses a candidate or approximation, preserve the choice and its scope; it does not make the drawing uniquely determine that geometry. Ask only for an unresolved decision that the existing request has not already settled.

Choose acceptance expectations from the source views and checked dimension chains before using the model to measure them. The check must distinguish the plausible wrong interpretation, not merely detect a surface with the right radius. Use [geometry-acceptance.md](geometry-acceptance.md#checks-that-distinguish-feature-interpretations) for the methods. Cross-reading completion is a reasoning record, not a geometry `PASS` and not a script-generated verification state.

## 5. Revisit the interpretation when new evidence conflicts

For zero wall thickness, unexpected breakthrough, negative remaining wall thickness or disagreement between views, preserve the actual failure and rollback result, then revisit:

`material relationship -> dimension ownership -> direction/datum -> surface construction -> CAD tolerance or API behavior`

The exception describes the submitted geometry. It does not by itself establish a defect in the drawing. Keep nominal dimensions until the evidence supports a change; widening a rib to accommodate a misread hole can make the wrong geometry build successfully.

When an interpretation changes, identify its dependent features and checks. Preserve the original measurements with their artifact and original expectations; record which expectations are withdrawn or limited, derive replacements from the corrected reading, and recheck the new model. A withdrawn basis is an explanation about old evidence, not an additional geometry status or permission to erase a failure.

After the first complete build, inspect the actual model in the views that expose the high-risk features, including front/back and top/bottom where relevant. Check bosses, ear gaps, hole axes, keys and preserved feet against the drawing. Prefer native NX views when available, and bind screenshots to the actual artifact. If visual inspection is unavailable, disclose it and use suitable geometry/section evidence within its measured scope; follow [geometry-acceptance.md](geometry-acceptance.md#views-and-sections).

## Worked distinctions from the 2026-09-30 retrospective

These are lessons from an iteratively corrected, user-accepted SKDZ-01 delivery. They are not default dimensions or a reference answer for another drawing. Read any new drawing from its own evidence.

| Observed misinterpretation | Cross-reading that changes the decision | Check that discriminates |
| --- | --- | --- |
| A diameter was modeled as a hole where the sections supported a solid boss | Match the diameter's owner to material retained in the sections and the end outline | Material inside the boss, void in the surrounding relief, and the boss's axis and extent |
| A slanted closed strip was removed as a slot | Match its side relationship and section material to the surrounding relief | Material within the strip and void on the relief side, at drawing-derived locations |
| Opposed spans were turned into complete circular cavities | Combine the section levels with feet or keys shown in the end view | Preserved circumferential sectors, gaps, and axial levels |
| A fork became one solid lug with a radial hole | Separate axial height, tangential ear/gap widths and the transverse hole axis | Material in both ears, void in the gap and hole, correct hole axis and connectivity |

The accepted delivery's local checks, user acceptance and remaining manufacturing/surface limits are separate facts. The historical run used the predecessor skill; it is motivation for these rules, not evidence that version 0.2 has already passed a fresh modeling trial.
