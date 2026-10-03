# Drawing-driven reconstruction

Use this reference when an existing engineering drawing, section view, or dimensioned image must become NX 12 3D geometry. It covers reading the drawing into a checked feature ledger and building the model in stages.

Two neighbouring workflows are not this one:

- Creating or editing a 2D drawing, view, or annotation: [drawing-and-drafting.md](drawing-and-drafting.md).
- Deciding whether a finished model matches its drawing: [geometry-acceptance.md](geometry-acceptance.md).

Worked situations that exercise these rules are collected in [reconstruction-review-cases.md](reconstruction-review-cases.md).

Before fixing feature types, dependent dimensions or construction operations, complete [mandatory cross-reading](cross-reading.md). It defines the required evidence record, the completion criterion and the response when a later modeling failure challenges the reading.

## Task scope

Four scopes are easy to merge, and merging them is how an unrequested model gets saved — or how a legitimate request gets stalled:

| Scope | What it covers |
| --- | --- |
| Read-only drawing analysis | Reading the drawing and reporting what it shows. |
| Modeling plan or code generation | Producing a ledger, a plan, or a journal. |
| Actual construction in NX | Running that journal against an authorized target. |
| Acceptance of the built model | Measuring the built geometry against the drawing. |

They are scopes to keep distinct, not four permissions to collect one at a time. Read the whole request first and take the scopes it already covers as authorized. A user who asks for a model to be built from a drawing, verified, and saved to a named target has authorized that flow: reading the drawing, planning, building, and the verification the flow needs are all part of it, and none of them is asked for again.

The reverse holds too. Reading and analyzing a drawing does **not**, by itself, authorize modeling, saving, or export. If the request was to look at, explain, or read-only review the drawing, a defect found during that review is a finding to report, not a licence to repair it.

Ask when the next step goes beyond what was requested, when the target file or export destination is unclear, when an object that is not authorized would be overwritten or modified, or when a decision only the user can make changes the construction. Apply the execution safety gate in `SKILL.md` before anything modifies a part; the existing part-protection and save/export rules are unchanged.

Evidence classes are not interchangeable, but display format alone does not determine evidence quality. Record source provenance and annotation completeness separately from the representation used to view them. Photographs, appearance renderings and thumbnails that lack dimension annotations or have an unverifiable source support proportions and appearance, not checked drawing dimensions.

A rendering of an ODG, SVG or vector PDF from a verifiable original can preserve the drawing's dimensions, leaders and sections. Use a clear rendering with the relevant annotations intact for drawing interpretation, and check visible annotation ownership through [cross-reading](cross-reading.md#1-read-related-views-together). Values estimated from screenshot pixels retain image-reading uncertainty; displaying a drawing as pixels does not itself downgrade its legible printed dimensions. Keep numeric evidence and evidence for feature type or ownership separately classified.

## Establish coordinates and view relationships

Record these before writing any geometry:

- Units, and the unit of every dimension quoted.
- Origin, and X, Y, Z directions.
- The axial and radial sense, when the part is rotational.
- The observation direction of every principal view, auxiliary view, and section.
- The projection method — first-angle or third-angle — only when the drawing gives a basis for deciding it.
- The angular zero position, and which direction is positive.
- For a repeated circumferential pattern, the repeat count and the angular spacing.

Do not:

- Read four visible directions and assume four equal divisions.
- Treat geometry that an isometric view hides behind other geometry as absent.
- Apply a left/right or a rotation convention before the projection relationship is established.

If the angular zero is unmarked and the choice does not change the task, record the convention used and proceed. If the zero position would change how features assemble or where they sit relative to each other, resolve it first. Do not ask the user to approve every inconsequential coordinate choice; ask about the ones that move geometry.

## Build the drawing feature ledger

Build the ledger with [drawing-feature-ledger.md](../assets/templates/drawing-feature-ledger.md). For a new build it is written before the model; for a review of a model that already exists it is written retrospectively, and the template says how to record that. Either way the ledger records where each requirement came from, so a later check traces back to a printed dimension rather than to the build code.

