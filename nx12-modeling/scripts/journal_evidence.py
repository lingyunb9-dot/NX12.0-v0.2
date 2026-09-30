"""Parse and check ``NX12-API:`` evidence comments in NX journals.

A comment is only a claim. This module separates three things that are easy to
conflate:

* **Structure** -- does the comment carry the locating information a reviewer
  needs (member identity, source, version, binding language)?
* **Resolution** -- does the member exist in a local NXOpen documentation
  index, when one was supplied?
* **Truth** -- whether the call actually behaves as intended in NX 12, which
  nothing here can establish. Comments are never treated as proof, and a
  comment asserting verification that the index contradicts is reported as a
  contradiction rather than accepted.

Command syntax
--------------
    # NX12-API: <MemberPath> | source=<source> | binding=<lang> | version=<x.y.z>
                              [| file=<evidence file>] [| status=<status>]

``member``, ``source``, ``binding`` and ``version`` are always required.
``file`` is additionally required for the local-index style sources, because
"source=local-xml" on its own does not say which index was consulted.

The module stays on conservative Python 3 syntax so it can also run under the
Python 3.6 interpreter embedded in NX 12.
"""

import io
import os
import re
import sys

try:
    import tokenize
except ImportError:  # pragma: no cover - tokenize is always present in Py3
    tokenize = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nxopen_index import (  # noqa: E402
    EVIDENCE_BINDINGS,
    EVIDENCE_SOURCES,
    STATUS_ELSEWHERE,
    STATUS_MEMBER,
    STATUS_MEMBER_UNDOCUMENTED,
    STATUS_TYPE,
    STATUS_TYPE_UNDOCUMENTED,
    compare_versions,
    major_version,
)

MARKER = "NX12-API:"

REQUIRED_FIELDS = ("source", "binding", "version")
FILE_REQUIRED_SOURCES = ("local-xml", "local-index")

# The only NX release this skill covers. A version whose leading component is
# anything else is a different release, not a variant of NX 12.
EVIDENCE_VERSION_MAJOR = 12

# The shipped NXOpen XML documentation describes the .NET binding. It cannot
# speak for the Python binding, so it is labelled explicitly.
INDEX_BINDING = "dotnet"

# Values that are placeholders rather than evidence. Comparing case-folded
# keeps the list short and still catches TODO / TBD / N/A spellings.
PLACEHOLDER_VALUES = {
    "",
    "todo",
    "tbd",
    "tba",
    "fixme",
    "none",
    "null",
    "n/a",
    "na",
    "unknown",
    "unset",
    "placeholder",
    "xxx",
    "???",
    "...",
    "x",
    "false",
}

VERSION_RE = re.compile(r"^\d+(\.\d+){1,3}$")

# Statuses a comment may claim, mirroring references/api-validation.md.
CLAIMED_STATUSES = (
    "verified-local",
    "verified-stub",
    "verified-recording",
    "inferred",
    "unverified",
)

# Statuses the index is able to corroborate by itself.
INDEX_CONFIRMED_STATUSES = ("member-documented", "type-documented")


def _strip_comment_marker(text):
    return text.strip()


def parse_python_comments(text):
    """Yield (line, comment_text) for real Python comments only.

    Uses the tokenizer so ``# NX12-API: ...`` inside a string literal is never
    mistaken for a comment, and a commented-out call is never mistaken for
    code.
    """
    if tokenize is None:
        return []
    results = []
    try:
        stream = io.StringIO(text)
        for token in tokenize.generate_tokens(stream.readline):
            if token.type == tokenize.COMMENT:
                results.append((token.start[0], token.string))
    except Exception:
        # A syntax error still leaves comments worth reading, so fall back to a
        # line scan rather than losing them. Callers are told the difference by
        # validate-journal.py, which reports the syntax error separately.
        for number, line in enumerate(text.splitlines(), start=1):
            index = line.find("#")
            if index >= 0:
                results.append((number, line[index:]))
    return results


