"""The conformance-vector checker and the runner for the areas this package covers.

Two things live here.

**The file-format check** is the Python twin of the engine's validate-vectors: it
reads every vector file of a directory and checks it against AGSC-09-04 (the
required members, the closed list of twenty-five areas, the identifier
grammars), AGSC-09-05 (the levels and the withdrawal rule) and AGSC-09-06 (the
encoding and the JCS member order), and resolves every rule identifier and every
error code against the specification.  An empty vector set is a failure, not a
clean run: a checker that reports a pass over zero files protects nothing.

Resolving rule identifiers needs the specification.  This package ships a small
index of it — the rule identifiers, the registered error codes and the declared
version, derived from ``spec/`` by command — and ``--spec <dir>`` derives the
same index from a live ``spec/`` directory instead.

**The runner** executes the vectors of the areas this package implements
natively and reports every other area as not run, by name, with the reason;
a vector of a run area whose input needs a whole Bundle build is reported as
not run the same way, under ``vectors_not_run``.  It
never reports a pass for something it did not execute.  The pending list is the
engine's: a file ``{"pending": [ids], "reason": {id: text}}`` whose entries are
skipped with their reason.

Standard library only.
"""

import json
import os
import re
import unicodedata

from . import SPEC_VERSION, __version__
from .areas import AREA_RUNNERS, NOT_RUN_REASONS
from .diagnostics import EXIT_FAIL, EXIT_PASS, envelope, finding
from .jcs import canonicalize, nfc, utf16_key

VALIDATE_VERB = "validate-vectors"
RUN_VERB = "run-vectors"

#: AGSC-09-04: the closed list of twenty-five areas, and no others.
AREAS = (
    "frontmatter", "slug", "links", "jcs", "graph", "lint", "cli", "bundle", "prov",
    "ledger", "compose", "build", "discovery", "adopt", "import", "export", "skills",
    "adapters", "channels", "harness", "run", "conform", "boundary", "chunks", "boards",
)
#: AGSC-09-04: every vector carries these members.
REQUIRED_MEMBERS = ("area", "description", "expected", "id", "input", "level", "rule")
#: AGSC-09-05: the three levels.
LEVELS = ("required", "optional", "withdrawn")
#: AGSC-09-06: the two files whose non-NFC input is the subject of the case.
NFC_EXEMPT = ("jcs-0005", "lint-0022")

#: AGSC-10-02 to AGSC-10-05: which areas a claim at each Level runs.
LEVEL_AREAS = {
    0: ("frontmatter", "slug", "bundle", "discovery"),
    1: ("frontmatter", "slug", "bundle", "jcs", "discovery", "links", "lint"),
    2: ("frontmatter", "slug", "bundle", "jcs", "discovery", "links", "lint", "graph",
        "build", "adopt", "ledger", "import", "export", "skills", "chunks", "boards", "boundary"),
    3: AREAS,
}

#: AGSC-10-15 (amended for 1.0.0): the cases of a Level's areas that exercise a higher
#: Level's behaviour, each with the Level it belongs to; a claim at a lower Level neither
#: runs them nor fails for them. The engine and the specification carry the same table.
HIGHER_LEVEL_CASES = {
    "bundle-0001": 1, "bundle-0006": 1, "bundle-0007": 1, "disc-0005": 1, "disc-0019": 1,
    "bundle-0008": 2, "disc-0009": 2, "disc-0012": 2, "disc-0015": 2, "disc-0016": 2,
    "disc-0017": 2, "disc-0018": 2, "disc-0020": 2, "disc-0021": 2, "lint-0026": 2,
    "bundle-0003": 3, "bundle-0004": 3, "bundle-0005": 3,
    "lint-0001": 3, "lint-0002": 3, "lint-0003": 3, "lint-0028": 3, "lint-0029": 3,
    "lint-0032": 3, "lint-0033": 3,
    "adopt-0007": 3, "adopt-0008": 3, "adopt-0009": 3,
}

_ID = re.compile(r"^[a-z]+-\d{4}$")
_RULE = re.compile(r"^AGSC-\d{2}-\d{2,3}[a-z]?$")
_CODE = re.compile(r"AGSC-E\d{3}")

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "spec-index.json")


