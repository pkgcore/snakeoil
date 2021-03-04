import errno
import os
import socket
import sys

import pytest

from snakeoil.decorators import namespace, splitexec, coroutine


class TestSplitExecDecorator:

    def setup_method(self, method):
        self.pid = os.getpid()

    @splitexec
    def test_separate_func_process(self):
        # code inside the decorated func is run in a different process
        assert self.pid != os.getpid()


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='supported on Linux only')
class TestNamespaceDecorator:

    @pytest.mark.skipif(not os.path.exists('/proc/self/ns/user'),
                        reason='user namespace support required')
    def test_user_namespace(self):
        @namespace(user=True)
        def do_test():
            assert os.getuid() == 0

        try:
            do_test()
        except PermissionError:
            pytest.skip('No permission to use user namespace')

    @pytest.mark.skipif(not (os.path.exists('/proc/self/ns/user') and os.path.exists('/proc/self/ns/uts')),
                        reason='user and uts namespace support required')
    def test_uts_namespace(self):
        @namespace(user=True, uts=True, hostname='host')
        def do_test():
            ns_hostname, _, ns_domainname = socket.getfqdn().partition('.')
            assert ns_hostname == 'host'
            assert ns_domainname == ''

        try:
            do_test()
        except PermissionError:
            pytest.skip('No permission to use user and uts namespace')


class TestCoroutineDecorator:

    def test_coroutine(self):
        @coroutine
        def count():
            i = 0
            while True:
                val = (yield i)
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
