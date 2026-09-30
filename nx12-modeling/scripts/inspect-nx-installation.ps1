<#
.SYNOPSIS
Read-only inspection of Siemens NX installations.

.DESCRIPTION
Locates candidate NX installation roots, gathers version evidence from files
that actually exist on disk, classifies every candidate, and reports the
outcome as text or JSON.

The script is strictly read-only. It does not modify the registry, PATH,
environment variables, licensing, or any NX configuration file.

A directory whose path merely contains a token such as "NX12" is treated as a
hint only. A candidate is confirmed as NX 12 only when authoritative file
version evidence reports major version 12 and nothing authoritative
contradicts it.

When several installations are present the script does not silently pick one:
SelectedRoot is populated only when exactly one candidate is confirmed.

.PARAMETER NxRoot
Explicit NX installation root(s) to inspect. Highest priority.

.PARAMETER ExtraSearchRoot
Additional directories to scan one or two levels deep for NX roots.

.PARAMETER SearchDepth
Maximum recursion depth used below each candidate root when sweeping for
artifacts. Bounded on purpose; the script never performs a full-disk search.

.PARAMETER Json
Emit a machine-readable JSON document instead of the text report.

.OUTPUTS
Exit codes:
  0  exactly one candidate was confirmed as NX 12 and selected
  1  no candidate NX installation was found
  2  usage error
  3  candidates were found but none could be confirmed as NX 12
  4  more than one candidate was confirmed as NX 12 (ambiguous)
  5  conflicting version evidence was detected

.EXAMPLE
.\inspect-nx-installation.ps1

