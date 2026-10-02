# Drawing feature ledger — {{PART_OR_TASK_NAME}}

<!--
How to use this ledger
----------------------
This is the record of what the drawing was read to mean, so that an acceptance
check can be traced back to a printed dimension rather than to the build code.

There are two ways to fill it in. The record-timing field in section 1 says which
one applies:

  prospective  -- written before the model is built, for a new build or a plan.
  retrospective -- written after the fact, for a review of a model that already
                   exists. Do not invent a planning date or a pre-modeling plan
                   that was never written. Record the real time the conditions
                   were established, and disclose it if the model or its
                   construction code had already been seen.

How much of this template gets used is proportional to the task. A complex
reconstruction keeps the full structure with item-by-item traceability. A simple
task whose dimensions the user already supplied may keep the same information in
the conversation, in a short table, or in the code's configuration -- the record
is condensed, never absent, and the applicable dimensions, units, and verified
scope are still written down. A read-only task may use this template to organize
an answer; filling it in is not authorization to write a new report into the
user's directories.

Placeholders are written as {{LIKE_THIS}}. Replace every one of them. A section
that genuinely does not apply is answered with "Not applicable: <reason>" --
never left blank, and never filled with a default such as "all confirmed" or
"all pass". A placeholder that is still present means the work is unfinished.

Identifiers are stable: features are F001, F002, ... and acceptance items are
A001, A002, ... The numbers carry no fixed length and no fixed total; add as many
as the part needs. Every feature lists the acceptance items that judge it, and
every acceptance item lists the drawing requirement it comes from.
-->

## 1. Task scope and delivery target

| Item | Value |
| --- | --- |
| Record timing | {{prospective / retrospective — see the note above}} |
| Time this record was established | {{yyyy-MM-dd HH:mm}} |
| Requested scope | {{READ_ONLY_ANALYSIS / MODELING_PLAN / BUILD_IN_NX / ACCEPTANCE — list only what was actually requested}} |
| Delivery artifact | {{FILE_OR_NOTHING, e.g. a .prt, a journal, a written analysis}} |
| Save or export authorized | {{YES_WITH_NAMED_TARGET / NO}} |
| Part or assembly in scope | {{COMPONENT_NAMES}} |
| Explicitly out of scope | {{WHAT_THE_USER_EXCLUDED}} |

Record the scopes that were actually requested. A request that already covers reading the drawing, building, verifying, and saving to a named target authorizes that whole flow and is not re-confirmed stage by stage. A read-only request does not authorize modeling, saving, or export; a defect found while reading is a finding to report, not a licence to repair.

## 2. Drawing source

| Item | Value |
| --- | --- |
| Source document | {{FILE_OR_DRAWING_IDENTIFIER}} |
| Revision or date | {{REVISION}} |
| Pages used | {{PAGE_NUMBERS}} |
| Source class | {{DIMENSIONED_DRAWING / SECTION_VIEW / PHOTOGRAPH / OTHER — classify the source, not its display format}} |
| Provenance and inspected representation | {{VERIFIABLE_ORIGINAL_AND_PAGE -> EXISTING_RENDER_OR_OTHER_VIEW_ACTUALLY_INSPECTED}} |
| Annotation completeness and visibility | {{RELEVANT_DIMENSIONS_LEADERS_AND_SECTIONS_VISIBLE; ANY_MISSING_OR_UNREADABLE_ITEMS}} |
| Missing or unusable sources | {{WHAT_COULD_NOT_BE_READ_AND_WHY}} |

## 3. Coordinates, views, and units

| Item | Value |
| --- | --- |
| Units | {{UNIT, e.g. millimetre}} |
| Origin | {{WHERE_THE_ORIGIN_SITS_ON_THE_PART}} |
| X / Y / Z directions | {{AXIS_DEFINITIONS_AS_PRINTED}} |
| Axial and radial sense | {{WHICH_AXIS_IS_AXIAL_AND_WHAT_RADIAL_MEANS_HERE}} |
| Angular zero and positive direction | {{ZERO_POSITION_AND_SIGN}} |
| Circumferential repeat and spacing | {{COUNT_AND_ANGULAR_PITCH}} |

| View or section | Identifier | Observation direction | Basis for that direction |
| --- | --- | --- | --- |
| {{MAIN_VIEW}} | {{V1}} | {{LOOKING_ALONG...}} | {{PRINTED_ARROW / LABEL / PROJECTION_SYMBOL / INFERRED_AND_FLAGGED_AS_UNRESOLVED}} |
| {{SECTION}} | {{S1}} | {{...}} | {{...}} |

