"""Canonical JSON (RFC 8785) and the strict I-JSON reader the checkers need.

Two orderings live in this specification and they are not interchangeable:
JSON member names sort by UTF-16 code units (AGSC-04-05) and everything else
sorts by Unicode code point (AGSC-04-12).  They differ only for astral-plane
text, which vector ``jcs-0003`` exists to prove, so both are spelled out here
rather than left to the runtime's default ordering.

AGSC-04-21 adds one thing on top of RFC 8785: member names are NFC-normalised
BEFORE they are sorted.  ``canonicalize`` does that; ``canonicalize_raw`` does
not, and is the form the discovery-file checker compares bytes against, because
the Node tool it mirrors uses the same raw form there.

Standard library only.
"""

import math
import unicodedata

#: 2**53 - 1, the I-JSON integer bound (RFC 7493).
MAX_SAFE_INTEGER = 9007199254740991

_SHORT_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


class JcsError(ValueError):
    """A value that cannot be canonicalised.  Always carries a registered code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def utf16_key(text):
    """Sort key that orders strings by UTF-16 code unit, as AGSC-04-05 requires.

    Comparing the big-endian UTF-16 bytes of two strings compares their code
    unit sequences, which is what a JavaScript ``Array.prototype.sort`` does to
    member names and what RFC 8785 section 3.2.3 pins.
    """
    return text.encode("utf-16-be", "surrogatepass")


def compare_utf16(a, b):
    """-1, 0 or 1 for two strings under the UTF-16 code unit ordering."""
    ka, kb = utf16_key(a), utf16_key(b)
    return -1 if ka < kb else (1 if ka > kb else 0)


def compare_code_point(a, b):
    """-1, 0 or 1 under the Unicode code point ordering (AGSC-04-12)."""
    return -1 if a < b else (1 if a > b else 0)


def nfc(text):
    """NFC-normalise a string (AGSC-04-07); anything else passes through."""
    return unicodedata.normalize("NFC", text) if isinstance(text, str) else text


def has_lone_surrogate(text):
    """True when the string holds an unpaired surrogate code unit."""
    units = text.encode("utf-16-be", "surrogatepass")
    i = 0
    while i < len(units):
        unit = (units[i] << 8) | units[i + 1]
        if 0xD800 <= unit <= 0xDBFF:
            if i + 3 >= len(units):
                return True
            following = (units[i + 2] << 8) | units[i + 3]
            if not 0xDC00 <= following <= 0xDFFF:
                return True
            i += 4
            continue
        if 0xDC00 <= unit <= 0xDFFF:
            return True
        i += 2
    return False


def serialize_number(value):
    """The ECMAScript ``Number::toString`` form RFC 8785 section 3.2.2.3 requires.

    Negative zero serialises as ``0``: ECMA-262 maps -0 to the string "0", which
    RFC 8785 erratum 7920 confirms, and vector ``jcs-0004`` pins.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        raise JcsError("AGSC-E601", "non-finite number")
    if number == 0:
        return "0"
    text = repr(number)
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    if "e" in text or "E" in text:
        mantissa, _, exponent_text = text.replace("E", "e").partition("e")
        exponent = int(exponent_text)
    else:
        mantissa, exponent = text, 0
    integer_part, _, fraction_part = mantissa.partition(".")
    combined = integer_part + fraction_part
    leading = len(combined) - len(combined.lstrip("0"))
    digits = combined.strip("0")
    point = len(integer_part) + exponent - leading
    length = len(digits)
    if length <= point <= 21:
        out = digits + "0" * (point - length)
    elif 0 < point <= 21:
        out = digits[:point] + "." + digits[point:]
    elif -6 < point <= 0:
        out = "0." + "0" * (-point) + digits
    else:
        power = point - 1
        sign = "+" if power >= 0 else "-"
        head = digits[0] if length == 1 else digits[0] + "." + digits[1:]
        out = head + "e" + sign + str(abs(power))
    return ("-" + out) if negative else out