def strip_csharp_noncode(text):
    """Replace comments and string literals in C# source with blanks.

    This is a light scan, not a parser. It keeps character positions and line
    numbers stable so the caller can still report locations. Callers must not
    describe the result as C# compilation or full syntax validation.
    """
    out = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]

        # Verbatim string: @"..." where "" is an escaped quote.
        if char == "@" and index + 1 < length and text[index + 1] == '"':
            out.append("  ")
            index += 2
            while index < length:
                if text[index] == '"':
                    if index + 1 < length and text[index + 1] == '"':
                        out.append("  ")
                        index += 2
                        continue
                    out.append(" ")
                    index += 1
                    break
                out.append("\n" if text[index] == "\n" else " ")
                index += 1
            continue

        # Character literal such as '/' which must not start a comment.
        if char == "'":
            out.append(" ")
            index += 1
            while index < length:
                if text[index] == "\\" and index + 1 < length:
                    out.append("  ")
                    index += 2
                    continue
                if text[index] == "'":
                    out.append(" ")
                    index += 1
                    break
                out.append("\n" if text[index] == "\n" else " ")
                index += 1
            continue

        if char == '"':
            out.append(" ")
            index += 1
            while index < length:
                if text[index] == "\\" and index + 1 < length:
                    out.append("  ")
                    index += 2
                    continue
                if text[index] == '"':
                    out.append(" ")
                    index += 1
                    break
                out.append("\n" if text[index] == "\n" else " ")
                index += 1
            continue

        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                out.append(" ")
                index += 1
            continue

        if char == "/" and index + 1 < length and text[index + 1] == "*":
            out.append("  ")
            index += 2
            while index < length:
                if text[index] == "*" and index + 1 < length and text[index + 1] == "/":
                    out.append("  ")
                    index += 2
                    break
                out.append("\n" if text[index] == "\n" else " ")
                index += 1
            continue

        out.append(char)
        index += 1

    return "".join(out)


def parse_csharp_comments(text):
    """Yield (line, comment_text) for C# comments, skipping strings."""
    results = []
    index = 0
    length = len(text)
    line = 1
    while index < length:
        char = text[index]

        if char == "@" and index + 1 < length and text[index + 1] == '"':
            index += 2
            while index < length:
                if text[index] == "\n":
                    line += 1
                elif text[index] == '"':
                    if index + 1 < length and text[index + 1] == '"':
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            continue

        if char == '"':
            index += 1
            while index < length:
                if text[index] == "\n":
                    line += 1
                if text[index] == "\\" and index + 1 < length:
                    index += 2
                    continue
                if text[index] == '"':
                    index += 1
                    break
                index += 1
            continue

        if char == "'":
            index += 1
            while index < length:
                if text[index] == "\\" and index + 1 < length:
                    index += 2
                    continue
                if text[index] == "'":
                    index += 1
                    break
                index += 1
            continue

        if char == "/" and index + 1 < length and text[index + 1] == "/":
            start = index
            while index < length and text[index] != "\n":
                index += 1
            results.append((line, text[start:index]))
            continue

        if char == "/" and index + 1 < length and text[index + 1] == "*":
            start = index
            index += 2
            while index < length:
                if text[index] == "\n":
                    line += 1
                if text[index] == "*" and index + 1 < length and text[index + 1] == "/":
                    index += 2
                    break
                index += 1
            results.append((line, text[start:index]))
            continue

        if char == "\n":
            line += 1
        index += 1

    return results


def comments_for(text, language):
    if language == "python":
        return parse_python_comments(text)
    return parse_csharp_comments(text)


def parse_evidence_comment(line, comment_text):
    """Turn one comment into an evidence entry, or None when it is not one."""
    position = comment_text.find(MARKER)
    if position < 0:
        return None

    body = comment_text[position + len(MARKER):].strip()
    # A trailing block-comment terminator must not become part of the value.
    body = body.replace("*/", "").strip()

    segments = [segment.strip() for segment in body.split("|")]
    member = segments[0].strip()
    fields = {}
    malformed = []

    for segment in segments[1:]:
        if not segment:
            continue
        key, separator, value = segment.partition("=")
        if not separator:
            malformed.append(segment)
            continue
        fields[key.strip().lower()] = value.strip()

    return {
        "line": line,
        "member": member,
        "fields": fields,
        "malformedSegments": malformed,
        "raw": comment_text.strip(),
    }


def _is_placeholder(value):
    return value is None or value.strip().lower() in PLACEHOLDER_VALUES


def _normalize_path(path):
    """A comparable key for a path: absolute, normalized, case-folded.

    Windows treats ``NXBIN\\managed\\NXOpen.xml`` and
    ``nxbin\\managed\\NXOpen.xml`` as the same file, so comparing the raw
    strings would report a false mismatch.
    """
    if not path:
        return None
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


