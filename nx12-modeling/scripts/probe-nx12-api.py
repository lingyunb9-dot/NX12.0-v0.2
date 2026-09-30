"""Read-only NX 12 runtime probe: version evidence, Python runtime, API paths.

Run this inside NX so that ``NXOpen`` is importable, either through
Tools > Journal > Play or through ``run_journal.exe``:

    run_journal.exe probe-nx12-api.py

Set NX12_API_TARGETS to a semicolon-separated list of dotted paths to resolve:

    NXOpen.Features.ExtrudeBuilder.Commit;NXOpen.Session.SetUndoMark

What the probe establishes, and what it does not
------------------------------------------------
It reports these separately, because they are not the same claim:

  version          the installation identifies itself as major version 12.
                   A real NX 12 session returns UGII_VERSION="v12" from
                   Session.GetEnvironmentVariableValue, so a leading v/V is
                   accepted; the rest of the string must still be a version.
  name resolution  the dotted path resolved to a real object at runtime
  signature        NOT confirmed. A resolved attribute says nothing about
                   which overload is correct or how it must be called.
  invocation       NOT attempted. The probe never calls a method it is
                   probing, so it cannot modify the work part.
  api truth        NOT established. The result field ``apiTruthChecked`` is
                   retained for consumers and is always false, whatever the
                   probe observes.

Use scripts/check-api-evidence.py with a local NXOpen XML index to check
overloads and declared parameter types. A runtime hit here is necessary but
not sufficient evidence that a call is correct.

Logical status codes
--------------------
These are the probe's own conclusions, and they are reported in the
``exitCode`` field of the JSON record. They keep their meanings:

  0  version confirmed as NX 12 and every requested API target resolved
  1  version confirmed as NX 12, but at least one API target did not resolve
  2  NXOpen could not be imported; the probe must run inside NX
  3  version evidence identifies a release other than NX 12
  4  no reliable version evidence; the environment stays unverified
  5  version evidence conflicts

Host status is a different thing
--------------------------------
The journal entry point returns naturally instead of calling ``sys.exit``,
because the NX 12 journal host reports SystemExit -- even ``sys.exit(0)`` --
as a journal error and exits with 1. A host process exit code therefore says
only whether the host ran the script; it is NOT the probe's logical status.

Consumers must read the complete ``PROBE-RESULT:`` JSON record and use its
``exitCode``. The marker name is ``PROBE-RESULT``. Do not infer a result from
a host exit code, from a truncated copy of the JSON line, or from searching
the text for a word such as "success": a host that exits 0 may still have
reported a logical 2, 3 or 4, and the record may be printed more than once.

This file intentionally uses conservative Python syntax: NX 12 embeds Python
3.6.1.
"""

from __future__ import print_function

import json
import os
import re
import sys

TARGET_MAJOR = 12

EXIT_OK = 0
EXIT_API_FAILURES = 1
EXIT_NO_NXOPEN = 2
EXIT_WRONG_RELEASE = 3
EXIT_UNVERIFIED = 4
EXIT_CONFLICT = 5

# Environment variables that state a version. These are treated as
# authoritative because they name a version rather than merely appearing in a
# path.
VERSION_FIELDS = ("UGII_VERSION",)

# Environment variables that merely locate an installation. A version-looking
# token inside one of these is a hint, never proof.
PATH_FIELDS = ("UGII_BASE_DIR", "UGII_ROOT_DIR")

# Tokens such as NX12, NX2312, or UG 12.0 found inside a path.
_PATH_TOKEN_RE = re.compile(r"(?i)(?:^|[^0-9a-z])(?:nx|ug)[\s_-]*(\d{1,4})")

_DOTTED_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")

# A whole version string: an optional v/V prefix, then a number, then any
# number of dotted numeric components. Matched with fullmatch, so surrounding
# or trailing text ("v12junk", "v12.") is a non-match rather than being
# silently ignored. Available in the Python 3.6 interpreter NX 12 embeds.
_VERSION_TEXT_RE = re.compile(r"[vV]?([0-9]{1,7})(?:\.[0-9]+)*")


def parse_major(text):
    """Return the major version number in *text*, or None.

    The whole string must be a version, optionally written with a leading
    ``v``/``V``: a real NX 12 session returns ``UGII_VERSION=v12`` from
    ``Session.GetEnvironmentVariableValue``, which is a legitimate version
    string and not a parse failure. Surrounding whitespace is ignored.

    A bare integer keeps its whole value, so "120" is major 120 and never 12,
    and "2312" is major 2312. Only a genuinely dotted version such as
    "12.0.2.9" is read as major 12. Anything else -- "NX12", "E:\\UG 12.0",
    "v12junk", "v12.", "vv12", "v 12" -- is not a version string and returns
    None. Trailing or embedded junk is never ignored, and a version-looking
    substring inside a longer string is never a match.
    """
    if text is None:
        return None
    stripped = str(text).strip()
    if not stripped:
        return None
    match = _VERSION_TEXT_RE.fullmatch(stripped)
    if match is None:
        return None
    return int(match.group(1))


