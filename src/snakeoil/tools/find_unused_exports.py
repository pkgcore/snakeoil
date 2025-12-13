"If you're having to work on this, python -m ast <path-to-a-file> is your best friend"

__all__ = ("main",)


import argparse
import ast
import logging
import sys
from collections import defaultdict
from pathlib import Path
from textwrap import dedent
from typing import NamedTuple, Optional, Self, cast

from snakeoil.python_namespaces import get_submodules_of

# Generally hard requirement- avoid relying on snakeoil here.  At somepoint this
# should be able to be pointed right back at snakeoil for finding components internally
# that are unused.

logger = logging.getLogger(__name__)


class CtxAccess(NamedTuple):
    attr: str
    module: "ModuleImport"


# This classes are effectively a tree that can be walked backwards as
# we recurse into the import pathways where they reference back down the pathways.
# It is cyclic as all hell.
class ModuleImport(dict[str, "ModuleImport"]):
    def __init__(self, root: Self | None, parent: Self | None, name: str) -> None:
        self.root = self if root is None else root  # oh yeah, cyclic baby.
        self.parent = self.root if parent is None else parent
        self.name = name
        # this is recordings of other modules accessing us.
        self.accessed_by: dict[str, set["ModuleImport"]] = defaultdict(set)
        # This is a mapping of the local name to the target namespace
        self.ctx_imports = dict[str, CtxAccess]()
        self.unscoped_accessers: set[str] = set()
        self.requires_reprocessing = False
        self.alls = None

    def __hash__(self) -> int:  # type: ignore
        return hash(self.qualname)

    def __eq__(self, other):
        return self is other

    @property
    def qualname(self):
        l = []
        current = self
        while current is not self.root:
            l.append(current.name)
            current = current.parent
        return ".".join(reversed(l))

    def create(self, chunks: list[str]) -> "ModuleImport":
        assert len(chunks)
        name, chunks = chunks[0], chunks[1:]
        obj = self.setdefault(name, self.__class__(self.root, parent=self, name=name))
        if chunks:
            return obj.create(chunks)
        return obj

    def resolve_import(
        self,
        name: str,
        requester: Optional["ModuleImport"],
    ) -> tuple[list[str], "ModuleImport"]:
        parts = name.split(".")
        assert all(parts)
        current = self

        while parts:
            if requester is not None:
                current.accessed_by[parts[0]].add(requester)
            if parts[0] not in current:
                break
            current = current[parts[0]]
            parts = parts[1:]

        try:
            assert parts or self.root is not current
        except AssertionError as _e:
            # structured this way to make debugging easier
            raise

        return (parts, current)

    def __str__(self) -> str:
        return f"{self.qualname}: access={self.accessed_by!r} unscoped={self.unscoped_accessers!r} known ctx={list(sorted(self.ctx_imports.keys()))!r}"

    def __repr__(self):
        return str(self)


class ImportCollector(ast.NodeVisitor):
    __slotting_intentionally_disabled__ = True

    def __init__(
        self, root: ModuleImport, current: ModuleImport, name: str, path: Path
    ) -> None:
        self.root = root
        self.current = current
        self.path = path
        # from semantics are directory traversals, despite how they look.  __init__ is special.
        self.level_adjustment = 1 if path.name.startswith("__init__.") else 0
        self.requires_reprocessing = True

    def visit(self, node):
        # reset our status
        self.current.requires_reprocessing = False
        super().visit(node)

    def get_asname(self, alias) -> str:
        if alias.asname:
            return alias.asname
        return alias.name.split(
            ".",
        )[0]

    def update_must_reprocess(self, asname: str):
        assert "." not in asname, asname
        for must_reprocess in self.current.accessed_by.pop(asname, []):
            must_reprocess.requires_reprocessing = True

    def visit_Import(self, node):
        for alias in node.names:
            asname = self.get_asname(alias)
            self.update_must_reprocess(asname)

            attrs, result = self.root.resolve_import(alias.name, requester=self.current)

            if attrs:
                # failed to fully import.  Don't inject the result into ctx;
                # the traversal to get there will notify of us of the rebuild
                # if necessary.  It's possible we're importing through a module
                # that assembles an API via doing it's own internal imports.
                continue
            self.current.ctx_imports[asname] = CtxAccess(
                alias.name,
                result,
            )
            result.unscoped_accessers.add(self.current.qualname)

    def visit_ImportFrom(self, node):
        # just rewrite into absolute pathing
        base: list[str]
        if node.level:
            base = self.current.qualname.split(".")
            level = node.level - self.level_adjustment
            if level:
                base = base[:-level]
            if node.module:
                base.extend(node.module.split("."))
        else:
            base = node.module.split(".")
        for alias in node.names:
            asname = self.get_asname(alias)
            self.update_must_reprocess(asname)
            l = base[:]
            l.append(alias.name)

            attrs, result = self.root.resolve_import(
                ".".join(l), requester=self.current
            )
            if attrs:
                if len(attrs) == 1:
                    # `from module import some_func`
                    result.accessed_by[attrs[0]].add(self.current)
                # lacking that, we couldn't import it fully.
                continue

            self.current.ctx_imports[asname] = CtxAccess(
                alias.name,
                result,
            )


