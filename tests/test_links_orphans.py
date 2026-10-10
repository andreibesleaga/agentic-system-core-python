"""The orphan warnings of AGSC-03-10, as the ``links`` area reports them."""

import copy

from agentic_system_core.areas import AREA_RUNNERS
from agentic_system_core.areas.links_area import orphans
from conftest import VECTORS


def vector(identifier):
    import json
    for path in sorted((VECTORS / "links").glob("%s-*.json" % identifier)):
        return json.loads(path.read_text(encoding="utf-8"))
    raise AssertionError("no case %s" % identifier)


def test_the_orphan_case_passes_and_names_four_orphans_in_slug_order():
    data = vector("links-0009")
    assert AREA_RUNNERS["links"](data)["status"] == "pass"
    assert [one["slug"] for one in orphans(data["input"]["items"])] == ["empty", "lonely", "mentioner", "target"]


def test_a_computed_inverse_counts_as_inbound_and_an_inline_link_does_not():
    items = [
        {"slug": "user", "type": "concept", "uses": ["used"]},
        {"slug": "used", "type": "concept"},
        {"body": "See [used](used).", "slug": "reader", "type": "concept"},
    ]
    assert orphans(items) == [{"code": "AGSC-E305", "slug": "reader"}]


def test_a_cluster_an_item_lists_is_not_an_orphan():
    items = [
        {"slug": "kept", "type": "cluster"},
        {"clusters": ["kept"], "slug": "member", "type": "concept"},
    ]
    assert orphans(items) == []


def test_a_wrong_warning_list_fails_the_case():
    data = copy.deepcopy(vector("links-0009"))
    data["expected"]["warnings"] = data["expected"]["warnings"][:-1]
    assert AREA_RUNNERS["links"](data)["status"] == "fail"
