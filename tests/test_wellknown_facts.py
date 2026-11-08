"""The 1.1 checks of the discovery-file checker that read what the document links.

Each is the twin of a check the engine's ``tools/validate-wellknown`` gained in 1.1:
the chunk count, set commitment and digest of the chunks surface link (AGSC-06-44,
AGSC-09-93 (b)), the ledger length (AGSC-09-93 (c)), the agent card on the node's own
origin (AGSC-11-16), the ``describedby`` link in the ``Link`` header of ``/``
(AGSC-06-40) and the request budget (AGSC-11-10(c)).  The fixture cases are the ones
``tests/test_equivalence.py`` also runs through the engine's tool; here the verdict is
stated.  No network: a URL is served by an injected fetcher.
"""

import json

import pytest

from agentic_system_core import cli, net, wellknown, wellknown_facts
from agentic_system_core.net import TransportError
from conftest import VECTORS, WELLKNOWN, case


def found(name, level):
    result, _ = wellknown.validate(case(name), level=level)
    return result["status"], sorted((one["code"], one["severity"]) for one in result["findings"])


@pytest.mark.parametrize("name,level,status,findings", [
    ("chunks-facts-complete", 2, "pass", []),
    ("chunks-facts-missing", 0, "pass", []),
    ("chunks-facts-missing", 2, "fail", [("AGSC-E202", "error")] * 3),
    ("chunks-facts-earlier", 2, "pass", []),
    ("chunks-count-wrong", 1, "pass", []),
    ("chunks-count-wrong", 2, "fail", [("AGSC-E201", "error")]),
    ("chunks-set-wrong", 2, "fail", [("AGSC-E201", "error")]),
    ("chunks-sharded", 2, "pass", []),
    ("chunks-lines-not-json", 2, "fail", [("AGSC-E201", "error")]),
    ("ledger-length-wrong", 0, "fail", [("AGSC-E201", "error")]),
    ("chunks-credential-not-served", 2, "pass", []),
    ("card-not-served", 0, "pass", [("AGSC-E210", "warn")]),
    ("card-served", 2, "pass", []),
    ("card-other-origin", 2, "pass", []),
])
def test_each_new_fixture_gets_the_engine_verdict(name, level, status, findings):
    assert found(name, level) == (status, findings)


def test_a_chunk_count_off_by_one_is_named_in_the_message():
    result, _ = wellknown.validate(case("chunks-count-wrong"), level=2)
    assert "is not the 3 lines of the fetched file" in result["findings"][0]["message"]


def test_the_three_missing_facts_are_each_named():
    result, _ = wellknown.validate(case("chunks-facts-missing"), level=2)
    named = sorted(one["message"].split(" carries no ")[1].split(" ")[0]
                   for one in result["findings"])
    assert named == ["agsc-chunk-count", "agsc-chunk-set", "digest"]


def test_a_shard_that_is_not_served_makes_the_lines_unreadable():
    data = (WELLKNOWN / "chunks-sharded" / "chunks.jsonl").read_bytes()
    target = {"agsc-chunk-count": ["3"]}

    class Missing(object):
        kind = "file"

        def resolve_target(self, href, anchor, checked=True):
            raise TransportError("AGSC-E901", "target not found on disk: /chunks-0001.jsonl")
    reported = []
    wellknown_facts.chunk_facts_findings(target, "https://example.org/chunks.jsonl", data,
                                         "https://example.org/", Missing(), 2,
                                         lambda *one, **_: reported.append(one))
    assert [one[0] for one in reported] == ["AGSC-E201"]
    assert "cannot be read" in reported[0][1]


@pytest.mark.parametrize("value,text", [
    ("a", "a"), (None, "null"), (True, "true"), (False, "false"), (3, "3"), (3.0, "3"),
    (2.5, "2.5"), ([1, None, "x"], "1,,x"), ({"k": 1}, "[object Object]"),
])
def test_an_id_is_joined_as_the_engine_writes_it(value, text):
    assert wellknown_facts._js_string(value) == text


def test_a_line_without_an_id_or_not_an_object_reads_as_undefined_and_null_is_refused():
    assert wellknown_facts._chunk_id({"no": "id"}) == "undefined"
    assert wellknown_facts._chunk_id(["a"]) == "undefined"
    with pytest.raises(ValueError):
        wellknown_facts._chunk_id(None)
    with pytest.raises(ValueError):
        wellknown_facts._lines(b"NaN\n")


