"""The nine ``build`` cases over a whole build, checked by this package (build-0020 to
build-0028).

This package writes no site, so ``run-vectors`` reports these cases as not run. Their
expectations are facts about the files a build writes, and this package checks them:
the engine builds the vector's Bundle exactly as its own handler does
(``tests/conformance/areas/_build-surfaces.js``, ``onBuild``) and
``areas/build_tree.py`` reads what was written. One test per case; each needs Node and
the engine checkout and is skipped with a message without them. The fixed-data tests
below show that every kind of expectation fails when the tree does not meet it.
"""

import hashlib
import json
import shutil
import subprocess

import pytest

from agentic_system_core.areas import build_tree
from conftest import ENGINE, engine_available

CASES = ["build-%04d" % number for number in range(20, 29)]

_SCRIPT = r"""
const path = require('node:path');
const [ROOT, bundle, argv, env, specVersion] = process.argv.slice(1);
const { main } = require(path.join(ROOT, 'src/application/cli/main.js'));
const { createFileSystem } = require(path.join(ROOT, 'src/adapters/node-fs.js'));
const stream = () => { const chunks = []; return { write(s) { chunks.push(s); return true; }, text: () => chunks.join('') }; };
const stdout = stream();
const stderr = stream();
const exit = main(JSON.parse(argv), { env: JSON.parse(env), ports: { fs: createFileSystem(bundle) },
  root: bundle, specVersion, stderr, stdout, version: specVersion });
process.stdout.write(JSON.stringify({ exit, stdout: stdout.text() }));
"""


def _walk(folder):
    if not folder.is_dir():
        return []
    return sorted(one.relative_to(folder).as_posix() for one in folder.rglob("*") if one.is_file())


class EngineBuild(object):
    """``build(sub_case)``: the engine's ``agsc build`` over a scratch copy of the
    vector's Bundle with the case's files written over it, the file-system port alone
    (so no git history) and exactly the environment the case states."""

    def __init__(self, vector, scratch):
        self.vector = vector
        self.scratch = scratch

    def __call__(self, sub):
        given = self.vector["input"]
        root = self.scratch / ((sub or {}).get("name") or "build")
        shutil.copytree(str(ENGINE / "tests" / given["bundle"]), str(root))
        adds = dict(given.get("add_files") or {})
        adds.update((sub or {}).get("add_files") or {})
        for relative, text in adds.items():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_bytes(text.encode("utf-8"))
        before = set(_walk(root))
        options = self.vector["options"]
        environment = {"SOURCE_DATE_EPOCH": str(options["source_date_epoch"])}
        environment.update((sub or {}).get("environment") or {})
        argv = (sub or {}).get("argv") or given.get("argv") or ["build", "--json"]
        done = subprocess.run(["node", "-e", _SCRIPT, str(ENGINE), str(root), json.dumps(argv),
                               json.dumps(environment), options["spec_version"]],
                              capture_output=True, text=True, cwd=str(ENGINE))
        assert done.returncode == 0, done.stderr[-2000:]
        result = json.loads(done.stdout)
        try:
            envelope = json.loads(result["stdout"])
        except ValueError:
            envelope = None
        out = (json.loads((root / "agsc.config.json").read_text(encoding="utf-8"))
               .get("build", {}).get("out") or "www").rstrip("/")
        return {"exit": result["exit"],
                "findings": (envelope or {}).get("findings") or [],
                "files": dict(("/" + one, (root / out / one).read_bytes())
                              for one in _walk(root / out)),
                "written": [one for one in _walk(root) if one not in before]}


def _engine_vector(identifier):
    path = next((ENGINE / "tests" / "vectors" / "build").glob(identifier + "-*.json"))
    return json.loads(path.read_bytes().decode("utf-8"))


needs_engine = pytest.mark.skipif(
    not (engine_available() and (ENGINE / "src" / "application" / "cli" / "main.js").is_file()),
    reason="the build cross-check needs Node and the engine checkout beside this one",
)


@needs_engine
@pytest.mark.parametrize("identifier", CASES)
def test_this_package_agrees_with_the_engine_build(identifier, tmp_path):
    vector = _engine_vector(identifier)
    if vector.get("level") == "withdrawn":
        pytest.skip("%s is withdrawn in the engine's vector set (superseded by %s)"
                    % (identifier, vector.get("superseded_by")))
    result = build_tree.check(vector, EngineBuild(vector, tmp_path))
    assert result["status"] == "pass", result["detail"]


# --- on fixed data ------------------------------------------------------------------

def _run(files, findings=(), exit_code=0, written=()):
    return {"exit": exit_code, "findings": list(findings), "written": list(written),
            "files": dict((route, data if isinstance(data, bytes) else data.encode("utf-8"))
                          for route, data in files.items())}


def _check(identifier, expected, runs, cases=None):
    vector = {"id": identifier, "input": {"cases": cases} if cases else {}, "expected": expected}
    return build_tree.check(vector, lambda sub: runs[(sub or {}).get("name")])


