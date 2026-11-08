"""Fitness functions for the package's shape, read from the source with ``ast``.

Two rules the README and docs/ARCHITECTURE.md state: the package imports nothing but
the standard library and itself (``dependencies = []``), and only ``cli.py`` starts a
process (it forwards the engine verbs to Node). A checker of a built tree reads files
another writer built; it never builds one itself.
"""

import ast
import importlib.util
import pathlib
import sys
import sysconfig

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "src" / "agentic_system_core"
MODULES = sorted(PACKAGE.rglob("*.py"))
_STDLIB = tuple(str(pathlib.Path(sysconfig.get_paths()[key]).resolve())
                for key in ("stdlib", "platstdlib"))


def _imports(path):
    """The top-level names a module imports absolutely (relative imports are the package)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _is_standard_library(name):
    if name in sys.builtin_module_names:
        return True
    spec = importlib.util.find_spec(name)
    if spec is None:
        return False
    if spec.origin in (None, "built-in", "frozen"):
        return True
    return str(pathlib.Path(spec.origin).resolve()).startswith(_STDLIB) \
        and "site-packages" not in spec.origin


def test_the_package_imports_only_the_standard_library_and_itself():
    outside = {}
    for path in MODULES:
        foreign = sorted(name for name in _imports(path)
                         if name != "agentic_system_core" and not _is_standard_library(name))
        if foreign:
            outside[str(path.relative_to(PACKAGE))] = foreign
    assert outside == {}


def test_a_third_party_name_would_be_caught():
    assert _is_standard_library("json") and _is_standard_library("sys")
    assert not _is_standard_library("pytest")
    assert not _is_standard_library("no_such_module_anywhere")


def test_only_the_command_line_starts_a_process():
    starters = sorted(str(path.relative_to(PACKAGE)) for path in MODULES
                      if _imports(path) & {"subprocess", "multiprocessing"})
    assert starters == ["cli.py"]
