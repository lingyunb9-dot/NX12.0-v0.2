#!/usr/bin/env python3
"""Behaviour regression tests for the nx12-modeling skill.

Run from the skill root:

    python tests/test_nx12_skill.py

Only the Python standard library is required. Tests that need PowerShell, a
real NX installation, or a C# compiler skip themselves with a reason when the
dependency is absent, so a partial environment produces a partial run rather
than a false pass.

These tests assert behaviour, not the presence of strings. Where a check can
only be approximate -- the C# scan, the builder-ownership analysis -- the test
asserts the script reports its own uncertainty rather than inventing a result.
"""

from __future__ import print_function

import ast
import contextlib
import importlib.util
import io
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

# Running the suite imports the skill's helper modules, which would leave
# bytecode caches in scripts/. That directory is part of the package, so
# caching is disabled here and for every subprocess started below.
sys.dont_write_bytecode = True

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL_ROOT, "scripts")
TEMPLATES = os.path.join(SKILL_ROOT, "assets", "templates")
REFERENCES = os.path.join(SKILL_ROOT, "references")

VALIDATE = os.path.join(SCRIPTS, "validate-journal.py")
EVIDENCE = os.path.join(SCRIPTS, "check-api-evidence.py")
PROBE = os.path.join(SCRIPTS, "probe-nx12-api.py")
CREATE_TEMPLATE = os.path.join(SCRIPTS, "create-journal-template.ps1")
INSPECT = os.path.join(SCRIPTS, "inspect-nx-installation.ps1")
CSHARP_CHECK = os.path.join(SCRIPTS, "validate-nx12-csharp.ps1")
CSHARP_TEMPLATE = os.path.join(TEMPLATES, "csharp-journal.cs")

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")

# The skill's helper modules are imported directly so the evidence rules can be
# exercised against small sample indexes with a stated version, rather than
# only end to end.
sys.path.insert(0, SCRIPTS)
import journal_evidence  # noqa: E402
import nxopen_index  # noqa: E402


def load_module(path, name):
    """Import a script whose filename is not a valid Python identifier."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OutputDecodingError(Exception):
    """A child process emitted bytes that are not valid UTF-8.

    Raised rather than repaired. Substituting replacement characters would hide
    a real fault in the child, and the run would still report success.
    """


class ProcessResult(object):
    """A finished child process, with stdout and stderr already decoded."""

    def __init__(self, args, returncode, stdout, stderr):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self):
        return "ProcessResult(returncode=%r, args=%r)" % (self.returncode, self.args)


def decode_utf8(raw, stream_name="output", args=None):
    """Decode captured bytes as UTF-8, failing loudly on invalid input.

    This runs on the calling thread against the captured bytes. Decoding is
    never left to a background reader thread and never falls back to the
    system code page, which on a Chinese Windows install is not UTF-8.
    """
    if raw is None:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise OutputDecodingError(
            "The %s of %r is not valid UTF-8 (%s at byte offset %d). The child "
            "process must be configured to write UTF-8; the bytes are not "
            "repaired, ignored or replaced."
            % (stream_name, args, error.reason, error.start)
        )


def run_process(args, **kwargs):
    """Run a child process and decode its output strictly as UTF-8.

    Bytes are captured first -- no text mode, so nothing is decoded by
    subprocess itself -- and decoded here after the process has finished.
    Every child is configured to write UTF-8: Python children through
    PYTHONIOENCODING, PowerShell children through run_powershell().
    """
    # PYTHONDONTWRITEBYTECODE keeps child interpreters from writing __pycache__
    # directories back into the skill tree.
    environment = dict(kwargs.pop("env", os.environ))
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    # This affects the child only. The parent's decoding is fixed by
    # decode_utf8 above and never depends on this variable.
    environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        **kwargs
    )
    return ProcessResult(
        args,
        completed.returncode,
        decode_utf8(completed.stdout, "stdout", args),
        decode_utf8(completed.stderr, "stderr", args),
    )


def run_python(script, *args):
    return run_process([sys.executable, script] + list(args))


PARAMETER_NAME_RE = re.compile(r"^--?[A-Za-z][A-Za-z0-9_-]*$")


def quote_powershell_argument(value):
    """Single-quote one argument *value* for a PowerShell command line.

    Use this for values only. A quoted parameter name is read by PowerShell as
    a string expression, so `'-Language' 'python'` binds "-Language" as a
    positional value and leaves -Language unset. Pass parameter names through
    quote_powershell_token() instead.
    """
    return "'" + str(value).replace("'", "''") + "'"


def quote_powershell_token(value):
    """Render one command-line token: parameter names stay bare, values quoted.

    PowerShell only recognises a parameter name as a bare token, so names must
    not be quoted. A *value* that itself looks like a switch cannot be passed on
    a PowerShell command line at all -- `-Name '-Force'` still binds the -Force
    switch -- so nothing is lost by treating these tokens as names.
    """
    text = str(value)
    if PARAMETER_NAME_RE.match(text):
        return text
    return quote_powershell_argument(text)


def run_powershell(script, *args, **kwargs):
    """Run a PowerShell script with its console output pinned to UTF-8.

    The encoding prelude is passed with -Command rather than -File, because
    -File offers nowhere to set the encoding before the script runs. Only this
    child process is affected: -NoProfile keeps the user's profile out of the
    test, and no environment variable or machine-wide setting is changed.

    The script's own exit code is propagated explicitly. `powershell -Command`
    does not turn an `exit N` inside a called script into its own exit code --
    it reports 1 for that case -- so a test that asserts exit code 3 or 4 would
    otherwise see the right value only by accident.
    """
    command = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        "& " + quote_powershell_argument(script)
    )
    if args:
        command += " " + " ".join(quote_powershell_token(a) for a in args)
    # A script that never sets an exit code leaves $LASTEXITCODE unset; that is
    # a successful run, not a missing result.
    command += (
        "; exit $(if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 0 })"
    )
    return run_process(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        **kwargs
    )


def nx_root():
    """A usable NX installation root, or None."""
    candidate = os.environ.get("UGII_BASE_DIR")
    if candidate and os.path.isfile(
        os.path.join(candidate, "NXBIN", "managed", "NXOpen.xml")
    ):
        return candidate
    return None


def csharp_compiler():
    """A .NET Framework csc.exe, or None.

    This mirrors the search order of validate-nx12-csharp.ps1 closely enough to
    answer one question: is a compiler present at all? The script still does
    its own lookup and its own version checks; nothing here is passed to it.
    """
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if not windir:
        return None
    for flavor in ("Framework64", "Framework"):
        candidate = os.path.join(
            windir, "Microsoft.NET", flavor, "v4.0.30319", "csc.exe"
        )
        if os.path.isfile(candidate):
            return candidate
    return None


# ------------------------------------------------------- evidence test helpers


def write_xml(path, member_ids):
    """Write a minimal NXOpen-style XML documentation sample."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<doc>", "<members>"]
    for member_id in member_ids:
        lines.append('  <member name="%s">' % member_id)
        lines.append("    <summary>sample entry</summary>")
        lines.append("  </member>")
    lines.append("</members>")
    lines.append("</doc>")
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def sample_index(folder, xml_name="NXOpen.xml", member_ids=(), version="12.0.0.27"):
    """A small index whose version is stated by a mock version provider.

    The provider exists because a temporary XML sample has no NXOpen.dll beside
    it. It supplies a version for comparison; it never proves that version
    exists anywhere. Pass version=None to model an unreadable version.
    """
    path = write_xml(os.path.join(folder, xml_name), member_ids)
    provider = None
    if version is not None:
        provider = lambda: version  # noqa: E731 - a tiny literal provider
    return nxopen_index.NxOpenIndex.load([path], version_provider=provider)


def sample_index_multi(folder, files, version="12.0.0.27"):
    """An index built from several temporary XML samples."""
    paths = [
        write_xml(os.path.join(folder, name), member_ids)
        for name, member_ids in files
    ]
    return nxopen_index.NxOpenIndex.load(
        paths, version_provider=(lambda: version)
    )


class TempMixin(object):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="nx12-test-")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self._tmp, name)
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path


# --------------------------------------------------------- output encoding


class TestProcessOutputEncoding(TempMixin, unittest.TestCase):
    """Child output is decoded once, in the parent, strictly as UTF-8.

    On a Chinese Windows install the ANSI code page is not UTF-8, so an
    undecoded child output stream can raise inside a reader thread while
    unittest still reports the test as passing. These tests pin the behaviour
    down from both ends: the children are made to write UTF-8, and the parent
    refuses anything that is not.
    """

    # Written as char codes so the helper script itself stays pure ASCII. A
    # .ps1 file without a BOM is read as ANSI by Windows PowerShell, so a
    # non-ASCII literal in the script would test the wrong thing.
    CHINESE = "中文"

    def test_invalid_utf8_raises_instead_of_being_replaced(self):
        """The required failure case: invalid bytes must not be swallowed."""
        with self.assertRaises(OutputDecodingError):
            decode_utf8(b"prefix \xff\xfe suffix", "stdout", ["fake"])

    def test_invalid_utf8_never_yields_replacement_text(self):
        """A repairing decoder would return U+FFFD here and report success."""
        try:
            decoded = decode_utf8(b"\xff\xfe", "stdout", ["fake"])
        except OutputDecodingError:
            return
        self.fail(
            "invalid UTF-8 was decoded to %r instead of raising" % (decoded,)
        )

    def test_valid_utf8_round_trips(self):
        self.assertEqual(
            decode_utf8(self.CHINESE.encode("utf-8"), "stdout"), self.CHINESE
        )

    def test_a_python_child_writes_utf8(self):
        script = self.write(
            "emit.py",
            "print(chr(0x4E2D) + chr(0x6587))\n",
        )
        result = run_python(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), self.CHINESE)

    def test_a_child_that_writes_invalid_utf8_fails_the_run(self):
        """End to end: the helper must raise, not return empty output."""
        script = self.write(
            "badbytes.py",
            "import sys\nsys.stdout.buffer.write(b'\\xff\\xfe broken')\n"
            "sys.stdout.flush()\n",
        )
        with self.assertRaises(OutputDecodingError):
            run_python(script)

    @unittest.skipUnless(POWERSHELL, "PowerShell is not available")
    def test_a_powershell_child_outputs_utf8(self):
        script = self.write(
            "emit.ps1",
            "Write-Output ([string][char]0x4E2D + [string][char]0x6587)\n",
        )
        result = run_powershell(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), self.CHINESE)

    @unittest.skipUnless(POWERSHELL, "PowerShell is not available")
    def test_a_powershell_child_exit_code_reaches_the_parent(self):
        """The encoding prelude must not swallow the script's exit code."""
        script = self.write("exit7.ps1", "exit 7\n")
        result = run_powershell(script)
        self.assertEqual(result.returncode, 7, result.stderr)


