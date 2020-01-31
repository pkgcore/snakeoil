import errno
from importlib import reload
import os
from unittest import mock

import pytest

from snakeoil import __version__
from snakeoil import version


class TestVersion:

    def setup_method(self, method):
        # reset the cached version in the module
        reload(version)

    def test_get_version_release(self):
        pass

    def test_get_version_unknown(self):
        with pytest.raises(ValueError):
            version.get_version('snakeoilfoo', __file__)

    def test_get_version_api(self):
        v = version.get_version('snakeoil', __file__, '9.9.9')
        assert v.startswith('snakeoil 9.9.9')

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

            result = version.get_version('snakeoil', __file__, __version__)
            expected = 'snakeoil %s-g%s -- %s' % (__version__, verinfo['rev'][:7], verinfo['date'])
            assert result == expected

    def test_get_version_git_release(self):
        verinfo={
            'rev': 'ab38751890efa8be96b7f95938d6b868b769bab6',
            'date': 'Thu Sep 21 15:57:38 2017 -0400',
            'tag': '2.3.4',
        }

        # fake snakeoil._verinfo module object
        class Verinfo:
            version_info=verinfo

        with mock.patch('snakeoil.version.import_module') as import_module:
            import_module.return_value = Verinfo()
            result = version.get_version('snakeoil', __file__, verinfo['tag'])
            expected = 'snakeoil %s -- released %s' % (verinfo['tag'], verinfo['date'])
            assert result == expected

    def test_get_version_no_git_version(self):
        with mock.patch('snakeoil.version.import_module') as import_module, \
                mock.patch('snakeoil.version.get_git_version') as get_git_version:
            import_module.side_effect = ImportError
            get_git_version.return_value = None
            result = version.get_version('snakeoil', 'nonexistent', __version__)
            expected = '%s %s -- extended version info unavailable' % ('snakeoil', __version__)
            assert result == expected

    def test_get_version_caching(self):
        # retrieved version info is cached in a module attr
        v = version.get_version('snakeoil', __file__)
        assert v.startswith('%s %s' % ('snakeoil', __version__))

        # re-running get_version returns the cached attr instead of reprocessing
        with mock.patch('snakeoil.version.import_module') as import_module:
            v = version.get_version('snakeoil', __file__)
        assert not import_module.called


class TestGitVersion:

    def test_get_git_version_not_available(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            run_git.side_effect = EnvironmentError(errno.ENOENT, 'git not found')
            assert version.get_git_version('nonexistent') is None

    def test_get_git_version_error(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            run_git.return_value = (b'foo', 1)
            assert version.get_git_version('nonexistent') is None

    def test_get_git_version_non_repo(self, tmpdir):
        assert version.get_git_version(str(tmpdir)) is None

    def test_get_git_version_exc(self):
        with pytest.raises(OSError):
            with mock.patch('snakeoil.version._run_git') as run_git:
                run_git.side_effect = OSError(errno.EIO, 'Input/output error')
                version.get_git_version('nonexistent')

    def test_get_git_version_good_dev(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            # dev version
            run_git.return_value = (
                b'1ff76b021d208f7df38ac524537b6419404f1c64\nMon Sep 25 13:50:24 2017 -0400', 0)
            result = version.get_git_version('nonexistent')
            expected = {
                'rev': '1ff76b021d208f7df38ac524537b6419404f1c64',
                'date': 'Mon Sep 25 13:50:24 2017 -0400',
                'tag': None,
                'commits': 2,
                }
            assert result == expected

    def test_get_git_version_good_tag(self):
        with mock.patch('snakeoil.version._run_git') as run_git, \
                mock.patch('snakeoil.version._get_git_tag') as get_git_tag:
            # tagged, release version
            run_git.return_value = (
                b'1ff76b021d208f7df38ac524537b6419404f1c64\nMon Sep 25 13:50:24 2017 -0400', 0)
            get_git_tag.return_value = '1.1.1'
            result = version.get_git_version('nonexistent')
            expected = {
                'rev': '1ff76b021d208f7df38ac524537b6419404f1c64',
                'date': 'Mon Sep 25 13:50:24 2017 -0400',
                'tag': '1.1.1',
                'commits': 2,
                }
            assert result == expected

    def test_get_git_tag_bad_output(self):
        with mock.patch('snakeoil.version._run_git') as run_git:
            # unknown git tag rev output
            run_git.return_value = (b'a', 1)
            assert version._get_git_tag('foo', 'bar') is None
            run_git.return_value = (b'a foo/v0.7.2', 0)
            assert version._get_git_tag('foo', 'bar') is None

            # expected output formats
            run_git.return_value = (b'ab38751890efa8be96b7f95938d6b868b769bab6 tags/v1.1.1^0', 0)
            assert version._get_git_tag('foo', 'bar') == '1.1.1'
            run_git.return_value = (b'ab38751890efa8be96b7f95938d6b868b769bab6 tags/v1.1.1', 0)
            assert version._get_git_tag('foo', 'bar') == '1.1.1'
            run_git.return_value = (b'ab38751890efa8be96b7f95938d6b868b769bab6 tags/1.1.1', 0)
            assert version._get_git_tag('foo', 'bar') == '1.1.1'
