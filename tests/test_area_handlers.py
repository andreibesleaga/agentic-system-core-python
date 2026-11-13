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


def _not_run(data):
    """A vector this package reports as not run, with its reason, is never judged, and nor
    is a withdrawn one, which the runner skips before any handler. A handler that raises
    is judged: the runner reports the raise as a failure."""
    if data.get("level") == "withdrawn":
        return True
    try:
        return AREA_RUNNERS[data["area"]](copy.deepcopy(data))["status"] == "not-run"
    except Exception:
        return False


RUN = [one for one in sorted(VECTORS.rglob("*.json"))
       if not _not_run(json.loads(one.read_bytes().decode("utf-8")))]


def test_a_vector_that_needs_a_whole_build_is_reported_not_run():
    for identifier in ("build-0015", "build-0017", "disc-0018", "graph-0027"):
        data = vector(identifier)
        result = AREA_RUNNERS[data["area"]](data)
        assert result["status"] == "not-run"
        assert "whole Bundle" in result["detail"] or "full Bundle build" in result["detail"]


def test_the_publishers_json_ld_files_are_written_and_compared_whole():
    # graph-0028 (AGSC-05-09): graph.jsonld and every per-item file, after JCS.
    data = vector("graph-0028")
    result = AREA_RUNNERS[data["area"]](data)
    assert result["status"] == "pass", result["detail"]


@pytest.mark.parametrize("member", ["graph_jsonld", "per_item"])
def test_a_changed_json_ld_expectation_fails(member):
    data = vector("graph-0028")
    document = data["expected"]["graph_jsonld"] if member == "graph_jsonld" \
        else data["expected"]["per_item"]["beta"]
    document["@graph"][1]["prefLabel"]["@value"] = "Changed"
    result = AREA_RUNNERS[data["area"]](data)
    assert result["status"] == "fail"


def test_a_per_item_file_the_vector_does_not_state_fails():
    data = vector("graph-0028")
    del data["expected"]["per_item"]["group"]
    assert AREA_RUNNERS[data["area"]](data)["status"] == "fail"


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


def test_the_level_the_level_zero_case_states_is_asserted():
    # The case states the Level its documents are the form of; a case stating another
    # Level fails, as it does in the engine's runner.
    data = vector("disc-0004")
    assert AREA_RUNNERS["discovery"](data)["status"] == "pass"
    mutated = copy.deepcopy(data)
    mutated["expected"]["level"] = data["expected"]["level"] + 1
    result = AREA_RUNNERS["discovery"](mutated)
    assert result["status"] == "fail", result
    assert "level" in result["detail"]


def test_the_portable_pattern_case_asserts_lookahead_in_either_polarity():
    # `lookahead` is asserted at the value the case states: a case that states the
    # other value fails.
    data = vector("slug-0006")
    assert data["expected"]["lookahead"] is False
    assert AREA_RUNNERS["slug"](data)["status"] == "pass"
    mutated = copy.deepcopy(data)
    mutated["expected"]["lookahead"] = True
    result = AREA_RUNNERS["slug"](mutated)
    assert result["status"] == "fail", result
    assert "lookahead" in result["detail"]


def test_the_portable_pattern_case_asserts_the_engine_features_it_states():
    # slug-0006: the non-portable features the pattern uses (none), as the engine's
    # handler reads them from the pattern source; a case stating one fails.
    data = vector("slug-0006")
    assert data["expected"]["engine_features_used"] == []
    mutated = copy.deepcopy(data)
    mutated["expected"]["engine_features_used"] = ["lookahead"]
    result = AREA_RUNNERS["slug"](mutated)
    assert result["status"] == "fail", result
    assert "engine-features-used" in result["detail"]


@pytest.mark.parametrize("source, used", [
    ("^[a-z0-9]+(?:-[a-z0-9]+)*$", []),
    ("^(?=a)(?<!b)\\1(?<n>x)(?>y)a++\\u0041\\p{L}$",
     ["lookahead", "lookbehind", "backreference", "named group", "atomic group",
      "possessive quantifier", "unicode escape", "property escape"]),
])
def test_the_non_portable_features_are_named_as_the_engine_names_them(source, used):
    from agentic_system_core.areas import slug_area
    assert slug_area.features_used(source) == used


