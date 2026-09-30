# NX 12 environment

Use this reference when discovering an installation, choosing a runtime, or configuring a project.

## Installation discovery

Do not assume a fixed drive or folder. Prefer evidence in this order:

1. A root supplied by the user.
2. `UGII_BASE_DIR`, `UGII_ROOT_DIR`, and other variables inherited by the NX process.
3. The location of `ugraf.exe`, `run_journal.exe`, `NXOpen.dll`, and `NXOpen.UF.dll`.
4. Common installation folders as search hints only.

Run `scripts/inspect-nx-installation.ps1` on Windows. It is read-only: it does not modify the registry, PATH, environment variables, licensing, or NX configuration.

```
.\inspect-nx-installation.ps1                       # text report
.\inspect-nx-installation.ps1 -NxRoot 'E:\UG 12.0' -Json
```

| Exit code | Meaning |
| --- | --- |
| 0 | Exactly one candidate was confirmed as NX 12; `selectedRoot` is populated. |
| 1 | No candidate installation was found. |
| 2 | Usage error. |
| 3 | Candidates were found, but none could be confirmed as NX 12. |
| 4 | More than one candidate was confirmed. The script does not choose one; select a root explicitly with `-NxRoot`. |
| 5 | Conflicting version evidence. No root is selected. |

A directory whose path contains `NX12` is a **hint only**. A candidate is confirmed as NX 12 only when file version evidence reports major version 12 and nothing authoritative contradicts it. Confirmation, `not-nx12`, `candidate-unconfirmed`, and `not-found` are reported as distinct outcomes.

An unknown version is unverified, not NX 12.

## Layout facts verified on a real NX 12.0.0.27 installation

Confirm these locally rather than assuming them, but they explain why the scripts probe instead of hard-coding:

| Item | Location |
| --- | --- |
| `ugraf.exe` | `UGII\` and `NXBIN\` |
| `run_journal.exe` | `NXBIN\` |
| `NXOpen.dll`, `NXOpen.UF.dll` | `NXBIN\managed\` — **not** `NXBIN\` itself |
| `NXOpen.xml`, `NXOpen.UF.xml` | `NXBIN\managed\`, beside the assemblies |
| Embedded Python | `NXBIN\python\python36.dll` — version **3.6.1** |
| Python NXOpen bindings | `NXBIN\python\NXOpen*.pyd` |

`run_journal.exe`, `NXOpen.dll`, and the XML index each carry a Win32 file version matching the release, which is what the inspector reads as evidence.

## Runtime boundaries

- **NX 12 embeds Python 3.6.1.** Journals run on that interpreter, not on whatever Python is installed on the workstation. Syntax and standard-library availability are decided by 3.6: f-strings and variable annotations are fine, assignment expressions (`:=`), `match`, and `dataclasses` are not.
- The host Python that runs `validate-journal.py`, `check-api-evidence.py`, and the tests is a different interpreter. A successful parse on the host does not prove the target accepts the syntax, so `validate-journal.py` checks constructs against Python 3.6 explicitly and reports both versions.
- The NXOpen MCP or indexing service is a separate process. Its Python requirement does not determine the language level supported by the embedded journal runtime.
- Probe the actual runtime with `scripts/probe-nx12-api.py` before relying on a newer language feature.
- Compile C# against the `NXOpen.dll` and `NXOpen.UF.dll` from the same installation that will execute the journal. Do not copy assemblies between NX releases to make a build pass.
- NX 12 managed assemblies target **.NET Framework 4.0** (`ImageRuntimeVersion` `v4.0.30319`). Do not retarget to a modern .NET runtime to make a build succeed; that hides a real compatibility requirement.

## Project configuration

For C#:

- Use a compiler compatible with the installed NX 12 environment. A .NET Framework `csc.exe` is the appropriate toolchain; a modern .NET SDK is not a substitute.
- Reference local assemblies through configurable paths rather than committing machine-specific hint paths.
- Keep `Copy Local` disabled for Siemens assemblies unless the deployment procedure requires otherwise.
- Use `scripts/validate-nx12-csharp.ps1` for a compile check when the local installation is available. It reports `compiled`, `compile-failed`, or `skipped`, and a successful compile proves only that the code compiled.

For Python:

- Start from `assets/templates/python-journal.py`.
- Avoid assignment expressions, `match`, positional-only parameters, and modules added after Python 3.6 until the interpreter has actually been probed.
- Use `scripts/probe-nx12-api.py` inside NX to confirm version evidence and resolve dotted API paths without modifying the work part. On a real NX 12 session `Session.GetEnvironmentVariableValue("UGII_VERSION")` returns `v12`, so a leading `v` is a normal version spelling, not a parse failure; the probe accepts `v12`/`V12`/`v12.0.0.27` and still refuses `v120`, `v2312` and anything with trailing text. Read the probe's logical status from the complete `PROBE-RESULT:` JSON record: the host process exit code says only whether the host ran the script, and is not the probe's result.

## Required preflight facts

Before claiming a journal is ready to run, record:

- NX product or file version evidence, and where it came from.
- NX root, and the source that identified it.
- Journal language, and the runtime or compiler evidence for it.
- Work part type, unit system, and whether it is a new blank part or a disposable copy.
- API validation source and date, and whether an index was actually consulted.
