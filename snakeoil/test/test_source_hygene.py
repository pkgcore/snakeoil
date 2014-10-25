# Copyright: 2010-2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

from snakeoil.test import TestCase, mixins

class Test_modules(mixins.PythonNamespaceWalker, TestCase):

    target_namespace = 'snakeoil'

    def test__all__accuracy(self):
        failures = []
        for module in self.walk_namespace(self.target_namespace):
            for target in getattr(module, '__all__', ()):
                if not hasattr(module, target):
                    failures.append((module, target))
        if failures:
            self.fail("nonexistent __all__ targets spotted: %s" % (failures,))
