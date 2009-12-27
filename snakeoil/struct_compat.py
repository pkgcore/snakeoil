# Copyright: 2009 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

#import struct
from struct import *

class fake_struct(object):

    def __init__(self, format):
        self.format = format
        self.size = struct.calcsize(self.format)

    def unpack(self, string):
        return struct.unpack(self.format, string)

    def pack(self, *args):
        return struct.pack(self.format, *args)

base_struct = locals().get('Struct', fake_struct)
#error = struct.error

class Struct(base_struct):

    def read(self, fd):
        return self.unpack(fd.read(self.size))

    def write(self, fd, *args):
        return fd.write(self.pack(*args))
