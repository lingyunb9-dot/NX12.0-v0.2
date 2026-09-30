<#
.SYNOPSIS
Render a Python or C# NX 12 journal scaffold from the skill templates.

.DESCRIPTION
Copies the language template from assets/templates, substitutes the
{{JOURNAL_NAME}} and {{DESCRIPTION}} placeholders, and writes the result to the
requested path.

The two placeholders are escaped differently on purpose, because they land in
different syntactic contexts:

  * {{JOURNAL_NAME}} is substituted into a string literal, so backslashes,
    quotes, newlines and tabs are escaped for the target language.
  * {{DESCRIPTION}} is substituted into a line comment, so newlines and
    control characters are flattened into single spaces. Left alone, a newline
    in a description would end the comment and inject live code into the
    generated file.

User input is only ever used through literal string replacement. It is never
passed to Invoke-Expression, a script block, or any command interpreter.

The generated file is a SCAFFOLD. It still needs a version-verified modeling
body before it should be run against a part, and this script never reports the
result as verified.

.PARAMETER Language
python or csharp.

.PARAMETER OutputPath
Destination file. Parent directories are created when missing.

.PARAMETER JournalName
Name recorded in the journal and used for the undo mark.

.PARAMETER Description
Short description placed in the file header comment.

.PARAMETER TemplatePath
Override the template location. Defaults to the template for the language.

.PARAMETER Force
Overwrite an existing output file. Without it, an existing file is refused.

.PARAMETER Json
Emit a machine-readable result document instead of the text summary.

.OUTPUTS
Exit codes:
  0  the scaffold was written
  2  usage error
  3  the output file already exists and -Force was not supplied
  4  the template could not be found or read

.EXAMPLE
.\create-journal-template.ps1 -Language python -OutputPath .\my_journal.py `
    -JournalName "BlockJournal" -Description "Creates a block from a sketch"

.EXAMPLE
.\create-journal-template.ps1 -Language csharp -OutputPath .\MyJournal.cs `
    -JournalName "BlockJournal" -Description "Creates a block" -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('python', 'csharp')]
    [string]$Language,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [Parameter(Mandatory = $true)]
    [string]$JournalName,

    [string]$Description = 'Describes what this journal does and which part it expects.',

    [string]$TemplatePath,

    [switch]$Force,

    [switch]$Json
)

$ErrorActionPreference = 'Stop'

$script:SkillRoot = Split-Path -Parent $PSScriptRoot

$script:TemplateNames = @{
    'python' = 'python-journal.py'
    'csharp' = 'csharp-journal.cs'
}

# File encodings chosen so the target toolchain reads non-ASCII correctly:
# the NX 12 Python runtime accepts UTF-8 without a BOM, while csc.exe assumes
# the local ANSI code page unless a BOM is present.
$script:EncodingNames = @{
    'python' = 'utf-8-no-bom'
    'csharp' = 'utf-8-with-bom'
}