def path_version_hints(text):
    """Pull version-looking tokens out of a path. Hints only, never proof."""
    if not text:
        return []
    return sorted(set(int(match.group(1)) for match in _PATH_TOKEN_RE.finditer(str(text))))


def _evidence(name, value, source, kind, authoritative):
    entry = {
        "name": name,
        "value": value,
        "source": source,
        "kind": kind,
        "major": parse_major(value),
        "authoritative": authoritative,
        "pathHints": [],
    }
    if kind == "path-hint":
        entry["pathHints"] = path_version_hints(value)
    return entry


def collect_version_evidence(environ, getter=None):
    """Collect version evidence from the process environment and from NX.

    ``getter`` is an optional callable equivalent to
    ``Session.GetEnvironmentVariableValue``. It is injected so this function
    can be exercised without an NX session.
    """
    evidence = []
    names = list(VERSION_FIELDS) + list(PATH_FIELDS)

    for name in names:
        value = environ.get(name)
        if value:
            evidence.append(
                _evidence(
                    name,
                    value,
                    "process-environment",
                    "version-field" if name in VERSION_FIELDS else "path-hint",
                    name in VERSION_FIELDS,
                )
            )

    if getter is not None:
        for name in names:
            try:
                value = getter(name)
            except Exception:
                continue
            if not value:
                continue
            entry = _evidence(
                name,
                str(value),
                "nx-session",
                "version-field" if name in VERSION_FIELDS else "path-hint",
                name in VERSION_FIELDS,
            )
            if not any(
                item["name"] == entry["name"]
                and item["value"] == entry["value"]
                and item["source"] == entry["source"]
                for item in evidence
            ):
                evidence.append(entry)

    return evidence


def classify_version(evidence):
    """Decide the version state from the authoritative evidence alone.

    Path hints are deliberately excluded: a directory named NX12 must never
    turn an installation that reports a different version into a confirmed
    NX 12.
    """
    authoritative = [
        item for item in evidence
        if item["authoritative"] and item["major"] is not None
    ]
    majors = sorted(set(item["major"] for item in authoritative))

    if not authoritative:
        status = "unverified"
    elif len(majors) > 1:
        status = "conflict"
    elif majors[0] == TARGET_MAJOR:
        status = "confirmed"
    else:
        status = "wrong-release"

    notes = []
    for item in evidence:
        if item["kind"] != "path-hint":
            continue
        for hint in item["pathHints"]:
            if status == "confirmed" and hint != TARGET_MAJOR:
                notes.append(
                    "Path hint '%s' in %s suggests version %d, but authoritative "
                    "evidence confirms major version %d. The path is not proof."
                    % (item["value"], item["name"], hint, TARGET_MAJOR)
                )
            elif status in ("wrong-release", "conflict") and hint == TARGET_MAJOR:
                notes.append(
                    "Path '%s' looks like NX 12, but it does not override the "
                    "authoritative version evidence." % item["value"]
                )

    return {
        "status": status,
        "majors": majors,
        "authoritativeCount": len(authoritative),
        "notes": notes,
    }


def python_runtime_info():
    """Describe the interpreter actually executing this probe.

    This is the NX-embedded interpreter when the probe runs as a journal, and
    it is not necessarily the interpreter that runs the validation scripts.
    """
    executable = getattr(sys, "executable", None)
    if executable is None:
        executable = getattr(sys, "prefix", None)
    return {
        "version": sys.version,
        "versionInfo": list(sys.version_info),
        "executable": executable,
        "platform": sys.platform,
        "maxsize": getattr(sys, "maxsize", None),
        "pointerBits": 64 if (getattr(sys, "maxsize", 0) or 0) > 2 ** 32 else 32,
        "hexversion": getattr(sys, "hexversion", None),
    }


def _describe(obj):
    kind = type(obj).__name__
    if isinstance(obj, type):
        kind = "class"
    elif hasattr(obj, "__module__") and getattr(obj, "__file__", None):
        kind = "module"
    return {
        "typeName": getattr(type(obj), "__name__", None),
        "kind": kind,
        "callable": callable(obj),
    }


