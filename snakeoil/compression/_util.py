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

def compress_data(binary, data, level=9, extra_args=()):
    args = [binary, '-%ic' % level]
    args.extend(extra_args)
    return _drive_process(args, 'compression', data)

def decompress_data(binary, data, extra_args=()):
    args = [binary, '-dc']
    args.extend(extra_args)
    return _drive_process(args, 'decompression', data)
