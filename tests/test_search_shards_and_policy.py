"""The sharded search index (AGSC-06-21) and the page policy by containment
(AGSC-06-17), as the build area runs them: build-0018 and build-0019."""

import copy
import json

from agentic_system_core import site
from agentic_system_core.areas import AREA_RUNNERS
from agentic_system_core.areas.build_area import admits_inline_script
from agentic_system_core.jcs import canonicalize
from conftest import VECTORS


def vector(identifier):
    for path in VECTORS.rglob("*.json"):
        data = json.loads(path.read_bytes().decode("utf-8"))
        if data["id"] == identifier:
            return data
    raise KeyError(identifier)


def items(count):
    return [{"slug": "n-%04d" % i, "title": "Note %04d" % i} for i in range(count, 0, -1)]


def test_at_or_below_the_bound_search_json_is_the_whole_index():
    files = site.search_files(items(3), per_shard=3)
    assert [path for path, _ in files] == ["/search.json"]
    assert files[0][1] == site.search_index(items(3))


def test_above_the_bound_search_json_is_the_manifest_and_postings_are_local():
    files = dict(site.search_files(items(5), per_shard=2))
    assert list(files) == ["/search.json", "/search-01.json", "/search-02.json", "/search-03.json"]
    assert canonicalize(files["/search.json"]) == \
        '{"docs_total":5,"shards":["/search-01.json","/search-02.json","/search-03.json"]}'
    assert [doc["slug"] for doc in files["/search-02.json"]["docs"]] == ["n-0003", "n-0004"]
    assert files["/search-02.json"]["terms"]["note"] == [0, 1]
    assert files["/search-03.json"]["terms"] == {"0005": [0], "note": [0]}


def test_the_default_bound_is_five_hundred_items():
    assert [path for path, _ in site.search_files(items(500))] == ["/search.json"]
    assert len(site.search_files(items(501))) == 3


def test_the_page_policy_holds_the_five_directives_of_the_rule():
    names = [part.split()[0] for part in site.CSP.split(";")]
    assert names == ["default-src", "script-src", "style-src", "img-src", "connect-src"]


def test_build_0018_and_build_0019_pass():
    for identifier in ("build-0018", "build-0019"):
        data = vector(identifier)
        assert AREA_RUNNERS["build"](data) == {"status": "pass", "detail": ""}, identifier


def test_a_policy_missing_a_directive_or_admitting_inline_script_fails(monkeypatch):
    data = vector("build-0018")
    monkeypatch.setattr(site, "CSP", "default-src 'none'; script-src 'self'")
    assert AREA_RUNNERS["build"](data)["status"] == "fail"
    monkeypatch.setattr(site, "CSP", site.CSP + "; style-src 'self'; img-src 'self'; "
                        "connect-src 'self'; script-src-elem 'self' 'unsafe-inline'")
    assert AREA_RUNNERS["build"](data)["status"] == "fail"


def test_the_policy_expectations_are_each_checked():
    data = vector("build-0018")
    for key, value in (("admits_inline_script", True), ("whole_string_asserted", True),
                       ("route", "/pages/*.md"), ("zz", 1)):
        changed = copy.deepcopy(data)
        changed["expected"]["content_security_policy"][key] = value
        assert AREA_RUNNERS["build"](changed)["status"] == "fail", key
    changed = copy.deepcopy(data)
    changed["expected"]["content_security_policy"]["contains"].append("worker-src 'self'")
    assert AREA_RUNNERS["build"](changed)["status"] == "fail"


def test_inline_script_sources_are_recognised():
    admits = admits_inline_script
    assert admits("default-src 'none'; script-src 'self'") is False
    assert admits("default-src 'self' 'unsafe-inline'") is True
    assert admits("script-src 'self' 'nonce-abc'") is True
    assert admits("script-src 'self'; script-src-attr 'unsafe-hashes'") is True
    assert admits("script-src 'self' 'sha256-AAAA'") is True


def test_shards_in_input_order_or_global_postings_fail():
    data = vector("build-0019")
    wrong = copy.deepcopy(data)
    wrong["expected"]["shards"][1]["output"] = \
        wrong["expected"]["shards"][1]["output"].replace("[0,1]", "[500,501]")
    assert AREA_RUNNERS["build"](wrong)["status"] == "fail"
    for key, value in (("docs_count", 499), ("first_slug", "n-0502"), ("last_slug", "n-0499"),
                       ("path", "/search-1.json"), ("zz", 1)):
        changed = copy.deepcopy(data)
        changed["expected"]["shards"][0][key] = value
        assert AREA_RUNNERS["build"](changed)["status"] == "fail", key
    changed = copy.deepcopy(data)
    changed["expected"]["output"] = changed["expected"]["output"].replace("502", "500")
    assert AREA_RUNNERS["build"](changed)["status"] == "fail"
