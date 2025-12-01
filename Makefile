PYTHON ?= python

.PHONY: man html
man html:
	doc/build.sh $@ "$$(pwd)/build/sphinx/$@"

html: man

.PHONY: docs
docs: man html

.PHONY: sdist wheel
sdist wheel:
	$(PYTHON) -m build --$@

sdist: man

.PHONY: release
release: sdist wheel

.PHONY: clean
clean:
	$(RM) -rf build/sphinx doc/api dist

.PHONY: format
format:
	$(PYTHON) -m ruff format

.PHONY: dev-environment
dev-environment:
	$(PYTHON) -m pip install -e .[test,doc,formatter]
