# Copyright: 2017 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

import errno
import os
import unittest

try:
    # py3.4 and up
    from importlib import reload
except ImportError:
    # py2
    pass

try:
    from unittest import mock
except ImportError:
    import mock

from snakeoil import __version__
from snakeoil import version


# fake _verinfo module object
class Verinfo(object):

    version_info={
        'rev': 'ab38751890efa8be96b7f95938d6b868b769bab6',
        'date': 'Thu Sep 21 15:57:38 2017 -0400',
        'tag': __version__,
    }


class TestVersion(unittest.TestCase):

    verinfo = Verinfo()

    def setUp(self):
        # reset the cached version in the module
        reload(version)

    def test_get_version_release(self):
        pass

    def test_get_version_unknown(self):
        with self.assertRaises(ValueError):
            version.get_version('snakeoilfoo', __file__)

    def test_get_version_api(self):
        v = version.get_version('snakeoil', __file__, '9.9.9')
        self.assertTrue(v.startswith('snakeoil 9.9.9'))

    def test_get_version_git_dev(self):
        try:
            import snakeoil._verinfo
        except ImportError:
            v = version.get_version('snakeoil', __file__)
            self.assertTrue(v.startswith('%s %s-g' % ('snakeoil', __version__)))

            # technically a nonexistent file will work too
            reload(version)
            v = version.get_version('snakeoil', 'nonexistent')
            self.assertTrue(v.startswith('%s %s-g' % ('snakeoil', __version__)))
        else:
            raise unittest.SkipTest('running on a release version')

    def test_get_version_git_mock_release(self):
        with mock.patch('snakeoil.version.import_module') as import_module:
            import_module.return_value = self.verinfo
            v = version.get_version('snakeoil', __file__, __version__)
            self.assertEqual(v, '%s %s, released %s' % (
                'snakeoil', __version__, self.verinfo.version_info['date']))

    def test_get_version_git_not_available(self):
        with mock.patch('snakeoil.version.import_module') as import_module:
            import_module.side_effect = ImportError
            with mock.patch('snakeoil.version._run_git') as run_git:
                run_git.side_effect = EnvironmentError(errno.ENOENT, 'git not found')
                v = version.get_version('snakeoil', __file__, __version__)
            self.assertEqual(v, '%s %s, extended version info unavailable' % (
                'snakeoil', __version__))

    def test_get_version_git_error(self):
        with mock.patch('snakeoil.version.import_module') as import_module:
            import_module.side_effect = ImportError
            with self.assertRaises(OSError):
                with mock.patch('snakeoil.version._run_git') as run_git:
                    run_git.side_effect = OSError(errno.EIO, 'Input/output error')
                    version.get_version('snakeoil', __file__, __version__)

    def test_get_git_tag_bad_output(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            # unknown git tag rev output
            run_git.return_value = (b'a', 1)
            self.assertEqual(version._get_git_tag('foo', 'bar'), None)
            run_git.return_value = (b'a foo/v0.7.2', 0)
            self.assertEqual(version._get_git_tag('foo', 'bar'), None)

            # expected output formats
            run_git.return_value = (b'ab38751890efa8be96b7f95938d6b868b769bab6 tags/v1.1.1', 0)
            self.assertEqual(version._get_git_tag('foo', 'bar'), '1.1.1')
            run_git.return_value = (b'ab38751890efa8be96b7f95938d6b868b769bab6 tags/1.1.1', 0)
            self.assertEqual(version._get_git_tag('foo', 'bar'), '1.1.1')

    def test_get_version_simple(self):
        with mock.patch('snakeoil.version.import_module') as import_module:
            import_module.side_effect = ImportError
            self.assertEqual(
                version.get_version('snakeoil', '/tmp', __version__),
                '%s %s, extended version info unavailable' % ('snakeoil', __version__))

    def test_get_version_caching(self):
        # retrieved version info is cached in a module attr
        v = version.get_version('snakeoil', __file__)
        self.assertTrue(v.startswith('%s %s' % ('snakeoil', __version__)))

        # re-running get_version returns the cached attr instead of reprocessing
        with mock.patch('snakeoil.version.import_module') as import_module:
            v = version.get_version('snakeoil', __file__)
        assert not import_module.called
