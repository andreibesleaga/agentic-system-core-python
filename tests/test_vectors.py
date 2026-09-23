"""The vector-set checker and the runner for the areas this package covers."""

import json
import os
import shutil

import pytest

from agentic_system_core import vectors
from conftest import ENGINE, VECTORS


def vectors_module_areas():
    """The areas this package runs natively, as the runner reports them."""
    return ["build", "discovery", "frontmatter", "graph", "jcs", "links", "slug"]


def codes(result):
    return sorted(one["code"] for one in result["findings"])


def test_the_shipped_vector_copies_pass_the_file_format_check():
    result, count, empty = vectors.validate(str(VECTORS))
    assert result["status"] == "pass", result["findings"]
    assert count == 75
    for area in vectors_module_areas():
        assert area not in empty
    assert "lint" in empty


def test_every_vector_of_every_area_this_package_runs_passes():
    report, code = vectors.run(str(VECTORS))
    assert code == 0
    assert report["tally"]["fail"] == 0
    assert report["tally"]["pass"] == 59
    assert report["tally"]["withdrawn"] == 16
    assert report["tally"]["not_run"] == 0
    assert report["areas_run"] == vectors_module_areas()
    assert report["areas_not_run"] == {}
    assert "59 pass" in report["summary"]


def test_a_level_selects_its_area_set():
    report, _ = vectors.run(str(VECTORS), level=0)
    # Level 0 runs frontmatter, slug, bundle and discovery only (AGSC-10-02).
    assert report["total"] == 12 + 5 + 16
    assert report["tally"]["pass"] == 12 + 5 + 9
    report, _ = vectors.run(str(VECTORS), level=3)
    assert report["total"] == 75


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
        "options": {"spec_version": "1.0.0-rc.6"}, "rule": "AGSC-04-05",
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
    ({"options": {"spec_version": "1.0.0-rc.1"}}, "AGSC-E201"),
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
    _write(tmp_path / "jcs", "a.json", _good())
    _write(tmp_path / "jcs", "b.json", _good())
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E201" in codes(result)


def test_the_folder_must_agree_with_the_area(tmp_path):
    _write(tmp_path / "slug", "jcs-9100.json", _good())
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E205" in codes(result)


def test_encoding_faults_are_e108(tmp_path):
    _write(tmp_path / "jcs", "a.json", _good(), trailer=b"\n\n")
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E108" in codes(result)

    other = tmp_path / "two" / "jcs"
    other.mkdir(parents=True)
    body = json.dumps(_good(), separators=(",", ":"), sort_keys=True)
    (other / "a.json").write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8") + b"\r\n")
    result, _, _ = vectors.validate(str(tmp_path / "two"))
    assert codes(result).count("AGSC-E108") >= 2


def test_non_nfc_text_is_e108_unless_the_case_is_the_exemption(tmp_path):
    decomposed = _good(description="A fixture with a decomposed é.")
    _write(tmp_path / "jcs", "a.json", decomposed)
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E108" in codes(result)

    exempt = tmp_path / "two" / "jcs"
    exempt.mkdir(parents=True)
    body = json.dumps(_good(id="jcs-0005", description="A fixture with a decomposed é."),
                      ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    (exempt / "a.json").write_bytes(body.encode("utf-8") + b"\n")
    result, _, _ = vectors.validate(str(tmp_path / "two"))
    assert "AGSC-E108" not in codes(result)


def test_members_out_of_jcs_order_are_e601(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    (area / "a.json").write_bytes(
        b'{"id":"jcs-9100","area":"jcs","description":"A fixture.","expected":{"output":"{}"},'
        b'"input":{"value":{}},"level":"required","rule":"AGSC-04-05"}\n')
    result, _, _ = vectors.validate(str(tmp_path))
    assert "AGSC-E601" in codes(result)


def test_the_input_value_subtree_is_exempt_from_the_order_rule(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    (area / "a.json").write_bytes(
        b'{"area":"jcs","description":"A fixture.","expected":{"output":"{\\"a\\":1,\\"b\\":2}"},'
        b'"id":"jcs-9100","input":{"value":{"b":2,"a":1}},"level":"required",'
        b'"rule":"AGSC-04-05"}\n')
    result, _, _ = vectors.validate(str(tmp_path))
    assert result["status"] == "pass", result["findings"]


def test_a_withdrawn_vector_must_carry_a_reason_and_a_reduced_expectation(tmp_path):
    _write(tmp_path / "jcs", "a.json", _good(level="withdrawn"))
    result, _, _ = vectors.validate(str(tmp_path))
    assert codes(result).count("AGSC-E202") == 1
    assert "AGSC-E201" in codes(result)


def test_a_file_that_is_not_json_is_e201(tmp_path):
    area = tmp_path / "jcs"
    area.mkdir()
    (area / "a.json").write_bytes(b"not json\n")
    result, _, _ = vectors.validate(str(tmp_path))
    assert codes(result) == ["AGSC-E201"]


def test_the_bundled_spec_index_is_the_one_the_specification_declares():
    index = vectors.bundled_spec_index()
    assert index["spec_version"] == "1.0.0-rc.6"
    assert "AGSC-04-05" in index["rule_ids"]
    assert "AGSC-E201" in index["error_codes"]
    assert len(index["error_codes"]) == 90


@pytest.mark.skipif(not (ENGINE / "spec").is_dir(), reason="the engine checkout is not here")
def test_the_bundled_index_agrees_with_the_live_specification():
    live = vectors.spec_index_from(str(ENGINE / "spec"))
    assert live == vectors.bundled_spec_index()


@pytest.mark.skipif(not (ENGINE / "tests" / "vectors").is_dir(),
                    reason="the engine checkout is not here")
def test_the_shipped_copies_are_the_engines_bytes():
    for area in vectors_module_areas():
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
    _write(tmp_path / "jcs", "a.json", _good(id="JCS-1"))
    result, _, _ = vectors.validate(str(tmp_path), root=str(tmp_path))
    assert result["findings"][0]["file"] == "jcs/a.json"


def test_a_specification_that_declares_no_rule_is_called_vacuous(tmp_path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "00-overview.md").write_bytes(b"1.0.0-rc.6\n")
    (spec / "09-conformance.md").write_bytes(b"| `AGSC-E201` | a shape fault |\n")
    area = tmp_path / "vectors" / "jcs"
    _write(area, "a.json", _good())
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
