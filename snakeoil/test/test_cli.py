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


class TestArghparse(TestCase):

    def test_add_argument_docs(self):
        # force using an unpatched version of argparse
        reload(argparse)

        parser = argparse.ArgumentParser()
        parser.add_argument('--foo', action='store_true')

        # vanilla argparse doesn't support docs kwargs
        with self.assertRaises(TypeError):
            parser.add_argument(
                '-b', '--blah', action='store_true', docs='Blah blah blah')
        with self.assertRaises(TypeError):
            foo = parser.add_argument_group('fa', description='fa la la', docs='fa la la la')
        with self.assertRaises(TypeError):
            bar = parser.add_mutually_exclusive_group('fee', description='fi', docs='fo fum')

        # forcibly monkey-patch argparse to allow docs kwargs
        from snakeoil.cli import arghparse
        reload(arghparse)

        docs = 'blah blah'
        for enable_docs, expected_docs in ((False, None), (True, docs)):
            arghparse._generate_docs = enable_docs
            parser = argparse.ArgumentParser()
            action = parser.add_argument(
                '-b', '--blah', action='store_true', docs=docs)
            arg_group = parser.add_argument_group('fa', description='fa la la', docs=docs)
            mut_arg_group = parser.add_mutually_exclusive_group()
            mut_action = mut_arg_group.add_argument(
                '-f', '--fee', action='store_true', docs=docs)

            self.assertEqual(getattr(action, 'docs', None), expected_docs)
            self.assertEqual(getattr(arg_group, 'docs', None), expected_docs)
            self.assertEqual(getattr(mut_action, 'docs', None), expected_docs)
