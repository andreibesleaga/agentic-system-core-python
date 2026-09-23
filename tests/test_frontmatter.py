"""The closed YAML subset reader, the item checks of spec/02 and adoption."""

import pytest

from agentic_system_core import frontmatter, yamlsubset
from agentic_system_core.yamlsubset import YamlError


def load(text):
    return frontmatter.plain(yamlsubset.load(text))


def error_of(text):
    with pytest.raises(YamlError) as caught:
        yamlsubset.load(text)
    return caught.value.code, caught.value.line


# --- the reader -----------------------------------------------------------------

def test_failsafe_scalars_quotes_and_comments():
    text = ('a: no\nb: "x\\ty\\u00e9\\x41\\U0001F600\\N\\_\\ \\/"\nc: \'it\'\'s\'\n'
            'd: plain # comment\ne: "#not a comment"\nf:\n# full-line comment\ng: 1e3\n')
    assert load(text) == {"a": "no", "b": "x\tyéA😀\x85\xa0 /", "c": "it's", "d": "plain",
                          "e": "#not a comment", "f": "", "g": "1e3"}


def test_nested_mappings_sequences_and_flow_sequences():
    text = ("prov:\n  origin: human\n  operator: human:x\nlist:\n  - a\n  - 'b'\n"
            "seq:\n- c\n- d\nflow: [a, \"b, c\", 'd']\nempty: []\n"
            "objects:\n  - by: human:x\n    at: \"2026-01-01T00:00:00Z\"\n  - name: two\n")
    assert load(text) == {
        "prov": {"origin": "human", "operator": "human:x"}, "list": ["a", "b"],
        "seq": ["c", "d"], "flow": ["a", "b, c", "d"], "empty": [],
        "objects": [{"by": "human:x", "at": "2026-01-01T00:00:00Z"}, {"name": "two"}]}


def test_plain_scalars_fold_over_continuation_lines():
    assert load("a: one\n  two\n  three\nb: x\n") == {"a": "one two three", "b": "x"}


def test_block_scalars_all_chomping_modes():
    text = ("lit: |\n  one\n  two\n\nfold: >\n  one\n  two\n\n  three\n    indented\n"
            "strip: |-\n  x\n\nkeep: |+\n  y\n\n\nexplicit: |2\n    deep\nnone: |\nlast: z\n")
    assert load(text) == {"lit": "one\ntwo\n", "fold": "one two\nthree\n  indented\n",
                          "strip": "x", "keep": "y\n\n\n", "explicit": "  deep\n", "none": "",
                          "last": "z"}


def test_a_keep_block_with_no_content():
    assert load("a: |+\n\nb: c\n") == {"a": "\n", "b": "c"}


def test_quoted_keys():
    assert load('"quoted key": 1\n\'single\': 2\n') == {"quoted key": "1", "single": "2"}


def test_every_rejected_construct_has_its_own_code():
    assert error_of("a: &x 1\n") == ("AGSC-E103", 2)
    assert error_of("a: 1\nb: *x\n") == ("AGSC-E103", 3)
    assert error_of("&x a: 1\n") == ("AGSC-E103", 2)
    assert error_of("a: !tag 1\n") == ("AGSC-E104", 2)
    assert error_of("!tag a: 1\n") == ("AGSC-E104", 2)
    assert error_of("<<: 1\n") == ("AGSC-E104", 2)
    assert error_of("a: {b: 1}\n") == ("AGSC-E105", 2)
    assert error_of("{b: 1}\n") == ("AGSC-E105", 2)
    assert error_of("? complex\n") == ("AGSC-E105", 2)
    assert error_of("a:\n  ? complex\n") == ("AGSC-E105", 3)
    assert error_of("a: [b, {c: 1}]\n") == ("AGSC-E105", 2)
    assert error_of("a: [b: c]\n") == ("AGSC-E105", 2)
    assert error_of("a: 1\na: 2\n") == ("AGSC-E106", 3)
    assert error_of("a: 1\n...\n") == ("AGSC-E107", 3)
    assert error_of("a: 1\n--- \n") == ("AGSC-E107", 3)
    assert error_of("%YAML 1.2\n") == ("AGSC-E107", 2)


def test_malformed_input_is_a_schema_fault():
    for text in ('a: "open\n', "a: 'open\n", 'a: "bad\\q"\n', 'a: "x"y"\n', "a: [1, 2\n",
                 "a: [1, , 2]\n", "a: ['x\n]\n".replace("\n]", "]"), "\tb: 1\n", "- a\n",
                 "a: 1\n   b: 2\n", "just text\n", "a: |x\n  b\n",
                 "a: 1\n- b\n"):
        code, _ = error_of(text)
        assert code in ("AGSC-E201",), text


def test_an_empty_block_is_an_empty_mapping():
    assert load("") == {}
    assert load("# only a comment\n") == {}