def bundled_spec_index():
    """The rule identifiers, error codes and version this package ships."""
    with open(_DATA, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def spec_index_from(directory):
    """Derive the same index from a live ``spec/`` directory."""
    names = sorted(name for name in os.listdir(directory) if name.endswith(".md"))
    parts = []
    for name in names:
        with open(os.path.join(directory, name), "rb") as handle:
            parts.append(handle.read().decode("utf-8"))
    text = "\n".join(parts)
    rules = sorted({one[2:-2] for one in re.findall(r"\*\*AGSC-\d{2}-\d{2,3}[a-z]?\*\*", text)})
    conformance_path = os.path.join(directory, "09-conformance.md")
    with open(conformance_path, "rb") as handle:
        conformance = handle.read().decode("utf-8")
    codes = sorted({_CODE.search(row).group(0)
                    for row in re.findall(r"^\| `AGSC-E\d{3}`", conformance, re.M)})
    overview_path = os.path.join(directory, "00-overview.md")
    with open(overview_path, "rb") as handle:
        overview = handle.read().decode("utf-8")
    match = re.search(r"1\.0\.0-rc\.\d+", overview)
    return {
        "error_codes": codes,
        "rule_ids": rules,
        "spec_version": match.group(0) if match else "unknown",
    }


def _walk(directory):
    out = []
    for root, directories, names in os.walk(directory):
        directories.sort()
        for name in sorted(names):
            if name.endswith(".json"):
                out.append(os.path.join(root, name))
    return sorted(out)


def _relative(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")


def _order_faults(node, pointer, out):
    """Every object in the tree whose member order is not JCS order (AGSC-09-06)."""
    if isinstance(node, list):
        for index, item in enumerate(node):
            _order_faults(item, "%s/%d" % (pointer, index), out)
        return
    if not isinstance(node, dict):
        return
    names = list(node.keys())
    if names != sorted((nfc(name) for name in names), key=utf16_key):
        out.append(pointer if pointer else "/")
    for key in names:
        # AGSC-09-06 exemption: input.value carries the order that IS the case.
        if pointer == "/input" and key == "value":
            continue
        _order_faults(node[key], "%s/%s" % (pointer, key), out)


def _collect_codes(node, out):
    if isinstance(node, str):
        out.update(_CODE.findall(node))
        return
    if isinstance(node, list):
        for item in node:
            _collect_codes(item, out)
        return
    if isinstance(node, dict):
        for key in node:
            _collect_codes(key, out)
            _collect_codes(node[key], out)


def validate(directory, spec=None, root=None):
    """Check a vector set.  Returns (envelope, file count, areas with no file)."""
    index = spec_index_from(spec) if spec else bundled_spec_index()
    rule_ids = set(index["rule_ids"])
    registered = set(index["error_codes"])
    declared = index["spec_version"]
    directory = os.path.abspath(directory)
    if root is None:
        marker = os.path.join("tests", "vectors")
        root = directory[:-len(marker)].rstrip(os.sep) if directory.endswith(marker) \
            else os.path.dirname(directory)
    root = os.path.abspath(root)

    findings = []
    files = _walk(directory)
    if not files:
        findings.append(finding(
            "AGSC-E901", _relative(directory, root),
            "no vector file under %s: there is nothing to validate (AGSC-09-90)" % directory))
    if not rule_ids:
        findings.append(finding(
            "AGSC-E901", "spec/",
            "spec/ declares no rule, so every rule-id resolution below is vacuous (AGSC-09-91)"))

    seen = {}
    present = set()
    for absolute in files:
        name = _relative(absolute, root)
        with open(absolute, "rb") as handle:
            data = handle.read()
        raw = data.decode("utf-8", "replace")
        if raw[:1] == "﻿":
            findings.append(finding("AGSC-E108", name, "byte-order mark (AGSC-09-06)"))
        if "\r" in raw:
            findings.append(finding("AGSC-E108", name, "CR or CRLF line endings (AGSC-09-06)"))
        if not raw.endswith("\n") or raw.endswith("\n\n"):
            findings.append(finding(
                "AGSC-E108", name, "the file must end with exactly one LF (AGSC-09-06)"))
        try:
            vector = json.loads(raw)
        except ValueError as error:
            findings.append(finding("AGSC-E201", name, "not valid JSON: %s" % error))
            continue
        identifier = vector.get("id") if isinstance(vector.get("id"), str) else "(no id)"
        if unicodedata.normalize("NFC", raw) != raw and identifier not in NFC_EXEMPT:
            findings.append(finding(
                "AGSC-E108", name,
                "the file is not NFC and is not one of the AGSC-09-06 exemptions"))
        for member in REQUIRED_MEMBERS:
            if member not in vector:
                findings.append(finding(
                    "AGSC-E202", name,
                    'required member "%s" is missing (AGSC-09-04)' % member))
        if isinstance(vector.get("id"), str):
            if _ID.match(vector["id"]) is None:
                findings.append(finding(
                    "AGSC-E204", name,
                    'id "%s" is not <area-prefix>-<nnnn> (AGSC-09-04)' % vector["id"]))
            if vector["id"] in seen:
                findings.append(finding(
                    "AGSC-E201", name,
                    'duplicate id "%s", first seen in %s' % (vector["id"], seen[vector["id"]])))
            else:
                seen[vector["id"]] = name
        if isinstance(vector.get("area"), str):
            present.add(vector["area"])
            if vector["area"] not in AREAS:
                findings.append(finding(
                    "AGSC-E203", name,
                    'area "%s" is outside the closed list of %d (AGSC-09-04)'
                    % (vector["area"], len(AREAS))))
            folder = name.split("/")[-2] if "/" in name else ""
            if folder != vector["area"]:
                findings.append(finding(
                    "AGSC-E205", name,
                    'area "%s" disagrees with the folder "%s" (AGSC-09-04)'
                    % (vector["area"], folder)))
        if isinstance(vector.get("level"), str) and vector["level"] not in LEVELS:
            findings.append(finding(
                "AGSC-E203", name,
                'level "%s" is not required|optional|withdrawn (AGSC-09-05)' % vector["level"]))
        if isinstance(vector.get("rule"), str):
            if _RULE.match(vector["rule"]) is None:
                findings.append(finding(
                    "AGSC-E204", name,
                    'rule "%s" is not an AGSC-nn-nn id (AGSC-09-05)' % vector["rule"]))
            elif vector["rule"] not in rule_ids:
                findings.append(finding(
                    "AGSC-E201", name,
                    'rule "%s" is defined nowhere in spec/ (AGSC-09-05)' % vector["rule"]))
        if vector.get("level") == "withdrawn":
            if not isinstance(vector.get("reason"), str) or vector["reason"] == "":
                findings.append(finding(
                    "AGSC-E202", name,
                    "a withdrawn vector MUST carry `reason` (AGSC-09-05)"))
            if canonicalize(vector.get("expected")) != '{"withdrawn":true}':
                findings.append(finding(
                    "AGSC-E201", name,
                    "a withdrawn vector's `expected` MUST be reduced to {\"withdrawn\": true} "
                    "(AGSC-09-05)"))
        options = vector.get("options")
        if isinstance(options, dict) and options.get("spec_version") is not None \
                and options["spec_version"] != declared:
            findings.append(finding(
                "AGSC-E201", name,
                'options.spec_version "%s" differs from the spec/00 declaration "%s" '
                "(AGSC-09-91)" % (options["spec_version"], declared)))
        order = []
        _order_faults(vector, "", order)
        for pointer in order:
            findings.append(finding(
                "AGSC-E601", name,
                "object members at %s are not in JCS order (AGSC-09-06)" % pointer))
        codes = set()
        _collect_codes(vector.get("expected"), codes)
        for code in sorted(codes):
            if code not in registered:
                findings.append(finding(
                    "AGSC-E203", name,
                    "error code %s is not registered in spec/09 section 9.4 (AGSC-09-15)" % code))

    empty = [area for area in AREAS if area not in present]
    return envelope(findings, VALIDATE_VERB, spec_version=declared), len(files), empty


def load_pending(path):
    """Read the engine's pending list: {"pending": [ids], "reason": {id: text}}."""
    if path is None or not os.path.isfile(path):
        return set(), {}
    with open(path, "rb") as handle:
        raw = json.loads(handle.read().decode("utf-8"))
    return set(raw.get("pending") or []), dict(raw.get("reason") or {})


def default_pending_path(directory):
    """The engine keeps its list at tests/conformance/pending.json beside the vectors."""
    parent = os.path.dirname(os.path.abspath(directory))
    return os.path.join(parent, "conformance", "pending.json")


def load_vectors(directory):
    """Every vector under the directory, ordered by identifier."""
    out = []
    for absolute in _walk(directory):
        with open(absolute, "rb") as handle:
            vector = json.loads(handle.read().decode("utf-8"))
        vector["__file"] = absolute
        out.append(vector)
    return sorted(out, key=lambda one: str(one.get("id")))


def run_one(vector, pending, reason, surfaces):
    """Classify and, where this package implements the area, execute one vector."""
    if vector.get("level") == "withdrawn":
        return {"status": "skip", "withdrawn": True, "detail": "withdrawn (AGSC-00-16)"}
    if vector.get("id") in pending:
        return {"status": "skip", "pending": True,
                "detail": reason.get(vector.get("id"), "pending")}
    requires = vector.get("requires_surface")
    if isinstance(requires, list) and not any(one in surfaces for one in requires):
        return {"status": "pass", "detail": "skipped as passed: surface not declared (AGSC-09-04)"}
    runner = AREA_RUNNERS.get(vector.get("area"))
    if runner is None:
        return {"status": "not-run",
                "detail": NOT_RUN_REASONS.get(
                    vector.get("area"),
                    "area %s is not implemented by this package" % vector.get("area"))}
    try:
        return runner(vector)
    except Exception as error:  # the handler itself is a fault, never a silent pass
        return {"status": "fail", "detail": "handler raised: %s" % error}


def run(directory, level=None, pending_path=None, surfaces=("mcp", "webmcp")):
    """Run the vector set.  Returns a plain report object and the exit code."""
    areas = set(LEVEL_AREAS[level]) if level is not None else None
    pending, reason = load_pending(
        pending_path if pending_path is not None else default_pending_path(directory))
    vectors = [one for one in load_vectors(directory)
               if areas is None or (one.get("area") in areas
                                    and HIGHER_LEVEL_CASES.get(one.get("id"), 0) <= level)]
    tally = {"fail": 0, "not_run": 0, "pass": 0, "pending": 0, "skip": 0, "withdrawn": 0}
    results = []
    not_run_areas = {}
    not_run_vectors = {}
    for vector in vectors:
        outcome = run_one(vector, pending, reason, surfaces)
        status = outcome["status"]
        if status == "pass":
            tally["pass"] += 1
        elif status == "skip":
            tally["skip"] += 1
            if outcome.get("withdrawn"):
                tally["withdrawn"] += 1
            else:
                tally["pending"] += 1
        elif status == "not-run":
            tally["not_run"] += 1
            if vector.get("area") in AREA_RUNNERS:
                not_run_vectors[vector.get("id")] = outcome["detail"]
            else:
                not_run_areas[vector.get("area")] = outcome["detail"]
        else:
            tally["fail"] += 1
        results.append({
            "area": vector.get("area"),
            "detail": outcome.get("detail", ""),
            "id": vector.get("id"),
            "rule": vector.get("rule"),
            "status": status,
        })
    report = {
        "areas_not_run": dict(sorted(not_run_areas.items())),
        "areas_run": sorted(AREA_RUNNERS),
        "level": level,
        "results": results,
        "schema": "agsc.vector-run.v1",
        "spec_version": SPEC_VERSION,
        "status": "fail" if tally["fail"] else "pass",
        "summary": summary_line(tally, len(vectors)),
        "tally": tally,
        "total": len(vectors),
        "vectors_not_run": dict(sorted(not_run_vectors.items())),
        "verb": RUN_VERB,
        "version": __version__,
    }
    return report, (EXIT_FAIL if tally["fail"] else EXIT_PASS)


def summary_line(tally, total):
    """One line, in the engine's shape, with the areas this package did not run."""
    return ("vectors: %d pass, %d fail, %d skip (%d withdrawn, %d pending), "
            "%d not run by this package, of %d"
            % (tally["pass"], tally["fail"], tally["skip"], tally["withdrawn"],
               tally["pending"], tally["not_run"], total))
