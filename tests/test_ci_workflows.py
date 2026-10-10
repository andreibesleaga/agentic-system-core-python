"""The two workflows test and release what the package claims, the same way.

``test.yml`` runs on every push and pull request; ``release.yml`` runs on a version tag
and calls ``test.yml`` itself, so a release is tested exactly as a pull request is, with
the engine checked out at the specification tag that belongs to the package version.
The release refuses a tag that is not the version, a version with no engine tag, and a
tag whose commit is not on ``main``. Both lanes run the engine's port-implementer
scenario with this package beside the engine and fail when it is skipped.

The steps that decide something are run here as they are written in the workflow, on
scratch input: the version step with a scratch ``pyproject.toml``, the ancestor check
on a scratch git repository with fixed dates, the skip check on scratch test output.
The files are repository files: a source distribution does not carry them, and there
the tests are skipped.
"""

import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

pytestmark = pytest.mark.skipif(
    (ROOT / "PKG-INFO").exists(),
    reason="a source distribution carries no workflow files",
)

#: The required status checks of this repository: the job names the test lane must keep.
PROTECTED = ["tests (Python 3.9)", "tests (Python 3.13)", "ruff and mypy (Python 3.13)"]

#: The scenario of the engine that needs this package beside it.
PORT_SCENARIO = (
    "persona-l-port-implementer \u2014 The Python package's runner agrees with the engine"
    " on the shared vectors"
)


def text(relative):
    path = ROOT / relative
    assert path.is_file(), relative + " is missing"
    return path.read_text(encoding="utf-8")


def job(workflow, name):
    """The lines of one job of a workflow, from its key to the next job key."""
    match = re.search(r"^  %s:\n(.*?)(?=^  [A-Za-z_-]+:\n|\Z)" % re.escape(name), workflow,
                      re.M | re.S)
    assert match, "no job %s" % name
    return match.group(1)


def step_script(workflow, step_name):
    """The ``run`` block of the step with this name, dedented, as the runner gets it."""
    match = re.search(
        r"^( +)- name: %s\n(?:\1  (?!run:).*\n)*\1  run: \|\n((?:(?:\1    .*)?\n)+)"
        % re.escape(step_name),
        workflow, re.M)
    assert match, "no step named %r with a run block" % step_name
    return textwrap.dedent(match.group(2))


def python_heredoc(script):
    """The Python program inside ``python - <<'PY' ... PY``."""
    match = re.search(r"python - <<'PY'\n(.*?)\nPY\n", script, re.S)
    assert match, "the step holds no python heredoc"
    return match.group(1) + "\n"


def matrix_pythons(workflow):
    match = re.search(r"python: \[([^\]]*)\]", job(workflow, "tests"))
    assert match, "the tests job has no python matrix"
    return [v.strip().strip("'\"") for v in match.group(1).split(",")]


# --- the test lane -----------------------------------------------------------------------


def test_the_test_lane_keeps_every_protected_job_name_and_adds_python_3_14():
    workflow = text(".github/workflows/test.yml")
    pythons = matrix_pythons(workflow)
    assert pythons == ["3.9", "3.13", "3.14"]
    names = ["tests (Python %s)" % p for p in pythons]
    names += re.findall(r"^    name: (ruff and mypy \(Python [0-9.]+\))$", workflow, re.M)
    assert re.search(r"^    name: tests \(Python \$\{\{ matrix\.python \}\}\)$", workflow, re.M)
    for context in PROTECTED:
        assert context in names, context + " is no longer produced"


def test_the_test_lane_can_be_called_with_an_engine_ref():
    workflow = text(".github/workflows/test.yml")
    on = re.search(r"^on:\n(.*?)(?=^\S)", workflow, re.M | re.S).group(1)
    assert re.search(r"^  workflow_call:\n    inputs:\n      engine_ref:\n", on, re.M)
    assert re.search(r"^  workflow_dispatch:\n    inputs:\n      engine_ref:\n", on, re.M)
    assert "ref: ${{ inputs.engine_ref || env.ENGINE_REF }}" in job(workflow, "tests")


def test_every_leg_checks_out_the_main_site_beside_the_package():
    # The main-site test reads the site's committed discovery document from the
    # checkout beside this one; without it that test is skipped and proves nothing.
    tests = job(text(".github/workflows/test.yml"), "tests")
    step = re.search(r"- name: the main site, beside it\n((?: {8}.*\n)+)", tests)
    assert step, "no step checks out the main site"
    body = step.group(1)
    assert re.search(r"uses: actions/checkout@[0-9a-f]{40} # v", body), "the checkout is pinned"
    assert "repository: andreibesleaga/AgenticSystemCore.com" in body
    assert "path: AgenticSystemCore.com" in body
    assert "persist-credentials: false" in body


def test_every_leg_runs_the_port_implementer_scenario_beside_the_engine():
    tests = job(text(".github/workflows/test.yml"), "tests")
    command = ('node --test --test-name-pattern "persona-l" --test-reporter=tap'
               ' tests/acceptance/features.test.js')
    assert command in tests
    assert "PYTHON: python" in tests, "the scenario must use the leg's Python"


