"""The diagnostics envelope of AGSC-09-11 and the finding it carries.

Every checker in this package emits exactly this object under ``--json``:

    {"counts": {"error": n, "warn": m}, "findings": [...],
     "schema": "agsc.diagnostics.v1", "spec_version": ..., "status": "pass"|"fail",
     "verb": ..., "version": ...}

A finding carries ``code``, ``col``, ``file``, ``line``, ``message`` and
``severity`` and nothing else.  Findings are ordered by file, line, column,
code and message, compared by UTF-16 code unit, so that two runs of two
implementations produce the same list in the same order (AGSC-09-10).

Exit codes: 0 pass, 1 fail, 2 usage.
"""

import functools

from . import SPEC_VERSION, __version__
from .jcs import compare_utf16

#: The envelope's schema identifier.
SCHEMA = "agsc.diagnostics.v1"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def finding(code, file, message, severity="error", line=1, col=1):
    """One finding of the envelope."""
    return {
        "code": code,
        "col": col,
        "file": file,
        "line": line,
        "message": message,
        "severity": severity,
    }


def _order(left, right):
    return (
        compare_utf16(left["file"], right["file"])
        or (left["line"] > right["line"]) - (left["line"] < right["line"])
        or (left["col"] > right["col"]) - (left["col"] < right["col"])
        or compare_utf16(left["code"], right["code"])
        or compare_utf16(left["message"], right["message"])
    )


def sort_findings(findings):
    """AGSC-09-10 order: file, line, column, code, message."""
    return sorted(findings, key=functools.cmp_to_key(_order))


def envelope(findings, verb, spec_version=SPEC_VERSION, version=__version__):
    """Build the AGSC-09-11 envelope over a list of findings."""
    ordered = sort_findings(findings)
    errors = sum(1 for one in ordered if one["severity"] == "error")
    return {
        "counts": {"error": errors, "warn": len(ordered) - errors},
        "findings": ordered,
        "schema": SCHEMA,
        "spec_version": spec_version,
        "status": "fail" if errors else "pass",
        "verb": verb,
        "version": version,
    }


def exit_code(envelope_object):
    """0 when the envelope passes, 1 when it fails."""
    return EXIT_PASS if envelope_object["status"] == "pass" else EXIT_FAIL
