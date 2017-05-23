#!/usr/bin/env bash

set -ev

if [[ ${TRAVIS_PYTHON_VERSION} == "2.7" ]] && [[ -n ${TRAVIS_TAG} ]]; then
	python3 -m pip install --only-binary ':all:' cython
	python3 setup.py sdist
	pip install cibuildwheel
	cibuildwheel --output-dir dist
	pip install twine
	twine upload dist/*
fi

exit 0