# --------------------------------------------------------------- skill package


class TestSkillPackage(unittest.TestCase):
    def read(self, *parts):
        with io.open(os.path.join(SKILL_ROOT, *parts), "r", encoding="utf-8") as handle:
            return handle.read()

    def test_frontmatter_parses_and_name_matches_directory(self):
        text = self.read("SKILL.md")
        self.assertTrue(text.startswith("---\n"), "frontmatter must open the file")
        end = text.index("\n---", 3)
        frontmatter = text[4:end]

        fields = {}
        for line in frontmatter.splitlines():
            if not line.strip() or line.startswith(" "):
                continue
            key, separator, value = line.partition(":")
            self.assertEqual(separator, ":", "unparsable frontmatter line: " + line)
            fields[key.strip()] = value.strip()

        self.assertIn("name", fields)
        self.assertIn("description", fields)
        self.assertRegex(fields["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertEqual(fields["name"], os.path.basename(SKILL_ROOT))
        self.assertGreater(len(fields["description"]), 80)

        # The description must scope the skill narrowly enough that ordinary
        # NX 12 usage does not trigger it.
        lowered = fields["description"].lower()
        self.assertIn("do not use", lowered)
        for excluded in ("1847", "general"):
            self.assertIn(excluded, lowered)

    def test_referenced_paths_all_exist(self):
        missing = []
        for folder, _, files in os.walk(SKILL_ROOT):
            if os.sep + "tests" in folder:
                continue
            for name in files:
                if not name.endswith(".md"):
                    continue
                path = os.path.join(folder, name)
                with io.open(path, "r", encoding="utf-8") as handle:
                    text = handle.read()
                for target in re.findall(r"\]\(([^)#\s]+)\)", text):
                    if "://" in target:
                        continue
                    resolved = os.path.normpath(
                        os.path.join(os.path.dirname(path), target)
                    )
                    if not os.path.exists(resolved):
                        missing.append((path, target))
                for target in re.findall(
                    r"`((?:scripts|assets|references)/[\w./-]+)`", text
                ):
                    resolved = os.path.join(SKILL_ROOT, target.replace("/", os.sep))
                    if not os.path.exists(resolved):
                        missing.append((path, target))
        self.assertEqual(missing, [], "broken internal references: %s" % missing)

    def test_templates_are_present_and_carry_placeholders(self):
        for name in ("python-journal.py", "csharp-journal.cs"):
            path = os.path.join(TEMPLATES, name)
            self.assertTrue(os.path.isfile(path), "missing template: " + name)
            with io.open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("{{JOURNAL_NAME}}", text)
            self.assertIn("{{DESCRIPTION}}", text)

    def test_every_documented_script_exists(self):
        for script in (VALIDATE, EVIDENCE, PROBE, CREATE_TEMPLATE, INSPECT,
                       CSHARP_CHECK, os.path.join(SCRIPTS, "nxopen_index.py"),
                       os.path.join(SCRIPTS, "journal_evidence.py")):
            self.assertTrue(os.path.isfile(script), "missing script: " + script)

    def test_documented_cli_flags_exist_in_the_python_scripts(self):
        expected = {
            VALIDATE: ("--language", "--mode", "--strict", "--allow-destructive",
                       "--nx-root", "--api-index", "--json"),
            EVIDENCE: ("--language", "--nx-root", "--api-index", "--json"),
        }
        for script, flags in expected.items():
            result = run_python(script, "--help")
            for flag in flags:
                self.assertIn(
                    flag,
                    result.stdout,
                    "%s is documented but %s does not accept it"
                    % (flag, os.path.basename(script)),
                )

    def test_documented_ps1_parameters_exist(self):
        expected = {
            INSPECT: ("NxRoot", "ExtraSearchRoot", "SearchDepth", "Json"),
            CREATE_TEMPLATE: ("Language", "OutputPath", "JournalName",
                              "Description", "TemplatePath", "Force", "Json"),
            CSHARP_CHECK: ("SourceFile", "NxRoot", "OutputDirectory", "Target",
                           "CompilerPath", "SearchDepth", "Json"),
        }
        for script, parameters in expected.items():
            with io.open(script, "r", encoding="utf-8") as handle:
                text = handle.read()
            start = text.index("param(")
            end = text.index("\n)", start)
            block = text[start:end]
            declared = set(re.findall(r"\$(\w+)", block))
            for parameter in parameters:
                self.assertIn(
                    parameter,
                    declared,
                    "%s is documented but %s does not declare it"
                    % (parameter, os.path.basename(script)),
                )

    def test_documented_exit_codes_match_the_scripts(self):
        """Each documented exit code must actually be returned somewhere."""
        scripts = {
            INSPECT: (2, 3, 4, 5),
            CREATE_TEMPLATE: (2, 3, 4),
            CSHARP_CHECK: (2, 3, 4, 5),
        }
        for script, codes in scripts.items():
            with io.open(script, "r", encoding="utf-8") as handle:
                text = handle.read()
            for code in codes:
                # A code counts as returned whether it is passed straight to
                # exit, handed to the failure helper, or assigned to the
                # exit-code variable that is passed to exit at the end.
                self.assertTrue(
                    any(
                        re.search(pattern % code, text)
                        for pattern in (
                            r"\bexit\s+%d\b",
                            r"-Code\s+%d\b",
                            r"\$exitCode\s*=\s*%d\b",
                        )
                    ),
                    "%s documents exit code %d but never returns it"
                    % (os.path.basename(script), code),
                )


# ------------------------------------------------------------ version handling


class TestVersionHandling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = load_module(PROBE, "probe_under_test")

    def classify(self, environ, getter=None):
        evidence = self.probe.collect_version_evidence(environ, getter=getter)
        return self.probe.classify_version(evidence)

    def test_dotted_nx12_version_confirms(self):
        self.assertEqual(self.classify({"UGII_VERSION": "12.0.2.9"})["status"], "confirmed")

    def test_bare_120_is_not_version_12(self):
        result = self.classify({"UGII_VERSION": "120"})
        self.assertEqual(result["status"], "wrong-release")
        self.assertEqual(result["majors"], [120])

    def test_nx2312_is_not_overridden_by_an_nx12_path(self):
        result = self.classify(
            {
                "UGII_VERSION": "2312",
                "UGII_BASE_DIR": r"E:\NX12-tools\NX2312",
            }
        )
        self.assertEqual(result["status"], "wrong-release")
        self.assertEqual(result["majors"], [2312])
        self.assertTrue(
            any("does not override" in note for note in result["notes"]),
            "the report must say the path did not override the version",
        )

    def test_path_evidence_alone_stays_unverified(self):
        result = self.classify({"UGII_BASE_DIR": r"E:\NX12-tools\NX 12.0"})
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["majors"], [])

    def test_conflicting_evidence_stays_unverified(self):
        result = self.classify(
            {"UGII_VERSION": "12.0.2.9"},
            getter=lambda name: "2312" if name == "UGII_VERSION" else None,
        )
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["majors"], [12, 2312])

    def test_probe_reports_python_runtime(self):
        info = self.probe.python_runtime_info()
        self.assertIn("version", info)
        self.assertIn("versionInfo", info)
        self.assertGreaterEqual(len(info["versionInfo"]), 3)
        self.assertIn(info["pointerBits"], (32, 64))

    def test_no_version_evidence_means_unverified(self):
        self.assertEqual(self.classify({})["status"], "unverified")

    # A real NX 12 session returns UGII_VERSION="v12" from
    # Session.GetEnvironmentVariableValue, so the v-prefixed spellings below are
    # legitimate version strings rather than parse failures.
    def test_a_v_prefixed_nx12_version_confirms(self):
        for value in ("v12", "V12", "v12.0.0.27"):
            with self.subTest(value=value):
                result = self.classify({"UGII_VERSION": value})
                self.assertEqual(result["status"], "confirmed")
                self.assertEqual(result["majors"], [12])

    def test_a_v_prefixed_bare_number_is_not_version_12(self):
        for value, major in (("v120", 120), ("v2312", 2312)):
            with self.subTest(value=value):
                result = self.classify({"UGII_VERSION": value})
                self.assertEqual(result["status"], "wrong-release")
                self.assertEqual(result["majors"], [major])

    def test_a_v_prefixed_version_conflict_is_still_a_conflict(self):
        result = self.classify(
            {"UGII_VERSION": "v12"},
            getter=lambda name: "v2312" if name == "UGII_VERSION" else None,
        )
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["majors"], [12, 2312])

    def test_a_v_prefixed_wrong_release_is_not_rescued_by_an_nx12_path(self):
        result = self.classify(
            {"UGII_VERSION": "v2312", "UGII_BASE_DIR": r"E:\NX12-tools\NX 12.0"}
        )
        self.assertEqual(result["status"], "wrong-release")
        self.assertEqual(result["majors"], [2312])
        self.assertTrue(
            any("does not override" in note for note in result["notes"]),
            "the report must say the path did not override the version",
        )


class TestProbeVersionStrings(unittest.TestCase):
    """parse_major accepts every documented real-world spelling, and nothing else.

    The positive cases come from what a real NX 12 session reports
    (``UGII_VERSION=v12``) plus the dotted forms already in use; the negative
    cases are strings that merely contain a version-looking number. A version
    found *inside* a longer string must never confirm a release.
    """

    MAJOR_CASES = (
        ("v12", 12),
        ("V12", 12),
        (" v12 ", 12),
        ("12", 12),
        ("12.0.0.27", 12),
        ("v12.0.0.27", 12),
        ("120", 120),
        ("v120", 120),
        ("2312", 2312),
        ("v2312", 2312),
        (None, None),
        ("", None),
        ("NX12", None),
        (r"E:\UG 12.0", None),
        ("v12junk", None),
        ("12.0junk", None),
        ("v12.", None),
        ("v12..0", None),
        ("vv12", None),
        ("v 12", None),
    )

    @classmethod
    def setUpClass(cls):
        cls.probe = load_module(PROBE, "probe_under_test")

    def test_every_documented_input_parses_as_specified(self):
        for text, expected in self.MAJOR_CASES:
            with self.subTest(text=text):
                actual = self.probe.parse_major(text)
                self.assertEqual(actual, expected, "parse_major(%r)" % (text,))
                if expected is None:
                    self.assertIsNone(actual)
                else:
                    self.assertIsInstance(actual, int)

    def test_the_result_is_the_first_component_never_a_substring_search(self):
        """A version-looking number inside a longer string is not a version."""
        self.assertIsNone(self.probe.parse_major("build v12 of NX"))
        self.assertIsNone(self.probe.parse_major("12 and 2312"))
        # ...while the same text as a whole string is still parsed.
        self.assertEqual(self.probe.parse_major("v12"), 12)


