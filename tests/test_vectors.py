"""The vector-set checker and the runner for the areas this package covers."""

import io
import json
import os
import re
import shutil
import subprocess

import pytest

from agentic_system_core import SPEC_VERSION, cli, vectors
from conftest import ENGINE, VECTORS, engine_available


def vectors_module_areas():
    """The areas this package runs natively, as the runner reports them."""
    return ["build", "discovery", "frontmatter", "graph", "jcs", "links", "slug"]


def codes(result):
    return sorted(one["code"] for one in result["findings"])


def test_the_shipped_vector_copies_pass_the_file_format_check():
    result, count, empty = vectors.validate(str(VECTORS))
    assert result["status"] == "pass", result["findings"]
    assert count == 156
    for area in vectors_module_areas():
        assert area not in empty
    assert "lint" in empty


#: The vectors of the seven areas this package reports as not run, by reason.
NEEDS_A_WHOLE_BUILD = [
    "build-0015", "build-0017", "build-0020", "build-0021", "build-0022", "build-0023",
    "build-0025", "build-0026", "build-0027", "build-0028", "build-0029", "build-0030",
    "build-0033", "build-0034", "disc-0018", "disc-0032", "graph-0027"]
NEEDS_A_WRITER_THIS_PACKAGE_LACKS = ["build-0031", "build-0032", "build-0037", "disc-0020",
                                     "disc-0021", "graph-0041"]
DOMAIN_LAYER = ["fm-0022", "fm-0023", "fm-0024", "fm-0025", "fm-0027", "graph-0042",
                "graph-0044", "graph-0045", "graph-0046", "links-0018", "links-0019"]


def test_every_vector_of_every_area_this_package_runs_passes():
    report, code = vectors.run(str(VECTORS))
    failed = [one["id"] for one in report["results"] if one["status"] == "fail"]
    assert failed == []
    assert code == 0
    assert report["tally"]["pass"] == 115
    # Thirty-four vectors are reported not run, by name, each with its reason.
    not_run = NEEDS_A_WHOLE_BUILD + NEEDS_A_WRITER_THIS_PACKAGE_LACKS + DOMAIN_LAYER
    assert report["tally"]["not_run"] == len(not_run) == 34
    assert sorted(report["vectors_not_run"]) == sorted(not_run)
    for identifier in DOMAIN_LAYER:
        assert report["vectors_not_run"][identifier] == "domain layer: engine only in 1.1"
    reasons = report["vectors_not_run"]
    for identifier in ("build-0029", "build-0030"):
        assert reasons[identifier] == "needs the engine's build and the query page (Level 3)"
    assert "PROV-O" in reasons["disc-0032"] and "writes no HTML" in reasons["disc-0032"]
    assert "export --closure" in reasons["graph-0041"]
    for identifier in ("disc-0020", "disc-0021"):
        assert "whole link table of AGSC-06-08" in reasons[identifier]
    assert report["tally"]["withdrawn"] == 7
    assert report["areas_run"] == vectors_module_areas()
    assert report["areas_not_run"] == {}
    assert "115 pass" in report["summary"]
    assert "34 not run by this package" in report["summary"]


def test_a_level_selects_its_area_set():
    report, _ = vectors.run(str(VECTORS), level=0)
    # Level 0 runs frontmatter, slug, bundle and discovery only (AGSC-10-02), less the
    # discovery cases AGSC-10-15 assigns to a higher Level: five discovery cases remain.
    # The two withdrawn discovery cases of 1.0 are skipped, never counted as a pass.
    assert report["total"] == 22 + 7 + 8
    assert report["tally"]["pass"] == 22 + 7 + 6
    assert report["tally"]["withdrawn"] == 2
    report, _ = vectors.run(str(VECTORS), level=3)
    assert report["total"] == 156


