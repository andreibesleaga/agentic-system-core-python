"""The SKOS view of the graph (AGSC-05-36), the file ``export --skos`` writes.

``skos.skos_view`` takes the triples of ``graph.nq`` and the scheme record and writes one
Turtle file with its own two-line prefix block. The engine's
``src/knowledge/skos-export.js`` is the reference; ``graph-0040`` pins the whole file.
Fixed data, no network.
"""

from agentic_system_core import graph, skos

BASE = "https://a.example/"
BUNDLE = {"license_prose": "CC0-1.0", "spec_version": "1.0.0"}


def view(items, record=None, bundle=BUNDLE):
    return skos.skos_view(graph.dataset(items, BASE, bundle), record or {})


def test_the_record_takes_title_tagline_and_author_where_present():
    assert skos.scheme_record({"site": {"title": "T", "tagline": "G", "author": "A"}}) == {
        "creator": "A", "description": "G", "title": "T"}
    assert skos.scheme_record({"site": {"title": "T"}}) == {"title": "T"}
    assert skos.scheme_record({}) == {}


def test_the_file_opens_with_the_two_line_prefix_block():
    text = view([{"slug": "a", "type": "concept", "title": "A"}])
    assert text.startswith("@prefix dcterms: <http://purl.org/dc/terms/> .\n"
                           "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n\n")


def test_a_concept_without_broader_is_a_top_concept_and_the_scheme_names_it():
    text = view([{"slug": "a", "type": "concept", "title": "A"},
                 {"slug": "b", "type": "concept", "title": "B", "broader": ["a"]}],
                {"title": "Node"})
    assert ("<https://a.example/> dcterms:license \"CC0-1.0\" ;\n"
            "    dcterms:title \"Node\" ;\n"
            "    a skos:ConceptScheme ;\n"
            "    skos:hasTopConcept <https://a.example/concepts/a/> ;\n"
            "    skos:prefLabel \"Node\" .\n") in text
    assert "<https://a.example/concepts/b/> a skos:Concept ;\n" in text
    assert text.count("skos:topConceptOf") == 1


def test_an_episode_and_every_triple_that_names_it_are_left_out():
    text = view([{"slug": "grp", "type": "cluster", "title": "G"},
                 {"slug": "ep", "type": "episode", "title": "E", "clusters": ["grp"]},
                 {"slug": "a", "type": "concept", "title": "A", "clusters": ["grp"]}])
    assert "episodes/ep" not in text
    assert "<https://a.example/clusters/grp/> a skos:Collection ;\n" in text
    assert "skos:member <https://a.example/concepts/a/> ;" in text


def test_a_graph_without_a_bundle_node_has_no_scheme():
    text = view([{"slug": "a", "type": "concept", "title": "A"}], bundle=None)
    assert "ConceptScheme" not in text and "topConceptOf" not in text
    assert "<https://a.example/concepts/a/> a skos:Concept ;\n" in text
