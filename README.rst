.. image:: https://travis-ci.org/pkgcore/snakeoil.svg?branch=master
    :target: https://travis-ci.org/pkgcore/snakeoil

.. image:: https://coveralls.io/repos/pkgcore/snakeoil/badge.png?branch=master
    :target: https://coveralls.io/r/pkgcore/snakeoil?branch=master


========
snakeoil
========

snakeoil is a python library that implements optimized versions of common
python functionality. Some classes and functions have cpython equivalents,
but they all have native python implementations too.


Contact
=======

Please create an issue in the `issue tracker`_.


Tests
=====

A standalone test runner is integrated in setup.py; to run, just execute
setup.py test
Aside from that, our runner of choice is twisteds trial; ran via-

trial snakeoil

if you're doing development, trial is significantly friendlier; the
standalone runner is designed to be used mainly for installations of
snakeoil, where all tests must pass, else installation is aborted.


Installing
==========

pretty simple-

tar jxf snakeoil-0.XX.tar.bz2
cd snakeoil-0.XX
python setup.py build

if after running tests,

cd snakeoil-0.xx
python setup.py test

finally, installing-

cd snakeoil-0.xx
python setup.py install


.. _`issue tracker`: https://github.com/pkgcore/snakeoil/issues
