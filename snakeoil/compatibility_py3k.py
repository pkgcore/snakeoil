# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

import sys
def raise_from(new_exception, exc_info=None):
    if exc_info is None:
        exc_info = sys.exc_info()
    raise new_exception from exc_info[1]