@pytest.mark.skipif(shutil.which("bash") is None, reason="no bash on this machine")
@pytest.mark.parametrize("lines, passes", [
    (["ok 1 - persona-l-port-implementer \u2014 A Level-0 node",
      "ok 2 - " + PORT_SCENARIO,
      "ok 3 - persona-l-port-implementer \u2014 The reference engine's Level-3 report"], True),
    (["ok 1 - persona-l-port-implementer \u2014 A Level-0 node",
      "ok 2 - " + PORT_SCENARIO + " # SKIP not available here (python-package): no Python"
      " checker package at /x"], False),
    (["ok 1 - persona-l-port-implementer \u2014 A Level-0 node"], False),
])
def test_a_skipped_port_scenario_fails_the_lane(tmp_path, lines, passes):
    script = step_script(text(".github/workflows/test.yml"),
                         "the port implementer's scenarios all ran (a skip fails the lane)")
    (tmp_path / "persona-l.tap").write_text("TAP version 13\n" + "\n".join(lines) + "\n# fail 0\n",
                                            encoding="utf-8")
    env = dict(os.environ, RUNNER_TEMP=str(tmp_path))
    done = subprocess.run(["bash", "-e", "-c", script], cwd=str(tmp_path), env=env,
                          capture_output=True, text=True)
    assert (done.returncode == 0) is passes, done.stdout + done.stderr
    assert ("::error::" in done.stdout) is not passes


# --- the release lane --------------------------------------------------------------------


def test_the_release_runs_the_test_lane_at_the_derived_engine_tag():
    workflow = text(".github/workflows/release.yml")
    tests = job(workflow, "test")
    assert "uses: ./.github/workflows/test.yml" in tests
    assert "engine_ref: ${{ needs.version.outputs.engine_ref }}" in tests
    assert re.search(r"needs: version\b", tests)
    assert re.search(r"needs: \[version, test\]", job(workflow, "build"))
    assert "fetch-depth: 0" in job(workflow, "version")


@pytest.mark.skipif(sys.version_info < (3, 11), reason="the release step reads pyproject.toml "
                    "with tomllib, which Python 3.11 and later ship")
@pytest.mark.parametrize("version, tag, engine", [
    ("1.0.0rc7", "v1.0.0rc7", "1.0.0-rc.7"),
    ("1.0.0", "v1.0.0", "1.0.0"),
    ("1.0.0.post1", "v1.0.0.post1", "1.0.0"),
    ("1.0.1", "v1.0.1", "1.0.1"),
    ("1.1.0rc2.post3", "v1.1.0rc2.post3", "1.1.0-rc.2"),
    ("1.0.0", "v1.0.0rc7", None),
    ("1.0.0a1", "v1.0.0a1", None),
    ("1.0.0.dev1", "v1.0.0.dev1", None),
    ("1.0", "v1.0", None),
])
def test_the_engine_tag_is_derived_from_the_package_version(tmp_path, version, tag, engine):
    script = step_script(text(".github/workflows/release.yml"),
                         "the tag must be the version; the engine tag follows from it")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "%s"\n' % version,
                                             encoding="utf-8")
    output = tmp_path / "output"
    output.write_text("", encoding="utf-8")
    env = dict(os.environ, GITHUB_REF_NAME=tag, GITHUB_OUTPUT=str(output))
    done = subprocess.run([sys.executable, "-c", python_heredoc(script)], cwd=str(tmp_path),
                          env=env, capture_output=True, text=True)
    if engine is None:
        assert done.returncode != 0
        assert re.search(r"does not match version|has no engine tag", done.stderr), done.stderr
        assert output.read_text(encoding="utf-8") == ""
    else:
        assert done.returncode == 0, done.stderr
        assert output.read_text(encoding="utf-8").splitlines() == [
            "version=" + version, "engine_ref=" + engine]


def _git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
               GIT_AUTHOR_DATE="2026-01-01T00:00:00Z", GIT_COMMITTER_DATE="2026-01-01T00:00:00Z",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(["git", "-C", str(repo)] + list(args), env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                    reason="no bash or git on this machine")
@pytest.mark.parametrize("tagged, passes", [("main", True), ("side", False)])
def test_the_release_refuses_a_tag_whose_commit_is_not_on_main(tmp_path, tagged, passes):
    script = step_script(text(".github/workflows/release.yml"), "the tagged commit must be on main")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "on main")
    on_main = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", on_main)
    _git(repo, "checkout", "-q", "-b", "side")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "beside main")
    commit = on_main if tagged == "main" else _git(repo, "rev-parse", "HEAD")
    _git(repo, "tag", "-a", "-m", "v9.9.9", "v9.9.9", commit)
    env = dict(os.environ, VERSION="9.9.9", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    done = subprocess.run(["bash", "-e", "-c", script], cwd=str(repo), env=env,
                          capture_output=True, text=True)
    assert (done.returncode == 0) is passes, done.stdout + done.stderr
    assert ("is not on main" in done.stdout) is not passes
    assert ("is on main" in done.stdout) is passes


# --- what the package claims ------------------------------------------------------------


def test_the_classifiers_name_exactly_the_pythons_from_the_floor_to_the_newest_leg():
    pyproject = text("pyproject.toml")
    floor = re.search(r'^requires-python = ">=3\.(\d+)"$', pyproject, re.M).group(1)
    newest = max(int(p.split(".")[1]) for p in matrix_pythons(text(".github/workflows/test.yml")))
    named = sorted(int(m) for m in re.findall(r'"Programming Language :: Python :: 3\.(\d+)"',
                                                pyproject))
    assert named == list(range(int(floor), newest + 1))


def test_the_readme_says_python_3_9_is_past_its_end_of_life_and_still_supported():
    readme = " ".join(text("README.md").split())
    assert re.search(r"Python 3\.9 reached its end of life in October 2025", readme)
    assert "still supported by every 1.x release" in readme


def test_dependabot_updates_the_pinned_actions():
    config = text(".github/dependabot.yml")
    assert re.search(r"^version: 2$", config, re.M)
    assert re.search(r"- package-ecosystem: github-actions\n    directory: /\n    schedule:\n"
                     r"      interval: monthly\n", config)
