|pypi| |test| |coverage|

========
snakeoil
========

snakeoil is a python library that implements optimized versions of common
python functionality. Some classes and functions have cython equivalents,
but they all have native python implementations too.

Installing
==========

Installing latest pypi release::

    pip install snakeoil

Installing from git::

    pip install https://github.com/pkgcore/snakeoil/archive/master.tar.gz

Installing from a tarball::

    pip install .

Tests
=====

Normal pytest is used, just execute::

    pytest

Using tox for all supported python versions::

    tox

Using tox for a specific python version::

    tox -e py310

Contact
=======

For bugs and feature requests please create an issue on Github_.


.. _Github: https://github.com/pkgcore/snakeoil/issues

.. |pypi| image:: https://img.shields.io/pypi/v/snakeoil.svg
    :target: https://pypi.python.org/pypi/snakeoil
.. |test| image:: https://github.com/pkgcore/snakeoil/workflows/test/badge.svg
    :target: https://github.com/pkgcore/snakeoil/actions?query=workflow%3A%22test%22
.. |coverage| image:: https://codecov.io/gh/pkgcore/snakeoil/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/pkgcore/snakeoil
