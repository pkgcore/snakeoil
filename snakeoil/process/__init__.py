# Copyright: 2011-2012 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

import os
import sys
from snakeoil.demandload import demandload
demandload(globals(),
    'subprocess',
    'snakeoil.osutils:access',
    'snakeoil.fileutils:readlines_ascii',
)

def _parse_cpuinfo():
    data = readlines_ascii("/proc/cpuinfo", True, True, False)
    procs = []
    current = []
    for line in data:
        if not line:
            if current:
                procs.append(current)
                current = []
        else:
            current.append(line.split(":", 1))
    return [dict((k.strip(), v.strip()) for k,v in items)
        for items in procs]

def _get_linux_physical_proc_count():
    procs = _parse_cpuinfo()
    if not procs:
        return _get_linux_proc_count()
    core_count = {}
    for proc in procs:
        physical_id = proc.get('physical id')
        if physical_id is None:
            return _get_linux_proc_count()
        if physical_id in core_count:
            continue
        cores = proc.get('cpu cores')
        if cores is None:
            return _get_linux_proc_count()
        core_count[physical_id] = int(cores)

    return sum(core_count.itervalues())

def _get_linux_proc_count():
    try:
        return os.sysconf('SC_NPROCESSORS_ONLN')
    except (ValueError, OSError, AttributeError):
        procs = _parse_cpuinfo()
        if not procs:
            return None
        return len(procs)

def _get_bsd_proc_count():
    p = subprocess.Popen(["sysctl", "-n", "hw.cpu"],
        env={"PATH":"/sbin:/bin:/usr/sbin:/usr/bin"}, close_fds=True, shell=False,
        stdout=subprocess.PIPE, stdin=None, stderr=subprocess.STDOUT)
    p.communicate()
    if p.returncode == 0:
        try:
            return int(out.strip() for out in p.stdin.read())
        except ValueError:
            pass
    return None

def get_physical_proc_count(force=False):
    """return the number of non-HT cpu's identified

    :param force: force recalculating the value, else use the cached value
    :return: integer of the number of processors.  If it can't be discerned, 1 is returned
    """
    val = getattr(get_physical_proc_count, 'cached_result', None)
    if val is None or force:
        if 'linux' in sys.platform:
            val = _get_linux_physical_proc_count()
        else:
            val = get_proc_count()
        get_physical_proc_count.cached_value = val
    return val

def get_proc_count(force=False):
    """return the number of cpu's identified, HT or otherwise

    :param force: force recalculating the value, else use the cached value
    :return: integer of the number of processors.  If it can't be discerned, 1 is returned
    """
    val = getattr(get_proc_count, 'cached_result', None)
    if val is None or force:
        if 'linux' in sys.platform:
            val = _get_linux_proc_count()
        elif 'bsd' in sys.platform or 'darwin' in sys.platform:
            val = _get_bsd_proc_count()
        if not val:
            val = 1
        get_proc_count.cached_result = val
    return val


def find_binary(binary, paths=None):
    """look through the PATH environment, finding the binary to execute"""

    if os.path.isabs(binary):
        if not (os.path.isfile(binary) and access(binary, os.X_OK)):
            raise CommandNotFound(binary)
        return binary

    if paths is None:
        paths = os.environ.get("PATH", "").split(":")

    for path in paths:
        filename = "%s/%s" % (path, binary)
        if access(filename, os.X_OK) and os.path.isfile(filename):
            return filename

    raise CommandNotFound(binary)


class CommandNotFound(Exception):

    def __init__(self, command):
        Exception.__init__(self, "Failed to find binary %r" % (command,))
        self.command = command


def _native_closerange(from_fd, to_fd):
    for fd in xrange(from_fd, to_fd):
        try:
            os.close(fd)
        except EnvironmentError:
            pass

try:
    if os.uname()[0].lower() != 'linux':
        # the optimized closerange works for sure on linux/glibc; for others
        # whitelist expand this as needed.
        raise ImportError()
    from snakeoil._posix import closerange
    # monkey patch os.closerange with the saner version;
    # this makes subprocess.Popen calls less noisy, and slightly faster.
    # only do this if we can drop our optimized version in.
    os.closerange = closerange
except ImportError:
    closerange = getattr(os, 'closerange', _native_closerange)

