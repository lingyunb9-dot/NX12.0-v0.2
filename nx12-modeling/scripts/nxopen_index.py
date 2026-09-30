"""Read-only helpers for querying a local NXOpen .NET API index.

Two independent pieces of evidence live here:

* ``read_file_version`` reads the Win32 fixed file version out of a PE image
  without loading or executing it, so a validator can prove which NX build an
  ``NXOpen.dll`` belongs to.
* ``NxOpenIndex`` scans the XML documentation files that ship beside
  ``NXOpen.dll`` and answers "is this type or member documented for this
  installation?".

Nothing in this module imports, loads, or calls into NXOpen itself. Every
operation is a read of files on disk.

Limits that callers must respect
--------------------------------
The shipped XML documentation is incomplete, and the index can only report
what is documented. Verified against a real NX 12.0.0.27 installation:

* ``NXOpen.Session.GetSession`` exists in the assembly and in Siemens' own
  samples, but has no XML entry at all.
* Members inherited from a base class are documented only on the declaring
  base type. ``NXOpen.Features.ExtrudeBuilder.Commit`` is documented as
  ``NXOpen.Builder.Commit``.
* ``T:NXOpen.UF.UFConstants`` is documented, but none of its fields are.

A missing entry therefore means "not documented in this index", never "does
not exist". ``NxOpenIndex.lookup`` returns a status that says which of those
cases applies, and callers must not upgrade a weak result into a strong claim.

The module deliberately stays on conservative Python 3 syntax so it can also
run under the Python 3.6 interpreter embedded in NX 12.
"""

import io
import os
import re


# The XML documentation file uses standard .NET member identifiers, for example
#   T:NXOpen.Features.ExtrudeBuilder
#   M:NXOpen.Features.ExtrudeBuilder.Commit()
#   P:NXOpen.Session.ListingWindow
#   F:NXOpen.Session.MarkVisibility.Visible
_MEMBER_RE = re.compile(r'<member name="([^"]+)">')

_MEMBER_KINDS = {
    "T": "type",
    "M": "method",
    "P": "property",
    "F": "field",
    "E": "event",
    "N": "namespace",
}

# Documentation files that ship with NX 12 beside NXOpen.dll, in load order.
DEFAULT_DOC_FILES = (
    "NXOpen.xml",
    "NXOpen.UF.xml",
    "NXOpen.Utilities.xml",
    "NXOpen.Guide.xml",
    "NXOpenUI.xml",
)

# Sources a caller may cite in an NX12-API evidence comment.
EVIDENCE_SOURCES = (
    "local-xml",
    "local-index",
    "nxopen-mcp",
    "pyi-stub",
    "recorded-journal",
    "nx12-example",
    "manual",
)

EVIDENCE_BINDINGS = ("dotnet", "python")

# Lookup outcomes, ordered from strongest to weakest.
STATUS_TYPE = "type-documented"
STATUS_MEMBER = "member-documented"
STATUS_ELSEWHERE = "member-declared-elsewhere"
STATUS_MEMBER_UNDOCUMENTED = "member-not-documented"
STATUS_TYPE_UNDOCUMENTED = "type-not-documented"
STATUS_EMPTY = "empty"


