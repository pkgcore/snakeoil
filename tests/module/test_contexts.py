import errno
import os
import random
import socket
import sys

import pytest

from snakeoil.contexts import chdir, syspath, SplitExec, Namespace


def test_chdir(tmpdir):
    orig_cwd = os.getcwd()

    with chdir(str(tmpdir)):
        assert orig_cwd != os.getcwd()

    assert orig_cwd == os.getcwd()


def test_syspath(tmpdir):
    orig_syspath = tuple(sys.path)

    # by default the path gets inserted as the first element
    with syspath(tmpdir):
        assert orig_syspath != tuple(sys.path)
        assert tmpdir == sys.path[0]

    assert orig_syspath == tuple(sys.path)

    # insert path in a different position
    with syspath(tmpdir, position=1):
        assert orig_syspath != tuple(sys.path)
        assert tmpdir != sys.path[0]
        assert tmpdir == sys.path[1]

    # conditional insert and nested context managers
    with syspath(tmpdir, condition=(tmpdir not in sys.path)):
        mangled_syspath = tuple(sys.path)
        assert orig_syspath != mangled_syspath
        assert tmpdir == sys.path[0]
        # dir isn't added again due to condition
        with syspath(tmpdir, condition=(tmpdir not in sys.path)):
            assert mangled_syspath == tuple(sys.path)


class TestSplitExec:

    def test_context_process(self):
        # code inside the with statement is run in a separate process
        pid = os.getpid()
        with SplitExec() as c:
            pass
        assert c.childpid is not None
        assert pid != c.childpid

    def test_context_exit_status(self):
        # exit status of the child process is available as a context attr
        with SplitExec() as c:
            pass
        assert c.exit_status == 0

        exit_status = random.randint(1, 255)
        with SplitExec() as c:
            sys.exit(exit_status)
        assert c.exit_status == exit_status

    def test_context_locals(self):
        # code inside the with statement returns modified, pickleable locals
        # via 'locals' attr of the context manager
        a = 1
        with SplitExec() as c:
            assert a == 1
            a = 2
            assert a == 2
            b = 3
        # changes to locals aren't propagated back
        assert a == 1
        assert 'b' not in locals()
        # but they're accessible via the 'locals' attr
        expected = {'a': 2, 'b': 3}
        for k, v in expected.items():
            assert c.locals[k] == v

        # make sure unpickleables don't cause issues
        with SplitExec() as c:
            func = lambda x: x
            import sys
            a = 4
        assert c.locals == {'a': 4}

    def test_context_exceptions(self):
        # exceptions in the child process are sent back to the parent and re-raised
        with pytest.raises(IOError) as e:
            with SplitExec() as c:
                raise IOError(errno.EBUSY, 'random error')
        assert e.value.errno == errno.EBUSY

    def test_child_setup_raises_exception(self):
        class ChildSetupException(SplitExec):
            def _child_setup(self):
                raise IOError(errno.EBUSY, 'random error')

        with pytest.raises(IOError) as e:
            with ChildSetupException() as c:
                pass
        assert e.value.errno == errno.EBUSY


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='supported on Linux only')
class TestNamespace:

    @pytest.mark.skipif(not os.path.exists('/proc/self/ns/user'),
                        reason='user namespace support required')
    def test_user_namespace(self):
        try:
            with Namespace(user=True) as ns:
                assert os.getuid() == 0
        except PermissionError:
            pytest.skip('No permission to use user namespace')

    @pytest.mark.skipif(not (os.path.exists('/proc/self/ns/user') and os.path.exists('/proc/self/ns/uts')),
                        reason='user and uts namespace support required')
    def test_uts_namespace(self):
        try:
            with Namespace(user=True, uts=True, hostname='host') as ns:
                ns_hostname, _, ns_domainname = socket.getfqdn().partition('.')
                assert ns_hostname == 'host'
                assert ns_domainname == ''
        except PermissionError:
            pytest.skip('No permission to use user and uts namespace')
