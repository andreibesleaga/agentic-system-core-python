"""Where the suite looks for the engine checkout.

The equivalence and cross-check tests run the engine beside this repository, at
``../agentic-system-core``. A maintainer who keeps a second engine worktree (a
release branch, say) points the suite at it with the environment variable
``AGSC_ENGINE_DIR``; without it, nothing changes.
"""

import pathlib
import re

import conftest


def test_without_the_variable_the_engine_is_the_sibling_checkout():
    assert conftest.engine_dir({}) == conftest.NEIGHBOURS / "agentic-system-core"


def test_an_empty_variable_counts_as_unset():
    assert conftest.engine_dir({"AGSC_ENGINE_DIR": ""}) == conftest.NEIGHBOURS / "agentic-system-core"


def test_the_variable_names_another_engine_checkout(tmp_path):
    assert conftest.engine_dir({"AGSC_ENGINE_DIR": str(tmp_path)}) == tmp_path.resolve()


def test_a_relative_value_is_read_from_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert conftest.engine_dir({"AGSC_ENGINE_DIR": "engine"}) == (tmp_path / "engine").resolve()


def test_the_suite_uses_the_value_of_this_run():
    import os

    assert conftest.ENGINE == conftest.engine_dir(os.environ)
    assert isinstance(conftest.ENGINE, pathlib.Path)


#: A path to the sibling engine folder spelled out in a test, not read from ``ENGINE``.
_HARD_WIRED = re.compile(r"""(/\s*|,\s*)["']agentic-system-core["']\s*[,)/]?""")


def test_no_test_module_hard_wires_the_engine_path():
    # Fitness function: every test that reads the engine reads it from conftest.ENGINE, so
    # AGSC_ENGINE_DIR reaches it (docs/MAINTAINING.md, "the engine checkout").
    here = pathlib.Path(__file__).parent
    offenders = [path.name for path in sorted(here.glob("test_*.py"))
                 if path.name != pathlib.Path(__file__).name
                 and _HARD_WIRED.search(path.read_text(encoding="utf-8"))]
    assert offenders == []
