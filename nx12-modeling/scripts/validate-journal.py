#!/usr/bin/env python3
"""Static checks for NX 12 Python and C# journals.

What this script is
-------------------
A review aid with two clearly separated modes:

  scaffold  the journal is still a template. Unreplaced placeholders and
            UNVERIFIED markers are expected and reported as warnings.
  ready     the journal is presented as runnable. Unreplaced placeholders,
            UNVERIFIED markers, and placeholder API evidence become errors.

What this script is not
-----------------------
It is not an NXOpen semantic verifier, not a sandbox, and not a C# compiler.

* Python journals are parsed with ``ast``, so comments and string literals are
  never mistaken for executed code.
* C# journals get a light scan of comment- and string-stripped text. That is
  not compilation and not full syntax validation; combine it with
  ``scripts/validate-nx12-csharp.ps1``, which actually compiles.
* Save, export, and file-operation checks are heuristics that flag code for
  review. They do not model NX behaviour.
* Builder-cleanup and undo-mark checks report only what is statically visible.
  Aliases, helper functions, and complex control flow produce explicit
  "could not determine" notes rather than a pass or a fail.
* API existence is checked only when an index is supplied. Without one, the
  report says API truth was not verified, because a comment claiming
  verification is not evidence.

What this script will not grant
-------------------------------
Loading an index does not mean every call in the file was checked, so this
tool never sets ``api-evidence-checked`` or ``apiTruthChecked`` for a file.
Those states may only be recorded as the conclusion of a separate human or
sufficient verification process. What the tool reports instead is:

  ``indexLoaded``           whether a usable index was loaded at all
  ``evidenceEntryCount``    how many NX12-API evidence comments were parsed
  ``documentedEntryCount``  how many of them matched a documented name with a
                            consistent version, binding and source file

Those are counts of *comments*, not of code calls, and none of them is proof
that the journal runs.

Exit codes
----------
  0  no errors were found
  1  at least one error was found
  2  the arguments or an input file could not be used
"""

from __future__ import print_function

import argparse
import ast
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from journal_evidence import SourceContext  # noqa: E402
from journal_evidence import check_text as check_evidence_text  # noqa: E402
from journal_evidence import strip_csharp_noncode  # noqa: E402

# The interpreter embedded in NX 12 is Python 3.6.1. Syntax and standard
# library checks are made against this, not against the interpreter running
# this script.
TARGET_PYTHON = (3, 6)

LATER_RELEASES = (
    "1847", "1872", "1899", "1926", "1953", "1980", "2007", "2206",
    "2212", "2306", "2312", "2406", "2506",
)

PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
UNVERIFIED_RE = re.compile(r"\bUNVERIFIED\b")
RELEASE_RE = re.compile(r"\bNX[\s_-]*(\d{4})\b", re.IGNORECASE)

# Standard library modules added after the NX 12 interpreter. Importing one is
# a hard failure at runtime, unlike a syntax difference.
POST_TARGET_MODULES = {
    "dataclasses": (3, 7),
    "contextvars": (3, 7),
    "importlib.metadata": (3, 8),
    "importlib_metadata": (3, 8),
    "graphlib": (3, 9),
    "zoneinfo": (3, 9),
    "tomllib": (3, 11),
}

# Calls that act on a part or on files. The receiver is inspected before a
# finding is raised, because lw.Close() on a Listing Window is not a part
# close.
PART_ACTIONS = {
    "Save": "saves the part",
    "SaveAs": "saves the part under a new name",
    "Close": "closes the part",
    "Export": "exports the part",
}
FILE_ACTIONS = {
    "DeleteFile": "deletes a file",
    "remove": "deletes a file",
    "unlink": "deletes a file",
    "rmtree": "deletes a directory tree",
    "Delete": "deletes a file or directory",
}
NX_OBJECT_ACTIONS = {
    "AddToDeleteList": "marks an NX object for deletion",
}

LISTING_WINDOW_KIND = "listing-window"
PART_KIND = "part"
SESSION_KIND = "session"
BUILDER_KIND = "builder"

SCOPE_PYTHON = [
    "Python AST: call graph, assignments, exception handlers, builder lifecycle",
    "Python comments and string literals are excluded from code checks",
    "NX12-API evidence comment structure",
    "Target-interpreter syntax and standard-library availability (Python 3.6)",
]
SCOPE_CSHARP = [
    "C# comment- and string-stripped text: call-shaped patterns, empty catch blocks, entry point",
    "NX12-API evidence comment structure",
]
SCOPE_NEITHER = [
    "API existence and overload selection (only checked when an index is supplied)",
    "Whether every NXOpen call in the file is covered by an evidence comment",
    "Whether the journal actually runs in NX 12",
    "Whether the resulting model or drawing is correct",
]

LIMITATIONS = [
    "Static success does not prove the journal runs, and does not prove any API behaves as expected.",
    "static-checked means only that the checks listed in checkedScope ran without error. It does not mean the NXOpen members named in the file exist, and it does not mean the journal is runnable.",
    "api-evidence-checked is never granted by this tool. Loading an index is not the same as checking the file's calls; record that state only from a separate review or verification process.",
    "Builder ownership is tracked through direct assignments. A builder passed to a helper function cannot be followed, and is reported as undetermined.",
    "Save, close, and delete detection is a heuristic for review, not a sandbox.",
    "The host interpreter that parsed this file is not the interpreter embedded in NX 12; a successful parse here does not prove the target accepts the syntax.",
]


