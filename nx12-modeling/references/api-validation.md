# NX 12 API validation

Use positive evidence. A member is not NX 12-compatible merely because it is absent from a later-version blacklist.

## Evidence hierarchy

1. **Local NX 12 XML/DLL index**: exact type, member, overload, and enum lookup from the target installation. `scripts/check-api-evidence.py --nx-root <NX root>` reads it directly.
2. **NX 12 Python stubs** (`nx12-nxopen-pyi`): Python names, inheritance, properties, and signatures. Confirm runtime behaviour when wrappers or overloads stay ambiguous.
3. **Same-installation Journal recording**: strong behavioural evidence for call order. Clean the recording before reuse.
4. **NX 12-targeted example**: accept only after checking its stated version and its members against the local installation.
5. **Community or later-release example**: use only to discover search terms. Never treat it as proof.

The .NET XML and DLL files document the **.NET binding**. They do not by themselves establish Python names or Python overloads. Check those against Python stubs or the target runtime.

`scripts/check-api-evidence.py` enforces that boundary rather than ignoring it: when an entry declares `binding=python` and the index in use is the .NET XML, the entry is reported as unverified, the declared value is left exactly as written, and the entry is not counted as a documented match. The warning is not silenced by rewriting `python` to `dotnet` — the difference is the finding.

## Required evidence comments

Place a comment beside each nontrivial call:

```python
# NX12-API: NXOpen.Features.ExtrudeBuilder.Commit | source=local-xml | file=NXBIN/managed/NXOpen.xml | version=12.0.0.27 | binding=dotnet | status=verified-local
feature = extrude_builder.Commit()
```

```csharp
// NX12-API: NXOpen.Builder.Commit | source=local-xml | file=NXBIN/managed/NXOpen.xml | version=12.0.0.27 | binding=dotnet | status=verified-local
NXObject committed = extrudeBuilder.Commit();
```

Format:

```
NX12-API: <MemberPath> | source=<source> | binding=<dotnet|python> | version=<x.y.z> [| file=<index or file>] [| status=<status>]
```

* `<MemberPath>` — required. The dotted path being claimed, starting with `NXOpen`.
* `source` — required. One of `local-xml`, `local-index`, `nxopen-mcp`, `pyi-stub`, `recorded-journal`, `nx12-example`, `manual`.
* `binding` — required. `dotnet` or `python`. A signature checked in one binding says nothing about the other.
* `version` — required. The NX version the evidence came from, for example `12.0.0.27`.
* `file` — required when `source` is `local-xml` or `local-index`. `source=local-xml` alone does not say which index was read, so it is not accepted as complete evidence.
* `status` — optional. `verified-local`, `verified-stub`, `verified-recording`, `inferred`, or `unverified`.

Placeholder values (`TODO`, `TBD`, `N/A`, `unknown`, `none`, or empty) are rejected in `ready` mode. An evidence comment that is not filled in is not evidence.

## What the local index can prove, and what it cannot

Verified against a real NX 12.0.0.27 installation, the shipped `NXOpen.xml` documentation is **incomplete**:

* `NXOpen.Session.GetSession` exists in the assembly and in Siemens' own samples, but has no XML entry at all.
* Inherited members are documented on the declaring base type only. `NXOpen.Features.ExtrudeBuilder.Commit` appears as `NXOpen.Builder.Commit`.
* `NXOpen.UF.UFConstants` is documented, but none of its fields are.

A missing entry therefore means **not documented**, never **does not exist**. `scripts/check-api-evidence.py` reports these lookup outcomes separately:

| Outcome | Meaning |
| --- | --- |
| `member-documented` | Documented on the named type. |
| `type-documented` | The path names a documented type. |
| `member-declared-elsewhere` | Not on the named type; a same-named member is documented elsewhere, usually a base class. Shown as a lead, in heuristic order, with the total count. |
| `member-not-documented` | The type is documented, the member is not. Not proof of absence. |
| `type-not-documented` | The type is not documented. Not proof of absence. |

An evidence comment claiming `status=verified-local` while the index reports anything other than `member-documented` or `type-documented` is reported as **not corroborated** (`evidence-not-corroborated`), in wording that says the index is incomplete and another source is needed. It is not reported as a contradiction, because an incomplete index is not proof of absence.

Contradiction wording is reserved for claims that really are inconsistent with what was loaded:

* the evidence version names another release (`evidence-version-not-nx12`);
* the declared source file does not exist (`evidence-source-missing`), or exists but was not one of the files this run loaded (`evidence-source-not-loaded`);
* the member is recorded only in a different XML file than the one the evidence names (`evidence-source-mismatch`).

## What is checked per entry, and what is not

For each `NX12-API` comment:

1. **Structure** — `member`, `source`, `binding` and `version`, plus `file` when the source is `local-xml` or `local-index`.
2. **Documentation** — whether the named member is recorded in the index that was loaded.
3. **Version** — the leading component must be 12: `version=2312.0.0` and `version=120.0` are errors, because those name different releases. The declared version is then compared with the version of the index actually loaded, padding missing trailing components with zero, so `12.0` equals `12.0.0.0` but not `12.0.0.27`. A differing patch level, an index from another release, and an index whose version cannot be read are each reported as **not a confirmed match**, never as a version match.
4. **Binding** — the shipped XML is .NET documentation and can only speak for `binding=dotnet`. A `binding=python` claim is reported as unverified against it, and .NET evidence cited from a Python file is kept as a reference that does not prove the Python binding. The declared value is never rewritten to make the warning go away.
5. **Source file** — an absolute `file` is used as written; a relative one is resolved against `--nx-root` when that was given, and otherwise against the directory of the journal being checked. The file must exist **and** be one of the XML files this run loaded. When several XML files were loaded, the member must be recorded in the file the evidence names: being found in a sibling file does not certify it. Paths are normalized and compared case-insensitively, so `NXBIN\managed\NXOpen.xml` and `nxbin\managed\NXOpen.xml` are the same file.

