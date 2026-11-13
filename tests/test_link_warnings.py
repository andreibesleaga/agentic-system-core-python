"""The four warnings about what an authored Link says (AGSC-03-23 to AGSC-03-26).

``links.link_warnings`` reports AGSC-E313 (an item links to itself), AGSC-E314 (two
relations a pair cannot both hold), AGSC-E315 (a target of a kind the key does not
expect) and AGSC-E316 (a ``supersedes`` target that is still stable), each carried by
the item that authors the key. The engine's ``src/knowledge/links.js`` is the reference;
``links-0010`` to ``links-0017`` and ``links-0020`` are the vectors. Fixed data, no network.
"""

from agentic_system_core import links


def codes(items):
    return sorted((one["slug"], one["code"]) for one in links.link_warnings(items))


def concept(slug, **keys):
    return dict({"slug": slug, "type": "concept"}, **keys)


def test_a_self_link_warns_once_per_key_and_a_cycle_key_does_not():
    items = [concept("a", related=["a"], uses=["a#top"], body="# Top\n"),
             concept("r", requires=["r"])]
    assert codes(items) == [("a", "AGSC-E313"), ("a", "AGSC-E313")]
    found = links.link_warnings(items)
    assert all(one["severity"] == "warn" for one in found)
    assert sorted(one["key"] for one in found) == ["related", "uses"]


def test_the_same_link_is_judged_once():
    assert codes([concept("a", related=["a", "a"])]) == [("a", "AGSC-E313")]


def test_an_incompatible_pair_is_carried_by_the_item_that_authors_the_first_key():
    items = [concept("a1", requires=["b1"], excludes=["b1"]), concept("b1"),
             concept("a5", requires=["b5"]), concept("b5", excludes=["a5"]),
             concept("n1", requires=["m1"], uses=["m1"]), concept("m1")]
    assert codes(items) == [("a1", "AGSC-E314"), ("a5", "AGSC-E314")]


def test_a_target_of_an_unexpected_kind_warns():
    items = [concept("d1", **{"decided-by": ["t1"]}), concept("t1", kind="task"),
             {"slug": "l1", "type": "lesson", "derived-from": ["t1"]},
             concept("b1", broader=["ep"]), {"slug": "ep", "type": "episode"},
             concept("v1", verifies=["g1"]), {"slug": "g1", "type": "gate"}]
    assert codes(items) == [("b1", "AGSC-E315"), ("d1", "AGSC-E315"), ("l1", "AGSC-E315")]


def test_each_expected_target_cell_admits_its_kinds():
    items = [concept("i1", implements=["p1"]), concept("p1", kind="pattern"),
             concept("c1", **{"derived-from": ["t1"]}), concept("t1", kind="task"),
             concept("b1", broader=["l1"]), {"slug": "l1", "type": "lesson"},
             concept("k1", **{"blocked-by": ["t1"]}),
             concept("v1", verifies=["pr"]), {"slug": "pr", "type": "procedure"},
             concept("u1", uses=["pr"], covers=["pr"])]
    assert codes(items) == []


def test_a_related_that_joins_a_cluster_warns_at_either_end():
    group = {"slug": "c1", "type": "cluster"}
    assert codes([concept("a1", related=["c1"]), group]) == [("a1", "AGSC-E315")]
    assert codes([dict(group, related=["a1"]), concept("a1")]) == [("c1", "AGSC-E315")]
    # Near misses: another key whose cell reads any stays silent at a cluster.
    assert codes([concept("a1", uses=["c1"], covers=["c1"]), group]) == []


def test_superseding_a_stable_item_warns_and_a_replaced_one_does_not():
    items = [concept("n1", supersedes=["o1"]), concept("o1"),
             concept("n2", supersedes=["o2"]), concept("o2", status="stable"),
             concept("n3", supersedes=["o3"]), concept("o3", status="deprecated"),
             concept("n4", supersedes=["o4"]), concept("o4", status="retired"),
             concept("n5", supersedes=["o5"]), concept("o5", status="draft")]
    assert codes(items) == [("n1", "AGSC-E316"), ("n2", "AGSC-E316")]


def test_an_unresolved_target_raises_no_warning():
    assert codes([concept("a", supersedes=["nowhere"], related=["missing"])]) == []
