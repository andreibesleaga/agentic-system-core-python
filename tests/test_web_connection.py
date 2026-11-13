"""The web connection of a node: the Signposting links and the Dataset block of ``/``,
the two catalogue files and the A2A agent card (AGSC-06-34, AGSC-06-40 to AGSC-06-42,
AGSC-06-44).

The shared vectors disc-0026 to disc-0038 pin what each writer gives, and the suite
runs them (``tests/test_vectors.py``); these tests state the rules the vectors do not
reach: the A2A-only card, the domain-name rule of a ``urn:air`` identifier, the
licence URL order and the creator taken from ``bundle.creator``.
"""

import hashlib
import json

import pytest

from agentic_system_core import agentcard, catalogue, signposting
from agentic_system_core.areas import AREA_RUNNERS
from conftest import VECTORS

CARD = {"access": "none", "surface": "a2a-card",
        "target": "https://a.example/.well-known/agent-card.json", "version": "1.0"}
RESPONDER = {"access": "consent", "binding": "HTTP+JSON", "surface": "responder",
             "target": "https://a.example/a2a", "version": "a2a:1.0"}


def vector(prefix):
    path = sorted((VECTORS / "discovery").glob(prefix + "-*.json"))[0]
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("identifier", ["disc-0026", "disc-0028", "disc-0029", "disc-0030",
                                        "disc-0031", "disc-0033", "disc-0035", "disc-0036",
                                        "disc-0037", "disc-0038"])
def test_each_web_connection_case_passes(identifier):
    data = vector(identifier)
    result = AREA_RUNNERS["discovery"](data)
    assert result["status"] == "pass", result["detail"]


def test_a_changed_card_byte_fails_its_case():
    data = vector("disc-0030")
    data["expected"]["cases"][0]["file"] = data["expected"]["cases"][0]["file"].replace(
        "v1.4.0", "v1.4.1")
    assert AREA_RUNNERS["discovery"](data)["status"] == "fail"


def test_a_case_with_no_expectation_fails():
    data = vector("disc-0037")
    del data["expected"]["cases"][0]["block"]
    assert AREA_RUNNERS["discovery"](data)["status"] == "fail"


# ---------------------------------------------------------------- AGSC-06-34, the card
def test_a_card_is_written_only_with_both_surfaces():
    assert agentcard.card_bytes([CARD, RESPONDER], [], "Node", "v1", "1.1.0") is not None
    assert agentcard.card_bytes([CARD], [], "Node", "v1", "1.1.0") is None
    assert agentcard.card_bytes([RESPONDER], [], "Node", "v1", "1.1.0") is None


def test_a_node_with_no_skill_pack_has_skills_empty_and_capabilities_an_empty_object():
    card = json.loads(agentcard.card_bytes([CARD, RESPONDER], [], "Node", "v1", "1.1.0"))
    assert card["skills"] == [] and card["capabilities"] == {}
    assert card["description"] == "Node"  # the title when there is no description or tagline
    assert "securitySchemes" not in card and "signatures" not in card
    assert card["supportedInterfaces"] == [{"protocolBinding": "HTTP+JSON",
                                            "protocolVersion": "1.0",
                                            "url": "https://a.example/a2a"}]


def test_a_responder_with_no_binding_is_json_rpc():
    plain = dict(RESPONDER)
    del plain["binding"]
    card = json.loads(agentcard.card_bytes([CARD, plain], [], "Node", "v1", "1.1.0"))
    assert card["supportedInterfaces"][0]["protocolBinding"] == "JSONRPC"


@pytest.mark.parametrize("surfaces,why", [
    ([CARD, dict(RESPONDER, version="mcp:2025-11-25")], "is not an A2A endpoint"),
    ([CARD, RESPONDER, dict(RESPONDER, target="https://a.example/mcp", version="2026-07-28")],
     "is not an A2A endpoint"),
    ([dict(CARD, version="a2a:1.0"), RESPONDER], "is not an A2A protocol version"),
    ([dict(CARD, version="1.0.0-beta"), RESPONDER], "is not an A2A protocol version"),
])
def test_a_card_that_would_not_be_a_true_a2a_card_is_not_written_and_warned(surfaces, why):
    # The A2A-only card rule of the block-8 close: no card, and the warning AGSC-E210
    # saying that the discovery document still declares it.
    assert agentcard.card_bytes(surfaces, [], "Node", "v1", "1.1.0") is None
    findings = agentcard.card_findings(surfaces)
    assert [(one["code"], one["severity"]) for one in findings] == [("AGSC-E210", "warn")]
    assert why in findings[0]["message"] and CARD["target"] in findings[0]["message"]


