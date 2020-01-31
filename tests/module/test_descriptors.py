from snakeoil import descriptors


class ClassProp:

    @descriptors.classproperty
    def test(cls):
        """Just an example."""
        return 'good', cls


class TestDescriptor:

    def test_classproperty(self):
        assert ('good', ClassProp) == ClassProp.test
        assert ('good', ClassProp) == ClassProp().test
