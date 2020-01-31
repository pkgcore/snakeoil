"""snakeoil-based pytest fixtures"""

import pytest

from . import random_str


class TempDir:
    """Provide temporary directory to every test method."""

    @pytest.fixture(autouse=True)
    def __setup(self, tmpdir):
        self.dir = str(tmpdir)


class RandomPath:
    """Provide random path in a temporary directory to every test method."""

    @pytest.fixture(autouse=True)
    def __setup(self, tmpdir):
        self.path = str(tmpdir.join(random_str(10)))
