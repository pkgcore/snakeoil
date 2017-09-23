# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

from snakeoil.test import TestCase
from snakeoil import dependant_methods as dm
from snakeoil import currying


def func(self, seq, data, val=True):
    seq.append(data)
    return val


class TestDependantMethods(TestCase):

    @staticmethod
    def generate_instance(methods, dependencies):
        class Class(object):
            __metaclass__ = dm.ForcedDepends
            stage_depends = dict(dependencies)

            locals().update(methods.iteritems())

        return Class()

    def test_no_dependant_methods(self):
        self.assertTrue(self.generate_instance({}, {}))

    def test_return_checking(self):
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x) for x in range(10)},
            {str(x): str(x - 1) for x in xrange(1, 10)})
        getattr(o, "9")()
        self.assertEqual(results, range(10))
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x, False) for x in range(10)},
            {str(x): str(x - 1) for x in xrange(1, 10)})
        getattr(o, "9")()
        self.assertEqual(results, [0])
        getattr(o, "9")()
        self.assertEqual(results, [0, 0])

    def test_stage_awareness(self):
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x) for x in range(10)},
            {str(x): str(x - 1) for x in xrange(1, 10)})
        getattr(o, "1")()
        self.assertEqual(results, [0, 1])
        getattr(o, "2")()
        self.assertEqual(results, [0, 1, 2])
        getattr(o, "2")()
        self.assertEqual(results, [0, 1, 2])
        o.__set_stage_state__(["0", "1"])
        l = []
        o.__stage_step_callback__ = l.append
        getattr(o, "2")()
        self.assertEqual(results, [0, 1, 2, 2])
        self.assertEqual(l, ["2"])

    def test_stage_depends(self):
        results = []
        methods = {str(x): currying.post_curry(func, results, x) for x in range(10)}
        deps = {str(x): str(x - 1) for x in xrange(1, 10)}
        deps["1"] = ["0", "a"]
        methods["a"] = currying.post_curry(func, results, "a")
        o = self.generate_instance(methods, deps)
        getattr(o, "1")()
        self.assertEqual(results, [0, "a", 1])
        getattr(o, "2")()
        self.assertEqual(results, [0, "a", 1, 2])

    def test_ignore_deps(self):
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x) for x in range(10)},
            {str(x): str(x - 1) for x in xrange(1, 10)})
        getattr(o, '2')(ignore_deps=True)
        self.assertEqual([2], results)

    def test_no_deps(self):
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x) for x in range(10)},
            {})
        getattr(o, '2')()
        self.assertEqual([2], results)
