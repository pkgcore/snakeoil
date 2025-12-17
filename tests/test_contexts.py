import os
import sys
from contextlib import chdir

from snakeoil._internals import deprecated
from snakeoil.contexts import syspath


@deprecated.suppress_deprecations()
def test_chdir(tmpdir):
    orig_cwd = os.getcwd()

    with chdir(str(tmpdir)):
        assert orig_cwd != os.getcwd()

    assert orig_cwd == os.getcwd()


@deprecated.suppress_deprecations()
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
