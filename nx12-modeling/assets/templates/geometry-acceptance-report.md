# Geometry acceptance report — {{PART_OR_TASK_NAME}}

<!--
What this template is
---------------------
This is an evidence organization tool. It is NOT an automatic geometry verifier:
filling it in does not measure anything, and no script produces this file. Every
value written here must come from a check that was actually run against the
artifact named in section 1, and every check records where its evidence lives.

This template is used proportionally to the task. A complex reconstruction with an
approval history uses all of it. A simple task whose dimensions the user already
supplied may keep the equivalent record in the conversation or in a short table.
A read-only review may use it to organize an answer; filling it in does not
authorize writing a new file into the user's directories.

Three vocabularies are used, and they are not interchangeable:

  Per-check status:    PASS | FAIL | NOT_RUN | BLOCKED | N/A          (section 4)
  Overall conclusion:  NOT_ASSESSED | PARTIAL | FAILED | PASSED       (sections 8, 9)
  Remediation status:  OPEN | IN_PROGRESS | AWAITING_RECHECK | CLOSED (section 6)

A remediation status tracks what is being done about a failure. It never
participates in a geometry pass judgement.

Placeholders are written as {{LIKE_THIS}}. Replace every one of them. A section
that does not apply is answered with "Not applicable: <reason>" -- never left
blank, and never defaulted to "all pass".
-->

## 1. Model and drawing identity

| Item | Value |
| --- | --- |
| Model path | {{ABSOLUTE_PATH}} |
| Saved version or file hash | {{HASH_AND_ALGORITHM, or "in-memory model, not saved"}} |
| NX version that produced it | {{VERSION_EVIDENCE_AND_ITS_SOURCE}} |
| Units | {{UNIT}} |
| Drawing source | {{DOCUMENT, REVISION, PAGE, VIEW}} |
| Modeling code version or hash | {{HASH, or "not applicable: model was not built by a script in this task"}} |
| Construction provenance | {{BLANK_PART_BUILD_OR_LOADED_COPY_REPAIR; INPUT_MODEL_HASH_IF_ANY; HELPER_CODE_REUSE_IF_ANY}} |
| Check code version or hash | {{HASH, or "not applicable: checks were performed by hand"}} |
| Expectation dataset and version | {{SOURCE_POINTS_CONDITIONS_AND_HASH; REPLACED_BASIS_IF_ANY}} |
| Feature ledger used | {{LEDGER_PATH_OR_ID}} |
| Acceptance run date and time | {{yyyy-MM-dd HH:mm}} |

If the evidence below describes an in-memory model or an earlier file version, say so here. It does not transfer automatically to a newer delivery artifact.

## 2. Scope of this acceptance

