from snakeoil import currying
from snakeoil import dependant_methods as dm


def func(self, seq, data, val=True):
    seq.append(data)
    return val


class TestDependantMethods:

    @staticmethod
    def generate_instance(methods, dependencies):
        class Class(metaclass=dm.ForcedDepends):
            stage_depends = dict(dependencies)

            locals().update(list(methods.items()))

        return Class()

    def test_no_dependant_methods(self):
        assert self.generate_instance({}, {})

    def test_return_checking(self):
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x) for x in range(10)},
            {str(x): str(x - 1) for x in range(1, 10)})
        getattr(o, "9")()
        assert results == list(range(10))
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x, False) for x in range(10)},
            {str(x): str(x - 1) for x in range(1, 10)})
        getattr(o, "9")()
        assert results == [0]
        getattr(o, "9")()
        assert results == [0, 0]

    def test_stage_awareness(self):
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x) for x in range(10)},
            {str(x): str(x - 1) for x in range(1, 10)})
        getattr(o, "1")()
        assert results == [0, 1]
        getattr(o, "2")()
        assert results == [0, 1, 2]
        getattr(o, "2")()
        assert results == [0, 1, 2]
        o.__set_stage_state__(["0", "1"])
        l = []
        o.__stage_step_callback__ = l.append
        getattr(o, "2")()
        assert results == [0, 1, 2, 2]
        assert l == ["2"]

    def test_stage_depends(self):
        results = []
        methods = {str(x): currying.post_curry(func, results, x) for x in range(10)}
        deps = {str(x): str(x - 1) for x in range(1, 10)}
        deps["1"] = ["0", "a"]
        methods["a"] = currying.post_curry(func, results, "a")
        o = self.generate_instance(methods, deps)
        getattr(o, "1")()
        assert results == [0, "a", 1]
        getattr(o, "2")()
        assert results == [0, "a", 1, 2]

    def test_ignore_deps(self):
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x) for x in range(10)},
            {str(x): str(x - 1) for x in range(1, 10)})
        getattr(o, '2')(ignore_deps=True)
        assert [2] == results

    def test_no_deps(self):
        results = []
        o = self.generate_instance(
            {str(x): currying.post_curry(func, results, x) for x in range(10)},
            {})
        getattr(o, '2')()
        assert [2] == results
