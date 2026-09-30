<#
.SYNOPSIS
Compile-check an NX 12 C# journal against the assemblies of ONE explicit NX installation.

.DESCRIPTION
Compiles the given C# source file(s) with the .NET Framework C# 5 compiler that
ships with Windows, referencing NXOpen.dll (and the companion assemblies) taken
from the NX installation the caller names. It reports, in text or JSON, exactly
which compiler and which assemblies were used, and what the result does and does
not prove.

What this script does NOT do:
  * It never executes, loads or reflects into the produced assembly.
  * It never starts NX, never opens a part and never models anything.
  * It never guesses the NX installation. -NxRoot is required.
  * It never borrows an assembly from a different NX installation or version to
    make a build succeed. Every referenced assembly must live under -NxRoot and
    must report major version 12.
  * It never falls back to dotnet, MSBuild or a modern .NET runtime compiler.

What a passing result proves:
  * The source is syntactically valid C# 5.
  * Every NXOpen type, member and constant named in the source resolved against
    the assemblies of the named installation, with argument lists the compiler
    accepted.

What a passing result does NOT prove:
  * That the selected overload is the intended one. C# overload resolution can
    pick a different overload than the author meant when implicit conversions,
    optional parameters or params arrays are involved.
  * That the journal runs, or that NX accepts it. The assembly is never
    executed and NX is never started.
  * That enum members, property types, builder sequences and units are
    semantically correct; the compiler checks types, not intent.

.PARAMETER SourceFile
One or more C# source files to compile. Required.

.PARAMETER NxRoot
The NX installation root that owns the assemblies to compile against, for
example 'E:\UG 12.0'. Required and never guessed.

.PARAMETER OutputDirectory
Directory for the produced assembly, the raw compiler logs and the JSON result.
Required. The source directory is never written to.

.PARAMETER Target
Compilation target passed to the compiler: 'library' (default) or 'exe'.
A library needs no entry point, so it works for fragments and for complete
journals alike.

.PARAMETER CompilerPath
Explicit path to csc.exe. When omitted, only the .NET Framework v4.0.30319
compiler directories are probed. When supplied, the caller takes
responsibility for it being a .NET Framework compiler; the script records it
but never substitutes a different one.

.PARAMETER SearchDepth
Maximum recursion depth used below the NX root when probing for the managed
assemblies. Bounded on purpose; the script never searches a whole disk.

.PARAMETER Json
Emit a machine-readable JSON document instead of the text report. The same
document is always written to the output directory as 'nx12-csharp-result.json',
ASCII encoded so it parses regardless of console code page or redirection.

.OUTPUTS
Exit codes:
  0  compiled        the source compiled against the named installation
  1  compile-failed  the compiler reported errors
  2  usage-error     a required parameter was missing or unusable
  3  skipped         no usable .NET Framework C# 5 compiler was found
  4  skipped         the NX root does not contain the required assemblies
  5  skipped         the assemblies do not belong to the stated root/version

.EXAMPLE
.\validate-nx12-csharp.ps1 -SourceFile .\myjournal.cs -NxRoot 'E:\UG 12.0' -OutputDirectory .\.build

