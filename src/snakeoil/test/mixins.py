import errno
import os
import stat
import sys

from snakeoil._internals import deprecated
from snakeoil.compatibility import IGNORED_EXCEPTIONS


@deprecated(
    "Use snakeoil.python_namespaces.submodules_of, or derive from snakeoil.code_quality.NamespaceWalker for tests",
    removal_in=(0, 12, 0),
)
class PythonNamespaceWalker:
    ignore_all_import_failures = False

    valid_inits = frozenset(f"__init__.{x}" for x in ("py", "pyc", "pyo", "so"))

    # This is for py3.2/PEP3149; dso's now have the interp + major/minor embedded
    # in the name.
    # TODO: update this for pypy's naming
    abi_target = "cpython-%i%i" % tuple(sys.version_info[:2])

    module_blacklist = frozenset(
        {
            "snakeoil.cli.arghparse",
        }
    )

    def _default_module_blacklister(self, target):
        return target in self.module_blacklist or target.startswith("snakeoil.dist")

    def walk_namespace(self, namespace, **kwds):
        location = os.path.abspath(
            os.path.dirname(self.poor_mans_load(namespace).__file__)
        )
        return self.get_modules(self.recurse(location), namespace=namespace, **kwds)

    def get_modules(
        self, feed, namespace=None, blacklist_func=None, ignore_failed_imports=None
    ):
        if ignore_failed_imports is None:
            ignore_failed_imports = self.ignore_all_import_failures
        if namespace is None:

            def mangle(x):  # pyright: ignore[reportRedeclaration]
                return x
        else:
            orig_namespace = namespace

            def mangle(x):
                return f"{orig_namespace}.{x}"

        if blacklist_func is None:
            blacklist_func = self._default_module_blacklister
        for mod_name in feed:
            try:
                if mod_name is None:
                    if namespace is None:
                        continue
                else:
                    namespace = mangle(mod_name)
                if blacklist_func(namespace):
                    continue
                yield self.poor_mans_load(namespace)
            except ImportError:
                if not ignore_failed_imports:
                    raise

    def recurse(self, location, valid_namespace=True):
        if os.path.dirname(location) == "__pycache__":
            # Shouldn't be possible, but make sure we avoid this if it manages
            # to occur.
            return
        dirents = os.listdir(location)
        if not self.valid_inits.intersection(dirents):
            if valid_namespace:
                return
        else:
            yield None

        stats: list[tuple[str, int]] = []
        for x in dirents:
            try:
                stats.append((x, os.stat(os.path.join(location, x)).st_mode))
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise
                # file disappeared under our feet... lock file from
                # trial can cause this.  ignore.
                import logging

                logging.debug(
                    "file %r disappeared under our feet, ignoring",
                    os.path.join(location, x),
                )

        seen = set(["__init__"])
        for x, st in stats:
            if not (x.startswith(".") or x.endswith("~")) and stat.S_ISREG(st):
                if x.endswith((".py", ".pyc", ".pyo", ".so")):
                    y = x.rsplit(".", 1)[0]
                    # Ensure we're not looking at a >=py3k .so which injects
                    # the version name in...
                    if y not in seen:
                        if "." in y and x.endswith(".so"):
                            y, abi = x.rsplit(".", 1)
                            if abi != self.abi_target:
                                continue
                        seen.add(y)
                        yield y

        for x, st in stats:
            if stat.S_ISDIR(st):
                for y in self.recurse(os.path.join(location, x)):
                    if y is None:
                        yield x
                    else:
                        yield f"{x}.{y}"

    @staticmethod
    def poor_mans_load(namespace, existence_check=False):
        try:
            obj = __import__(namespace)
            if existence_check:
                return True
        except:
            if existence_check:
                return False
            raise
        for chunk in namespace.split(".")[1:]:
            try:
                obj = getattr(obj, chunk)
            except IGNORED_EXCEPTIONS:
                raise
            except AttributeError:
                raise AssertionError(f"failed importing target {namespace}")
            except Exception as e:
                raise AssertionError(f"failed importing target {namespace}; error {e}")
        return obj
