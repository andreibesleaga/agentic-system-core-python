"""The ``agsc`` command.

Three verbs run here, in Python, with no Node and no network:

    agsc validate-wellknown <file> [--level 0|1|2|3] [--peer <file>] [--json] [--dev]
                                   [--allow-network]
    agsc validate-vectors [<dir>] [--json] [--quiet] [--spec <dir>] [--root <dir>]
    agsc run-vectors [<dir>] [--json] [--level 0|1|2|3] [--pending <file>]

``agsc --version`` prints the version.  Every other verb belongs to the engine:
if the Node package's ``agsc`` is on the PATH, the call is handed to it exactly
as it was typed and its exit code is returned; if it is not, the command stops
with one sentence saying what to install.

Exit codes are the specification's: 0 pass, 1 fail, 2 usage.

No shell is ever invoked: the forwarding call passes a list of arguments.
"""

import os
import subprocess
import sys

from . import SEMVER_VERSION, __version__
from .diagnostics import EXIT_PASS, EXIT_USAGE, envelope, exit_code, finding
from .jcs import canonicalize_raw
from .net import fetch

#: The npm package that carries the engine and every other verb.
NPM_PACKAGE = "agentic-system-core"
NODE_REQUIREMENT = "Node 22.12 or newer"

NATIVE_VERBS = ("validate-wellknown", "validate-vectors", "run-vectors")

USAGE = """agsc <verb> [options]

Runs natively, with no Node and no network:
  validate-wellknown <file> [--level 0|1|2|3] [--peer <file>] [--json] [--dev]
                            [--allow-network]
      Check one discovery document served at /.well-known/knowledge-linkset.
      A file is read always; a URL is read only with --allow-network.
  validate-vectors [<dir>] [--json] [--quiet] [--spec <dir>] [--root <dir>]
      Check a conformance-vector set against the file-format rules.
  run-vectors [<dir>] [--json] [--level 0|1|2|3] [--pending <file>]
      Run the vectors of the areas this package implements and name every area
      it does not run.

  --version   print the version
  --help      this text

Every other verb is handed to the Node package %s when its
agsc command is on the PATH.
""" % NPM_PACKAGE


def _write(stream, text):
    stream.write(text)


def _emit_envelope(result, as_json, out, err, tool_line):
    if as_json:
        _write(out, canonicalize_raw(result) + "\n")
    else:
        for one in result["findings"]:
            _write(err, "%s:%d:%d %s %s %s\n"
                   % (one["file"], one["line"], one["col"], one["severity"],
                      one["code"], one["message"]))
        _write(out, tool_line)
    return exit_code(result)


def _usage_envelope(code, message, as_json, out, err, verb):
    result = envelope([finding(code, "", message)], verb)
    if as_json:
        _write(out, canonicalize_raw(result) + "\n")
    else:
        _write(err, "%s %s\n" % (code, message))
    return EXIT_USAGE


def run_validate_wellknown(argv, out, err):
    """The discovery-file checker."""
    as_json = "--json" in argv
    options = {"dev": False, "level": 0, "peer": None, "target": None, "allow_network": False}
    index = 0
    while index < len(argv):
        argument = argv[index]
        index += 1
        if argument == "--json":
            continue
        if argument == "--dev":
            options["dev"] = True
        elif argument == "--allow-network":
            options["allow_network"] = True
        elif argument == "--level":
            value = argv[index] if index < len(argv) else None
            index += 1
            if value is None or value not in ("0", "1", "2", "3"):
                return _usage_envelope("AGSC-E003", "--level needs 0, 1, 2 or 3",
                                       as_json, out, err, "validate-wellknown")
            options["level"] = int(value)
        elif argument == "--peer":
            value = argv[index] if index < len(argv) else None
            index += 1
            if not value:
                return _usage_envelope("AGSC-E003", "--peer needs a url or file",
                                       as_json, out, err, "validate-wellknown")
            options["peer"] = value
        elif argument in ("-h", "--help"):
            _write(out, USAGE)
            return EXIT_PASS
        elif argument.startswith("-"):
            return _usage_envelope("AGSC-E002", "unknown flag %s" % argument,
                                   as_json, out, err, "validate-wellknown")
        elif options["target"] is None:
            options["target"] = argument
        else:
            return _usage_envelope("AGSC-E002", "unexpected argument %s" % argument,
                                   as_json, out, err, "validate-wellknown")
    if options["target"] is None:
        return _usage_envelope("AGSC-E003", "missing <file|url>",
                               as_json, out, err, "validate-wellknown")

    from .wellknown import validate
    result, reads = validate(
        options["target"], level=options["level"], peer=options["peer"],
        dev=options["dev"], allow_network=options["allow_network"], fetcher=fetch)
    line = ("validate-wellknown %s (level %d): %d input file(s) read, %d error(s), "
            "%d warning(s)\n" % (result["status"], options["level"], reads,
                                 result["counts"]["error"], result["counts"]["warn"]))
    return _emit_envelope(result, as_json, out, err, line)