@pytest.mark.skipif(not (ENGINE / "spec").is_dir(), reason="the engine checkout is not here")
def test_the_higher_level_table_is_the_specifications():
    text = (ENGINE / "spec" / "10-implementation-profiles.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\s*\| `([a-z]+-\d{4})` \| `[a-z]+` \| (\d) \|", text, re.M)
    assert dict((case, int(level)) for case, level in rows) == vectors.HIGHER_LEVEL_CASES


def test_an_area_this_package_does_not_run_is_named_never_skipped(tmp_path):
    area = tmp_path / "lint"
    area.mkdir()
    vector = {
        "area": "lint", "description": "A fixture.", "expected": {"output": ""},
        "id": "lint-9001", "input": {}, "level": "required", "rule": "AGSC-05-04",
    }
    (area / "lint-9001.json").write_bytes(
        json.dumps(vector, separators=(",", ":")).encode("utf-8") + b"\n")
    report, code = vectors.run(str(tmp_path))
    assert code == 0
    assert report["tally"]["not_run"] == 1
    assert report["tally"]["skip"] == 0
    assert report["results"][0]["status"] == "not-run"
    assert "lint" in report["areas_not_run"]
    assert "not run by this package" in report["summary"]


def test_a_case_of_an_area_not_run_can_carry_its_own_reason(tmp_path):
    # bundle-0018 and bundle-0019 need the diagram compiler, not only the Bundle loader;
    # the area keeps its own reason in areas_not_run.
    area = tmp_path / "bundle"
    area.mkdir()
    for identifier in ("bundle-0001", "bundle-0018"):
        vector = {"area": "bundle", "description": "A fixture.", "expected": {},
                  "id": identifier, "input": {}, "level": "required", "rule": "AGSC-01-42"}
        (area / (identifier + ".json")).write_bytes(
            json.dumps(vector, separators=(",", ":")).encode("utf-8") + b"\n")
    report, _ = vectors.run(str(tmp_path))
    details = dict((one["id"], one["detail"]) for one in report["results"])
    assert details["bundle-0018"] == "needs the diagram compiler (Level 3)"
    assert details["bundle-0001"] == report["areas_not_run"]["bundle"]
    assert "Bundle loader" in report["areas_not_run"]["bundle"]


def test_the_pending_list_is_the_engines(tmp_path):
    pending = tmp_path / "pending.json"
    pending.write_bytes(json.dumps(
        {"pending": ["jcs-0001"], "reason": {"jcs-0001": "awaiting a decision"}}
    ).encode("utf-8"))
    report, code = vectors.run(str(VECTORS), pending_path=str(pending))
    assert code == 0
    assert report["tally"]["pending"] == 1
    skipped = [one for one in report["results"] if one["id"] == "jcs-0001"][0]
    assert skipped["status"] == "skip"
    assert skipped["detail"] == "awaiting a decision"


def test_a_pending_entry_with_no_reason_still_skips(tmp_path):
    pending = tmp_path / "pending.json"
    pending.write_bytes(b'{"pending":["jcs-0001"]}')
    report, _ = vectors.run(str(VECTORS), pending_path=str(pending))
    assert [one for one in report["results"] if one["id"] == "jcs-0001"][0]["detail"] == "pending"


def test_a_missing_pending_file_means_nothing_is_pending():
    assert vectors.load_pending(None) == (set(), {})
    assert vectors.load_pending("/no/such/file.json") == (set(), {})