Projection method (first-angle or third-angle): {{METHOD_AND_THE_EVIDENCE_FOR_IT, or "unresolved: no basis on the sheet — recorded as an open question"}}.

## 4. Feature ledger

Basis class is one of: `explicit` (the drawing states it), `derived` (computed from stated conditions; write the derivation), `user-confirmed` (quote the confirmation), `unresolved` (evidence missing or conflicting). "It looks like" is not `explicit`, and an `unresolved` entry cannot be the foundation of a `derived` one.

| feature_id | Source (page / view / region) | Raw dimension or symbol | Geometry type | Add / remove / annotation | Qty | Position and direction | Size and unit | Depends on | Basis | Open question | Acceptance items |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F001 | {{PAGE_VIEW_REGION}} | {{AS_PRINTED, e.g. "Ø10H7" or "M10"}} | {{HOLE / SLOT / RIB / POCKET / BOSS / SURFACE / CHAMFER / ...}} | {{ADD / REMOVE / ANNOTATION}} | {{N}} | {{LOCATION_AND_AXIS}} | {{VALUE_AND_UNIT}} | {{F003, F007}} | {{explicit / derived / user-confirmed / unresolved}} | {{NONE, or the question}} | {{A001, A004}} |
| F002 | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} |

Feature-specific decisions that are easy to get wrong: state each one explicitly rather than leaving it implied — axial or radial; through, blind, counterbored, conical, or stepped; plain, fit, or threaded; radius, diameter, centre distance, or overall size; boss, rib, or pocket; a repeat pattern or the outline count in one view; reference or controlling dimension.

### 4.1 Cross-reading evidence and decision

For drawing-driven work, complete [mandatory cross-reading](../../references/cross-reading.md) before fixing the corresponding feature interpretation and operations. Link shared group evidence once where appropriate. For a small task, an equivalent compact record is sufficient; the actual view evidence and decision remain required.

| feature_id / group | Related views and each added constraint | Material, quantity and connectivity | Dimension ownership, direction and datum chain | Interpretation and rejected alternatives, if ambiguous | Remaining uncertainty and basis for proceeding or blocking | Acceptance items that distinguish the interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| {{F001}} | {{EACH_RELATED_VIEW_AND_ITS_CONSTRAINT; AVAILABLE_VIEW_LIMITATIONS}} | {{RETAINED_AND_EMPTY_REGIONS}} | {{RAW_MARK -> ENDPOINTS -> EDGE_OR_FACE -> DIRECTION_AND_DATUM -> LOCAL_OR_CIRCUMFERENTIAL_SCOPE}} | {{SELECTED_TYPE_AND_EVIDENCE_THAT_REJECTS_PLAUSIBLE_ALTERNATIVES}} | {{EVIDENCE_SUFFICIENT_FOR_SCOPE, INCLUDING_SINGLE_VIEW_BASIS_WHEN_USED / SPECIFIC_MISSING_EVIDENCE / EXPLICIT_USER_CHOICE_AND_SCOPE, in prose}} | {{A001, A004_AND_HOW_THEY_COULD_REJECT_THE_WRONG_TYPE}} |

Record the reading's actual timing in section 1. Keep the evidence class of the numeric value separate from that of its ownership/type when they differ. For a single-view decision, fill in the determining annotations, material relationships, geometric conditions and evidence excluding plausible alternatives as required by [cross-reading section 4](../../references/cross-reading.md#4-record-the-decision-and-its-falsification-check). State view limitations rather than inventing corroboration. Completion of this record is not a geometry `PASS`; the completion criterion and treatment of critical unresolved items are in the linked procedure.

### 4.2 Controlling dimensions and interpretation changes

For complex features, enumerate the controlling dimensions under the existing feature ID. Include unchanged requirements, every stepped segment and its boundaries, and derived values; do not list only known errors. A compact equivalent is sufficient for a small task.

| feature_id / dimension | Raw mark and source | Owner, direction, start/end datums | Numeric basis / ownership basis | Derivation or standard/construction provenance | Initial reading -> current reading and reason | Affected acceptance items |
| --- | --- | --- | --- | --- | --- | --- |
| {{F001 / DIMENSION_OR_SEGMENT_ID}} | {{AS_PRINTED_OR_NO_SEPARATE_PRINTED_VALUE; PAGE_VIEW_REGION}} | {{EDGE_FACE_AXIS_AND_FINITE_BOUNDARIES}} | {{CLASSIFY_VALUE_AND_OWNER_SEPARATELY}} | {{SOURCE_CHAIN_OR_STANDARD_BASIS; FLAG_CANDIDATE_OR_FIT}} | {{READINGS_ACTUAL_CHANGE_TIME_AND_EVIDENCE, or unchanged}} | {{A001_AND_REPLACEMENT_CHECK_IDS}} |