def test_a_card_without_an_endpoint_is_an_error_and_no_declaration_gives_nothing():
    assert [(one["code"], one["severity"]) for one in agentcard.card_findings([CARD])] == \
        [("AGSC-E210", "error")]
    assert agentcard.card_findings([RESPONDER]) == []
    assert agentcard.card_findings([]) == []


def test_a_bare_version_with_a_patch_is_an_a2a_version():
    surfaces = [dict(CARD, version="1.0.2"), RESPONDER]
    assert agentcard.card_findings(surfaces) == []
    card = json.loads(agentcard.card_bytes(surfaces, [], "Node", "v1", "1.1.0"))
    assert card["supportedInterfaces"][0]["protocolVersion"] == "1.0.2"


# ---------------------------------------------------------------- AGSC-06-42, catalogues
@pytest.mark.parametrize("base,host", [
    ("https://a.example/", "a.example"),
    ("https://A.Example:8443/x/", "a.example"),
    ("https://a.example./", "a.example."),
    ("https://localhost/", None),
    ("https://192.0.2.1/", None),
    ("https://0x7f.1/", None),
    ("https://[2001:db8::1]/", None),
    ("https://printer.local/", None),
    ("not a url", None),
    (None, None),
])
def test_a_urn_air_identifier_needs_a_fully_qualified_domain_name(base, host):
    assert catalogue.domain_name(base) == host


def _config(**changes):
    config = {"bundle": {"id": "example"}, "discovery": {"ai_catalog": True},
              "site": {"base": "https://a.example/", "title": "Example"}}
    config.update(changes)
    return config


def test_the_catalogues_are_opt_in_and_digest_the_exact_bytes():
    assert catalogue.catalogue_files(_config(discovery={}), "{}\n") == ({}, [])
    files, findings = catalogue.catalogue_files(_config(), "{}\n", card_bytes="[]\n")
    assert findings == []
    entries = json.loads(files[catalogue.AI_CATALOG_PATH])["entries"]
    assert [one["identifier"] for one in entries] == ["urn:air:a.example:a2a:example",
                                                     "urn:air:a.example:knowledge:example"]
    assert entries[1]["digest"] == "sha256:" + hashlib.sha256(b"{}\n").hexdigest()
    ard = json.loads(files[catalogue.ARD_PATH])["entries"]
    assert ard[0]["metadata"] == {"digest": "sha256:" + hashlib.sha256(b"[]\n").hexdigest()}


def test_a_catalogue_without_a_bundle_id_or_a_domain_name_is_refused():
    assert [one["code"] for one in catalogue.catalogue_files(
        _config(bundle={}), "{}\n")[1]] == ["AGSC-E202"]
    files, findings = catalogue.catalogue_files(
        _config(site={"base": "https://127.0.0.1/"}), "{}\n")
    assert files == {} and [one["code"] for one in findings] == ["AGSC-E209"]


# ---------------------------------------------------------------- AGSC-06-40, 06-41, 06-44
def test_the_licence_url_is_the_configured_one_then_legal_then_none():
    named = {"bundle": {"license_url": "https://l.example/4.0/"}, "site": {"base": "https://a.example/"}}
    assert signposting.license_url(named, legal=True) == "https://l.example/4.0/"
    default = {"bundle": {}, "site": {"base": "https://a.example//"}}
    assert signposting.license_url(default, legal=True) == "https://a.example/legal/"
    assert signposting.license_url(default, legal=False) is None
    other = {"bundle": {"license_prose": "CC0-1.0"}, "site": {"base": "https://a.example/"}}
    assert signposting.license_url(other, legal=True) is None


def test_a_level_0_publisher_without_a_home_page_keeps_the_one_link_of_1_0():
    assert signposting.home_links({"site": {"base": "https://a.example/"}}, ["/graph.jsonld"]) == \
        [{"href": "/.well-known/knowledge-linkset", "rel": "describedby",
          "type": "application/linkset+json"}]


def test_the_first_cite_as_in_href_order_is_named():
    config = {"related": [{"href": "https://z.example/", "rel": "cite-as", "type": "text/html"},
                          {"href": "https://b.example/", "rel": "cite-as", "type": "text/html"},
                          {"href": "https://a.example/x", "rel": "related", "type": "text/html"}],
              "site": {"base": "https://n.example/"}}
    links = signposting.home_links(config, ["/index.html"])
    assert [one["href"] for one in links if one["rel"] == "cite-as"] == ["https://b.example/"]


