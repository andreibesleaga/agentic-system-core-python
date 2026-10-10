"""The discovery-file checker, over the fixture set and the two sites' files."""

import json

import pytest

from agentic_system_core import wellknown
from agentic_system_core.net import TransportError
from conftest import SITE_DOCUMENTS, WELLKNOWN, case


def codes(result):
    return sorted(one["code"] for one in result["findings"])


#: The cross-origin and caching headers a conforming node sends on its discovery
#: document (AGSC-11-03, AGSC-11-05), merged into the served headers of the tests below
#: that are about something else.
WELL_SERVED = {
    "access-control-allow-origin": "*",
    "access-control-expose-headers": "Link, ETag, Content-Type",
    "cache-control": "no-cache",
    "etag": '"e"',
}


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

    def fetcher(href, dev=False, cap=None):
        headers = dict(WELL_SERVED, **{"content-type":
                       'application/linkset+json;profile="https://w3id.org/agentic-system-core/'
                       'profile/agentic-knowledge"'})
        if href not in served:
            raise TransportError("AGSC-E907", "HTTP 404 for %s" % href)
        return href, headers, served[href]

    result, reads = wellknown.validate(
        "https://node.example/.well-known/knowledge-linkset", level=2,
        allow_network=True, fetcher=fetcher)
    assert result["status"] == "pass", result["findings"]
    assert reads > 1


def test_a_served_document_with_the_wrong_media_type_is_e201():
    def fetcher(href, dev=False, cap=None):
        with open(case("good"), "rb") as handle:
            return href, dict(WELL_SERVED, **{"content-type": "application/json"}), handle.read()

    result, _ = wellknown.validate("https://node.example/.well-known/knowledge-linkset",
                                   allow_network=True, fetcher=fetcher)
    assert "AGSC-E201" in codes(result)


def test_the_profile_may_be_carried_by_a_link_header():
    def fetcher(href, dev=False, cap=None):
        with open(case("good"), "rb") as handle:
            return href, dict(WELL_SERVED, **{
                "content-type": "application/linkset+json",
                "link": '<https://w3id.org/agentic-system-core/profile/agentic-knowledge>; '
                        'rel="profile"',
            }), handle.read()

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
    def fetcher(href, dev=False, cap=None):
        with open(case("good"), "rb") as handle:
            return href, dict(WELL_SERVED, **{
                "content-type": "application/json",
                "link": '<https://w3id.org/agentic-system-core/profile/agentic-knowledge>; '
                        'rel="profile"',
            }), handle.read()

    result, _ = wellknown.validate("https://node.example/.well-known/knowledge-linkset",
                                   allow_network=True, fetcher=fetcher)
    assert codes(result) == ["AGSC-E201"]
    assert "is not application/linkset+json" in result["findings"][0]["message"]


PROFILE_LINK = ('<https://w3id.org/agentic-system-core/profile/agentic-knowledge>; '
                'rel="profile"')


def test_the_media_type_is_required_even_when_the_profile_link_header_is_sent():
    # AGSC-06-07, AGSC-09-93: the Link header replaces only the profile parameter,
    # never the media type.
    state = wellknown._media_type_state({"content-type": "application/json", "link": PROFILE_LINK})
    assert state["ok"] is False
    assert state["essence"] == "application/json"
    assert wellknown._media_type_state({
        "content-type": 'application/json; profile="https://w3id.org/agentic-system-core'
                        '/profile/agentic-knowledge"'})["ok"] is False
    assert wellknown._media_type_state({"content-type": "application/linkset+json",
                                        "link": PROFILE_LINK})["ok"] is True


def _media_findings(content_type, link=None):
    def fetcher(href, dev=False, cap=None):
        headers = dict(WELL_SERVED, **{"content-type": content_type})
        if link is not None:
            headers["link"] = link
        with open(case("good"), "rb") as handle:
            return href, headers, handle.read()

    result, _ = wellknown.validate("https://node.example/.well-known/knowledge-linkset",
                                   allow_network=True, fetcher=fetcher)
    return [one for one in result["findings"] if "(AGSC-06-07)" in one["message"]]