def add(issues, level, code, message, line=None, detail=None):
    issue = {"level": level, "code": code, "message": message}
    if line is not None:
        issue["line"] = line
    if detail:
        issue["detail"] = detail
    issues.append(issue)


# --------------------------------------------------------------- Python facts


def dotted_text(node):
    """Best-effort source-like text for an expression node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_text(node.value)
        return (base + "." + node.attr) if base else node.attr
    if isinstance(node, ast.Call):
        base = dotted_text(node.func)
        return base + "()" if base else None
    if isinstance(node, ast.Subscript):
        base = dotted_text(node.value)
        return base + "[]" if base else None
    return None


def call_parts(node):
    """Return (receiver_text, attribute_name) for a Call node."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return dotted_text(func.value), func.attr
    if isinstance(func, ast.Name):
        return None, func.id
    return None, None


def name_kind_guess(name):
    """Infer a receiver kind from a variable name alone. A hint, not proof."""
    if not name:
        return None
    lowered = name.lower()
    if "listing" in lowered:
        return LISTING_WINDOW_KIND
    if lowered in ("part", "the_part", "work_part", "display_part", "workpart"):
        return PART_KIND
    if lowered in ("session", "the_session", "thesession"):
        return SESSION_KIND
    return None


def expr_kind(node, known):
    """Infer what an expression produces, using earlier assignments as context."""
    if node is None:
        return None
    if isinstance(node, ast.Call):
        _, attr = call_parts(node)
        if attr == "GetSession":
            return SESSION_KIND
        if attr and attr.startswith("Create") and attr.endswith("Builder"):
            return BUILDER_KIND
        if attr and attr.endswith("Builder"):
            return BUILDER_KIND
        return None
    if isinstance(node, ast.Attribute):
        if node.attr == "ListingWindow":
            return LISTING_WINDOW_KIND
        if node.attr in ("Work", "Display", "Root"):
            base = dotted_text(node.value) or ""
            if base.endswith("Parts"):
                return PART_KIND
        base_kind = expr_kind(node.value, known)
        if base_kind in (SESSION_KIND, PART_KIND):
            return base_kind
        return None
    if isinstance(node, ast.Name):
        if node.id in known:
            return known[node.id]
        return name_kind_guess(node.id)
    return None


def infer_kinds(tree):
    """Map variable name -> inferred kind, from assignments only."""
    known = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            kind = expr_kind(node.value, known)
            if kind is None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        kind = name_kind_guess(target.id)
                        if kind:
                            break
            if kind is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        known[target.id] = kind
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                kind = expr_kind(node.value, known) or name_kind_guess(node.target.id)
                if kind is not None:
                    known[node.target.id] = kind
    return known


class PythonFacts(object):
    def __init__(self):
        self.tree = None
        self.syntax_error = None
        self.parsed_by_host = False
        self.kinds = {}
        self.calls = []
        self.builder_vars = set()
        self.committed_vars = set()
        self.destroyed_vars = set()
        self.escaped_vars = set()
        self.undo_mark_calls = []
        self.destroy_in_loop = False
        self.commit_count = 0
        self.destroy_count = 0
        self.handlers = 0
        self.identifiers = set()
        self.string_literals = []
        # Where NXOpen is imported or called, taken from the AST. Comments and
        # string literals never reach these lists, so prose mentioning NXOpen
        # cannot make a file look like it uses the API.
        self.nxopen_imports = []
        self.nxopen_calls = []


def is_nxopen_name(text):
    """Whether a dotted name refers to NXOpen itself or one of its members."""
    if not text:
        return False
    return text == "NXOpen" or text.startswith("NXOpen.")


def describe_nxopen_use(facts):
    """(uses_nxopen, description) for a Python file, from AST facts alone."""
    if facts.nxopen_imports:
        first = facts.nxopen_imports[0]
        return True, "import of '%s' at line %s" % (first["module"], first["line"])
    if facts.nxopen_calls:
        first = facts.nxopen_calls[0]
        return True, "call to '%s' at line %s" % (first["path"], first["line"])
    return False, None