def test_the_creator_is_read_from_the_bundle_first():
    config = {"bundle": {"creator": {"name": "A. Person", "orcid": "0000-0002-1825-0097"}},
              "site": {"author": "Someone Else"}}
    base = "https://a.example/"
    assert signposting.creator_of(config, base) == {
        "@id": "https://orcid.org/0000-0002-1825-0097", "@type": "Person", "name": "A. Person",
        "sameAs": "https://orcid.org/0000-0002-1825-0097"}
    assert signposting.creator_of({"site": {"author": "B"}}, base) == {
        "@id": "https://a.example/#creator", "@type": "Person", "name": "B"}
    assert signposting.creator_of({"site": {"author": ""}}, base) is None


def test_the_dataset_block_names_the_bundle_and_one_person_and_the_dcat_block_is_opt_in():
    """AGSC-06-41 as amended 2026-11-10 (disc-0037)."""
    config = {"site": {"author": "B", "base": "https://a.example/"}}
    block = signposting.dataset_block(config, "2026-01-01T00:00:00Z", {"/graph.nq"})
    assert block["@id"] == "https://a.example/"
    assert block["prov:wasAttributedTo"] == {"@id": "https://a.example/#creator"}
    assert signposting.catalog_block(config, "2026-01-01T00:00:00Z", {"/graph.nq"}) is None
    catalog = signposting.catalog_block(dict(config, discovery={"dcat": True}),
                                        "2026-01-01T00:00:00Z", {"/graph.nq", "/chunks.jsonl"})
    assert catalog["@type"] == "dcat:Catalog"
    assert [one.get("dcterms:format") for one in catalog["dcat:dataset"]["dcat:distribution"]] \
        == [None, "application/jsonl"]


def test_a_dataset_block_with_nothing_served_names_no_distribution():
    block = signposting.dataset_block({"site": {"base": "https://a.example/"}},
                                      "2026-01-01T00:00:00Z", set())
    assert "distribution" not in block and block["isAccessibleForFree"] is True
    assert block["name"] == "" and block["description"] == ""


def test_a_responder_without_a_version_and_a_card_without_one_are_named_undefined():
    surfaces = [{"surface": "a2a-card", "target": "https://a.example/c"},
                {"surface": "responder", "target": "https://a.example/a2a"}]
    message = agentcard.card_findings(surfaces)[0]["message"]
    assert "is not an A2A endpoint" in message
    surfaces[1]["version"] = "a2a:1.0"
    assert "the a2a-card version undefined" in agentcard.card_findings(surfaces)[0]["message"]
    assert agentcard.card_bytes(surfaces, [], "", "v1", "1.1.0") is None


def test_a_card_with_no_title_or_description_leaves_both_out():
    card = json.loads(agentcard.card_bytes([CARD, RESPONDER], [{"name": "p"}], "", "v1", "1.1.0"))
    assert "name" not in card and "description" not in card
    assert card["skills"] == [{"id": "p", "name": "p", "tags": ["knowledge", "skill-pack"]}]


def test_a_base_the_url_parser_refuses_has_no_domain_name():
    assert catalogue.domain_name("https://[::1/") is None


def test_a_web_case_that_states_no_case_fails_on_its_shape():
    data = vector("disc-0030")
    data["input"]["cases"] = []
    data["expected"]["cases"] = []
    result = AREA_RUNNERS["discovery"](data)
    assert result["status"] == "fail" and "shape" in result["detail"]


def test_a_validator_case_that_states_no_findings_fails():
    data = vector("disc-0026")
    del data["expected"]["validator_cases"][1]["findings"]
    assert AREA_RUNNERS["discovery"](data)["status"] == "fail"


def test_a_card_carries_the_security_a_responder_states_and_a_credential_one_without_is_warned():
    """AGSC-06-34 as amended 2026-11-10 (disc-0038), and the declaration of AGSC-11-16 (disc-0035)."""
    card_entry = {"access": "none", "surface": "a2a-card", "target": "https://a.example/c",
                  "version": "1.0"}
    responder = {"access": "credential", "surface": "responder", "target": "https://a.example/a2a",
                 "version": "a2a:1.0", "security_requirements": [{"schemes": {"b": {"list": []}}}],
                 "security_schemes": {"b": {"httpAuthSecurityScheme": {"scheme": "Bearer",
                                                                       "description": ""}}}}
    out = agentcard.card([responder, card_entry], [], "T", "v1", "1.1.0")
    assert out["securitySchemes"] == {"b": {"httpAuthSecurityScheme": {"scheme": "Bearer"}}}
    assert out["securityRequirements"] == [{"schemes": {"b": {}}}]
    bare = dict(responder)
    del bare["security_schemes"]
    assert [one["severity"] for one in agentcard.card_findings([bare, card_entry])] == ["warn"]
    mcp = dict(responder, version="mcp:2026-07-28")
    assert agentcard.served_declarations([mcp, card_entry]) == [mcp]
    assert agentcard.served_declarations([responder, card_entry]) == [responder, card_entry]
