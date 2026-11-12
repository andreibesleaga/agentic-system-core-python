"""The relation table of AGSC-03-01, read from ``data/relations.json``.

The table is the engine's ``src/knowledge/relations.js``, derived by the command in
docs/MAINTAINING.md and never typed. ``links.py`` and ``graph.py`` take their key
lists, inverses and RDF properties from it, so the package keeps one copy. On fixed
data: the facts of the frozen table that the rest of the package relies on. Against
the engine, when it is beside this repository with Node: the file is the bytes the
command derives. No network.
"""

import json
import subprocess

import pytest

from agentic_system_core import graph, links, relations
from agentic_system_core.rdf import ASC, DCTERMS, PROV, SKOS
from conftest import ENGINE, engine_available

#: The command of docs/MAINTAINING.md, "Refreshing what is copied from the specification".
DERIVE = ("const r = require(require('node:path').resolve(process.argv[1], 'src/knowledge/relations.js'));"
          " process.stdout.write(JSON.stringify({ relations: r.RELATIONS }, null, 2) + '\\n');")


def test_the_table_has_the_fourteen_keys_in_the_order_of_the_specification():
    assert relations.CORE_KEYS == ("related", "broader", "narrower", "uses", "requires",
                                   "excludes", "derived-from", "contradicts", "supersedes")
    assert relations.MODE2_KEYS == ("implements", "verifies", "covers", "blocked-by",
                                    "decided-by")
    assert relations.KEYS == relations.CORE_KEYS + relations.MODE2_KEYS
    assert [row["key"] for row in relations.RELATIONS] == list(relations.KEYS)


def test_symmetric_keys_are_their_own_inverse_and_the_rest_are_computed_names():
    assert relations.SYMMETRIC == ("related", "excludes", "contradicts")
    assert all(relations.INVERSE[key] == key for key in relations.SYMMETRIC)
    # AGSC-03-04: the computed names, never authored; `narrower` is an authorable key.
    assert relations.COMPUTED_KEYS == ("used-by", "required-by", "derivation-of",
                                       "superseded-by", "implemented-by", "verified-by",
                                       "covered-by", "blocks", "decides")
    assert "narrower" not in relations.COMPUTED_KEYS


def test_each_key_has_its_rdf_properties_as_full_iris():
    assert relations.LINK_PROPERTIES["related"] == (SKOS + "related", SKOS + "related")
    assert relations.LINK_PROPERTIES["requires"] == (DCTERMS + "requires",
                                                     DCTERMS + "isRequiredBy")
    assert relations.LINK_PROPERTIES["blocked-by"] == (ASC + "blockedBy", ASC + "blocks")
    # AGSC-05-23: `derivation-of` has no property of its own.
    assert relations.LINK_PROPERTIES["derived-from"] == (PROV + "wasDerivedFrom", None)


def test_links_and_graph_read_the_one_table():
    assert links.KEYS is relations.KEYS
    assert links.INVERSE is relations.INVERSE
    assert links.AUTHORED_INVERSE_FORBIDDEN is relations.COMPUTED_KEYS
    assert graph.LINK_PROPERTIES is relations.LINK_PROPERTIES


def test_a_curie_outside_the_known_prefixes_is_refused():
    with pytest.raises(ValueError):
        relations.expand("ex:thing")


def test_the_three_combiner_columns_are_read_as_data():
    row = relations.ROW["derived-from"]
    assert row["transitive"] is True and row["selfLink"] == "warning"
    assert row["targets"] == {"any": True, "lessonTarget": {"type": "episode"}}
    assert relations.ROW["requires"]["selfLink"] == "cycle"


@pytest.mark.skipif(not engine_available(),
                    reason="the relation-table drift check needs Node and the engine checkout")
def test_the_shipped_table_is_the_bytes_the_engine_derives():
    done = subprocess.run(["node", "-e", DERIVE, str(ENGINE)], capture_output=True)
    assert done.returncode == 0, done.stderr[-2000:]
    assert relations.data_bytes() == done.stdout


@pytest.mark.skipif(not engine_available(),
                    reason="the link-shaped names check needs Node and the engine checkout")
def test_the_link_shaped_names_are_the_engines():
    """AGSC-03-03: the names that are AGSC-E304, as the engine's relation table lists them."""
    script = ("const r = require(require('node:path').resolve(process.argv[1], 'src/knowledge/relations.js'));"
              " process.stdout.write(JSON.stringify([...r.LINK_SHAPED_UNKNOWN]));")
    done = subprocess.run(["node", "-e", script, str(ENGINE)], capture_output=True)
    assert done.returncode == 0, done.stderr[-2000:]
    assert sorted(links.LINK_SHAPED_UNKNOWN) == sorted(json.loads(done.stdout))
