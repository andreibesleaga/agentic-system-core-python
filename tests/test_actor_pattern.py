"""The actor grammar of AGSC-02-09, as this checker applies it to an item.

The specification's ledger ends with a ``build`` entry whose actor is
``process:agsc/<version>`` (AGSC-08-20a), so the grammar admits a process actor
followed by ``/<version>``. The engine's item schema carries the same pattern; when
the engine is beside this repository, the two are compared on every case below.
"""

import json
import os
import re

import pytest

from agentic_system_core import frontmatter

PROV = {"origin": "human", "operator": "human:x"}
GOOD = ["human:ada", "process:ci", "process:agsc/1.0.0", "process:agsc/1.0.0-rc.7",
        "claude-code/1.0", "Tool/2.0+x"]
BAD = ["agent:x", "ada", "human:Ada", "human:", "/1.0", "process:", "process:/1.0",
       "process:agsc/", "process:agsc/1.0/2", "process:Agsc/1.0", "human:ada/1.0",
       "process:agsc/-1"]
ENGINE_SCHEMA = os.path.join(os.path.dirname(__file__), "..", "..", "agentic-system-core",
                             "schema", "item.schema.json")


def episode(actor):
    return {"type": "episode", "title": "A build run", "prov": PROV,
            "started": "2026-01-01T00:00:00Z", "actor": actor, "outcome": "success"}


def actor_codes(data):
    return [one["code"] for one in frontmatter.check(data) if one.get("key") == "actor"]


@pytest.mark.parametrize("actor", GOOD)
def test_an_actor_of_the_four_forms_is_clean(actor):
    assert actor_codes(episode(actor)) == []


@pytest.mark.parametrize("actor", BAD)
def test_anything_else_is_agsc_e204(actor):
    assert actor_codes(episode(actor)) == ["AGSC-E204"]


def test_generated_by_takes_the_same_grammar():
    data = {"type": "concept", "title": "Title here", "kind": "term", "prov": PROV,
            "generated": {"by": "process:agsc/1.0.0", "at": "2026-01-01T00:00:00Z"}}
    assert frontmatter.check(data) == []


@pytest.mark.skipif(not os.path.isfile(ENGINE_SCHEMA), reason="the engine is not beside this repository")
def test_the_engine_schema_agrees_on_every_case():
    with open(ENGINE_SCHEMA, encoding="utf-8") as handle:
        pattern = re.compile(json.load(handle)["$defs"]["actor"]["pattern"])
    for actor in GOOD:
        assert pattern.search(actor) is not None, actor
    for actor in BAD:
        assert pattern.search(actor) is None, actor
