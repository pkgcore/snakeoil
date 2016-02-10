# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: GPL2/BSD 3 clause

import argparse
from unittest import TestCase

try:
    # py3.4 and up
    from importlib import reload
except ImportError:
    try:
        # py3.3
        from imp import reload
    except ImportError:
        # py2
        pass


class TestCli(TestCase):

    def test_add_argument(self):
        # force using an unpatched version of argparse
        reload(argparse)

        parser = argparse.ArgumentParser()
        parser.add_argument('--foo', action='store_true')
        # add_argument() doesn't support docs kwargs
        with self.assertRaises(TypeError):
            parser.add_argument(
                '-b', '--blah', action='store_true', docs='Blah blah blah')

        # monkeypatch add_argument() from argparse to allow docs kwargs
        # force argparse to be patched
        from snakeoil.cli import argparser
        reload(argparser)
        action = parser.add_argument(
            '-b', '--blah', action='store_true', docs='Blah blah blah')

        # docs attrs are discarded by default
        self.assertIsNone(getattr(action, 'docs', None))

        # they're only enabled if the _generate_docs flag is set
        argparser._generate_docs = True
        action = parser.add_argument(
            '-c', '--cat', action='store_true', docs='cat cat cat')
        self.assertEqual(getattr(action, 'docs', None), 'cat cat cat')
