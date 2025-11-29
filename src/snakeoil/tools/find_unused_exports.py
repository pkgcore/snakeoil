"If you're having to work on this, python -m ast <path-to-a-file> is your best friend"

__all__ = ("main",)


import argparse
import ast
import logging
import sys
from pathlib import Path
from textwrap import dedent
from typing import Self, cast

from snakeoil.python_namespaces import get_submodules_of

# Generally hard requirement- avoid relying on snakeoil here.  At somepoint this
# should be able to be pointed right back at snakeoil for finding components internally
# that are unused.

logger = logging.getLogger(__name__)


# This classes are effectively a tree that can be walked backwards as
# we recurse into the import pathways where they reference back down the pathways.
# It is cyclic as all hell.
class ModuleImport(ast.NodeVisitor, dict[str, "ModuleImport"]):
    __slots__ = ("root", "parent", "name", "accesses", "unscoped_access", "ctx_imports")

    def __init__(self, root: Self | None, parent: Self | None, name: str) -> None:
        if name == "pkgcore.vdb.repo_ops":
            import pdb

            pdb.set_trace()
        self.root = self if root is None else root  # oh yeah, cyclic baby.
        self.parent = self.root if parent is None else parent
        self.name = name
        self.accesses: set[str] = set()
        self.unscoped_access: set[str] = set()
        self.ctx_imports = dict[str, Self]()

    @property
    def qualname(self):
        l = []
        current = self
        while current is not self.root:
            l.append(current.name)
            current = current.parent
        return ".".join(reversed(l))

    def __missing__(self, name: str) -> "ModuleImport":
        assert "." not in name
        self[name] = obj = self.__class__(self.root, parent=self, name=name)
        return obj

    def resolve_import(self, name: str) -> "ModuleImport":
        parts = name.split(".")

        current = self if parts[0] == "" else self.root
        while parts and parts[0] == "":
            if current is self.root:
                raise Exception(
                    f"in {self.qualname}, an import tried to climb past root: {name}"
                )
            current = current.parent
            parts = parts[1:]
        for part in parts:
            current = current[part]
        return current

    def __str__(self) -> str:
        return f"{self.qualname}: access={self.accesses!r} unscoped={self.unscoped_access!r} known ctx={list(sorted(self.ctx_imports.keys()))!r}"

    def __repr__(self):
        return str(self)


class ImportCollector(ast.NodeVisitor):
    __slotting_intentionally_disabled__ = True

    def __init__(self, root: ModuleImport, name: str) -> None:
        self.root = root
        self.current = self.root.resolve_import(name)

    def visit_Import(self, node):
        for alias in node.names:
            # rework this to look for getattrs

            result = self.current.resolve_import(alias.name)
            result.unscoped_access.add(self.current.name)
            self.current.ctx_imports[alias.asname if alias.asname else alias.name] = (
                result
            )

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if node.module is None:
                continue  # not touching that with a 20ft pole.
            result = self.current.resolve_import(node.module)
            result.accesses.add(alias.name)
            self.current.ctx_imports[alias.asname if alias.asname else alias.name] = (
                result
            )

    def visit_Attribute(self, node):
        if not hasattr(node.value, "id"):
            return
        # this isn't confirming there isn't shadowing-
        # import os
        # def foon(os): ... # just got shadowed, 'os' in that ctx is not globals()['os']
        # it takes effort, and it's not worth it; this tool is already known loose.
        if (target := self.current.ctx_imports.get(node.value.id, None)) is not None:
            target.accesses.add(node.attr)


parser = argparse.ArgumentParser(
    __name__.rsplit(".", 1)[-1],
    description=dedent(
        """\
        Tool for finding potentially dead code

        This imports all modules of the source namespace, then scans the target
        namespaces actual imports to find identify if a member of the sources __all__ is
        actually used somewhere in the targets.  It specifically knows how to 'see' through
        snakeoil mechanisms to thunk an import- a lazy import.

        It is not authorative; code doing imports within a function it isn't written to 'see'.
        Consider this tooling as a way to get suggestions of what is dead code from the
        standpoint of nothing in the target namespaces holds a reference to the object, thus
        either they do dynamic imports or getattrs- which we can't see- during code execution-
        or it's not in use.
        """
    ),
)
parser.add_argument(
    "source",
    action="store",
    type=str,
    help="the python module to import and scan recursively, using __all__ to find things only used within that codebase.",
)
parser.add_argument(
    "targets", type=str, nargs="+", help="python namespaces to scan for usage."
)


def main(options, out, err) -> int:
    root = ModuleImport(None, None, "")
    for target in tuple(options.targets) + (options.source,):
        for mod in get_submodules_of(__import__(target), include_root=True):
            p = cast(str, mod.__file__)
            with Path(p).open() as f:
                tree = ast.parse(f.read(), str(p))
                ImportCollector(root, target).visit(tree)

    source_modules = list(get_submodules_of(__import__(options.source)))
    results = []
    for mod in source_modules:
        results.append(result := [mod.__name__])
        if (mod_alls := getattr(mod, "__all__", None)) is None:
            result.append(f"{mod.__name__} has no __all__.  Not analyzing")
            continue
        collected = root.resolve_import(mod.__name__)
        missing = list(sorted(set(mod_alls).difference(collected.accesses)))
        if not missing:
            continue
        result.append(f"all is {list(sorted(mod_alls))}")
        if collected.unscoped_access:
            result.append(
                f"unscoped access exists from {collected.unscoped_access!r}.  getattr() type isn't detectable current, results may be wrong"
            )

        result.append(f"possibly unused {missing}")

    first = ""
    for block in sorted(results, key=lambda l: l[0]):
        if len(block) == 1:
            continue
        out.write(f"{first}{block[0]}\n")
        first = "\n"
        for lines in block[1:]:
            out.write(f"  {lines}\n")

    return 0


if __name__ == "__main__":
    options = parser.parse_args()
    sys.exit(main(options, sys.stdout, sys.stderr))
