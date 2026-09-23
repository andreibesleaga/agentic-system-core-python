"""Canonical JSON: the number forms, the two orderings and the strict reader."""

import pytest

from agentic_system_core import jcs


@pytest.mark.parametrize("value,expected", [
    (0, "0"),
    (1, "1"),
    (-1, "-1"),
    (1.5, "1.5"),
    (-0.5, "-0.5"),
    (0.0, "0"),
    (-0.0, "0"),
    (100.0, "100"),
    (1e21, "1e+21"),
    (1e-7, "1e-7"),
    (1e-6, "0.000001"),
    (0.0001, "0.0001"),
    (1e-21, "1e-21"),
    (123456789012345678901234567890.0, "1.2345678901234568e+29"),
    (5e-324, "5e-324"),
])
def test_number_forms(value, expected):
    assert jcs.serialize_number(value) == expected


def test_non_finite_number_is_refused():
    with pytest.raises(jcs.JcsError):
        jcs.serialize_number(float("inf"))
    with pytest.raises(jcs.JcsError):
        jcs.serialize_number(float("nan"))


def test_member_names_sort_by_utf16_code_unit():
    # U+10000 encodes as D800 DC00, whose first unit is below U+FF01, so the
    # astral name sorts first - the opposite of a code point sort.
    assert jcs.canonicalize({"！": 1, "\U00010000": 2}) == '{"\U00010000":2,"！":1}'
    assert jcs.compare_utf16("\U00010000", "Ｚ") < 0
    assert jcs.compare_code_point("\U00010000", "Ｚ") > 0
    assert jcs.compare_utf16("a", "a") == 0
    assert jcs.compare_code_point("a", "a") == 0
    assert jcs.compare_code_point("b", "a") == 1


def test_names_are_normalised_before_they_are_sorted():
    decomposed = "é"
    assert jcs.canonicalize({decomposed: 2, "f": 1}) == '{"f":1,"é":2}'
    # Sorting the raw name would have put the decomposed one first.
    assert jcs.canonicalize_raw({decomposed: 2, "f": 1}) == '{"é":2,"f":1}'


def test_string_escaping():
    assert jcs.serialize_string('a"b\\c') == '"a\\"b\\\\c"'
    assert jcs.serialize_string("\n\t\r\b\f") == '"\\n\\t\\r\\b\\f"'
    assert jcs.serialize_string("\u0000\u001f") == '"\\u0000\\u001f"'
    assert jcs.serialize_string("é\U0001f600") == '"é\U0001f600"'


def test_canonicalize_shapes():
    assert jcs.canonicalize(None) == "null"
    assert jcs.canonicalize(True) == "true"
    assert jcs.canonicalize(False) == "false"
    assert jcs.canonicalize([1, "a", None]) == '[1,"a",null]'
    assert jcs.canonicalize({}) == "{}"


def test_canonicalize_refuses_a_value_that_is_not_json():
    with pytest.raises(jcs.JcsError):
        jcs.canonicalize({"a": object()})
    with pytest.raises(jcs.JcsError):
        jcs.canonicalize_raw({1: "a"})


def test_ijson_admissibility():
    assert jcs.is_ijson({"a": [1, 2.5, "x", None, True]})
    assert not jcs.is_ijson(float("inf"))
    assert not jcs.is_ijson(jcs.MAX_SAFE_INTEGER + 1)
    assert not jcs.is_ijson(float(jcs.MAX_SAFE_INTEGER + 1) * 2)
    assert not jcs.is_ijson(object())
    assert not jcs.is_ijson({"a": object()})
    assert jcs.is_ijson([])


def test_lone_surrogates_are_outside_ijson():
    lone = "\ud800"
    assert jcs.has_lone_surrogate(lone)
    assert jcs.has_lone_surrogate("\udc00")
    assert jcs.has_lone_surrogate("a\ud800")
    assert not jcs.has_lone_surrogate("\U0001f600")
    assert not jcs.is_ijson(lone)


def test_duplicate_member_names_after_nfc_are_refused():
    with pytest.raises(jcs.JcsError):
        jcs.assert_ijson({"é": 1, "é": 2})


def test_strict_reader_accepts_a_document():
    parsed = jcs.parse_ijson('{"b":1,"a":[1,2,{"c":null}],"s":"x\\u0041\\n"}')
    assert list(parsed.keys()) == ["b", "a", "s"]
    assert parsed["s"] == "xA\n"
    assert parsed["a"][2] == {"c": None}


def test_strict_reader_reads_surrogate_pairs_and_literals():
    assert jcs.parse_ijson('"\\ud83d\\ude00"') == "\U0001f600"
    assert jcs.parse_ijson('"\U0001f600"') == "\U0001f600"
    assert jcs.parse_ijson('"\\"\\\\\\/\\b\\f"') == '"\\/\b\f'


@pytest.mark.parametrize("text", [
    "﻿{}",
    '{"a":1,"a":2}',
    "{} trailing",
    '{"a"}',
    "{'a':1}",
    '{"a":}',
    '{"a":1',
    '["a"',
    '"\\ud800"',
    '"\\udc00x"',
    '"\\q"',
    '"\\u00zz"',
    '"unterminated',
    '"\t"',
    "01",
    "1.",
    "1e",
    "-",
    "",
    "   ",
    "tru",
    '{"a":1 "b":2}',
    '[1 2]',
    '"\\',
])
def test_strict_reader_refuses(text):
    with pytest.raises(ValueError):
        jcs.parse_ijson(text)


def test_strict_reader_numbers():
    assert jcs.parse_ijson("0") == 0
    assert jcs.parse_ijson("-12") == -12
    assert jcs.parse_ijson("1.25") == 1.25
    assert jcs.parse_ijson("1e3") == 1000.0
    assert jcs.parse_ijson("1E+3") == 1000.0
    assert jcs.parse_ijson("[]") == []
    assert jcs.parse_ijson("{}") == {}
    assert jcs.parse_ijson("true") is True
    assert jcs.parse_ijson("false") is False
    assert jcs.parse_ijson("null") is None


def test_nfc_passes_non_strings_through():
    assert jcs.nfc(5) == 5


def test_a_high_surrogate_followed_by_something_else_is_lone():
    assert jcs.has_lone_surrogate("\ud800a")


def test_the_raw_canonicaliser_refuses_a_value_that_is_not_json():
    with pytest.raises(jcs.JcsError):
        jcs.canonicalize_raw(object())


def test_a_member_name_that_is_not_a_string_is_outside_ijson():
    with pytest.raises(jcs.JcsError):
        jcs.assert_ijson({1: "a"})
