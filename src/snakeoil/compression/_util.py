__all__ = ("compress_data", "decompress_data")

import errno
import os
import subprocess


def _drive_process(args, mode, data):
    p = subprocess.Popen(args,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, close_fds=True)
    try:
        stdout, stderr = p.communicate(data)
        if p.returncode != 0:
            raise ValueError(
                "%s returned %i exitcode from '%s', stderr=%r" %
                (mode, p.returncode, ' '.join(args), stderr))
        return stdout
    finally:
        if p is not None and p.returncode is None:
            p.kill()


def compress_data(binary, data, compresslevel=9, extra_args=()):
    args = [binary, '-%ic' % compresslevel]
    args.extend(extra_args)
    return _drive_process(args, 'compression', data)


def decompress_data(binary, data, extra_args=()):
    args = [binary, '-dc']
    args.extend(extra_args)
    return _drive_process(args, 'decompression', data)


class _process_handle:

    def __init__(self, handle, args, is_read=False):
        self.mode = 'wb'
        if is_read:
            self.mode = 'rb'

        self.args = tuple(args)
        self.is_read = is_read
        self._open_handle(handle)

    def _open_handle(self, handle):
        self._allow_reopen = None
        close = False
        if isinstance(handle, str):
            if self.is_read:
                self._allow_reopen = handle
            handle = open(handle, mode=self.mode)
            close = True
        elif not isinstance(handle, int):
            if not hasattr(handle, 'fileno'):
                raise TypeError(
                    "handle %r isn't a string, integer, and lacks a fileno "
                    "method" % (handle,))
            handle = handle.fileno()

        try:
            self._setup_process(handle)
        finally:
            if close:
                handle.close()

    def _setup_process(self, handle):
        self.position = 0
        stderr = open(os.devnull, 'wb')
        kwds = dict(stderr=stderr)
        if self.is_read:
            kwds['stdin'] = handle
            kwds['stdout'] = subprocess.PIPE
        else:
            kwds['stdout'] = handle
            kwds['stdin'] = subprocess.PIPE

        try:
            self._process = subprocess.Popen(
                self.args, close_fds=True, **kwds)
        finally:
            stderr.close()

        if self.is_read:
            self.handle = self._process.stdout
        else:
            self.handle = self._process.stdin

    def read(self, amount=None):
        if amount is None:
            data = self.handle.read()
        else:
            data = self.handle.read(amount)

        self.position += len(data)
        return data

    def write(self, data):
        self.position += len(data)
        self.handle.write(data)

    def tell(self):
        return self.position

    def seek(self, position=0):
        fwd_seek = position - self.position
        if fwd_seek < 0:
            if self._allow_reopen is None:
                raise TypeError(
                    "instance %s can't do negative seeks: asked for %i, "
                    "was at %i" % (self, position, self.position))
            self._terminate()
            self._open_handle(self._allow_reopen)
            return self.seek(position)
        elif fwd_seek > 0:
            if self.is_read:
                self._read_seek(fwd_seek)
            else:
                self._write_seek(fwd_seek)
        return self.position

    def _read_seek(self, offset, seek_size=(64 * 1024)):
        val = min(offset, seek_size)
        while val:
            self.read(val)
            offset -= val
            val = min(offset, seek_size)

    def _write_seek(self, offset, seek_size=64 * 1024):
        val = min(offset, seek_size)
        # allocate up front a null block so we can avoid
        # reallocating it continually; via this usage, we
        # only slice once the val is less than seek_size;
        # iow, two allocations worst case.
        null_block = '\0' * seek_size
        while val:
            self.write(null_block[:val])
            offset -= val
            val = min(offset, seek_size)

    def _terminate(self):
        try:
            self._process.terminate()
        except EnvironmentError as e:
            # allow no such process only.
            if e.errno != errno.ESRCH:
                raise

    def close(self):
        if self._process.returncode is not None:
            if self._process.returncode != 0:
                raise Exception("%s invocation had non zero exit: %i" %
                                (self.args, self._process.returncode))
            return

        self.handle.close()
        if self.is_read:
            self._terminate()
        else:
            self._process.wait()

    def __del__(self):
        self.close()


def compress_handle(binary_path, handle, compresslevel=9, extra_args=()):
    args = [binary_path, '-%ic' % compresslevel]
    args.extend(extra_args)
    return _process_handle(handle, args, False)


def decompress_handle(binary_path, handle, extra_args=()):
    args = [binary_path, '-dc']
    args.extend(extra_args)
    return _process_handle(handle, args, True)
