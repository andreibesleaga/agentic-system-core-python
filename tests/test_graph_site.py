"""RDF terms and serialisations, the dataset mapping, the context, and the site artefacts."""

import pytest

from agentic_system_core import context, discovery, graph, rdf, site, wellknown
from agentic_system_core.rdf import IRI, Literal


# --- rdf ------------------------------------------------------------------------

def test_terms_compare_and_hash_by_value():
    assert IRI("a") == IRI("a") and IRI("a") != IRI("b") and IRI("a") != "a"
    assert len({IRI("a"), IRI("a")}) == 1
    assert Literal("x", datatype=rdf.XSD_STRING) == Literal("x")
    assert Literal("x", lang="EN").lang == "en" and Literal("x") != Literal("y")
    assert "IRI(" in repr(IRI("a")) and "Literal(" in repr(Literal("x"))
    with pytest.raises(ValueError):
        Literal("x", datatype=rdf.XSD_DATETIME, lang="en")
    with pytest.raises(ValueError):
        Literal("x", lang="")


def test_subjects_are_iris_and_never_memory_aliases():
    with pytest.raises(ValueError):
        rdf.nquads({(Literal("x"), IRI("p"), IRI("o"))})
    with pytest.raises(ValueError):
        rdf.turtle({(IRI("memory://b/s"), IRI("p"), IRI("o"))})


def test_pn_local_and_prefixed_names():
    assert rdf.is_pn_local("Concept") and rdf.is_pn_local("a.b") and rdf.is_pn_local("9x")
    assert rdf.is_pn_local("é·x") and rdf.is_pn_local(":x")
    for bad in ("", "a.", "a/b", "-a", "a#b", "a b"):
        assert not rdf.is_pn_local(bad), bad
    assert rdf.turtle_iri(rdf.ASC + "Concept") == "asc:Concept"
    assert rdf.turtle_iri(rdf.SCHEMA) == "<https://schema.org/>"
    assert rdf.turtle_iri("https://a.example/x/") == "<https://a.example/x/>"


def test_turtle_term_forms_and_object_lists():
    assert rdf.turtle_term(Literal("2026", datatype=rdf.XSD_DATETIME)) == '"2026"^^xsd:dateTime'
    assert rdf.turtle_term(Literal("x", datatype="https://t.example/t")) == \
        '"x"^^<https://t.example/t>'
    ttl = rdf.turtle({(IRI("https://a.example/s"), IRI(rdf.ASC + "p"), Literal("b")),
                      (IRI("https://a.example/s"), IRI(rdf.ASC + "p"), Literal("a"))})
    assert ttl.endswith('\n<https://a.example/s> asc:p "a" , "b" .\n')


def test_blank_node_detection_skips_iris_strings_and_comments():
    assert rdf.turtle_has_blank_node("<a> <b> _:x .")
    assert rdf.turtle_has_blank_node("<a> <b> ( <c> ) .")
    assert not rdf.turtle_has_blank_node('<a[b]> <p> "[x]" , \'(y)\' , """[z]""" . # [c]\n')
    assert not rdf.turtle_has_blank_node('<a> <p> "esc \\" [x]" .')
    assert not rdf.turtle_has_blank_node("<unterminated")
    assert not rdf.turtle_has_blank_node("# only a comment")


# --- graph ------------------------------------------------------------------------

