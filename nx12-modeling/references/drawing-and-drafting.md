# Drawing and drafting discipline

Use this reference for sheets, views, dimensions, notes, symbols, tables, and drafting attributes — that is, for creating and editing 2D drawings and their annotations.

It is **not** the reference for reading an existing engineering drawing and rebuilding the 3D model it describes. That workflow is [drawing-reconstruction.md](drawing-reconstruction.md), and judging the rebuilt model against the drawing is [geometry-acceptance.md](geometry-acceptance.md). The two workflows share the drawing, not the procedure.

## Establish context

- Confirm whether the work part is the master model, drawing part, or an assembly component.
- Resolve the intended sheet and drawing view by user-confirmed semantic identity, not recorded indices.
- Confirm drafting standard, units, decimal precision, text style, layer, and destination view.
- Treat model annotations and drafting annotations as different workflows until NX 12 evidence confirms the required API.

## Preserve associativity

- Prefer associative references when the user expects annotations to follow geometry.
- Explain when an operation creates fixed geometry or loses associativity.
- Validate referenced edges, faces, points, and views before committing a dimension or symbol.
- Do not silently substitute the display view for the requested drawing view.

## Drafting API evidence

Drafting members are less consistently documented than modeling ones, so evidence matters more here, not less. Check every annotation, dimension, and view member with `scripts/check-api-evidence.py --nx-root <NX root>` before writing it. A `member-not-documented` result is a gap in the shipped documentation, not proof the member is absent — fall back to a same-version recording or the `NXOpen.Drawings` and `NXOpen.Annotations` members you can confirm.

Record `binding=dotnet` or `binding=python` on each evidence comment. The .NET XML documentation does not establish the Python spelling or overload of a drafting call.

## Recorded drafting journals

Journal recordings are valuable for builder order and style initialization. Remove hard-coded sheet numbers, view handles, annotation identifiers, screen coordinates, and selection indices. Replace them with explicit inputs or stable lookup rules. As with modeling, do not delete a recorded expression or annotation merely because the recording deletes it; confirm ownership and lifetime first.

## Safety

- Do not delete or replace existing sheets, notes, dimensions, or tables without explicit authorization.
- Detect an existing journal-owned annotation before creating a duplicate.
- Apply changes to one sheet or view first and report the result before scaling to the drawing set.
- Keep export, print, plot, and Teamcenter submission outside the default workflow.