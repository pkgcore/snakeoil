"""default chksum implementation- sha1, sha256, rmd160, and md5"""

import hashlib
import os
import queue
import threading
from functools import partial
from multiprocessing import cpu_count
from sys import intern

from ..data_source import base as base_data_source
from ..fileutils import mmap_or_open_for_read

blocksize = 2 ** 17

sha1_size = 40
md5_size = 32
rmd160_size = 40
sha256_size = 64
sha512_size = 128
sha3_256_size = 64
sha3_512_size = 128
blake2b_size = 128
blake2s_size = 64


def chf_thread(queue, callback):
    qget = queue.get
    data = qget()
    while data is not None:
        callback(data)
        data = qget()


def chksum_loop_over_file(filename, chfs, parallelize=True, can_mmap=True):
    chfs = [chf() for chf in chfs]
    loop_over_file(
        filename, [chf.update for chf in chfs],
        parallelize=parallelize, can_mmap=can_mmap)
    return [int(chf.hexdigest(), 16) for chf in chfs]


def loop_over_file(handle, callbacks, parallelize=True, can_mmap=True):
    m = None
    close_f = True
    if isinstance(handle, str):
        if can_mmap:
            m, f = mmap_or_open_for_read(handle)
        else:
            f = open(handle, "rb")
    elif isinstance(handle, base_data_source):
        f = handle.bytes_fileobj()
    else:
        f = handle
        close_f = False
        if getattr(handle, 'encoding', None):
            # wanker.  bypass the encoding, go straight to the raw source.
            f = f.buffer
        # reset; we do it for compat, but it also avoids unpleasant issues from
        # the encoding bypass during py3k
        f.seek(0, 0)

    parallelize = parallelize and len(callbacks) > 1 and cpu_count() > 1
    threads, queues = [], []

    try:
        if parallelize:
            queues = [queue.Queue(8) for _ in callbacks]

            threads = [threading.Thread(target=chf_thread, args=(queue, functor))
                       for queue, functor in zip(queues, callbacks)]

            for thread in threads:
                thread.start()

            callbacks = [queue.put for queue in queues]

        if m is not None:
            for callback in callbacks:
                callback(m)
        elif hasattr(f, 'getvalue'):
            data = f.getvalue()
            if not isinstance(data, bytes):
                data = data.encode()

            for callback in callbacks:
                callback(data)
        else:
            data = f.read(blocksize)
            while data:
                for callback in callbacks:
                    callback(data)
                data = f.read(blocksize)

    finally:
        if parallelize:
            for functor in callbacks:
                functor(None)
            for thread in threads:
                thread.join()

        if m is not None:
            m.close()
        elif f is not None and close_f:
            f.close()


class Chksummer:

    def __init__(self, chf_type, obj, str_size, can_mmap=True):
        self.obj = obj
        self.chf_type = chf_type
        self.str_size = str_size
        self.can_mmap = can_mmap

    def new(self):
        return self.obj

    def long2str(self, val):
        return ("%x" % val).rjust(self.str_size, '0')

    @staticmethod
    def str2long(val):
        return int(val, 16)

    def __call__(self, filename):
        return chksum_loop_over_file(
            filename, [self.obj], can_mmap=self.can_mmap)[0]

    def __str__(self):
        return "%s chksummer" % self.chf_type


chksum_types = {}

# Always available according to docs.python.org:
# md5(), sha1(), sha224(), sha256(), sha384(), and sha512().
for hashlibname, chksumname, size in [
        ('md5', 'md5', md5_size),
        ('sha1', 'sha1', sha1_size),
        ('sha256', 'sha256', sha256_size),
        ('sha512', 'sha512', sha512_size),
    ]:
    chksum_types[chksumname] = Chksummer(
        chksumname, getattr(hashlib, hashlibname), size)

# May or may not be available depending on openssl. List
# determined through trial and error.
for hashlibname, chksumname, size in [
        ('ripemd160', 'rmd160', rmd160_size),
        ('sha3_256', 'sha3_256', sha3_256_size),
        ('sha3_512', 'sha3_512', sha3_512_size),
        ('blake2b', 'blake2b', blake2b_size),
        ('blake2s', 'blake2s', blake2s_size),
    ]:
    try:
        hashlib.new(hashlibname)
    except ValueError:
        pass
    else:
        chksum_types[chksumname] = Chksummer(
            chksumname, partial(hashlib.new, hashlibname), size)
del hashlibname, chksumname


class SizeUpdater:

    def __init__(self):
        self.count = 0

    def update(self, data):
        self.count += len(data)

    def hexdigest(self):
        return "%x" % self.count


class SizeChksummer(Chksummer):
    """Size based chksum handler.

    yes, aware that size isn't much of a chksum. ;)
    """

    def __init__(self):
        super().__init__(
            chf_type='size', obj=SizeUpdater, str_size=1000000000)

    @staticmethod
    def long2str(val):
        return str(val)

    @staticmethod
    def str2long(val):
        return int(val)

    def __call__(self, file_obj):
        if isinstance(file_obj, base_data_source):
            if file_obj.path is not None:
                file_obj = file_obj.path
            else:
                file_obj = file_obj.text_fileobj()
        if isinstance(file_obj, str):
            try:
                st_size = os.lstat(file_obj).st_size
            except OSError:
                return -1
            return st_size
        # seek to the end.
        file_obj.seek(0, 2)
        return int(file_obj.tell())


chksum_types["size"] = SizeChksummer()
chksum_types = {intern(k): v for k, v in chksum_types.items()}