class AttributeCollector(ast.NodeVisitor):
    def __init__(self, root: ModuleImport, current: ModuleImport) -> None:
        self.root = root
        self.current = current

    def visit_Attribute(self, node):
        if not isinstance(node.ctx, ast.Load):
            return

        lookup = [node.attr]
        value = node.value
        try:
            while isinstance(value, ast.Name):
                if (last := getattr(value, "id", None)) is not None:
                    # terminus.  This node won't have attr.
                    lookup.append(last)
                    break
                lookup.append(value.attr)
                node = node.value

        except Exception as e:
            print(
                f"ast traversal bug in {self.current.qualname} for original {type(node)}={node} sub-value {type(value)}={value}"
            )
            import pdb

            pdb.set_trace()
            raise e

        lookup.reverse()

        # this isn't confirming there isn't shadowing-
        # import os
        # def foon(os): ... # just got shadowed, 'os' in that ctx is not globals()['os']
        # it takes effort, and it's not worth it; this tool is already known loose.

        if (target := self.current.ctx_imports.get(lookup[0], None)) is None:
            # it's an attribute, or an import we don't care about.
            return
        # build an absolute path, use resolve machinery to sort this.
        parts = target.module.qualname.split(".") + lookup[1:]
        parts, mod = self.root.resolve_import(".".join(parts), requester=self.current)
        assert mod is not self.root

        if parts:
            # attribute access into that module.
            mod.accessed_by[parts[0]].add(self.current)


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
parser.add_argument(
    "-v", action="store_true", default=False, dest="verbose", help="Increase verbosity"
)


def main(options, out, err) -> int:
    root = ModuleImport(None, None, "")

    source_modules: list[ModuleImport] = []
    ast_sources = {}
    # pre-initialize the module tree of what we care about.
    for target in tuple(options.targets) + (options.source,):
        for module in get_submodules_of(target, include_root=True):
            obj = root.create(module.__name__.split("."))
            obj.alls = getattr(module, "__all__", None)
            p = Path(cast(str, module.__file__))
            with p.open("r") as f:
                ast_sources[obj] = (p, ast.parse(f.read(), str(p)))
            if target == options.source:
                source_modules.append(obj)

    # collect and finalize imports, then run analysis based on attribute access.

    # Note: the import collection may need to run multiple times.  Consider:
    # klass.py:
    # __all__ = ('blah', 'foon')
    # from .other import blah, foon
    #
    # If some other module tries to travers klass.py before those from imports have been placed, the
    # other module will think it stopped at an attribute for 'blah'.  Which isn't correct.
    # They internally detect this conflict and mark a boolean to indicate if a reprocessing is needed.
    must_be_processed = list(ast_sources)
    for run in range(0, 10):
        for mod in must_be_processed:
            p, tree = ast_sources[mod]
            ImportCollector(root, mod, mod.qualname, p).visit(tree)

        if new_reprocess := [mod for mod in ast_sources if mod.requires_reprocessing]:
            if len(new_reprocess) == len(must_be_processed):
                raise Exception("cycle encountered")
            must_be_processed = new_reprocess
        else:
            break

    for mod, (p, tree) in ast_sources.items():
        AttributeCollector(root, mod).visit(tree)

    results = []
    for mod in source_modules:
        results.append(result := [mod.qualname])
        if mod.alls is None:
            result.append(f"{mod.qualname} has no __all__.  Not analyzing")
            continue
        if options.verbose:
            result.append("__all__ = (" + ", ".join(sorted(mod.alls)) + ")")

        missing = list(sorted(set(mod.alls).difference(mod.accessed_by)))
        if not missing:
            continue
        # result.append(f"all is {list(sorted(mod.alls))}")
        if mod.unscoped_accessers:
            result.append(
                f"unscoped access exists from {mod.unscoped_accessers!r}.  Results may be inaccurate"
            )

        result.append(f"possibly unused {missing}")

    first = ""
    for block in sorted(results, key=lambda l: l[0]):
        if len(block) == 1 and not options.verbose:
            continue
        out.write(f"{first}{block[0]}\n")
        first = "\n"
        if len(block) == 1:
            out.write("  __all__ is fully used\n")
            continue

        for lines in block[1:]:
            out.write(f"  {lines}\n")

    return 0


if __name__ == "__main__":
    options = parser.parse_args()
    sys.exit(main(options, sys.stdout, sys.stderr))