def serialize_string(text):
    """The RFC 8785 section 3.2.2.2 string form (ECMAScript ``JSON.stringify``)."""
    out = ['"']
    for character in text:
        short = _SHORT_ESCAPES.get(character)
        if short is not None:
            out.append(short)
        elif ord(character) < 0x20:
            out.append("\\u%04x" % ord(character))
        else:
            out.append(character)
    out.append('"')
    return "".join(out)


def _canonicalize(value, normalise_names):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return serialize_number(value)
    if isinstance(value, str):
        return serialize_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonicalize(item, normalise_names) for item in value) + "]"
    if isinstance(value, dict):
        pairs = []
        for key in value:
            if not isinstance(key, str):
                raise JcsError("AGSC-E601", "member name is not a string")
            pairs.append((nfc(key) if normalise_names else key, value[key]))
        pairs.sort(key=lambda pair: utf16_key(pair[0]))
        body = ",".join(
            serialize_string(name) + ":" + _canonicalize(member, normalise_names)
            for name, member in pairs
        )
        return "{" + body + "}"
    raise JcsError("AGSC-E601", "value of type %s is not JSON" % type(value).__name__)


def canonicalize(value):
    """RFC 8785 with the AGSC-04-21 NFC-before-sort rule.  No trailing LF."""
    assert_ijson(value)
    return _canonicalize(value, True)


def canonicalize_raw(value):
    """RFC 8785 member order without the NFC pass.

    This is the form the discovery-file checker compares the served bytes
    against, so that it reports exactly what the Node tool reports.
    """
    return _canonicalize(value, False)


def assert_ijson(value):
    """Raise ``JcsError`` when the value is outside I-JSON (RFC 7493, AGSC-04-04)."""
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise JcsError("AGSC-E601", "integer outside the I-JSON range")
        return
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise JcsError("AGSC-E601", "non-finite number")
        if value.is_integer() and abs(value) > MAX_SAFE_INTEGER:
            raise JcsError("AGSC-E601", "integer outside the I-JSON range")
        return
    if isinstance(value, str):
        if has_lone_surrogate(value):
            raise JcsError("AGSC-E601", "lone surrogate in string")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            assert_ijson(item)
        return
    if isinstance(value, dict):
        seen = set()
        for key in value:
            if not isinstance(key, str):
                raise JcsError("AGSC-E601", "member name is not a string")
            name = nfc(key)
            if name in seen:
                raise JcsError("AGSC-E601", "duplicate member name %s" % name)
            seen.add(name)
            assert_ijson(value[key])
        return
    raise JcsError("AGSC-E601", "value of type %s is not JSON" % type(value).__name__)


def is_ijson(value):
    """True when the value is admissible I-JSON (the Level-0 duty of AGSC-04-04)."""
    try:
        assert_ijson(value)
    except JcsError:
        return False
    return True


class IJsonError(ValueError):
    """The strict reader refused the text."""


_WHITESPACE = " \t\n\r"
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
_HEX = "0123456789abcdefABCDEF"