@pytest.mark.parametrize("declared,later", [
    ("1.1.0", True), ("1.99.0", True), ("2.0.0", True), ("1.0.0", False), ("0.9", False),
    (None, False), ("v1.1", False),
])
def test_the_facts_are_required_from_1_1(declared, later):
    assert wellknown_facts.from_one_one(declared) is later


# ------------------------------------------------------------------ disc-0033 by value
def test_disc_0033_runs_in_memory_as_from_disk():
    vector = json.loads((VECTORS / "discovery" /
                         "disc-0033-chunks-surface-link-carries-digest-count-and-set.json")
                        .read_text(encoding="utf-8"))
    verdicts = {}
    for given in vector["input"]["cases"]:
        findings = []
        source = wellknown.from_build(given["document"], given["files"])
        wellknown.check(source, given["level"], findings)
        verdicts[given["name"]] = sorted(set(one["code"] for one in findings))
    assert verdicts == {"complete": [], "missing": ["AGSC-E202"], "earlier-document": []}


def test_a_build_held_in_memory_names_a_missing_route_and_stays_on_its_origin():
    source = wellknown.from_build({"linkset": []}, {"/a.txt": "a"})
    assert source.resolve_target("https://n.example/a.txt", "https://n.example/") == b"a"
    assert source.resolve_target("https://other.example/a.txt", "https://n.example/") is None
    with pytest.raises(TransportError) as error:
        source.resolve_target("https://n.example/b/", "https://n.example/")
    assert error.value.code == "AGSC-E901" and "/b/index.html" in error.value.message


# ------------------------------------------------------------------ AGSC-06-40, home page
DESCRIBEDBY = '</.well-known/knowledge-linkset>; rel="describedby"; type="application/linkset+json"'


@pytest.mark.parametrize("values,warned", [
    ([DESCRIBEDBY], False),
    (DESCRIBEDBY, False),
    (['<https://a.example/.well-known/knowledge-linkset>; rel="describedby"'], False),
    (["</.well-known/knowledge-linkset>; rel=describedby"], False),
    (['</.well-known/knowledge-linkset>; rel="DescribedBy item"'], False),
    (['</graph.jsonld>; rel="describedby"', DESCRIBEDBY], False),
    (['</graph.jsonld>; rel="describedby"; type="application/ld+json"'], True),
    (['</.well-known/knowledge-linkset>; rel="linkset"'], True),
    (["</.well-known/knowledge-linkset>"], True),
    (['<https://b.example/.well-known/knowledge-linkset>; rel="describedby"'], True),
    ([], True),
    (None, True),
])
def test_the_home_link_header_must_carry_the_describedby_link(values, warned):
    findings = wellknown_facts.home_link_findings(values, anchor="https://a.example/")
    assert [(one["code"], one["severity"]) for one in findings] == \
        ([("AGSC-E202", "warn")] if warned else [])


GOOD_URL = "https://node.example/.well-known/knowledge-linkset"
HOME_URL = "https://node.example/"


def _served(home_headers=None):
    with open(case("good"), "rb") as handle:
        document = handle.read()
    served = {GOOD_URL: document}
    requested = []

    def fetcher(href, dev=False, cap=None):
        requested.append(href)
        if href == HOME_URL and home_headers is not None:
            return href, home_headers, b"<!doctype html>\n"
        if href not in served:
            raise TransportError("AGSC-E907", "HTTP 404 for %s" % href)
        return href, {"content-type": 'application/linkset+json; profile="https://w3id.org/'
                                      'agentic-system-core/profile/agentic-knowledge"'}, served[href]
    fetcher.requested = requested
    return fetcher


def _home_findings(result):
    return [(one["code"], one["severity"], one["file"]) for one in result["findings"]
            if "Link header of /" in one["message"]]


def test_given_a_url_the_home_page_is_read_and_its_link_header_judged():
    fetcher = _served({"link": DESCRIBEDBY})
    result, reads = wellknown.validate(GOOD_URL, allow_network=True, fetcher=fetcher)
    assert HOME_URL in fetcher.requested
    assert _home_findings(result) == []
    # The home page is a request, not one of the files the run reads.
    assert reads == 1 + len([one for one in fetcher.requested if one not in (HOME_URL, GOOD_URL)])
    result, _ = wellknown.validate(GOOD_URL, allow_network=True, fetcher=_served({}))
    assert _home_findings(result) == [("AGSC-E202", "warn", HOME_URL)]