def test_split_frontmatter():
    assert yamlsubset.split_frontmatter("---\na: 1\n---\nbody")[1] == "body"
    assert yamlsubset.split_frontmatter("no block")[2].code == "AGSC-E101"
    assert yamlsubset.split_frontmatter("---\na: 1\n")[2].code == "AGSC-E102"


def test_the_emitted_profile_quotes_only_what_would_re_parse():
    assert yamlsubset.emit_scalar("plain words") == "plain words"
    for value in ("", "no", "1e3", "- dash", " lead", "a: b", "x #y", "end:", "2026-01-01",
                  "tab\there"):
        assert yamlsubset.emit_scalar(value).startswith('"'), value
    assert yamlsubset.emit_scalar('a"b') == 'a"b'
    text = yamlsubset.dump({"a": "x", "m": {"b": "why"}, "s": ["one", {"k": "v", "l": "w"}]})
    assert text == "a: x\nm:\n  b: why\ns:\n  - one\n  - k: v\n    l: w\n"
    assert load(text) == {"a": "x", "m": {"b": "why"}, "s": ["one", {"k": "v", "l": "w"}]}


# --- the checks -----------------------------------------------------------------

BASE = {"type": "concept", "title": "Title here", "kind": "term",
        "prov": {"origin": "human", "operator": "human:x"}}


def codes_of(data):
    return sorted((one["code"], one.get("key")) for one in frontmatter.check(data))


def with_(**extra):
    out = dict(BASE)
    out.update(extra)
    return out


def test_a_minimal_concept_is_clean():
    assert codes_of(BASE) == []


def test_required_keys_and_enums():
    assert ("AGSC-E202", "type") in codes_of({"title": "abc", "prov": BASE["prov"]})
    assert ("AGSC-E202", "title") in codes_of({"type": "gate", "level": "L1",
                                               "prov": BASE["prov"]})
    assert ("AGSC-E203", "type") in codes_of(with_(type="widget"))
    assert ("AGSC-E501", "prov") in codes_of({"type": "gate", "title": "abc", "level": "L1"})
    assert ("AGSC-E202", "prov/origin") in codes_of(with_(prov={"operator": "human:x"}))
    assert ("AGSC-E202", "prov/operator") in codes_of(with_(prov={"origin": "human"}))
    assert ("AGSC-E203", "prov/origin") in codes_of(with_(prov={"origin": "robot",
                                                                "operator": "human:x"}))
    assert ("AGSC-E204", "prov/operator") in codes_of(with_(prov={"origin": "human",
                                                                  "operator": "process:x"}))
    assert ("AGSC-E201", "prov") in codes_of(with_(prov="text"))
    assert codes_of(with_(prov={"origin": "human", "operator": "human:x", "agent": "a",
                                "model": "m", "agreement": "g"})) == []


def test_key_names_vendor_keys_unknown_keys_and_inverses():
    found = codes_of(with_(**{"Bad": "1", "x-acme-thing": "1", "odd": "1", "used-by": ["a"]}))
    assert found == [("AGSC-E204", "Bad"), ("AGSC-E207", "odd"), ("AGSC-E306", "used-by")]


def test_common_key_patterns():
    found = codes_of(with_(description="short", status="gone", release="Bad Slug", id="x",
                           iri="http://x/", spec_version="1", lang="e", date="2026-1-1",
                           modified="2026-01-01", stale_after="2026-01-01", tags=["Bad"],
                           aliases=["one\ntwo"], clusters=["Bad"], related=["a#B"],
                           title=5))
    assert ("AGSC-E204", "description") in found
    assert ("AGSC-E203", "status") in found
    for key in ("release", "iri", "spec_version", "lang", "date", "stale_after", "tags",
                "aliases", "clusters", "related"):
        assert ("AGSC-E204", key) in found, key
    assert ("AGSC-E201", "title") in found
    assert ("AGSC-E204", "modified") not in found
    mismatch = frontmatter.check(with_(id="x"), slug="y")
    assert [one["code"] for one in mismatch if one["key"] == "id"] == ["AGSC-E204"]


def test_sources_generated_verified_and_attachments():
    found = codes_of(with_(sources=[{"title": "t"}, {"resource": "https://x", "grade": "best",
                                                     "id": "i", "author": "a"}, "text"],
                           generated={"at": "2026"}, verified=[{"by": "process:x"}, "x"],
                           attachments=[{"file": "a.svg"}, {"file": "b", "media_type": "x/y",
                                                           "alt": ""}]))
    assert ("AGSC-E202", "sources") in found
    assert ("AGSC-E203", "sources") in found
    assert ("AGSC-E201", "sources") in found
    assert ("AGSC-E202", "generated") in found
    assert ("AGSC-E204", "generated") in found
    assert ("AGSC-E204", "verified") in found
    assert ("AGSC-E202", "verified") in found
    assert ("AGSC-E202", "attachments") in found
    assert ("AGSC-E204", "attachments") in found
    assert codes_of(with_(generated={"by": "tool/1.0", "at": "2026-01-01T00:00:00Z"})) == []
    assert ("AGSC-E201", "generated") in codes_of(with_(generated="x"))
    assert ("AGSC-E201", "tags") in codes_of(with_(tags="x"))


