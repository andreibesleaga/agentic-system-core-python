"""The repository's community files route people the way the project decided.

A security report goes to private vulnerability reporting first and to the contact page
second, never to a public issue; an outside contribution signs off under the
contributor agreement ``CA-v1``. GitHub shows these files on the repository's pages, so
a missing or wrong file sends a reporter to the wrong place. The files are repository
files: a source distribution does not carry them, and there the tests are skipped.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = "andreibesleaga/agentic-system-core-python"
ENGINE = "https://github.com/andreibesleaga/agentic-system-core/blob/main/"

pytestmark = pytest.mark.skipif(
    (ROOT / "PKG-INFO").exists(),
    reason="a source distribution carries no repository community files",
)


def read(relative: str) -> str:
    path = ROOT / relative
    assert path.is_file(), relative + " is missing"
    return " ".join(path.read_text(encoding="utf-8").split())


def sentences_with(text: str, pattern: str) -> list:
    """Each sentence of ``text`` (whitespace already collapsed) that matches ``pattern``."""
    out = []
    for match in re.finditer(pattern, text, re.I):
        start = max(text.rfind(". ", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
        end = text.find(". ", match.end())
        out.append(text[start:end if end >= 0 else len(text)])
    return out


def test_security_policy_names_private_reporting_first() -> None:
    text = read("SECURITY.md")
    private = text.find("private vulnerability reporting")
    contact = text.find("https://andreibesleaga.com/contact/")
    assert private >= 0, "private vulnerability reporting is not named"
    assert contact >= 0, "the contact page is not named"
    assert private < contact, "private reporting must come before the contact page"
    assert "https://github.com/" + REPO + "/security/advisories/new" in text
    assert ENGINE + "SECURITY.md" in text, "the engine's policy is not linked"


def test_security_policy_never_sends_a_reporter_to_a_public_issue() -> None:
    text = read("SECURITY.md")
    hits = sentences_with(text, r"\bopen (?:a public|an|a) issue\b")
    assert hits, "the sentence that says not to open a public issue is missing"
    for sentence in hits:
        assert re.search(r"\b(?:not|never)\b", sentence, re.I), sentence


def test_contributing_names_the_sign_off_for_outside_contributions() -> None:
    text = read("CONTRIBUTING.md")
    assert "Signed-off-by:" in text
    assert "(CA-v1)" in text
    assert re.search(r"\boutside contributions?\b", text, re.I)
    assert ENGINE + "CONTRIBUTOR-AGREEMENT" in text


def test_code_of_conduct_points_to_the_engine() -> None:
    assert ENGINE + "CODE_OF_CONDUCT.md" in read("CODE_OF_CONDUCT.md")


def test_issue_and_pull_request_templates() -> None:
    chooser = read(".github/ISSUE_TEMPLATE/config.yml")
    assert "https://github.com/" + REPO + "/security/advisories/new" in chooser
    forms = [p for p in sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
             if p.name != "config.yml"]
    assert forms, "no issue form"
    for form in forms:
        body = form.read_text(encoding="utf-8")
        assert re.search(r"^name: \S", body, re.M) and re.search(r"^body:$", body, re.M), form.name
    assert "(CA-v1)" in read(".github/pull_request_template.md")