def test_a_home_page_that_cannot_be_read_is_a_warning_not_a_failure():
    result, _ = wellknown.validate(GOOD_URL, allow_network=True, fetcher=_served(None))
    assert _home_findings(result) == [("AGSC-E202", "warn", HOME_URL)]
    assert "could not be read" in [one["message"] for one in result["findings"]
                                   if one["file"] == HOME_URL][0]


def test_a_file_has_no_home_page_to_read():
    result, _ = wellknown.validate(case("good"))
    assert _home_findings(result) == []


# ------------------------------------------------------------------ AGSC-11-10(c), budget
def test_the_budget_is_spent_once_per_request_and_the_next_one_is_e906():
    budget = net.RequestBudget(2)
    budget.spend()
    budget.spend()
    with pytest.raises(TransportError) as error:
        budget.spend()
    assert error.value.code == "AGSC-E906" and "request budget of 2 spent" in error.value.message


def test_fetch_spends_the_budget_on_every_redirect(monkeypatch):
    replies = iter([(302, {"location": "/b"}, b""), (200, {}, b"{}")])
    monkeypatch.setattr(net, "fetch_once", lambda href, dev=False, cap=net.MAX_BYTES: next(replies))
    budget = net.RequestBudget(5)
    net.fetch("https://example.org/a", budget=budget)
    assert budget.spent == 2
    replies = iter([(302, {"location": "/b"}, b""), (200, {}, b"{}")])
    with pytest.raises(TransportError) as error:
        net.fetch("https://example.org/a", budget=net.RequestBudget(1))
    assert error.value.code == "AGSC-E906"


def test_a_spent_budget_stops_the_run_with_e906():
    # The document is the one request the budget allows; the llms-txt surface target
    # is refused with AGSC-E906, and the home page, read last, cannot be read.
    fetcher = _served({"link": DESCRIBEDBY})
    result, _ = wellknown.validate(GOOD_URL, allow_network=True, max_requests=1, fetcher=fetcher)
    assert fetcher.requested == [GOOD_URL]
    assert ("AGSC-E906", "error") in [(one["code"], one["severity"]) for one in result["findings"]]
    assert _home_findings(result) == [("AGSC-E202", "warn", HOME_URL)]
    result, _ = wellknown.validate(GOOD_URL, allow_network=True, max_requests=500,
                                   fetcher=_served({"link": DESCRIBEDBY}))
    assert "AGSC-E906" not in [one["code"] for one in result["findings"]]


def test_the_budget_is_shared_with_the_peer():
    budget_runs = []

    def fetcher(href, dev=False, cap=None):
        budget_runs.append(href)
        raise TransportError("AGSC-E907", "HTTP 404 for %s" % href)
    result, _ = wellknown.validate(GOOD_URL, peer="https://peer.example/.well-known/x",
                                   allow_network=True, max_requests=1, fetcher=fetcher)
    assert budget_runs == [GOOD_URL]
    assert sorted(one["code"] for one in result["findings"]) == ["AGSC-E906", "AGSC-E907"]


def test_the_built_in_reader_is_handed_the_budget_and_an_injected_one_keeps_its_call(monkeypatch):
    calls = []
    monkeypatch.setattr(net, "fetch_once", lambda href, dev=False, cap=net.MAX_BYTES:
                        calls.append(href) or (200, {}, b"{}"))
    budget = net.RequestBudget(3)
    net.counted(net.fetch, "https://example.org/", False, net.MAX_BYTES, budget)
    assert budget.spent == 1 and calls == ["https://example.org/"]
    net.counted(lambda href, dev, cap: (href, {}, b""), "https://example.org/", False, 1, budget)
    assert budget.spent == 2


def test_a_repeated_header_field_is_read_as_one_joined_value():
    fields = net._header_fields([("Link", "<a>; rel=x"), ("ETag", '"e"'), ("link", "<b>; rel=y")])
    assert fields == {"link": "<a>; rel=x, <b>; rel=y", "etag": '"e"'}


def _cli(argv):
    import io
    out, err = io.StringIO(), io.StringIO()
    return cli.main(argv, out=out, err=err), out.getvalue(), err.getvalue()