class TestProbeJournalEntry(unittest.TestCase):
    """The NX journal entry point returns naturally instead of calling sys.exit.

    A real run_journal.exe host reports SystemExit -- even ``sys.exit(0)`` --
    under "Syntax errors" and exits with 1, so the entry must not raise it. The
    file is executed as ``__main__`` with runpy against a controlled NXOpen
    import, and the logical status is read from the captured PROBE-RESULT
    record. No NX session is started and nothing is written to the skill tree.
    """

    TARGET = "NXOpen.Session.MarkVisibility.Visible"

    def run_entry(self, environ, nxopen):
        """Run the probe as __main__; return (stdout, SystemExit or None)."""
        stream = io.StringIO()
        with mock.patch.dict(sys.modules, {"NXOpen": nxopen}):
            with mock.patch.dict(os.environ, environ, clear=False):
                try:
                    with contextlib.redirect_stdout(stream):
                        runpy.run_path(PROBE, run_name="__main__")
                except SystemExit as signal:
                    return stream.getvalue(), signal
        return stream.getvalue(), None

    def assert_no_systemexit(self, signal):
        if signal is not None:
            self.fail(
                "the entry point raised SystemExit(%r); the NX journal host "
                "treats that as a journal error" % (signal.code,)
            )

    def assert_no_systemexit_or_failure(self, *args, **kwargs):
        stdout, signal = self.run_entry(*args, **kwargs)
        self.assert_no_systemexit(signal)
        return stdout

    def result_record(self, stdout):
        """The first complete PROBE-RESULT record. Truncated copies are skipped."""
        for line in stdout.splitlines():
            if not line.startswith("PROBE-RESULT: "):
                continue
            try:
                return json.loads(line[len("PROBE-RESULT: "):])
            except ValueError:
                continue
        self.fail("no complete PROBE-RESULT record was printed")

    @staticmethod
    def fake_nxopen():
        """A stand-in module: names resolve, and no real NX session is reached."""
        module = types.ModuleType("NXOpen")

        class Session(object):
            MarkVisibility = types.SimpleNamespace(Visible=1)

            @staticmethod
            def GetSession():
                return types.SimpleNamespace()

        module.Session = Session
        return module

    def test_a_confirmed_environment_returns_without_systemexit(self):
        stdout = self.assert_no_systemexit_or_failure(
            {
                "UGII_VERSION": "v12",
                "NX12_API_TARGETS": self.TARGET,
            },
            self.fake_nxopen(),
        )
        record = self.result_record(stdout)

        self.assertEqual(record["version"]["status"], "confirmed")
        self.assertEqual(record["version"]["majors"], [12])
        self.assertEqual(
            [item["status"] for item in record["targets"]], ["resolved"]
        )
        self.assertIs(record["exitCode"], 0)
        self.assertIs(record["apiTruthChecked"], False)

    def test_a_missing_nxopen_returns_without_systemexit(self):
        # sys.modules["NXOpen"] = None makes the import fail deterministically,
        # the same way it does outside NX.
        stdout = self.assert_no_systemexit_or_failure(
            {"NX12_API_TARGETS": ""}, None
        )
        record = self.result_record(stdout)

        self.assertIs(record["exitCode"], 2)
        self.assertIsNotNone(record["nxopenImportError"])
        self.assertIs(record["apiTruthChecked"], False)

    def test_a_wrong_release_returns_without_systemexit(self):
        stdout = self.assert_no_systemexit_or_failure(
            {"UGII_VERSION": "v2312", "NX12_API_TARGETS": ""},
            self.fake_nxopen(),
        )
        record = self.result_record(stdout)

        self.assertEqual(record["version"]["status"], "wrong-release")
        self.assertEqual(record["version"]["majors"], [2312])
        self.assertIs(record["exitCode"], 3)
        self.assertIs(record["apiTruthChecked"], False)

    def test_an_unexpected_exception_is_not_swallowed(self):
        """A real fault must reach the host, not be turned into a clean return."""
        with mock.patch.dict(
            sys.modules, {"NXOpen": self.fake_nxopen()}
        ), mock.patch.dict(
            os.environ, {"NX12_API_TARGETS": ""}, clear=False
        ), mock.patch.object(
            json,
            "dumps",
            side_effect=RuntimeError("unexpected probe failure"),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    runpy.run_path(PROBE, run_name="__main__")


class TestApiResolution(unittest.TestCase):
    """Resolution behaviour is exercised against a simulated NXOpen package.

    No real NX session is involved, and nothing here claims otherwise.
    """

    @classmethod
    def setUpClass(cls):
        cls.probe = load_module(PROBE, "probe_under_test")

    def setUp(self):
        self.imported = []

        nxopen = types.ModuleType("NXOpen")
        session = types.SimpleNamespace()
        session.MarkVisibility = types.SimpleNamespace(Visible=1)
        nxopen.Session = session
        self.nxopen = nxopen

        features = types.ModuleType("NXOpen.Features")

        class ExtrudeBuilder(object):
            def Commit(self):
                raise AssertionError("the probe must never call the API")

        features.ExtrudeBuilder = ExtrudeBuilder
        self.features = features

    def importer(self, name):
        self.imported.append(name)
        if name == "NXOpen.Features":
            return self.features
        raise ImportError("No module named %s" % name)

    def resolve(self, target):
        return self.probe.resolve_target(
            self.nxopen, "NXOpen", target, importer=self.importer
        )

    def test_attribute_chain_resolves_without_import(self):
        result = self.resolve("NXOpen.Session.MarkVisibility.Visible")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(self.imported, [])

    def test_unimported_submodule_is_not_reported_missing(self):
        result = self.resolve("NXOpen.Features.ExtrudeBuilder.Commit")
        self.assertEqual(result["status"], "resolved-after-import")
        self.assertIn("NXOpen.Features", result["importsPerformed"])

    def test_missing_leaf_is_reported_as_member_missing(self):
        result = self.resolve("NXOpen.Session.NonexistentMember")
        self.assertEqual(result["status"], "member-missing")

    def test_unknown_type_is_distinguished_from_import_failure(self):
        result = self.resolve("NXOpen.NonexistentClass.NonexistentMethod")
        self.assertEqual(result["status"], "not-found")

    def test_broken_submodule_is_reported_as_import_error(self):
        def broken(name):
            raise OSError("load failed")

        result = self.probe.resolve_target(
            self.nxopen, "NXOpen", "NXOpen.Features.ExtrudeBuilder", importer=broken
        )
        self.assertEqual(result["status"], "import-error")
        self.assertIn("OSError", result["importError"])

    def test_resolution_never_claims_signature_confirmation(self):
        result = self.resolve("NXOpen.Session.MarkVisibility.Visible")
        self.assertFalse(result["signatureConfirmed"])
        self.assertFalse(result["invoked"])

    def test_invalid_target_is_rejected(self):
        self.assertEqual(self.resolve("not a dotted path")["status"], "invalid-target")


class TestProbeResultState(unittest.TestCase):
    """The probe's result object never claims API truth.

    ``apiTruthChecked`` used to be ``nxopen_import_error is None``, so it read
    as true whenever NXOpen imported -- including when no version had been
    established and no target had been requested. The field now stays false for
    every outcome the probe can observe.

    These call ``build_result`` (and ``emit`` for the JSON form) directly, so
    no NX session, no journal, and no work part is involved. Version states are
    produced by the probe's own ``collect_version_evidence`` and
    ``classify_version``; target results by its own ``resolve_target`` against
    a simulated NXOpen module. No status string or field name is invented here.
    """

    @classmethod
    def setUpClass(cls):
        cls.probe = load_module(PROBE, "probe_under_test")

    def setUp(self):
        # A stand-in for the NXOpen module object: enough for a name to resolve,
        # and deliberately without GetSession, so nothing can reach a session.
        nxopen = types.ModuleType("NXOpen")
        session = types.SimpleNamespace()
        session.MarkVisibility = types.SimpleNamespace(Visible=1)
        nxopen.Session = session
        self.nxopen = nxopen

    def version_state(self, environ):
        """The version structure main() builds, from the probe's own logic."""
        evidence = self.probe.collect_version_evidence(environ)
        classification = self.probe.classify_version(evidence)
        return {
            "status": classification["status"],
            "majors": classification["majors"],
            "notes": classification["notes"],
            "evidence": evidence,
        }

    def resolve(self, target):
        def importer(name):
            raise ImportError("No module named %s" % name)

        return self.probe.resolve_target(
            self.nxopen, "NXOpen", target, importer=importer
        )

    def assert_conservative(self, result):
        """The field must be the boolean False -- not None, not 0, not absent.

        assertIs is deliberate: it distinguishes False from 0, from None, and
        from a missing key, none of which a truthiness check would catch.
        """
        self.assertIn("apiTruthChecked", result, "the field must stay in the result")
        self.assertIs(
            result["apiTruthChecked"],
            False,
            "apiTruthChecked must be exactly False, got %r"
            % (result["apiTruthChecked"],),
        )

    def test_an_unverified_environment_does_not_claim_api_truth(self):
        """Scenario 1: no version evidence, no targets, NXOpen imported."""
        runtime = self.probe.python_runtime_info()
        result = self.probe.build_result(
            self.version_state({}), runtime, [], None
        )

        self.assertEqual(result["version"]["status"], "unverified")
        self.assertEqual(result["version"]["majors"], [])
        self.assert_conservative(result)
        self.assertEqual(result["exitCode"], 4)

    def test_a_non_nx12_environment_does_not_claim_api_truth(self):
        """Scenario 2: the version names another release, no targets."""
        runtime = self.probe.python_runtime_info()
        result = self.probe.build_result(
            self.version_state({"UGII_VERSION": "2312"}), runtime, [], None
        )

        self.assertEqual(result["version"]["status"], "wrong-release")
        self.assertEqual(result["version"]["majors"], [2312])
        self.assert_conservative(result)
        self.assertEqual(result["exitCode"], 3)

    def test_an_nxopen_import_failure_does_not_claim_api_truth(self):
        """Scenario 3: the import failed; the error report is unchanged."""
        runtime = self.probe.python_runtime_info()
        error = "ModuleNotFoundError: No module named 'NXOpen'"
        # The same shape main() builds on the import-failure path.
        version = {"status": "unverified", "majors": [], "notes": [], "evidence": []}
        result = self.probe.build_result(version, runtime, [], error)

        self.assert_conservative(result)
        self.assertEqual(result["exitCode"], 2)
        self.assertEqual(result["nxopenImportError"], error)
        self.assertEqual(result["summary"], "NXOpen could not be imported.")

    def test_successful_name_resolution_does_not_claim_api_truth(self):
        """Scenario 4: NX 12 confirmed and every target resolved.

        This is the strongest case the probe can reach, and it still reports
        apiTruthChecked as false: name resolution is not argument, overload,
        call-order or runtime verification.
        """
        runtime = self.probe.python_runtime_info()
        targets = [self.resolve("NXOpen.Session.MarkVisibility.Visible")]
        version = self.version_state({"UGII_VERSION": "12.0.2.9"})

        result = self.probe.build_result(version, runtime, targets, None)

        self.assertEqual(result["version"]["status"], "confirmed")
        self.assertEqual(result["version"]["majors"], [12])
        self.assertEqual([item["status"] for item in targets], ["resolved"])
        self.assert_conservative(result)
        self.assertEqual(result["exitCode"], 0)
        self.assertEqual(result["targets"], targets)
        self.assertFalse(result["targets"][0]["signatureConfirmed"])
        self.assertFalse(result["targets"][0]["invoked"])
        self.assertIn("resolved by name", result["summary"])

        # The field survives into the machine-readable output consumers read.
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            return_code = self.probe.emit(result)
        self.assertEqual(return_code, 0)
        line = [
            text for text in captured.getvalue().splitlines()
            if text.startswith("PROBE-RESULT: ")
        ]
        self.assertEqual(len(line), 1, captured.getvalue())
        emitted = json.loads(line[0][len("PROBE-RESULT: "):])
        self.assertIs(emitted["apiTruthChecked"], False)
        self.assertEqual(emitted["exitCode"], 0)

    def test_a_failed_target_does_not_claim_api_truth(self):
        """Scenario 5: NX 12 confirmed, one target does not resolve."""
        runtime = self.probe.python_runtime_info()
        targets = [self.resolve("NXOpen.Session.NonexistentMember")]
        version = self.version_state({"UGII_VERSION": "12.0.2.9"})

        result = self.probe.build_result(version, runtime, targets, None)

        self.assertEqual(result["version"]["status"], "confirmed")
        self.assertEqual(targets[0]["status"], "member-missing")
        # failureAt is the path below the root module, as resolve_target builds it.
        self.assertEqual(targets[0]["failureAt"], "Session.NonexistentMember")
        self.assert_conservative(result)
        self.assertEqual(result["exitCode"], 1)
        self.assertEqual(result["targets"], targets)
        self.assertIn("did not resolve", result["summary"])


# ------------------------------------------------------------------ validator


class TestValidator(TempMixin, unittest.TestCase):
    def validate(self, text, name="journal.py", *extra):
        path = self.write(name, text)
        result = run_python(VALIDATE, path, *extra)
        return result, path

    def test_scaffold_passes_and_ready_rejects_it(self):
        scaffold = 'JOURNAL_NAME = "{{JOURNAL_NAME}}"\n# UNVERIFIED\n'
        result, _ = self.validate(scaffold, "scaffold.py", "--mode", "scaffold")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("scaffold", result.stdout)

        result, _ = self.validate(scaffold, "scaffold2.py", "--mode", "ready")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unreplaced-placeholder", result.stdout)
        self.assertIn("unverified-marker", result.stdout)

    def test_forged_evidence_and_unverified_call_are_rejected(self):
        forged = (
            "# NX12-API: TODO\n"
            "# UNVERIFIED\n"
            "import NXOpen\n"
            "NXOpen.NonexistentClass.NonexistentMethod()\n"
            "# SetUndoMark\n"
        )
        result, _ = self.validate(forged, "forged.py", "--mode", "ready")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("unverified-marker", result.stdout)
        self.assertIn("evidence-empty-member", result.stdout)
        self.assertIn("evidence-missing-field", result.stdout)

    def test_undo_mark_mentioned_only_in_a_comment_does_not_count(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    session = NXOpen.Session.GetSession()\n"
            "    # SetUndoMark is not actually called here\n"
            "    session.Parts.Work.Save()\n"
        )
        result, _ = self.validate(source, "comment_only.py", "--mode", "ready")
        self.assertIn("missing-undo-mark", result.stdout)

    def test_comments_and_strings_are_not_treated_as_calls(self):
        source = (
            '"""Do not call part.Save() or part.Close()."""\n'
            "import NXOpen\n"
            "def f():\n"
            "    # part.Save() is forbidden here\n"
            '    note = "call part.Close() only with authorization"\n'
            "    return note\n"
        )
        result, _ = self.validate(source, "prose.py", "--mode", "ready")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("destructive-operation", result.stdout)
        self.assertIn("read-only", result.stdout)

    def test_listing_window_close_is_not_a_part_close(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    session = NXOpen.Session.GetSession()\n"
            "    lw = session.ListingWindow\n"
            "    lw.Open()\n"
            "    lw.Close()\n"
        )
        result, _ = self.validate(source, "lw.py", "--mode", "ready")
        self.assertNotIn("destructive-operation", result.stdout)
        self.assertIn("undo-mark-not-required", result.stdout)

    def test_unknown_receiver_is_flagged_for_review_not_asserted(self):
        source = (
            "import NXOpen\n"
            "def f(thing):\n"
            "    thing.Close()\n"
        )
        result, _ = self.validate(source, "unknown.py", "--mode", "ready")
        self.assertIn("possible-destructive-operation", result.stdout)
        self.assertIn("could not be determined", result.stdout)

    def test_two_builders_one_never_destroyed_is_reported(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    session = NXOpen.Session.GetSession()\n"
            "    work_part = session.Parts.Work\n"
            "    mark = session.SetUndoMark(NXOpen.Session.MarkVisibility.Visible, 'x')\n"
            "    first = work_part.Features.CreateExtrudeBuilder(None)\n"
            "    second = work_part.Features.CreateBlockFeatureBuilder(None)\n"
            "    first.Commit()\n"
            "    second.Commit()\n"
            "    first.Destroy()\n"
        )
        result, _ = self.validate(source, "builders.py", "--mode", "ready")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("builder-not-destroyed", result.stdout)
        self.assertIn("'second'", result.stdout)

    def test_unanalysable_builder_cleanup_is_reported_as_undetermined(self):
        source = (
            "import NXOpen\n"
            "def collect(builders, data):\n"
            "    builders.append(data['builder'])\n"
            "def f():\n"
            "    session = NXOpen.Session.GetSession()\n"
            "    work_part = session.Parts.Work\n"
            "    session.SetUndoMark(NXOpen.Session.MarkVisibility.Visible, 'x')\n"
            "    builders = []\n"
            "    builder = work_part.Features.CreateExtrudeBuilder(None)\n"
            "    collect(builders, {'builder': builder})\n"
            "    builder.Commit()\n"
        )
        result, _ = self.validate(source, "undetermined.py", "--mode", "ready")
        self.assertIn("undetermined", result.stdout)
        self.assertNotIn("builder-not-destroyed", result.stdout)

    def test_read_only_journal_needs_no_undo_mark(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    session = NXOpen.Session.GetSession()\n"
            "    lw = session.ListingWindow\n"
            "    lw.Open()\n"
            "    lw.WriteLine('reading only')\n"
        )
        result, _ = self.validate(source, "readonly.py", "--mode", "ready")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("undo-mark-not-required", result.stdout)

    def test_target_python_construct_is_checked_against_36(self):
        source = "import NXOpen\nvalues = [x for x in range(3)]\nif (n := len(values)) > 1:\n    pass\n"
        result, _ = self.validate(source, "walrus.py", "--mode", "scaffold")
        self.assertIn("target-python-unsupported", result.stdout)
        self.assertIn("3.6", result.stdout)

    def test_post_36_module_is_rejected(self):
        source = "import dataclasses\nimport NXOpen\n"
        result, _ = self.validate(source, "modules.py", "--mode", "scaffold")
        self.assertIn("target-python-module-missing", result.stdout)

    def test_host_and_target_python_are_both_reported(self):
        result, _ = self.validate("x = 1\n", "plain.py", "--json")
        document = json.loads(result.stdout)
        self.assertEqual(document["targetPython"], "3.6")
        self.assertNotEqual(document["hostPython"], "3.6")
        self.assertTrue(document["reports"][0]["limitations"])

    def test_json_output_is_parseable_and_matches_exit_code(self):
        path = self.write("bad.py", "# UNVERIFIED\n")
        result = run_python(VALIDATE, path, "--mode", "ready", "--json")
        self.assertEqual(result.returncode, 1)
        document = json.loads(result.stdout)
        self.assertEqual(document["summary"]["exitCode"], 1)
        self.assertGreaterEqual(document["summary"]["errorCount"], 1)

    def test_api_truth_is_declared_unchecked_without_an_index(self):
        result, _ = self.validate("x = 1\n", "noindex.py", "--json")
        document = json.loads(result.stdout)
        self.assertFalse(document["apiTruthChecked"])
        self.assertIn("NOT verified", document["apiIndexNote"])

    def assert_no_file_level_api_state(self, document):
        """No automatic grant of api-evidence-checked / apiTruthChecked.

        Loading an index is not the same as checking the file's calls, so the
        file-level states must stay ungranted however the run went.
        """
        report = document["reports"][0]
        self.assertNotIn(
            "api-evidence-checked",
            report["verificationStates"],
            "api-evidence-checked must not be granted by this tool",
        )
        self.assertFalse(report["evidence"]["apiTruthChecked"])
        self.assertFalse(report["apiEvidence"]["apiEvidenceChecked"])
        self.assertFalse(report["apiEvidence"]["callCoverageChecked"])
        self.assertFalse(document["apiTruthChecked"])
        self.assertFalse(document["callCoverageChecked"])
        self.assertEqual(report["evidence"]["documentedEntryCount"], 0)

    def test_nxopen_calls_without_evidence_do_not_get_api_evidence_state(self):
        """The confirmed defect, without an index.

        A file that calls NXOpen and carries no evidence comment used to be
        reported as api-evidence-checked as soon as an index was loaded. With
        no index it was silent instead, which reads the same way.
        """
        path = self.write(
            "ghost.py",
            "import NXOpen\nNXOpen.NonexistentClass.NonexistentMethod()\n",
        )
        result = run_python(VALIDATE, path, "--mode", "ready", "--json")
        document = json.loads(result.stdout)
        self.assert_no_file_level_api_state(document)
        codes = [issue["code"] for issue in document["reports"][0]["issues"]]
        self.assertIn("missing-api-evidence", codes)

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    def test_nxopen_calls_without_evidence_do_not_get_api_evidence_state_with_index(self):
        """The same file, with the real index loaded."""
        path = self.write(
            "ghost_indexed.py",
            "import NXOpen\nNXOpen.NonexistentClass.NonexistentMethod()\n",
        )
        result = run_python(
            VALIDATE, path, "--mode", "ready", "--json", "--nx-root", nx_root()
        )
        document = json.loads(result.stdout)
        self.assert_no_file_level_api_state(document)
        self.assertTrue(document["indexLoaded"], "the index really was loaded")
        codes = [issue["code"] for issue in document["reports"][0]["issues"]]
        self.assertIn("missing-api-evidence", codes)

    def test_missing_api_evidence_is_reported_only_in_ready_mode(self):
        path = self.write("scaffold_no_evidence.py", "import NXOpen\n")
        result = run_python(VALIDATE, path, "--mode", "scaffold", "--json")
        document = json.loads(result.stdout)
        codes = [issue["code"] for issue in document["reports"][0]["issues"]]
        self.assertNotIn("missing-api-evidence", codes)

    def test_nxopen_use_is_read_from_the_ast_not_from_prose(self):
        """Prose mentioning NXOpen is not NXOpen use."""
        prose = self.write(
            "prose_only.py",
            "# NXOpen.NonexistentClass.NonexistentMethod() is never called\n"
            "value = 1\n",
        )
        result = run_python(VALIDATE, prose, "--mode", "ready", "--json")
        codes = [
            issue["code"]
            for issue in json.loads(result.stdout)["reports"][0]["issues"]
        ]
        self.assertNotIn("missing-api-evidence", codes)

        # ...and a real call counts even when nothing imports NXOpen, which a
        # text scan of the comments could never detect.
        called = self.write(
            "unimported.py",
            "NXOpen.Session.GetSession()\n",
        )
        result = run_python(VALIDATE, called, "--mode", "ready", "--json")
        codes = [
            issue["code"]
            for issue in json.loads(result.stdout)["reports"][0]["issues"]
        ]
        self.assertIn("missing-api-evidence", codes)

    def test_static_checked_is_not_described_as_an_api_or_runtime_result(self):
        path = self.write("plain_ok.py", "value = 1\n")
        result = run_python(VALIDATE, path, "--mode", "ready", "--json")
        document = json.loads(result.stdout)
        report = document["reports"][0]
        self.assertTrue(report["verificationStates"]["static-checked"])
        self.assertNotIn("api-evidence-checked", report["verificationStates"])
        limitations = " ".join(report["limitations"])
        self.assertIn("static-checked", limitations)
        self.assertIn("runnable", limitations)

    def test_strict_flag_still_maps_to_ready_mode(self):
        path = self.write("strict.py", "# UNVERIFIED\n")
        result = run_python(VALIDATE, path, "--strict")
        self.assertEqual(result.returncode, 1)

    def test_csharp_helper_catch_is_not_reported_as_suppression(self):
        source = (
            "using System;\n"
            "using NXOpen;\n"
            "public class J {\n"
            "  private static void Log(string m) {\n"
            "    try { Console.WriteLine(m); }\n"
            "    catch (Exception) { }\n"
            "  }\n"
            "  public static int Main(string[] args) {\n"
            "    try { Log(\"x\"); }\n"
            "    catch (Exception) { }\n"
            "    return 0;\n"
            "  }\n"
            "}\n"
        )
        result, _ = self.validate(source, "helper.cs", "--mode", "scaffold")
        self.assertIn("suppressed-exception-in-helper", result.stdout)
        # The handler in Main is not in a best-effort helper and stays a warning.
        self.assertIn("suppressed-exception ", result.stdout)

    def test_template_evidence_names_only_members_the_template_uses(self):
        """Illustrative evidence in a template must not read as a real claim.

        Every evidence comment must be well formed, and the member it names
        must actually be referenced in the file's code. A comment describing a
        call the template never makes would otherwise be counted as evidence
        for that call.
        """
        helper = load_module(
            os.path.join(SCRIPTS, "journal_evidence.py"), "evidence_for_test"
        )
        json_module = load_module(VALIDATE, "validator_for_test")

        for name, language in (
            ("python-journal.py", "python"),
            ("csharp-journal.cs", "csharp"),
        ):
            with io.open(os.path.join(TEMPLATES, name), "r", encoding="utf-8") as handle:
                text = handle.read()

            if language == "python":
                facts = json_module.collect_python_facts(text)
                mentioned = facts.identifiers
            else:
                facts = json_module.collect_csharp_facts(text)
                mentioned = set(re.findall(r"[A-Za-z_]\w*", facts["codeOnly"]))

            entries = []
            for line, comment in helper.comments_for(text, language):
                entry = helper.parse_evidence_comment(line, comment)
                if entry is not None:
                    entries.append(entry)

            for entry in entries:
                self.assertEqual(
                    entry["malformedSegments"],
                    [],
                    "%s line %s has malformed evidence segments"
                    % (name, entry["line"]),
                )
                for field in ("source", "binding", "version"):
                    self.assertIn(
                        field,
                        entry["fields"],
                        "%s line %s is missing '%s'" % (name, entry["line"], field),
                    )
                leaf = entry["member"].split(".")[-1]
                self.assertIn(
                    leaf,
                    mentioned,
                    "%s line %s cites %s, which the file's code never uses: "
                    "this is illustrative text being read as evidence."
                    % (name, entry["line"], entry["member"]),
                )


# ------------------------------------------------------------ evidence checker


class TestEvidenceChecker(TempMixin, unittest.TestCase):
    def check(self, text, name="journal.py", *extra):
        path = self.write(name, text)
        return run_python(EVIDENCE, path, *extra)

    def test_well_formed_evidence_passes(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    session = NXOpen.Session.GetSession()\n"
            "    # NX12-API: NXOpen.Session.SetUndoMark | source=local-xml"
            " | file=managed/NXOpen.xml | version=12.0.0.27 | binding=dotnet\n"
            "    session.SetUndoMark(1, 'x')\n"
        )
        result = self.check(source, "good.py")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_placeholder_evidence_is_rejected(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    # NX12-API: NXOpen.Session.SetUndoMark | source=todo | binding= | version=unknown\n"
            "    pass\n"
        )
        result = self.check(source, "placeholder.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("evidence-placeholder-value", result.stdout)

    def test_local_xml_source_requires_a_file(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    # NX12-API: NXOpen.Session.SetUndoMark | source=local-xml"
            " | version=12.0.0.27 | binding=dotnet\n"
            "    pass\n"
        )
        result = self.check(source, "nofile.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("evidence-missing-file", result.stdout)

    def test_evidence_marker_inside_a_string_is_ignored(self):
        source = (
            "import NXOpen\n"
            'text = "# NX12-API: NXOpen.Fake.Member | source=todo"\n'
        )
        result = self.check(source, "instring.py")
        self.assertEqual(result.returncode, 0, result.stdout)

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    def test_a_missing_xml_entry_is_not_corroboration_but_is_not_a_contradiction(self):
        """An incomplete index is not evidence that an API is absent.

        A claim of verified-local that the index cannot corroborate is reported
        as *not corroborated*, at warning level. Reporting it as a factual
        contradiction would assert something the index cannot know, because the
        shipped XML documentation is known to be incomplete.
        """
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    # NX12-API: NXOpen.NonexistentClass.NonexistentMethod | source=local-xml"
            " | file=NXBIN/managed/NXOpen.xml | version=12.0.0.27 | binding=dotnet"
            " | status=verified-local\n"
            "    pass\n"
        )
        result = self.check(source, "notcorroborated.py", "--nx-root", nx_root())
        self.assertIn("evidence-not-corroborated", result.stdout)
        self.assertIn("not corroborated", result.stdout)
        # The wording must not read as proof of absence.
        self.assertNotIn("evidence-contradicts-index", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    def test_inherited_member_is_resolved_as_declared_elsewhere(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    # NX12-API: NXOpen.Features.ExtrudeBuilder.Commit | source=local-xml"
            " | file=NXBIN/managed/NXOpen.xml | version=12.0.0.27 | binding=dotnet\n"
            "    pass\n"
        )
        result = self.check(source, "inherited.py", "--nx-root", nx_root())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("api-declared-elsewhere", result.stdout)

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    def test_undocumented_but_real_member_is_not_called_absent(self):
        source = (
            "import NXOpen\n"
            "def f():\n"
            "    # NX12-API: NXOpen.Session.GetSession | source=local-xml"
            " | file=NXBIN/managed/NXOpen.xml | version=12.0.0.27 | binding=dotnet\n"
            "    pass\n"
        )
        result = self.check(source, "undocumented.py", "--nx-root", nx_root())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("not proof the member is absent", result.stdout)

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    def test_index_reports_the_assembly_it_came_from(self):
        result = self.check("import NXOpen\n", "index.py", "--nx-root", nx_root(), "--json")
        document = json.loads(result.stdout)
        index = document["reports"][0]["index"]
        self.assertEqual(index["assemblyVersion"].split(".")[0], "12")
        self.assertGreater(index["memberCount"], 1000)


# ------------------------------------ evidence version, binding and source


class TestEvidenceVersionBindingAndSource(TempMixin, unittest.TestCase):
    """The version, binding and source fields are checked, not merely parsed.

    These use small temporary XML samples and an explicit mock version
    provider. Passing here means the comparison logic behaves as documented; it
    does not mean any real NX API was verified.
    """

    MEMBERS = (
        "T:NXOpen.Session",
        "M:NXOpen.Session.SetUndoMark(NXOpen.Session.MarkVisibility,System.String)",
    )

    def report_for(
        self,
        version="12.0.0.27",
        index_version="12.0.0.27",
        binding="dotnet",
        language="csharp",
        file_field="NXOpen.xml",
        source="local-xml",
        member="NXOpen.Session.SetUndoMark",
        index=None,
    ):
        if index is None:
            index = sample_index(
                self._tmp, member_ids=self.MEMBERS, version=index_version
            )
        marker = "//" if language == "csharp" else "#"
        extension = "cs" if language == "csharp" else "py"
        text = "%s NX12-API: %s | source=%s | file=%s | version=%s | binding=%s\n" % (
            marker,
            member,
            source,
            file_field,
            version,
            binding,
        )
        journal_path = self.write("journal.%s" % extension, text)
        context = journal_evidence.SourceContext(index, journal_path=journal_path)
        return journal_evidence.check_text(
            text, language, index=index, source_context=context
        )

    @unittest.skipUnless(os.name == "nt", "path comparison is case-insensitive on Windows")
    def test_case_differences_in_the_declared_path_do_not_break_matching(self):
        report = self.report_for(file_field="NXOPEN.XML")
        self.assertEqual(report["documentedEntryCount"], 1, self.codes(report))

    @staticmethod
    def codes(report):
        return sorted(set(problem["code"] for problem in report["problems"]))

    def test_version_2312_is_an_error(self):
        report = self.report_for(version="2312.0.0")
        self.assertEqual(report["errorCount"], 1, self.codes(report))
        self.assertIn("evidence-version-not-nx12", self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 0)

    def test_version_120_is_an_error(self):
        report = self.report_for(version="120.0")
        self.assertEqual(report["errorCount"], 1, self.codes(report))
        self.assertIn("evidence-version-not-nx12", self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 0)

    def test_a_matching_index_version_is_a_documented_match(self):
        report = self.report_for(version="12.0.0.27", index_version="12.0.0.27")
        self.assertEqual(report["errorCount"], 0, self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 1, self.codes(report))

    def test_missing_trailing_components_compare_equal_to_zero(self):
        """12.0 is 12.0.0.0, but it is still not 12.0.0.27."""
        padded = self.report_for(version="12.0", index_version="12.0.0.0")
        self.assertEqual(padded["documentedEntryCount"], 1, self.codes(padded))

        differing = self.report_for(version="12.0", index_version="12.0.0.27")
        self.assertEqual(differing["documentedEntryCount"], 0, self.codes(differing))

    def test_a_differing_patch_version_is_a_warning_and_not_a_match(self):
        report = self.report_for(version="12.0.2.9", index_version="12.0.0.27")
        self.assertIn("evidence-version-patch-differs", self.codes(report))
        self.assertEqual(report["errorCount"], 0, self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 0, "not a full match")

    def test_an_index_of_another_release_cannot_serve_as_an_nx12_source(self):
        report = self.report_for(version="12.0.0.0", index_version="2312.0.0.0")
        self.assertIn("index-version-not-nx12", self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 0)

    def test_an_unreadable_index_version_is_not_a_version_confirmation(self):
        report = self.report_for(version="12.0.0.27", index_version=None)
        self.assertIn("index-version-unknown", self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 0)

    def test_a_python_binding_is_not_verified_by_an_nxopen_dotnet_index(self):
        report = self.report_for(binding="python", language="python")
        self.assertIn("binding-not-verified-by-dotnet-index", self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 0)
        entry = report["entries"][0]
        # The declaration is reported as written; it is never rewritten to
        # silence the warning.
        self.assertEqual(entry["fields"]["binding"], "python")
        self.assertEqual(entry["bindingCheck"]["declared"], "python")

    def test_dotnet_evidence_in_a_python_source_is_a_reference_only(self):
        report = self.report_for(binding="dotnet", language="python")
        self.assertIn("binding-dotnet-in-python-source", self.codes(report))
        # The documentation lookup did succeed; what it cannot do is speak for
        # the Python binding, so it is not counted as a full match.
        self.assertEqual(report["documentationMatchedCount"], 1)
        self.assertEqual(report["documentedEntryCount"], 0)

    def test_a_missing_evidence_file_is_an_error(self):
        report = self.report_for(file_field="DoesNotExist.xml")
        self.assertIn("evidence-source-missing", self.codes(report))
        self.assertEqual(report["errorCount"], 1, self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 0)

    def test_a_file_outside_the_loaded_set_is_an_error(self):
        # The file exists, so only the loaded-set check can catch it.
        write_xml(os.path.join(self._tmp, "Other.xml"), ("T:NXOpen.Other",))
        report = self.report_for(file_field="Other.xml")
        self.assertIn("evidence-source-not-loaded", self.codes(report))
        self.assertEqual(report["errorCount"], 1, self.codes(report))

    def test_a_member_only_in_another_xml_cannot_certify_the_declared_file(self):
        index = sample_index_multi(
            self._tmp,
            [
                ("NXOpen.xml", ("T:NXOpen.Session",)),
                ("NXOpen.UF.xml", self.MEMBERS),
            ],
        )
        wrong = self.report_for(index=index, file_field="NXOpen.xml")
        self.assertIn("evidence-source-mismatch", self.codes(wrong))
        self.assertEqual(wrong["errorCount"], 1, self.codes(wrong))
        self.assertEqual(wrong["documentedEntryCount"], 0)

        # The same entry is accepted when it names the file it really came from.
        right = self.report_for(index=index, file_field="NXOpen.UF.xml")
        self.assertNotIn("evidence-source-mismatch", self.codes(right))
        self.assertEqual(right["errorCount"], 0, self.codes(right))
        self.assertEqual(right["documentedEntryCount"], 1)

    def test_a_relative_file_resolves_against_the_journal_directory(self):
        """--api-index without --nx-root: the journal's own directory is the base.

        This is the convention written down in references/api-validation.md and
        in SourceContext. It is pinned here because a silent change to it would
        start checking a different file than the evidence names.
        """
        index_directory = os.path.join(self._tmp, "index")
        os.makedirs(index_directory)
        xml = write_xml(os.path.join(index_directory, "NXOpen.xml"), self.MEMBERS)

        journal_directory = os.path.join(self._tmp, "journal")
        os.makedirs(journal_directory)

        def codes_for(name, file_field):
            path = os.path.join(journal_directory, name)
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "// NX12-API: NXOpen.Session.SetUndoMark | source=local-xml"
                    " | file=%s | version=12.0.0.27 | binding=dotnet\n"
                    % (file_field,)
                )
            result = run_python(EVIDENCE, path, "--api-index", xml, "--json")
            document = json.loads(result.stdout)
            return set(
                problem["code"] for problem in document["reports"][0]["problems"]
            )

        reachable = codes_for("relative.cs", "../index/NXOpen.xml")
        self.assertNotIn("evidence-source-missing", reachable)
        self.assertNotIn("evidence-source-not-loaded", reachable)

        # The same file name, resolved from the journal's directory, is not
        # there. Both conventions cannot pass at once.
        misplaced = codes_for("misplaced.cs", "NXOpen.xml")
        self.assertIn("evidence-source-missing", misplaced)

    def test_an_evidence_source_without_a_local_verifier_is_marked_unchecked(self):
        report = self.report_for(source="nx12-example", file_field="Example.cs")
        self.assertIn("evidence-source-not-locally-checked", self.codes(report))
        self.assertEqual(report["documentedEntryCount"], 0)

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    def test_a_documented_match_still_does_not_grant_file_level_api_truth(self):
        """Correct version, correct binding, correct source, existing member.

        Every per-entry check passes, and the file-level API states are still
        not granted: matching comments against documentation is not proof that
        every call is covered, nor that the journal runs.
        """
        source = (
            "using NXOpen;\n"
            "public class J {\n"
            "  public static int Main(string[] args) {\n"
            "    // NX12-API: NXOpen.Session.SetUndoMark | source=local-xml"
            " | file=NXBIN/managed/NXOpen.xml | version=12.0.0.27 | binding=dotnet\n"
            "    Session s = Session.GetSession();\n"
            '    s.SetUndoMark(Session.MarkVisibility.Visible, "j");\n'
            "    return 0;\n"
            "  }\n"
            "}\n"
        )
        path = self.write("documented.cs", source)
        result = run_python(EVIDENCE, path, "--nx-root", nx_root(), "--json")
        document = json.loads(result.stdout)
        report = document["reports"][0]

        self.assertEqual(report["documentedEntryCount"], 1, result.stdout)
        self.assertEqual(report["errorCount"], 0, result.stdout)
        self.assertTrue(document["indexLoaded"])
        self.assertFalse(document["apiTruthChecked"])
        self.assertFalse(document["callCoverageChecked"])
        self.assertEqual(document["documentedEntryCount"], 1)


# ------------------------------------------------------ template control flow


class FakeListingWindow(object):
    def __init__(self):
        self.lines = []
        self.fail = False
        self.opened = False

    def Open(self):
        self.opened = True

    def WriteLine(self, text):
        if self.fail:
            raise RuntimeError("listing window unavailable")
        self.lines.append(text)


class FakeBuilder(object):
    def __init__(self, name, fail_destroy=False):
        self.name = name
        self.fail_destroy = fail_destroy
        self.destroy_attempts = 0
        self.destroyed = False

    def Destroy(self):
        self.destroy_attempts += 1
        if self.fail_destroy:
            raise RuntimeError("destroy failed: " + self.name)
        self.destroyed = True


class FakeSession(object):
    def __init__(self, listing_window):
        self.ListingWindow = listing_window
        self.Parts = types.SimpleNamespace(Work=object(), Display=object())
        self.undo_marks = []
        self.rollbacks = []
        self.fail_rollback = False

    def SetUndoMark(self, visibility, name):
        self.undo_marks.append(name)
        return 4242

    def SetUndoMarkName(self, mark, name):
        pass

    def UndoToMark(self, mark, name):
        if self.fail_rollback:
            raise RuntimeError("rollback failed")
        self.rollbacks.append((mark, name))


def fake_nxopen(session):
    module = types.ModuleType("NXOpen")

    class Session(object):
        MarkVisibility = types.SimpleNamespace(Visible=1, Invisible=2)

        @staticmethod
        def GetSession():
            return session

    module.Session = Session
    return module


class TestTemplateControlFlow(TempMixin, unittest.TestCase):
    """Exercise the template's failure handling with simulated NXOpen objects.

    These tests cover control flow only. They say nothing about whether the
    template's NXOpen calls are valid.
    """

    def build(self, listing_window=None, session=None):
        if listing_window is None:
            listing_window = FakeListingWindow()
        if session is None:
            session = FakeSession(listing_window)

        with io.open(
            os.path.join(TEMPLATES, "python-journal.py"), "r", encoding="utf-8"
        ) as handle:
            source = handle.read()
        source = source.replace("{{JOURNAL_NAME}}", "TestJournal")
        source = source.replace("{{DESCRIPTION}}", "control flow test")
        path = self.write("template_under_test.py", source)

        original = sys.modules.get("NXOpen")
        sys.modules["NXOpen"] = fake_nxopen(session)
        try:
            module = load_module(path, "template_under_test")
        finally:
            if original is None:
                sys.modules.pop("NXOpen", None)
            else:
                sys.modules["NXOpen"] = original
        return module, session, listing_window

    @contextlib.contextmanager
    def quiet_stderr(self):
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            yield buffer

    def test_log_failure_does_not_prevent_rollback(self):
        module, session, listing_window = self.build()
        listing_window.fail = True

        def boom(session_arg, work_part, builders):
            raise ValueError("original modeling failure")

        module.run_modeling = boom
        with self.quiet_stderr():
            with self.assertRaises(ValueError) as caught:
                module.main()

        self.assertEqual(str(caught.exception), "original modeling failure")
        self.assertEqual(len(session.rollbacks), 1, "rollback must still be attempted")

    def test_broken_log_helper_does_not_prevent_rollback(self):
        module, session, listing_window = self.build()

        def broken_log(message):
            raise RuntimeError("logging is broken")

        module.log = broken_log

        def boom(session_arg, work_part, builders):
            raise ValueError("original modeling failure")

        module.run_modeling = boom
        with self.quiet_stderr():
            with self.assertRaises(ValueError) as caught:
                module.main()

        self.assertEqual(str(caught.exception), "original modeling failure")
        self.assertEqual(len(session.rollbacks), 1)

    def test_rollback_failure_does_not_replace_the_original_exception(self):
        module, session, _ = self.build()
        session.fail_rollback = True

        def boom(session_arg, work_part, builders):
            raise ValueError("original modeling failure")

        module.run_modeling = boom
        with self.quiet_stderr():
            with self.assertRaises(ValueError) as caught:
                module.main()

        self.assertEqual(
            str(caught.exception),
            "original modeling failure",
            "a failed rollback must not become the reported error",
        )

    def test_one_failed_builder_destroy_does_not_stop_the_others(self):
        module, session, _ = self.build()
        builders = [
            FakeBuilder("first"),
            FakeBuilder("second", fail_destroy=True),
            FakeBuilder("third"),
        ]

        def register(session_arg, work_part, registry):
            registry.extend(builders)

        module.run_modeling = register
        with self.quiet_stderr():
            module.main()

        self.assertTrue(builders[0].destroyed)
        self.assertTrue(builders[2].destroyed)
        self.assertEqual(builders[1].destroy_attempts, 1)
        self.assertFalse(builders[1].destroyed)

    def test_builders_are_destroyed_before_the_undo_mark_is_restored(self):
        module, session, _ = self.build()
        order = []
        builder = FakeBuilder("only")
        original_destroy = builder.Destroy

        def recording_destroy():
            order.append("destroy")
            return original_destroy()

        builder.Destroy = recording_destroy
        original_rollback = session.UndoToMark

        def recording_rollback(mark, name):
            order.append("rollback")
            return original_rollback(mark, name)

        session.UndoToMark = recording_rollback

        def register_then_fail(session_arg, work_part, registry):
            registry.append(builder)
            raise ValueError("failure")

        module.run_modeling = register_then_fail
        with self.quiet_stderr():
            with self.assertRaises(ValueError):
                module.main()

        self.assertEqual(order, ["destroy", "rollback"])

    def test_successful_run_reports_success_and_does_not_roll_back(self):
        module, session, _ = self.build()
        module.run_modeling = lambda s, w, b: None
        with self.quiet_stderr():
            self.assertEqual(module.main(), 0)
        self.assertEqual(session.rollbacks, [])

    def test_template_never_saves_closes_or_exports_by_default(self):
        with io.open(
            os.path.join(TEMPLATES, "python-journal.py"), "r", encoding="utf-8"
        ) as handle:
            source = handle.read()
        tree = ast.parse(source)
        forbidden = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("Save", "SaveAs", "Close", "Export", "DeleteFile"):
                    forbidden.add(node.func.attr)
        self.assertEqual(forbidden, set(), "template performs file operations: %s" % forbidden)


# --------------------------------------------------- C# rollback status log


def csharp_block_bounds(stripped, header):
    """Offsets of the brace-matched block that follows *header*, or None.

    *stripped* must be comment- and string-stripped text: the stripper keeps
    positions and line numbers stable, so braces inside comments or literals
    cannot throw the count off, and the same offsets apply to the raw text.
    """
    start = stripped.find(header)
    if start < 0:
        return None
    open_brace = stripped.find("{", start + len(header))
    if open_brace < 0:
        return None
    depth = 0
    for index in range(open_brace, len(stripped)):
        char = stripped[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return open_brace, index + 1
    return None


def csharp_body(raw, stripped, header):
    """The (stripped, raw) text of one brace-matched C# block."""
    bounds = csharp_block_bounds(stripped, header)
    if bounds is None:
        return None, None
    return stripped[bounds[0]:bounds[1]], raw[bounds[0]:bounds[1]]


class TestCsharpRollbackStatus(unittest.TestCase):
    """The C# failure log reports the rollback that actually happened.

    The template is analysed, not executed. The allowed operations cover
    compiling C# but not running the result, and NX is never started, so these
    checks read the control flow the compiler would see: where the state is
    reset, which branch assigns which value, and what Main reads when it
    reports the failure.

    They are structural rather than a search for the word "succeeded", and
    test_the_original_defect_would_be_caught shows they fail if the old
    unconditional sentence is restored.
    """

    MAIN = "public static int Main(string[] args)"
    RUN = "private static void Run()"
    UNDO = "private static void UndoToMark("
    STATUS = "private static string RollbackStatus()"

    def setUp(self):
        with io.open(CSHARP_TEMPLATE, "r", encoding="utf-8") as handle:
            self.raw = handle.read()
        self.code = journal_evidence.strip_csharp_noncode(self.raw)

    def body(self, header):
        code, raw = csharp_body(self.raw, self.code, header)
        self.assertIsNotNone(code, "no C# block found for: " + header)
        return code, raw

    def status_messages(self):
        """The three messages, with each one's line-broken fragments joined."""
        _, raw = self.body(self.STATUS)
        messages = []
        for statement in raw.split("return")[1:]:
            fragments = re.findall(r'"((?:[^"\\]|\\.)*)"', statement.split(";")[0])
            if fragments:
                messages.append("".join(fragments))
        return messages

    def test_the_state_is_reset_before_the_journal_can_fail(self):
        """Scenario 1: a failure before the undo mark reports not-attempted."""
        code, _ = self.body(self.RUN)
        reset = code.find("_rollbackState = RollbackState.NotAttempted")
        mark = code.find("SetUndoMark(")
        self.assertGreaterEqual(reset, 0, "Run() must reset the rollback state")
        self.assertGreaterEqual(mark, 0, "Run() must create the undo mark")
        self.assertLess(
            reset,
            mark,
            "the state must be reset before the undo mark exists, so a failure "
            "on the way there cannot inherit an older status",
        )
        self.assertIn(
            "_rollbackException = null",
            code,
            "a previous rollback exception must not survive into a new run",
        )

        # The untouched state is the one Main reports as "not-attempted", and
        # that message must not claim the part was rolled back.
        messages = self.status_messages()
        unattempted = [text for text in messages if text.startswith("not-attempted")]
        self.assertEqual(len(unattempted), 1, messages)
        self.assertNotIn("was rolled back to", unattempted[0])
        self.assertIn("NOT rolled back", unattempted[0])

    def test_a_completed_rollback_is_recorded_after_the_call_returns(self):
        """Scenario 2: the business operation fails and the rollback works."""
        code, _ = self.body(self.UNDO)
        call = code.find("session.UndoToMark(")
        succeeded = code.find("RollbackState.Succeeded")
        handler = code.find("catch")
        self.assertGreaterEqual(call, 0)
        self.assertGreaterEqual(succeeded, 0, "a completed rollback must be recorded")
        self.assertGreater(
            succeeded,
            call,
            "Succeeded must be assigned after the UndoToMark call, on the path "
            "that only a normal return reaches",
        )
        self.assertGreaterEqual(handler, 0)
        self.assertLess(
            succeeded,
            handler,
            "Succeeded must not sit in the catch block",
        )

        messages = self.status_messages()
        succeeded_message = [text for text in messages if text.startswith("succeeded")]
        self.assertEqual(len(succeeded_message), 1, messages)
        self.assertIn("was rolled back to the journal undo mark", succeeded_message[0])

    def test_a_failed_rollback_is_recorded_with_its_exception(self):
        """Scenario 3: the rollback itself throws."""
        code, _ = self.body(self.UNDO)
        handler = code.find("catch")
        failed = code.find("RollbackState.Failed")
        recorded = code.find("_rollbackException = ex")
        self.assertGreaterEqual(handler, 0, "UndoToMark must handle a throw")
        self.assertGreater(
            failed, handler, "Failed belongs in the block that handles the throw"
        )
        self.assertGreater(
            recorded,
            handler,
            "the exception thrown by the rollback must be kept, not discarded",
        )

        messages = self.status_messages()
        failed_message = [text for text in messages if text.startswith("failed")]
        self.assertEqual(len(failed_message), 1, messages)
        self.assertIn("did not complete", failed_message[0])

    def test_main_logs_the_recorded_state_and_keeps_the_original_exception(self):
        code, _ = self.body(self.MAIN)
        self.assertIn(
            "RollbackStatus()",
            code,
            "the failure log must read the recorded state instead of asserting "
            "that the part was rolled back",
        )
        self.assertIn(
            "ex.ToString()",
            code,
            "the original exception must still be reported in full",
        )
        self.assertIn(
            "_rollbackException",
            code,
            "a failed rollback must be reported, separately from the cause",
        )

    def test_only_one_message_claims_a_rollback_happened(self):
        messages = self.status_messages()
        self.assertEqual(len(messages), 3, messages)
        claiming = [
            text for text in messages if "was rolled back to the journal undo mark" in text
        ]
        self.assertEqual(
            len(claiming),
            1,
            "exactly one of the three states may claim the part was rolled back",
        )

    def test_the_original_defect_would_be_caught(self):
        """Mutation sensitivity for the confirmed defect.

        The defect was a fixed sentence claiming a rollback even when none had
        happened. Putting it back must make the check above fail, which is what
        makes that check a control-flow assertion rather than a word search.
        """
        broken = re.sub(
            r'": journal failed\. Rollback: ",\s*RollbackStatus\(\),\s*"\."',
            '": journal failed and the part was rolled back."',
            self.raw,
        )
        self.assertNotEqual(broken, self.raw, "the mutation must apply")
        stripped = journal_evidence.strip_csharp_noncode(broken)
        code, _ = csharp_body(broken, stripped, self.MAIN)
        self.assertIsNotNone(code)
        self.assertNotIn(
            "RollbackStatus()",
            code,
            "with the old sentence restored there is no state read left, so the "
            "assertion in test_main_logs_the_recorded_state must fail",
        )


# ------------------------------------------------------------------ PowerShell


@unittest.skipUnless(POWERSHELL, "PowerShell is not available")
class TestTemplateRenderer(TempMixin, unittest.TestCase):
    def render(self, *args):
        return run_powershell(CREATE_TEMPLATE, *args)

    def test_renders_a_parseable_python_journal(self):
        output = os.path.join(self._tmp, "rendered.py")
        result = self.render(
            "-Language", "python",
            "-OutputPath", output,
            "-JournalName", "BlockJournal",
            "-Description", "Creates a block",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with io.open(output, "r", encoding="utf-8") as handle:
            source = handle.read()
        ast.parse(source)
        self.assertNotIn("{{JOURNAL_NAME}}", source)
        self.assertNotIn("{{DESCRIPTION}}", source)

    def test_hostile_input_round_trips(self):
        output = os.path.join(self._tmp, "hostile.py")
        name = 'My"Journal"\nSecond\tline\\path\\to 中文名'
        result = self.render(
            "-Language", "python",
            "-OutputPath", output,
            "-JournalName", name,
            "-Description", "C:\\temp\\new\nsecond line 中文描述",
            "-Json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with io.open(output, "r", encoding="utf-8") as handle:
            source = handle.read()

        tree = ast.parse(source)
        recovered = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "JOURNAL_NAME":
                recovered = ast.literal_eval(node.value)
        self.assertEqual(recovered, name, "name must survive escaping intact")

        with io.open(output, "r", encoding="utf-8") as handle:
            header = handle.readline()
        self.assertIn("C:\\temp\\new", header, "the comment must keep single backslashes")
        self.assertIn("中文描述", header)

    def test_path_with_spaces_and_chinese_is_accepted(self):
        folder = os.path.join(self._tmp, "nx 中文 目录")
        output = os.path.join(folder, "journal.py")
        result = self.render(
            "-Language", "python",
            "-OutputPath", output,
            "-JournalName", "Spaced",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.isfile(output))

    def test_existing_output_is_refused_without_force(self):
        output = os.path.join(self._tmp, "existing.py")
        first = self.render("-Language", "python", "-OutputPath", output, "-JournalName", "One")
        self.assertEqual(first.returncode, 0, first.stderr)

        second = self.render("-Language", "python", "-OutputPath", output, "-JournalName", "Two")
        self.assertEqual(second.returncode, 3, second.stdout)

        forced = self.render(
            "-Language", "python", "-OutputPath", output, "-JournalName", "Two", "-Force"
        )
        self.assertEqual(forced.returncode, 0, forced.stderr)

    def test_missing_template_exits_four(self):
        result = self.render(
            "-Language", "python",
            "-OutputPath", os.path.join(self._tmp, "x.py"),
            "-JournalName", "N",
            "-TemplatePath", os.path.join(self._tmp, "absent.py"),
        )
        self.assertEqual(result.returncode, 4)

    def test_rendered_scaffold_is_reported_as_scaffold(self):
        output = os.path.join(self._tmp, "scaffold.py")
        self.render("-Language", "python", "-OutputPath", output, "-JournalName", "S")
        result = run_python(VALIDATE, output, "--mode", "scaffold")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("scaffold", result.stdout)


@unittest.skipUnless(POWERSHELL, "PowerShell is not available")
class TestInstallationInspector(TempMixin, unittest.TestCase):
    def inspect(self, *args):
        return run_powershell(INSPECT, *args)

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    def test_confirms_a_real_nx12_installation(self):
        result = self.inspect("-NxRoot", nx_root(), "-Json")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["summary"]["classification"], "confirmed-nx12")
        self.assertEqual(document["summary"]["selectedRoot"], nx_root())
        candidates = [c for c in document["candidates"] if c["root"] == nx_root()]
        self.assertEqual(len(candidates), 1)
        majors = {
            item["major"]
            for item in candidates[0]["evidence"]
            if item["authoritative"]
        }
        self.assertEqual(majors, {12})

    def test_a_non_nx12_version_is_not_rescued_by_an_nx12_path(self):
        folder = os.path.join(self._tmp, "NX12-decoy")
        os.makedirs(folder)
        shutil.copyfile(
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "notepad.exe"),
            os.path.join(folder, "ugraf.exe"),
        )
        result = self.inspect("-NxRoot", folder, "-Json")
        document = json.loads(result.stdout)
        entry = [c for c in document["candidates"] if c["root"] == folder][0]
        self.assertEqual(entry["classification"], "not-nx12")
        self.assertTrue(entry["pathNameHint"]["matched"])

    def test_artifacts_without_version_evidence_stay_unconfirmed(self):
        folder = os.path.join(self._tmp, "NX12-emptydll")
        os.makedirs(folder)
        open(os.path.join(folder, "NXOpen.dll"), "w").close()
        result = self.inspect("-NxRoot", folder, "-Json")
        document = json.loads(result.stdout)
        entry = [c for c in document["candidates"] if c["root"] == folder][0]
        self.assertEqual(entry["classification"], "candidate-unconfirmed")

    def test_json_is_parseable_and_arrays_stay_arrays(self):
        result = self.inspect("-Json")
        document = json.loads(result.stdout)
        self.assertIsInstance(document["candidates"], list)
        self.assertIn("selectedRoot", document["summary"])
        self.assertIn(document["exitCode"], (0, 1, 3, 4, 5))

    def test_an_unconfirmed_candidate_is_never_selected(self):
        """A discovered root that is not NX 12 must never be selected.

        The exit code is deliberately not asserted here. Installation
        discovery also scans drive roots, so on a machine that really has NX 12
        the script legitimately finds and confirms it and exits 0. The
        invariant that matters is that the decoy is neither confirmed nor
        chosen, and that no unconfirmed root is ever used to compile or run
        anything.
        """
        folder = os.path.join(self._tmp, "NX12-decoy")
        os.makedirs(folder)
        shutil.copyfile(
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "notepad.exe"),
            os.path.join(folder, "ugraf.exe"),
        )
        environment = dict(os.environ)
        for name in ("UGII_BASE_DIR", "UGII_ROOT_DIR"):
            environment.pop(name, None)

        result = run_powershell(
            INSPECT, "-NxRoot", folder, "-Json", env=environment
        )
        document = json.loads(result.stdout)
        decoys = [c for c in document["candidates"] if c["root"] == folder]
        self.assertEqual(len(decoys), 1, "the named root must be inspected")
        self.assertEqual(decoys[0]["classification"], "not-nx12")
        self.assertNotEqual(document["summary"]["selectedRoot"], folder)

        confirmed = [
            c for c in document["candidates"] if c["classification"] == "confirmed-nx12"
        ]
        if confirmed:
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(document["summary"]["selectedRoot"], confirmed[0]["root"])
        else:
            self.assertEqual(result.returncode, 3, result.stdout)
            self.assertIsNone(document["summary"]["selectedRoot"])


@unittest.skipUnless(POWERSHELL, "PowerShell is not available")
class TestCsharpCompileCheck(TempMixin, unittest.TestCase):
    """The flow is tested here; a simulated assembly never proves NX 12
    compatibility, and the script is expected to say so itself."""

    def check(self, *args):
        return run_powershell(CSHARP_CHECK, *args)

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    @unittest.skipUnless(csharp_compiler(), "no .NET Framework C# compiler available")
    @unittest.skipUnless(os.path.isfile(CSHARP_CHECK), "C# compile check not present")
    def test_the_rendered_template_really_compiles(self):
        """The template compiles against the real installation.

        The JSON-contract test above accepts compiled, compile-failed and
        skipped, because it has to run on machines without an NX root or a
        compiler. This test is the proof rather than the contract: when both
        are present, the rendered template must reach "compiled", and a
        compile-failed or skipped result is a failure.

        The result is never executed, NX is never started, and both the source
        and the assembly stay in the temporary directory.
        """
        rendered = os.path.join(self._tmp, "Nx12Journal.cs")
        render = run_powershell(
            CREATE_TEMPLATE,
            "-Language", "csharp",
            "-OutputPath", rendered,
            "-JournalName", "CompileCheckJournal",
            "-Description", "compile check for the rendered template",
        )
        self.assertEqual(render.returncode, 0, render.stderr)
        self.assertTrue(os.path.isfile(rendered), render.stdout)

        output_directory = os.path.join(self._tmp, "compiled")
        result = self.check(
            "-SourceFile", rendered,
            "-NxRoot", nx_root(),
            "-OutputDirectory", output_directory,
            "-Json",
        )
        document = json.loads(result.stdout)

        self.assertEqual(
            document["outcome"],
            "compiled",
            "an NX root and a compiler are both present, so this must compile. "
            "Reason given: " + str(document.get("reason")),
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(document["diagnostics"]["errorCount"], 0, result.stdout)

        assembly = document["compilation"]["assemblyPath"]
        self.assertTrue(assembly, "the result must name the compiled artifact")
        self.assertTrue(
            os.path.isfile(assembly),
            "the compiled artifact must exist on disk: %s" % (assembly,),
        )
        self.assertTrue(
            os.path.abspath(assembly).startswith(os.path.abspath(self._tmp)),
            "the compiled artifact must stay in the temporary directory: %s"
            % (assembly,),
        )
        self.assertFalse(document["safety"]["assemblyExecuted"])
        self.assertFalse(document["safety"]["nxStarted"])

    @unittest.skipUnless(os.path.isfile(CSHARP_CHECK), "C# compile check not present")
    def test_missing_nx_root_is_not_reported_as_success(self):
        result = self.check(
            "-SourceFile", CSHARP_TEMPLATE,
            "-NxRoot", os.path.join(self._tmp, "does-not-exist"),
            "-OutputDirectory", os.path.join(self._tmp, "build"),
            "-Json",
        )
        self.assertNotEqual(result.returncode, 0, "must not claim success")
        document = json.loads(result.stdout)
        self.assertNotEqual(document["outcome"], "compiled")

    @unittest.skipUnless(os.path.isfile(CSHARP_CHECK), "C# compile check not present")
    def test_assemblies_of_the_wrong_version_are_refused(self):
        # A decoy root whose "NXOpen.dll" is an unrelated Windows binary: the
        # script must skip rather than compile against a foreign assembly.
        folder = os.path.join(self._tmp, "NX12-decoy", "NXBIN", "managed")
        os.makedirs(folder)
        system = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32")
        for name in ("NXOpen.dll", "NXOpen.UF.dll"):
            shutil.copyfile(os.path.join(system, "notepad.exe"), os.path.join(folder, name))

        result = self.check(
            "-SourceFile", CSHARP_TEMPLATE,
            "-NxRoot", os.path.join(self._tmp, "NX12-decoy"),
            "-OutputDirectory", os.path.join(self._tmp, "build-decoy"),
            "-Json",
        )
        self.assertNotEqual(result.returncode, 0, "must not claim success")
        document = json.loads(result.stdout)
        self.assertEqual(document["outcome"], "skipped")

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    @unittest.skipUnless(os.path.isfile(CSHARP_CHECK), "C# compile check not present")
    def test_json_reports_what_the_result_does_not_prove(self):
        result = self.check(
            "-SourceFile", CSHARP_TEMPLATE,
            "-NxRoot", nx_root(),
            "-OutputDirectory", os.path.join(self._tmp, "build"),
            "-Json",
        )
        document = json.loads(result.stdout)
        self.assertIn(document["outcome"], ("compiled", "compile-failed", "skipped"))

        self.assertTrue(document["notes"], "the report must carry explicit caveats")
        combined = json.dumps(document).lower()
        self.assertTrue(
            any(
                phrase in combined
                for phrase in (
                    "model runs correctly",
                    "not that the model",
                    "does not prove",
                )
            ),
            "a successful compile must not be presented as proving the "
            "journal runs",
        )
        self.assertIn(
            "overload",
            combined,
            "compilation catches missing members but can still pick the wrong "
            "overload, and the report must say so",
        )

    @unittest.skipUnless(nx_root(), "no local NX installation available")
    @unittest.skipUnless(os.path.isfile(CSHARP_CHECK), "C# compile check not present")
    def test_a_nonexistent_member_fails_the_compile(self):
        source = self.write(
            "broken.cs",
            "using NXOpen;\n"
            "public class Broken {\n"
            "  public static int Main(string[] args) {\n"
            "    Session s = Session.GetSession();\n"
            "    NXOpen.NonexistentClass.NonexistentMethod();\n"
            "    return 0;\n"
            "  }\n"
            "}\n",
        )
        result = self.check(
            "-SourceFile", source,
            "-NxRoot", nx_root(),
            "-OutputDirectory", os.path.join(self._tmp, "build-broken"),
            "-Json",
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        document = json.loads(result.stdout)
        self.assertEqual(document["outcome"], "compile-failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