def resolve_target(root_module, root_name, dotted, importer=None):
    """Resolve one dotted path without ever calling the object it names.

    Distinguishes the failure modes that a plain getattr chain would collapse
    into one:

      resolved / resolved-after-import
          the path names a real object. ``resolved-after-import`` means the
          submodule had simply not been imported yet, which is not a missing
          API.
      member-missing
          the parent resolved, but the final attribute does not exist.
      not-found
          some part is neither an attribute nor an importable submodule.
      import-error
          a submodule exists but failed to load for a reason other than
          not being found.
    """
    if importer is None:
        import importlib
        importer = importlib.import_module

    result = {
        "target": dotted,
        "status": "unresolved",
        "failureAt": None,
        "importError": None,
        "importsPerformed": [],
        "detail": {},
        "signatureConfirmed": False,
        "invoked": False,
    }

    if not dotted or not _DOTTED_RE.match(dotted):
        result["status"] = "invalid-target"
        result["detail"] = {"note": "Expected a dotted identifier path."}
        return result

    parts = dotted.split(".")
    if parts[0] == root_name:
        parts = parts[1:]
    if not parts:
        result["status"] = "resolved"
        result["detail"] = _describe(root_module)
        return result

    current = root_module
    imports_performed = []
    last_index = len(parts) - 1

    for index, part in enumerate(parts):
        try:
            attribute = getattr(current, part)
        except AttributeError:
            attribute = None
            attribute_error = True
        except Exception as exception:
            result["status"] = "member-missing"
            result["failureAt"] = ".".join(parts[: index + 1])
            result["importError"] = "%s: %s" % (type(exception).__name__, exception)
            return result
        else:
            attribute_error = False

        if not attribute_error:
            current = attribute
            continue

        # Not an attribute. It may be a submodule that has not been imported
        # yet, which is a very different thing from a missing API.
        if index == last_index:
            result["status"] = "member-missing"
            result["failureAt"] = ".".join(parts)
            return result

        module_name = root_name + "." + ".".join(parts[: index + 1])
        try:
            current = importer(module_name)
        except ImportError as exception:
            result["status"] = "not-found"
            result["failureAt"] = module_name
            result["importError"] = "%s: %s" % (type(exception).__name__, exception)
            result["detail"] = {
                "note": "The name is neither an attribute of its parent nor an "
                        "importable NXOpen submodule.",
            }
            return result
        except Exception as exception:
            result["status"] = "import-error"
            result["failureAt"] = module_name
            result["importError"] = "%s: %s" % (type(exception).__name__, exception)
            result["detail"] = {
                "note": "The submodule exists but could not be loaded.",
            }
            return result
        imports_performed.append(module_name)

    result["status"] = "resolved-after-import" if imports_performed else "resolved"
    result["importsPerformed"] = imports_performed
    result["detail"] = _describe(current)
    result["detail"]["note"] = (
        "Name resolution only. Which overload applies, and whether a call "
        "succeeds, are not established by this probe."
    )
    return result


def build_result(version, runtime, targets, nxopen_import_error):
    """Assemble the single result object behind every output form."""
    result = {
        "schemaVersion": 1,
        "probe": "probe-nx12-api.py",
        "targetMajor": TARGET_MAJOR,
        "pythonRuntime": runtime,
        "versionEvidence": version["evidence"],
        "version": {
            "status": version["status"],
            "majors": version["majors"],
            "notes": version["notes"],
        },
        "nxopenImportError": nxopen_import_error,
        "targets": targets,
        # Kept for consumers that read the field, and always false. This probe
        # establishes the environment and name resolution only; it does not
        # verify arguments, overloads, call order or runtime behaviour. No
        # outcome it can observe -- a clean NXOpen import, a confirmed NX 12
        # environment, a non-empty or fully resolved target list, no errors, or
        # exit code 0 -- upgrades that, so this is a conservative
        # compatibility field and never a pass flag.
        "apiTruthChecked": False,
        "exitCode": None,
        "summary": None,
    }

    if nxopen_import_error is not None:
        result["exitCode"] = EXIT_NO_NXOPEN
        result["summary"] = "NXOpen could not be imported."
        return result

    if version["status"] == "conflict":
        result["exitCode"] = EXIT_CONFLICT
        result["summary"] = "Version evidence conflicts; the environment is unverified."
        return result
    if version["status"] == "unverified":
        result["exitCode"] = EXIT_UNVERIFIED
        result["summary"] = "No reliable version evidence; the environment is unverified."
        return result
    if version["status"] == "wrong-release":
        result["exitCode"] = EXIT_WRONG_RELEASE
        result["summary"] = (
            "Version evidence identifies major version(s) %s, not %d."
            % (", ".join(str(m) for m in version["majors"]), TARGET_MAJOR)
        )
        return result

    failures = [item for item in targets if item["status"] != "resolved" and item["status"] != "resolved-after-import"]
    if failures:
        result["exitCode"] = EXIT_API_FAILURES
        result["summary"] = "%d of %d API target(s) did not resolve." % (len(failures), len(targets))
        return result

    result["exitCode"] = EXIT_OK
    if targets:
        result["summary"] = "Version confirmed as NX 12; all %d API target(s) resolved by name." % len(targets)
    else:
        result["summary"] = "Version confirmed as NX 12; no API targets were requested."
    return result


