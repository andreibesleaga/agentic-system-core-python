"""The readings of the Link graph (AGSC-05-33) and the ten questions (AGSC-05-34).

``derive.readings`` gives the relations the graph holds without anyone having authored
them, each with its reasons; ``questions.answer`` answers one of the ten questions over
the items. The engine's ``src/knowledge/derive.js`` and ``questions.js`` are the
reference; ``graph-0029`` to ``graph-0039`` are the vectors. Fixed data, no network.
"""

import pytest

from agentic_system_core import derive, links, questions


def concept(slug, **keys):
    return dict({"slug": slug, "type": "concept"}, **keys)


def readings(items):
    edges, _ = links.edges(items)
    return derive.readings(edges)


def test_an_authored_edge_gives_its_inverse_and_a_symmetric_one_its_swap():
    got = readings([concept("a", uses=["b"]), concept("b", related=["c"]), concept("c")])
    assert got == [
        {"because": [{"from": [["a", "uses", "b"]], "rule": "inverse"}],
         "key": "used-by", "source": "b", "target": "a"},
        {"because": [{"from": [["b", "related", "c"]], "rule": "symmetric"}],
         "key": "related", "source": "c", "target": "b"},
    ]


def test_a_chain_of_a_transitive_key_is_one_reading_with_its_steps():
    got = readings([concept("a", broader=["b"]), concept("b", broader=["c"]), concept("c")])
    chains = [one for one in got if one["because"][0]["rule"] == "transitive"]
    assert [(one["source"], one["key"], one["target"]) for one in chains] == [
        ("a", "broader", "c"), ("c", "narrower", "a")]
    assert chains[0]["because"][0]["from"] == [["a", "broader", "b"], ["b", "broader", "c"]]


def test_a_requires_chain_is_a_closure_and_a_cycle_gives_no_reading_of_the_start():
    got = readings([concept("x", requires=["y"]), concept("y", requires=["z"]),
                    concept("z", requires=["x"])])
    rules = set(one["because"][0]["rule"] for one in got)
    assert rules == {"inverse", "closure"}
    assert all(one["source"] != one["target"] for one in got)


def test_a_key_that_is_not_transitive_gives_no_chain():
    got = readings([concept("a", uses=["b"]), concept("b", uses=["c"]), concept("c")])
    assert all(one["because"][0]["rule"] == "inverse" for one in got)


WORLD = [
    {"slug": "c-top", "type": "cluster"},
    {"slug": "c-sub", "type": "cluster", "broader": ["c-top"]},
    concept("i1", clusters=["c-sub"]), concept("i2", clusters=["c-top"]),
    concept("x", requires=["y"]), concept("y", requires=["z"]), concept("z"),
    concept("ex1", excludes=["ex2"]), concept("ex2"),
    concept("p", supersedes=["q"]), concept("q", supersedes=["r"]), concept("r"),
    concept("consumer", consumes=["cap-a", "cap-b"]), concept("prov", produces=["cap-a"]),
    concept("ver", verifies=["spec1"]), concept("spec1", kind="spec"),
    concept("t1", **{"blocked-by": ["t2"]}), concept("t2", **{"blocked-by": ["t3"]}),
    concept("t3"),
    {"slug": "l", "type": "lesson", "derived-from": ["e1", "m"]},
    {"slug": "e1", "type": "episode", "derived-from": ["e0"]},
    {"slug": "e0", "type": "episode"}, concept("m"),
    concept("st", stale_after="2026-01-01"), concept("dr", status="draft"),
    concept("ok"),
    concept("s1", sources=[{"resource": "a"}, {"resource": "b"}]),
    concept("s2", sources=[{"resource": "a"}]), concept("s3", sources=[{"resource": "c"}]),
]


@pytest.mark.parametrize("number, subject, extra, answer", [
    (1, "x", {}, ["y", "z"]),
    (2, "ex2", {}, ["ex1"]),
    (3, "r", {}, ["p", "q"]),
    (4, "consumer", {"selection": ["prov"]}, ["cap-b"]),
    (4, "consumer", {}, ["cap-a", "cap-b"]),
    (5, "spec1", {}, {"verified_by": ["ver"], "verifies": []}),
    (6, "t1", {}, ["t2", "t3"]),
    (7, "l", {}, {"episodes": ["e0", "e1"], "lineage": ["e0", "e1", "m"]}),
    (8, "c-top", {}, {"clusters": ["c-sub"], "items": ["i1", "i2"]}),
    (9, None, {"selection": ["st", "dr", "ok", "nobody"], "at": "2026-10-29T00:00:00Z"},
     [{"reasons": ["draft"], "slug": "dr"}, {"reasons": ["stale"], "slug": "st"}]),
    (10, "s1", {}, {"shared": [{"items": ["s2"], "resource": "a"}], "sources": ["a", "b"]}),
])
def test_each_question_has_the_answer_of_the_rule(number, subject, extra, answer):
    assert questions.answer(number, WORLD, subject=subject, **extra) == answer


def test_there_are_ten_questions():
    with pytest.raises(ValueError):
        questions.answer(11, WORLD, subject="x")


@pytest.mark.parametrize("value, millis", [
    ("1970-01-01", 0),
    ("1970-01-02T00:00:00Z", 86400000),
    ("2026-10-29T00:00:00Z", 1793232000000),
    ("2026-10-29T02:00:00+02:00", 1793232000000),
    ("2026-10-29 00:00:00.5Z", 1793232000500),
    ("2000-02-29T00:00", 951782400000),
])
def test_an_instant_is_read_without_a_clock(value, millis):
    assert questions.instant_of(value) == millis


def test_staleness_falls_back_to_text_order_when_an_instant_does_not_parse():
    assert questions.is_stale("2026-01-01", "2026-10-29") is True
    assert questions.is_stale("2027-01-01", "2026-10-29") is False
    assert questions.is_stale("not a date", "zzz") is True
    assert questions.is_stale(None, "2026-10-29") is False
