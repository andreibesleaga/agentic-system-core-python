"""Every area handler fails closed: an expectation it cannot check is a failure,
never a pass, and a wrong expectation is caught."""

import copy
import json

import pytest

from agentic_system_core.areas import AREA_RUNNERS
from conftest import VECTORS


def vector(identifier):
    for path in VECTORS.rglob("*.json"):
        data = json.loads(path.read_bytes().decode("utf-8"))
        if data["id"] == identifier:
            return data
    raise KeyError(identifier)


def _needs_build(data):
    """A vector whose input is a whole Bundle, or which states the publisher's JSON-LD
    files, is reported not run, never judged."""
    given = data["input"]
    if data["area"] == "build":
        return any(k in given for k in ("bundle", "files"))
    if data["area"] == "graph":
        return ("bundle" in given and isinstance(given.get("item"), dict)) or "graph_jsonld" in data["expected"]
    return data["area"] == "discovery" and "bundle" in given and "items" not in given


RUN = [one for one in sorted(VECTORS.rglob("*.json"))
       if json.loads(one.read_bytes().decode("utf-8"))["area"] not in ("jcs", "slug")
       and not _needs_build(json.loads(one.read_bytes().decode("utf-8")))]


def test_a_vector_that_needs_a_whole_build_is_reported_not_run():
    for identifier in ("build-0015", "build-0017", "disc-0018", "graph-0027"):
        data = vector(identifier)
        result = AREA_RUNNERS[data["area"]](data)
        assert result["status"] == "not-run"
        assert "whole Bundle" in result["detail"] or "full Bundle build" in result["detail"]


def test_the_publishers_json_ld_files_are_reported_not_run():
    data = vector("graph-0028")
    result = AREA_RUNNERS[data["area"]](data)
    assert result["status"] == "not-run"
    assert "graph.jsonld writer" in result["detail"]


@pytest.mark.parametrize("path", RUN, ids=[one.stem for one in RUN])
def test_an_unknown_expected_member_fails(path):
    data = json.loads(path.read_bytes().decode("utf-8"))
    data["expected"]["zz_unknown_member"] = True
    assert AREA_RUNNERS[data["area"]](data)["status"] == "fail"


@pytest.mark.parametrize("path", RUN, ids=[one.stem for one in RUN])
def test_every_scalar_expectation_flipped_fails(path):
    data = json.loads(path.read_bytes().decode("utf-8"))
    for key, value in data["expected"].items():
        if isinstance(value, bool) and not key.endswith("_asserted"):
            flipped = copy.deepcopy(data)
            flipped["expected"][key] = not value
            assert AREA_RUNNERS[data["area"]](flipped)["status"] == "fail", key


@pytest.mark.parametrize("area", ["build", "discovery", "frontmatter", "graph"])
def test_an_input_shape_no_handler_knows_fails(area):
    result = AREA_RUNNERS[area]({"expected": {}, "input": {"zz": 1}})
    assert result["status"] == "fail"


def test_case_lists_with_missing_or_extra_cases_fail():
    for identifier in ("build-0013", "build-0014", "disc-0012", "disc-0015"):
        data = vector(identifier)
        extra = copy.deepcopy(data)
        extra["input"]["cases"].append(dict(extra["input"]["cases"][0], name="zz-no-expectation"))
        assert AREA_RUNNERS[data["area"]](extra)["status"] == "fail", identifier
        unknown = copy.deepcopy(data)
        unknown["expected"]["cases"][0]["zz_member"] = 1
        assert AREA_RUNNERS[data["area"]](unknown)["status"] == "fail", identifier
    data = vector("disc-0015")
    missing = copy.deepcopy(data)
    missing["input"]["cases"].pop()
    assert AREA_RUNNERS["discovery"](missing)["status"] == "fail"
    last = vector("build-0014")
    now = copy.deepcopy(last)
    now["expected"]["cases"][-1]["zz"] = 1
    assert AREA_RUNNERS["build"](now)["status"] == "fail"


def test_wrong_bytes_are_caught():
    for identifier, member in (("graph-0026", "turtle"), ("graph-0021", "nquads"),
                               ("disc-0013", "output"), ("build-0003", "output"),
                               ("fm-0008", "output")):
        data = vector(identifier)
        data["expected"][member] = data["expected"][member] + "x"
        assert AREA_RUNNERS[data["area"]](data)["status"] == "fail", identifier


def test_negative_vectors_that_expect_a_different_code_fail():
    for identifier in ("graph-0003", "links-0002", "fm-0005", "fm-0004"):
        data = vector(identifier)
        data["expected"]["error"] = "AGSC-E999"
        assert AREA_RUNNERS[data["area"]](data)["status"] == "fail", identifier


def test_the_links_area_reports_errors_on_a_clean_case():
    data = vector("links-0001")
    data["expected"]["errors"] = ["AGSC-E301"]
    assert AREA_RUNNERS["links"](data)["status"] == "fail"
    data = vector("links-0004")
    data["expected"]["errors"] = ["AGSC-E301"]
    assert AREA_RUNNERS["links"](data)["status"] == "fail"
