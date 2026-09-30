# Source index and provenance

Use sources to discover patterns, then validate every API against the target NX 12 installation. Do not copy Siemens binaries or proprietary documentation into this skill.

## Verified locally

These are facts this skill was built against, confirmed on a real NX 12.0.0.27 installation:

| Fact | Evidence |
| --- | --- |
| `NXOpen.dll` and `NXOpen.UF.dll` file version `12.0.0.27` | Win32 file version read from `NXBIN\managed\` |
| Both assemblies target .NET Framework 4.0 | `ImageRuntimeVersion` `v4.0.30319`, `mscorlib 4.0.0.0` |
| NX 12 embeds Python 3.6.1 | `NXBIN\python\python36.dll` file version |
| The shipped XML documentation is incomplete | `NXOpen.Session.GetSession` has no entry; inherited members appear only on the base type; `NXOpen.UF.UFConstants` fields are undocumented |
| The first four facts in the table below about index contents | Resolved against `NXBIN\managed\NXOpen.xml` (about 85,000 members across five documentation files) |

Local evidence always outranks this table. Re-run `scripts/inspect-nx-installation.ps1` and `scripts/check-api-evidence.py --nx-root <root>` on the machine in question.

## Candidate references

Candidates for discovery, not authorities. Nothing here has been verified against the target installation for this skill, and none of it is bundled.

| Source | Intended use | NX 12 confidence | Packaging note |
| --- | --- | --- | --- |
| `mingfeng6684/nxopen-mcp` | Query local NXOpen .NET XML/DLL metadata | High when built from the target installation | Install separately; do not vendor its generated index |
| `nikitamamay/nx12-nxopen-pyi` | Python names, docstrings, inheritance, signatures | Medium: useful for Python names, but not verified here | Check the repository license before redistributing files |
| `nikitamamay/nx-journals` | NX 12 Journal and builder patterns | Medium: not verified here | Distill patterns; retain provenance |
| `digvijaytaunk/NX_Getting_started` | NX 12 C# setup and debugging orientation | Medium: environment guidance, never API proof | Use as orientation only |
| `Foadsf/NXOpen_Python_tutorials` | Conservative Python teaching examples | Low to medium: examples may target earlier releases | CC0 examples can be adapted, but revalidate APIs |
| `feifeiwang/NXOPEN` | C++/UFUN learning examples | Low for this skill: C++ is out of scope | Do not copy bundled vendor documentation |
| `ugopen/nxopen_lib` | Version/toolchain comparison | Medium | Use local licensed NX libraries instead of vendoring binaries |
| `JMarschner/NXopenExamples` | C#/VBA drafting and utility ideas | Low for direct NX 12 use | Retarget and revalidate every API and project setting |
| `theScriptingEngineer/NXOpen-CAE-python` | CAE workflow ideas | Out of scope: CAE is not covered by this skill | Not a dependency |
| `alivirgo/Major-AI-Skills/skills/siemens-nx` | Skill structure and topic coverage | Low for NX 12 API truth | Do not inherit modern-release assumptions |

## Prefer local evidence over any of this

Siemens' own installation already ships better material than most of the candidates:

- The XML documentation beside the assemblies, which `scripts/check-api-evidence.py` reads directly.
- `UGOPEN\SampleNXOpenApplications\`, including NX 12 C# and Python examples.
- `UGOPEN\NXOpen\*.hxx`, the C++ headers, useful for discovering names — but a C++ name is not proof of a .NET or Python binding.

For every imported pattern, record:

- Repository and exact commit or release.
- Original target NX version.
- Language and subsystem.
- License or redistribution status.
- Local NX 12 validation method and result.
- Any modifications made to remove recorded identifiers or later-release calls.

Prefer links and short derived patterns over copied documentation. If license or provenance is unclear, use the source only to identify API search terms.