def collect_python_facts(text):
    facts = PythonFacts()
    try:
        facts.tree = ast.parse(text)
    except SyntaxError as exception:
        facts.syntax_error = exception
        return facts
    facts.parsed_by_host = True

    tree = facts.tree
    facts.kinds = infer_kinds(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            facts.identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            facts.identifiers.add(node.attr)
        elif isinstance(node, ast.arg):
            facts.identifiers.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            facts.identifiers.add(node.arg)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
            facts.identifiers.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                facts.identifiers.add(alias.name)
                if is_nxopen_name(alias.name):
                    facts.nxopen_imports.append(
                        {"line": getattr(node, "lineno", None), "module": alias.name}
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            facts.identifiers.add(node.module)
            if is_nxopen_name(node.module):
                facts.nxopen_imports.append(
                    {"line": getattr(node, "lineno", None), "module": node.module}
                )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            facts.string_literals.append((getattr(node, "lineno", None), node.value))
        elif isinstance(node, ast.Try):
            facts.handlers += len(node.handlers)

    # Builder variables come from direct assignments of a builder factory call.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            kind = expr_kind(node.value, facts.kinds)
            if kind == BUILDER_KIND:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        facts.builder_vars.add(target.id)
        elif isinstance(node, (ast.For, ast.While)):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    _, attr = call_parts(inner)
                    if attr == "Destroy":
                        facts.destroy_in_loop = True
                        break

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        receiver, attr = call_parts(node)
        line = getattr(node, "lineno", None)
        facts.calls.append({"line": line, "receiver": receiver, "attr": attr})

        full_path = dotted_text(node.func)
        if is_nxopen_name(full_path):
            facts.nxopen_calls.append({"line": line, "path": full_path})

        if attr == "Commit":
            facts.commit_count += 1
            if receiver and receiver in facts.builder_vars:
                facts.committed_vars.add(receiver)
        elif attr == "Destroy":
            facts.destroy_count += 1
            if receiver:
                facts.destroyed_vars.add(receiver)
        elif attr in ("SetUndoMark", "SetUndoMarkName"):
            facts.undo_mark_calls.append({"line": line, "attr": attr})

        # A builder handed anywhere other than its own lifecycle methods leaves
        # the reach of this analysis, so ownership can no longer be decided
        # statically. This covers both builder.append(builder) and a plain
        # helper call such as register_builders(builders, builder).
        own_lifecycle_method = (
            receiver in facts.builder_vars and attr in ("Commit", "Destroy")
        )
        if not own_lifecycle_method:
            arguments = list(node.args or [])
            arguments.extend(keyword.value for keyword in node.keywords or [])
            for argument in arguments:
                for inner in ast.walk(argument):
                    if isinstance(inner, ast.Name) and inner.id in facts.builder_vars:
                        facts.escaped_vars.add(inner.id)

    return facts


# ---------------------------------------------------------------- C# facts


# Matches a C# method declaration at the start of a line. Used only to guess
# which method an empty catch block sits in, so that a best-effort helper is not
# reported the same way as a handler in the main flow. It is a heuristic:
# local functions and lambdas can make it pick the wrong owner.
CSHARP_METHOD_RE = re.compile(
    r"^[ \t]*(?:(?:public|private|protected|internal|static|virtual|override"
    r"|sealed|async|partial|new|unsafe|extern)\s+)+[\w<>\[\],\.\?]+\s+(\w+)\s*\(",
    re.MULTILINE,
)


def csharp_enclosing_method(code, position):
    """The nearest method declaration before *position*, or None."""
    owner = None
    for match in CSHARP_METHOD_RE.finditer(code):
        if match.start() > position:
            break
        owner = match.group(1)
    return owner


def collect_csharp_facts(text):
    """Light scan of comment- and string-stripped C#. Not compilation."""
    code = strip_csharp_noncode(text)
    facts = {
        "codeOnly": code,
        "callPattern": re.compile(r"\.(\w+)\s*\("),
        "commitCount": len(re.findall(r"\.Commit\s*\(", code)),
        "destroyCount": len(re.findall(r"\.Destroy\s*\(", code)),
        "hasMain": bool(re.search(r"\b(?:static\s+)?(?:int|void)\s+Main\s*\(", code)),
        "hasUndoMark": bool(re.search(r"\.SetUndoMark\s*\(", code)),
        "emptyCatches": [
            (match.start(), code.count("\n", 0, match.start()) + 1)
            for match in re.finditer(
                r"catch\s*(?:\([^)]*\))?\s*\{\s*\}", code, re.DOTALL
            )
        ],
        "identifiers": set(re.findall(r"[A-Za-z_]\w*", code)),
        "strings": re.findall(r'"([^"\n]*)"', text),
    }
    return facts


# --------------------------------------------------------------- readiness


def check_readiness(text, language, issues, mode):
    """Flag things that block a journal from being treated as runnable."""
    strict = mode == "ready"

    for match in PLACEHOLDER_RE.finditer(text):
        add(
            issues,
            "error" if strict else "warning",
            "unreplaced-placeholder",
            "Unreplaced template placeholder {{%s}}. Render the template with "
            "scripts/create-journal-template.ps1 before running it." % match.group(1),
            text.count("\n", 0, match.start()) + 1,
        )

    for match in UNVERIFIED_RE.finditer(text):
        add(
            issues,
            "error" if strict else "warning",
            "unverified-marker",
            "The journal still marks pending logic as UNVERIFIED.",
            text.count("\n", 0, match.start()) + 1,
        )

    # An ordinary explanatory TODO is a note. It only blocks a journal that is
    # being presented as ready when it sits in code that has no implementation
    # at all, which the UNVERIFIED marker above already covers.
    for match in re.finditer(r"\bTODO\b", text):
        add(
            issues,
            "warning",
            "todo-marker",
            "TODO present. Explanatory TODOs are fine; confirm this one does "
            "not stand for unimplemented logic.",
            text.count("\n", 0, match.start()) + 1,
        )


def check_release_markers(text, language, facts, issues):
    """Report later-release markers found in code, not in prose."""
    if language == "python" and facts.parsed_by_host:
        for identifier in sorted(facts.identifiers):
            for match in RELEASE_RE.finditer(identifier):
                add(
                    issues,
                    "error",
                    "later-release-marker",
                    "Identifier references NX %s, which this skill does not "
                    "cover. Verify the API against NX 12." % match.group(1),
                )
        for line, value in facts.string_literals:
            for match in RELEASE_RE.finditer(value):
                add(
                    issues,
                    "warning",
                    "later-release-marker-in-string",
                    "String literal references NX %s. A path or identifier "
                    "naming another release is a review signal."
                    % match.group(1),
                    line,
                )
        return

    if language == "csharp":
        code = facts["codeOnly"]
        for match in re.finditer(r"\bNX[\s_-]*(\d{4})\b", code, re.IGNORECASE):
            add(
                issues,
                "error",
                "later-release-marker",
                "Code references NX %s, which this skill does not cover."
                % match.group(1),
                code.count("\n", 0, match.start()) + 1,
            )


def receiver_kind(facts, receiver):
    """Infer the kind of a call receiver from assignments, then from its name."""
    if not receiver:
        return None
    kind = facts.kinds.get(receiver)
    return kind if kind is not None else name_kind_guess(receiver)


def file_receiver(receiver):
    """Whether a receiver names a filesystem API rather than an NX object."""
    if not receiver:
        return False
    return receiver.split(".")[-1] in ("os", "shutil", "File", "Directory", "Path")


def check_destructive_python(facts, issues, allow_destructive):
    """Report part, file and object-deletion calls. Returns whether the
    journal mutates anything, so the undo-mark check can share this verdict."""
    level = "warning" if allow_destructive else "error"
    mutating = False

    for call in facts.calls:
        receiver, attr = call["receiver"], call["attr"]
        if attr is None:
            continue

        if attr in PART_ACTIONS:
            kind = receiver_kind(facts, receiver)
            if kind == LISTING_WINDOW_KIND:
                # lw.Close() closes the Listing Window, not the part, so it is
                # neither a destructive call nor a mutation.
                continue
            mutating = True
            description = PART_ACTIONS[attr]
            if kind == PART_KIND:
                add(
                    issues,
                    level,
                    "destructive-operation",
                    "Call to %s() %s. This needs explicit user authorization "
                    "and a destination." % (attr, description),
                    call["line"],
                )
            else:
                add(
                    issues,
                    "warning",
                    "possible-destructive-operation",
                    "Call to %s() may %s, but the receiver type could not be "
                    "determined from the code. Confirm the receiver before "
                    "treating this as safe." % (attr, description),
                    call["line"],
                )
        elif attr in NX_OBJECT_ACTIONS:
            mutating = True
            add(
                issues,
                level,
                "destructive-operation",
                "Call to %s() %s." % (attr, NX_OBJECT_ACTIONS[attr]),
                call["line"],
            )
        elif attr in FILE_ACTIONS and file_receiver(receiver):
            mutating = True
            add(
                issues,
                level,
                "destructive-operation",
                "Call to %s.%s() %s." % (receiver, attr, FILE_ACTIONS[attr]),
                call["line"],
            )
        elif attr.startswith("Create") or attr.startswith("Delete"):
            mutating = True

    return mutating


def check_destructive_csharp(facts, issues, allow_destructive):
    """Coarse scan. Boundaries are stated in the report.

    Returns whether a mutating call shape was seen, so the undo-mark check can
    reuse the verdict. Unlike the Python path this cannot resolve receiver
    types, so a Listing Window Close is a possible false positive and is called
    out as such.
    """
    code = facts["codeOnly"]
    level = "warning" if allow_destructive else "error"
    mutating = bool(re.search(r"\.(?:Create|Delete|New)\w*\s*\(", code))
    patterns = (
        (r"\.SaveAs\s*\(", "SaveAs"),
        (r"\.Save\s*\(", "Save"),
        (r"\.Close\s*\(", "Close"),
        (r"\bFile\.Delete\s*\(", "File.Delete"),
        (r"\bDirectory\.Delete\s*\(", "Directory.Delete"),
        (r"AddToDeleteList\s*\(", "AddToDeleteList"),
    )
    for pattern, name in patterns:
        for match in re.finditer(pattern, code):
            receiver = ""
            prefix = code[: match.start()]
            found = re.search(r"([A-Za-z_][\w.]*)\s*$", prefix)
            if found:
                receiver = found.group(1)
            if name == "Close" and "listing" in receiver.lower():
                continue
            mutating = True
            add(
                issues,
                level,
                "destructive-operation",
                "Call to %s(...) may modify or discard the part. This light C# "
                "scan cannot resolve the receiver type, so review it manually."
                % name,
                code.count("\n", 0, match.start()) + 1,
            )

    return mutating


def is_read_only_journal(facts, language, mutating):
    """Decide whether the journal can plausibly be read-only.

    A read-only journal cannot be unsafe for lacking an undo mark, so this
    decision gates that check. The Python verdict reuses the receiver-aware
    result from check_destructive_python so that lw.Close() on a Listing Window
    does not make a read-only journal look like it mutates the part.
    """
    if language == "python":
        if facts.builder_vars or facts.commit_count:
            return False
        return not mutating
    if facts["commitCount"] or facts["destroyCount"]:
        return False
    return not re.search(r"\.(?:Create|Delete|New)\w*\s*\(", facts["codeOnly"])


def check_builder_cleanup(facts, language, issues, mode):
    """Report only what is statically visible, and say so when it is not."""
    strict = mode == "ready"

    if language == "csharp":
        if facts["commitCount"] and not facts["destroyCount"]:
            add(
                issues,
                "error" if strict else "warning",
                "missing-builder-cleanup",
                "Commit(...) is present without any Destroy(...) call. This is "
                "a text scan: it cannot prove a builder leaks, and cannot "
                "prove the cleanup is correct.",
            )
        elif facts["commitCount"]:
            add(
                issues,
                "info",
                "builder-cleanup-present",
                "Commit(...) and Destroy(...) both appear. The scan cannot "
                "match them up, so pairing is unverified.",
            )
        return

    if facts.builder_vars or facts.committed_vars:
        if not facts.destroyed_vars and facts.destroy_count == 0:
            if facts.escaped_vars:
                # The builders were handed to code this module does not show,
                # so their cleanup may well happen elsewhere. Saying so is the
                # honest answer; calling it missing would be a guess.
                add(
                    issues,
                    "info",
                    "builder-cleanup-undetermined",
                    "Builders are created but no Destroy() call appears in this "
                    "module, and at least one builder is passed to another "
                    "function. Cleanup cannot be judged from this module alone.",
                )
            else:
                add(
                    issues,
                    "error" if strict else "warning",
                    "missing-builder-cleanup",
                    "Builders are created but no Destroy() call exists anywhere "
                    "in the module.",
                )

    unpaired = sorted(facts.committed_vars - facts.destroyed_vars)
    for name in unpaired:
        if name in facts.escaped_vars:
            add(
                issues,
                "info",
                "builder-cleanup-undetermined",
                "Builder '%s' is committed and is also passed to another "
                "function, so this analysis cannot tell whether it is "
                "destroyed later. Verify its cleanup by reading that function."
                % name,
            )
        elif facts.destroy_in_loop:
            add(
                issues,
                "info",
                "builder-cleanup-undetermined",
                "Builder '%s' is committed without a direct Destroy() call, but "
                "a Destroy() call exists inside a loop. This analysis cannot "
                "match builders to loop iterations." % name,
            )
        else:
            add(
                issues,
                "error" if strict else "warning",
                "builder-not-destroyed",
                "Builder '%s' is committed but never destroyed. Destroy every "
                "builder the journal creates." % name,
            )

    if facts.committed_vars and facts.destroy_count:
        add(
            issues,
            "info",
            "builder-cleanup-scope",
            "Builder tracking covers direct variable assignments only. "
            "Builders stored in collections or passed to helpers are reported "
            "as undetermined rather than as missing.",
        )


def check_undo_mark(facts, language, issues, mode, read_only):
    strict = mode == "ready"

    if read_only:
        add(
            issues,
            "info",
            "undo-mark-not-required",
            "No mutating call was detected, so this looks like a read-only "
            "journal and an undo mark is not required.",
        )
        return

    if language == "python":
        present = bool(facts.undo_mark_calls)
    else:
        present = facts["hasUndoMark"]

    if not present:
        add(
            issues,
            "error" if strict else "warning",
            "missing-undo-mark",
            "No SetUndoMark call was found, but mutating calls are present. A "
            "visible undo mark is required before the first change.",
        )


def check_python_target_compat(facts, issues, host_version):
    """Check syntax and modules against the NX 12 interpreter, not the host."""
    if not facts.parsed_by_host:
        add(
            issues,
            "error",
            "python-syntax",
            "The file could not be parsed (line %s): %s"
            % (getattr(facts.syntax_error, "lineno", "?"), facts.syntax_error),
        )
        return

    tree = facts.tree
    too_new = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if hasattr(ast, "NamedExpr") and isinstance(node, ast.NamedExpr):
            too_new.append((line, "assignment expression (:=)", (3, 8)))
        if hasattr(ast, "Match") and isinstance(node, ast.Match):
            too_new.append((line, "match statement", (3, 10)))
        if isinstance(node, ast.arguments):
            if getattr(node, "posonlyargs", None):
                too_new.append((line, "positional-only parameters (/)", (3, 8)))
        if isinstance(node, (ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith)):
            too_new.append((line, "async syntax", (3, 5)))

    for line, construct, required in too_new:
        add(
            issues,
            "error" if required > TARGET_PYTHON else "warning",
            "target-python-unsupported",
            "%s requires Python %d.%d, but NX 12 embeds Python %d.%d."
            % (construct, required[0], required[1], TARGET_PYTHON[0], TARGET_PYTHON[1]),
            line,
        )

    # A from __future__ import annotations changes annotation evaluation and
    # only exists from 3.7.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for alias in node.names:
                if alias.name == "annotations":
                    add(
                        issues,
                        "error",
                        "target-python-unsupported",
                        "from __future__ import annotations requires Python "
                        "3.7; NX 12 embeds Python 3.6.",
                        getattr(node, "lineno", None),
                    )

    for node in ast.walk(tree):
        module = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                _check_module(module, node, issues)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            module = node.module
            _check_module(module, node, issues)

    add(
        issues,
        "info",
        "host-vs-target-python",
        "Checked with the host interpreter %d.%d.%d; the target interpreter is "
        "NX 12's embedded Python %d.%d. A successful parse here does not prove "
        "the target accepts this syntax."
        % (
            host_version[0], host_version[1], host_version[2],
            TARGET_PYTHON[0], TARGET_PYTHON[1],
        ),
    )


def _check_module(module, node, issues):
    if not module:
        return
    for name, required in POST_TARGET_MODULES.items():
        if module == name or module.startswith(name + "."):
            add(
                issues,
                "error",
                "target-python-module-missing",
                "Module '%s' requires Python %d.%d, but NX 12 embeds Python "
                "%d.%d." % (name, required[0], required[1], TARGET_PYTHON[0], TARGET_PYTHON[1]),
                getattr(node, "lineno", None),
            )


def check_csharp_structure(facts, issues):
    if not facts["hasMain"]:
        add(
            issues,
            "warning",
            "missing-main",
            "No C# entry point was found. A journal needs a Main method.",
        )
    for position, line in facts["emptyCatches"]:
        owner = csharp_enclosing_method(facts["codeOnly"], position)
        if owner and is_guarded_helper(owner):
            add(
                issues,
                "info",
                "suppressed-exception-in-helper",
                "Exception swallowed inside helper '%s()'. That is expected for "
                "a logging or cleanup helper, whose contract is not to throw. "
                "Confirm the helper really is best-effort." % owner,
                line,
            )
        else:
            add(
                issues,
                "warning",
                "suppressed-exception",
                "An empty catch block was found outside any best-effort helper. "
                "It silently discards the failure.",
                line,
            )


# Functions whose whole contract is to report or clean up without raising.
# Swallowing an exception inside one of these is the documented design for this
# skill, not an oversight, so it is reported as information rather than as a
# warning. The list is a naming heuristic and is described as one.
GUARDED_HELPER_PREFIXES = (
    "log",
    "safe_",
    "cleanup",
    "destroy",
    "undo",
    "close_",
    "write_",
    "print_",
    "report_",
)


def is_guarded_helper(name):
    lowered = (name or "").lower().lstrip("_")
    return any(lowered.startswith(prefix) for prefix in GUARDED_HELPER_PREFIXES)


def iter_handlers(node, owner=None):
    """Yield (ExceptHandler, enclosing_function_name) for a whole module."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for item in iter_handlers(child, child.name):
                yield item
            continue
        if isinstance(child, ast.ExceptHandler):
            yield child, owner
        for item in iter_handlers(child, owner):
            yield item


def check_python_quality(facts, issues, mutating):
    """Structural notes that are worth a look but are not blockers."""
    if mutating and not facts.handlers:
        add(
            issues,
            "warning",
            "no-exception-handling",
            "The journal mutates the part but has no try/except block. A "
            "failure part-way through will not be logged or rolled back.",
        )

    if facts.tree is None:
        return

    for node, owner in iter_handlers(facts.tree):
        if not node.body:
            continue
        if not (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
            continue
        line = getattr(node, "lineno", None)
        if owner and is_guarded_helper(owner):
            add(
                issues,
                "info",
                "suppressed-exception-in-helper",
                "Exception swallowed inside helper '%s()'. That is expected "
                "for a logging or cleanup helper, whose contract is not to "
                "raise. Confirm the helper really is best-effort." % owner,
                line,
            )
        else:
            add(
                issues,
                "warning",
                "suppressed-exception",
                "An except handler only passes, silently discarding the "
                "exception outside any best-effort helper.",
                line,
            )


# ----------------------------------------------------------------- driver


def detect_language(path, requested):
    if requested != "auto":
        return requested
    extension = os.path.splitext(path)[1].lower()
    if extension == ".py":
        return "python"
    if extension == ".cs":
        return "csharp"
    raise ValueError("Cannot infer language from extension: " + extension)


def validate(path, language, options):
    with io.open(path, "r", encoding="utf-8-sig") as handle:
        text = handle.read()

    issues = []
    mode = options["mode"]
    allow_destructive = options["allow_destructive"]

    check_readiness(text, language, issues, mode)

    read_only = False
    if language == "python":
        facts = collect_python_facts(text)
        check_python_target_compat(facts, issues, options["host_version"])
        check_release_markers(text, language, facts, issues)
        if facts.parsed_by_host:
            mutating = check_destructive_python(facts, issues, allow_destructive)
            read_only = is_read_only_journal(facts, language, mutating)
            check_builder_cleanup(facts, language, issues, mode)
            check_undo_mark(facts, language, issues, mode, read_only)
            check_python_quality(facts, issues, mutating)
        # NXOpen use is read from the AST only. Prose mentioning NXOpen, and a
        # file the host could not parse, both leave this false rather than
        # producing a claim that was never checked.
        nxopen_used, nxopen_use_note = describe_nxopen_use(facts)
        scope = list(SCOPE_PYTHON)
        facts_summary = {
            "calls": len(facts.calls),
            "commitCalls": facts.commit_count,
            "destroyCalls": facts.destroy_count,
            "builderVariables": sorted(facts.builder_vars),
            "committedBuilders": sorted(facts.committed_vars),
            "destroyedBuilders": sorted(facts.destroyed_vars),
            "undeterminedBuilders": sorted(facts.escaped_vars),
            "undoMarkCalls": len(facts.undo_mark_calls),
            "readOnly": read_only,
        }
    else:
        facts = collect_csharp_facts(text)
        check_release_markers(text, language, facts, issues)
        mutating = check_destructive_csharp(facts, issues, allow_destructive)
        read_only = is_read_only_journal(facts, language, mutating)
        check_builder_cleanup(facts, language, issues, mode)
        check_undo_mark(facts, language, issues, mode, read_only)
        check_csharp_structure(facts, issues)
        # The C# scan is comment- and string-stripped text, so a mention in
        # prose does not count here either.
        csharp_nxopen = re.search(r"\bNXOpen\b", facts["codeOnly"])
        nxopen_used = csharp_nxopen is not None
        nxopen_use_note = None
        if nxopen_used:
            nxopen_use_note = "an NXOpen reference at line %d" % (
                facts["codeOnly"].count("\n", 0, csharp_nxopen.start()) + 1
            )
        scope = list(SCOPE_CSHARP)
        scope.append(
            "C# is scanned as comment- and string-stripped text. This is NOT "
            "compilation and NOT full syntax validation."
        )
        facts_summary = {
            "commitCalls": facts["commitCount"],
            "destroyCalls": facts["destroyCount"],
            "hasMain": facts["hasMain"],
            "hasUndoMark": facts["hasUndoMark"],
            "readOnly": read_only,
        }

    index = options.get("index")
    evidence = check_evidence_text(
        text,
        language,
        index=index,
        mode=mode,
        source_context=SourceContext(index, nx_root=options.get("nx_root"), journal_path=path),
    )
    for problem in evidence["problems"]:
        add(
            issues,
            problem["level"],
            problem["code"],
            problem["message"],
            problem.get("line"),
        )

    # A file that imports or calls NXOpen but carries no evidence comment has
    # had nothing checked, whatever else this run reports. Saying so is the
    # point: silence here previously read as a pass.
    if mode == "ready" and nxopen_used and evidence["entryCount"] == 0:
        add(
            issues,
            "warning",
            "missing-api-evidence",
            "No API evidence was provided. This file uses NXOpen (%s), but "
            "carries no NX12-API evidence comment, so its NXOpen calls were "
            "NOT checked against anything." % nxopen_use_note,
        )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    infos = sum(1 for issue in issues if issue["level"] == "info")

    # Loading an index is not the same as checking every call in the file.
    # Index loading is reported through indexLoaded; the file-level API state
    # is never granted automatically here.
    index_loaded = index is not None
    api_evidence_state = {
        "indexLoaded": index_loaded,
        "evidenceEntryCount": evidence["entryCount"],
        "documentedEntryCount": evidence["documentedEntryCount"],
        "callCoverageChecked": False,
        "apiEvidenceChecked": False,
        "apiTruthChecked": False,
        "note": (
            "This tool checks explicit NX12-API evidence comments and the "
            "documentation names they cite. It does not prove that every "
            "NXOpen call in this file is covered by an evidence comment, and "
            "it does not prove runtime behaviour. api-evidence-checked and "
            "apiTruthChecked are therefore NOT granted for the file; they may "
            "only be recorded as the conclusion of a separate human or "
            "sufficient verification process."
        ),
    }

    states = {}
    if any(issue["code"] in ("unreplaced-placeholder", "unverified-marker") for issue in issues):
        states["scaffold"] = True
    if errors == 0 and not states.get("scaffold"):
        # static-checked means exactly one thing: the checks this tool actually
        # ran, ran without error. It says nothing about NXOpen existing, and
        # nothing about the journal being runnable.
        states["static-checked"] = True

    return {
        "path": path,
        "language": language,
        "mode": mode,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "issues": issues,
        "facts": facts_summary,
        "evidence": {
            "entryCount": evidence["entryCount"],
            "documentationMatchedCount": evidence["documentationMatchedCount"],
            "documentedEntryCount": evidence["documentedEntryCount"],
            "callCoverageChecked": False,
            "apiTruthChecked": False,
            "apiTruthNote": api_evidence_state["note"],
            "note": evidence.get("note"),
            "index": (index.summary() if index_loaded else None),
        },
        "apiEvidence": api_evidence_state,
        "checkedScope": scope,
        "notChecked": SCOPE_NEITHER,
        "limitations": LIMITATIONS,
        "hostPython": "%d.%d.%d" % options["host_version"],
        "targetPython": "%d.%d" % TARGET_PYTHON,
        "verificationStates": states,
    }


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Python or C# journal files")
    parser.add_argument(
        "--language",
        choices=("auto", "python", "csharp"),
        default="auto",
        help="Journal language; inferred from the extension by default",
    )
    parser.add_argument(
        "--mode",
        choices=("scaffold", "ready"),
        default="scaffold",
        help="scaffold expects placeholders; ready treats them as errors",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Deprecated alias for --mode ready",
    )
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Downgrade save, close, delete and overwrite findings to warnings "
             "after explicit review",
    )
    parser.add_argument(
        "--nx-root",
        help="NX installation root; its XML documentation files become the API index",
    )
    parser.add_argument(
        "--api-index",
        nargs="+",
        metavar="XML",
        help="Explicit NXOpen XML documentation file(s) to use as the API index",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args(argv)


def build_index(args):
    from nxopen_index import NxOpenIndex, find_doc_files

    paths = list(args.api_index or [])
    if args.nx_root:
        paths.extend(find_doc_files(args.nx_root))
    paths = [path for path in paths if os.path.isfile(path)]
    if not paths:
        return None
    return NxOpenIndex.load(paths)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    mode = "ready" if args.strict else args.mode
    index = None
    try:
        index = build_index(args)
    except Exception as exception:
        print(
            "input-error: the API index could not be loaded: %s" % exception,
            file=sys.stderr,
        )
        return 2

    options = {
        "mode": mode,
        "allow_destructive": args.allow_destructive,
        "index": index,
        "nx_root": args.nx_root,
        "host_version": sys.version_info[:3],
    }

    reports = []
    for path in args.paths:
        try:
            language = detect_language(path, args.language)
            reports.append(validate(path, language, options))
        except (OSError, ValueError) as exception:
            reports.append(
                {
                    "path": path,
                    "language": args.language,
                    "mode": mode,
                    "errors": 1,
                    "warnings": 0,
                    "infos": 0,
                    "issues": [
                        {
                            "level": "error",
                            "code": "input-error",
                            "message": str(exception),
                        }
                    ],
                    "checkedScope": [],
                    "notChecked": SCOPE_NEITHER,
                    "limitations": [],
                    "verificationStates": {},
                    "apiEvidence": {
                        "indexLoaded": index is not None,
                        "evidenceEntryCount": 0,
                        "documentedEntryCount": 0,
                        "callCoverageChecked": False,
                        "apiEvidenceChecked": False,
                        "apiTruthChecked": False,
                    },
                }
            )

    total_errors = sum(report["errors"] for report in reports)
    total_warnings = sum(report["warnings"] for report in reports)
    total_entries = sum(
        report.get("evidence", {}).get("entryCount", 0) for report in reports
    )
    total_documented = sum(
        report.get("evidence", {}).get("documentedEntryCount", 0) for report in reports
    )

    document = {
        "schemaVersion": 1,
        "tool": "validate-journal.py",
        "mode": mode,
        # Kept for callers that read it, and always false. See apiIndexNote.
        "apiTruthChecked": False,
        "apiIndexNote": (
            "An API index was supplied; the evidence comments that name a "
            "member were resolved against it. That is all it establishes: this "
            "tool does not prove that every call in the file is covered by "
            "evidence, and it does not prove the journal runs."
            if index is not None
            else "No API index was supplied, so API existence and overloads were "
                 "NOT verified. Comments claiming verification were not treated "
                 "as proof."
        ),
        # New, explicit fields. Read these instead of apiTruthChecked.
        "indexLoaded": index is not None,
        "evidenceEntryCount": total_entries,
        "documentedEntryCount": total_documented,
        "callCoverageChecked": False,
        "hostPython": "%d.%d.%d" % sys.version_info[:3],
        "targetPython": "%d.%d" % TARGET_PYTHON,
        "reports": reports,
        "summary": {
            "fileCount": len(reports),
            "entryCount": total_entries,
            "documentedEntryCount": total_documented,
            "errorCount": total_errors,
            "warningCount": total_warnings,
            "exitCode": 1 if total_errors else 0,
        },
    }

    if args.json:
        print(json.dumps(document, indent=2, ensure_ascii=False, default=str))
    else:
        if index is None:
            print("NOTE: " + document["apiIndexNote"])
        for report in reports:
            print(
                "{0} [{1}] mode={2}: {3} error(s), {4} warning(s), {5} info(s)".format(
                    report["path"],
                    report.get("language", "?"),
                    report["mode"],
                    report["errors"],
                    report["warnings"],
                    report.get("infos", 0),
                )
            )
            for issue in report["issues"]:
                location = ""
                if issue.get("line") is not None:
                    location = " line {0}".format(issue["line"])
                print(
                    "  {0:<7} {1}{2}: {3}".format(
                        issue["level"].upper(),
                        issue["code"],
                        location,
                        issue["message"],
                    )
                )
            for state, value in sorted(report.get("verificationStates", {}).items()):
                if value:
                    print("  state   : " + state)
            for item in report.get("notChecked", []):
                print("  not-checked: " + item)
        print(
            "summary: {0} file(s), {1} error(s), {2} warning(s)".format(
                len(reports), total_errors, total_warnings
            )
        )

    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
