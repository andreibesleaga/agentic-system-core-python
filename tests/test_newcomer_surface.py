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


def test_a_final_version_installs_with_a_plain_pip_install():
    # Once the package version has no pre-release part, pip finds it without `--pre`.
    # `--pre` would then also pick up a candidate of a later version, so the README names
    # the plain command and does not call the current version a release candidate.
    version = re.search(r'^version = "([^"]+)"$', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    if re.search(r"[a-z]", version):
        pytest.skip("the package version %s is a pre-release" % version)
    text = README.read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert "\npip install agentic-system-core\n" in text
    assert "pip install --pre" not in text
    assert "every version of this package is a release candidate" not in flat
    assert "Until `%s` is released" % version not in flat
    assert not re.search(r"\b\d+\.\d+\.\d+rc\d+\b", text), "the README names a release-candidate version"


CHANGELOG_URL = "https://github.com/andreibesleaga/agentic-system-core-python/blob/main/CHANGELOG.md"


def test_the_change_log_is_reachable_from_the_package_page():
    # PyPI shows the project links and the README, and the sdist is what a
    # downstream packager reads, so the change log is reachable from all three.
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    urls = pyproject.split("[project.urls]\n", 1)[1].split("\n\n", 1)[0]
    assert re.search(r'^Changelog = "%s"$' % re.escape(CHANGELOG_URL), urls, re.M)
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    assert "include CHANGELOG.md" in manifest
    assert (ROOT / "CHANGELOG.md").is_file()
    assert "](%s)" % CHANGELOG_URL in README.read_text(encoding="utf-8")


def test_the_readme_promises_python_3_9_for_this_release_only():
    # Python 3.9 is kept at this release; a later release may drop it, so the
    # README does not promise it for every release of the major version.
    flat = " ".join(README.read_text(encoding="utf-8").split())
    assert "Python 3.9 reached its end of life in October 2025 and is still supported by this release" in flat
    assert "every 1.x release" not in flat


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
