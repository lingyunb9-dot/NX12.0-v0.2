# NX12 observations requiring task-specific verification

Consult this reference when using symbolic threads or using a bounding box to judge shape. These observations come from the SKDZ-01 run on NX 12.0.0.27 documented on 2026-09-30. They are bounded observations from that installation and workflow, not universal NX behavior or proof of a particular overload. Verify the actual binding and calls through [api-validation.md](api-validation.md).

The face-bound observation below additionally comes from the 2026-10-03 reconstruction reports and retained query outputs. Its endpoint numbers and outcome are case evidence, not a new API guarantee.

## Symbolic thread changes and readback

The recorded native symbolic-thread operation changed a nominal diameter of 30 to 29.732; internal/external type readback was unreliable in that run. Restoring the nominal cylinder did not independently certify the final symbolic feature's face association.

Measure the supporting geometry before and after creating the thread. Check the final feature's association, axis, location, designation and required representation against the saved artifact. Resolve any mismatch using observed geometry and a verified same-installation call sequence; do not hard-code 29.732 as a correction or treat a plausible label as proof of a correct association. Keep unresolved representation/association evidence explicit.

A conflict between a thread designation and the drawn material relationship is a drawing/requirement question; a surprising API readback is a separate runtime question. Record a user's exact choice without silently declaring all original callout conditions consistent. Apply [drawing-reconstruction.md](drawing-reconstruction.md#separate-the-confusions-that-get-modelled-wrong) for the required thread representation and [geometry-acceptance.md](geometry-acceptance.md#requirement-sets) for its acceptance scope.

## Loose bounding boxes around spline geometry

The recorded ordinary bounding box extended beyond the part's checked envelope; the report attributed this to the underlying spline surfaces. A separately queried exact envelope was 98 by 98 by 136 mm. Those values belong only to that artifact.

When an ordinary box conflicts with analytic dimensions or visible shape, identify the query, coordinate frame and trimmed geometry it measures. Verify an appropriate exact-envelope query on the target installation, and corroborate relevant dimensions with analytic faces or sections. Confirm availability, signature and meaning before using an API such as `AskBoundingBoxExact`.

Do not reshape a surface solely to make a loose box match the target. Even an exact envelope proves extents only; use the dimensional, material and surface checks in [geometry-acceptance.md](geometry-acceptance.md) for local conformance.

In the later threaded-interface readback, the face-data box suggested axial bounds of about 37.1542 to 45.8762; the separately checked trimmed face envelope gave 38 to 45. Identify whether a query returns a loose surface enclosure, a trimmed-face envelope or the part envelope before deriving a local length. Corroborate the intended endpoint faces and axis, preserve the misleading first readback, and verify an exact query on the target installation rather than assuming every returned box is a physical edge measurement.
