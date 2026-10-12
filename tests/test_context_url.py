"""The versioned context address this package writes (AGSC-05-09, AGSC-05-25).

AGSC-05-09 names one persistent context address per vocabulary version,
``https://w3id.org/agentic-system-core/ns/<version>/context.jsonld``, and
AGSC-05-25 takes the version from the vocabulary's ``owl:versionIRI``. The
engine derives the address from ``ontology/agsc.ttl``; this package carries it
as a constant. When the engine is beside this repository, the constant is
compared with the address the engine's vocabulary gives.

No network, no clock: the test reads one file of the engine checkout.
"""

import re

import pytest

from agentic_system_core import context
from agentic_system_core.rdf import IRI, RDF_TYPE
from conftest import ENGINE

ONTOLOGY = ENGINE / "ontology" / "agsc.ttl"
NAMESPACE = "https://w3id.org/agentic-system-core/ns"


def _version_iri():
    text = ONTOLOGY.read_text(encoding="utf-8")
    found = re.findall(r"^\s*owl:versionIRI <([^>]+)>\s*[;.]\s*$", text, re.M)
    assert len(found) == 1, "the engine's vocabulary carries %d owl:versionIRI" % len(found)
    return found[0]


@pytest.mark.skipif(not ONTOLOGY.is_file(), reason="the engine is not beside this repository")
def test_the_context_address_is_the_one_the_engine_vocabulary_gives():
    version_iri = _version_iri()
    assert version_iri.startswith(NAMESPACE + "/")
    assert context.CONTEXT_URL == version_iri + "/context.jsonld"


def test_the_address_is_the_persistent_form_of_the_rule():
    assert re.fullmatch(re.escape(NAMESPACE) + r"/[0-9A-Za-z.+-]+/context\.jsonld", context.CONTEXT_URL)


def test_a_compacted_document_names_that_address():
    subject = IRI("https://a.example/concepts/sample/")
    triples = {(subject, IRI(RDF_TYPE), IRI(context.ASC + "Concept"))}
    built = context.build([{"kind": "object", "term": "uses"}], ["skos:prefLabel"])
    document = context.compact(triples, built)
    assert document["@context"] == context.CONTEXT_URL
