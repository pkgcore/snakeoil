# Copyright: 2017 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2
#
# TODO: Rework to use the project's git repo when tests are moved to project's
# root dir instead of mocking everything.

import errno
import os
import tempfile
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


class TestVersion(unittest.TestCase):

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
        with mock.patch('snakeoil.version.import_module') as import_module, \
                mock.patch('snakeoil.version.get_git_version') as get_git_version:
            import_module.side_effect = ImportError
            verinfo = {
                'rev': '1ff76b021d208f7df38ac524537b6419404f1c64',
                'date': 'Mon Sep 25 13:50:24 2017 -0400',
                'tag': None
            }
            get_git_version.return_value = verinfo

            self.assertEqual(
                version.get_version('snakeoil', __file__, __version__),
                'snakeoil %s-g%s, %s' % (__version__, verinfo['rev'][:7], verinfo['date']))

    def test_get_version_git_release(self):
        verinfo={
            'rev': 'ab38751890efa8be96b7f95938d6b868b769bab6',
            'date': 'Thu Sep 21 15:57:38 2017 -0400',
            'tag': '2.3.4',
        }

        # fake snakeoil._verinfo module object
        class Verinfo(object):
            version_info=verinfo

        with mock.patch('snakeoil.version.import_module') as import_module:
            import_module.return_value = Verinfo()
            self.assertEqual(
                version.get_version('snakeoil', __file__, verinfo['tag']),
                'snakeoil %s, released %s' % (verinfo['tag'], verinfo['date']))

    def test_get_version_no_git_version(self):
        with mock.patch('snakeoil.version.import_module') as import_module, \
                mock.patch('snakeoil.version.get_git_version') as get_git_version:
            import_module.side_effect = ImportError
            get_git_version.return_value = None
            self.assertEqual(
                version.get_version('snakeoil', 'nonexistent', __version__),
                '%s %s, extended version info unavailable' % ('snakeoil', __version__))

    def test_get_version_caching(self):
        # retrieved version info is cached in a module attr
        v = version.get_version('snakeoil', __file__)
        self.assertTrue(v.startswith('%s %s' % ('snakeoil', __version__)))

        # re-running get_version returns the cached attr instead of reprocessing
        with mock.patch('snakeoil.version.import_module') as import_module:
            v = version.get_version('snakeoil', __file__)
        assert not import_module.called


class TestGitVersion(unittest.TestCase):

    def test_get_git_version_not_available(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            run_git.side_effect = EnvironmentError(errno.ENOENT, 'git not found')
            self.assertEqual(version.get_git_version('nonexistent'), None)

    def test_get_git_version_error(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            run_git.return_value = (b'foo', 1)
            self.assertEqual(version.get_git_version('nonexistent'), None)

    def test_get_git_version_non_repo(self):
        # test our basic git cmd running
        # TODO: switch to TemporaryDirectory context manager when py3 only
        tempdir = tempfile.mkdtemp()
        self.assertEqual(version.get_git_version(tempdir), None)
        os.rmdir(tempdir)

    def test_get_git_version_exc(self):
        with self.assertRaises(OSError):
            with mock.patch('snakeoil.version._run_git') as run_git:
                run_git.side_effect = OSError(errno.EIO, 'Input/output error')
                version.get_git_version('nonexistent')

    def test_get_git_version_good_dev(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            # dev version
            run_git.return_value = (
                b'1ff76b021d208f7df38ac524537b6419404f1c64\nMon Sep 25 13:50:24 2017 -0400', 0)
            self.assertEqual(
                version.get_git_version('nonexistent'),
                {'rev': '1ff76b021d208f7df38ac524537b6419404f1c64',
                 'date': 'Mon Sep 25 13:50:24 2017 -0400',
                 'tag': None
                })

    def test_get_git_version_good_tag(self):
        with mock.patch('snakeoil.version._run_git') as run_git, \
                mock.patch('snakeoil.version._get_git_tag') as get_git_tag:
            # tagged, release version
            run_git.return_value = (
                b'1ff76b021d208f7df38ac524537b6419404f1c64\nMon Sep 25 13:50:24 2017 -0400', 0)
            get_git_tag.return_value = '1.1.1'
            self.assertEqual(
                version.get_git_version('nonexistent'),
                {'rev': '1ff76b021d208f7df38ac524537b6419404f1c64',
                 'date': 'Mon Sep 25 13:50:24 2017 -0400',
                 'tag': '1.1.1'
                })

    def test_get_git_tag_bad_output(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            # unknown git tag rev output
            run_git.return_value = (b'a', 1)
            self.assertEqual(version._get_git_tag('foo', 'bar'), None)
            run_git.return_value = (b'a foo/v0.7.2', 0)
            self.assertEqual(version._get_git_tag('foo', 'bar'), None)

            # expected output formats
            run_git.return_value = (b'ab38751890efa8be96b7f95938d6b868b769bab6 tags/v1.1.1^0', 0)
            self.assertEqual(version._get_git_tag('foo', 'bar'), '1.1.1')
            run_git.return_value = (b'ab38751890efa8be96b7f95938d6b868b769bab6 tags/v1.1.1', 0)
            self.assertEqual(version._get_git_tag('foo', 'bar'), '1.1.1')
            run_git.return_value = (b'ab38751890efa8be96b7f95938d6b868b769bab6 tags/1.1.1', 0)
            self.assertEqual(version._get_git_tag('foo', 'bar'), '1.1.1')