@pytest.mark.parametrize("value", ["0", "2001", "x", "-1", "123456", "1.5", ""])
def test_a_max_requests_outside_one_to_two_thousand_is_a_usage_fault(value):
    code, out, _ = _cli(["validate-wellknown", case("good"), "--max-requests", value, "--json"])
    assert code == 2
    assert json.loads(out)["findings"][0]["code"] == "AGSC-E003"


def test_max_requests_needs_a_value_and_accepts_the_range():
    assert _cli(["validate-wellknown", case("good"), "--max-requests"])[0] == 2
    for value in ("1", "2000", "500"):
        assert _cli(["validate-wellknown", case("good"), "--max-requests", value])[0] == 0


# ------------------------------------------------------------------ AGSC-06-06, /ns/x.y.z/
def test_only_a_versioned_copy_under_ns_may_be_immutable():
    headers = {"etag": '"e"', "cache-control": "public, max-age=31536000, immutable"}
    assert wellknown.header_shortfalls(headers, cors=False, no_cache=False, versioned=True) == []
    flagged = wellknown.header_shortfalls(headers, cors=False, no_cache=False)
    assert [code for code, _ in flagged] == ["AGSC-E201"]
    assert wellknown.VERSIONED.match("/ns/1.0.0/context.jsonld")
    assert not wellknown.VERSIONED.match("/ns/context.jsonld")


def test_the_1_1_attributes_are_known_so_a_newer_document_is_not_warned_about_them():
    for name in ("agsc-chunk-count", "agsc-chunk-set", "agsc-ledger-length"):
        assert name in wellknown.KNOWN_ATTRIBUTES


def test_a_reader_of_another_version_is_named_by_the_caller():
    # disc-0023: the case names its reader; the one constant is only the default.
    with open(case("good"), "rb") as handle:
        document = json.loads(handle.read())
    context = document["linkset"][0]
    context["describedby"][0]["agsc-spec-version"] = ["1.99.0"]
    context["https://w3id.org/agentic-system-core/rel#brief"] = [{"href": "https://node.example/b"}]
    findings = []
    wellknown.check(wellknown.from_value(document), 0, findings, spec_version="1.1.0")
    assert [one["code"] for one in findings] == ["AGSC-E506"]
    findings = []
    wellknown.check(wellknown.from_value(document), 0, findings, spec_version="2.0.0")
    assert "AGSC-E209" in [one["code"] for one in findings]


# ------------------------------------------------------------------ reads that fail
class _Refusing(object):
    """A source whose every read fails with one transport code."""
    kind = "url"

    def __init__(self, code):
        self.code = code

    def resolve_target(self, href, anchor, checked=True):
        raise TransportError(self.code, "refused")


class _Empty(object):
    kind = "memory"

    def resolve_target(self, href, anchor, checked=True):
        return None


def _reports(call):
    reported = []
    call(lambda code, message, severity="error": reported.append((code, severity)))
    return reported


def test_a_ledger_that_cannot_be_read_keeps_its_transport_code_and_none_is_not_judged():
    target = {"agsc-ledger-length": ["1"]}
    href, anchor = "https://n.example/ledger.jsonl", "https://n.example/"
    assert _reports(lambda report: wellknown_facts.ledger_length_findings(
        target, href, anchor, _Refusing("AGSC-E906"), 2, report)) == [("AGSC-E906", "error")]
    assert _reports(lambda report: wellknown_facts.ledger_length_findings(
        target, href, anchor, _Empty(), 2, report)) == []
    # From a URL below Level 2 the ledger is not read at all.
    assert _reports(lambda report: wellknown_facts.ledger_length_findings(
        target, href, anchor, _Refusing("AGSC-E907"), 1, report)) == []


def test_a_card_read_stopped_by_the_budget_is_e906_and_any_other_fault_a_warning():
    href, anchor = "https://n.example/.well-known/agent-card.json", "https://n.example/"
    parsed = wellknown.Url(href)
    assert _reports(lambda report: wellknown_facts.card_target_findings(
        href, parsed, anchor, _Refusing("AGSC-E906"), report)) == [("AGSC-E906", "error")]
    assert _reports(lambda report: wellknown_facts.card_target_findings(
        href, parsed, anchor, _Refusing("AGSC-E907"), report)) == [("AGSC-E210", "warn")]