def emit(result, listing_window=None):
    """Print the report and the machine-readable line. Never raises."""
    def write(text):
        try:
            print(text)
        except Exception:
            pass
        if listing_window is not None:
            try:
                listing_window.WriteLine(text)
            except Exception:
                pass

    runtime = result["pythonRuntime"]
    write("NX 12 API probe (read-only)")
    write("Python runtime : %s" % runtime["version"].replace("\n", " "))
    write("Executable     : %s" % runtime["executable"])
    write("Pointer size   : %d-bit" % runtime["pointerBits"])
    write("Target major   : %d" % result["targetMajor"])
    write("")

    if result["versionEvidence"]:
        write("Version evidence:")
        for item in result["versionEvidence"]:
            write(
                "  %-22s = %-24s major=%-6s source=%s%s"
                % (
                    item["name"],
                    item["value"],
                    item["major"],
                    item["source"],
                    "" if item["authoritative"] else " (hint, not authoritative)",
                )
            )
    else:
        write("Version evidence: none found.")

    write("Version state  : %s" % result["version"]["status"])
    for note in result["version"]["notes"]:
        write("  note: %s" % note)

    if result["nxopenImportError"] is not None:
        write("")
        write("ERROR: NXOpen could not be imported: %s" % result["nxopenImportError"])
        write("This probe must run inside NX, where NXOpen is importable.")
    else:
        write("")
        if not result["targets"]:
            write("No API targets requested. Set NX12_API_TARGETS to probe dotted paths.")
        for item in result["targets"]:
            write("  %-52s %s" % (item["target"], item["status"]))
            if item["failureAt"]:
                write("      failed at : %s" % item["failureAt"])
            if item["importError"]:
                write("      error     : %s" % item["importError"])
            if item["importsPerformed"]:
                write("      imported  : %s" % ", ".join(item["importsPerformed"]))
            note = (item.get("detail") or {}).get("note")
            if note:
                write("      note      : %s" % note)

    write("")
    write("API signature/overload confirmation: NOT performed by this probe.")
    write("Actual invocation: NOT attempted; probe results describe name resolution only.")
    write("Summary        : %s" % result["summary"])

    payload = json.dumps(result, sort_keys=True, default=str)
    write("PROBE-RESULT: " + payload)

    return result["exitCode"]


def _open_listing_window(session):
    window = getattr(session, "ListingWindow", None)
    if window is None:
        return None
    try:
        window.Open()
    except Exception:
        return None
    return window


def main(environ=None, importer=None):
    if environ is None:
        environ = os.environ

    runtime = python_runtime_info()
    listing_window = None
    nxopen_import_error = None
    targets = []

    try:
        import NXOpen
    except Exception as exception:
        nxopen_import_error = "%s: %s" % (type(exception).__name__, exception)
        version = {"status": "unverified", "majors": [], "notes": [], "evidence": []}
        result = build_result(version, runtime, targets, nxopen_import_error)
        return emit(result)

    getter = None
    session = None
    try:
        session = NXOpen.Session.GetSession()
    except Exception:
        session = None

    if session is not None:
        listing_window = _open_listing_window(session)
        candidate = getattr(session, "GetEnvironmentVariableValue", None)
        if callable(candidate):
            getter = candidate

    evidence = collect_version_evidence(environ, getter=getter)
    classification = classify_version(evidence)
    version = {
        "status": classification["status"],
        "majors": classification["majors"],
        "notes": classification["notes"],
        "evidence": evidence,
    }

    raw_targets = environ.get("NX12_API_TARGETS", "") if hasattr(environ, "get") else ""
    requested = [item.strip() for item in str(raw_targets).split(";") if item.strip()]
    for dotted in requested:
        targets.append(resolve_target(NXOpen, "NXOpen", dotted, importer=importer))

    if nxopen_import_error is None and listing_window is None and session is None:
        version["notes"] = list(version["notes"]) + [
            "No NX session was available; version evidence came from the process "
            "environment only."
        ]

    result = build_result(version, runtime, targets, nxopen_import_error)
    return emit(result, listing_window=listing_window)


if __name__ == "__main__":
    # Return naturally. The NX 12 journal host treats SystemExit as a journal
    # error: even `sys.exit(0)` is reported under "Syntax errors" and makes the
    # host exit with 1. The probe's logical outcome is therefore recorded in
    # the complete PROBE-RESULT JSON record, not in the host's exit status.
    #
    # This does not soften any check: main() still decides the logical status
    # exactly as before, and an unexpected exception is not caught here, so it
    # still reaches the host as a real failure.
    main()