TREE = {"/index.html": "<p>handoff</p>", "/graph.nq": "<x> birch .",
        "/pages/birch.md": "---\ntitle: Birch\n---\n"}


def test_each_surface_expectation_is_read_from_the_tree():
    expected = {"no_error_finding": True, "routes_present": ["/", "/pages/birch.md"],
                "routes_absent": ["/pages/alder.md"], "carried_by": {"/graph.nq": ["birch"]},
                "not_carried_by": {"/": ["birch"]}, "files_contain": {"/": ["handoff"]},
                "in_no_file": ["alder"], "route_bytes": {"/pages/birch.md": TREE["/pages/birch.md"]}}
    assert _check("build-0020", expected, {None: _run(TREE)})["status"] == "pass"


@pytest.mark.parametrize("member, value", [
    ("routes_present", ["/pages/alder.md"]), ("routes_absent", ["/"]),
    ("carried_by", {"/": ["birch"]}), ("carried_by", {"/absent/": ["birch"]}),
    ("not_carried_by", {"/graph.nq": ["birch"]}), ("files_contain", {"/": ["alder"]}),
    ("in_no_file", ["birch"]), ("in_no_file", ["pages"]),
    ("route_bytes", {"/pages/birch.md": "other"}), ("no_error_finding", False),
])
def test_a_surface_expectation_the_tree_does_not_meet_fails(member, value):
    assert _check("build-0022", {member: value}, {None: _run(TREE)})["status"] == "fail"


def test_an_error_finding_or_a_failed_exit_is_not_a_clean_build():
    errors = [{"code": "AGSC-E901", "severity": "error"}]
    for run in (_run(TREE, findings=errors, exit_code=1), _run(TREE, exit_code=1)):
        assert _check("build-0023", {"no_error_finding": True}, {None: run})["status"] == "fail"


def test_an_expected_member_no_check_reads_fails():
    assert _check("build-0028", {"zz_unknown": True}, {None: _run(TREE)})["status"] == "fail"


def test_a_case_this_module_does_not_check_is_not_run():
    result = build_tree.check({"id": "build-0001", "input": {}, "expected": {}}, None)
    assert result["status"] == "not-run"


def test_a_withdrawn_case_is_reported_withdrawn():
    vector = {"id": "build-0024", "level": "withdrawn", "input": {}, "expected": {"withdrawn": True}}
    assert build_tree.check(vector, None) == {"status": "skip", "withdrawn": True,
                                              "detail": "withdrawn (AGSC-00-16)"}


REFUSED = {"name": "content", "exit_one_of": [1, 2], "nothing_written": True,
           "findings": [{"code": "AGSC-E204", "severity": "error"}]}
ACCEPTED = {"name": "slash", "exit": 0, "codes_absent": ["AGSC-E204"], "written_only_under": "www/"}


def test_the_build_out_cases_read_exit_findings_and_what_was_written():
    runs = {"content": _run({}, findings=[{"code": "AGSC-E204", "severity": "error", "line": 1}],
                            exit_code=1),
            "slash": _run(TREE, written=["www/index.html"])}
    cases = [{"name": "content"}, {"name": "slash"}]
    assert _check("build-0021", {"cases": [REFUSED, ACCEPTED]}, runs, cases)["status"] == "pass"
    runs = {"content": _run({}, exit_code=0, written=["content/x.md"]),
            "slash": _run(TREE, findings=[{"code": "AGSC-E204", "severity": "error"}], exit_code=1,
                          written=["dist/index.html"])}
    detail = _check("build-0021", {"cases": [REFUSED, ACCEPTED]}, runs, cases)["detail"]
    for part in ("content exit", "content findings", "content nothing written", "slash exit",
                 "slash no AGSC-E204", "slash writes only under www/"):
        assert part in detail


def test_a_sub_case_the_vector_does_not_expect_fails():
    result = _check("build-0021", {"cases": []}, {}, [{"name": "content"}])
    assert result["status"] == "fail" and "no expected case" in result["detail"]


def test_a_sub_case_member_no_check_reads_fails():
    runs = {"content": _run({})}
    result = _check("build-0021", {"cases": [{"name": "content", "zz": 1}]}, runs, [{"name": "content"}])
    assert result["status"] == "fail" and "zz" in result["detail"]


def _skills_index(index):
    return json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n"


SKILL = b"# Agent patterns\n"
PACK = {"description": "d", "members": ["handoff"], "name": "agent-patterns",
        "path": "/skills/agent-patterns/SKILL.md"}
INDEX = {"bundle_version": "0.0.0+20260101T000000Z", "license": "L", "spec_version": "1.0.0",
         "terms": "L", "packs": [dict(PACK, lock={"SKILL.md": hashlib.sha256(SKILL).hexdigest()})]}
