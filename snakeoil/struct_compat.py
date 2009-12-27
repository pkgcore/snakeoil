# Copyright: 2009 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

from struct import *

class fake_struct(object):

    def __init__(self, format):
        self.format = format
        self.size = calcsize(self.format)

    def unpack(self, string):
        return unpack(self.format, string)

    def pack(self, *args):
        return pack(self.format, *args)

base_struct = locals().get('Struct', fake_struct)

class Struct(base_struct):

    def read(self, fd):
        return self.unpack(fd.read(self.size))

    def write(self, fd, *args):
        return fd.write(self.pack(*args))
