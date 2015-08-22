# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

"""Various command-line related support"""

import argparse

from snakeoil.klass import patch

# Enable flag to pull extended docs keyword args into arguments during doc
# generation, when disabled the keyword is silently discarded.
_generate_docs = False


@patch(argparse._ActionsContainer, 'add_argument')
def add_argument(argparse_add_argument, self, *args, **kwargs):
    """Enable docs keyword args support for arguments.

    This is used to add extended, rST-formatted docs to man pages (or other
    generated doc formats) without affecting the regular, summarized help
    output for scripts.

    To use, import this module where argparse is used to add command-line
    arguments so the 'docs' kwarg gets ignored during general use. During
    document generation, enable the global _generate_docs variable in order to
    add 'docs' attributes to action objects that specify them. The strings from
    those attributes can then be extracted and added to the correct locations
    in the generated docs, see snakeoil.dist.generate_man_rsts for an example.
    """
    docs = kwargs.pop('docs', None)
    action = argparse_add_argument(self, *args, **kwargs)
    if docs is not None and _generate_docs:
        action.docs = docs
    return action
