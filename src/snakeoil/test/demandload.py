from . import mixins


class DemandLoadTargets(mixins.PythonNamespaceWalker):

    target_namespace = 'snakeoil'
    ignore_all_import_failures = False

    def setup_method(self, method):
        self._failures = []

    def teardown_method(self, method):
        msg = "\n".join(sorted("%s: error %s" % (target, e)
                               for target, e in self._failures))
        assert not self._failures, "bad demandload targets:\n%s" % (msg,)

    def test_demandload_targets(self):
        for x in self.walk_namespace(
                self.target_namespace,
                ignore_failed_imports=self.ignore_all_import_failures):
            self.check_space(x)

    def check_space(self, mod):
        for attr in dir(mod):
            try:
                obj = getattr(mod, attr)
                # force __getattribute__ to fire
                getattr(obj, "__class__", None)
            except ImportError as ie:
                # hit one.
                self._failures.append(("%s: target %s" % (mod.__name__, attr), ie))
