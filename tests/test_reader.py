"""The reading API: links, digests, chunks and the graph.  Nothing fetches."""

import json

import pytest

from agentic_system_core import reader
from conftest import WELLKNOWN, case

LLMS = b"# node.example\n\n> A fixture.\n"


@pytest.fixture
def document():
    return reader.DiscoveryDocument.from_path(case("good"))


def test_the_anchor_and_the_wellknown_url(document):
    assert document.anchor == "https://node.example/"
    assert document.wellknown_url == "https://node.example/.well-known/knowledge-linkset"


def test_links_by_relation(document):
    alternates = document.links("alternate")
    assert len(alternates) == 1
    assert alternates[0].href == "https://node.example/llms.txt"
    assert alternates[0].type == "text/plain"
    assert alternates[0].relation == "alternate"
    assert document.links("license")[0].href == "https://node.example/legal/"


def test_a_short_extension_name_is_expanded(document):
    peers = document.links("peer")
    assert len(peers) == 1
    assert peers[0].relation == reader.relation("peer")
    assert document.peers() == ["https://peer.example/.well-known/knowledge-linkset"]
    # The full URI works too.
    assert document.links(reader.relation("peer"))[0].href == peers[0].href


def test_every_link_at_once(document):
    every = document.links()
    assert len(every) == len(document.relations()) == 6
    assert "anchor" not in document.relations()


def test_surfaces(document):
    surfaces = document.surfaces()
    assert list(surfaces) == ["llms-txt"]
    assert surfaces["llms-txt"].attribute("agsc-access") == "none"
    assert surfaces["llms-txt"].attribute("nothing", "fallback") == "fallback"


def test_a_digest_is_verified_against_bytes_you_already_hold(document):
    link = document.links("alternate")[0]
    assert link.digest.startswith("sha-256=:")
    assert link.verify(LLMS)
    assert not link.verify(b"other bytes")
    assert reader.digest_of(LLMS) == link.digest


def test_digest_forms_that_are_refused():
    assert not reader.verify_digest(None, b"")
    assert not reader.verify_digest("sha-512=:abc:", b"")
    assert not reader.verify_digest("sha-256=:!!!:", b"")
    assert not reader.verify_digest("sha-256=:" + "A" * 43 + "=:", b"")


def test_a_link_with_no_digest_verifies_nothing():
    document = reader.DiscoveryDocument.from_path(case("missing-digest"))
    assert document.links("alternate")[0].digest is None
    assert not document.links("alternate")[0].verify(LLMS)


def test_nothing_is_fetched_unless_you_pass_a_fetcher(document):
    link = document.links("alternate")[0]
    with pytest.raises(reader.DiscoveryError):
        link.fetch(None)
    assert link.fetch(lambda href: (href, LLMS)) == (link.href, LLMS)


def test_a_document_that_is_not_a_link_set_is_refused():
    with pytest.raises(reader.DiscoveryError):
        reader.DiscoveryDocument.from_bytes(b'{"linkset":[]}')
    with pytest.raises(reader.DiscoveryError):
        reader.DiscoveryDocument.from_bytes(b'{"nope":1}')
    with pytest.raises(reader.DiscoveryError):
        reader.DiscoveryDocument.from_bytes(b'{"linkset":[{"license":[]}]}')


def test_a_target_that_is_not_an_object_is_left_out():
    document = reader.DiscoveryDocument.from_bytes(
        b'{"linkset":[{"anchor":"https://n.example/","license":["x",{"no":1}]}]}')
    assert document.links("license") == []
    assert document.links("absent") == []


def test_read_chunks_reads_one_record_per_line():
    text = '{"id":"a","text":"one"}\n{"id":"b","text":"two"}\n'
    records = reader.read_chunks(text)
    assert [one["id"] for one in records] == ["a", "b"]
    assert reader.read_chunks(text.encode("utf-8")) == records


def test_read_chunks_returns_a_shard_manifest_as_it_stands():
    manifest = '{"lines_total":7,"shards":["/chunks-01.jsonl"]}'
    assert reader.read_chunks(manifest) == {"lines_total": 7, "shards": ["/chunks-01.jsonl"]}


def test_a_broken_chunk_line_names_its_line_number():
    with pytest.raises(reader.DiscoveryError) as error:
        reader.read_chunks('{"id":"a"}\nnot json\n')
    assert "line 2" in str(error.value)


def test_read_graph_is_plain_json(tmp_path):
    graph = {"@context": "https://node.example/ns/context.jsonld", "@graph": []}
    path = tmp_path / "graph.jsonld"
    path.write_bytes(json.dumps(graph).encode("utf-8"))
    assert reader.read_graph_path(str(path)) == graph
    assert reader.read_graph(json.dumps(graph)) == graph


def test_read_chunks_from_a_file(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_bytes(b'{"id":"a"}\n')
    assert reader.read_chunks_path(str(path)) == [{"id": "a"}]


def test_a_same_origin_target_maps_onto_the_build_output(document):
    root = str(WELLKNOWN / "good")
    assert reader.local_path_for(document, "https://node.example/llms.txt", root) \
        == root + "/llms.txt"
    assert reader.local_path_for(document, "https://node.example/legal/", root) \
        == root + "/legal/index.html"
    assert reader.local_path_for(document, "https://elsewhere.example/x", root) is None
    assert reader.local_path_for(document, "https://node.example/../escape", root) is None


def test_the_relation_helper():
    assert reader.relation("graph") == \
        "https://w3id.org/agentic-system-core/rel#graph"


def test_an_attribute_with_several_values_is_returned_whole(document):
    link = document.links("describedby")[0]
    assert link.attribute("agsc-counts") == "concepts=1"
    link.attributes["many"] = ["a", "b"]
    assert link.attribute("many") == ["a", "b"]


def test_a_digest_whose_base64_is_malformed_is_refused():
    assert not reader.verify_digest("sha-256=:AAAAA:", b"")


def test_members_of_a_later_version_are_ignored_and_kept_as_they_stand():
    # AGSC-00-21: a reader never fails on, and never rewrites, a member it does not know
    # in a chunk line, a chunk manifest or a discovery document of its MAJOR.
    line = '{"id":"a","text":"one","x-later":{"k":[1,2]}}\n'
    assert reader.read_chunks(line) == [{"id": "a", "text": "one", "x-later": {"k": [1, 2]}}]
    manifest = '{"later":true,"lines_total":7,"shards":["/chunks-01.jsonl"]}'
    assert reader.read_chunks(manifest)["later"] is True
    later = {"linkset": [{
        "anchor": "https://a.example/",
        "https://w3id.org/agentic-system-core/rel#later": [
            {"agsc-later": ["x"], "href": "https://a.example/later.json"}],
        "describedby": [{"agsc-spec-version": ["1.9.0"], "href": "https://a.example/graph.jsonld"}],
    }]}
    node = reader.DiscoveryDocument(later)
    assert node.links("later")[0].attribute("agsc-later") == "x"
    assert node.peers() == [] and node.surfaces() == {}
    assert reader.read_graph('{"@context":{},"later":1}') == {"@context": {}, "later": 1}
