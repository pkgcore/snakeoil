# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

import os
import sys
from snakeoil.demandload import demandload
demandload(globals(),
    'subprocess',
)

def _get_linux_proc_count():
    try:
        return os.sysconf('SC_NPROCESSORS_ONLN')
    except (ValueError, OSError, AttributeError):
        try:
            return len([x for x in open("/proc/cpuinfo") if x.split(":", 1)[0].strip() == "processor"])
        except EnvironmentError:
            return None

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
    return val


