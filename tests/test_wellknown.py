"""The discovery-file checker, over the fixture set and the two sites' files."""

import json

import pytest

from agentic_system_core import wellknown
from agentic_system_core.net import TransportError
from conftest import SITE_DOCUMENTS, WELLKNOWN, case


def codes(result):
    return sorted(one["code"] for one in result["findings"])


def run(name, **options):
    result, reads = wellknown.validate(case(name), **options)
    return result


def test_a_conforming_document_passes_at_every_level():
    for level in (0, 1, 2, 3):
        result = run("good", level=level)
        assert result["status"] == "pass", result["findings"]
    assert result["schema"] == "agsc.diagnostics.v1"
    assert result["verb"] == "validate-wellknown"


def test_the_envelope_counts_errors_and_warnings_apart():
    result = run("surface-unknown-name")
    assert result["counts"] == {"error": 0, "warn": 1}
    assert result["status"] == "pass"
    assert codes(result) == ["AGSC-E210"]
    assert result["findings"][0]["severity"] == "warn"


@pytest.mark.parametrize("name,level,expected", [
    ("not-json", 0, ["AGSC-E201"]),
    ("bom", 0, ["AGSC-E201"]),
    ("duplicate-member", 0, ["AGSC-E201"]),
    ("trailing-characters", 0, ["AGSC-E201"]),
    ("not-an-object", 0, ["AGSC-E201"]),
    ("extra-top-member", 0, ["AGSC-E201"]),
    ("linkset-not-array", 0, ["AGSC-E201"]),
    ("linkset-two-contexts", 0, ["AGSC-E201"]),
    ("context-not-object", 0, ["AGSC-E201"]),
    ("anchor-missing", 0, ["AGSC-E201"]),
    ("anchor-http", 0, ["AGSC-E201"]),
    ("anchor-no-slash", 0, ["AGSC-E201"]),
    ("members-unordered", 0, ["AGSC-E201"]),
    ("unknown-relation", 0, ["AGSC-E209"]),
    ("empty-relation-array", 0, ["AGSC-E201"]),
    ("target-not-object", 0, ["AGSC-E201"]),
    ("href-relative", 0, ["AGSC-E201"]),
    ("targets-unordered", 0, ["AGSC-E201"]),
    ("attribute-not-array", 0, ["AGSC-E201"]),
    ("type-not-string", 0, ["AGSC-E201"]),
    ("bad-digest", 0, ["AGSC-E204"]),
    ("digest-mismatch", 0, ["AGSC-E201"]),
    ("digest-target-missing", 0, ["AGSC-E901"]),
    ("ledger-no-head", 2, ["AGSC-E202"]),
    ("related-no-type", 0, ["AGSC-E209"]),
    ("surface-unknown-access", 0, ["AGSC-E210"]),
    ("surface-no-version", 0, ["AGSC-E210"]),
    ("surface-version-on-llms", 0, ["AGSC-E210"]),
    ("surface-llms-wrong-path", 0, ["AGSC-E210"]),
    ("surface-target-missing", 0, ["AGSC-E210"]),
    ("surface-multi-value", 0, ["AGSC-E210", "AGSC-E210"]),
    ("non-canonical-bytes", 2, ["AGSC-E202", "AGSC-E601"]),
    ("no-trailing-lf", 2, ["AGSC-E202", "AGSC-E601"]),
    ("invalid-utf8", 0, ["AGSC-E201"]),
    ("empty-file", 0, ["AGSC-E201"]),
    ("not-in-wellknown", 0, ["AGSC-E210", "AGSC-E901", "AGSC-E901"]),
])
def test_each_broken_document_raises_the_expected_codes(name, level, expected):
    assert codes(run(name, level=level)) == expected


def test_level_2_requires_the_graph_attributes_and_every_digest():
    # The five bundle facts of AGSC-06-08 (agsc-bundle-version among them)
    # plus the one artefact link with no digest.
    # One more: neither fixture links the ledger, which Level 2 includes (AGSC-10-04).
    assert codes(run("missing-level2-attributes", level=2)) == ["AGSC-E202"] * 7
    assert codes(run("missing-digest", level=2)) == ["AGSC-E202"] * 2
    # At Level 0 and 1 neither is required.
    assert run("missing-level2-attributes", level=1)["status"] == "pass"