How much record the task needs is proportional to the task:

- A complex reconstruction — sections, repeated structures, free-form surfaces — keeps the structured ledger, with drawing sources and item-by-item traceability. That is where a single misread entry multiplies.
- A simple task whose dimensions the user already supplied may keep the same information in the conversation, in a short table, or in the code's configuration, without a separate ledger file. The record is condensed, never absent: the applicable dimensions, units, and the scope actually verified are still written down.
- A read-only task may use the template to organize the answer. Reading the template does not authorize writing a new report into the user's directories; when the user asked for a saved report, save it where they authorized.

At minimum, each feature records:

- `feature_id`;
- source page, view or section, and a locatable region within it;
- the raw dimension or symbol as printed;
- geometry type;
- whether it adds material, removes material, or is an annotation property;
- quantity;
- position and direction;
- size and unit;
- dependencies on other features;
- basis class;
- questions still open;
- the acceptance item it maps to.

Link each feature to its cross-reading record. Preserve the dimension/leader endpoints, owning edge or face, direction, datum and local or circumferential scope for controlling dimensions. Classify the numeric reading and its geometric interpretation separately when their evidence differs; an explicit value does not make its assumed owner explicit.

The basis class is fixed to four values:

| Class | Meaning |
| --- | --- |
| `explicit` | The drawing states it. |
| `derived` | Computed from stated conditions, with the derivation written out. |
| `user-confirmed` | The user confirmed it; quote what was confirmed. |
| `unresolved` | Evidence is missing or conflicting. |

Two rules hold the ledger honest:

- "It looks like" is not `explicit`.
- An `unresolved` assumption cannot be the foundation of a `derived` entry.

Whichever form the record takes, a field that does not apply to this task is left out rather than filled with a default.

## Separate the confusions that get modelled wrong

These pairs are routinely conflated. Decide each one explicitly and record the decision:

- Axial holes and radial holes.
- Through, blind, counterbored, conical, and stepped holes.
- Plain holes, fit holes, and threaded holes.
- `M10` and `Ø10H7` — different feature types that share a number.
- Radius, diameter, hole centre distance, and overall envelope size.
- Bosses, ribs, and pockets.
- A circumferential repeat pattern and the number of outlines a projected view happens to show of it.
- Reference dimensions and controlling dimensions.
- A CAD nominal size and a manufacturing tolerance.
- Surface roughness and other requirements that constrain no shape.

Thread representation is decided by the delivery requirement, not by a default, and three situations end differently:

1. **The established delivery requirement allows a nominal, symbolic, or thread-attribute expression, and the model retains the information that requirement needs.** The absence of a solid helical form is then not, by itself, a non-conformance. Judge the thread by the actual requirement and the actual evidence. Do not record the choice of expression as "a simplification that lowered the requirement" — nothing was lowered.
2. **The original delivery required a particular expression and the user later approved omitting it.** Record the original requirement and the approval specifically, then evaluate the drawing requirement set and the approved delivery requirement set separately, as described in [geometry-acceptance.md](geometry-acceptance.md).
3. **Only a plain pilot hole exists, with no evidence of the required thread information or the agreed expression.** The thread is not established by the pilot hole's presence. Decide `FAIL`, `NOT_RUN`, or `BLOCKED` from the evidence that actually exists, and do not invent a thread specification, depth, hand, or attribute that was never verified.

In all three, "no solid helical form was built" does not by itself mean that a 2D thread callout may be dropped, that a thread specification is unnecessary, that the drawing necessarily fails, or that the drawing necessarily passes.

For a threaded projection, name the endpoints of each length: total projection, relief, chamfer, nominal cylindrical span and required full-thread or engagement interval. Derive only lengths supported by those endpoints. Total projection minus relief is not automatically full thread engagement; a chamfer or incomplete end turns can further limit it. Keep internal bore chamfers and external end chamfers attached to their own edges.

## Extracted drawing geometry

