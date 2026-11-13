"""Parity as a property: on generated Link graphs, this package and the engine agree.

For each of a fixed set of item sets drawn from a seeded generator (no clock, no
randomness between runs), the engine's ``links.resolve``, ``derive.readings`` and
``questions.answer`` run in one Node process, and the result must equal this
package's ``links.link_warnings``, ``derive.readings`` and ``questions.answer``: the
warnings AGSC-E313 to AGSC-E316, every reading of AGSC-05-33 with its reasons, and the
answer to each of the ten questions of AGSC-05-34. Skipped, with the reason, when Node
or the engine checkout is not here. No network.
"""

import json
import random
import subprocess

import pytest

from agentic_system_core import derive, links, questions, relations
from conftest import ENGINE, engine_available

pytestmark = pytest.mark.skipif(
    not (engine_available() and (ENGINE / "src" / "knowledge" / "derive.js").is_file()),
    reason="the link parity property needs Node and a 1.1 engine checkout beside this one",
)

SEED = 20261108
CASES = 120
TYPES = ("concept", "concept", "concept", "lesson", "episode", "procedure", "gate", "cluster")
KINDS = (None, "principle", "task", "spec", "pattern", "decision", "architecture")
STATUSES = (None, None, "stable", "draft", "deprecated", "retired")
WARNINGS = ("AGSC-E313", "AGSC-E314", "AGSC-E315", "AGSC-E316")
AT = "2026-10-29T00:00:00Z"

_SCRIPT = r"""
const path = require('node:path');
const ROOT = process.argv[1];
const links = require(path.join(ROOT, 'src/knowledge/links.js'));
const derive = require(path.join(ROOT, 'src/knowledge/derive.js'));
const questions = require(path.join(ROOT, 'src/knowledge/questions.js'));
const WARN = new Set(JSON.parse(process.argv[2]));
const cases = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const out = cases.map(({ items, subject, selection, at }) => {
  const resolved = links.resolve(items);
  return {
    warnings: resolved.findings.filter((f) => WARN.has(f.code)).map((f) => [f.slug, f.code]),
    readings: derive.readings(resolved.edges),
    answers: Array.from({ length: 10 }, (_, i) => questions.answer(i + 1, items, { subject, selection, at })),
  };
});
process.stdout.write(JSON.stringify(out));
"""


def _item(rng, slug, slugs):
    item = {"slug": slug, "type": rng.choice(TYPES)}
    for name, choices in (("kind", KINDS), ("status", STATUSES)):
        value = rng.choice(choices)
        if value is not None:
            item[name] = value
    for key in rng.sample(relations.KEYS, rng.randint(0, 3)):
        item[key] = sorted(set(rng.choice(slugs) for _ in range(rng.randint(1, 2))))
    if rng.random() < 0.3:
        item["clusters"] = [rng.choice(slugs)]
    if rng.random() < 0.3:
        item["sources"] = [{"resource": "https://example.org/%d" % rng.randint(1, 3)}]
    if rng.random() < 0.3:
        item["produces"] = ["port-%d" % rng.randint(1, 3)]
        item["consumes"] = ["port-%d" % rng.randint(1, 3)]
    if rng.random() < 0.2:
        item["stale_after"] = rng.choice(("2026-01-01", "2027-01-01", "2026-10-29T00:00:00Z"))
    return item


def generated_cases():
    rng = random.Random(SEED)
    cases = []
    for _ in range(CASES):
        slugs = ["s%d" % index for index in range(rng.randint(1, 7))]
        items = [_item(rng, slug, slugs) for slug in slugs]
        cases.append({"at": AT, "items": items, "selection": slugs, "subject": slugs[0]})
    return cases


def _ours(case):
    edges, _ = links.edges(case["items"])
    found = sorted([one["slug"], one["code"]] for one in links.link_warnings(case["items"]))
    return {
        "warnings": found,
        "readings": derive.readings(edges),
        "answers": [questions.answer(number, case["items"], subject=case["subject"],
                                     selection=case["selection"], at=case["at"])
                    for number in range(1, 11)],
    }


def test_the_generator_is_fixed():
    assert generated_cases() == generated_cases()


def test_both_implementations_agree_on_every_generated_graph():
    cases = generated_cases()
    done = subprocess.run(["node", "-e", _SCRIPT, str(ENGINE), json.dumps(WARNINGS)],
                          input=json.dumps(cases), capture_output=True, text=True,
                          cwd=str(ENGINE))
    assert done.returncode == 0, done.stderr[-2000:]
    theirs = json.loads(done.stdout)
    disagreements = []
    for index, (case, engine) in enumerate(zip(cases, theirs)):
        engine["warnings"] = sorted(engine["warnings"])
        mine = _ours(case)
        for part in ("warnings", "readings", "answers"):
            if mine[part] != engine[part]:
                disagreements.append((index, part))
    assert disagreements == []
    assert len(theirs) == CASES
