"""The proof: both checkers, the same inputs, the same verdicts.

The Node tool is run through a subprocess, and only here.  When Node or the
engine checkout is not on this machine the whole module is skipped with a
message that says so, because a silent skip would look like a pass.

The inputs are every fixture case, the built discovery files of the two sites
when their checkouts are here, and two nodes the engine builds for the run: its
own minimal fixture and, when its checkout is beside this one, the demonstration
node ``agsc-demo-node`` (with its git history, so the build writes the ledger and
the 1.1 chunk and ledger facts the checkers recompute).

Nothing in this module touches the network: every input is a file on disk.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import ENGINE, NEIGHBOURS, SITE_DOCUMENTS, WELLKNOWN, engine_available

pytestmark = pytest.mark.skipif(
    not engine_available(),
    reason="the equivalence proof needs Node and the engine checkout beside this one",
)

NODE_TOOL = str(ENGINE / "tools" / "validate-wellknown")
PACKAGE_SRC = str((WELLKNOWN.parent.parent.parent / "src").resolve())

def _shape(text):
    """Status, counts and the position and code of every finding.

    Message text is deliberately left out: the specification says a message is
    unspecified so that it can be localised, and pins the code.
    """
    if not text.strip():
        return None
    envelope = json.loads(text)
    return {
        "counts": envelope["counts"],
        "findings": sorted((one["file"], one["line"], one["col"], one["code"], one["severity"])
                           for one in envelope["findings"]),
        "status": envelope["status"],
    }


def node(args):
    done = subprocess.run(["node", NODE_TOOL] + args, capture_output=True, text=True,
                          cwd=str(ENGINE))
    return done.returncode, _shape(done.stdout)


def python(args):
    environment = dict(os.environ, PYTHONPATH=PACKAGE_SRC)
    done = subprocess.run(
        [sys.executable, "-m", "agentic_system_core.cli", "validate-wellknown"] + args,
        capture_output=True, text=True, env=environment, cwd=str(ENGINE))
    return done.returncode, _shape(done.stdout)


def _documents():
    out = sorted(str(one) for one in WELLKNOWN.rglob("knowledge-linkset"))
    out += [str(one) for one in SITE_DOCUMENTS if one.is_file()]
    out.append(str(WELLKNOWN / "nowhere" / ".well-known" / "knowledge-linkset"))
    return out


def _argument_sets():
    cases = []
    for document in _documents():
        for level in ("0", "1", "2", "3"):
            cases.append([document, "--level", level, "--json"])
        cases.append([document, "--json", "--dev"])
        cases.append([document, "--level", "2", "--json", "--dev"])
    good = str(WELLKNOWN / "good" / ".well-known" / "knowledge-linkset")
    mutual = str(WELLKNOWN / "peer-mutual" / ".well-known" / "knowledge-linkset")
    apart = str(WELLKNOWN / "peer-not-mutual" / ".well-known" / "knowledge-linkset")
    broken = str(WELLKNOWN / "not-json" / ".well-known" / "knowledge-linkset")
    for first, second in ((good, mutual), (good, apart), (good, broken), (broken, good)):
        for level in ("0", "2"):
            cases.append([first, "--peer", second, "--level", level, "--json"])
    cases += [["--level", "9", "--json"], ["--bogus", "--json"],
              [good, good, "--json"], ["--json"]]
    return cases


ARGUMENT_SETS = _argument_sets()


def test_there_is_something_to_compare():
    # A proof over zero inputs proves nothing, so the count is asserted.
    assert len(ARGUMENT_SETS) >= 200
    assert len([one for one in _documents() if os.path.isfile(one)]) >= 40


@pytest.mark.parametrize("args", ARGUMENT_SETS, ids=lambda one: " ".join(
    part.split("/wellknown/")[-1] for part in one))
def test_both_checkers_agree(args):
    node_code, node_shape = node(args)
    python_code, python_shape = python(args)
    assert node_code == python_code
    assert node_shape == python_shape


@pytest.mark.parametrize("level", ["0", "1", "2", "3"])
def test_both_checkers_agree_when_the_card_target_is_a_directory(tmp_path, level):
    # A target path that names a directory is read as a target that is not served.
    copy = tmp_path / "card-served"
    shutil.copytree(str(WELLKNOWN / "card-served"), str(copy))
    card = copy / ".well-known" / "agent-card.json"
    card.unlink()
    card.mkdir()
    args = [str(copy / ".well-known" / "knowledge-linkset"), "--level", level, "--json"]
    python_code, python_shape = python(args)
    assert python_shape is not None
    assert (python_code, python_shape) == node(args)


#: The build instant of every node built here (docs/MAINTAINING.md, the reference builds).
SOURCE_DATE_EPOCH = "1767225600"
DEMO_NODE = NEIGHBOURS / "agsc-demo-node"


def _build(source, out, ignore=()):
    """Copy one Bundle and build it with the engine; the discovery file it wrote."""
    shutil.copytree(str(source), str(out), ignore=shutil.ignore_patterns(*ignore))
    # The engine refuses an AGSC_* variable it does not know (AGSC-01-37), this suite's
    # AGSC_ENGINE_DIR among them, and AGSC_DOI would change the bytes: the build sees
    # the search path, the home folder (git reads it) and the build instant only.
    environment = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
                   "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH}
    done = subprocess.run(["node", str(ENGINE / "bin" / "agsc.js"), "build"], cwd=str(out),
                          capture_output=True, text=True, env=environment)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return out / "www" / ".well-known" / "knowledge-linkset"


@pytest.fixture(scope="module")
def built_nodes(tmp_path_factory):
    root = tmp_path_factory.mktemp("built")
    nodes = {"minimal": _build(ENGINE / "tests" / "fixtures" / "minimal", root / "minimal")}
    if (DEMO_NODE / "agsc.config.json").is_file():
        nodes["agsc-demo-node"] = _build(DEMO_NODE, root / "agsc-demo-node", ("www", "dist"))
    return nodes


@pytest.mark.parametrize("node_name", ["minimal", "agsc-demo-node"])
@pytest.mark.parametrize("level", ["0", "1", "2", "3"])
def test_both_checkers_agree_on_a_node_the_engine_builds(built_nodes, node_name, level):
    if node_name not in built_nodes:
        pytest.skip("the demonstration node is not checked out beside this repository at %s"
                    % DEMO_NODE)
    args = [str(built_nodes[node_name]), "--level", level, "--json"]
    node_code, node_shape = node(args)
    python_code, python_shape = python(args)
    assert (node_code, node_shape) == (python_code, python_shape)
    assert node_shape is not None


@pytest.mark.parametrize("level", ["0", "2"])
def test_the_known_difference_when_a_digest_target_or_the_ledger_is_a_directory(
        built_nodes, tmp_path, level):
    # The one difference the README names: the engine reports Node's own error name
    # EISDIR, which is not a registered code, where this package reports AGSC-E901 (a
    # target not found on disk). Exit code, status and counts agree. This test fails once
    # the engine reports a registered code there; then the README note comes out.
    if "agsc-demo-node" not in built_nodes:
        pytest.skip("the demonstration node is not checked out beside this repository at %s"
                    % DEMO_NODE)
    site = tmp_path / "www"
    shutil.copytree(str(built_nodes["agsc-demo-node"].parent.parent), str(site))
    for name in ("llms.txt", "ledger.jsonl"):
        (site / name).unlink()
        (site / name).mkdir()
    args = [str(site / ".well-known" / "knowledge-linkset"), "--level", level, "--json"]
    node_code, node_shape = node(args)
    python_code, python_shape = python(args)
    assert node_code == python_code == 1
    assert (node_shape["status"], node_shape["counts"]) == \
        (python_shape["status"], python_shape["counts"])
    theirs = [one[3] for one in node_shape["findings"]]
    ours = [one[3] for one in python_shape["findings"]]
    assert theirs.count("EISDIR") == ours.count("AGSC-E901") == 3
    assert [code for code in theirs if code != "EISDIR"] == \
        [code for code in ours if code != "AGSC-E901"]
