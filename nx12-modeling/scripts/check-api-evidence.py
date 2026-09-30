#!/usr/bin/env python3
"""Check the ``NX12-API:`` evidence comments in NX journals.

Reports four separate things:

1. Whether each evidence comment carries the locating information a reviewer
   needs -- member identity, source, version, and binding language.
2. Whether the named member is documented in a local NXOpen index, when one is
   supplied with ``--nx-root`` or ``--api-index``.
3. Whether the declared version agrees with the version of the index that was
   actually loaded, and whether the declared source file exists and is one of
   the files that index was built from.
4. Whether the declared binding can be spoken for by that index. The shipped
   NXOpen XML is .NET documentation; it cannot confirm a Python binding.

What this script cannot do is prove that an API behaves as intended in NX 12,
or that the code's calls are covered by the evidence comments it finds. Only
comments are matched against documentation; calls are never mapped to entries.
``apiTruthChecked`` is therefore always false, and ``callCoverageChecked``
records that no coverage claim is being made. Passing comments are a review
aid, not proof. When no index is supplied the report says so instead of
implying that the members were checked.

Exit codes:
  0  no errors were found
  1  at least one error was found
  2  the arguments or an input file could not be used
"""

from __future__ import print_function

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from journal_evidence import SourceContext, check_text  # noqa: E402
from nxopen_index import NxOpenIndex, find_doc_files  # noqa: E402


def detect_language(path, requested):
    if requested != "auto":
        return requested
    extension = os.path.splitext(path)[1].lower()
    if extension == ".py":
        return "python"
    if extension == ".cs":
        return "csharp"
    raise ValueError("Cannot infer language from extension: " + extension)


def build_index(nx_root, api_index):
    """Build an index from explicit XML files or from an NX installation root."""
    paths = list(api_index or [])
    if nx_root:
        paths.extend(find_doc_files(nx_root))
    if not paths:
        return None, "No API index was found to check against."
    existing = [path for path in paths if os.path.isfile(path)]
    if not existing:
        return None, "None of the supplied index files exist: " + ", ".join(paths)
    return NxOpenIndex.load(existing), None


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
        "--nx-root",
        help="NX installation root; its NXOpen XML documentation files are used as the index",
    )
    parser.add_argument(
        "--api-index",
        nargs="+",
        metavar="XML",
        help="Explicit NXOpen XML documentation file(s) to use as the index",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    index = None
    index_note = None
    if args.nx_root or args.api_index:
        index, index_note = build_index(args.nx_root, args.api_index)

    reports = []
    for path in args.paths:
        try:
            language = detect_language(path, args.language)
            with open(path, "r", encoding="utf-8-sig") as handle:
                text = handle.read()
            report = check_text(
                text,
                language,
                index=index,
                source_context=SourceContext(
                    index, nx_root=args.nx_root, journal_path=path
                ),
            )
            report["path"] = path
            reports.append(report)
        except (OSError, ValueError) as exception:
            reports.append(
                {
                    "path": path,
                    "language": args.language,
                    "entryCount": 0,
                    "documentationMatchedCount": 0,
                    "documentedEntryCount": 0,
                    "callCoverageChecked": False,
                    "entries": [],
                    "problems": [
                        {
                            "level": "error",
                            "code": "input-error",
                            "message": str(exception),
                        }
                    ],
                    "errorCount": 1,
                    "warningCount": 0,
                    "indexUsed": index is not None,
                }
            )

    total_errors = sum(report["errorCount"] for report in reports)
    total_warnings = sum(report["warningCount"] for report in reports)
    total_entries = sum(report["entryCount"] for report in reports)
    total_documented = sum(report["documentedEntryCount"] for report in reports)

    document = {
        "schemaVersion": 1,
        "tool": "check-api-evidence.py",
        # Kept for callers that read this field, and always false: loading an
        # index is not the same as checking the file's calls against it. See
        # apiTruthNote.
        "apiTruthChecked": False,
        "apiTruthNote": (
            "This tool checks the explicit NX12-API evidence comments and the "
            "documentation names they cite. It does not verify that every "
            "NXOpen call in the code is covered by evidence, and it does not "
            "verify runtime behaviour. File-level API truth is therefore NOT "
            "granted; record it only from a separate review or verification "
            "process."
        ),
        # New, explicit fields. Read these instead of apiTruthChecked.
        "indexLoaded": index is not None,
        "evidenceEntryCount": total_entries,
        "documentedEntryCount": total_documented,
        "callCoverageChecked": False,
        "indexNote": index_note,
        "reports": reports,
        "summary": {
            "entryCount": total_entries,
            "documentedEntryCount": total_documented,
            "errorCount": total_errors,
            "warningCount": total_warnings,
            "exitCode": 1 if total_errors else 0,
        },
    }

    if args.json:
        print(json.dumps(document, indent=2, ensure_ascii=False))
    else:
        if index is None:
            print(
                "NOTE: no API index supplied; evidence structure was checked, "
                "but API truth was not."
            )
            if index_note:
                print("      " + index_note)
        for report in reports:
            print(
                "{0}: {1} evidence entr(ies), {2} documented, "
                "{3} error(s), {4} warning(s)".format(
                    report["path"],
                    report["entryCount"],
                    report["documentedEntryCount"],
                    report["errorCount"],
                    report["warningCount"],
                )
            )
            for problem in report["problems"]:
                location = ""
                if "line" in problem:
                    location = " line {0}".format(problem["line"])
                print(
                    "  {0} {1}{2}: {3}".format(
                        problem["level"].upper(),
                        problem["code"],
                        location,
                        problem["message"],
                    )
                )
        print(
            "summary: {0} entr(ies), {1} documented, {2} error(s), {3} warning(s)".format(
                total_entries, total_documented, total_errors, total_warnings
            )
        )
        print(
            "note: documented entries are comments matched against "
            "documentation names. Call coverage and runtime behaviour were NOT "
            "verified, so file-level API truth is not granted."
        )

    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