def test_a_withdrawn_vector_counts_for_nothing(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    vector = {
        "area": "jcs", "description": "A withdrawn fixture.", "expected": {"withdrawn": True},
        "id": "jcs-9001", "input": {}, "level": "withdrawn",
        "reason": "superseded by a later case", "rule": "AGSC-04-05",
    }
    (area / "jcs-9001.json").write_bytes(
        json.dumps(vector, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
    report, code = vectors.run(str(tmp_path))
    assert code == 0
    assert report["tally"]["withdrawn"] == 1
    assert report["tally"]["pass"] == 0


def test_a_vector_naming_an_undeclared_surface_is_skipped_as_passed(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    vector = {
        "area": "jcs", "description": "A fixture.", "expected": {"output": "{}"},
        "id": "jcs-9002", "input": {"value": {}}, "level": "required",
        "requires_surface": ["solid"], "rule": "AGSC-04-05",
    }
    (area / "jcs-9002.json").write_bytes(
        json.dumps(vector, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
    report, _ = vectors.run(str(tmp_path))
    assert report["tally"]["pass"] == 1
    assert "surface not declared" in report["results"][0]["detail"]


def test_a_failing_vector_fails_the_run(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    vector = {
        "area": "jcs", "description": "A fixture whose expectation is wrong.",
        "expected": {"output": "{\"wrong\":1}"}, "id": "jcs-9003",
        "input": {"value": {"a": 1}}, "level": "required", "rule": "AGSC-04-05",
    }
    (area / "jcs-9003.json").write_bytes(
        json.dumps(vector, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
    report, code = vectors.run(str(tmp_path))
    assert code == 1
    assert report["status"] == "fail"
    assert report["results"][0]["status"] == "fail"


def test_a_handler_that_raises_is_a_failure_never_a_pass(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    vector = {
        "area": "jcs", "description": "A fixture with no input value.",
        "expected": {"output": "{}"}, "id": "jcs-9004", "input": {}, "level": "required",
        "rule": "AGSC-04-05",
    }
    (area / "jcs-9004.json").write_bytes(
        json.dumps(vector, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
    report, code = vectors.run(str(tmp_path))
    assert code == 1
    assert "handler raised" in report["results"][0]["detail"]


def test_an_empty_vector_set_is_a_failure(tmp_path):
    result, count, _ = vectors.validate(str(tmp_path))
    assert count == 0
    assert result["status"] == "fail"
    assert codes(result) == ["AGSC-E901"]


def _write(directory, name, vector, trailer=b"\n"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    body = json.dumps(vector, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    path.write_bytes(body.encode("utf-8") + trailer)
    return path


def _good(**overrides):
    vector = {
        "area": "jcs", "description": "A fixture.", "expected": {"output": "{}"},
        "id": "jcs-9100", "input": {"value": {}}, "level": "required",
        "options": {"spec_version": SPEC_VERSION}, "rule": "AGSC-04-05",
    }
    vector.update(overrides)
    return vector


def test_a_conforming_vector_file_passes(tmp_path):
    _write(tmp_path / "jcs", "jcs-9100.json", _good())
    result, count, _ = vectors.validate(str(tmp_path))
    assert result["status"] == "pass", result["findings"]
    assert count == 1


@pytest.mark.parametrize("overrides,expected", [
    ({"id": "JCS-1"}, "AGSC-E204"),
    ({"area": "nowhere"}, "AGSC-E203"),
    ({"level": "maybe"}, "AGSC-E203"),
    ({"rule": "nonsense"}, "AGSC-E204"),
    ({"rule": "AGSC-99-99"}, "AGSC-E201"),
    ({"expected": {"error": "AGSC-E999"}}, "AGSC-E203"),
    ({"options": {"spec_version": "9.9.9"}}, "AGSC-E201"),
])
def test_each_file_format_fault_raises_its_code(tmp_path, overrides, expected):
    _write(tmp_path / "jcs", "jcs-9100.json", _good(**overrides))
    result, _, _ = vectors.validate(str(tmp_path))
    assert expected in codes(result)


def test_a_missing_required_member_is_e202(tmp_path):
    vector = _good()
    del vector["description"]
    _write(tmp_path / "jcs", "jcs-9100.json", vector)
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E202" in codes(result)


def test_a_duplicate_id_is_e201(tmp_path):
    _write(tmp_path / "jcs", "jcs-9100.json", _good())
    _write(tmp_path / "jcs", "jcs-9100-copy.json", _good())
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E201" in codes(result)


def test_the_folder_must_agree_with_the_area(tmp_path):
    _write(tmp_path / "slug", "jcs-9100.json", _good())
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E205" in codes(result)


def test_encoding_faults_are_e108(tmp_path):
    _write(tmp_path / "jcs", "jcs-9100.json", _good(), trailer=b"\n\n")
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E108" in codes(result)

    other = tmp_path / "two" / "jcs"
    other.mkdir(parents=True)
    body = json.dumps(_good(), separators=(",", ":"), sort_keys=True)
    (other / "jcs-9100.json").write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8") + b"\r\n")
    result, _, _ = vectors.validate(str(tmp_path / "two"))
    assert codes(result).count("AGSC-E108") >= 2


def test_non_nfc_text_is_e108_unless_the_case_is_the_exemption(tmp_path):
    decomposed = _good(description="A fixture with a decomposed é.")
    _write(tmp_path / "jcs", "jcs-9100.json", decomposed)
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E108" in codes(result)

    exempt = tmp_path / "two" / "jcs"
    exempt.mkdir(parents=True)
    body = json.dumps(_good(id="jcs-0005", description="A fixture with a decomposed é."),
                      ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    (exempt / "jcs-9100.json").write_bytes(body.encode("utf-8") + b"\n")
    result, _, _ = vectors.validate(str(tmp_path / "two"))
    assert "AGSC-E108" not in codes(result)


def test_members_out_of_jcs_order_are_e601(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    (area / "jcs-9100.json").write_bytes(
        b'{"id":"jcs-9100","area":"jcs","description":"A fixture.","expected":{"output":"{}"},'
        b'"input":{"value":{}},"level":"required","rule":"AGSC-04-05"}\n')
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E601" in codes(result)


def test_the_input_value_subtree_is_exempt_from_the_order_rule(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    (area / "jcs-9100.json").write_bytes(
        b'{"area":"jcs","description":"A fixture.","expected":{"output":"{\\"a\\":1,\\"b\\":2}"},'
        b'"id":"jcs-9100","input":{"value":{"b":2,"a":1}},"level":"required",'
        b'"rule":"AGSC-04-05"}\n')
    result, _, _ = vectors.validate(str(tmp_path))
    assert result["status"] == "pass", result["findings"]


def test_a_withdrawn_vector_must_carry_a_reason_and_a_reduced_expectation(tmp_path):
    _write(tmp_path / "jcs", "jcs-9100.json", _good(level="withdrawn"))
    result, _, _ = vectors.validate(str(tmp_path))
    assert codes(result).count("AGSC-E202") == 1
    assert "AGSC-E201" in codes(result)


def test_a_file_that_is_not_json_is_e201(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    (area / "jcs-9100.json").write_bytes(b"not json\n")
    result, _, _ = vectors.validate(str(tmp_path))
    assert codes(result) == ["AGSC-E201"]


def test_the_bundled_spec_index_is_the_one_the_specification_declares():
    index = vectors.bundled_spec_index()
    # One constant names the version the package implements (B13 moves both to 1.1.0).
    assert index["spec_version"] == SPEC_VERSION
    assert "AGSC-04-05" in index["rule_ids"]
    assert "AGSC-E201" in index["error_codes"]
    # 1.1 registers AGSC-E005, E313 to E317, E417 to E423 and E512 (spec/09 section 9.4).
    assert len(index["error_codes"]) == 105
    assert "AGSC-E313" in index["error_codes"] and "AGSC-03-23" in index["rule_ids"]


def test_the_index_reads_the_declaration_not_a_candidate_quoted_as_history(tmp_path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "00-overview.md").write_bytes(
        b'`spec_version: "1.0.0"`. Rules follow.\n\n'
        b"> **This version.** Since `1.0.0-rc.6`, the first public release candidate, ...\n")
    (spec / "09-conformance.md").write_bytes(b"| `AGSC-E201` | a shape fault |\n")
    assert vectors.spec_index_from(str(spec))["spec_version"] == "1.0.0"


@pytest.mark.skipif(not (ENGINE / "spec").is_dir(), reason="the engine checkout is not here")
def test_the_bundled_index_agrees_with_the_live_specification():
    live = vectors.spec_index_from(str(ENGINE / "spec"))
    assert live == vectors.bundled_spec_index()


@pytest.mark.skipif(not (ENGINE / "tests" / "vectors").is_dir(),
                    reason="the engine checkout is not here")
def test_the_shipped_copies_are_the_engines_bytes():
    for area in vectors_module_areas():
        # Every file of the engine's area is here, and nothing else is.
        assert sorted(os.listdir(str(VECTORS / area))) == \
            sorted(os.listdir(str(ENGINE / "tests" / "vectors" / area))), area
        for name in sorted(os.listdir(str(VECTORS / area))):
            ours = (VECTORS / area / name).read_bytes()
            theirs = (ENGINE / "tests" / "vectors" / area / name).read_bytes()
            assert ours == theirs, "%s/%s has drifted from the engine's copy" % (area, name)


@pytest.mark.skipif(not (ENGINE / "tests" / "vectors").is_dir(),
                    reason="the engine checkout is not here")
def test_the_whole_engine_vector_set_passes_the_file_format_check():
    result, count, _ = vectors.validate(str(ENGINE / "tests" / "vectors"))
    assert result["status"] == "pass", result["findings"][:5]
    assert count > 100


def test_a_vector_directory_that_is_not_tests_vectors_still_names_files(tmp_path):
    _write(tmp_path / "jcs", "jcs-9100.json", _good(id="JCS-1"))
    result, _, _ = vectors.validate(str(tmp_path), root=str(tmp_path))
    assert result["findings"][0]["file"] == "jcs/jcs-9100.json"


def test_a_specification_that_declares_no_rule_is_called_vacuous(tmp_path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "00-overview.md").write_bytes(b"1.0.0\n")
    (spec / "09-conformance.md").write_bytes(b"| `AGSC-E201` | a shape fault |\n")
    area = tmp_path / "vectors" / "jcs"
    _write(area, "jcs-9100.json", _good())
    result, _, _ = vectors.validate(str(tmp_path / "vectors"), spec=str(spec))
    assert "AGSC-E901" in codes(result)
    assert any("vacuous" in one["message"] for one in result["findings"])


def test_a_slug_vector_that_states_no_pattern_still_runs(tmp_path):
    area = tmp_path / "slug"
    area.mkdir()
    vector = {
        "area": "slug", "description": "A fixture.",
        "expected": {"invalid": ["A"], "valid": ["ok"]}, "id": "slug-9001",
        "input": {"candidates": ["ok", "A"]}, "level": "required", "rule": "AGSC-01-10",
    }
    (area / "slug-9001.json").write_bytes(
        json.dumps(vector, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
    report, code = vectors.run(str(tmp_path))
    assert code == 0 and report["tally"]["pass"] == 1


def _withdrawn(**overrides):
    vector = _good(expected={"withdrawn": True}, level="withdrawn",
                   reason="replaced by a later case")
    vector.update(overrides)
    return vector


def test_a_withdrawn_vector_may_name_the_vector_that_supersedes_it(tmp_path):
    _write(tmp_path / "jcs", "jcs-9100.json", _withdrawn(superseded_by="jcs-9101"))
    _write(tmp_path / "jcs", "jcs-9101.json", _good(id="jcs-9101"))
    result, _, _ = vectors.validate(str(tmp_path))
    assert result["status"] == "pass", result["findings"]


@pytest.mark.parametrize("vector,expected", [
    # AGSC-09-04: only a withdrawn vector carries the link...
    (_good(superseded_by="jcs-9101"), ["AGSC-E201"]),
    # ...it is a vector identifier...
    (_withdrawn(superseded_by="JCS-1"), ["AGSC-E204"]),
    (_withdrawn(superseded_by=7), ["AGSC-E204"]),
    # ...and it names a vector of the same set.
    (_withdrawn(superseded_by="jcs-9999"), ["AGSC-E201"]),
    (_good(superseded_by="jcs-9999"), ["AGSC-E201", "AGSC-E201"]),
], ids=["not-withdrawn", "not-an-id", "not-a-string", "names-no-vector", "both"])
def test_a_superseded_by_link_is_checked_as_the_engine_checks_it(tmp_path, vector, expected):
    _write(tmp_path / "jcs", "jcs-9100.json", vector)
    _write(tmp_path / "jcs", "jcs-9101.json", _good(id="jcs-9101"))
    result, _, _ = vectors.validate(str(tmp_path))
    assert codes(result) == expected


def test_a_folder_with_no_file_of_the_vector_shape_is_not_a_vector_tree(tmp_path):
    # One area folder given in place of the tree: the files sit one level too high.
    _write(tmp_path, "jcs-9100.json", _good())
    result, count, _ = vectors.validate(str(tmp_path))
    assert codes(result) == ["AGSC-E901"] and count == 0
    assert "not a vector directory" in result["findings"][0]["message"]


def test_a_published_skills_index_is_not_judged_as_a_vector(tmp_path):
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "index.json").write_bytes(b'{"skills":[]}\n')
    result, count, _ = vectors.validate(str(tmp_path))
    assert codes(result) == ["AGSC-E901"] and count == 0


def test_inside_a_vector_tree_a_misnamed_file_is_still_judged(tmp_path):
    _write(tmp_path / "jcs", "jcs-9100.json", _good())
    (tmp_path / "jcs" / "notes.json").write_bytes(b"not json\n")
    result, count, _ = vectors.validate(str(tmp_path))
    assert codes(result) == ["AGSC-E201"] and count == 2


def test_a_missing_folder_is_an_e901_finding(tmp_path):
    result, count, _ = vectors.validate(str(tmp_path / "nowhere"))
    assert codes(result) == ["AGSC-E901"] and count == 0
    assert "no such directory" in result["findings"][0]["message"]


def _engine_validate(directory):
    done = subprocess.run(["node", str(ENGINE / "tools" / "validate-vectors"), str(directory),
                           "--json"], capture_output=True, text=True, cwd=str(ENGINE))
    envelope = json.loads(done.stdout)
    return done.returncode, envelope["status"], sorted(one["code"] for one in envelope["findings"])


def _python_validate(directory):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["validate-vectors", str(directory), "--json"], out=out, err=err)
    envelope = json.loads(out.getvalue())
    return code, envelope["status"], sorted(one["code"] for one in envelope["findings"])


def _vector_tree_with(tmp_path, identifier, **members):
    tree = tmp_path / "vectors"
    shutil.copytree(str(VECTORS), str(tree))
    path = next(tree.glob("*/%s*.json" % identifier))
    vector = json.loads(path.read_text(encoding="utf-8"))
    vector.update(members)
    path.write_text(json.dumps(vector, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return tree


def _inputs_the_two_validators_judge(tmp_path):
    skills = tmp_path / "site"
    (skills / "skills").mkdir(parents=True)
    (skills / "skills" / "index.json").write_bytes(b'{"skills":[]}\n')
    return {
        "copies": VECTORS,
        "superseded-by-on-a-required-vector":
            _vector_tree_with(tmp_path / "a", "slug-0001", superseded_by="slug-9999"),
        "superseded-by-on-a-withdrawn-vector":
            _vector_tree_with(tmp_path / "b", "disc-0013", superseded_by="disc-0004"),
        "one-area-folder": VECTORS / "slug",
        "a-skills-index-only": skills,
        "a-missing-folder": tmp_path / "nowhere",
    }


@pytest.mark.skipif(not (engine_available() and (ENGINE / "tools" / "validate-vectors").is_file()),
                    reason="the validator equivalence needs Node and the engine checkout")
@pytest.mark.parametrize("name", ["copies", "superseded-by-on-a-required-vector",
                                  "superseded-by-on-a-withdrawn-vector", "one-area-folder",
                                  "a-skills-index-only", "a-missing-folder"])
def test_both_validators_agree(tmp_path, name):
    directory = _inputs_the_two_validators_judge(tmp_path)[name]
    assert _python_validate(directory) == _engine_validate(directory)
