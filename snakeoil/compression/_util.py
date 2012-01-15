# Copyright: 2006-2012 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

__all__ = ("compress_data", "decompress_data")

import subprocess

def _drive_process(args, mode, data):
    p = subprocess.Popen(args,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, close_fds=True)
    try:
        stdout, stderr = p.communicate(data)
        if p.returncode != 0:
            raise ValueError("%s returned %i exitcode from %s"
                ", stderr=%r" % (mode, p.returncode, binary, stderr))
        return stdout
    finally:
        if p is not None and p.returncode is None:
            p.kill()

def compress_data(binary, data, compress_level=9):
    return _drive_process([binary, '-%ic' % compress_level],
        'compression', data)

def decompress_data(binary, data):
    return _drive_process([binary, '-dc'],
        'decompression', data)
