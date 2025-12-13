import re

import pytest

from snakeoil import demandload
from snakeoil._internals import deprecated


class TestDemandCompileRegexp:
    def test_demand_compile_regexp(self):
        with deprecated.suppress_deprecations():
            scope = {}
            demandload.demand_compile_regexp("foo", "frob", scope=scope)
            assert list(scope.keys()) == ["foo"]
            assert "frob" == scope["foo"].pattern
            assert "frob" == scope["foo"].pattern

            # verify it's delayed via a bad regex.
            demandload.demand_compile_regexp("foo", "f(", scope=scope)
            assert list(scope.keys()) == ["foo"]
            # should blow up on accessing an attribute.
            obj = scope["foo"]
            with pytest.raises(re.error):
                getattr(obj, "pattern")
