# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# License: GPL2


import os
import shutil
import tempfile

from snakeoil.test import TestCase
from snakeoil import compatibility

class TempDirMixin(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        # force it, since sticky bits spread.
        os.chmod(self.dir, 0700)

    def tearDown(self):
        # change permissions back or rmtree can't kill it
        for root, dirs, files in os.walk(self.dir):
            for directory in dirs:
                os.chmod(os.path.join(root, directory), 0777)
        shutil.rmtree(self.dir)

def tempdir_decorator(func):
    def f(self, *args, **kwargs):
        self.dir = tempfile.mkdtemp()
        try:
            os.chmod(self.dir, 0700)
            return func(self, *args, **kwargs)
        finally:
            for root, dirs, files in os.walk(self.dir):
                for directory in dirs:
                    os.chmod(os.path.join(root, directory), 0777)
            shutil.rmtree(self.dir)
    f.__name__ = func.__name__
    return f

mk_named_tempfile = tempfile.NamedTemporaryFile
if compatibility.is_py3k:
    import io
    def mk_named_tempfile(*args, **kwds):
        tmp_f = tempfile.NamedTemporaryFile(*args, **kwds)
        return io.TextIOWrapper(tmp_f)