SKILLS = {"/skills/index.json": _skills_index(INDEX), "/skills/agent-patterns/SKILL.md": SKILL}
WANT_INDEX = {"name": "terms", "jcs_with_one_lf": True, "bundle_version": INDEX["bundle_version"],
              "license": "L", "spec_version": "1.0.0", "terms": "L",
              "members": ["bundle_version", "license", "packs", "spec_version", "terms"],
              "pack_members": ["description", "lock", "members", "name", "path"], "packs": [PACK]}


def test_the_skills_index_is_read_member_by_member():
    runs = {"terms": _run(SKILLS)}
    assert _check("build-0025", {"cases": [WANT_INDEX]}, runs, [{"name": "terms"}])["status"] == "pass"
    unlocked = dict(INDEX, packs=[PACK], license="M")
    runs = {"terms": _run({"/skills/index.json": json.dumps(unlocked, indent=1)})}
    detail = _check("build-0025", {"cases": [WANT_INDEX]}, runs, [{"name": "terms"}])["detail"]
    for part in ("JCS and one LF", "terms license", "pack 0 members", "pack 0 has a lock"):
        assert part in detail
    runs = {"terms": _run({})}
    detail = _check("build-0025", {"cases": [WANT_INDEX]}, runs, [{"name": "terms"}])["detail"]
    assert "terms packs" in detail and "terms members" in detail


def test_each_lock_is_the_hash_of_the_served_skill_file():
    want = {"packs_count": 1, "lock_members": ["SKILL.md"], "lock_is_sha256_of_skill_md": True,
            "no_lock_route": True}
    assert _check("build-0026", want, {None: _run(SKILLS)})["status"] == "pass"
    changed = dict(SKILLS, **{"/skills/agent-patterns/SKILL.md": b"other\n",
                              "/skills/agent-patterns.lock": b"x"})
    detail = _check("build-0026", want, {None: _run(changed)})["detail"]
    assert "lock is the hash" in detail and "no lock route" in detail
    detail = _check("build-0026", want, {None: _run({"/skills/index.json": "[]"})})["detail"]
    assert "packs_count" in detail


ROBOTS = ("User-agent: GPTBot\nDisallow: /\n\nUser-agent: CCBot\nUser-agent: ClaudeBot\n"
          "Disallow: /\n\nUser-agent: *\nAllow: /  # everyone else\n")
TDM = '[{"location":"/*","tdm-reservation":1}]\n'
WANT_TDM = {"name": "terms", "jcs_with_one_lf": True, "routes_absent": ["/tdmrep.json"],
            "reservation_for_paths": {"/": 1, "/graph.nq": 1},
            "robots_disallow_all_groups": ["GPTBot", "CCBot", "ClaudeBot"]}


def test_the_reservation_file_and_the_robots_groups():
    runs = {"terms": _run({"/.well-known/tdmrep.json": TDM, "/robots.txt": ROBOTS})}
    assert _check("build-0027", {"cases": [WANT_TDM]}, runs, [{"name": "terms"}])["status"] == "pass"
    runs = {"terms": _run({"/tdmrep.json": TDM, "/robots.txt": "User-agent: *\nDisallow: /x\n"})}
    detail = _check("build-0027", {"cases": [WANT_TDM]}, runs, [{"name": "terms"}])["detail"]
    for part in ("JCS and one LF", "terms /graph.nq", "terms no /tdmrep.json", "robots groups"):
        assert part in detail


def test_a_tdm_location_is_a_prefix_pattern_with_an_optional_end():
    assert build_tree.tdm_matches("/*", "/a/b")
    assert build_tree.tdm_matches("/pages/", "/pages/handoff.md")
    assert not build_tree.tdm_matches("/pages/$", "/pages/handoff.md")
    assert build_tree.tdm_matches("/*.md$", "/pages/handoff.md")
    assert not build_tree.tdm_matches("/a.b", "/axb")


ROUTE_SET = {"/index.html": '<link rel="stylesheet" href="/assets/site.css">'
                            '<script src="https://cdn.example/x.js"></script>',
             "/concepts/index.html": '<script src="../assets/page.js"></script>',
             "/assets/site.css": "", "/assets/page.js": "", "/graph.nq": ""}
WANT_ROUTES = {"routes": ["/", "/concepts/", "/graph.nq"], "page_assets_required": ["/assets/site.css"],
               "other_files_are_page_assets": True}


def test_the_route_set_leaves_out_the_assets_the_pages_load():
    vector = {"id": "build-0024", "input": {"deployment_profile": "cloudflare-pages"},
              "expected": WANT_ROUTES}
    assert build_tree.check(vector, lambda sub: _run(ROUTE_SET))["status"] == "pass"
    vector["input"]["deployment_profile"] = "netlify"
    extra = dict(ROUTE_SET, **{"/extra.js": ""})
    detail = build_tree.check(vector, lambda sub: _run(extra))["detail"]
    assert "the route set" in detail and "deployment profile" in detail
