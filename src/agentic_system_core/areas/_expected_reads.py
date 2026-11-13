"""A guard against a vacuous pass (AGSC-09-02, AGSC-09-06).

The twin of the engine's ``tests/conformance/areas/_expected-reads.js``.  A handler
that never reads a member of ``expected`` has asserted nothing about it, and a pass
it returns says nothing about that member.  The guard runs a handler over a copy of
the case whose ``expected`` records every top-level member the handler reads, and
turns a pass into a fail when a member was never read, or when the case states no
member at all.  A fail or a not-run is returned unchanged, so the guard can only make
a result stricter.

A member counts as read as it does in the engine: by name (``expected["x"]``,
``expected.get("x")`` or a presence test ``"x" in expected``, which the engine's
``expected.x !== undefined`` is), or by listing the members.
"""


class _Recording(dict):
    """``expected`` that notes the name of every member read."""

    def __init__(self, members):
        super().__init__(members)
        self.read = set()

    def __getitem__(self, key):
        self.read.add(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.read.add(key)
        return super().get(key, default)

    def __contains__(self, key):
        self.read.add(key)
        return super().__contains__(key)

    def _listed(self):
        self.read.update(super().keys())

    def __iter__(self):
        self._listed()
        return super().__iter__()

    def keys(self):
        self._listed()
        return super().keys()

    def items(self):
        self._listed()
        return super().items()

    def values(self):
        self._listed()
        return super().values()


def guarded(handler):
    """``handler``, with a pass that left a member of ``expected`` unread turned into a
    fail that names the members."""
    def run(vector):
        expected = vector.get("expected")
        if not isinstance(expected, dict):
            return handler(vector)
        tracked = _Recording(expected)
        result = handler(dict(vector, expected=tracked))
        if not result or result.get("status") != "pass":
            return result
        unread = [key for key in expected if key not in tracked.read]
        if expected and not unread:
            return result
        if not expected:
            detail = "%s: the case states no expected member, so a pass would assert nothing" \
                % vector.get("id")
        else:
            detail = "%s: no branch of the handler reads %s" % (
                vector.get("id"), ", ".join('"%s"' % key for key in unread))
        return {"status": "fail", "detail": detail}
    return run
