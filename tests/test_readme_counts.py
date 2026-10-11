"""The README names the vectors this package reports as not run, and how many there are."""

import pathlib
import re

from agentic_system_core import vectors
from conftest import VECTORS

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen", "twenty"]


def named_ids(text):
    """Vector ids written as `a-0001` or as a range `a-0001` to `a-0004`."""
    ids = []
    for m in re.finditer(r"`([a-z]+)-(\d{4})`(?: to `\1-(\d{4})`)?", text):
        first = int(m.group(2))
        last = int(m.group(3)) if m.group(3) else first
        ids += [f"{m.group(1)}-{n:04d}" for n in range(first, last + 1)]
    return ids


def test_the_readme_lists_every_vector_not_run_and_counts_them():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    row = next(line for line in readme.splitlines() if line.startswith("| `build` |"))
    sentence = re.search(r"(\w+) vectors of these seven areas need a whole build[^(]*\(([^)]*)\)", row)
    assert sentence, "the build row does not say which vectors are not run"
    report, _ = vectors.run(str(VECTORS))
    expected = sorted(report["vectors_not_run"])
    assert sorted(named_ids(sentence.group(2))) == expected
    assert WORDS.index(sentence.group(1).lower()) == len(expected)