function Get-TemplatePath {
    param([string]$Requested, [string]$TargetLanguage)
    if (-not [string]::IsNullOrWhiteSpace($Requested)) { return $Requested }
    return (Join-Path $script:SkillRoot ('assets\templates\' + $script:TemplateNames[$TargetLanguage]))
}

# Escape a value for use inside a double-quoted string literal of the target
# language. Python and C# agree on the escapes needed here (backslash, double
# quote, carriage return, newline, tab), so one implementation serves both;
# TargetLanguage is kept so a divergence can be handled without changing the
# call sites.
#
# A literal backslash must be doubled. Emitting it unchanged would let it merge
# with the following character into an escape sequence the user never asked
# for: the input "\path" would land in the file as "\path", which Python reads
# as an invalid escape and C# would eventually reject.
#
# Each input character is appended exactly once, so an escape sequence produced
# here is never rescanned.
function ConvertTo-StringLiteral {
    param([string]$Value, [string]$TargetLanguage)

    $builder = [System.Text.StringBuilder]::new()
    foreach ($character in $Value.ToCharArray()) {
        $code = [int][char]$character
        if ($character -eq '\') { [void]$builder.Append('\\') }
        elseif ($character -eq '"') { [void]$builder.Append('\"') }
        elseif ($character -eq "`r") { [void]$builder.Append('\r') }
        elseif ($character -eq "`n") { [void]$builder.Append('\n') }
        elseif ($character -eq "`t") { [void]$builder.Append('\t') }
        elseif ($code -lt 32) {
            # Control characters have no printable form; drop them rather than
            # emit an escape sequence that the target language may not accept.
        }
        else { [void]$builder.Append($character) }
    }
    return $builder.ToString()
}

# Flatten a value for use inside a line comment. Newlines would terminate the
# comment, so they collapse to spaces along with other control characters.
function ConvertTo-CommentText {
    param([string]$Value)

    $builder = [System.Text.StringBuilder]::new()
    foreach ($character in $Value.ToCharArray()) {
        $code = [int][char]$character
        if ($code -lt 32) {
            if ($builder.Length -gt 0) {
                $last = $builder[$builder.Length - 1]
                if ($last -ne ' ') { [void]$builder.Append(' ') }
            }
        }
        else { [void]$builder.Append($character) }
    }
    return $builder.ToString().Trim()
}

# Report a failure on stderr and terminate with a documented exit code.
#
# Write-Error is deliberately avoided here: with $ErrorActionPreference set to
# Stop it raises a terminating error and the script never reaches its own
# `exit`, so callers would never see the documented codes.
function Write-Failure {
    param([string]$Message, [int]$Code)
    [Console]::Error.WriteLine($Message)
    exit $Code
}

function Write-Result {
    param([object]$Result, [switch]$AsJson)

    if ($AsJson) {
        $Result | ConvertTo-Json -Depth 8
        return
    }

    Write-Output ('created  : ' + $Result.outputPath)
    Write-Output ('language : ' + $Result.language)
    Write-Output ('template : ' + $Result.templatePath)
    Write-Output ('encoding : ' + $Result.encoding)
    Write-Output ('overwrote: ' + $Result.overwritten)
    Write-Output ('status   : ' + $Result.verificationState)
    foreach ($note in $Result.notes) { Write-Output ('note     : ' + $note) }
}

# ------------------------------------------------------------------- main

try {
    $templatePath = Get-TemplatePath -Requested $TemplatePath -TargetLanguage $Language
} catch {
    Write-Failure -Message $_.Exception.Message -Code 2
}

if ([string]::IsNullOrWhiteSpace($JournalName)) {
    Write-Failure -Message 'JournalName must contain at least one visible character.' -Code 2
}

if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
    Write-Failure -Message ('Template not found: ' + $templatePath) -Code 4
}

$resolvedOutput = $OutputPath
try {
    $parent = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    if (-not [System.IO.Path]::IsPathRooted($resolvedOutput)) {
        $resolvedOutput = Join-Path (Get-Location).Path $resolvedOutput
    }
} catch {
    Write-Failure -Message $_.Exception.Message -Code 2
}

$overwritten = $false
if (Test-Path -LiteralPath $resolvedOutput -PathType Leaf) {
    if (-not $Force) {
        Write-Failure -Message ('Output already exists: ' + $resolvedOutput + ' . Pass -Force to overwrite it.') -Code 3
    }
    $overwritten = $true
}

$templateText = Get-Content -LiteralPath $templatePath -Raw -Encoding UTF8

$escapedName = ConvertTo-StringLiteral -Value $JournalName -TargetLanguage $Language
$commentText = ConvertTo-CommentText -Value $Description

$rendered = $templateText.Replace('{{JOURNAL_NAME}}', $escapedName)
$rendered = $rendered.Replace('{{DESCRIPTION}}', $commentText)

$encoding = [System.Text.UTF8Encoding]::new($Language -eq 'csharp')
[System.IO.File]::WriteAllText($resolvedOutput, $rendered, $encoding)

$notes = @(
    'The generated file is a scaffold: its modeling body still contains an UNVERIFIED placeholder.',
    'Nothing here verifies that the NXOpen calls in the resulting journal exist in the target NX 12 installation.',
    'Run scripts/validate-journal.py --mode ready after filling in verified API evidence, and scripts/check-api-evidence.py --nx-root <NX root> to resolve that evidence against a local index.'
)

$result = [ordered]@{
    schemaVersion     = 1
    tool              = 'create-journal-template.ps1'
    language          = $Language
    outputPath        = $resolvedOutput
    templatePath      = (Resolve-Path -LiteralPath $templatePath).Path
    journalName       = $JournalName
    description       = $commentText
    encoding          = $script:EncodingNames[$Language]
    bytesWritten      = (Get-Item -LiteralPath $resolvedOutput).Length
    overwritten       = $overwritten
    verificationState = 'scaffold'
    notes             = $notes
}

Write-Result -Result $result -AsJson:$Json
exit 0
