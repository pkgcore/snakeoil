# Copyright: 2015 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

import argparse

# Enable flag to pull extended docs keyword args into arguments during doc
# generation, when disabled the keyword is silently discarded.
_generate_docs = False


orig_add_argument = argparse._ActionsContainer.add_argument
def add_argument(self, *args, **kwargs):
    """Enable docs keyword args support for arguments.

    This is used to add extended, rST-formatted docs to man pages without
    affecting the regular help output for scripts.
    """
    docs = kwargs.pop('docs', None)
    action = orig_add_argument(self, *args, **kwargs)
    if docs is not None and _generate_docs:
        action.docs = docs
    return action
argparse._ActionsContainer.add_argument = add_argument