When measuring vector paths, record the page/view transform, rotation, scale, origin and units, and check their registration against the inspected rendering and known drawing marks. Evaluate curves on their parameterized paths; Bezier control handles are not boundary samples. Distinguish printed dimensions from vector-derived estimates, including fit residuals and sensitivity to a short or nearly straight arc. An unstable fitted radius supplies no controlling dimension. A leader landing inside a projected region identifies an annotation target only to the extent the other views support; it does not locate a unique 3D guide point.

## Curves and surfaces

Before a formula becomes geometry, record:

- The parameter definition, its range, and whether it is in degrees or radians.
- The coordinate mapping from the parameter into model space.
- Phase, start position, and end position.
- Whether the curve lies in a plane, on a cylinder, or in general space.
- Pitch or lead, and the hand of the helix.
- The section, the orientation of the section, and the thickness direction.
- How the surface connects to the neighbouring structure.

Then respect these limits:

- The same `sin` expression does not identify the same space curve. Amplitude, period, phase, axis, and start position all change the result.
- If the drawing does not make the angular unit clear, do not decide degrees or radians on your own.
- Lofting through a few sections does not automatically produce an accurate helical surface.
- A guide-line pitch alone does not determine section correspondence, a surface-generation rule or end treatment. Record those separately, and retain candidate constructions as candidates until their stated scope is established.
- Separate the section-motion law, the guide actually supplied to the builder, and helper curves added for display or diagnosis. Name the constrained section point/edge and verify the builder's actual input and resulting geometry; a feature name or a subsequently added helix is not evidence that it generated the surface.
- Distinguish fixed-plane rotating sections from sections normal to a path. Establish section orientation and point correspondence from the drawing, and keep a projected end outline distinct from an actual section before using either as a profile.
- Record the generating surface, trimming boundaries, retained material side and end treatments separately. A span or an envelope circle constrains its stated location; it does not define the same root or material boundary over the entire height. A candidate blend cannot replace a specified chamfer without a basis.
- The regions **between** sections need deviation checks as much as the sections themselves; that is where bulging appears.

A numeric approximation is allowed when it is justified. State the reference geometry, the error bound, the sampling strategy, and the result. It is not allowed to adjust a radius or a control point that has no basis in the drawing, purely to bring the overall bounding box into range, and then report the result as conforming to the drawing.

Interpret a failed parameter search within its tested construction family, source-point set, search range and objective. Failure of one fixed-section candidate does not establish that every fixed-section method fails, that a variable section is required, or that a printed pitch is wrong. Preserve these alternatives as unresolved when the evidence does not distinguish them.

## Handle ambiguity explicitly

- An ambiguity affecting quantity, hole type, connectivity, a critical dimension, or helix hand is isolated first. Do not quietly pick one reading.
- A requirement the drawing states clearly does not need the user's confirmation.
- A simplification the user approves is recorded as an approval, with what it excludes.
- When a view or a dimension conflicts with another at the same location, record the conflict. Do not silently choose the reading that happens to suit the model already built.

## Segment the build

Advance by related feature group — for example the main body, the bottom structure, the middle holes and slots, the upper structure, and the free-form surfaces. After each group, check it against the matching ledger entries before extending the build. A group that fails its check is not carried forward as an assumption.

When a material or dimension interpretation changes, revisit its dependent groups and acceptance conditions through [cross-reading](cross-reading.md#5-revisit-the-interpretation-when-new-evidence-conflicts). Preserve the old artifact and evidence; a successful repair does not retroactively validate the old reading.

Record whether each delivered artifact was built from a blank part or repaired from a loaded model copy, naming the input artifact when one exists and any helper code reused. A newly saved filename alone does not establish a blank rebuild. A curve network or diagnostic construction is delivered and judged as that artifact, without implying a completed solid.

Two habits to avoid:

- Treating a feature count or a boolean count (`139 features`, `69 booleans`) as a quality score. Those numbers say how much was done, not whether it is right.
- Copying one part's grouping onto another. Choose groups that match the task in front of you.
