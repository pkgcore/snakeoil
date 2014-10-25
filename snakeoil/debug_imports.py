#!/usr/bin/python
# Copyright: 2007 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
script used for debugging imports required for a script

use at your own peril, unmaintained.  Roughly, it'll intercept
all imports and return a break down of how much time was taken
per import cumulative.
"""

from __future__ import print_function
import __builtin__

class intercept_import(object):

    def __init__(self, callback):
        self.callback = callback
        self.stack = []
        self.seen = set()

    def __call__(self, *args):
        if args[0] not in self.seen:
            self.disable()
            self.callback(self.stack, args)
            self.enable()
        self.stack.append(args[0])
        self.seen.add(args[0])
        try:
            return self.orig_import(*args)
        finally:
            self.stack.pop()

    def enable(self):
        cur_import = __builtin__.__import__
        if isinstance(cur_import, intercept_import):
            raise RuntimeError("an intercept is already active")
        self.orig_import = cur_import
        __builtin__.__import__ = self

    def disable(self):
        if __builtin__.__import__ != self:
            raise RuntimeError(
                "either not active, or a different intercept is in use")
        __builtin__.__import__ = self.orig_import
        del self.orig_import


if __name__ == "__main__":
    import __main__
    orig = dict(__main__.__dict__.iteritems())
    del orig["intercept_import"]
    del orig["__builtin__"]
    del orig["__main__"]

    import sys, imp

    usage = "debug_imports.py [-o output_file_path || -i] scriptfile [arg] ..."
    if not sys.argv[1:]:
        print("Usage: %s" % usage)
        sys.exit(2)

    # yes, at first thought, this should use getopt or optparse.
    # problem is, folks may want to spot that import, thus we can't.

    import traceback, pdb

    args = sys.argv[1:]
    if args[0] == '-o':
        if not len(args) > 2:
            print("Usage: %s" % usage)
            sys.exit(2)
        f = open(args[1], 'w')
        def callback(modules, key, val):
            f.write("adding %s\n" % key)
            traceback.print_stack(file=f)
        args = args[2:]
    elif args[0] == '-i':
        def callback(args):
            pdb.set_trace()
        args = args[1:]
    else:
        import time
        def callback(stack, args):
            if stack:
                print("in: %s" % ', '.join(stack))
            if len(args) == 4 and args[3] is not None:
                print("from %s import %s" % (args[0], ', '.join(args[3])))
            else:
                print("import %s " % args[0])
            print(time.time())
            #traceback.print_stack(file=sys.stdout)
            print()


    path = args[0]

    sys.argv = args[:]
    i = intercept_import(callback)
    i.enable()
    print("starting\n", time.time(), "\n")
    try:
        with open(args[0]) as f:
            imp.load_module("__main__", f, args[0], ("", "r", imp.PY_SOURCE))
    finally:
        i.disable()
        print("\nfinished\n", time.time(), "\n")
    sys.exit(0)