def test_the_mapping_covers_every_row_and_relation():
    items = [
        {"slug": "c1", "type": "cluster", "title": "C1", "narrower": ["c2"]},
        {"slug": "c2", "type": "cluster", "title": "C2", "related": ["x"]},
        {"slug": "x", "type": "concept", "title": "X", "kind": "term", "description": "D",
         "aliases": ["Ex"], "date": "2026-01-01", "stale_after": "2027-01-01T00:00:00Z",
         "status": "retired", "prov": {"origin": "human", "operator": "human:a",
                                       "model": "m"},
         "generated": {"by": "tool/1", "at": "2026-01-02"}, "clusters": ["c2", "nope"],
         "uses": ["y"], "derived-from": ["y"], "supersedes": ["gone"],
         "broader": ["c1"], "verified": [{"by": "human:a", "at": "2026-01-01T00:00:00Z"}],
         "attachments": [{"file": "f.png", "media_type": "image/png", "alt": "F",
                          "license": "CC0-1.0"}]},
        {"slug": "y", "type": "episode", "title": "Y", "outcome": "success"},
        {"slug": "g", "type": "gate", "title": "G", "level": "L1"},
        {"slug": "l", "type": "lesson", "title": "L", "severity": "warn", "modified": None},
    ]
    triples = graph.dataset(items, "https://a.example", bundle={},
                            attachment_bytes={"f.png": b"\x89PNG"})
    text = rdf.nquads(triples)
    assert "<https://a.example/clusters/c1/> <http://www.w3.org/2004/02/skos/core#member> " \
           "<https://a.example/clusters/c2/>" in text
    assert "skos/core#related" not in text and "skos/core#broader" not in text
    assert "#usedBy> <https://a.example/concepts/x/>" in text
    assert "wasDerivedFrom" in text and "#retiredAt" in text and "#altLabel" in text
    assert "#definition" in text and "#staleAfter" in text and "#generatedAt" in text
    assert "#generatedBy" in text and "#model" in text and "#outcome" in text
    assert "#level" in text and "#severity" in text and "#verifiedAt" in text
    assert '"CC0-1.0"' in text and "#sha256" in text
    assert "asc:Bundle" not in text and "ns#Bundle" in text


def test_retired_without_a_date_has_no_retired_at_and_memory_aliases_resolve():
    text = graph.to_nquads([{"slug": "r", "type": "concept", "title": "R", "status": "retired"}],
                           "https://a.example/")
    assert "retiredAt" not in text
    assert graph.resolve_memory("plain-slug", "b") == "plain-slug"
    with pytest.raises(graph.GraphError):
        graph.resolve_memory("memory://other/s", "b")


# --- context --------------------------------------------------------------------

def test_the_context_round_trips_every_value_form():
    built = context.build([{"kind": "object", "term": "uses"},
                           {"kind": "datatype", "range": "xsd:string", "term": "kind"},
                           {"kind": "datatype", "term": "untyped"}],
                          [prop for prop, _ in context.EXTERNAL_PROPERTIES])
    triples = context.sample_triples(built)
    subject = IRI("https://a.example/concepts/sample/")
    # values no term can carry: an unmapped predicate, a mismatched datatype, an IRI
    triples |= {(subject, IRI("https://other.example/p"), IRI("https://a.example/o")),
                (subject, IRI(rdf.ASC + "kind"), Literal("x", datatype=rdf.XSD_DATETIME)),
                (subject, IRI("https://other.example/q"), Literal("hi", lang="en")),
                (subject, IRI("https://other.example/r"), Literal("plain")),
                (subject, IRI(rdf.ASC + "kind"), Literal("second"))}
    first, again = context.roundtrip_bytes(triples, built)
    assert first == again
    assert context.expand(__import__("json").loads(first), built) == triples
    assert context.expand_curie("nope:x") == "nope:x"
    assert context.expand_curie("https://x") == "https://x"


# --- site -----------------------------------------------------------------------

def test_tokenizer_and_fences():
    assert site.tokens("ÉCOLE Ab x ²2") == ["École", "ab"]
    assert site.tokens("AB-cd") == ["ab", "cd"]
    body = "keep\n````\n```\ninside\n````\nafter\n~~~\nx\n"
    assert site.strip_fenced_code(body) == "keep\nafter"


def test_search_index_postings_are_unique_and_optional_members_absent():
    index = site.search_index([{"slug": "a", "title": "Go go go", "body": "go"}])
    assert index == {"docs": [{"slug": "a", "title": "Go go go"}], "terms": {"go": [0]}}


def test_fragments_and_headers():
    files, index = site.fragments("<s> <p> <o> <g> .\n\n", "2026-01-01T00:00:00Z")
    assert len(files) == 2 and index["subjects"] and index["predicates"]
    assert site.header_set(["/x"]) == {"/*": {"Content-Security-Policy": site.CSP}}


