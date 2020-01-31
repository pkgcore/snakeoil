import os
import tempfile

import pytest

from snakeoil import chksum, fileutils
from snakeoil.currying import post_curry
from snakeoil.data_source import data_source, local_source

data = "afsd123klawerponzzbnzsdf;h89y23746123;haas"
multi = 40000


def require_chf(func):
    def subfunc(self):
        if self.chf is None:
            pytest.skip(
                'no handler for %s, do you need to install PyCrypto or mhash?'
                % (self.chf_type,))
        func(self)
    return subfunc


class base:

    def get_chf(self):
        try:
            self.chf = chksum.get_handler(self.chf_type)
        except chksum.MissingChksumHandler:
            self.chf = None

    def setup_method(self, method):
        self.get_chf()
        fd, self.fn = tempfile.mkstemp()
        for i in range(multi):
            os.write(fd, data.encode())
        os.close(fd)

    def teardown_method(self, method):
        try:
            os.unlink(self.fn)
        except IOError:
            pass

    @require_chf
    def test_fp_check(self):
        assert self.chf(self.fn) == self.expected_long

    @require_chf
    def test_fileobj_check(self):
        with open(self.fn, "r") as f:
            assert self.chf(f) == self.expected_long

    @require_chf
    def test_data_source_check(self):
        assert self.chf(local_source(self.fn)) == self.expected_long
        assert self.chf(data_source(fileutils.readfile_ascii(self.fn))) == self.expected_long

class ChksumTest(base):

    @require_chf
    def test_str2long(self):
        assert self.chf.str2long(self.expected_str) == self.expected_long
        if self.chf_type == 'size':
            return
        for x in extra_chksums.get(self.chf_type, ()):
            assert self.chf.str2long(x) == int(x, 16)

    @require_chf
    def test_long2str(self):
        assert self.chf.long2str(self.expected_long) == self.expected_str
        if self.chf_type == 'size':
            return
        for x in extra_chksums.get(self.chf_type, ()):
            assert self.chf.long2str(int(x == 16)), x

checksums = {
    "rmd160": "b83ad488d624e7911f886420ab230f78f6368b9f",
    "sha1": "63cd8cce8a1773dffb400ee184be3ec7d89791f5",
    "md5": "d17ea153bc57ba9e07298c5378664369",
    "sha256": "68ae37b45e4a4a5df252db33c0cbf79baf5916b5ff6fc15e8159163b6dbe3bae",
    "sha512": "cdc2b749d28cd9c5fca45d3ca6b65661445decd992da93054fd6f4f3e4013ca8b44b0ba159d1cf1f58f9af2b9d267343b9e10f611494c0850fdcebe0379135c6",
    "sha3_256": "33e910cd302a2a210ccd9bc5331d61c164aa228a23af2ae97edc9eb60ddb01f9",
    "sha3_512": "820e3526c76ca2c41582439c50b395aef7560ae57c5d6273fe7dbaa01f4f1f121ddbb147cf42fc23e0a2823bf0bb4c47027cd35620141126d374c6782a512f95",
    "blake2b": "9f9bbd37d28994c871fffbc21358358e79c85c80fad70a0c0ce5998ff9ff04001f4984ec46e596bd4c482adc701cca44f70318c389dc6014c1bb5818d6991c7f",
    "blake2s": "805b836cb59b5144b2a738422b342a90fbdc0dd8e75321eb3022766ff333a7b1",
}
checksums.update((k, (int(v, 16), v)) for k, v in checksums.items())
checksums["size"] = (int(len(data) * multi), str(int(len(data) * multi)))

extra_chksums = {
    "md5":
        ["2dfd84279314a178d0fa842af3a40e25577e1bc"]
}

for k, v in checksums.items():
    extra_chksums.setdefault(k, []).extend((''.rjust(len(v[1]), '0'), '01'.rjust(len(v[1]), '0')))

# trick: create subclasses for each checksum with a useful class name.
for chf_type, expected in checksums.items():
    expectedsum = expected[0]
    expectedstr = expected[1]
    globals()['TestChksum' + chf_type.capitalize()] = type(
        'TestChksum' + chf_type.capitalize(),
        (ChksumTest,),
        dict(chf_type=chf_type, expected_long=expectedsum, expected_str=expectedstr))

# pylint: disable=undefined-loop-variable
del chf_type, expected


class TestGetChksums(base):

    chfs = [k for k in sorted(checksums) if k in ('md5', 'sha1')]
    expected_long = [checksums[k][0] for k in chfs]

    def get_chf(self):
        self.chf = post_curry(chksum.get_chksums, *self.chfs)
