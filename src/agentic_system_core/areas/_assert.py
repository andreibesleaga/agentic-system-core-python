"""The one way an area handler reports its verdict."""

import json


def checks(items):
    """Turn a list of (name, ok, detail) into one pass or one fail with reasons."""
    failed = ["%s: %s" % (name, detail) for name, ok, detail in items if not ok]
    if failed:
        return {"status": "fail", "detail": "; ".join(failed)}
    return {"status": "pass", "detail": ""}


def shown(value):
    """A short, stable rendering of a value for a failure message."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
