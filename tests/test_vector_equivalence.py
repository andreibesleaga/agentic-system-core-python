"""The second proof: this package's vector runner and the engine's agree, vector
by vector, on every area this package runs.

The engine's own runner (``src/application/conformance.js`` with the area
handlers under ``tests/conformance/areas``) is driven through one Node
subprocess over the engine's live vector set, and each vector's status is
compared with this package's.  Skipped, with the reason, when Node or the
engine checkout is not here.  No network.
"""

import json
import subprocess

import pytest

from agentic_system_core import vectors
from agentic_system_core.areas import AREA_RUNNERS
from conftest import ENGINE, engine_available

pytestmark = pytest.mark.skipif(
    not (engine_available() and (ENGINE / "src" / "application" / "conformance.js").is_file()),
    reason="the vector equivalence proof needs Node and the engine checkout beside this one",
)

_SCRIPT = r"""
const path = require('node:path');
const fs = require('node:fs');
const ROOT = process.argv[1];
const conformance = require(path.join(ROOT, 'src/application/conformance.js'));
const nodeFs = require(path.join(ROOT, 'src/adapters/node-fs.js'));
const validate = require(path.join(ROOT, 'src/knowledge/validate.js'));
const AREAS = path.join(ROOT, 'tests/conformance/areas');
const cache = new Map();
function handlerFor(area) {
  if (!cache.has(area)) {
    const file = path.join(AREAS, area + '.js');
    cache.set(area, fs.existsSync(file) ? require(file) : null);
  }
  return cache.get(area);
}
const overview = fs.readFileSync(path.join(ROOT, 'spec/00-overview.md'), 'utf8');
const schemas = nodeFs.readSchemas(ROOT);
const ctx = { root: ROOT, schemas: validate.schemas(schemas), itemSchema: schemas.item,
  specVersion: (/spec_version: "([^"]+)"/u.exec(overview) || [0, 'unknown'])[1],
  surfaces: conformance.DECLARED_SURFACES };
const raw = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests/conformance/pending.json'), 'utf8'));
const { results } = conformance.runAll(conformance.vectors(nodeFs.createFileSystem(ROOT)),
  { ctx, handlerFor, pending: new Set(raw.pending || []), reason: raw.reason || {} });
process.stdout.write(JSON.stringify({ specVersion: ctx.specVersion,
  results: results.map((r) => [r.id, r.area, r.status]) }));
"""


def _node_run():
    """The engine's runner over its live vector set: the version it ran under and
    one (id, area, status) per vector."""
    done = subprocess.run(["node", "-e", _SCRIPT, str(ENGINE)], capture_output=True,
                          text=True, cwd=str(ENGINE))
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def _node_statuses():
    return dict((identifier, (area, status))
                for identifier, area, status in _node_run()["results"])


def test_the_engine_side_of_the_proof_runs_at_the_version_this_package_indexes():
    # The engine's area handlers read the version they run under from the context the
    # runner is given; the proof holds only when that version is the one this package
    # indexes, a release as much as a candidate.
    assert _node_run()["specVersion"] == vectors.bundled_spec_index()["spec_version"]


def test_both_runners_agree_on_every_vector_of_every_area_this_package_runs():
    theirs = _node_statuses()
    report, _ = vectors.run(str(ENGINE / "tests" / "vectors"))
    compared = 0
    disagreements = []
    for result in report["results"]:
        if result["area"] not in AREA_RUNNERS or result["status"] == "not-run":
            continue
        compared += 1
        area, status = theirs[result["id"]]
        if status != result["status"]:
            disagreements.append((result["id"], status, result["status"], result["detail"]))
    assert disagreements == []
    assert compared > 0
    assert report["tally"]["fail"] == 0