def parse_ijson(text):
    """Read I-JSON strictly: no duplicate member name, no lone surrogate, no BOM.

    Member order is the document's, because a Python dict keeps insertion
    order, and several rules of AGSC-06-08 are about order.
    """
    state = {"i": 0}

    def fail(message):
        raise IJsonError(message)

    def skip_whitespace():
        while state["i"] < len(text) and text[state["i"]] in _WHITESPACE:
            state["i"] += 1

    def read_string():
        units = []
        state["i"] += 1
        while True:
            if state["i"] >= len(text):
                fail("unterminated string")
            character = text[state["i"]]
            state["i"] += 1
            if character == '"':
                break
            if character == "\\":
                if state["i"] >= len(text):
                    fail("unterminated string")
                escape = text[state["i"]]
                state["i"] += 1
                if escape == "u":
                    digits = text[state["i"]:state["i"] + 4]
                    if len(digits) != 4 or any(d not in _HEX for d in digits):
                        fail("bad \\u escape")
                    units.append(int(digits, 16))
                    state["i"] += 4
                elif escape in _ESCAPES:
                    units.append(ord(_ESCAPES[escape]))
                else:
                    fail("bad escape")
            elif character < " ":
                fail("control character in string")
            else:
                encoded = character.encode("utf-16-be", "surrogatepass")
                for offset in range(0, len(encoded), 2):
                    units.append((encoded[offset] << 8) | encoded[offset + 1])
        out = []
        index = 0
        while index < len(units):
            unit = units[index]
            if 0xD800 <= unit <= 0xDBFF:
                following = units[index + 1] if index + 1 < len(units) else None
                if following is None or not 0xDC00 <= following <= 0xDFFF:
                    fail("lone surrogate")
                out.append(chr(0x10000 + ((unit - 0xD800) << 10) + (following - 0xDC00)))
                index += 2
                continue
            if 0xDC00 <= unit <= 0xDFFF:
                fail("lone surrogate")
            out.append(chr(unit))
            index += 1
        return "".join(out)

    def read_number():
        start = state["i"]
        if state["i"] < len(text) and text[state["i"]] == "-":
            state["i"] += 1
        if state["i"] >= len(text) or text[state["i"]] not in "0123456789":
            fail("value expected")
        if text[state["i"]] == "0":
            state["i"] += 1
        else:
            while state["i"] < len(text) and text[state["i"]].isdigit():
                state["i"] += 1
        integral = True
        if state["i"] < len(text) and text[state["i"]] == ".":
            state["i"] += 1
            if state["i"] >= len(text) or not text[state["i"]].isdigit():
                fail("value expected")
            while state["i"] < len(text) and text[state["i"]].isdigit():
                state["i"] += 1
            integral = False
        if state["i"] < len(text) and text[state["i"]] in "eE":
            state["i"] += 1
            if state["i"] < len(text) and text[state["i"]] in "+-":
                state["i"] += 1
            if state["i"] >= len(text) or not text[state["i"]].isdigit():
                fail("value expected")
            while state["i"] < len(text) and text[state["i"]].isdigit():
                state["i"] += 1
            integral = False
        raw = text[start:state["i"]]
        return int(raw) if integral else float(raw)

    def read_value():
        skip_whitespace()
        if state["i"] >= len(text):
            fail("value expected")
        character = text[state["i"]]
        if character == "{":
            state["i"] += 1
            out = {}
            skip_whitespace()
            if state["i"] < len(text) and text[state["i"]] == "}":
                state["i"] += 1
                return out
            while True:
                skip_whitespace()
                if state["i"] >= len(text) or text[state["i"]] != '"':
                    fail("member name expected")
                name = read_string()
                if name in out:
                    fail('duplicate member name "%s"' % name)
                skip_whitespace()
                if state["i"] >= len(text) or text[state["i"]] != ":":
                    fail('":" expected')
                state["i"] += 1
                out[name] = read_value()
                skip_whitespace()
                if state["i"] < len(text) and text[state["i"]] == ",":
                    state["i"] += 1
                    continue
                if state["i"] < len(text) and text[state["i"]] == "}":
                    state["i"] += 1
                    break
                fail('"," or "}" expected')
            return out
        if character == "[":
            state["i"] += 1
            out = []
            skip_whitespace()
            if state["i"] < len(text) and text[state["i"]] == "]":
                state["i"] += 1
                return out
            while True:
                out.append(read_value())
                skip_whitespace()
                if state["i"] < len(text) and text[state["i"]] == ",":
                    state["i"] += 1
                    continue
                if state["i"] < len(text) and text[state["i"]] == "]":
                    state["i"] += 1
                    break
                fail('"," or "]" expected')
            return out
        if character == '"':
            return read_string()
        for literal, value in (("true", True), ("false", False), ("null", None)):
            if text.startswith(literal, state["i"]):
                state["i"] += len(literal)
                return value
        return read_number()

    if text[:1] == "﻿":
        fail("byte order mark")
    value = read_value()
    skip_whitespace()
    if state["i"] != len(text):
        fail("trailing characters")
    return value
