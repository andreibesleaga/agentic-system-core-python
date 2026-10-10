"""The command line: the three native verbs, the version and the forwarding."""

import io
import os
import stat

import pytest

from agentic_system_core import cli
from agentic_system_core.jcs import parse_ijson
from conftest import VECTORS, case


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_version():
    code, out, _ = run(["--version"])
    assert code == 0
    assert "1.0.0rc7" in out and "1.0.0-rc.7" in out


def test_help_and_no_arguments():
    code, out, _ = run(["--help"])
    assert code == 0 and "validate-wellknown" in out
    code, out, _ = run([])
    assert code == 2 and "validate-wellknown" in out


def test_validate_wellknown_passes_and_prints_the_envelope():
    code, out, _ = run(["validate-wellknown", case("good"), "--json"])
    assert code == 0
    envelope = parse_ijson(out)
    assert envelope["status"] == "pass"
    assert envelope["schema"] == "agsc.diagnostics.v1"


def test_validate_wellknown_plain_output_names_what_it_read():
    code, out, err = run(["validate-wellknown", case("missing-digest"), "--level", "2"])
    assert code == 1
    assert "input file(s) read" in out
    assert "AGSC-E202" in err


def test_validate_wellknown_help():
    code, out, _ = run(["validate-wellknown", "--help"])
    assert code == 0 and "run-vectors" in out


@pytest.mark.parametrize("argv,code", [
    (["validate-wellknown"], "AGSC-E003"),
    (["validate-wellknown", "--level"], "AGSC-E003"),
    (["validate-wellknown", "x", "--level", "9"], "AGSC-E003"),
    (["validate-wellknown", "x", "--peer"], "AGSC-E003"),
    (["validate-wellknown", "x", "--bogus"], "AGSC-E002"),
    (["validate-wellknown", "x", "y"], "AGSC-E002"),
])
def test_validate_wellknown_usage_faults_exit_two(argv, code):
    status, out, err = run(argv)
    assert status == 2
    assert code in err
    status, out, err = run([argv[0], "--json"] + argv[1:])
    assert status == 2
    assert code in out


def test_validate_wellknown_peer_and_dev_flags():
    code, _, _ = run(["validate-wellknown", case("good"), "--peer", case("peer-mutual")])
    assert code == 0
    code, _, _ = run(["validate-wellknown", case("anchor-http"), "--dev"])
    assert code == 0


def test_validate_vectors():
    code, out, _ = run(["validate-vectors", str(VECTORS)])
    assert code == 0
    assert "92 input file(s) read" in out
    code, out, _ = run(["validate-vectors", str(VECTORS), "--json"])
    assert code == 0
    assert parse_ijson(out)["verb"] == "validate-vectors"
    code, out, _ = run(["validate-vectors", str(VECTORS), "--quiet"])
    assert code == 0 and out == ""


def test_validate_vectors_usage_faults():
    assert run(["validate-vectors"])[0] == 2
    assert run(["validate-vectors", "/no/such/dir"])[0] == 2
    assert run(["validate-vectors", "--bogus"])[0] == 2
    assert run(["validate-vectors", "--spec"])[0] == 2
    assert run(["validate-vectors", "--help"])[0] == 0


def test_validate_vectors_with_a_live_spec_directory(tmp_path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "00-overview.md").write_bytes(b"version 1.0.0-rc.7\n**AGSC-00-01** a rule.\n")
    (spec / "04-canonicalization.md").write_bytes(b"**AGSC-04-05** the canonical form.\n")
    (spec / "09-conformance.md").write_bytes(b"| `AGSC-E201` | a shape fault |\n")
    code, out, _ = run(["validate-vectors", str(VECTORS), "--spec", str(spec), "--json"])
    # The shipped vectors name rules this cut-down spec does not define, so the
    # run fails - which is the point: the resolution is real, not decorative.
    assert code == 1
    assert parse_ijson(out)["spec_version"] == "1.0.0-rc.7"


def test_validate_vectors_root_option(tmp_path):
    code, out, _ = run(["validate-vectors", str(VECTORS), "--root", str(VECTORS.parent)])
    assert code == 0


def test_run_vectors():
    code, out, _ = run(["run-vectors", str(VECTORS)])
    assert code == 0
    assert "77 pass" in out
    assert "not run by this package: build-0015" in out
    code, out, _ = run(["run-vectors", str(VECTORS), "--json"])
    assert parse_ijson(out)["areas_run"] == [
        "build", "discovery", "frontmatter", "graph", "jcs", "links", "slug"]
    code, out, _ = run(["run-vectors", str(VECTORS), "--level", "1"])
    assert code == 0


