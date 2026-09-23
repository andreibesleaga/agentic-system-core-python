"""The CommonMark subset scanner and the Link rules of spec/03."""

from agentic_system_core import links, markdown


def texts(body):
    return [(one.level, one.text) for one in markdown.headings(body)]


def dests(body):
    return [one.destination for one in markdown.links(body)]


# --- headings ------------------------------------------------------------------

def test_atx_headings_with_closing_sequences_and_indent():
    body = "# A #\n  ## B ##   \n### C#\n#### #\n####### seven\n#tag\n"
    assert texts(body) == [(1, "A"), (2, "B"), (3, "C#"), (4, "")]


def test_setext_headings_and_thematic_breaks():
    body = "Title\nline two\n===\n\nSub\n---\n\n---\n\n***\ntext\n"
    assert texts(body) == [(1, "Title\nline two"), (2, "Sub")]


def test_fenced_and_indented_code_is_never_a_heading_or_a_link():
    body = ("```md\n# not a heading\n[x](y.md)\n```\n"
            "~~~~\n## nor this\n~~~\n~~~~\n"
            "    # indented code\n    [x](z.md)\n"
            "# Real\n")
    assert texts(body) == [(1, "Real")]
    assert dests(body) == []


def test_a_backtick_fence_whose_info_string_carries_a_backtick_is_not_a_fence():
    body = "``` a`b\n# heading\n"
    assert texts(body) == [(1, "heading")]


def test_an_unclosed_fence_runs_to_the_end():
    assert texts("```\n# no\n") == []


def test_indented_lines_continue_a_paragraph():
    body = "para\n    [x](a.md)\n"
    assert dests(body) == ["a.md"]


# --- inline links -------------------------------------------------------------

def test_inline_links_images_titles_and_angle_destinations():
    body = ('See [a](one.md "t") and ![img](pic.svg) and [b](<two words.md>) '
            "and [c](three.md 'x') and [d](four.md (y)) and [e]( five.md ).")
    assert dests(body) == ["one.md", "pic.svg", "two words.md", "three.md", "four.md",
                           "five.md"]
    assert [one.image for one in markdown.links(body)] == [False, True, False, False, False,
                                                           False]


def test_balanced_parentheses_and_escapes_in_a_destination():
    assert dests("[a](x(1).md) [b](y\\).md)") == ["x(1).md", "y).md"]


def test_code_spans_escapes_and_nested_brackets():
    body = "`[no](a.md)` \\[no](b.md) [a [nested] label](c.md) ``x`` `` `unclosed"
    assert dests(body) == ["c.md"]


def test_a_code_span_inside_a_label_and_a_link_inside_an_image_label():
    body = "[`]`](a.md) ![see [inner](b.md)](c.png)"
    assert dests(body) == ["a.md", "c.png", "b.md"]


def test_malformed_links_are_not_links():
    body = ("[a] (x.md) [b](<open.md [c](unterminated.md \"t [d](e.md 'x' junk) "
            "[e](<bad\nline>) [f]")
    assert dests(body) == []


def test_links_carry_their_line_numbers():
    body = "one\n\ntwo [a](a.md)\nthree [b](b.md)\n"
    assert [(one.destination, one.line) for one in markdown.links(body)] == [
        ("a.md", 3), ("b.md", 4)]


def test_links_in_headings_are_found_and_reduced_to_text_for_anchors():
    body = "## See [the \\*spec\\*](spec.md) now\n"
    assert dests(body) == ["spec.md"]
    assert markdown.plain_heading_text(markdown.headings(body)[0].text) == "See the *spec* now"
    assert links.anchors(body) == ["see-the-spec-now"]


# --- anchors (AGSC-03-13) -----------------------------------------------------

def test_anchor_algorithm_and_suffixes():
    body = "# Café au Lait\n# A\n# A\n# A-2\n# ✦\n# ✧\n"
    assert links.anchors(body) == ["caf-au-lait", "a", "a-2", "a-2-2", "section-1", "section-2"]


# --- edges and checks ---------------------------------------------------------

def item(slug, **keys):
    out = {"slug": slug, "type": keys.pop("type", "concept")}
    out.update(keys)
    return out


def test_symmetric_edges_authored_on_both_sides_are_not_duplicated():
    items = [item("a", related=["b"], broader=["c"]), item("b", related=["a"]),
             item("c", narrower=["a"])]
    edges, findings = links.edges(items)
    assert findings == []
    assert {"computed": False, "key": "related", "source": "b", "target": "a"} in edges
    assert sum(1 for one in edges if one["key"] == "related") == 2
    assert sum(1 for one in edges if one["key"] in ("broader", "narrower")) == 2


def test_an_unresolved_target_is_e301_and_an_anchor_target_resolves():
    edges, findings = links.edges([item("a", uses=["b#part", "missing"]), item("b")])
    assert [one["code"] for one in findings] == ["AGSC-E301"]
    assert edges[0]["target"] == "b"


def test_authored_inverse_is_e306():
    _, findings = links.edges([item("a", **{"required-by": ["b"]}), item("b")])
    assert findings[0]["code"] == "AGSC-E306"


def test_requires_cycle_in_discovery_order_and_acyclic_graphs():
    items = [item("b", requires=["c"]), item("c", requires=["b"]), item("a", requires=["b"]),
             item("d", requires=["zz"])]
    assert links.requires_cycle(items) == ["b", "c"]
    assert links.requires_cycle([item("a", requires=["b"]), item("b"), item("c")]) is None


def test_hierarchy_cycle_is_e303_and_stops():
    items = [item("a", broader=["b"]), item("b", broader=["a"])]
    found = links.hierarchy_findings(items)
    assert [one["code"] for one in found] == ["AGSC-E303"]
    assert found[0]["cycle"] == ["a", "b"]


def test_hierarchy_through_narrower_and_non_cluster_items():
    items = [item("p", type="cluster", narrower=["q"]), item("q", type="cluster"),
             item("x", broader=["y"]), item("y")]
    assert links.hierarchy_findings(items) == []


def test_body_links_resolve_escape_and_assets():
    items = [
        item("a", body="[x](../../../../out.md) [y](../concepts/b.md#top) [z](/assets/p.png) "
                        "[w](?q) [v](//cdn.example/x) [u](mailto:a@b) [t](b/) [s](c.md#top)"),
        item("b", body="# Top\n"),
    ]
    report = links.body_link_report(items, assets=("p.png",))
    assert [one["code"] for one in report["findings"]] == ["AGSC-E902", "AGSC-E310"]
    missing_anchor = links.body_link_report([item("a", body="[x](b.md#nope)"), item("b")])
    assert missing_anchor["unresolved"] == ["b.md#nope"]
    assert report["resolved"] == ["../concepts/b.md#top", "/assets/p.png", "?q", "b/"]
    assert report["unresolved"] == ["../../../../out.md", "c.md#top"]
    assert report["external"] == ["//cdn.example/x", "mailto:a@b"]


def test_external_detection():
    assert links.is_external("https://x")
    assert links.is_external("mailto:a")
    assert not links.is_external("a:b/c.md".replace("a:", "1a:"))
    assert not links.is_external("page.md")
    assert not links.is_external("#frag")


def test_mentions_are_one_per_pair_and_never_self():
    items = [item("a", body="[b](b.md) [b](b.md) [me](a.md) [out](https://x/)"),
             item("b", body="")]
    assert links.mentions(items) == [("a", "b")]
