import errno
from unittest import mock

import pytest

from snakeoil.process import namespaces

# every helper that unshares; each is documented as a no-op when the namespace
# type isn't supported.  simple_unshare is driven per namespace so the arguments
# keep it away from the mount and net paths, which do more than unshare.
helpers = pytest.mark.parametrize(
    "func,kwargs",
    (
        pytest.param(namespaces.create_utsns, {}, id="create_utsns"),
        pytest.param(namespaces.create_netns, {}, id="create_netns"),
        pytest.param(namespaces.create_userns, {}, id="create_userns"),
        pytest.param(namespaces.create_pidns, {}, id="create_pidns"),
        pytest.param(
            namespaces.simple_unshare,
            dict(mount=False, uts=True, ipc=False),
            id="simple_unshare-uts",
        ),
        pytest.param(
            namespaces.simple_unshare,
            dict(mount=False, uts=False, ipc=True),
            id="simple_unshare-ipc",
        ),
        pytest.param(
            namespaces.simple_unshare,
            dict(mount=False, uts=False, ipc=False, user=True),
            id="simple_unshare-user",
        ),
        pytest.param(
            namespaces.simple_unshare,
            dict(mount=False, uts=False, ipc=False, pid=True),
            id="simple_unshare-pid",
        ),
    ),
)


@pytest.fixture
def unshare_fails():
    def failing(err):
        return mock.patch.object(
            namespaces, "unshare", side_effect=OSError(err, "mocked")
        )

    return failing


@helpers
def test_unsupported_namespace_is_skipped(func, kwargs, unshare_fails):
    with unshare_fails(errno.EINVAL):
        func(**kwargs)


@helpers
def test_failure_propagates(func, kwargs, unshare_fails):
    with unshare_fails(errno.EPERM), pytest.raises(OSError) as excinfo:
        func(**kwargs)
    assert errno.EPERM == excinfo.value.errno


@pytest.mark.parametrize("err", (errno.EINVAL, errno.EPERM))
def test_utsns_hostname_needs_the_namespace(err, unshare_fails):
    # without a UTS namespace of our own, setting the hostname would be setting
    # it for whatever namespace we're already in.
    with mock.patch.object(namespaces.socket, "sethostname") as sethostname:
        with unshare_fails(err):
            try:
                namespaces.create_utsns("wrong-host")
            except OSError:
                pass
        assert not sethostname.called
