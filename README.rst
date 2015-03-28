|pypi| |test| |coverage| |docs|

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

A standalone test runner is integrated in setup.py; to run, just execute::

    python setup.py test

In addition, a tox config is provided so snakeoil can be tested against all
versions of Python it currently supports. Just run **tox** in the root
directory of the repo or an unpacked tarball to run the testsuite.


Installing
==========

To build::

    tar jxf snakeoil-0.xx.tar.bz2
    cd snakeoil-0.xx
    python setup.py build

To install::

    cd snakeoil-0.xx
    python setup.py install


.. _`issue tracker`: https://github.com/pkgcore/snakeoil/issues

.. |pypi| image:: https://img.shields.io/pypi/v/snakeoil.svg
    :target: https://pypi.python.org/pypi/snakeoil
.. |test| image:: https://travis-ci.org/pkgcore/snakeoil.svg?branch=master
    :target: https://travis-ci.org/pkgcore/snakeoil
.. |coverage| image:: https://coveralls.io/repos/pkgcore/snakeoil/badge.png?branch=master
    :target: https://coveralls.io/r/pkgcore/snakeoil?branch=master
.. |docs| image:: https://readthedocs.org/projects/snakeoil/badge/?version=latest
    :target: https://readthedocs.org/projects/snakeoil/?badge=latest
    :alt: Documentation Status