class SourceContext(object):
    """Resolves and vets the ``file=`` field of a ``local-xml`` evidence entry.

    Resolution follows the documented convention, and never guesses:

    * an absolute ``file`` is used as written;
    * a relative ``file`` is resolved against ``nx_root`` when the caller gave
      one;
    * otherwise it is resolved against the directory of the journal being
      checked;
    * a name is never matched against the loaded set by filename or suffix
      alone.

    Verification then asks two separate questions: does the file exist, and is
    it one of the XML files this run actually loaded?
    """

    def __init__(self, index, nx_root=None, journal_path=None):
        self.index = index
        self.nx_root = nx_root
        self.journal_path = journal_path
        self.loaded_keys = set()
        if index is not None:
            for path in index.xml_paths:
                key = _normalize_path(path)
                if key:
                    self.loaded_keys.add(key)

    def base_directory(self):
        """The single directory relative paths are resolved against, or None."""
        if self.nx_root:
            return os.path.abspath(self.nx_root)
        if self.journal_path:
            return os.path.dirname(os.path.abspath(self.journal_path))
        return None

    def resolve(self, declared):
        """Absolute path the evidence names, or None when there is no base.

        The path is returned even when nothing exists there, so the caller can
        report the location it actually looked at.
        """
        if not declared:
            return None
        text = declared.strip().strip('"').strip("'")
        if not text:
            return None
        if os.path.isabs(text):
            return os.path.abspath(os.path.normpath(text))
        base = self.base_directory()
        if base is None:
            return None
        return os.path.abspath(os.path.normpath(os.path.join(base, text)))

    def is_loaded(self, path):
        """Whether *path* is one of the XML files this index was built from."""
        key = _normalize_path(path)
        return key is not None and key in self.loaded_keys

    def recorded_in_declared_file(self, resolution, declared_path):
        """Whether the resolved entry is recorded in the declared file.

        Only meaningful when more than one XML file was loaded.
        """
        recorded = resolution.get("matchedSources") if resolution else None
        if not recorded:
            return False
        declared_key = _normalize_path(declared_path)
        if declared_key is None:
            return False
        for candidate in recorded:
            if _normalize_path(candidate) == declared_key:
                return True
        return False


def _check_evidence_version(entry, index, issue):
    """Check the evidence version against NX 12 and against the index version.

    Returns True only when the two versions are exactly equal after padding
    missing trailing components with zero. Everything else -- an unknown index
    version, an index from another release, a differing patch level -- is
    reported and refused, because none of them is a confirmed match.
    """
    fields = entry["fields"]
    raw = (fields.get("version") or "").strip()
    verdict = {
        "evidenceVersion": raw or None,
        "evidenceMajor": None,
        "indexVersion": None,
        "indexMajor": None,
        "verdict": "not-checked",
    }
    entry["versionCheck"] = verdict

    if not raw or _is_placeholder(raw):
        return False

    major = major_version(raw)
    verdict["evidenceMajor"] = major
    if major is None:
        # The dotted-version format warning already covers this.
        verdict["verdict"] = "unparseable"
        return False
    if major != EVIDENCE_VERSION_MAJOR:
        issue(
            "error",
            "evidence-version-not-nx12",
            "Evidence version '" + raw + "' has major version " + str(major)
            + ". This skill covers NX " + str(EVIDENCE_VERSION_MAJOR)
            + " only, so a leading component of " + str(major)
            + " names a different release.",
        )
        verdict["verdict"] = "evidence-not-nx12"
        return False

    if index is None:
        verdict["verdict"] = "no-index"
        return False

    index_version = index.assembly_version()
    verdict["indexVersion"] = index_version
    if index_version is None:
        issue(
            "warning",
            "index-version-unknown",
            "The version of the supplied index could not be read, so the "
            "evidence version cannot be compared with it. The version is NOT "
            "confirmed.",
        )
        verdict["verdict"] = "index-version-unknown"
        return False

    index_major = major_version(index_version)
    verdict["indexMajor"] = index_major
    if index_major != EVIDENCE_VERSION_MAJOR:
        issue(
            "warning",
            "index-version-not-nx12",
            "The supplied index reports version " + str(index_version)
            + ", whose major version is not " + str(EVIDENCE_VERSION_MAJOR)
            + ". It cannot serve as an NX 12 source for this evidence.",
        )
        verdict["verdict"] = "index-not-nx12"
        return False

    comparison = compare_versions(raw, index_version)
    if comparison == "equal":
        verdict["verdict"] = "matches"
        return True
    if comparison in ("patch-differs", "major-differs"):
        issue(
            "warning",
            "evidence-version-patch-differs",
            "Evidence version " + raw + " and index version "
            + str(index_version) + " are not exactly the same version, so this "
            "is not a confirmed match.",
        )
        verdict["verdict"] = "patch-differs"
        return False

    issue(
        "warning",
        "evidence-version-not-comparable",
        "Evidence version '" + raw + "' could not be compared with index "
        "version '" + str(index_version) + "'.",
    )
    verdict["verdict"] = "unparseable"
    return False