def run_validate_vectors(argv, out, err):
    """The vector-set file-format checker."""
    from .vectors import validate
    as_json = "--json" in argv
    quiet = "--quiet" in argv
    directory = None
    spec = None
    root = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        index += 1
        if argument in ("--json", "--quiet", "--plain"):
            continue
        if argument in ("-h", "--help"):
            _write(out, USAGE)
            return EXIT_PASS
        if argument in ("--spec", "--root"):
            value = argv[index] if index < len(argv) else None
            index += 1
            if not value:
                _write(err, "validate-vectors: %s needs a directory (AGSC-E003)\n" % argument)
                return EXIT_USAGE
            if argument == "--spec":
                spec = value
            else:
                root = value
        elif argument.startswith("--"):
            _write(err, "validate-vectors: unknown flag %s (AGSC-E002)\n" % argument)
            return EXIT_USAGE
        else:
            directory = argument
    if directory is None:
        _write(err, "validate-vectors: a vector directory is required; this package ships no "
                    "vector set of its own (AGSC-E003)\n")
        return EXIT_USAGE
    if not os.path.isdir(directory):
        _write(err, "validate-vectors: no such directory: %s (AGSC-E901)\n" % directory)
        return EXIT_USAGE
    result, count, empty = validate(directory, spec=spec, root=root)
    if as_json:
        _write(out, canonicalize_raw(result) + "\n")
        for one in result["findings"]:
            _write(err, canonicalize_raw(one) + "\n")
    elif not quiet:
        for one in result["findings"]:
            _write(err, "%s: %s:%d:%d %s %s\n"
                   % (one["severity"], one["file"], one["line"], one["col"],
                      one["code"], one["message"]))
        _write(out, "validate-vectors: %d input file(s) read, %d vectors, %d error, %d warn; "
                    "declared areas with no vector file (informational, AGSC-09-90): %s\n"
                    % (count, count, result["counts"]["error"], result["counts"]["warn"],
                       " ".join(empty) if empty else "none"))
    return exit_code(result)


