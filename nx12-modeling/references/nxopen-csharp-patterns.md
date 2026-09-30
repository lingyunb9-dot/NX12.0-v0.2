# NXOpen C# patterns for NX 12

Use this reference for C# journals and compiled NXOpen utilities.

## Project and assembly rules

Verified on a real NX 12.0.0.27 installation:

- Reference `NXOpen.dll`, `NXOpen.Utilities.dll`, and `NXOpen.UF.dll` from the **same** installation that will run the code. All three live in `NXBIN\managed\`.
- **`NXOpen.dll` cannot be compiled against on its own.** NXOpen exposes base types such as `NXOpen.Utilities.BaseSession`, `NXOpen.TaggedObject`, and `NXOpen.TaggedObjectCollection` from `NXOpen.Utilities.dll`, so a source that names a `Session`, `Builder`, or `Part` fails with `CS0012` without it.
- NX 12 managed assemblies target **.NET Framework 4.0** (`ImageRuntimeVersion` `v4.0.30319`). Use the in-box .NET Framework compiler, not a modern .NET SDK.
- Some assemblies are not version evidence. `NXOpen.Guide.dll` reports file version `0.0.0.0`; only `NXOpen.dll` and `NXOpen.UF.dll` should decide whether an installation is NX 12.
- Keep assembly paths configurable and avoid committing copied Siemens DLLs.

## Compile check

```
.\validate-nx12-csharp.ps1 -SourceFile .\myjournal.cs -NxRoot 'E:\UG 12.0' -OutputDirectory .\.build
```

| Parameter | Purpose |
| --- | --- |
| `-SourceFile` | One or more C# files. Required. |
| `-NxRoot` | The installation that owns the assemblies. Required and never guessed. |
| `-OutputDirectory` | Where the assembly and logs go. The source directory is never written to. |
| `-Target` | `library` (default) or `exe`. |
| `-CompilerPath` | Explicit `csc.exe`. Never substituted for a different compiler. |
| `-SearchDepth` | Bounded search depth below the NX root. |
| `-Json` | Machine-readable result, also written to `nx12-csharp-result.json`. |

| Exit code | Outcome |
| --- | --- |
| 0 | `compiled` |
| 1 | `compile-failed` |
| 2 | `usage-error` |
| 3 | `skipped` — no usable .NET Framework C# compiler |
| 4 | `skipped` — the NX root has no required assemblies |
| 5 | `skipped` — the assemblies are not of the stated root or version |

The script never executes the produced assembly, never starts NX, and never borrows an assembly from another release to make a build pass. A `skipped` result is not a pass: it means the check could not be performed.

## Journal structure

Copy `assets/templates/csharp-journal.cs`. Preserve:

- A single `Session.GetSession()` call.
- Work/display part checks that fail before any mutation.
- A visible undo mark before mutation.
- Builder registration at creation and cleanup in `finally`, newest first.
- The original exception preserved with a bare `throw;`.
- Completed exception logging and a nonzero return code on failure.
- A compatible unload option for journal execution.

## Failure handling

The same contract as the Python template, expressed in C#:

- `Log()` never throws, so a diagnostic cannot hide the failure it reports.
- `DestroyBuilders()` never throws, and one failed `Destroy()` does not skip the rest.
- `UndoToMark()` never throws, so a failed rollback cannot replace the original exception.
- Builders are destroyed **before** the undo mark is restored, for the same reason as in Python: they were created after the mark.
- The original exception reaches the caller. `Main` reports it once, in full, and returns a nonzero code.
- The rollback outcome is recorded as it happens and read back by `Main`, which reports one of three states:
  - `not-attempted` — no `UndoToMark` call was made, for example because the journal failed before the undo mark was created. The log must not claim the part was rolled back.
  - `succeeded` — `UndoToMark` was called and returned normally.
  - `failed` — `UndoToMark` was called and threw. The rollback exception is kept and reported as a second, clearly labelled message; it never replaces the original failure.

`assets/templates/csharp-journal.cs` implements that contract. A fixed sentence such as "the part was rolled back" is wrong in two of the three cases, so the message is built from the recorded state.

`scripts/validate-journal.py` scans C# as comment- and string-stripped text. That is a review aid, **not** compilation and not syntax validation. Use it alongside `validate-nx12-csharp.ps1`, which actually compiles.

## What a passing compile establishes

It proves the source is valid C# 5 and that every named NXOpen type, member, and constant resolved against the assemblies of the named installation with argument lists the compiler accepted.

It does **not** prove:

- That the selected overload is the intended one. Overload resolution can pick a different overload when implicit conversions, optional parameters, or `params` arrays are involved.
- That the journal runs, or that NX accepts it. The assembly is never executed.
- That enum members, property types, builder sequences, and units are semantically correct.

Compiling and executing are different states and are recorded separately: `compiled` comes from this check, `executed-in-nx12` only from a real run in NX 12, and `result-confirmed` only from checking the resulting model. A `skipped` result is not a pass — it means the check could not be performed.

## Recorded code cleanup

Recorded C# is version evidence, not production structure. Keep the call order while replacing:

- Opaque journal identifiers.
- Recorded selection indices.
- Machine-specific paths.
- Repeated undo marks and UI noise.
- Numbered variables that obscure ownership and cleanup.

## Overloads and enums

Compilation catches missing members but can still select an unintended overload. Verify:

- Argument types and order.
- Enum declaring type and member.
- Builder property types.
- Commit return types and casts.
- Required references beyond `NXOpen.dll` and `NXOpen.UF.dll`.

Record the source of each overload-sensitive call with an evidence comment. Use `binding=dotnet` for C#: evidence read from `NXOpen.xml` proves the .NET binding directly, and says nothing about the Python spelling of the same call.