def test_a_cross_origin_digest_is_not_checked_offline():
    assert run("digest-cross-origin", level=2)["status"] == "pass"


def test_a_missing_file_is_e901():
    result, reads = wellknown.validate(str(WELLKNOWN / "nowhere" / "knowledge-linkset"))
    assert codes(result) == ["AGSC-E901"]
    assert reads == 1


def test_a_file_over_one_mebibyte_is_e904(tmp_path):
    big = tmp_path / "knowledge-linkset"
    big.write_bytes(b"x" * (1048576 + 1))
    result, _ = wellknown.validate(str(big))
    assert codes(result) == ["AGSC-E904"]


def test_a_target_outside_the_site_root_is_e902(tmp_path):
    root = tmp_path / ".well-known"
    root.mkdir()
    document = {"linkset": [{"anchor": "https://node.example/",
                             "alternate": [{"digest": ["sha-256=:" + "A" * 43 + "=:"],
                                            "href": "https://node.example/../../escape.txt",
                                            "type": "text/plain"}]}]}
    (root / "knowledge-linkset").write_bytes(
        json.dumps(document, separators=(",", ":")).encode("utf-8") + b"\n")
    result, _ = wellknown.validate(str(root / "knowledge-linkset"))
    assert "AGSC-E902" in codes(result)


def test_the_mutual_peer_check():
    ok, _ = wellknown.validate(case("good"), peer=case("peer-mutual"))
    assert ok["status"] == "pass"
    bad, _ = wellknown.validate(case("good"), peer=case("peer-not-mutual"))
    assert codes(bad) == ["AGSC-E907"]
    broken, _ = wellknown.validate(case("good"), peer=case("not-json"))
    assert "AGSC-E201" in codes(broken)


def test_a_peer_check_over_two_valid_but_unreadable_documents_reports_once(tmp_path):
    # Both documents parse but neither yields a result, so the run says the
    # check could not be made rather than reporting a false mutuality.
    first = tmp_path / "a"
    first.mkdir()
    second = tmp_path / "b"
    second.mkdir()
    for directory in (first, second):
        (directory / "knowledge-linkset").write_bytes(b'{"linkset":[{"anchor":"x"}]}\n')
    result, _ = wellknown.validate(str(first / "knowledge-linkset"),
                                   peer=str(second / "knowledge-linkset"))
    assert result["status"] == "fail"


@pytest.mark.parametrize("path", SITE_DOCUMENTS, ids=lambda one: one.parts[-4])
def test_the_two_sites_discovery_files_pass_at_level_one(path):
    if not path.is_file():
        pytest.skip("the built site %s is not in this checkout" % path.parts[-4])
    result, _ = wellknown.validate(str(path), level=1)
    assert result["status"] == "pass", result["findings"]


def test_a_url_is_refused_unless_network_is_allowed():
    result, _ = wellknown.validate("https://node.example/.well-known/knowledge-linkset")
    assert codes(result) == ["AGSC-E905"]
    assert "--allow-network" in result["findings"][0]["message"]


def test_a_url_is_read_through_the_injected_fetcher():
    with open(case("good"), "rb") as handle:
        body = handle.read()
    served = {
        "https://node.example/.well-known/knowledge-linkset": body,
        "https://node.example/llms.txt": b"# node.example\n\n> A fixture.\n",
        "https://node.example/graph.jsonld": b"{}\n",
        "https://node.example/ledger.jsonl": (WELLKNOWN / "good" / "ledger.jsonl").read_bytes(),
    }

    def fetcher(href, dev=False):
        headers = {"content-type":
                   'application/linkset+json;profile="https://w3id.org/agentic-system-core/'
                   'profile/agentic-knowledge"'}
        if href not in served:
            raise TransportError("AGSC-E907", "HTTP 404 for %s" % href)
        return href, headers, served[href]

    result, reads = wellknown.validate(
        "https://node.example/.well-known/knowledge-linkset", level=2,
        allow_network=True, fetcher=fetcher)
    assert result["status"] == "pass", result["findings"]
    assert reads > 1


