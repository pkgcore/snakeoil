# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

from snakeoil import modules, klass

class _transform_source(object):

    def __init__(self, name):
        self.name = name

    @klass.jit_attr
    def module(self):
        return modules.load_module('snakeoil.compression._%s' % (self.name,))

    for attr in ('compress_data', 'decompress_data'):
        locals()[attr] = klass.alias_attr('module.%s' % (attr,))
    del attr

_transforms = dict((name, _transform_source(name))
    for name in ('bzip2',))

def compress_data(compressor_type, data, level=9):
    return _transforms[compressor_type].compress_data(data, level)

def decompress_data(compressor_type, data):
    return _transforms[compressor_type].decompress_data(data)