def _check_binding(entry, index, language, issue):
    """Check the declared binding against the index and the journal language.

    Returns True only when the index is able to speak for the declared binding
    and the declaration agrees with the language being checked.
    """
    fields = entry["fields"]
    binding = (fields.get("binding") or "").strip().lower()
    verdict = {
        "declared": binding or None,
        "indexBinding": None,
        "language": language,
        "verdict": "not-checked",
    }
    entry["bindingCheck"] = verdict

    if not binding or _is_placeholder(binding):
        return False

    if index is not None:
        verdict["indexBinding"] = INDEX_BINDING
        if binding != INDEX_BINDING:
            issue(
                "warning",
                "binding-not-verified-by-dotnet-index",
                "Evidence declares binding=" + binding + ", but the index in "
                "use is the NXOpen .NET XML documentation. A name found there "
                "is a .NET documentation lead only. The " + binding
                + " binding is NOT verified by it.",
            )
            verdict["verdict"] = "index-cannot-confirm"
            return False

    if language == "python" and binding == "dotnet":
        issue(
            "warning",
            "binding-dotnet-in-python-source",
            "This evidence cites the .NET binding, but the file being checked "
            "is Python. Keep it as a reference if it is useful, but it does not "
            "prove the Python binding of this call.",
        )
        verdict["verdict"] = "language-mismatch"
        return False

    if verdict["verdict"] == "not-checked":
        verdict["verdict"] = "consistent"
    return True


def _check_evidence_source(entry, index, source_context, issue):
    """Check the declared source file of a ``local-xml``/``local-index`` entry.

    Returns True only when the file exists *and* is one of the XML files the
    index was actually built from.
    """
    fields = entry["fields"]
    source = (fields.get("source") or "").strip().lower()
    declared = (fields.get("file") or "").strip()
    verdict = {
        "declared": declared or None,
        "resolved": None,
        "loaded": False,
        "verdict": "not-checked",
    }
    entry["sourceCheck"] = verdict

    if source in FILE_REQUIRED_SOURCES:
        pass
    elif source and not _is_placeholder(source):
        # Some other source. Nothing here can verify it, and a same-named XML
        # entry must not be used to certify it.
        verdict["verdict"] = "no-local-verifier"
        issue(
            "info",
            "evidence-source-not-locally-checked",
            "source=" + source + " has no local verifier in this tool, so this "
            "entry is marked NOT checked. Its format was validated.",
        )
        return False
    else:
        return False

    if index is None:
        # Without an index there is no loaded set to compare against, and the
        # report already says API truth was not checked.
        verdict["verdict"] = "no-index"
        return False

    if not declared or _is_placeholder(declared):
        # The format check already reported evidence-missing-file.
        verdict["verdict"] = "missing"
        return False

    if source_context is None:
        verdict["verdict"] = "unresolvable"
        return False

    resolved = source_context.resolve(declared)
    verdict["resolved"] = resolved
    if resolved is None:
        issue(
            "warning",
            "evidence-source-unresolvable",
            "The relative source file '" + declared + "' cannot be resolved: "
            "neither --nx-root nor the journal's own directory is available as "
            "a base. The source file was NOT checked.",
        )
        verdict["verdict"] = "unresolvable"
        return False

    if not os.path.isfile(resolved):
        issue(
            "error",
            "evidence-source-missing",
            "The declared evidence file does not exist: " + resolved,
        )
        verdict["verdict"] = "missing"
        return False

    if not source_context.is_loaded(resolved):
        issue(
            "error",
            "evidence-source-not-loaded",
            "The declared evidence file exists but is not one of the XML files "
            "this check actually loaded: " + resolved,
        )
        verdict["verdict"] = "not-loaded"
        return False

    verdict["loaded"] = True
    verdict["verdict"] = "verified"
    return True


