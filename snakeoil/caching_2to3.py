#!/usr/bin/python3
# Copyright: 2009 Brian Harring <ferringb@gmail.com>
# License: PSF-2.2/GPL2/BSD

import lib2to3.main
import lib2to3.refactor
import os, hashlib

def md5_hash_data(data):
    chf = hashlib.md5()
    chf.update(data)
    return chf.hexdigest()

class caching_mixin(object):

    base_cls = None

    @property
    def cache_dir(self):
        return os.environ.get("PY2TO3_CACHEDIR", "cache")

    def get_cache_path(self, cache_key):
        return os.path.join(self.cache_dir, cache_key)

    def update_cache_from_file(self, cache_key, filename, encoding):
        cache_dir = self.cache_dir
        if not os.path.exists(cache_dir):
            os.mkdir(cache_dir)
            return None
        output = open(filename, 'rb').read().decode(encoding)
        open(os.path.join(cache_dir, cache_key), 'wb').write(output.encode(encoding))

    def check_cache(self, cache_key, encoding):
        cache_path = self.get_cache_path(cache_key)
        if os.path.isfile(cache_path):
            return open(cache_path, 'rb').read().decode(encoding)
        return None

    @staticmethod
    def compute_cache_key(input, encoding):
        return md5_hash_data(input.encode(encoding))

    def refactor_file(self, filename, write=False, doctests_only=False):
        if not write:
            return self.base_cls.refactor_file(self, filename, write=write,
                doctests_only=doctests_only)
        input, encoding = self._read_python_source(filename)
        cache_key = self.compute_cache_key(input, encoding)
        cache_data = self.check_cache(cache_key, encoding)
        if cache_data is None:
            self.base_cls.refactor_file(self, filename, write=write,
                doctests_only=doctests_only)
            self.update_cache_from_file(cache_key, filename, encoding)
        else:
            print("cache hit")
            self.processed_file(cache_data, filename, write=write,
                encoding=encoding, old_text=input)

class RefactoringTool(caching_mixin, lib2to3.refactor.RefactoringTool):

    base_cls = lib2to3.refactor.RefactoringTool


class MultiprocessRefactoringTool(caching_mixin, lib2to3.refactor.MultiprocessRefactoringTool):

    base_cls = lib2to3.refactor.MultiprocessRefactoringTool

class my_StdoutRefactoringTool(caching_mixin, lib2to3.main.StdoutRefactoringTool):

    base_cls = lib2to3.main.StdoutRefactoringTool

def StdoutRefactoringTool(*args):
    # stupid hacks...
    lib2to3.main.StdoutRefactoringTool = my_StdoutRefactoringTool.base_cls
    inst = my_StdoutRefactoringTool.base_cls(*args)
    inst.__class__ = my_StdoutRefactoringTool
    return inst

if __name__ == '__main__':
    lib2to3.main.StdoutRefactoringTool = StdoutRefactoringTool
    import sys
    sys.exit(lib2to3.main.main("lib2to3.fixes"))