def read_file_version(path):
    """Return the Win32 file version of *path* as "a.b.c.d", or None.

    Uses version.dll so the image is only read, never mapped into the process.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    class _FixedFileInfo(ctypes.Structure):
        _fields_ = [
            ("dwSignature", wintypes.DWORD),
            ("dwStrucVersion", wintypes.DWORD),
            ("dwFileVersionMS", wintypes.DWORD),
            ("dwFileVersionLS", wintypes.DWORD),
        ]

    try:
        library = ctypes.WinDLL("version")
    except OSError:
        return None

    library.GetFileVersionInfoSizeW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    library.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    library.GetFileVersionInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    library.GetFileVersionInfoW.restype = wintypes.BOOL
    library.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint),
    ]
    library.VerQueryValueW.restype = wintypes.BOOL

    try:
        ignored = wintypes.DWORD(0)
        size = library.GetFileVersionInfoSizeW(str(path), ctypes.byref(ignored))
        if not size:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not library.GetFileVersionInfoW(str(path), 0, size, buffer):
            return None
        pointer = ctypes.c_void_p()
        length = ctypes.c_uint()
        if not library.VerQueryValueW(
            buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)
        ):
            return None
        if length.value < ctypes.sizeof(_FixedFileInfo):
            return None
        info = ctypes.cast(pointer, ctypes.POINTER(_FixedFileInfo)).contents
        if info.dwSignature != 0xFEEF04BD:
            return None
    except Exception:
        return None

    high = info.dwFileVersionMS
    low = info.dwFileVersionLS
    return "{0}.{1}.{2}.{3}".format(
        high >> 16, high & 0xFFFF, low >> 16, low & 0xFFFF
    )


def major_version(version_text):
    """Return the leading integer of a dotted version string, or None.

    A bare number keeps its full value: "120" yields 120, never 12.
    """
    if not version_text:
        return None
    match = re.match(r"\s*(\d{1,6})", str(version_text))
    if not match:
        return None
    return int(match.group(1))


# Win32 file versions have four components. Evidence may write fewer, so the
# missing ones are treated as zero when two versions are compared.
VERSION_COMPONENTS = 4


def version_components(version_text):
    """Return a 4-tuple of ints for a dotted version, or None.

    At most four components are accepted, matching what a Win32 file version
    can hold. Missing trailing components are padded with zero, so
    ``12.0`` becomes ``(12, 0, 0, 0)``.
    """
    if version_text is None:
        return None
    match = re.match(r"\s*(\d+(?:\.\d+){0,3})\s*$", str(version_text))
    if not match:
        return None
    parts = [int(part) for part in match.group(1).split(".")]
    while len(parts) < VERSION_COMPONENTS:
        parts.append(0)
    return tuple(parts)


def compare_versions(left, right):
    """Compare two dotted versions after padding missing components with 0.

    Returns one of:

    ``"equal"``          the padded components are identical (12.0 == 12.0.0.0)
    ``"patch-differs"``  same major, a later component differs (12.0.0.27 vs 12.0.2.9)
    ``"major-differs"``  the leading component differs (12.x vs 2312.x)
    ``None``             either side is absent or not a dotted version

    ``None`` is not a pass. A caller that cannot parse a version has not
    compared anything.
    """
    first = version_components(left)
    second = version_components(right)
    if first is None or second is None:
        return None
    if first == second:
        return "equal"
    if first[0] != second[0]:
        return "major-differs"
    return "patch-differs"


def parse_member_id(member_id):
    """Split a .NET XML member id into (kind, dotted_name, parameter_list)."""
    prefix, _, remainder = member_id.partition(":")
    kind = _MEMBER_KINDS.get(prefix, "unknown")
    name, _, parameters = remainder.partition("(")
    if parameters.endswith(")"):
        parameters = parameters[:-1]
    return kind, name, parameters


def find_doc_files(nx_root, doc_names=DEFAULT_DOC_FILES):
    """Return the documentation files present under an NX installation root.

    ``managed`` is not hard-coded as the only possible location: known layouts
    are probed first, then a bounded search covers the rest.
    """
    found = []
    seen = set()

    def _consider(path):
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            return
        if os.path.isfile(path):
            seen.add(key)
            found.append(os.path.abspath(path))

    for hint in ("NXBIN/managed", "managed", "NXBIN", ""):
        folder = os.path.join(nx_root, hint) if hint else nx_root
        if not os.path.isdir(folder):
            continue
        for name in doc_names:
            _consider(os.path.join(folder, name))

    return found


class NxOpenIndex(object):
    """An in-memory index of members documented across one or more NXOpen XML files."""

    def __init__(self, xml_paths, version_provider=None):
        if isinstance(xml_paths, str):
            xml_paths = [xml_paths]
        self.xml_paths = [os.path.abspath(p) for p in xml_paths]
        self.members = {}
        # Which XML file recorded each member and each type. Without this a
        # checker could only say "some index in the set contains this name",
        # which is not the same as "the file this evidence names contains it".
        self.member_sources = {}
        self.type_sources = {}
        self.types = set()
        self.namespaces = set()
        self.member_count = 0
        self.truncated = False
        self._by_leaf = None
        # Tests and callers that copied the XML away from its assembly supply
        # the version explicitly. A provider returning None means "unknown",
        # which callers must report as unknown rather than as a match.
        self._version_provider = version_provider

    @property
    def assembly_path(self):
        """The NXOpen.dll that would sit beside the first documentation file."""
        if not self.xml_paths:
            return None
        return os.path.join(os.path.dirname(self.xml_paths[0]), "NXOpen.dll")

    def assembly_version(self):
        """File version that the assemblies beside this index carry.

        Falls back to reading the sibling ``NXOpen.dll`` when no explicit
        version provider was supplied. Returns None when the version cannot be
        established, which is *not* the same as a version match.
        """
        if self._version_provider is not None:
            try:
                return self._version_provider()
            except Exception:
                return None
        path = self.assembly_path
        if not path:
            return None
        return read_file_version(path)

    def sources_of(self, full_name):
        """XML files that recorded *full_name*, case-insensitively compared."""
        collected = self.member_sources.get(full_name)
        if collected is None:
            collected = self.type_sources.get(full_name)
        return sorted(collected) if collected else []

    @classmethod
    def load(cls, xml_paths, member_limit=None, version_provider=None):
        """Scan the given XML files and build a combined index.

        ``member_limit`` bounds the number of members read, which keeps tests
        fast. The limit is recorded so a truncated index never silently reports
        a documented member as absent.
        """
        index = cls(xml_paths, version_provider=version_provider)
        for xml_path in index.xml_paths:
            if not os.path.isfile(xml_path):
                continue
            with io.open(xml_path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    for match in _MEMBER_RE.finditer(line):
                        member_id = match.group(1)
                        kind, name, parameters = parse_member_id(member_id)
                        if kind == "namespace":
                            index.namespaces.add(name)
                            continue
                        if kind == "type":
                            index.types.add(name)
                            index.members.setdefault(name, [])
                            index.type_sources.setdefault(name, set()).add(xml_path)
                            continue
                        index.members.setdefault(name, []).append(parameters)
                        index.member_sources.setdefault(name, set()).add(xml_path)
                        index.types.add(name.rsplit(".", 1)[0])
                        index.member_count += 1
                        if member_limit is not None and index.member_count >= member_limit:
                            index.truncated = True
                            return index
        return index

    @classmethod
    def load_from_root(cls, nx_root, member_limit=None, version_provider=None):
        """Build an index from the documentation files found under *nx_root*."""
        return cls.load(
            find_doc_files(nx_root),
            member_limit=member_limit,
            version_provider=version_provider,
        )

    def _leaf_map(self):
        if self._by_leaf is None:
            by_leaf = {}
            for full_name in self.members:
                leaf = full_name.rsplit(".", 1)[-1]
                by_leaf.setdefault(leaf, []).append(full_name)
            self._by_leaf = by_leaf
        return self._by_leaf

    def documented_on_other_type(self, member_name, limit=8):
        """Same-named members documented somewhere else, plus the total count.

        These are usually inherited members documented on a base type, but the
        index cannot prove the inheritance relationship, so the caller must
        treat the result as a lead rather than as confirmation.

        Ordering is a heuristic only: base classes are usually declared higher
        in the hierarchy and so have shallower dotted names, which places
        ``NXOpen.Builder.Commit`` ahead of
        ``NXOpen.Assemblies.SubsetConfigurationBuilder.Commit``. The heuristic
        is not reliable -- for ``Save`` it surfaces ``NXOpen.WCS.Save`` before
        ``NXOpen.BasePart.Save`` -- so the full candidate list is returned and
        the caller sees how many were found.
        """
        candidates = self._leaf_map().get(member_name, [])
        if not candidates:
            return [], 0
        ranked = sorted(
            set(candidates),
            key=lambda full: (
                full.count("."),
                len(full),
                full,
            ),
        )
        return ranked[:limit], len(ranked)

    def lookup(self, dotted):
        """Resolve a dotted API path such as ``NXOpen.Session.SetUndoMark``.

        The returned status says exactly how far resolution got. Callers must
        not read more into the answer than the status supports.
        """
        result = {
            "query": dotted,
            "status": STATUS_EMPTY,
            "declaringType": None,
            "member": None,
            "overloads": [],
            "declaredOn": [],
            "declaredOnCount": 0,
            # Every XML file in the index...
            "sources": list(self.xml_paths),
            # ...versus the files that actually recorded the entry this query
            # resolved to. Empty when the query did not resolve to an entry.
            "matchedSources": [],
            "truncated": self.truncated,
        }
        if not dotted or not dotted.strip():
            return result

        candidate = dotted.strip()
        parts = candidate.split(".")

        # Longest type prefix wins, so NXOpen.Features.ExtrudeBuilder.Commit
        # resolves against the builder type rather than the NXOpen.Features
        # namespace.
        for split in range(len(parts) - 1, 0, -1):
            type_name = ".".join(parts[:split])
            if type_name not in self.types:
                continue
            member_name = ".".join(parts[split:])
            full_name = type_name + "." + member_name
            result["declaringType"] = type_name
            result["member"] = member_name
            if full_name in self.members:
                result["status"] = STATUS_MEMBER
                result["overloads"] = sorted(set(self.members[full_name]))
                result["declaredOn"] = [full_name]
                result["matchedSources"] = self.sources_of(full_name)
            else:
                elsewhere, total = self.documented_on_other_type(member_name)
                result["status"] = (
                    STATUS_ELSEWHERE if elsewhere else STATUS_MEMBER_UNDOCUMENTED
                )
                result["declaredOn"] = elsewhere
                result["declaredOnCount"] = total
            return result

        if candidate in self.types:
            result["status"] = STATUS_TYPE
            result["declaringType"] = candidate
            result["declaredOn"] = [candidate]
            result["declaredOnCount"] = 1
            result["matchedSources"] = self.sources_of(candidate)
            return result

        leaf = parts[-1]
        elsewhere, total = self.documented_on_other_type(leaf)
        result["status"] = (
            STATUS_ELSEWHERE if elsewhere else STATUS_TYPE_UNDOCUMENTED
        )
        result["declaredOn"] = elsewhere
        result["declaredOnCount"] = total
        result["member"] = leaf
        return result

    def summary(self):
        version = self.assembly_version()
        return {
            "xmlPaths": list(self.xml_paths),
            "assemblyPath": self.assembly_path,
            "assemblyVersion": version,
            # An unreadable version is reported as such. Treating it as a match
            # would let an unknown index pass as an NX 12 source.
            "assemblyVersionState": (
                "unknown" if version is None else "read"
            ),
            "assemblyMajor": major_version(version),
            "typeCount": len(self.types),
            "memberCount": self.member_count,
            "truncated": self.truncated,
        }
