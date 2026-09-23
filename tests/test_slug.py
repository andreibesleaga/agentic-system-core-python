"""The slug grammar, the 1 to 64 bound and the uniqueness rule."""

import pytest

from agentic_system_core import slug


@pytest.mark.parametrize("candidate", ["a", "a2a", "multi-agent-supervisor", "x1-y2-z3", "a" * 64])
def test_accepted(candidate):
    assert slug.is_valid(candidate)


@pytest.mark.parametrize("candidate", [
    "multi--agent", "-agent", "agent-", "Agent", "agent.core", "", "a" * 65, "a_b", 5, None,
])
def test_rejected(candidate):
    assert not slug.is_valid(candidate)


def test_the_pattern_is_portable():
    assert slug.SLUG_PATTERN == "^[a-z0-9]+(?:-[a-z0-9]+)*$"
    assert "(?=" not in slug.SLUG_PATTERN and "(?!" not in slug.SLUG_PATTERN


def test_a_malformed_slug_is_e204_and_a_repeat_is_e206():
    findings = slug.check(["ok", "Bad", "ok"], files=["a.md", "b.md", "c.md"])
    assert [one["code"] for one in findings] == ["AGSC-E204", "AGSC-E206"]
    assert findings[1]["message"].endswith("a.md")
    assert findings[0]["file"] == "b.md"


def test_a_repeat_with_no_file_names_another_item():
    findings = slug.check(["ok", "ok"])
    assert findings[0]["code"] == "AGSC-E206"
    assert "another item" in findings[0]["message"]


def test_stem_of_a_path():
    assert slug.stem_of("content/concepts/handoff.md") == "handoff"
    assert slug.stem_of("handoff") == "handoff"
    assert slug.code_point_length("a\U0001f600") == 2
