PYTHON ?= python

SPHINX_BUILD ?= sphinx-build
SPHINX_BUILD_SOURCE_DIR ?= doc
SPHINX_BUILD_BUILD_DIR ?= build/sphinx

.PHONY: man
man:
	$(SPHINX_BUILD) -a -b man $(SPHINX_BUILD_SOURCE_DIR) $(SPHINX_BUILD_BUILD_DIR)/man

.PHONY: html
html:
	$(SPHINX_BUILD) -a -b html $(SPHINX_BUILD_SOURCE_DIR) $(SPHINX_BUILD_BUILD_DIR)/html

.PHONY: sdist
sdist:
	$(PYTHON) -m build --sdist

.PHONY: wheel
wheel:
	$(PYTHON) -m build --wheel

.PHONY: clean
clean:
	$(RM) -r build/sphinx doc/api
