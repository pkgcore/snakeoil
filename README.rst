|pypi| |test| |coverage| |docs|

========
snakeoil
========

snakeoil is a python library that implements optimized versions of common
python functionality. Some classes and functions have cpython equivalents,
but they all have native python implementations too.

Installing
==========

Installing latest pypi release in a virtualenv::

    pip install snakeoil

Installing from git in a virtualenv::

    pip install https://github.com/pkgcore/snakeoil/archive/master.tar.gz

Installing from a tarball or git repo::

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
.. _mock: https://pypi.python.org/pypi/mock

.. |pypi| image:: https://img.shields.io/pypi/v/snakeoil.svg
    :target: https://pypi.python.org/pypi/snakeoil
.. |test| image:: https://travis-ci.org/pkgcore/snakeoil.svg?branch=master
    :target: https://travis-ci.org/pkgcore/snakeoil
.. |coverage| image:: https://codecov.io/gh/pkgcore/snakeoil/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/pkgcore/snakeoil
.. |docs| image:: https://readthedocs.org/projects/snakeoil/badge/?version=latest
    :target: http://snakeoil.readthedocs.org/
    :alt: Documentation Status
