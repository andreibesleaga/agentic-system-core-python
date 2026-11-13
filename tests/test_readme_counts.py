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
    # One bullet per reason, after the sentence that opens the list.
    opening = readme.index("reports as not run, each with its reason:")
    block = readme[opening:readme.index("\n\n", readme.index("\n- ", opening))]
    bullets = [line for line in block.splitlines() if line.startswith("- ")]
    assert len(bullets) == 3, bullets
    report, _ = vectors.run(str(VECTORS))
    named = []
    for bullet in bullets:
        count = re.match(r"- (\w+) ", bullet)
        assert count, bullet
        ids = named_ids(bullet)
        assert WORDS.index(count.group(1).lower()) == len(ids), bullet
        named += ids
    assert sorted(named) == sorted(report["vectors_not_run"])


def test_the_change_log_counts_the_vector_copies():
    """The change log's count of the vector files is the number of files copied."""
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    said = re.search(r"seven areas \((\d+) files;", log)
    assert said is not None
    assert int(said.group(1)) == sum(1 for one in pathlib.Path(VECTORS).rglob("*") if one.is_file())