def _check_member_is_in_declared_file(entry, index, source_context, issue):
    """Require the member to be recorded in the file the evidence names.

    Only meaningful when several XML files were loaded. A member found in some
    other file of the set does not certify the declared source.
    """
    resolution = entry.get("resolution")
    verdict = entry.get("sourceCheck") or {}
    if not resolution or verdict.get("verdict") != "verified":
        return False
    if index is None or source_context is None:
        return False
    if resolution.get("status") not in INDEX_CONFIRMED_STATUSES:
        return False
    if len(index.xml_paths) < 2:
        # With a single file there is nothing to confuse it with.
        return True

    recorded = resolution.get("matchedSources") or []
    if source_context.recorded_in_declared_file(resolution, verdict.get("resolved")):
        return True

    if recorded:
        issue(
            "error",
            "evidence-source-mismatch",
            "The member is recorded in "
            + ", ".join(sorted(os.path.basename(path) for path in recorded))
            + ", which is not the file this evidence names. A name found in "
            "another XML file does not certify the declared source.",
        )
    return False


def check_entry(entry, index=None, mode="ready", language=None, source_context=None):
    """Return a list of issue dicts for one evidence entry.

    The verdicts stay separate on purpose:

    * *structure* -- the comment carries the fields a reviewer needs;
    * *documentation* -- the member is recorded in the supplied index;
    * *version*, *binding*, *source* -- the claim agrees with the index that
      was actually loaded.

    ``fullyMatched`` is set only when all of them hold. Even then it means the
    documented name, version, binding and source lined up; it does not mean the
    call is correct, that the code calls it, or that the journal runs.
    """
    issues = []
    member = entry["member"]
    fields = entry["fields"]

    def issue(level, code, message):
        issues.append(
            {
                "level": level,
                "code": code,
                "message": message,
                "line": entry["line"],
            }
        )

    for segment in entry["malformedSegments"]:
        issue(
            "error",
            "evidence-malformed",
            "Evidence segment is not key=value: " + segment,
        )

    if not member or _is_placeholder(member):
        issue(
            "error",
            "evidence-empty-member",
            "Evidence must name the NXOpen member it applies to.",
        )
    elif not member.startswith("NXOpen"):
        issue(
            "warning",
            "evidence-member-not-nxopen",
            "Evidence member does not start with NXOpen: " + member,
        )

    for required in REQUIRED_FIELDS:
        value = fields.get(required)
        if required not in fields:
            issue(
                "error",
                "evidence-missing-field",
                "Evidence is missing the required field '" + required + "'.",
            )
        elif _is_placeholder(value):
            issue(
                "error",
                "evidence-placeholder-value",
                "Evidence field '" + required + "' holds a placeholder value: "
                + repr(value),
            )

    source = (fields.get("source") or "").strip().lower()
    if source and not _is_placeholder(source):
        if source not in EVIDENCE_SOURCES:
            issue(
                "warning",
                "evidence-unknown-source",
                "Unknown evidence source '" + source + "'. Expected one of: "
                + ", ".join(EVIDENCE_SOURCES)
                + ".",
            )
        elif source in FILE_REQUIRED_SOURCES and _is_placeholder(fields.get("file")):
            issue(
                "error",
                "evidence-missing-file",
                "source=" + source
                + " must also name the index or file it was read from.",
            )

    binding = (fields.get("binding") or "").strip().lower()
    if binding and not _is_placeholder(binding) and binding not in EVIDENCE_BINDINGS:
        issue(
            "error",
            "evidence-unknown-binding",
            "Unknown binding '" + binding + "'. Expected one of: "
            + ", ".join(EVIDENCE_BINDINGS) + ".",
        )

    version = (fields.get("version") or "").strip()
    if version and not _is_placeholder(version) and not VERSION_RE.match(version):
        issue(
            "warning",
            "evidence-version-not-dotted",
            "Evidence version does not look like a dotted version: " + version,
        )

    claimed = (fields.get("status") or "").strip().lower()
    if claimed and claimed not in CLAIMED_STATUSES:
        issue(
            "warning",
            "evidence-unknown-status",
            "Unknown evidence status '" + claimed + "'. Expected one of: "
            + ", ".join(CLAIMED_STATUSES) + ".",
        )

    resolution = None
    if index is not None and member and member.startswith("NXOpen"):
        resolution = index.lookup(member)
        status = resolution["status"]
        entry["resolution"] = resolution

        if status in INDEX_CONFIRMED_STATUSES:
            issue(
                "info",
                "api-resolved",
                "Resolved in the local index: " + status + ".",
            )
        elif status == STATUS_ELSEWHERE:
            issue(
                "warning",
                "api-declared-elsewhere",
                "Not documented on the named type; a member of this name is "
                "documented elsewhere (possibly a base class): "
                + ", ".join(resolution["declaredOn"][:3])
                + ".",
            )
        elif status == STATUS_TYPE_UNDOCUMENTED:
            issue(
                "warning",
                "api-type-not-documented",
                "This type is not documented in the supplied index. The index "
                "is incomplete, so this is not proof the type is absent.",
            )
        elif status == STATUS_MEMBER_UNDOCUMENTED:
            issue(
                "warning",
                "api-not-documented",
                "Not documented in the supplied index. The index is "
                "incomplete, so this is not proof the member is absent.",
            )
        if resolution.get("truncated"):
            issue(
                "warning",
                "api-index-truncated",
                "The index was truncated, so a missing member proves nothing.",
            )

        if claimed == "verified-local" and status not in INDEX_CONFIRMED_STATUSES:
            # A missing XML entry is an incomplete index, not proof the API is
            # absent. The claim is therefore reported as not corroborated
            # rather than as a contradiction, and the wording says so.
            issue(
                "warning",
                "evidence-not-corroborated",
                "Evidence claims status=verified-local, but this index reports '"
                + status + "'. The claim is not corroborated by the index, "
                "which is incomplete; other evidence is needed. This is not "
                "proof that the API is absent.",
            )

    documented = bool(
        resolution is not None
        and resolution.get("status") in INDEX_CONFIRMED_STATUSES
    )
    entry["documentationMatched"] = documented

    version_ok = _check_evidence_version(entry, index, issue)
    binding_ok = _check_binding(entry, index, language, issue)
    source_ok = _check_evidence_source(entry, index, source_context, issue)
    member_in_file = False
    if source_ok:
        member_in_file = _check_member_is_in_declared_file(
            entry, index, source_context, issue
        )

    entry["fullyMatched"] = bool(
        documented and version_ok and binding_ok and source_ok and member_in_file
    )
    entry["issues"] = issues
    return issues


