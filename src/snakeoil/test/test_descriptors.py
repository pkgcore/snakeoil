# Copyright: 2006 Marien Zwart <marienz@gentoo.org>
# License: BSD/GPL2


from snakeoil.test import TestCase
from snakeoil import descriptors


class ClassProp(object):

    @descriptors.classproperty
    def test(cls):
        """Just an example."""
        return 'good', cls


class DescriptorTest(TestCase):

    def test_classproperty(self):
        self.assertEqual(('good', ClassProp), ClassProp.test)
        self.assertEqual(('good', ClassProp), ClassProp().test)