def test_run_vectors_names_the_areas_it_did_not_run(tmp_path):
    area = tmp_path / "lint"
    area.mkdir()
    (area / "lint-9001.json").write_bytes(
        b'{"area":"lint","description":"A fixture.","expected":{},"id":"lint-9001",'
        b'"input":{},"level":"required","rule":"AGSC-05-04"}\n')
    code, out, err = run(["run-vectors", str(tmp_path)])
    assert code == 0
    assert "not run by this package: lint" in out
    assert "not-run lint-9001" in err


def test_run_vectors_usage_faults(tmp_path):
    assert run(["run-vectors"])[0] == 2
    assert run(["run-vectors", "/no/such/dir"])[0] == 2
    assert run(["run-vectors", "--bogus"])[0] == 2
    assert run(["run-vectors", "--level", "9"])[0] == 2
    assert run(["run-vectors", "--pending"])[0] == 2
    assert run(["run-vectors", "--help"])[0] == 0
    pending = tmp_path / "pending.json"
    pending.write_bytes(b'{"pending":[],"reason":{}}')
    assert run(["run-vectors", str(VECTORS), "--pending", str(pending)])[0] == 0


def _make(directory, name, body):
    path = directory / name
    path.write_bytes(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_the_node_command_is_found_by_its_shebang(tmp_path):
    good = tmp_path / "npm"
    good.mkdir()
    _make(good, "agsc", b"#!/usr/bin/env node\nconsole.log('engine');\n")
    found = cli.find_node_cli(path_value=str(good), own=set())
    assert found == str(good / "agsc")


def test_this_packages_own_script_is_never_mistaken_for_the_engines(tmp_path):
    mine = tmp_path / "venv"
    mine.mkdir()
    script = _make(mine, "agsc", b"#!/usr/bin/python3\nimport sys\n")
    assert cli.find_node_cli(path_value=str(mine), own=set()) is None
    assert cli.find_node_cli(path_value=str(mine), own={os.path.realpath(str(script))}) is None


def test_a_windows_shim_is_recognised(tmp_path):
    shim = tmp_path / "npm"
    shim.mkdir()
    _make(shim, "agsc.cmd", b"@ECHO off\nnode  \"%~dp0\\agsc.js\" %*\n")
    assert cli.find_node_cli(path_value=str(shim), own=set()).endswith("agsc.cmd")


def test_an_unreadable_or_absent_candidate_is_ignored(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli.find_node_cli(path_value=str(empty), own=set()) is None
    assert cli.find_node_cli(path_value="", own=set()) is None
    assert cli.find_node_cli(path_value=str(tmp_path / "nowhere"), own=set()) is None
    assert not cli._looks_like_node(str(tmp_path / "nowhere" / "agsc"))


def test_an_unknown_verb_is_forwarded_verbatim():
    calls = []

    class Completed(object):
        returncode = 7

    def runner(argv):
        calls.append(argv)
        return Completed()

    err = io.StringIO()
    code = cli.forward(["build", "--json"], err, runner=runner, finder=lambda: "/opt/npm/agsc")
    assert code == 7
    assert calls == [["/opt/npm/agsc", "build", "--json"]]
    assert err.getvalue() == ""


def test_an_unknown_verb_without_the_engine_says_what_to_install():
    err = io.StringIO()
    code = cli.forward(["build"], err, finder=lambda: None)
    assert code == 2
    assert "agentic-system-core" in err.getvalue()
    assert "Node 22.13 or newer" in err.getvalue()


def test_the_node_floor_is_the_one_the_readme_and_the_engine_state():
    # The engine's package.json says "node": ">=22.13.0" and the README says Node 22.13;
    # the message the command prints must name the same floor.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "README.md"), encoding="utf-8") as handle:
        readme = " ".join(handle.read().split())
    assert cli.NODE_REQUIREMENT == "Node 22.13 or newer"
    assert "Node 22.13 or newer" in readme


def test_main_forwards_an_unknown_verb(monkeypatch):
    seen = {}

    def fake_forward(argv, err):
        seen["argv"] = argv
        return 3

    monkeypatch.setattr(cli, "forward", fake_forward)
    assert run(["compose", "--json"])[0] == 3
    assert seen["argv"] == ["compose", "--json"]


def test_own_paths_covers_the_running_script():
    assert isinstance(cli._own_paths(), set)


def test_allow_network_is_accepted_with_a_file_argument():
    code, _, _ = run(["validate-wellknown", case("good"), "--allow-network"])
    assert code == 0


def test_validate_vectors_prints_findings_in_plain_form(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    (area / "a.json").write_bytes(b'{"area":"jcs"}\n')
    code, out, err = run(["validate-vectors", str(tmp_path)])
    assert code == 1
    assert "AGSC-E202" in err
    assert "input file(s) read" in out