def test_security_txt_every_fault():
    good = "Contact: mailto:a@b\n"
    base = "https://a.example/"
    now = "2026-01-01T00:00:00Z"
    assert site.security_txt(good + "junk line\n", now, base, False)[0] is None
    text, found = site.security_txt(good + "Expires: 2026-02-01T00:00:00Z\nExpires: x\n",
                                    now, base, False)
    assert text is None and found[0]["code"] == "AGSC-E204"
    assert site.security_txt(good + "Expires: tomorrow\n", now, base, False)[0] is None
    text, found = site.security_txt(good + "Expires: 2028-01-01T00:00:00Z\nCanonical: c\n"
                                    "Policy: p\n", now, base, True)
    assert text is not None and found[0]["severity"] == "warn"


def test_content_version_branches_and_ledger_kinds():
    log = [{"sha": "a" * 40, "tag": "bad tag"}, {"sha": "b" * 40}]
    assert site.content_version(log, 5)[0] == "0.0.0+2.gbbbbbbbbbbbb"
    assert site.content_version([], 86400)[0] == "0.0.0+19700102T000000Z"
    assert site.content_version([], 86400)[1] == []
    assert site.ledger_kind({"parents": ["a", "b"]}) == "merge"
    assert site.ledger_kind({"trailers": {"Proposal": "1"}}) == "merge"
    assert site.ledger_kind({}) == "commit"


# --- discovery ------------------------------------------------------------------

def test_llms_files_neutralise_comment_closers_and_handle_cluster_items():
    bundle = {"base": "https://a.example", "title": "T", "description": "one\ntwo",
              "license_prose": "evil --> x"}
    items = [{"slug": "c", "type": "cluster", "title": "Cl"},
             {"slug": "i", "type": "concept", "title": "I", "clusters": ["c"]}]
    text = discovery.llms_txt(bundle, items)
    assert "license: evil --&gt; x" in text and "> one two" in text and "## Cl" in text
    assert discovery.reachability("- [x](y): z\n") == {}


def test_sitemap_robots_and_linkset_writers():
    assert discovery.sitemap_xml("https://a.example/", ["/b&c/", "/"], "T").count("<url>") == 2
    groups, _ = discovery.robots_groups(["Bot"], 0)
    assert discovery.robots_txt(groups) == ("User-agent: Bot\nDisallow: /\n\n"
                                            "User-agent: *\nAllow: /\n")
    level0 = discovery.linkset("https://a.example/", level=0)
    assert "digest" not in discovery.linkset_bytes(level0)
    restricted = discovery.linkset("https://a.example/", level=2, restricted=True,
                                   facts={"generated_at": "T", "spec_version": "S"})
    findings = []
    wellknown.check(wellknown.from_value(restricted), 2, findings)
    assert [one for one in findings if one["severity"] == "error"] == []
    raw = wellknown.from_value(b'{"linkset":[]}')
    assert raw.data == b'{"linkset":[]}'


def test_a_restricted_node_that_publishes_a_forbidden_fact_is_e210():
    document = discovery.linkset("https://a.example/", level=2, restricted=True,
                                 facts={"generated_at": "T", "spec_version": "S"})
    document["linkset"][0]["https://w3id.org/agentic-system-core/rel#ledger"][0][
        "agsc-ledger-head"] = ["x"]
    findings = []
    wellknown.check(wellknown.from_value(document), 2, findings)
    assert [one["code"] for one in findings] == ["AGSC-E210"]
    assert wellknown._is_restricted({"describedby": "x"}) is False


def test_cite_as_is_an_admitted_related_system_relation_that_carries_a_type():
    document = discovery.linkset("https://a.example/", level=0)
    document["linkset"][0]["cite-as"] = [{"href": "https://doi.example/10.1/x",
                                          "type": "text/html"}]
    findings = []
    wellknown.check(wellknown.from_value(document), 0, findings)
    assert findings == []
    del document["linkset"][0]["cite-as"][0]["type"]
    findings = []
    wellknown.check(wellknown.from_value(document), 0, findings)
    assert [one["code"] for one in findings] == ["AGSC-E209"]
