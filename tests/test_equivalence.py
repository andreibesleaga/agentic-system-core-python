"""The proof: both checkers, the same inputs, the same verdicts.

The Node tool is run through a subprocess, and only here.  When Node or the
engine checkout is not on this machine the whole module is skipped with a
message that says so, because a silent skip would look like a pass.

Nothing in this module touches the network: every input is a file on disk.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import ENGINE, SITE_DOCUMENTS, WELLKNOWN, engine_available

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
