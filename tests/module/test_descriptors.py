from snakeoil import descriptors


class ClassProp(object):

    @descriptors.classproperty
    def test(cls):
        """Just an example."""
        return 'good', cls


class TestDescriptor(object):

    def test_classproperty(self):
        assert ('good', ClassProp) == ClassProp.test
        assert ('good', ClassProp) == ClassProp().test