def run_run_vectors(argv, out, err):
    """The runner for the areas this package implements."""
    from .vectors import run
    as_json = "--json" in argv
    directory = None
    level = None
    pending = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        index += 1
        if argument == "--json":
            continue
        if argument in ("-h", "--help"):
            _write(out, USAGE)
            return EXIT_PASS
        if argument == "--level":
            value = argv[index] if index < len(argv) else None
            index += 1
            if value is None or value not in ("0", "1", "2", "3"):
                _write(err, "run-vectors: --level needs 0, 1, 2 or 3 (AGSC-E003)\n")
                return EXIT_USAGE
            level = int(value)
        elif argument == "--pending":
            value = argv[index] if index < len(argv) else None
            index += 1
            if not value:
                _write(err, "run-vectors: --pending needs a file (AGSC-E003)\n")
                return EXIT_USAGE
            pending = value
        elif argument.startswith("--"):
            _write(err, "run-vectors: unknown flag %s (AGSC-E002)\n" % argument)
            return EXIT_USAGE
        else:
            directory = argument
    if directory is None:
        _write(err, "run-vectors: a vector directory is required; this package ships no vector "
                    "set of its own (AGSC-E003)\n")
        return EXIT_USAGE
    if not os.path.isdir(directory):
        _write(err, "run-vectors: no such directory: %s (AGSC-E901)\n" % directory)
        return EXIT_USAGE
    report, code = run(directory, level=level, pending_path=pending)
    if as_json:
        _write(out, canonicalize_raw(report) + "\n")
    else:
        for one in report["results"]:
            if one["status"] in ("fail", "not-run"):
                _write(err, "%s %s %s: %s\n"
                       % (one["status"], one["id"], one["rule"], one["detail"]))
        _write(out, report["summary"] + "\n")
        if report["areas_not_run"]:
            for area in sorted(report["areas_not_run"]):
                _write(out, "not run by this package: %s -- %s\n"
                       % (area, report["areas_not_run"][area]))
        for identifier in sorted(report.get("vectors_not_run", {})):
            _write(out, "not run by this package: %s -- %s\n"
                   % (identifier, report["vectors_not_run"][identifier]))
    return code


def _own_paths():
    """Every path that could be this package's own console script."""
    paths = set()
    for candidate in (sys.argv[0] if sys.argv else None, os.environ.get("_")):
        if candidate:
            paths.add(os.path.realpath(candidate))
    return paths


def _looks_like_node(path):
    """True when the executable at ``path`` is started by Node."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(512)
    except OSError:
        return False
    if head.startswith(b"#!"):
        return b"node" in head.split(b"\n", 1)[0]
    return path.lower().endswith((".cmd", ".bat", ".ps1")) and b"node" in head


def find_node_cli(path_value=None, own=None):
    """The npm ``agsc`` on the PATH, or None.  Never this package's own script."""
    entries = (path_value if path_value is not None else os.environ.get("PATH", "")).split(os.pathsep)
    own = own if own is not None else _own_paths()
    for entry in entries:
        if not entry:
            continue
        for name in ("agsc", "agsc.cmd", "agsc.bat", "agsc.ps1", "agsc.exe"):
            candidate = os.path.join(entry, name)
            if not os.path.isfile(candidate) or not os.access(candidate, os.X_OK):
                continue
            if os.path.realpath(candidate) in own:
                continue
            if _looks_like_node(os.path.realpath(candidate)):
                return candidate
    return None


def forward(argv, err, runner=subprocess.run, finder=find_node_cli):
    """Hand a verb to the Node engine verbatim, or explain what to install."""
    node_cli = finder()
    if node_cli is None:
        _write(err,
               "This verb belongs to the engine: install the npm package %s "
               "(it needs %s) and run it again.\n" % (NPM_PACKAGE, NODE_REQUIREMENT))
        return EXIT_USAGE
    completed = runner([node_cli] + list(argv))
    return completed.returncode


def main(argv=None, out=None, err=None):
    """The console-script entry point.  Returns the process exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if not argv:
        _write(out, USAGE)
        return EXIT_USAGE
    verb = argv[0]
    if verb in ("--version", "-V", "version"):
        _write(out, "agsc %s (Python package; specification %s)\n" % (__version__, SEMVER_VERSION))
        return EXIT_PASS
    if verb in ("--help", "-h", "help"):
        _write(out, USAGE)
        return EXIT_PASS
    if verb == "validate-wellknown":
        return run_validate_wellknown(argv[1:], out, err)
    if verb == "validate-vectors":
        return run_validate_vectors(argv[1:], out, err)
    if verb == "run-vectors":
        return run_run_vectors(argv[1:], out, err)
    return forward(argv, err)


def console_main():  # pragma: no cover - the installed entry point
    sys.exit(main())


if __name__ == "__main__":  # pragma: no cover - module execution
    sys.exit(main())