def test_one_media_type_finding_says_which_half_is_missing():
    found = _media_findings("application/json", PROFILE_LINK)
    assert [one["code"] for one in found] == ["AGSC-E201"]
    assert found[0]["message"].startswith(
        'media type "application/json" is not application/linkset+json; the profile Link '
        'header replaces only the profile parameter, never the media type')
    for content_type in ("application/json",
                         'application/json; profile="https://w3id.org/agentic-system-core/'
                         'profile/agentic-knowledge"'):
        found = _media_findings(content_type)
        assert [one["code"] for one in found] == ["AGSC-E201"]
        assert found[0]["message"].startswith(
            'media type "application/json" is not application/linkset+json and no profile is '
            'carried: ')
    found = _media_findings("application/linkset+json")
    assert [one["code"] for one in found] == ["AGSC-E201"]
    assert found[0]["message"].startswith("media type application/linkset+json carries no profile: ")
    assert found[0]["message"].endswith('or a Link header with rel="profile" (AGSC-06-07)')
    assert _media_findings("application/linkset+json", PROFILE_LINK) == []


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


def _served_as(final_url):
    """A fetcher that serves the `good` case (anchored at node.example) as if read from
    `final_url` after redirects."""
    def fetcher(href, dev=False, cap=None):
        with open(case("good"), "rb") as handle:
            return final_url, dict(WELL_SERVED, **{
                "content-type": 'application/linkset+json;profile="https://w3id.org/'
                                'agentic-system-core/profile/agentic-knowledge"',
            }), handle.read()
    return fetcher


def test_a_document_served_from_another_origin_than_its_anchor_is_e907():
    # AGSC-06-08 (amended 2026-10-02 for 1.0.0): a copy of node.example's document served
    # by another origin is not that origin's discovery document.
    url = "https://copy.example/.well-known/knowledge-linkset"
    result, _ = wellknown.validate(url, allow_network=True, fetcher=_served_as(url))
    assert "AGSC-E907" in codes(result)


def test_the_origin_judged_is_the_one_finally_read_after_redirects():
    own = "https://node.example/.well-known/knowledge-linkset"
    result, _ = wellknown.validate("https://alias.example/.well-known/knowledge-linkset",
                                   allow_network=True, fetcher=_served_as(own))
    assert "AGSC-E907" not in codes(result)
    moved = "https://copy.example/.well-known/knowledge-linkset"
    result, _ = wellknown.validate(own, allow_network=True, fetcher=_served_as(moved))
    assert "AGSC-E907" in codes(result)


# ------------------------------------------------- AGSC-09-93, amended 2026-10-06 for 1.0.0
# Given a URL, the checker reads the response headers of the discovery document and of
# every same-origin public artefact it fetches, and checks the rules on cross-origin
# reading (AGSC-11-03) and caching (AGSC-11-05): a missing header or value is AGSC-E202,
# a forbidden one AGSC-E201; errors at Level 2 and above, warnings below.  Until then
# only the media type was read, so a node that served none of these headers passed.
# The engine's tools/validate-wellknown
# does the same.

GOOD_URL = "https://node.example/.well-known/knowledge-linkset"
NO_CACHE_PATHS = ("/.well-known/knowledge-linkset", "/now.md", "/ledger.jsonl")


def _good_served():
    with open(case("good"), "rb") as handle:
        body = handle.read()
    return {
        GOOD_URL: body,
        "https://node.example/llms.txt": (WELLKNOWN / "good" / "llms.txt").read_bytes(),
        "https://node.example/graph.jsonld": (WELLKNOWN / "good" / "graph.jsonld").read_bytes(),
        "https://node.example/ledger.jsonl": (WELLKNOWN / "good" / "ledger.jsonl").read_bytes(),
    }


def _full_headers(href):
    """The header set a conforming public node sends for one of its artefacts."""
    headers = {
        "access-control-allow-origin": "*",
        "access-control-expose-headers": "Link, ETag, Content-Type",
        "etag": '"%s"' % href.rsplit("/", 1)[-1],
    }
    if href == GOOD_URL:
        headers["content-type"] = ('application/linkset+json; profile="https://w3id.org/'
                                   'agentic-system-core/profile/agentic-knowledge"')
    if href.endswith(NO_CACHE_PATHS):
        headers["cache-control"] = "no-cache"
    return headers


def _serving(change=lambda href, headers: headers, served=None):
    served = served if served is not None else _good_served()
    caps = []

    def fetcher(href, dev=False, cap=None):
        caps.append((href, cap))
        if href not in served:
            raise TransportError("AGSC-E907", "HTTP 404 for %s" % href)
        return href, change(href, _full_headers(href)), served[href]
    fetcher.caps = caps
    return fetcher


def _about(result, rule):
    return [one for one in result["findings"] if rule in one["message"]]


