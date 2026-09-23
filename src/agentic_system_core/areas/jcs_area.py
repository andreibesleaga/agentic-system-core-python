"""Area ``jcs`` — AGSC-04-05 and AGSC-04-21.

Vectors jcs-0001 to jcs-0005: the canonical bytes, the UTF-16 member-name order,
the astral member order, negative zero and NFC before sorting.  Every
expectation follows from the vector's own input, so a consumer can run this area
with nothing but this package.
"""

import re

from ..jcs import canonicalize
from ._assert import checks, shown

_MEMBER = re.compile(r'"((?:[^"\\]|\\.)*)":')


def member_order(text):
    """The member names of a canonical document, in the order they appear."""
    return [json_unescape(one) for one in _MEMBER.findall(text)]


def json_unescape(raw):
    import json
    return json.loads('"%s"' % raw)


def run(vector):
    expected = vector["expected"]
    got = canonicalize(vector["input"]["value"])
    items = [("output", got == expected.get("output"), shown(got))]
    if isinstance(expected.get("order"), list):
        order = member_order(got)
        items.append(("order", order == expected["order"], shown(order)))
    if isinstance(expected.get("wrong_if_sorted_before_nfc"), str):
        items.append(("nfc-before-sort",
                      got != expected["wrong_if_sorted_before_nfc"],
                      "sorted before NFC"))
    if isinstance(expected.get("wrong_order_if_sorted_by_code_point"), list):
        order = member_order(got)
        items.append(("not-code-point-order",
                      order != expected["wrong_order_if_sorted_by_code_point"],
                      "member names were sorted by code point, not UTF-16 code units"))
    return checks(items)