| Item | Value |
| --- | --- |
| What is being accepted | {{THE_FEATURES, DIMENSIONS, OR PROPERTIES IN SCOPE}} |
| Delivery scope | {{WHAT_THE_USER_REQUIRED, including any item that came from a requirement note rather than a view}} |
| Explicitly not in scope | {{EXCLUDED_ITEMS_AND_WHY}} |
| When the acceptance conditions were established | {{prospective — for a new build, before the model / retrospective — for a model that already existed}} |
| Time the conditions were established | {{yyyy-MM-dd HH:mm — the real time, not a backdated planning date}} |
| Where they are recorded | {{e.g. the ledger's section 7}} |
| Had the model or its construction code already been seen when the conditions were written? | {{YES / NO — if yes, say so plainly; this is disclosed, not presented as blind testing}} |
| Independence of this check | {{e.g. "same executor, re-checked against the original drawing using a different method"; state plainly that this is not blind testing}} |
| Cross-reading evidence | {{LEDGER_SECTION_4.1_OR_EQUIVALENT; relevant views, decisions and unresolved items, or reason not applicable}} |
| User acceptance | {{CONFIRMATION_SOURCE, TIME, ARTIFACT_AND_SCOPE / not yet received; separate from measured conformance}} |

Independence: a second process adds file-reopen independence only. It does not add independent drawing understanding or an independent algorithm, and a self-review is never described as a blind test.

## 3. Existing execution, compile, and API states

List each state separately. They are independent and none of them implies another. A state that was not reached is written as not reached, not omitted.

| State | Reached? | Evidence | What it does NOT establish |
| --- | --- | --- | --- |
| `scaffold` | {{YES / NO / N-A}} | {{LOCATION}} | {{...}} |
| `static-checked` | {{YES / NO / N-A}} | {{COMMAND_AND_LOG_LOCATION}} | That NXOpen members exist, or that the journal runs. |
| `api-evidence-checked` | {{YES / NO / N-A}} | {{WHICH_ENTRIES_WERE_VERIFIED_AND_HOW}} | {{Not granted automatically by any script; say which entries it covers, and that `apiTruthChecked` and `callCoverageChecked` remain conservative}} |
| `compiled` | {{YES / NO / N-A}} | {{COMPILER, ASSEMBLIES, LOG_LOCATION}} | That the journal runs, or that the selected overload is the intended one. |
| `executed-in-nx12` | {{YES / NO / N-A}} | {{NX VERSION, HOST, LOG LOCATION}} | That the geometry is correct. |
| `result-confirmed` | {{YES / NO / N-A}} | {{SCOPE AND EVIDENCE, per section 10}} | Anything outside the stated scope. |

A save that completed and a reopen that loaded the file are execution facts. They belong in the `executed-in-nx12` row and do not become geometry evidence.

## 4. Check table

Status values: `PASS` (suitable evidence exists and the condition is met), `FAIL` (actual evidence conflicts with the condition), `NOT_RUN`, `BLOCKED` (cannot be decided because specific information or a tool is missing), `N/A` (not applicable, reason written).

| check_id | feature_id | Basis (drawing source) | Expected and unit | Tolerance and its source | Method | Actual value or observation | Status | Evidence location | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A001 | {{F001}} | {{VIEW_DIMENSION_OR_NOTE}} | {{NOMINAL_AND_UNIT}} | {{DRAWING_TOLERANCE / NOMINAL_CAD_REQUIREMENT / MEASUREMENT_ERROR}} | {{HOW_IT_WAS_MEASURED, and against which artifact}} | {{WHAT_WAS_ACTUALLY_OBSERVED}} | {{PASS}} | {{LOG, SCREENSHOT, OR RECORD PATH}} | {{WHAT_THIS_CHECK_DOES_NOT_COVER}} |
| A002 | {{F005}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{FAIL}} | {{...}} | {{...}} |
| A003 | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{BLOCKED}} | {{...}} | {{SPECIFIC_MISSING_INFORMATION_OR_TOOL}} |

Method rules that must be visible in this table:

- For topology-sensitive features, state how the check distinguishes the plausible wrong interpretation recorded during cross-reading, including a swapped side where applicable. Record an available known-wrong comparison or its limitation; reference [the acceptance methods](../../references/geometry-acceptance.md#checks-that-distinguish-feature-interpretations).
- A hole centre reading "outside the solid" appears with its limitation stated: it proves the sample point is not in material, and does not establish diameter or depth.
- Bounding-box evidence is recorded with the limitation that it proves axis-aligned overall extents only. It never stands in for a diameter, a local dimension, or a surface check.
- Point-containment checks record which points were chosen and why, including any boundary, hole-wall, hole-bottom, or must-remain-material samples, and state that a fixed point count proves nothing by itself.
- Volume evidence is labelled as a supporting indicator, with the note that equal volumes do not prove equal shapes.
- Fillet and chamfer checks state which edges they act on; the absence of an NX error message is never recorded as evidence that a fillet exists.
- Surface checks state the parameter interval actually sampled and are not described as a full mathematical proof.
- Any visual confirmation that did not happen is written here as not performed. A screenshot, where one exists, does not prove a hidden internal cavity.
- For view comparisons, record the registered plane, viewing and screen axes, line type, and any boundary inset. Identify whether the measured object is cut material, a projected edge or a silhouette.

For sampled or interrupted runs, reconcile the following with the actual data under [completed measurements](../../references/geometry-acceptance.md#completed-measurements-and-comparable-results):

| Run / artifact / dataset | Expected coverage | Actual complete coverage and partial remainder | Terminal application result and output integrity | Checks supported and checks still uncompleted |
| --- | --- | --- | --- | --- |
| {{RUN_AND_HASHES}} | {{PLANES_LEVELS_RANGES_RECORDS}} | {{COUNTS_AND_RANGES_VERIFIED_FROM_DATA}} | {{LOG_MARKER_SCHEMA_LENGTH_AND_ANY_MISMATCH}} | {{CHECK_IDS_AND_LIMITS; EXISTING_STATUSES_ONLY}} |

## 5. Unchecked items

| check_id | feature_id | Requirement | Why it was not run | Consequence |
| --- | --- | --- | --- | --- |
| {{A0nn}} | {{F0nn}} | {{REQUIREMENT}} | {{NO_TOOL / NO_ACCESS / WAITING_ON_USER / TIME}} | {{WHAT_REMAINS_UNKNOWN_AND_WHY_THAT_BLOCKS_PASSED}} |

An item is not moved to `N/A` to reach `PASSED`. Inability to measure is not non-applicability.

## 6. Known non-conformances

| check_id | feature_id | Requirement | Observed | Deviation | Check status | Model version | Remediation status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {{A0nn}} | {{F0nn}} | {{EXPECTED}} | {{OBSERVED}} | {{MEASURED_DIFFERENCE_AND_UNIT}} | {{FAIL — one of PASS / FAIL / NOT_RUN / BLOCKED / N/A}} | {{the artifact this was observed on: saved version or hash}} | {{OPEN / IN_PROGRESS / AWAITING_RECHECK / CLOSED}} |

The two status columns record different things:

- **Check status** is a geometry result. It is one of the five per-check values, and nothing else. `OPEN` is not a check status.
- **Remediation status** is what is being done about the failure. It is `OPEN`, `IN_PROGRESS`, `AWAITING_RECHECK`, or `CLOSED`, and it does not take part in any geometry pass judgement.

Rules that keep the two apart:

- Setting a remediation status to `CLOSED` does not turn that check's `FAIL` into a `PASS`. Only a re-check produces a check status.
- After the model is modified, the check is run again **against the new version**. A repair is not evidence.
- The original failure record, the model version it was observed on, and its evidence are retained. A new record cites the new version and the new result; it never overwrites the historical failure evidence.
- If cross-reading changes an expectation, retain the old measurements and their original basis. Record the withdrawn or limited interpretation separately, identify the dependent checks and their replacements, and measure the new version. Explanatory labels do not replace a per-check status.
- A read-only review may record `OPEN` and stop there. Recording a remediation status does not authorize starting the repair.
- When this delivery does not track remediation, omit only the `Remediation status` column. Keep `Model version`, or replace that column with an explicit reference to an unambiguous artifact/version identifier recorded elsewhere in the report. Every non-conformance record must remain traceable to the model version on which it was observed. No script or mandatory remediation workflow is added for this.

List every known discrepancy here, including ones already being worked around, and ones found during a read-only review. A check left at `FAIL` is not offset by other checks passing, and a pass rate is never used to cancel a critical failure.

## 7. User-approved simplifications

| Item | Requirement the approval changes | What the model no longer carries | Approval source | Which requirement set this changes |
| --- | --- | --- | --- | --- |
| S001 | {{THE SPECIFIC REQUIREMENT THAT WAS IN FORCE AND WAS THEN APPROVED AWAY OR REPLACED}} | {{WHAT THE REQUIREMENT ASKED FOR THAT THE MODEL DOES NOT CARRY — a fact, not a pass/fail verdict}} | {{WHO_APPROVED_AND_WHEN}} | {{removed from the approved delivery requirement set; it stays in the drawing requirement set, and section 8 still judges it}} |

Only requirements that were in force and were then approved away or replaced belong here. An expression or simplification the delivery requirement already allowed is not an approved omission.

Approvals and the requirements they affect are kept in the record. They are not deleted once the work is closed.

## 8. Overall conclusion for the drawing requirement set

This section judges the **drawing requirement set only**: the applicable requirements of the drawing named in section 1, before any approval recorded in section 7 is applied. The approved delivery set is not substituted here.

`{{NOT_ASSESSED | PARTIAL | FAILED | PASSED}}`

Decide in this order:

1. Any applicable required check has `FAIL` → `FAILED`.
2. No `FAIL`, and no effective geometry check has been run → `NOT_ASSESSED`.
3. Some effective checks exist, but required items remain unexecuted, blocked, or without evidence → `PARTIAL`.
4. Every applicable required item has valid passing evidence, and no critical ambiguity is unresolved → `PASSED`.

How items in this set are handled:

- Evidence shows the requirement is not met → the check is `FAIL`, and this conclusion is `FAILED`. An approval in section 7 does **not** convert it to a `PASS` here.
- Not yet verified → `NOT_RUN` or `BLOCKED`. Do not manufacture a measured failure merely because an approval removed the requirement.
- Not applicable → `N/A`, with a real reason.
- Removed or replaced by an approval → still recorded here, marked as omitted by that approval. An approval changes the delivery; it does not change what the drawing requires.

State the reasoning in one or two sentences: {{WHY_THIS_CONCLUSION, naming the deciding checks}}. An empty checklist is not a `PASSED`, a checklist of nothing but `N/A` is not a measurement, and with the source drawing missing or the acceptance conditions incomplete this conclusion is not `PASSED`.

## 9. Overall conclusion for the approved delivery requirement set (if applicable)

This section judges the **approved delivery requirement set only**: the drawing requirement set after the approvals recorded in section 7. Write down:

- which requirements were excluded or replaced;
- which approvals are the basis for that; and
- which checks participate in this conclusion.

`{{NOT_ASSESSED | PARTIAL | FAILED | PASSED}}`

When evidence confirms that a feature required by the drawing was omitted with approval, and all remaining applicable requirements in the approved delivery requirement set pass with valid evidence and no unresolved critical ambiguity, the drawing requirement set in section 8 is `FAILED`, while the approved delivery requirement set in section 9 is `PASSED`. Report both conclusions explicitly. Approval does not convert the drawing-conformance failure into a pass.

A pass here is a pass of the reduced, approved scope. It is never summarized as "the whole part fully conforms to the drawing", and it never overrides section 8.

If no simplification was approved: "Not applicable: no approved simplification; section 8 is the only conclusion."

## 10. Basis for `result-confirmed`

| Item | Value |
| --- | --- |
| Is `result-confirmed` claimed? | {{YES / NO}} |
| Exact confirmation scope | {{THE_FEATURES, DIMENSIONS, OR PROPERTIES CONFIRMED — a stated scope, never "the whole part" by default}} |
| Requirement set this scope belongs to | {{drawing requirement set / approved delivery requirement set}} |
| Governing checks | {{THE check_ids INSIDE THAT SCOPE, all at PASS}} |
| Checks outside the scope | {{check_ids AT FAIL / NOT_RUN / BLOCKED, and where each is reported prominently}} |
| Evidence referenced | {{MODEL HASH, DRAWING SOURCE, LOG LOCATIONS, CHECK TIME}} |

The threshold is scoped, not global:

- Every applicable required check **inside the stated scope** must have a valid `PASS`. The claim does not require that every check elsewhere in the drawing passed.
- A `FAIL` outside the scope is retained and reported prominently — still listed in section 6, still visible in sections 8 and 9. It is not buried by the local confirmation, and it does not automatically cancel a different local scope that was independently and fully verified.
- With F001 fully passing and F002 failing: F001's limited scope may be reported as confirmed, the whole-part drawing conclusion is still `FAILED`, and no unscoped "the model is confirmed" wording may be used.

Still not evidence for this state:

- A journal that executed, a save that completed, or a reopen that loaded the file.
- A partial pass promoted to the whole part.
- An appearance-only approval extended to unmeasured internal cavities or unchecked dimensions.
- A check whose remediation status is `CLOSED` but which has not been re-run against the current model version.

A result that failed acceptance keeps its `executed-in-nx12` state; the execution is not hidden, and it does not become `result-confirmed`.

If no scope can be stated, or any applicable required check inside the claimed scope is other than `PASS`, this section is answered `NO` and the reason is stated here.