Vector/image measurement basis, if used: {{CALIBRATION_DIMENSION, PAGE_TRANSFORM, SCALE_AND_UNITS, RESIDUAL_AND_READING_UNCERTAINTY; HOW_DIFFERING_SCALES_WERE_RECONCILED}}. Keep thread type, root relief, internal bore, mating evidence and any inconsistent printed tolerance designation distinct. Preserve conditional user discussions as conditional until an actual choice or model change occurs; a revised interpretation is not a revised model. See [dimension tracing](../../references/cross-reading.md#3-trace-dimensions-into-a-common-coordinate-system).

Thread expression: {{WHAT THE ESTABLISHED DELIVERY REQUIREMENT ALLOWS OR REQUIRES FOR EACH THREADED FEATURE, AND WHAT THE MODEL ACTUALLY CARRIES}}. An expression that the requirement already allowed is not a simplification — record it here. If a requirement in force was later approved away or replaced, record that in section 6 instead.

## 5. Ambiguities and user confirmations

| Item | Question | Why it matters (what it would change) | Status | Resolution and who confirmed it |
| --- | --- | --- | --- | --- |
| Q001 | {{THE_AMBIGUITY_AS_NOTICED}} | {{QUANTITY / HOLE_TYPE / CONNECTIVITY / CRITICAL_DIMENSION / HELIX_HAND}} | {{OPEN / RESOLVED / BLOCKING}} | {{ANSWER, CONFIRMING_PARTY, AND DATE — or "none yet"}} |
| Q002 | {{...}} | {{...}} | {{...}} | {{...}} |

An open question that changes quantity, hole type, connectivity, a critical dimension, or helix hand keeps the features it governs out of the final build and out of acceptance. Work that does not depend on it may continue.

Conflicts found between views or dimensions at the same location:

| Item | Conflicting readings | Which features it affects | Status |
| --- | --- | --- | --- |
| C001 | {{READING_A_FROM_VIEW_X / READING_B_FROM_VIEW_Y}} | {{F00N}} | {{OPEN / RESOLVED_AS_RECORDED}} |

Do not resolve a conflict by silently choosing the reading that suits a model that already exists.

## 6. User-approved approximations and simplifications

| Item | Requirement the approval changes | What the model no longer carries | Approval source | Which requirement set this changes, and which checks still judge the delivery |
| --- | --- | --- | --- | --- |
| S001 | {{THE SPECIFIC REQUIREMENT THAT WAS IN FORCE AND WAS THEN APPROVED AWAY OR REPLACED}} | {{WHAT THE REQUIREMENT ASKED FOR THAT THE MODEL DOES NOT CARRY — stated as a fact, not as a pass/fail verdict}} | {{WHO_APPROVED_AND_WHEN}} | {{e.g. removed from the approved delivery requirement set; it stays in the drawing requirement set, and check A00n still judges the delivery}} |
| S002 | {{...}} | {{...}} | {{...}} | {{...}} |

This table is only for requirements that were in force and were then approved away or replaced. An expression or simplification the delivery requirement already allowed is not an approved omission and does not belong here.

An approved simplification is recorded, not absorbed. The approval basis and the requirements it affects stay in the record, and they remain in the drawing requirement set even after the delivery closes.

## 7. Key acceptance items for the drawing requirement set

Defined from the drawing for the **drawing requirement set**. For a prospective record these are written before the model is built; for a retrospective record they are rebuilt from the drawing, and section 1 carries the actual time. Either way each item is checkable and traces back to a printed requirement.

A requirement that an approval in section 6 removed or replaced stays listed here, marked as omitted. It is removed only from the approved delivery requirement set — the drawing still requires it.

| check_id | feature_id | Drawing requirement and its source | Expected value and unit | Tolerance and where it comes from | Check method | Status at definition time |
| --- | --- | --- | --- | --- | --- | --- |
| A001 | {{F001}} | {{VIEW_DIMENSION_OR_NOTE}} | {{NOMINAL_AND_UNIT}} | {{DRAWING_TOLERANCE / NOMINAL_CAD_REQUIREMENT / MEASUREMENT_ERROR — say which}} | {{HOW_IT_WILL_BE_MEASURED}} | {{DEFINED — not yet run}} |
| A002 | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} |

Keep drawing tolerances, the requirement that a CAD model be nominal, measurement error, and image-reading uncertainty separate. No tolerance is widened to make a check pass.

Note at definition time which required items are expected to be blocked by an open question from section 5, and which delivery properties will need visual confirmation that may not be available.