def test_a_node_served_with_the_full_header_set_passes_at_level_2():
    result, _ = wellknown.validate(GOOD_URL, level=2, allow_network=True, fetcher=_serving())
    assert result["status"] == "pass", result["findings"]
    assert result["findings"] == []


def test_targets_are_fetched_with_the_federation_cap_and_the_document_with_one_mebibyte():
    # A target is held to federation.max_bytes' default (AGSC-11-01).
    from agentic_system_core import net
    fetcher = _serving()
    wellknown.validate(GOOD_URL, level=2, allow_network=True, fetcher=fetcher)
    caps = dict(fetcher.caps)
    assert caps[GOOD_URL] == net.MAX_BYTES
    assert caps["https://node.example/graph.jsonld"] == net.TARGET_MAX_BYTES


def test_no_expose_headers_is_e202_on_the_document_and_on_every_target_read():
    def change(href, headers):
        del headers["access-control-expose-headers"]
        return headers
    result, _ = wellknown.validate(GOOD_URL, level=2, allow_network=True, fetcher=_serving(change))
    hits = _about(result, "AGSC-11-03")
    assert len(hits) > 1, result["findings"]
    assert all(one["code"] == "AGSC-E202" and one["severity"] == "error" for one in hits)
    assert any("/.well-known/knowledge-linkset" in one["message"] for one in hits)
    assert any("/graph.jsonld" in one["message"] for one in hits)


def test_below_level_2_a_header_shortfall_is_a_warning():
    def change(href, headers):
        del headers["access-control-expose-headers"]
        return headers
    result, _ = wellknown.validate(GOOD_URL, level=0, allow_network=True, fetcher=_serving(change))
    assert result["status"] == "pass", result["findings"]
    hits = _about(result, "AGSC-11-03")
    assert hits and all(one["severity"] == "warn" and one["code"] == "AGSC-E202" for one in hits)


def test_a_narrowed_origin_a_short_exposed_list_and_credentials_are_each_reported():
    def change(href, headers):
        if href.endswith("/graph.jsonld"):
            headers["access-control-expose-headers"] = "Link, Content-Type"
        if href.endswith("/llms.txt"):
            headers["access-control-allow-origin"] = "https://example.org"
        if href == GOOD_URL:
            headers["access-control-allow-credentials"] = "true"
        return headers
    result, _ = wellknown.validate(GOOD_URL, level=2, allow_network=True, fetcher=_serving(change))
    hits = _about(result, "AGSC-11-03")

    def one(*words):
        found = [h for h in hits if all(w in h["message"] for w in words)]
        assert found, (words, hits)
        return found[0]["code"]
    assert one("graph.jsonld", "ETag") == "AGSC-E202"
    assert one("llms.txt", "Access-Control-Allow-Origin") == "AGSC-E201"
    assert one("knowledge-linkset", "Access-Control-Allow-Credentials") == "AGSC-E201"


def test_no_etag_no_no_cache_and_immutable_are_reported():
    def change(href, headers):
        if href.endswith("/graph.jsonld"):
            del headers["etag"]
        if href == GOOD_URL:
            del headers["cache-control"]
        if href.endswith("/llms.txt"):
            headers["cache-control"] = "public, max-age=31536000, immutable"
        return headers
    result, _ = wellknown.validate(GOOD_URL, level=2, allow_network=True, fetcher=_serving(change))
    hits = _about(result, "AGSC-11-05")
    codes_by = {("graph.jsonld" in h["message"], "knowledge-linkset" in h["message"],
                 "llms.txt" in h["message"]): h["code"] for h in hits}
    assert codes_by[(True, False, False)] == "AGSC-E202", hits
    assert codes_by[(False, True, False)] == "AGSC-E202", hits
    assert codes_by[(False, False, True)] == "AGSC-E201", hits


