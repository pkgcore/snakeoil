"""Various with-statement context utilities."""

import contextlib
import os
import subprocess
from contextlib import AbstractContextManager, contextmanager
from contextlib import chdir as _contextlib_chdir
from importlib import import_module

from snakeoil._internals import deprecated
from snakeoil.python_namespaces import protect_imports

from .cli.exceptions import UserException
from .sequences import predicate_split


class GitStash(AbstractContextManager):
    """Context manager for stashing untracked or modified/uncommitted files."""

    def __init__(self, path, pathspecs=None, staged=False):
        self.path = path
        self.pathspecs = ["--"] + pathspecs if pathspecs else []
        self._staged = ["--keep-index"] if staged else []
        self._stashed = False

    def __enter__(self):
        """Stash all untracked or modified files in working tree."""
        # check for untracked or modified/uncommitted files
        try:
            p = subprocess.run(
                ["git", "status", "--porcelain=1", "-u"] + self.pathspecs,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=self.path,
                encoding="utf8",
                check=True,
            )
        except subprocess.CalledProcessError:
            raise ValueError(f"not a git repo: {self.path}")

        # split file changes into unstaged vs staged
        unstaged, staged = predicate_split(lambda x: x[1] == " ", p.stdout.splitlines())

        # don't stash when no relevant changes exist
        if self._staged:
            if not unstaged:
                return
        elif not p.stdout:
            return

        # stash all existing untracked or modified/uncommitted files
        try:
            stash_cmd = ["git", "stash", "push", "-u", "-m", "pkgcheck scan --commits"]
            subprocess.run(
                stash_cmd + self._staged + self.pathspecs,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=self.path,
                check=True,
                encoding="utf8",
            )
        except subprocess.CalledProcessError as e:
            error = e.stderr.splitlines()[0]
            raise UserException(f"git failed stashing files: {error}")
        self._stashed = True

    def __exit__(self, _exc_type, _exc_value, _traceback):
        """Apply any previously stashed files back to the working tree."""
        if self._stashed:
            try:
                subprocess.run(
                    ["git", "stash", "pop"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    cwd=self.path,
                    check=True,
                    encoding="utf8",
                )
            except subprocess.CalledProcessError as e:
                error = e.stderr.splitlines()[0]
                raise UserException(f"git failed applying stash: {error}")


@deprecated(
    "Use contextlib.chdir instead",
    removal_in=(0, 12, 0),
)
def chdir(path: str) -> contextlib.chdir:
    return _contextlib_chdir(path)


@deprecated(
    "This is not threadsafe.  For runtime use `snakeoil.python_namespaces.import_module_from_path`.  *Strictly* for tests, use `protect_imports`."
)
@contextmanager
def syspath(path: str, condition: bool = True, position: int = 0):
    """Context manager that mangles ``sys.path`` and then reverts on exit.

    :param path: The directory path to add to ``sys.path``.
    :param condition: Optional boolean that decides whether ``sys.path`` is mangled
        or not, defaults to being enabled.
    :param position: Optional integer that is the place where the path is inserted
        in ``sys.path``, defaults to prepending.
    """
    with protect_imports() as (paths, _):
        if condition:
            paths.insert(position, path)
        yield


@contextmanager
def os_environ(*remove, **update):
    """Mangle the ``os.environ`` dictionary and revert on exit.

    :param remove: variables to remove
    :param update: variable -> value mapping to add or alter
    """
    env = os.environ
    update = update or {}
    remove = remove or []

    # variables being updated or removed
    changed = (set(update) | set(remove)) & set(env)
    # variables to restore on exit
    update_after = {k: env[k] for k in changed}
    # variables to remove on exit
    remove_after = frozenset(k for k in update if k not in env)

    try:
        env.update(update)
        for k in remove:
            env.pop(k, None)
        yield
    finally:
        env.update(update_after)
        for k in remove_after:
            env.pop(k)


# Ideas and code for the patch context manager have been borrowed from mock
# (https://github.com/testing-cabal/mock) governed by the BSD-2 license found
# below.
#
# Copyright (c) 2007-2013, Michael Foord & the mock team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


@contextmanager
def patch(target, new):
    """Simplified module monkey patching via context manager.

    :param target: Target class or object.
    :param new: Object or value to replace the target with.
    """

    def _import_module(target):
        components = target.split(".")
        import_path = components.pop(0)
        module = import_module(import_path)
        for comp in components:
            try:
                module = getattr(module, comp)
            except AttributeError:
                import_path += ".%s" % comp
                module = import_module(import_path)
        return module

    def _get_target(target):
        if isinstance(target, str):
            try:
                module, attr = target.rsplit(".", 1)
            except (TypeError, ValueError):
                raise TypeError(f"invalid target: {target!r}")
            module = _import_module(module)
            return module, attr
        else:
            try:
                obj, attr = target
            except (TypeError, ValueError):
                raise TypeError(f"invalid target: {target!r}")
            return obj, attr

    obj, attr = _get_target(target)
    orig_attr = getattr(obj, attr)
    setattr(obj, attr, new)

    try:
        yield
    finally:
        setattr(obj, attr, orig_attr)
