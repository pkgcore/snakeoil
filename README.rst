|pypi| |test| |coverage|

========
snakeoil
========

snakeoil is a python library that implements optimized versions of common
python functionality. Some classes and functions have cpython equivalents,
but they all have native python implementations too.

Installing
==========

Installing latest pypi release::

    pip install snakeoil

Installing from git::

    pip install https://github.com/pkgcore/snakeoil/archive/master.tar.gz

Installing from a tarball::

    python setup.py install

Tests
=====

A standalone test runner is integrated in setup.py; to run, just execute::

    python setup.py test

Using tox for all supported python versions::

    tox

Using tox for a specific python version::

    tox -e py36

Contact
=======

For support and development inquiries join `#pkgcore`_ on Freenode.

For bugs and feature requests please create an issue on Github_.


.. _#pkgcore: https://webchat.freenode.net?channels=%23pkgcore&uio=d4
.. _Github: https://github.com/pkgcore/snakeoil/issues

.. |pypi| image:: https://img.shields.io/pypi/v/snakeoil.svg
    :target: https://pypi.python.org/pypi/snakeoil
.. |test| image:: https://github.com/pkgcore/snakeoil/workflows/Run%20tests/badge.svg
    :target: https://github.com/pkgcore/snakeoil/actions?query=workflow%3A%22Run+tests%22
.. |coverage| image:: https://codecov.io/gh/pkgcore/snakeoil/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/pkgcore/snakeoil