def test_type_specific_checks():
    prov = BASE["prov"]
    episode = {"type": "episode", "title": "Run", "prov": prov, "started": "2026",
               "actor": "nobody", "outcome": "meh", "ended": "2026-01-01T00:00:00Z",
               "refs": ["ftp://x"], "usage": {}}
    found = codes_of(episode)
    assert ("AGSC-E204", "started") in found and ("AGSC-E204", "actor") in found
    assert ("AGSC-E203", "outcome") in found and ("AGSC-E204", "refs") in found
    assert ("AGSC-E202", "severity") in codes_of({"type": "lesson", "title": "abc",
                                                  "prov": prov})
    assert ("AGSC-E203", "severity") in codes_of({"type": "lesson", "title": "abc",
                                                  "prov": prov, "severity": "high"})
    assert ("AGSC-E204", "when") in codes_of({"type": "procedure", "title": "abc", "prov": prov,
                                              "when": "", "inputs": ["a\nb"]})
    cluster = {"type": "cluster", "title": "abc", "prov": prov, "order": "x", "family": "f"}
    assert ("AGSC-E201", "order") in codes_of(cluster)
    assert frontmatter.typed(dict(cluster, order="7"))["order"] == 7
    gate = {"type": "gate", "title": "abc", "prov": prov, "level": "L1",
            "checks": ["schema"], "enforce": ["hook", "magic"]}
    found = codes_of(gate)
    assert ("AGSC-E203", "checks") in found and ("AGSC-E203", "enforce") in found
    assert ("AGSC-E203", "level") in codes_of(dict(gate, level="L3"))


def test_concept_facets_ports_task_state_and_verdict_digest():
    found = codes_of(with_(kind="odd", evidence="x", signature="maybe",
                           produces=["Bad", "ok", "ok"], task_state="TASK_STATE_WORKING",
                           verdict_digest="0" * 64, domains=["a\nb"]))
    assert ("AGSC-E203", "kind") in found and ("AGSC-E203", "evidence") in found
    assert ("AGSC-E201", "signature") in found
    assert ("AGSC-E204", "produces") in found and ("AGSC-E201", "produces") in found
    assert ("AGSC-E207", "task_state") in found and ("AGSC-E207", "verdict_digest") in found
    assert ("AGSC-E204", "domains") in found
    task = codes_of(with_(kind="task", task_state="TASK_STATE_FROZEN"))
    assert task == [("AGSC-E203", "task_state")]
    arch = codes_of(with_(kind="architecture", verdict_digest="xyz"))
    assert arch == [("AGSC-E204", "verdict_digest")]
    assert frontmatter.typed(with_(signature="true"))["signature"] is True


def test_read_reports_structure_and_yaml_faults_with_lines():
    assert frontmatter.read("no block\n")[2][0]["code"] == "AGSC-E101"
    data, body, findings = frontmatter.read("---\na: &x 1\n---\nbody\n")
    assert data is None and findings[0]["line"] == 2 and body == "body\n"


def test_task_state_reading():
    assert frontmatter.task_state({}) == ("TASK_STATE_UNSPECIFIED", None)
    assert frontmatter.task_state({"task_state": "X"}, own=False) == \
        ("TASK_STATE_UNSPECIFIED", None)


# --- adoption -------------------------------------------------------------------

def test_adoption_slug_title_operator_and_idempotence():
    path, output, findings = frontmatter.adopt("notes/My Notes.md", "# My Notes\n\nBody\n",
                                               git_user_email="Jane.Doe+x@example.org")
    assert path == "content/concepts/my-notes.md"
    assert "operator: human:jane.doe-x" in output
    assert [one["code"] for one in findings] == ["AGSC-E506", "AGSC-E506"]
    assert frontmatter.adopt(path, output) == (path, output, [])


def test_adoption_defaults_and_edge_cases():
    _, output, findings = frontmatter.adopt("x.md", "```\n# not\n```\nno heading\n")
    assert "title: note-x" in output and "operator: human:unknown" in output
    assert frontmatter.adopt("README.md", "text")[2][0]["code"] == "AGSC-E506"
    _, output, _ = frontmatter.adopt("long.md", "# " + "a" * 130 + "\n",
                                     git_user_email="---@x")
    assert "title: " + "a" * 120 + "\n" in output
    path, _, _ = frontmatter.adopt("dup.md", "text", taken=("dup", "dup-2"))
    assert path == "content/concepts/dup-3.md"
    assert frontmatter.slugify("!!!") == "note"
    _, output, _ = frontmatter.adopt("content/concepts/kept.md", "# Kept\n")
    assert "aliases" not in output
