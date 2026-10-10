"""What a newcomer meets first: the usage text, the README PyPI shows, the paths
the suite reads the two built sites from, and the wording of the shipped source.

No network, no clock: every check reads files of this repository or, when it sits
beside this one, the configuration file of a site checkout.
"""

import io
import json
import re

import pytest

from agentic_system_core import cli
from conftest import HERE, SITE_DOCUMENTS

ROOT = HERE.parent
README = ROOT / "README.md"


def test_the_usage_text_shows_the_vector_directory_as_required():
    # Both vector verbs stop with a usage fault when no directory is given, so the
    # directory is not shown in brackets as if it were optional.
    out = io.StringIO()
    assert cli.main(["--help"], out=out, err=io.StringIO()) == 0
    for text in (out.getvalue(), cli.__doc__):
        assert "validate-vectors <dir>" in text
        assert "run-vectors <dir>" in text
        assert "[<dir>]" not in text


@pytest.mark.parametrize("verb", ["validate-vectors", "run-vectors"])
def test_a_vector_verb_without_a_directory_is_a_usage_fault(verb):
    err = io.StringIO()
    assert cli.main([verb], out=io.StringIO(), err=err) == 2
    assert "a vector directory is required" in err.getvalue()


def test_the_readme_has_no_relative_link():
    # PyPI shows this file as the project page and does not rewrite a relative link,
    # so every link in it is absolute (or an anchor on the same page).
    links = re.findall(r"\]\(([^)\s]+)\)", README.read_text(encoding="utf-8"))
    relative = [one for one in links if not re.match(r"(https?://|mailto:|#)", one)]
    assert relative == []


def test_the_readme_says_where_the_vectors_are():
    text = README.read_text(encoding="utf-8")
    assert "tests/vectors/" in text
    assert "https://github.com/andreibesleaga/agentic-system-core" in text


@pytest.mark.parametrize("path", SITE_DOCUMENTS, ids=lambda one: one.parts[-4])
def test_each_site_path_is_the_build_folder_its_configuration_names(path):
    # The suite reads a site's built discovery file from the folder that site's own
    # configuration builds into; a stale folder name would skip its tests forever.
    checkout = path.parents[2]
    config = checkout / "agsc.config.json"
    if not config.is_file():
        pytest.skip("the checkout %s is not beside this one" % checkout.name)
    with open(config, encoding="utf-8") as handle:
        out = json.load(handle).get("build", {}).get("out", "www")
    assert path.relative_to(checkout).parts[0] == out


def _shipped_and_test_sources():
    sources = sorted((ROOT / "src" / "agentic_system_core").rglob("*.py"))
    return sources + sorted(HERE.glob("*.py"))


#: Words of the review process, which belong in private records and never in a
#: public file.  Built from parts so that this file does not match itself.
REVIEW_WORDING = [
    re.compile("verification" + " finding"),
    re.compile(r"\(" + "finding "),
    re.compile(r"\b[A-Z]{1,3}[0-9]{1,3} \([a-z]\)"),
    re.compile("the " + "(Python|checker) half"),
    re.compile("Until " + r"[0-9]{4}-[0-9]{2}-[0-9]{2}"),
]


def test_no_review_label_or_drafting_date_in_the_source_or_the_tests():
    hits = []
    for path in _shipped_and_test_sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(pattern.search(line) for pattern in REVIEW_WORDING):
                hits.append("%s:%d" % (path.relative_to(ROOT), number))
    assert hits == []


def test_the_scan_sees_the_files_it_promises_to_read():
    names = [one.name for one in _shipped_and_test_sources()]
    assert "net.py" in names and "test_net.py" in names and "test_wellknown.py" in names


def test_the_review_patterns_catch_what_they_are_meant_to():
    examples = ["(verification" + " finding X1)", "# C" + "17 (b): held", "Until " + "2026-01-02 it"]
    for example in examples:
        assert any(pattern.search(example) for pattern in REVIEW_WORDING), example
    assert not any(pattern.search("AGSC-11-10(e, f) and RFC 9530 (a)")
                   for pattern in REVIEW_WORDING)