.EXAMPLE
.\inspect-nx-installation.ps1 -NxRoot 'E:\UG 12.0' -Json
#>
[CmdletBinding()]
param(
    [string[]]$NxRoot = @(),
    [string[]]$ExtraSearchRoot = @(),
    [int]$SearchDepth = 3,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

# Artifacts that identify an NX installation layout.
$script:ArtifactNames = @(
    'ugraf.exe',
    'run_journal.exe',
    'NXOpen.dll',
    'NXOpen.UF.dll',
    'NXOpen.xml',
    'NXOpen.UF.xml'
)

# Artifacts whose file version is treated as authoritative version evidence.
$script:VersionArtifactNames = @(
    'ugraf.exe',
    'run_journal.exe',
    'NXOpen.dll',
    'NXOpen.UF.dll'
)

# Relative directories checked first. These are hints for common layouts, not
# an assumption that a layout must use them; a bounded sweep covers the rest.
$script:LayoutHints = @(
    '',
    'UGII',
    'NXBIN',
    'managed',
    'NXBIN\managed',
    'nxbin\managed',
    'NXBIN\python'
)

function Get-MajorVersion {
    param([string]$VersionText)
    if ([string]::IsNullOrWhiteSpace($VersionText)) { return $null }
    $match = [regex]::Match($VersionText, '^\s*(\d{1,6})(?:\.|\s|$)')
    if (-not $match.Success) { return $null }
    return [int]$match.Groups[1].Value
}

function Get-VersionEvidence {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    if ($null -eq $item) { return $null }
    $fileVersion = $null
    $productVersion = $null
    try {
        if ($item.VersionInfo.FileVersion) { $fileVersion = $item.VersionInfo.FileVersion.Trim() }
        if ($item.VersionInfo.ProductVersion) { $productVersion = $item.VersionInfo.ProductVersion.Trim() }
    } catch {
        return $null
    }
    return [ordered]@{
        fileVersion    = $fileVersion
        productVersion = $productVersion
        major          = (Get-MajorVersion $fileVersion)
    }
}

function Test-IsDirectory {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    try { return (Get-Item -LiteralPath $Path -ErrorAction Stop).PSIsContainer } catch { return $false }
}

function Get-ChildDirectoryName {
    param([string]$Path)
    try {
        return Get-ChildItem -LiteralPath $Path -Directory -ErrorAction SilentlyContinue
    } catch {
        return @()
    }
}

# Returns candidate roots with the reason each one was considered.
function Get-CandidateRoot {
    param(
        [string[]]$Explicit,
        [string[]]$Extra,
        [int]$Depth
    )

    $candidates = [System.Collections.Generic.List[object]]::new()
    $seen = @{}

    $add = {
        param([string]$Path, [string]$Source, [bool]$Verify)
        if ([string]::IsNullOrWhiteSpace($Path)) { return }
        $full = $Path
        try { $full = (Get-Item -LiteralPath $Path -ErrorAction Stop).FullName } catch { return }
        if (-not (Test-IsDirectory $full)) { return }
        $key = $full.ToLowerInvariant()
        if ($seen.ContainsKey($key)) {
            if ($candidates[$seen[$key]].sources -notcontains $Source) {
                $candidates[$seen[$key]].sources += $Source
            }
            return
        }
        if ($Verify -and -not (Test-LooksLikeNxRoot $full)) { return }
        $seen[$key] = $candidates.Count
        $candidates.Add([pscustomobject]@{
            root    = $full
            sources = @($Source)
        })
    }

    foreach ($path in $Explicit) { & $add $path 'parameter' $true }
    foreach ($path in @($env:UGII_BASE_DIR, $env:UGII_ROOT_DIR)) { & $add $path 'environment' $true }
    foreach ($path in $Extra) { & $add $path 'extra-search-root' $false }

    # Scan plausible parents one level deep for NX-shaped directory names.
    $parents = [System.Collections.Generic.List[string]]::new()
    foreach ($drive in (Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
        if ($drive.Root -match '^[A-Za-z]:\\$') { $parents.Add($drive.Root) }
    }
    foreach ($pf in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($pf) { $parents.Add($pf) }
    }

    foreach ($parent in $parents) {
        if (-not (Test-IsDirectory $parent)) { continue }
        foreach ($child in (Get-ChildDirectoryName $parent)) {
            $name = $child.Name
            if ($name -match '^(?i)(Siemens)$') {
                # e.g. C:\Program Files\Siemens\NX 12.0
                foreach ($grand in (Get-ChildDirectoryName $child.FullName)) {
                    if ($grand.Name -match '(?i)(NX|UG)') { & $add $grand.FullName 'common-location' $true }
                }
                & $add $child.FullName 'common-location' $true
            } elseif ($name -match '(?i)^(NX|UG)') {
                # e.g. E:\UG 12.0, D:\NX12
                & $add $child.FullName 'common-location' $true
            }
        }
    }

    return $candidates
}

function Test-LooksLikeNxRoot {
    param([string]$Root)
    foreach ($name in @('ugraf.exe', 'run_journal.exe', 'NXOpen.dll', 'UGII', 'NXBIN')) {
        if (Test-Path -LiteralPath (Join-Path $Root $name)) { return $true }
    }
    foreach ($hint in $script:LayoutHints) {
        if ([string]::IsNullOrWhiteSpace($hint)) { continue }
        if (Test-Path -LiteralPath (Join-Path $Root (Join-Path $hint 'ugraf.exe'))) { return $true }
        if (Test-Path -LiteralPath (Join-Path $Root (Join-Path $hint 'NXOpen.dll'))) { return $true }
    }
    return $false
}

# Locate artifacts using known layout hints first, then a bounded sweep.
function Find-Artifact {
    param([string]$Root, [int]$Depth)

    $found = @{}
    $seenPaths = @{}
    foreach ($name in $script:ArtifactNames) {
        $found[$name] = [System.Collections.Generic.List[string]]::new()
    }

    # Windows paths are case-insensitive, so hint entries such as "NXBIN\managed"
    # and "nxbin\managed" resolve to the same file. Track visited paths with a
    # case-insensitive key so a single artifact is never reported twice.
    $addArtifact = {
        param([string]$Name, [string]$FullPath)
        $key = $FullPath.ToLowerInvariant()
        if ($seenPaths.ContainsKey($key)) { return }
        $seenPaths[$key] = $true
        $found[$Name].Add($FullPath)
    }

    foreach ($hint in $script:LayoutHints) {
        $dir = if ([string]::IsNullOrWhiteSpace($hint)) { $Root } else { Join-Path $Root $hint }
        if (-not (Test-IsDirectory $dir)) { continue }
        foreach ($name in $script:ArtifactNames) {
            $full = Join-Path $dir $name
            if (Test-Path -LiteralPath $full -PathType Leaf) { & $addArtifact $name $full }
        }
    }

    # Bounded sweep only for artifacts the hints did not cover, so unusual
    # layouts are still discovered without searching an entire disk.
    foreach ($name in $script:ArtifactNames) {
        if ($found[$name].Count -gt 0) { continue }
        $hits = Get-ChildItem -LiteralPath $Root -Recurse -Depth $Depth -Filter $name -File -ErrorAction SilentlyContinue
        foreach ($hit in $hits) { & $addArtifact $name $hit.FullName }
    }

    $result = [ordered]@{}
    foreach ($name in $script:ArtifactNames) {
        $result[$name] = @($found[$name])
    }
    return $result
}

function Get-PathNameHint {
    param([string]$Root)
    $tokens = [System.Collections.Generic.List[string]]::new()
    foreach ($match in [regex]::Matches($Root, '(?i)(NX|UG)[\s_-]*(\d{2,4}(?:\.\d+)*)')) {
        $tokens.Add($match.Value)
    }
    return [ordered]@{
        matched = ($tokens.Count -gt 0)
        tokens  = @($tokens)
        note    = 'A path token is a search hint only and is never treated as version proof.'
    }
}

function Get-LayoutInfo {
    param([string]$Root, $Artifacts)
    $ugii = $null
    $nxbin = $null
    $managed = $null
    $pythonDir = $null

    $ugraf = $Artifacts['ugraf.exe']
    if ($ugraf.Count -gt 0) {
        $ugii = Split-Path -Parent $ugraf[0]
        $nxbin = Join-Path $Root 'NXBIN'
        if (-not (Test-IsDirectory $nxbin)) { $nxbin = $ugii }
    }

    $nxopenDll = $Artifacts['NXOpen.dll']
    if ($nxopenDll.Count -gt 0) { $managed = Split-Path -Parent $nxopenDll[0] }

    foreach ($guess in @('NXBIN\python', 'nxbin\python', 'python')) {
        $candidate = Join-Path $Root $guess
        if (Test-IsDirectory $candidate) { $pythonDir = $candidate; break }
    }

    $embeddedPython = $null
    if ($pythonDir) {
        $dll = Get-ChildItem -LiteralPath $pythonDir -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '(?i)^python\d+\.dll$' } |
            Select-Object -First 1
        if ($dll) {
            $evidence = Get-VersionEvidence $dll.FullName
            $embeddedVersion = $null
            $embeddedMajor = $null
            if ($null -ne $evidence) {
                $embeddedVersion = $evidence.fileVersion
                $embeddedMajor = $evidence.major
            }
            $embeddedPython = [ordered]@{
                library        = $dll.FullName
                fileVersion    = $embeddedVersion
                major          = $embeddedMajor
                note           = 'Version of the interpreter embedded with NX. The host Python that runs the validators is a different interpreter.'
            }
        }
    }

    return [ordered]@{
        ugii           = $ugii
        nxbin          = $nxbin
        managed        = $managed
        python         = $pythonDir
        embeddedPython = $embeddedPython
    }
}

function Get-CandidateReport {
    param([object]$Candidate, [int]$Depth)

    $root = $Candidate.root
    $artifacts = Find-Artifact -Root $root -Depth $Depth
    $evidence = [System.Collections.Generic.List[object]]::new()
    $warnings = [System.Collections.Generic.List[string]]::new()

    foreach ($name in $script:VersionArtifactNames) {
        foreach ($path in $artifacts[$name]) {
            $version = Get-VersionEvidence $path
            if ($null -eq $version) { continue }
            $evidence.Add([ordered]@{
                kind           = 'file-version'
                artifact       = $name
                path           = $path
                fileVersion    = $version.fileVersion
                productVersion = $version.productVersion
                major          = $version.major
                authoritative  = $true
            })
        }
    }

    # Environment variables are recorded, but they are configuration rather
    # than file evidence, so they are not authoritative on their own.
    if ($root -ieq $env:UGII_BASE_DIR) {
        foreach ($name in @('UGII_VERSION', 'UGII_BASE_DIR', 'UGII_ROOT_DIR')) {
            $value = [Environment]::GetEnvironmentVariable($name)
            if ([string]::IsNullOrWhiteSpace($value)) { continue }
            $evidence.Add([ordered]@{
                kind           = 'environment-variable'
                artifact       = $name
                path           = $null
                fileVersion    = $value
                productVersion = $null
                major          = (Get-MajorVersion $value)
                authoritative  = $false
            })
        }
    }

    $artifactCount = 0
    foreach ($name in $script:ArtifactNames) { $artifactCount += $artifacts[$name].Count }

    $authoritative = @($evidence | Where-Object { $_.authoritative })
    $majors = @($authoritative | ForEach-Object { $_.major } | Where-Object { $null -ne $_ } | Sort-Object -Unique)

    $classification = 'not-found'
    if ($artifactCount -eq 0) {
        $classification = 'not-found'
    } elseif ($authoritative.Count -eq 0) {
        $classification = 'candidate-unconfirmed'
        $warnings.Add('Artifacts were found, but no authoritative version evidence could be read.')
    } elseif ($majors.Count -eq 0) {
        $classification = 'candidate-unconfirmed'
        $warnings.Add('Version strings were present but no major version could be parsed from them.')
    } elseif ($majors.Count -gt 1) {
        $classification = 'conflicting-evidence'
        $warnings.Add('Authoritative file versions disagree: major versions ' + ($majors -join ', ') + '.')
    } elseif ($majors[0] -eq 12) {
        $classification = 'confirmed-nx12'
    } else {
        $classification = 'not-nx12'
    }

    if ($classification -eq 'confirmed-nx12') {
        foreach ($item in $evidence) {
            if ($item.authoritative -and $null -ne $item.major -and $item.major -ne 12) {
                $warnings.Add('Confirmed NX 12 by majority evidence, but ' + $item.artifact + ' reports major version ' + $item.major + '.')
            }
        }
    }

    return [ordered]@{
        root           = $root
        sources        = @($Candidate.sources)
        classification = $classification
        pathNameHint   = (Get-PathNameHint -Root $root)
        artifacts      = $artifacts
        evidence       = @($evidence)
        layout         = (Get-LayoutInfo -Root $root -Artifacts $artifacts)
        warnings       = @($warnings)
    }
}

function Write-TextReport {
    param([object]$Report)

    Write-Output 'NX installation inspection (read-only)'
    Write-Output ('Generated: ' + $Report.timestamp)
    Write-Output ('Candidate roots evaluated: ' + $Report.candidates.Count)
    Write-Output ''

    $index = 0
    foreach ($candidate in $Report.candidates) {
        $index++
        Write-Output ('[' + $index + '] ' + $candidate.root)
        Write-Output ('    source        : ' + ($candidate.sources -join ', '))
        Write-Output ('    result        : ' + $candidate.classification)
        Write-Output ('    path hint     : ' + $(if ($candidate.pathNameHint.matched) { 'yes (' + ($candidate.pathNameHint.tokens -join ', ') + ')' } else { 'no' }))

        if ($candidate.evidence.Count -gt 0) {
            Write-Output '    evidence      :'
            foreach ($item in $candidate.evidence) {
                $flag = if ($item.authoritative) { 'authoritative' } else { 'not authoritative' }
                Write-Output ('      ' + $item.kind + ' ' + $item.artifact + ' = ' + $item.fileVersion + ' (major ' + $item.major + ', ' + $flag + ')')
            }
        }

        Write-Output '    artifacts     :'
        foreach ($name in $script:ArtifactNames) {
            $paths = $candidate.artifacts[$name]
            if ($paths.Count -eq 0) { continue }
            Write-Output ('      ' + $name + ' : ' + ($paths -join ' ; '))
        }

        $embedded = $candidate.layout.embeddedPython
        if ($embedded) {
            Write-Output ('    embedded py   : ' + $embedded.fileVersion + ' (' + $embedded.library + ')')
        }
        if ($candidate.layout.managed) {
            Write-Output ('    managed dir   : ' + $candidate.layout.managed)
        }

        foreach ($warning in $candidate.warnings) {
            Write-Output ('    WARNING       : ' + $warning)
        }
        Write-Output ''
    }

    Write-Output 'Summary'
    Write-Output ('  classification : ' + $Report.summary.classification)
    if ($Report.summary.selectedRoot) {
        Write-Output ('  selected root  : ' + $Report.summary.selectedRoot)
    } else {
        Write-Output '  selected root  : (none)'
    }
    Write-Output ('  reason         : ' + $Report.summary.selectionReason)
    foreach ($note in $Report.summary.notes) {
        Write-Output ('  note           : ' + $note)
    }
    Write-Output ('  exit code      : ' + $Report.exitCode)
}

# ---------------------------------------------------------------- main

try {
    if ($SearchDepth -lt 0) { throw 'SearchDepth must be zero or greater.' }
} catch {
    Write-Error $_
    exit 2
}

# @() keeps a single candidate from being unrolled into a bare object.
$candidateRoots = @(Get-CandidateRoot -Explicit $NxRoot -Extra $ExtraSearchRoot -Depth $SearchDepth)

$candidateReports = [System.Collections.Generic.List[object]]::new()
foreach ($candidate in $candidateRoots) {
    $candidateReports.Add((Get-CandidateReport -Candidate $candidate -Depth $SearchDepth))
}

$confirmed = @($candidateReports | Where-Object { $_.classification -eq 'confirmed-nx12' })
$conflicting = @($candidateReports | Where-Object { $_.classification -eq 'conflicting-evidence' })
$notes = [System.Collections.Generic.List[string]]::new()
$notes.Add('Path names are treated as hints only; version confirmation requires file version evidence.')

$selectedRoot = $null
$classification = 'not-found'
$reason = ''
$exitCode = 1

if ($conflicting.Count -gt 0) {
    $classification = 'conflicting-evidence'
    $reason = 'At least one candidate reports disagreeing authoritative file versions. No root is selected automatically.'
    $exitCode = 5
} elseif ($confirmed.Count -eq 1) {
    $classification = 'confirmed-nx12'
    $selectedRoot = $confirmed[0].root
    $reason = 'Exactly one candidate was confirmed as major version 12.'
    $exitCode = 0
} elseif ($confirmed.Count -gt 1) {
    $classification = 'ambiguous'
    $reason = 'More than one candidate was confirmed as NX 12. Select one explicitly with -NxRoot before compiling or executing.'
    $exitCode = 4
    $notes.Add('Confirmed roots: ' + (($confirmed | ForEach-Object { $_.root }) -join ' ; '))
} elseif ($candidateReports.Count -eq 0) {
    $classification = 'not-found'
    $reason = 'No candidate NX installation root was discovered.'
    $exitCode = 1
} else {
    $classification = 'unconfirmed'
    $reason = 'Candidates were discovered, but none could be confirmed as NX 12.'
    $exitCode = 3
}

$report = [ordered]@{
    schemaVersion       = 1
    tool                = 'inspect-nx-installation.ps1'
    timestamp           = (Get-Date).ToString('o')
    readOnly            = $true
    hostPowerShell      = $PSVersionTable.PSVersion.ToString()
    candidates          = @($candidateReports)
    summary             = [ordered]@{
        classification  = $classification
        selectedRoot    = $selectedRoot
        selectionReason = $reason
        confirmedRoots  = @($confirmed | ForEach-Object { $_.root })
        notes           = @($notes)
    }
    exitCode            = $exitCode
}

if ($Json) {
    $report | ConvertTo-Json -Depth 12
} else {
    Write-TextReport -Report $report
}

exit $exitCode
