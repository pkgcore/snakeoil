# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD 3 clause

import argparse
from unittest import SkipTest, TestCase

try:
    # py3
    from importlib import reload
except ImportError:
    # py2
    pass


class TestCli(TestCase):

    def test_add_argument(self):
        # force using an unpatched version of argparse
        reload(argparse)

        parser = argparse.ArgumentParser()
        parser.add_argument('--foo', action='store_true')
        # add_argument() shouldn't support docs kwargs
        # if it does, then likely it is patched already and we can't
        # test properly
        try:
            parser.add_argument(
                '-b', '--blah', action='store_true', docs='Blah blah blah')
        except TypeError:
            pass
        else:
            raise SkipTest('argparse seems patched already')

        # monkeypatch add_argument() from argparse to allow docs kwargs
        from snakeoil import cli
        # force argparse to be patched
        reload(cli)
        action = parser.add_argument(
            '-b', '--blah', action='store_true', docs='Blah blah blah')

        # docs attrs are discarded by default
        self.assertIsNone(getattr(action, 'docs', None))

        # they're only enabled if the _generate_docs flag is set
        cli._generate_docs = True
        action = parser.add_argument(
            '-c', '--cat', action='store_true', docs='cat cat cat')
        self.assertEqual(getattr(action, 'docs', None), 'cat cat cat')