Sources with no local verifier here — `local-index`, `pyi-stub`, `recorded-journal`, `nxopen-mcp`, `nx12-example`, `manual` — are marked as not locally checked. Their format is validated, and a same-named XML entry is never used to certify them.

`documentedEntryCount` counts entries that passed all five checks above. It is a count of **comments**, not of calls: no call in the code is ever mapped to an evidence entry. Loading an index does not mean the file's calls were checked, so neither script grants file-level `api-evidence-checked` or `apiTruthChecked` — both stay `false`, and `callCoverageChecked` records that no coverage claim is being made.

An evidence comment naming a member the index does not document is a gap in the evidence, reported as `member-not-documented` or `type-not-documented`. It needs another source: a Python stub, a journal recorded in the same installation, or a runtime probe.

## Validation sequence

1. List the proposed NXOpen classes, builders, members, enums, and overload-sensitive calls.
2. Resolve them against the local index or MCP before writing the implementation.
3. Check Python-only names against the NX 12 stubs.
4. Compare builder order with a same-version recording when feature construction is involved.
5. Write the smallest journal that proves the call sequence.
6. Run `scripts/validate-journal.py --mode ready`, and `scripts/check-api-evidence.py --nx-root <NX root>` when an index is available.
7. Compile C# with `scripts/validate-nx12-csharp.ps1`. A passing compile proves the source is valid C# and that every named type, member and constant resolved against the assemblies of the named installation. It is **not** execution, and it does not prove the journal runs or that the model is correct.
8. Execute only in a clean disposable part, after the safety gate in `SKILL.md` passes. Until that happens the journal is at most `static-checked`, and any C# is at most `compiled`.
9. Record failures with the NX version, exception text, failing call, and part context.

## Runtime probing

`scripts/probe-nx12-api.py` runs inside NX and reports three things separately:

* **Version state** — parsed structurally. `UGII_VERSION=120` is major 120, not 12. A real NX 12 session reports `UGII_VERSION=v12` through `Session.GetEnvironmentVariableValue`, so a leading `v`/`V` is accepted, and the rest of the string must still be a whole version: `v12`, `V12`, `v12.0.0.27` and ` 12 ` parse to major 12, while `v120`, `v2312`, `NX12`, `E:\UG 12.0`, `v12junk` and `v12.` do not parse to 12. A path containing `NX12` is a hint and never overrides a version field. Conflicting or missing evidence yields `unverified`.
* **Python runtime** — `sys.version`, `sys.version_info`, executable, and pointer size, so language-level decisions rest on the interpreter that will actually run the journal.
* **Name resolution** — a dotted path resolved with `getattr` and, where needed, a submodule import. A submodule that simply had not been imported yet is reported as `resolved-after-import`, not as a missing API.

The probe never invokes the member it is probing, so it cannot modify the work part. It does **not** confirm signatures or overloads.

The probe's entry point returns naturally rather than calling `sys.exit`, because the NX 12 journal host reports `SystemExit` — including `sys.exit(0)` — as a journal error and exits with 1. Two different things must therefore not be conflated:

* the **host process exit code**, which says only whether the host ran the script; and
* the **logical status**, carried in the `exitCode` field of the probe's `PROBE-RESULT:` JSON record (0, 1, 2, 3, 4, 5 as listed in `scripts/probe-nx12-api.py`).

A host that exits 0 can carry a logical status of 2, 3 or 4. Consume the complete `PROBE-RESULT:` record — the marker name is unchanged — and read its `exitCode`; do not infer a result from the host exit code, from a truncated copy of the line (a journal's Listing Window can print the report more than once, and a copy may be wrapped across lines), or from the presence of a word such as "success".

## Handling missing evidence

If an API cannot be verified:

- Search for an older builder or a UFUN equivalent only when that language is in scope.
- Ask for a Journal recording produced by the user's NX 12 installation.
- Return a scaffold with an `UNVERIFIED` TODO instead of inventing a method.
- Never replace the uncertainty with an API copied from NX 1847 or later.

## Static checks

Run `scripts/validate-journal.py --mode ready` against code presented as ready to run, and `--mode scaffold` while the journal is still a template. The script parses Python with `ast`, so comments and string literals are never mistaken for executed code; C# gets a lighter scan of comment- and string-stripped text, which is **not** compilation.

Static success does not prove API availability or correctness. Local lookup or compilation remains required, and neither proves the journal runs.

In `ready` mode the validator adds a `missing-api-evidence` warning when the file imports or calls NXOpen but carries no `NX12-API` comment at all. The check is made against the parsed code — the Python AST, or the comment- and string-stripped C# text — so a mention of NXOpen in prose does not trigger it and does not satisfy it. Silence is not a pass.

`static-checked` means only this: the checks listed in the report's `checkedScope` ran without error. It does not mean the NXOpen members exist, and it does not mean the journal can run. File-level `api-evidence-checked` and `apiTruthChecked` are reported as `false` by both scripts; see [What is checked per entry, and what is not](#what-is-checked-per-entry-and-what-is-not).
