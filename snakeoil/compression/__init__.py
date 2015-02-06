# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

from importlib import import_module

from snakeoil import klass


class _transform_source(object):

    def __init__(self, name):
        self.name = name

    @klass.jit_attr
    def module(self):
        return import_module('snakeoil.compression._%s' % (self.name,))

    @klass.jit_attr
    def parallelizable(self):
        return bool(getattr(self.module, 'parallelizable', False))

    def compress_data(self, data, level, parallelize=False):
        parallelize = parallelize and self.module.parallelizable
        return self.module.compress_data(data, level, parallelize=parallelize)

    def decompress_data(self, data, parallelize=False):
        parallelize = parallelize and self.module.parallelizable
        return self.module.decompress_data(data, parallelize=parallelize)

    def compress_handle(self, handle, level, parallelize=False):
        parallelize = parallelize and self.module.parallelizable
        return self.module.compress_handle(handle, level, parallelize=parallelize)

    def decompress_handle(self, handle, parallelize=False):
        parallelize = parallelize and self.module.parallelizable
        return self.module.decompress_handle(handle, parallelize=parallelize)


_transforms = {name: _transform_source(name) for name in ('bzip2',)}

def compress_data(compressor_type, data, level=9, **kwds):
    return _transforms[compressor_type].compress_data(data, level, **kwds)

def decompress_data(compressor_type, data, **kwds):
    return _transforms[compressor_type].decompress_data(data, **kwds)

def compress_handle(compressor_type, handle, level=9, **kwds):
    return _transforms[compressor_type].compress_handle(handle, level, **kwds)

def decompress_handle(compressor_type, source, **kwds):
    return _transforms[compressor_type].decompress_handle(source, **kwds)
