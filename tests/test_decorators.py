import contextlib
import os
import socket
import sys
from unittest import mock

import pytest

from snakeoil.decorators import coroutine, namespace, splitexec


@pytest.mark.skip("flaky test, needs rework")
class TestSplitExecDecorator:
    def setup_method(self, method):
        self.pid = os.getpid()

    @splitexec
    def test_separate_func_process(self):
        # code inside the decorated func is run in a different process
        assert self.pid != os.getpid()


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="supported on Linux only"
)
class TestNamespaceDecorator:
    @contextlib.contextmanager
    def capture_call(self):
        @contextlib.contextmanager
        def fake_namespace():
            yield

        with mock.patch("snakeoil.contexts.Namespace") as m:
            m.side_effect = lambda *a, **kw: fake_namespace()
            yield object(), m

    def test_user_namespace(self):
        with self.capture_call() as (unique, m):

            @namespace(user=True)
            def do_test():
                return unique

            # do_test()
            assert unique is do_test()
            m.assert_called_once_with(user=True)

    def test_uts_namespace(self):
        with self.capture_call() as (unique, m):

            @namespace(user=True, uts=True, hostname="host")
            def do_test():
                return unique

            assert unique is do_test()
            m.assert_called_once_with(user=True, uts=True, hostname="host")


class TestCoroutineDecorator:
    def test_coroutine(self):
        @coroutine
        def count():
            i = 0
            while True:
                val = yield i
                i = val if val is not None else i + 1

        cr = count()

        # argument required
        with pytest.raises(TypeError):
            cr.send()

        assert cr.send(-1) == -1
        assert next(cr) == 0
        assert next(cr) == 1
        assert cr.send(10) == 10
        assert next(cr) == 11