def test_a_served_document_with_the_wrong_media_type_is_e201():
    def fetcher(href, dev=False):
        with open(case("good"), "rb") as handle:
            return href, {"content-type": "application/json"}, handle.read()

    result, _ = wellknown.validate("https://node.example/.well-known/knowledge-linkset",
                                   allow_network=True, fetcher=fetcher)
    assert "AGSC-E201" in codes(result)


def test_the_profile_may_be_carried_by_a_link_header():
    def fetcher(href, dev=False):
        with open(case("good"), "rb") as handle:
            return href, {
                "content-type": "application/linkset+json",
                "link": '<https://w3id.org/agentic-system-core/profile/agentic-knowledge>; '
                        'rel="profile"',
            }, handle.read()

    result, _ = wellknown.validate("https://node.example/.well-known/knowledge-linkset",
                                   allow_network=True, fetcher=fetcher)
    assert result["status"] == "pass", result["findings"]


def test_a_quoted_profile_parameter_is_read():
    state = wellknown._media_type_state({
        "content-type": 'application/linkset+json; profile="https://w3id.org/agentic-system-core'
                        '/profile/agentic-knowledge"',
    })
    assert state["ok"]
    assert not wellknown._media_type_state({"content-type": "text/plain"})["ok"]
    assert not wellknown._media_type_state(None)["checked"]
    assert wellknown._media_type_state({"content-type": "application/linkset+json",
                                        "link": ["<x>; rel=other", "not a link"]})["ok"] is False


def test_an_http_anchor_is_accepted_under_dev():
    result = run("anchor-http", dev=True)
    assert result["status"] == "pass", result["findings"]


def test_a_directory_target_with_a_digest_resolves_to_its_index(tmp_path):
    import hashlib
    import base64
    root = tmp_path / ".well-known"
    root.mkdir()
    page = tmp_path / "legal" / "index.html"
    page.parent.mkdir()
    page.write_bytes(b"<!doctype html>\n")
    digest = "sha-256=:%s:" % base64.b64encode(
        hashlib.sha256(b"<!doctype html>\n").digest()).decode()
    document = {"linkset": [{"anchor": "https://node.example/",
                             "license": [{"digest": [digest],
                                          "href": "https://node.example/legal/"}]}]}
    (root / "knowledge-linkset").write_bytes(
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
    result, _ = wellknown.validate(str(root / "knowledge-linkset"), level=2)
    # The document links no ledger, which Level 2 includes (AGSC-10-04): that is the
    # only finding, so the directory target itself resolved.
    assert codes(result) == ["AGSC-E202"], result["findings"]


def test_a_profile_link_header_on_the_wrong_media_type_is_still_reported():
    def fetcher(href, dev=False):
        with open(case("good"), "rb") as handle:
            return href, {
                "content-type": "application/json",
                "link": '<https://w3id.org/agentic-system-core/profile/agentic-knowledge>; '
                        'rel="profile"',
            }, handle.read()

    result, _ = wellknown.validate("https://node.example/.well-known/knowledge-linkset",
                                   allow_network=True, fetcher=fetcher)
    assert codes(result) == ["AGSC-E201"]
    assert "is not application/linkset+json" in result["findings"][0]["message"]


def test_an_extra_top_member_with_no_usable_linkset_stops_there(tmp_path):
    path = tmp_path / "knowledge-linkset"
    path.write_bytes(b'{"extra":1,"linkset":{}}\n')
    result, _ = wellknown.validate(str(path))
    assert codes(result) == ["AGSC-E201"]


def test_a_title_star_attribute_must_be_an_array(tmp_path):
    root = tmp_path / ".well-known"
    root.mkdir()
    document = {"linkset": [{"anchor": "https://node.example/",
                             "license": [{"href": "https://node.example/legal/",
                                          "title*": "not an array"}]}]}
    (root / "knowledge-linkset").write_bytes(
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
    result, _ = wellknown.validate(str(root / "knowledge-linkset"))
    assert codes(result) == ["AGSC-E201"]
    assert "title*" in result["findings"][0]["message"]


def test_the_first_document_is_told_when_it_does_not_name_its_peer():
    result, _ = wellknown.validate(case("peer-mutual"), peer=case("peer-not-mutual"))
    assert codes(result) == ["AGSC-E907", "AGSC-E907"]
    assert {one["file"] for one in result["findings"]} == \
        {case("peer-mutual"), case("peer-not-mutual")}
