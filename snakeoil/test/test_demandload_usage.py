# Copyright: 2005-2009 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

import os, stat, errno

from snakeoil.test import TestCase, mixins
from snakeoil import compatibility

class TestDemandLoadTargets(mixins.PythonNamespaceWalker, TestCase):

    target_namespace = 'snakeoil'
    ignore_all_import_failures = False

    if not compatibility.is_py3k:
        module_blacklist = frozenset(['snakeoil.caching_2to3'])

    def test_demandload_targets(self):
        for x in self.walk_namespace(self.target_namespace,
            ignore_failed_imports=self.ignore_all_import_failures):
            self.check_space(x)

    def check_space(self, mod):
        for attr in dir(mod):
            try:
                obj = getattr(mod, attr)
                # force __getattribute__ to fire
                getattr(obj, "__class__", None)
            except ImportError, ie:
                # hit one.
                self.fail("failed 'touching' demandloaded %s.%s: error %s" %
                    (mod.__name__, attr, ie))