.EXAMPLE
.\validate-nx12-csharp.ps1 -SourceFile .\myjournal.cs -NxRoot 'E:\UG 12.0' -OutputDirectory .\.build -Json
#>
[CmdletBinding()]
param(
    [string[]]$SourceFile = @(),
    [string]$NxRoot = '',
    [string]$OutputDirectory = '',
    [ValidateSet('library', 'exe')]
    [string]$Target = 'library',
    [string]$CompilerPath = '',
    [int]$SearchDepth = 3,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

# The C# language level of the in-box .NET Framework 4.0 compiler. Passing it
# explicitly keeps the check honest: syntax that only a later compiler accepts
# must fail here, because NX 12 ships against this toolchain.
$script:LangVersion = '5'

$script:TargetFramework = '.NETFramework,Version=v4.0'

# Companion assemblies that are always referenced when present beside a located
# NXOpen.dll. NXOpen.Utilities.dll is not optional in practice: NXOpen.dll
# exposes base types such as NXOpen.Utilities.BaseSession and NXOpen.TaggedObject
# from it, so any source that names a Session, a Builder or a Part fails with
# CS0012 without it. Speculative companions such as NXOpenUI.dll are NOT added
# up front; the bounded retry adds them only when the compiler asks for them.
$script:CompanionAssemblyNames = @('NXOpen.Utilities.dll')

# Assemblies whose file version is treated as authoritative NX version evidence.
# Other assemblies in the same folder (NXOpen.Guide.dll reports 0.0.0.0, for
# instance) are recorded but must never decide the version check.
$script:VersionAuthoritativeNames = @('NXOpen.dll', 'NXOpen.UF.dll')

# Relative layouts probed before any search. 'managed' is a hint here, never an
# assumption: NX 12 uses NXBIN\managed, but that must not be hard-coded.
$script:ManagedLayoutHints = @(
    'NXBIN\managed',
    'managed',
    'NXBIN',
    'UGII\managed',
    'UGII',
    'nxbin\managed',
    ''
)

function Get-MajorVersion {
    param([string]$VersionText)
    if ([string]::IsNullOrWhiteSpace($VersionText)) { return $null }
    $match = [regex]::Match($VersionText, '^\s*(\d{1,6})(?:\.|\s|$)')
    if (-not $match.Success) { return $null }
    return [int]$match.Groups[1].Value
}

function Get-FileVersionText {
    param([string]$Path)
    try {
        $item = Get-Item -LiteralPath $Path -ErrorAction Stop
        if ($item.VersionInfo.FileVersion) { return $item.VersionInfo.FileVersion.Trim() }
    } catch {
        return $null
    }
    return $null
}

function Get-FileEvidence {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $fileVersion = Get-FileVersionText $Path
    return [ordered]@{
        name        = (Split-Path -Leaf $Path)
        path        = $Path
        fileVersion = $fileVersion
        major       = (Get-MajorVersion $fileVersion)
    }
}

function Test-IsDirectory {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    try { return (Get-Item -LiteralPath $Path -ErrorAction Stop).PSIsContainer } catch { return $false }
}

# True only when Path resolves to a location strictly inside Root. This is the
# guard that stops the script from silently compiling against another NX
# installation's binaries.
function Test-IsUnderRoot {
    param([string]$Path, [string]$Root)
    try {
        $fullPath = [System.IO.Path]::GetFullPath($Path)
        $fullRoot = [System.IO.Path]::GetFullPath($Root)
    } catch {
        return $false
    }
    if (-not $fullRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $fullRoot = $fullRoot + [System.IO.Path]::DirectorySeparatorChar
    }
    return $fullPath.StartsWith($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

# Locate an assembly under the stated root: known layouts first, then a bounded
# search. The returned path is always inside the root.
function Find-RootFile {
    param([string]$Root, [string]$Name, [int]$Depth)

    foreach ($hint in $script:ManagedLayoutHints) {
        $dir = if ([string]::IsNullOrWhiteSpace($hint)) { $Root } else { Join-Path $Root $hint }
        if (-not (Test-IsDirectory $dir)) { continue }
        $candidate = Join-Path $dir $Name
        if ((Test-Path -LiteralPath $candidate -PathType Leaf) -and (Test-IsUnderRoot -Path $candidate -Root $Root)) {
            return $candidate
        }
    }

    $hits = Get-ChildItem -LiteralPath $Root -Recurse -Depth $Depth -Filter $Name -File -ErrorAction SilentlyContinue |
        Where-Object { Test-IsUnderRoot -Path $_.FullName -Root $Root } |
        Sort-Object -Property FullName
    foreach ($hit in @($hits)) {
        return $hit.FullName
    }
    return $null
}

# Cheap, hint-only lookup for corroborating artifacts such as ugraf.exe. It
# never recurses, so reporting version evidence stays fast.
function Find-RootFileShallow {
    param([string]$Root, [string]$Name)
    foreach ($hint in @('', 'UGII', 'NXBIN')) {
        $dir = if ([string]::IsNullOrWhiteSpace($hint)) { $Root } else { Join-Path $Root $hint }
        $candidate = Join-Path $dir $Name
        if ((Test-Path -LiteralPath $candidate -PathType Leaf) -and (Test-IsUnderRoot -Path $candidate -Root $Root)) {
            return $candidate
        }
    }
    return $null
}

function Get-CandidateCompilerPath {
    param([string]$Explicit)

    $paths = [System.Collections.Generic.List[string]]::new()
    $sources = [System.Collections.Generic.List[string]]::new()

    if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
        # An explicit compiler that is not there is reported as "no compiler",
        # never silently replaced by a different one.
        if (Test-Path -LiteralPath $Explicit -PathType Leaf) {
            $result = [ordered]@{ paths = @($Explicit); sources = @('parameter') }
        } else {
            $result = [ordered]@{ paths = @(); sources = @() }
        }
        return $result
    }

    $windir = $env:WINDIR
    if ([string]::IsNullOrWhiteSpace($windir)) { $windir = $env:SystemRoot }

    if (-not [string]::IsNullOrWhiteSpace($windir)) {
        foreach ($flavor in @('Framework64', 'Framework')) {
            $paths.Add((Join-Path $windir ('Microsoft.NET\' + $flavor + '\v4.0.30319\csc.exe')))
            $sources.Add('framework-directory')
        }
    }

    # The CLR hosting this script is itself a .NET Framework v4 runtime, so its
    # own directory is a truthful place to look for a matching compiler.
    try {
        $runtimeDirectory = [System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()
        if (-not [string]::IsNullOrWhiteSpace($runtimeDirectory)) {
            $paths.Add((Join-Path $runtimeDirectory 'csc.exe'))
            $sources.Add('script-runtime-directory')
        }
    } catch {
        # Purely a fallback source; ignoring it is safe.
    }

    $existing = [System.Collections.Generic.List[string]]::new()
    $existingSources = [System.Collections.Generic.List[string]]::new()
    for ($index = 0; $index -lt $paths.Count; $index++) {
        if (Test-Path -LiteralPath $paths[$index] -PathType Leaf) {
            $existing.Add($paths[$index])
            $existingSources.Add($sources[$index])
        }
    }
    $result = [ordered]@{ paths = @($existing); sources = @($existingSources) }
    return $result
}

# Turn one compiler output line into a structured diagnostic, or return null.
# csc keeps the words "error" and "warning" in English even on a localized
# Windows, so the severity is matchable while the message stays as emitted.
function ConvertTo-Diagnostic {
    param([string]$Line)
    if ([string]::IsNullOrWhiteSpace($Line)) { return $null }
    $pattern = '^(?:(?<file>.+?)\((?<line>\d+),(?<col>\d+)\)\s*:\s*)?(?<sev>fatal error|error|warning)\s+(?<code>[A-Za-z]{1,4}\d+)\s*:\s*(?<msg>.*)$'
    $match = [regex]::Match($Line, $pattern)
    if (-not $match.Success) { return $null }
    $severity = $match.Groups['sev'].Value
    if ($severity -eq 'fatal error') { $severity = 'error' }
    $number = $null
    if ($match.Groups['line'].Success) {
        try { $number = [int]$match.Groups['line'].Value } catch { $number = $null }
    }
    $column = $null
    if ($match.Groups['col'].Success) {
        try { $column = [int]$match.Groups['col'].Value } catch { $column = $null }
    }
    $file = $null
    if ($match.Groups['file'].Success) { $file = $match.Groups['file'].Value }
    $result = [ordered]@{
        severity = $severity
        code     = $match.Groups['code'].Value
        file     = $file
        line     = $number
        column   = $column
        message  = $match.Groups['msg'].Value
    }
    return $result
}

# Language-independent recovery of assemblies the compiler said were missing.
# The diagnostic text is localized; a .NET assembly identity is not.
function Get-MissingAssemblyName {
    param([string]$Text)
    $names = [System.Collections.Generic.List[string]]::new()
    foreach ($match in [regex]::Matches($Text, '"([^",]+),\s*Version=\d+\.\d+\.\d+\.\d+')) {
        $name = $match.Groups[1].Value.Trim()
        if ($name -notmatch '\.dll$') { $name = $name + '.dll' }
        if (-not $names.Contains($name)) { $names.Add($name) }
    }
    return @($names)
}

function Write-ResultText {
    param([object]$Report)

    Write-Output 'NX 12 C# compile check'
    Write-Output ('  outcome        : ' + $Report.outcome + ' (' + $Report.reason + ')')
    Write-Output ('  exit code      : ' + $Report.exitCode)
    Write-Output ('  source files   : ' + (@($Report.sourceFiles) -join ' ; '))
    Write-Output ('  nx root        : ' + $Report.nxRoot)
    Write-Output ('  managed dir    : ' + $Report.assemblies.managedDirectory)

    if ($null -ne $Report.nxRootEvidence) {
        Write-Output ('  version check  : root exists = ' + $Report.nxRootEvidence.rootExists + '; authoritative major versions seen = ' + (@($Report.nxRootEvidence.majorVersionsSeen) -join ', '))
        foreach ($item in @($Report.nxRootEvidence.items)) {
            Write-Output ('                   ' + $item.name + ' = ' + $item.fileVersion + ' (major ' + $item.major + ', authoritative ' + $item.authoritative + ') at ' + $item.path)
        }
    }

    foreach ($item in @($Report.assemblies.items)) {
        Write-Output ('  reference      : ' + $item.name + ' = ' + $item.fileVersion + ' underStatedRoot=' + $item.underStatedRoot + ' at ' + $item.path)
    }
    foreach ($item in @($Report.assemblies.autoResolved)) {
        Write-Output ('  reference      : auto-added ' + $item.name + ' = ' + $item.fileVersion + ' (' + $item.reason + ')')
    }

    Write-Output ('  compiler       : ' + $Report.compiler.path)
    Write-Output ('  compiler ver   : ' + $Report.compiler.fileVersion + ' (found via: ' + $Report.compiler.source + ')')
    Write-Output ('  language       : C# ' + $Report.compilation.langVersion)
    Write-Output ('  target         : ' + $Report.compilation.target + ' -> ' + $Report.compilation.assemblyPath)
    Write-Output ('  target fwk     : ' + $Report.compilation.targetFramework)
    Write-Output ('  compile rounds  : ' + $Report.compilation.attempts)

    Write-Output ('  errors         : ' + $Report.diagnostics.errorCount)
    foreach ($item in @($Report.diagnostics.errors)) {
        Write-Output ('    ' + $item.code + ' ' + $item.file + '(' + $item.line + ',' + $item.column + '): ' + $item.message)
    }
    Write-Output ('  warnings       : ' + $Report.diagnostics.warningCount)
    foreach ($item in @($Report.diagnostics.warnings)) {
        Write-Output ('    ' + $item.code + ' ' + $item.file + '(' + $item.line + ',' + $item.column + '): ' + $item.message)
    }

    foreach ($note in @($Report.notes)) { Write-Output ('  note           : ' + $note) }

    Write-Output ''
    Write-Output ('Safety: assembly executed = ' + $Report.safety.assemblyExecuted + '; NX started = ' + $Report.safety.nxStarted + '; part touched = ' + $Report.safety.partTouched)
    Write-Output 'What this result does NOT prove:'
    foreach ($line in @($Report.evidence.doesNotProve)) { Write-Output ('  - ' + $line) }
}

# ---------------------------------------------------------------- state

$outcome = 'usage-error'
$reason = 'The validation script did not reach a result.'
$exitCode = 2

$sourceFiles = @()
$root = ''
# Resolved, absolute output directory. Deliberately NOT named $outputDirectory:
# PowerShell variable names are case-insensitive, so that name would be the same
# variable as the -OutputDirectory parameter and would silently erase it.
$resolvedOutputDirectory = ''
$nxRootEvidence = $null
$assemblyItems = @()
$autoResolved = @()
$referenceArguments = ''
$compilationAssemblyPath = $null
$compileAttempts = 0
$errors = @()
$warnings = @()
$rawStdout = ''
$rawStderr = ''
# NOTE: PowerShell variable names are case-insensitive, so local names must not
# collide with the parameter names above. In particular the resolved compiler is
# $resolvedCompilerPath, never $compilerPath, and the JSON text is $jsonText,
# never $json.
$resolvedCompilerPath = $null
$compilerFileVersion = $null
$compilerSource = $null
$compilerRuntimeDirectory = $null

$notes = [System.Collections.Generic.List[string]]::new()
$notes.Add('A successful compile only proves this compile check passed, not that the model runs correctly.')
$notes.Add('C# compilation catches missing members but can still select an unintended overload.')

$proves = @(
    'The source is syntactically valid C# 5.',
    'Every NXOpen type, member and constant named in the source resolved against the assemblies of the named NX installation.',
    'The compiler accepted the argument lists at each resolved call site.'
)
$doesNotProve = @(
    'That the selected overload is the intended one. C# overload resolution can pick a different overload than the author meant when implicit conversions, optional parameters or params arrays are involved.',
    'That the journal runs, or that NX accepts it. The produced assembly is never executed and NX is never started.',
    'That enum members, property types, builder sequences and unit assumptions are semantically correct; the compiler checks types, not intent.',
    'That the assemblies referenced here are the ones NX will load at run time.'
)

# ---------------------------------------------------------------- main

try {
    if (-not [string]::IsNullOrWhiteSpace($NxRoot)) {
        try { $root = (Get-Item -LiteralPath $NxRoot -ErrorAction Stop).FullName } catch { $root = $NxRoot }
    }

    # ---- stage 0: parameters. Source files are resolved first so that the
    # report still names them when a later parameter turns out to be unusable.
    $missingFiles = [System.Collections.Generic.List[string]]::new()
    foreach ($item in $SourceFile) {
        if (Test-Path -LiteralPath $item -PathType Leaf) {
            $sourceFiles += (Get-Item -LiteralPath $item -ErrorAction Stop).FullName
        } else {
            $missingFiles.Add($item)
        }
    }

    $badParameters = [System.Collections.Generic.List[string]]::new()
    if ($SourceFile.Count -eq 0) { $badParameters.Add('-SourceFile') }
    if ([string]::IsNullOrWhiteSpace($NxRoot)) { $badParameters.Add('-NxRoot (an explicit NX installation root is required and is never guessed)') }
    if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { $badParameters.Add('-OutputDirectory') }

    if ($badParameters.Count -gt 0) {
        $outcome = 'usage-error'
        $reason = 'Missing required parameter(s): ' + ($badParameters -join ', ') + '.'
        $exitCode = 2
    } elseif ($missingFiles.Count -gt 0) {
        $outcome = 'usage-error'
        $reason = 'Source file(s) not found: ' + ($missingFiles -join ', ') + '.'
        $exitCode = 2
    } elseif ($SearchDepth -lt 0) {
        $outcome = 'usage-error'
        $reason = 'SearchDepth must be zero or greater.'
        $exitCode = 2
    } elseif (Test-IsDirectory $OutputDirectory) {
        $resolvedOutputDirectory = (Get-Item -LiteralPath $OutputDirectory -ErrorAction Stop).FullName
        $exitCode = 0
    } else {
        try {
            New-Item -ItemType Directory -Path $OutputDirectory -Force -ErrorAction Stop | Out-Null
            $resolvedOutputDirectory = (Get-Item -LiteralPath $OutputDirectory -ErrorAction Stop).FullName
            $exitCode = 0
        } catch {
            $outcome = 'usage-error'
            $reason = 'OutputDirectory could not be created: ' + $OutputDirectory
            $exitCode = 2
        }
    }

    # ---- stage 1: the stated NX root must exist, on its own evidence
    if ($exitCode -eq 0 -and -not (Test-IsDirectory $root)) {
        $outcome = 'skipped'
        $reason = 'The stated NX root does not exist or is not a directory. It is never guessed and nothing is substituted for it.'
        $exitCode = 4
    }

    # ---- stage 2: locate NXOpen.dll strictly inside that root
    $nxOpenPath = $null
    if ($exitCode -eq 0) {
        $nxOpenPath = Find-RootFile -Root $root -Name 'NXOpen.dll' -Depth $SearchDepth
        if ([string]::IsNullOrWhiteSpace($nxOpenPath)) {
            $outcome = 'skipped'
            $reason = 'NXOpen.dll was not found anywhere under the stated root. Assemblies from another installation are never borrowed.'
            $exitCode = 4
        }
    }

    # ---- stage 3: version evidence of the target installation, before compiling
    if ($exitCode -eq 0) {
        $managedDirectory = Split-Path -Parent $nxOpenPath

        $sourceText = ''
        foreach ($item in $sourceFiles) {
            try { $sourceText = $sourceText + "`n" + (Get-Content -LiteralPath $item -Raw -Encoding utf8) } catch { }
        }
        $ufReferenced = [bool]($sourceText -match 'NXOpen\.UF')

        $assemblyPaths = [System.Collections.Generic.List[string]]::new()
        $assemblyPaths.Add($nxOpenPath)
        foreach ($name in $script:CompanionAssemblyNames) {
            $companion = Join-Path $managedDirectory $name
            if (Test-Path -LiteralPath $companion -PathType Leaf) { $assemblyPaths.Add($companion) }
        }
        $ufPath = Join-Path $managedDirectory 'NXOpen.UF.dll'
        $ufAvailable = Test-Path -LiteralPath $ufPath -PathType Leaf
        if ($ufReferenced -and $ufAvailable) { $assemblyPaths.Add($ufPath) }

        $majors = [System.Collections.Generic.List[int]]::new()
        $evidenceItems = [System.Collections.Generic.List[object]]::new()
        $outsideRoot = [System.Collections.Generic.List[string]]::new()

        foreach ($path in $assemblyPaths) {
            $evidence = Get-FileEvidence $path
            if ($null -eq $evidence) { continue }
            $underRoot = Test-IsUnderRoot -Path $path -Root $root
            $authoritative = [bool]($script:VersionAuthoritativeNames -contains $evidence.name)
            $evidenceItems.Add([ordered]@{
                name            = $evidence.name
                path            = $evidence.path
                fileVersion     = $evidence.fileVersion
                major           = $evidence.major
                authoritative   = $authoritative
                underStatedRoot = $underRoot
            })
            if ($authoritative -and $null -ne $evidence.major) { $majors.Add($evidence.major) }
            $assemblyItems += [ordered]@{
                name            = $evidence.name
                path            = $evidence.path
                fileVersion     = $evidence.fileVersion
                major           = $evidence.major
                authoritative   = $authoritative
                underStatedRoot = $underRoot
            }
            if (-not $underRoot) { $outsideRoot.Add($evidence.name) }
        }

        # Corroborating evidence from the installation's main executable. Cheap
        # lookup only; it is reported but never treated as authoritative alone.
        $ugrafPath = Find-RootFileShallow -Root $root -Name 'ugraf.exe'
        if (-not [string]::IsNullOrWhiteSpace($ugrafPath)) {
            $ugrafEvidence = Get-FileEvidence $ugrafPath
            if ($null -ne $ugrafEvidence) { $evidenceItems.Add($ugrafEvidence) }
        }

        $distinctMajors = @($majors | Sort-Object -Unique)
        $nxRootEvidence = [ordered]@{
            root              = $root
            rootExists        = (Test-IsDirectory $root)
            managedDirectory  = $managedDirectory
            ufReferenced      = $ufReferenced
            majorVersionsSeen = @($distinctMajors)
            items             = @($evidenceItems)
            note              = 'File versions read from the named installation only. No assembly outside the stated root is ever used, and no assembly from another NX version is ever borrowed to make a build pass.'
        }

        if ($outsideRoot.Count -gt 0) {
            $outcome = 'skipped'
            $reason = 'Resolved assembly/assemblies outside the stated root: ' + ($outsideRoot -join ', ') + '. Refusing to compile against them.'
            $exitCode = 5
        } elseif ($distinctMajors.Count -eq 0) {
            # Version identity is checked before anything else about the
            # assemblies, so a wrong installation is never mistaken for a
            # merely incomplete one.
            $outcome = 'skipped'
            $reason = 'No authoritative version evidence could be read from NXOpen.dll / NXOpen.UF.dll under the stated root.'
            $exitCode = 5
        } elseif ($distinctMajors.Count -gt 1) {
            $outcome = 'skipped'
            $reason = 'The authoritative assemblies under the stated root report disagreeing major versions (' + ($distinctMajors -join ', ') + ').'
            $exitCode = 5
        } elseif ($distinctMajors[0] -ne 12) {
            $outcome = 'skipped'
            $reason = 'The stated root reports major version ' + $distinctMajors[0] + ', not 12. Later-release assemblies must not be used to validate NX 12 code.'
            $exitCode = 5
        } elseif ($ufReferenced -and -not $ufAvailable) {
            $outcome = 'skipped'
            $reason = 'The source references NXOpen.UF, but NXOpen.UF.dll was not found beside NXOpen.dll under the stated root. It is never taken from another installation.'
            $exitCode = 4
        } else {
            $notes.Add('Version evidence confirms major version 12 for the assemblies of the stated root.')
        }
    }

    # ---- stage 4: a real, available, appropriate compiler
    if ($exitCode -eq 0) {
        $candidates = Get-CandidateCompilerPath -Explicit $CompilerPath
        $candidatePaths = @($candidates.paths)
        $candidateSources = @($candidates.sources)
        if ($candidatePaths.Count -eq 0) {
            $outcome = 'skipped'
            if (-not [string]::IsNullOrWhiteSpace($CompilerPath)) {
                $reason = 'The compiler given with -CompilerPath does not exist: ' + $CompilerPath + '. It is never replaced by a different compiler.'
            } else {
                $reason = 'No .NET Framework C# compiler (csc.exe v4.0.30319) is available. dotnet and MSBuild are deliberately not used as substitutes.'
            }
            $exitCode = 3
        } else {
            $resolvedCompilerPath = $candidatePaths[0]
            $compilerSource = $candidateSources[0]
            $compilerFileVersion = Get-FileVersionText $resolvedCompilerPath
            try { $compilerRuntimeDirectory = [System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory() } catch { $compilerRuntimeDirectory = $null }
            if (-not [string]::IsNullOrWhiteSpace($CompilerPath)) {
                $notes.Add('The compiler was supplied explicitly; the caller is responsible for it targeting .NET Framework rather than a modern .NET runtime.')
            }
        }
    }

    # ---- stage 5: compile, writing only into the explicit output directory
    if ($exitCode -eq 0) {
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($sourceFiles[0])
        $extension = '.nx12check.dll'
        if ($Target -eq 'exe') { $extension = '.nx12check.exe' }
        $compilationAssemblyPath = Join-Path $resolvedOutputDirectory ($baseName + $extension)

        $stdoutPath = Join-Path $resolvedOutputDirectory 'csc.stdout.txt'
        $stderrPath = Join-Path $resolvedOutputDirectory 'csc.stderr.txt'

        $managedDirectory = Split-Path -Parent $nxOpenPath
        $referencePaths = [System.Collections.Generic.List[string]]::new()
        $resolvedNames = [System.Collections.Generic.List[string]]::new()
        foreach ($item in $assemblyItems) {
            $referencePaths.Add($item.path)
            $resolvedNames.Add($item.name)
        }

        $stdoutText = ''
        $stderrText = ''
        $lastExit = $null

        # The console code page on a localized Windows does not match what csc
        # writes by default. Pin both sides to UTF-8 for the duration of the
        # call so the captured diagnostics are readable and deterministic.
        $previousOutputEncoding = $null
        try { $previousOutputEncoding = [Console]::OutputEncoding } catch { $previousOutputEncoding = $null }
        $previousErrorActionPreference = $ErrorActionPreference

        try {
            try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
            $ErrorActionPreference = 'Continue'

            # Bounded retry: when the compiler names an assembly it could not
            # resolve, add it only if it lives in the SAME managed directory
            # found inside the stated root. Anything else would be borrowing.
            for ($attempt = 1; $attempt -le 4; $attempt++) {
                $compileAttempts = $attempt

                $argumentParts = [System.Collections.Generic.List[string]]::new()
                $argumentParts.Add('/nologo')
                $argumentParts.Add('/utf8output')
                $argumentParts.Add('/langversion:' + $script:LangVersion)
                $argumentParts.Add('/target:' + $Target)
                $argumentParts.Add('/out:"' + $compilationAssemblyPath + '"')
                foreach ($path in $referencePaths) {
                    $argumentParts.Add('/reference:"' + $path + '"')
                }
                foreach ($item in $sourceFiles) {
                    $argumentParts.Add('"' + $item + '"')
                }
                $argumentLine = ($argumentParts.ToArray() -join ' ')

                try {
                    $process = Start-Process -FilePath $resolvedCompilerPath -ArgumentList $argumentLine `
                        -WorkingDirectory $resolvedOutputDirectory -NoNewWindow -Wait -PassThru `
                        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
                    $lastExit = $process.ExitCode
                } catch {
                    # The compiler could not be launched at all. That is a skip,
                    # not a compile failure, and never a reason to substitute a
                    # different compiler.
                    $lastExit = $null
                    $stderrText = 'The compiler could not be launched: ' + $_.Exception.Message
                    break
                }

                $stdoutText = ''
                $stderrText = ''
                if (Test-Path -LiteralPath $stdoutPath) { $stdoutText = [string](Get-Content -LiteralPath $stdoutPath -Raw -Encoding utf8) }
                if (Test-Path -LiteralPath $stderrPath) { $stderrText = [string](Get-Content -LiteralPath $stderrPath -Raw -Encoding utf8) }

                if ($lastExit -eq 0) { break }

                $added = $false
                foreach ($name in (Get-MissingAssemblyName -Text ($stdoutText + "`n" + $stderrText))) {
                    if ($resolvedNames.Contains($name)) { continue }
                    $candidate = Join-Path $managedDirectory $name
                    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
                    if (-not (Test-IsUnderRoot -Path $candidate -Root $root)) { continue }
                    $resolvedNames.Add($name)
                    $referencePaths.Add($candidate)
                    $evidence = Get-FileEvidence $candidate
                    $versionText = $null
                    if ($null -ne $evidence) { $versionText = $evidence.fileVersion }
                    $autoResolved += [ordered]@{
                        name        = $name
                        path        = $candidate
                        fileVersion = $versionText
                        reason      = 'Named by the compiler as an unresolved assembly and found in the same managed directory as NXOpen.dll.'
                    }
                    $added = $true
                }
                if (-not $added) { break }
            }
        } finally {
            if ($null -ne $previousOutputEncoding) {
                try { [Console]::OutputEncoding = $previousOutputEncoding } catch { }
            }
            $ErrorActionPreference = $previousErrorActionPreference
        }

        $allLines = @(($stdoutText + "`n" + $stderrText) -split "\r?\n")
        $errors = @()
        $warnings = @()
        foreach ($line in $allLines) {
            $diagnostic = ConvertTo-Diagnostic -Line $line
            if ($null -eq $diagnostic) { continue }
            if ($diagnostic.severity -eq 'error') { $errors += $diagnostic } else { $warnings += $diagnostic }
        }
        $rawStdout = $stdoutText
        $rawStderr = $stderrText

        $referenceArguments = ''
        foreach ($path in $referencePaths) {
            if ($referenceArguments.Length -gt 0) { $referenceArguments = $referenceArguments + ' ' }
            $referenceArguments = $referenceArguments + '/reference:"' + $path + '"'
        }

        if ($null -eq $lastExit) {
            $outcome = 'skipped'
            $reason = 'The compiler did not run.'
            $exitCode = 3
        } elseif ($lastExit -eq 0) {
            $outcome = 'compiled'
            $reason = 'The compiler reported no errors.'
            $exitCode = 0
            if ($errors.Count -gt 0) {
                $notes.Add('The compiler exited 0 but error-shaped lines were seen in its output; treat this result as suspect.')
            }
        } else {
            $outcome = 'compile-failed'
            $reason = 'The compiler exited with code ' + $lastExit + ' and reported ' + $errors.Count + ' error(s).'
            $exitCode = 1
        }
    }
} catch {
    $outcome = 'usage-error'
    $reason = 'The validation script failed before a result could be produced: ' + $_.Exception.Message
    $exitCode = 2
}

# ---------------------------------------------------------------- report

$report = [ordered]@{
    schemaVersion   = 1
    tool            = 'validate-nx12-csharp.ps1'
    timestamp       = (Get-Date).ToString('o')
    outcome         = $outcome
    reason          = $reason
    exitCode        = $exitCode
    sourceFiles     = @($sourceFiles)
    nxRoot          = $(if ([string]::IsNullOrWhiteSpace($root)) { $NxRoot } else { $root })
    outputDirectory = $resolvedOutputDirectory
    nxRootEvidence  = $nxRootEvidence
    assemblies      = [ordered]@{
        managedDirectory   = $(if ($null -ne $nxRootEvidence) { $nxRootEvidence.managedDirectory } else { $null })
        referenceArguments = $referenceArguments
        items              = @($assemblyItems)
        autoResolved       = @($autoResolved)
    }
    compiler        = [ordered]@{
        path             = $resolvedCompilerPath
        fileVersion      = $compilerFileVersion
        source           = $compilerSource
        runtimeDirectory = $compilerRuntimeDirectory
        note             = 'A .NET Framework compiler is required. dotnet, MSBuild and modern .NET runtime compilers are deliberately never used.'
    }
    compilation     = [ordered]@{
        target               = $Target
        langVersion          = $script:LangVersion
        targetFramework      = $script:TargetFramework
        targetFrameworkBasis = 'Derived from the resolved .NET Framework compiler directory; NXOpen.dll and NXOpen.UF.dll ship as .NET Framework 4.0 assemblies with ImageRuntimeVersion v4.0.30319.'
        assemblyPath         = $compilationAssemblyPath
        attempts             = $compileAttempts
    }
    diagnostics     = [ordered]@{
        errorCount   = @($errors).Count
        warningCount = @($warnings).Count
        errors       = @($errors)
        warnings     = @($warnings)
        rawStdout    = $rawStdout
        rawStderr    = $rawStderr
    }
    evidence        = [ordered]@{
        proves           = @($proves)
        doesNotProve     = @($doesNotProve)
        overloadBoundary = 'C# compilation catches missing members but can still select an unintended overload. Argument types, argument order, enum declaring types and builder property types must still be read by a human.'
        successStatement = 'A successful compile proves ONLY that this compile check passed against the named installation. It does NOT show that the model runs correctly.'
    }
    notes           = @($notes)
    safety          = [ordered]@{
        readOnly         = $true
        assemblyExecuted = $false
        nxStarted        = $false
        partTouched      = $false
        note             = 'The produced assembly is written to disk and never executed. NX is never started and no part is opened or modified.'
    }
}

# ---------------------------------------------------------------- output

$jsonText = $report | ConvertTo-Json -Depth 12
# Escape every non-ASCII character so the document parses no matter which code
# page the console or a redirection uses.
$jsonText = [regex]::Replace($jsonText, '[^\x00-\x7F]', { param($match) '\u{0:x4}' -f [int][char]$match.Value })

$jsonPath = $null
$jsonWritten = $false
if (-not [string]::IsNullOrWhiteSpace($resolvedOutputDirectory) -and (Test-IsDirectory $resolvedOutputDirectory)) {
    try {
        $jsonPath = Join-Path $resolvedOutputDirectory 'nx12-csharp-result.json'
        Set-Content -LiteralPath $jsonPath -Value $jsonText -Encoding ascii
        $jsonWritten = $true
    } catch {
        $jsonWritten = $false
    }
}

if ($Json) {
    Write-Output $jsonText
} else {
    Write-ResultText -Report $report
    Write-Output ''
    Write-Output ('Result: ' + $outcome + ' - ' + $reason)
    Write-Output 'A successful compile only proves this compile check passed. It does NOT show that the model runs correctly.'
    Write-Output 'C# compilation catches missing members but can still pick an unintended overload; overloads must still be reviewed by hand.'
    if ($jsonWritten) {
        Write-Output ('JSON result written to ' + $jsonPath)
    }
}

exit $exitCode