def test_a_restricted_node_is_asked_the_cross_origin_pair_on_its_document_alone():
    # AGSC-11-20: a restricted node applies the wildcard to its discovery document only.
    import base64
    import hashlib

    def digest(data):
        return "sha-256=:%s:" % base64.b64encode(hashlib.sha256(data).digest()).decode()
    graph, llms = b'{"@graph":[]}\n', b"# A node\n"
    context = {
        "alternate": [{"digest": [digest(llms)], "href": "https://node.example/llms.txt",
                       "type": "text/plain"}],
        "anchor": "https://node.example/",
        "describedby": [{"agsc-generated-at": ["2026-01-01T00:00:00Z"],
                         "agsc-spec-version": ["1.0.0-rc.7"], "agsc-visibility": ["restricted"],
                         "digest": [digest(graph)], "href": "https://node.example/graph.jsonld",
                         "type": "application/ld+json"}],
        "https://w3id.org/agentic-system-core/rel#access": [
            {"href": "https://node.example/access/", "type": "text/html"}],
    }
    served = {GOOD_URL: json.dumps({"linkset": [context]}, separators=(",", ":"),
                                   sort_keys=True).encode() + b"\n",
              "https://node.example/graph.jsonld": graph, "https://node.example/llms.txt": llms}

    def gated(href, headers):
        if href != GOOD_URL:
            del headers["access-control-allow-origin"]
            del headers["access-control-expose-headers"]
        return headers
    result, _ = wellknown.validate(GOOD_URL, level=2, allow_network=True,
                                   fetcher=_serving(gated, served))
    assert result["findings"] == [], result["findings"]

    def bare(href, headers):
        del headers["access-control-allow-origin"]
        del headers["access-control-expose-headers"]
        return headers
    result, _ = wellknown.validate(GOOD_URL, level=2, allow_network=True,
                                   fetcher=_serving(bare, served))
    hits = _about(result, "AGSC-11-03")
    assert len(hits) == 2 and all("knowledge-linkset" in one["message"] for one in hits), hits


#: AGSC-11-20: a restricted node carries exactly one rel#access link.
_ACCESS_REL = "https://w3id.org/agentic-system-core/rel#access"


def _level0_view(access=(), restricted=True):
    """The Level-0 view of a node at node.example, with the given access-link targets."""
    described = {"href": "https://node.example/graph.jsonld", "type": "application/ld+json"}
    if restricted:
        described.update({"agsc-generated-at": ["2026-09-16T00:00:00Z"],
                          "agsc-spec-version": ["1.0.0"], "agsc-visibility": ["restricted"]})
    context = {
        "alternate": [{"href": "https://node.example/llms.txt", "type": "text/plain"}],
        "anchor": "https://node.example/",
        "describedby": [described],
        "license": [{"href": "https://node.example/legal/"}],
    }
    if access:
        context[_ACCESS_REL] = [{"agsc-access": ["credential"], "href": href} for href in access]
    return {"linkset": [context]}


def _access_findings(document, level=0):
    findings = []
    wellknown.check(wellknown.from_value(document), level, findings)
    return findings, [one for one in findings if "rel#access" in one["message"]]


def test_a_restricted_node_with_no_access_link_is_e202():
    findings, about = _access_findings(_level0_view())
    assert [(one["code"], one["severity"]) for one in about] == [("AGSC-E202", "error")]
    assert "exactly one" in about[0]["message"] and "AGSC-11-20" in about[0]["message"]
    assert findings == about, findings


def test_a_restricted_node_with_two_access_links_is_e210():
    findings, about = _access_findings(_level0_view(
        access=("https://node.example/access/", "https://node.example/access/other/")))
    assert [(one["code"], one["severity"]) for one in about] == [("AGSC-E210", "error")]
    assert "exactly one" in about[0]["message"] and " 2 " in about[0]["message"]
    assert findings == about, findings


def test_a_restricted_node_with_one_access_link_passes():
    findings, _ = _access_findings(_level0_view(access=("https://node.example/access/",)))
    assert findings == []


def test_the_access_link_is_asked_at_every_level_and_never_of_a_public_node():
    for level in (1, 2, 3):
        _, about = _access_findings(_level0_view(), level)
        assert [one["code"] for one in about] == ["AGSC-E202"], level
    findings, _ = _access_findings(_level0_view(restricted=False))
    assert findings == []


def test_the_two_checkers_word_the_access_findings_alike():
    # The same message as the Node tool's, so an operator reads one text whichever
    # checker ran (AGSC-09-93).
    _, missing = _access_findings(_level0_view())
    _, repeated = _access_findings(_level0_view(
        access=("https://node.example/access/", "https://node.example/access/other/")))
    assert missing[0]["message"] == (
        "a restricted node carries exactly one rel#access link, naming where a reader "
        "obtains credentials; this one carries none (AGSC-11-20)")
    assert repeated[0]["message"] == (
        "a restricted node carries exactly one rel#access link, naming where a reader "
        "obtains credentials; this one carries 2 (AGSC-11-20)")