def check_text(text, language, index=None, mode="ready", source_context=None):
    """Check every evidence comment in *text* and return a report dict.

    ``documentedEntryCount`` counts entries whose member is documented in the
    index *and* whose version, binding and source file agreed with it. It is
    deliberately named after what it counts: entries, not calls. It says
    nothing about how many NXOpen calls the file makes, and nothing about
    whether those calls work.
    """
    if source_context is None and index is not None:
        source_context = SourceContext(index)

    entries = []
    for line, comment_text in comments_for(text, language):
        entry = parse_evidence_comment(line, comment_text)
        if entry is None:
            continue
        check_entry(
            entry,
            index=index,
            mode=mode,
            language=language,
            source_context=source_context,
        )
        entries.append(entry)

    problems = []
    for entry in entries:
        problems.extend(entry["issues"])

    report = {
        "language": language,
        "entryCount": len(entries),
        "documentationMatchedCount": sum(
            1 for entry in entries if entry.get("documentationMatched")
        ),
        "documentedEntryCount": sum(
            1 for entry in entries if entry.get("fullyMatched")
        ),
        # This tool matches comments against documentation. It does not map
        # code calls to evidence, so it cannot report coverage of the calls.
        "callCoverageChecked": False,
        "entries": entries,
        "problems": problems,
        "errorCount": sum(1 for item in problems if item["level"] == "error"),
        "warningCount": sum(1 for item in problems if item["level"] == "warning"),
        "indexUsed": index is not None,
    }
    if index is not None:
        report["index"] = index.summary()
    else:
        report["note"] = (
            "No API index was supplied, so API truth was not checked. Nothing "
            "here confirms that a listed member exists in the target NX 12 "
            "installation."
        )
    return report