def test_a_pass_that_left_an_expected_member_unread_is_a_fail():
    # The engine's guard (tests/conformance/areas/_expected-reads.js): a handler that
    # never read a member of `expected` asserted nothing about it.
    from agentic_system_core.areas._expected_reads import guarded

    def reads_a(data):
        return {"status": "pass" if data["expected"]["a"] == 1 else "fail", "detail": ""}

    assert guarded(reads_a)({"id": "x-0001", "expected": {"a": 1}})["status"] == "pass"
    result = guarded(reads_a)({"id": "x-0001", "expected": {"a": 1, "b": 2}})
    assert result == {"status": "fail", "detail": 'x-0001: no branch of the handler reads "b"'}
    nothing = guarded(lambda data: {"status": "pass", "detail": ""})({"id": "x-0002",
                                                                       "expected": {}})
    assert nothing["status"] == "fail" and "states no expected member" in nothing["detail"]
    # Presence tests, `get` and listing the members count as reads, as in the engine.
    for handler in (lambda data: "a" in data["expected"], lambda data: data["expected"].get("a"),
                    lambda data: list(data["expected"]), lambda data: dict(data["expected"]),
                    lambda data: data["expected"].keys(), lambda data: data["expected"].items(),
                    lambda data: data["expected"].values()):
        def run(data, handler=handler):
            handler(data)
            return {"status": "pass", "detail": ""}
        assert guarded(run)({"id": "x-0003", "expected": {"a": 1}})["status"] == "pass"
    # A fail and a not-run pass through unchanged, and the vector is not changed.
    own = {"status": "fail", "detail": "own"}
    case = {"id": "x-0004", "expected": {"a": 1}}
    assert guarded(lambda data: own)(case) is own
    assert guarded(lambda data: {"status": "not-run", "detail": "r"})(case)["status"] == "not-run"
    assert type(case["expected"]) is dict
    # A case whose `expected` is not an object is the handler's to judge.
    assert guarded(lambda data: {"status": "pass", "detail": ""})(
        {"id": "x-0005", "expected": None})["status"] == "pass"


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_a_forbidden_form_the_handler_does_not_know_fails(index):
    # graph-0018: each entry of `forbidden` is a prose statement of a form the rules
    # exclude, checked by its own reading; an entry no reading knows fails, as in the
    # engine's `forbiddenCheck`.
    data = vector("graph-0018")
    assert AREA_RUNNERS["graph"](data)["status"] == "pass"
    data["expected"]["forbidden"][index] = "zz a clause no handler knows"
    result = AREA_RUNNERS["graph"](data)
    assert result["status"] == "fail", result
    assert "does not implement that clause" in result["detail"]


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
                               ("disc-0024", "output"), ("disc-0034", "output"),
                               ("build-0003", "output"), ("fm-0008", "output"),
                               ("graph-0040", "skos")):
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


@pytest.mark.parametrize("identifier, reason", [
    ("build-0031", "writes no HTML"), ("build-0032", "writes no HTML"),
    ("build-0037", "chunk"),
    ("disc-0020", "whole link table"), ("disc-0021", "whole link table"),
    ("fm-0022", "domain layer: engine only in 1.1"),
    ("graph-0044", "domain layer: engine only in 1.1"),
    ("links-0019", "domain layer: engine only in 1.1"),
])
def test_a_case_this_package_cannot_run_is_reported_not_run_with_its_reason(identifier,
                                                                             reason):
    data = vector(identifier)
    result = AREA_RUNNERS[data["area"]](data)
    assert result["status"] == "not-run"
    assert reason in result["detail"]


@pytest.mark.parametrize("identifier", ["links-0010", "links-0012", "links-0014",
                                        "links-0016"])
def test_a_warning_the_case_does_not_state_fails(identifier):
    data = vector(identifier)
    assert AREA_RUNNERS["links"](data)["status"] == "pass"
    data["expected"]["warnings"] = data["expected"]["warnings"][1:]
    assert AREA_RUNNERS["links"](data)["status"] == "fail"


@pytest.mark.parametrize("identifier", ["graph-0029", "graph-0030", "graph-0035",
                                        "graph-0038"])
def test_a_changed_reading_or_answer_fails(identifier):
    data = vector(identifier)
    assert AREA_RUNNERS["graph"](data)["status"] == "pass"
    member = "readings" if "readings" in data["expected"] else "answer"
    value = data["expected"][member]
    data["expected"][member] = value[1:] if isinstance(value, list) else {}
    assert AREA_RUNNERS["graph"](data)["status"] == "fail"


def test_the_nesting_cases_count_their_warnings():
    data = vector("fm-0026")
    assert AREA_RUNNERS["frontmatter"](data)["status"] == "pass"
    data["expected"]["warning_count"] = 1
    assert AREA_RUNNERS["frontmatter"](data)["status"] == "fail"
    data = vector("fm-0021")
    data["expected"]["warnings"] = [{"code": "AGSC-E105", "severity": "error"}]
    assert AREA_RUNNERS["frontmatter"](data)["status"] == "fail"


def test_the_disclosure_page_and_the_restricted_now_line_are_asserted():
    data = vector("build-0035")
    data["expected"]["cases"][0]["text"] = data["expected"]["cases"][1]["text"]
    assert AREA_RUNNERS["build"](data)["status"] == "fail"
    data = vector("build-0036")
    data["expected"]["cases"][1]["line"] = data["expected"]["cases"][0]["line"]
    assert AREA_RUNNERS["build"](data)["status"] == "fail"
