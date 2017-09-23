# Copyright: 2006-2007 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

from functools import partial
import math
from time import time

from snakeoil import klass
from snakeoil.compatibility import cmp, is_py3k
from snakeoil.test import TestCase, mk_cpy_loadable_testcase, not_a_test


class Test_native_GetAttrProxy(TestCase):
    kls = staticmethod(klass.native_GetAttrProxy)

    def test_it(self):
        class foo1(object):
            def __init__(self, obj):
                self.obj = obj
            __getattr__ = self.kls('obj')

        class foo2(object):
            pass

        o2 = foo2()
        o = foo1(o2)
        self.assertRaises(AttributeError, getattr, o, "blah")
        self.assertEqual(o.obj, o2)
        o2.foon = "dar"
        self.assertEqual(o.foon, "dar")
        o.foon = "foo"
        self.assertEqual(o.foon, 'foo')

    def test_attrlist(self):
        def make_class(attr_list=None):
            class foo(object):
                __metaclass__ = self.kls

                if attr_list is not None:
                    locals()['__attr_comparison__'] = attr_list

        self.assertRaises(TypeError, make_class)
        self.assertRaises(TypeError, make_class, [u'foon'])
        self.assertRaises(TypeError, make_class, [None])

    def test_instancemethod(self):
        class foo(object):
            bar = "baz"

        class Test(object):
            method = self.kls('test')
            test = foo()

        test = Test()
        self.assertEqual(test.method('bar'), foo.bar)


class Test_CPY_GetAttrProxy(Test_native_GetAttrProxy):

    kls = staticmethod(klass.GetAttrProxy)
    if klass.GetAttrProxy is klass.native_GetAttrProxy:
        skip = "cpython extension isn't available"

    def test_sane_recursion_bail(self):
        # people are stupid; if protection isn't in place, we wind up blowing
        # the c stack, which doesn't result in a friendly Exception being
        # thrown.
        # results in a segfault.. so if it's horked, this will bail the test
        # runner.

        class c(object):
            __getattr__ = self.kls("obj")

        o = c()
        o.obj = o
        # now it's cyclical.
        self.assertRaises((AttributeError, RuntimeError), getattr, o, "hooey")


class Test_native_contains(TestCase):
    func = staticmethod(klass.native_contains)

    def test_it(self):
        class c(dict):
            __contains__ = self.func
        d = c({"1": 2})
        self.assertIn("1", d)
        self.assertNotIn(1, d)


class Test_CPY_contains(Test_native_contains):
    func = staticmethod(klass.contains)

    if klass.contains is klass.native_contains:
        skip = "cpython extension isn't available"


class Test_native_get(TestCase):
    func = staticmethod(klass.native_get)

    def test_it(self):
        class c(dict):
            get = self.func
        d = c({"1": 2})
        self.assertEqual(d.get("1"), 2)
        self.assertEqual(d.get("1", 3), 2)
        self.assertEqual(d.get(1), None)
        self.assertEqual(d.get(1, 3), 3)

class Test_CPY_get(Test_native_get):
    func = staticmethod(klass.get)

    if klass.get is klass.native_get:
        skip = "cpython extension isn't available"

class Test_native_generic_equality(TestCase):
    op_prefix = "native_"

    kls = partial(
        klass.generic_equality,
        ne=klass.native_generic_attr_ne,
        eq=klass.native_generic_attr_eq)

    def test_it(self):
        class c(object):
            __attr_comparison__ = ("foo", "bar")
            __metaclass__ = self.kls
            def __init__(self, foo, bar):
                self.foo, self.bar = foo, bar

            def __repr__(self):
                return "<c: foo=%r, bar=%r, %i>" % (
                    getattr(self, 'foo', 'unset'),
                    getattr(self, 'bar', 'unset'),
                    id(self))

        self.assertEqual(c(1, 2), c(1, 2))
        c1 = c(1, 3)
        self.assertEqual(c1, c1)
        del c1
        self.assertNotEqual(c(2, 1), c(1, 2))
        c1 = c(1, 2)
        del c1.foo
        c2 = c(1, 2)
        self.assertNotEqual(c1, c2)
        del c2.foo
        self.assertEqual(c1, c2)

    def test_call(self):
        def mk_class(meta):
            class c(object):
                __metaclass__ = meta
            return c
        self.assertRaises(TypeError, mk_class)


class Test_cpy_generic_equality(Test_native_generic_equality):
    op_prefix = ''
    if klass.native_generic_attr_eq is klass.generic_eq:
        skip = "extension not available"

    kls = staticmethod(klass.generic_equality)


class Test_inject_richcmp_methods_from_cmp(TestCase):

    func = staticmethod(klass.inject_richcmp_methods_from_cmp)

    def get_cls(self, force=False, overrides={}):
        class foo(object):

            def __init__(self, value):
                self.value = value

            def __cmp__(self, other):
                return cmp(self.value, other.value)

            self.func(locals(), force)
            locals().update(overrides)
        return foo

    def test_it(self):
        for force in (True, False):
            kls = self.get_cls(force)
            self.assertTrue(kls(1) > kls(0))
            self.assertTrue(kls(1) >= kls(0))
            self.assertTrue(kls(1) >= kls(1))
            self.assertFalse(kls(1) > kls(2))
            self.assertFalse(kls(1) >= kls(2))
            self.assertTrue(kls(1) == kls(1))
            self.assertTrue(kls(2) == kls(2))
            self.assertFalse(kls(2) != kls(2))
            self.assertTrue(kls(2) != kls(1))
            self.assertTrue(kls(0) < kls(1))
            self.assertTrue(kls(0) <= kls(1))
            self.assertTrue(kls(1) <= kls(1))
            self.assertFalse(kls(1) < kls(1))
            self.assertFalse(kls(2) < kls(1))
            if not is_py3k and force:
                for methname in ("lt", "le", "ge", "eq", "ne", "gt", "ge"):
                    self.assertTrue(hasattr(kls, '__%s__' % methname))


class Test_chained_getter(TestCase):

    kls = klass.chained_getter

    def test_hash(self):
        self.assertEqual(hash(self.kls("foon")), hash("foon"))
        self.assertEqual(hash(self.kls("foon.dar")), hash("foon.dar"))

    def test_caching(self):
        l = [id(self.kls("fa2341f%s" % x)) for x in "abcdefghij"]
        self.assertEqual(id(self.kls("fa2341fa")), l[0])

    def test_eq(self):
        self.assertEqual(self.kls("asdf", disable_inst_caching=True),
                         self.kls("asdf", disable_inst_caching=True))

        self.assertNotEqual(self.kls("asdf2", disable_inst_caching=True),
                            self.kls("asdf", disable_inst_caching=True))

    def test_it(self):
        class maze(object):
            def __init__(self, kwargs):
                self.__data__ = kwargs

            def __getattr__(self, attr):
                return self.__data__.get(attr, self)

        d = {}
        m = maze(d)
        f = self.kls
        self.assertEqual(f('foon')(m), m)
        d["foon"] = 1
        self.assertEqual(f('foon')(m), 1)
        self.assertEqual(f('dar.foon')(m), 1)
        self.assertEqual(f('.'.join(['blah']*10))(m), m)
        self.assertRaises(AttributeError, f('foon.dar'), m)


class Test_native_jit_attr(TestCase):

    kls = staticmethod(klass._native_internal_jit_attr)

    @property
    def jit_attr(self):
        return partial(klass.jit_attr, kls=self.kls)

    @property
    def jit_attr_named(self):
        return partial(klass.jit_attr_named, kls=self.kls)

    @property
    def jit_attr_ext_method(self):
        return partial(klass.jit_attr_ext_method, kls=self.kls)

    def mk_inst(self, attrname='_attr', method_lookup=False,
                use_cls_setattr=False, func=None,
                singleton=klass._uncached_singleton):

        f = func
        if not func:
            def f(self):
                self._invokes.append(self)
                return 54321

        class cls(object):

            def __init__(self):
                sf = partial(object.__setattr__, self)
                sf('_sets', [])
                sf('_reflects', [])
                sf('_invokes', [])

            attr = self.kls(f, attrname, singleton, use_cls_setattr)

            def __setattr__(self, attr, value):
                self._sets.append(self)
                object.__setattr__(self, attr, value)

            def reflect(self):
                self._reflects.append(self)
                return 12345

        return cls()

    def assertState(self, instance, sets=0, reflects=0, invokes=0, value=54321):
        self.assertEqual(instance.attr, value)
        sets = [instance] * sets
        reflects = [instance] * reflects
        invokes = [instance] * invokes
        msg = ("checking %s: got(%r), expected(%r); state was sets=%r, "
               "reflects=%r, invokes=%r" % (
                   "%s", "%s", "%s", instance._sets, instance._reflects,
                   instance._invokes))
        self.assertEqual(instance._sets, sets,
                         msg=(msg % ("sets", instance._sets, sets,)))
        self.assertEqual(instance._reflects, reflects,
                         msg=(msg % ("reflects", instance._reflects,
                                     reflects,)))
        self.assertEqual(instance._invokes, invokes,
                         msg=(msg % ("invokes", instance._invokes, invokes,)))

    def test_implementation(self):
        obj = self.mk_inst()

        # default state is use_cls_setattr = False
        self.assertState(obj, invokes=1)
        self.assertState(obj, invokes=1)
        del obj._attr
        self.assertState(obj, invokes=2)
        self.assertState(obj, invokes=2)

        # basic caching is now verified.
        obj = self.mk_inst(use_cls_setattr=True)
        self.assertState(obj, sets=1, invokes=1)
        self.assertState(obj, sets=1, invokes=1)
        del obj._attr
        self.assertState(obj, sets=2, invokes=2)
        self.assertState(obj, sets=2, invokes=2)

    def test_jit_attr(self):
        now = time()

        class cls(object):
            @self.jit_attr
            def my_attr(self):
                return now

        o = cls()
        self.assertEqual(o.my_attr, now)
        self.assertEqual(o._my_attr, now)

        class cls(object):
            @self.jit_attr
            def attr2(self):
                return now

            def __setattr__(self, attr, value):
                raise AssertionError("setattr was invoked")

        o = cls()
        self.assertEqual(o.attr2, now)
        self.assertEqual(o._attr2, now)
        del o._attr2
        self.assertEqual(o.attr2, now)
        self.assertEqual(o._attr2, now)

    def test_jit_attr_named(self):
        now = time()

        # check attrname control and default object.__setattr__ avoidance
        class cls(object):
            @self.jit_attr_named("_blah")
            def my_attr(self):
                return now

            def __setattr__(self, attr, value):
                raise AssertionError("setattr was invoked")

        o = cls()
        self.assertEqual(o.my_attr, now)
        self.assertEqual(o._blah, now)

        class cls(object):
            @self.jit_attr_named("_blah2", use_cls_setattr=True)
            def my_attr(self):
                return now

            def __setattr__(self, attr, value):
                object.__setattr__(self, "invoked", True)
                object.__setattr__(self, attr, value)

        o = cls()
        self.assertFalse(hasattr(o, 'invoked'))
        self.assertEqual(o.my_attr, now)
        self.assertEqual(o._blah2, now)
        self.assertTrue(o.invoked)

    def test_jit_attr_ext_method(self):
        now = time()
        now2 = now + 100

        class base(object):
            def f1(self):
                return now

            def f2(self):
                return now2

            def __setattr__(self, attr, value):
                if not getattr(self, '_setattr_allowed', False):
                    raise TypeError("setattr isn't allowed for %s" % attr)
                object.__setattr__(self, attr, value)

        base.attr = self.jit_attr_ext_method('f1', '_attr')
        o = base()
        self.assertEqual(o.attr, now)
        self.assertEqual(o._attr, now)
        self.assertEqual(o.attr, now)

        base.attr = self.jit_attr_ext_method('f1', '_attr', use_cls_setattr=True)
        o = base()
        self.assertRaises(TypeError, getattr, o, 'attr')
        base._setattr_allowed = True
        self.assertEqual(o.attr, now)

        base.attr = self.jit_attr_ext_method('f2', '_attr2')
        o = base()
        self.assertEqual(o.attr, now2)
        self.assertEqual(o._attr2, now2)

        # finally, check that it's doing lookups rather then storing the func.
        base.attr = self.jit_attr_ext_method('func', '_attr2')
        o = base()
        # no func...
        self.assertRaises(AttributeError, getattr, o, 'attr')
        base.func = base.f1
        self.assertEqual(o.attr, now)
        self.assertEqual(o._attr2, now)
        # check caching...
        base.func = base.f2
        self.assertEqual(o.attr, now)
        del o._attr2
        self.assertEqual(o.attr, now2)

    def test_check_singleton_is_compare(self):
        def throw_assert(*args, **kwds):
            raise AssertionError("I shouldn't be invoked: %s, %s" % (args, kwds,))

        class puker(object):
            __cmp__ = __eq__ = throw_assert

        puker_singleton = puker()

        obj = self.mk_inst(singleton=puker_singleton)
        obj._attr = puker_singleton
        # force attr access. if it's done wrong, it'll puke.
        # pylint: disable=pointless-statement
        obj.attr

    def test_cached_property(self):
        l = []
        class foo(object):
            @klass.cached_property
            def blah(self, l=l, i=iter(xrange(5))):
                l.append(None)
                return i.next()
        f = foo()
        self.assertEqual(f.blah, 0)
        self.assertEqual(len(l), 1)
        self.assertEqual(f.blah, 0)
        self.assertEqual(len(l), 1)
        del f.blah
        self.assertEqual(f.blah, 1)
        self.assertEqual(len(l), 2)

    def test_cached_property(self):
        l = []

        def named(self, l=l, i=iter(xrange(5))):
            l.append(None)
            return i.next()

        class foo(object):
            blah = klass.cached_property_named("blah")(named)

        f = foo()
        self.assertEqual(f.blah, 0)
        self.assertEqual(len(l), 1)
        self.assertEqual(f.blah, 0)
        self.assertEqual(len(l), 1)
        del f.blah
        self.assertEqual(f.blah, 1)
        self.assertEqual(len(l), 2)


class Test_cpy_jit_attr(Test_native_jit_attr):

    kls = staticmethod(klass._internal_jit_attr)
    if klass._internal_jit_attr is klass._native_internal_jit_attr:
        skip = "extension is missing"


class test_aliased_attr(TestCase):

    func = staticmethod(klass.alias_attr)

    def test_it(self):
        class cls(object):
            attr = self.func("dar.blah")

        o = cls()
        self.assertRaises(AttributeError, getattr, o, 'attr')
        o.dar = "foon"

        self.assertRaises(AttributeError, getattr, o, 'attr')
        o.dar = o
        o.blah = "monkey"

        self.assertEqual(o.attr, 'monkey')

        # verify it'll cross properties...
        class blah(object):
            target = object()

        class cls(object):
            @property
            def foon(self):
                return blah()

            alias = self.func("foon.target")
        o = cls()
        self.assertIdentical(o.alias, blah.target)


class test_cached_hash(TestCase):
    func = staticmethod(klass.cached_hash)

    def test_it(self):
        now = long(time())
        class cls(object):
            invoked = []
            @self.func
            def __hash__(self):
                self.invoked.append(self)
                return now
        o = cls()
        self.assertEqual(hash(o), now)
        self.assertEqual(o.invoked, [o])
        # ensure it cached...
        self.assertEqual(hash(o), now)
        self.assertEqual(o.invoked, [o])
        self.assertEqual(o._hash, now)


class test_native_reflective_hash(TestCase):
    func = staticmethod(klass.native_reflective_hash)

    def test_it(self):
        class cls(object):
            __hash__ = self.func('_hash')

        obj = cls()
        self.assertRaises(AttributeError, hash, obj)
        obj._hash = 1
        self.assertEqual(hash(obj), 1)
        obj._hash = 123123123
        self.assertEqual(hash(obj), 123123123)
        # verify it's not caching in any form
        del obj._hash
        self.assertRaises(AttributeError, hash, obj)

        class cls2(object):
            __hash__ = self.func('_dar')
        obj = cls2()
        self.assertRaises(AttributeError, hash, obj)
        obj._dar = 4
        self.assertEqual(hash(obj), 4)


class test_cpy_reflective_hash(test_native_reflective_hash):

    kls = staticmethod(klass.reflective_hash)
    if klass.reflective_hash is klass.native_reflective_hash:
        skip = "cpython extension isn't available"


cpy_loaded_Test = mk_cpy_loadable_testcase(
    "snakeoil._klass", "snakeoil.klass", "reflective_hash", "reflective_hash")


class TestImmutableInstance(TestCase):

    def test_metaclass(self):
        def f(scope):
            scope["__metaclass__"] = klass.immutable_instance

        self.common_test(f)

    def test_injection(self):

        def f(scope):
            klass.inject_immutable_instance(scope)

        self.common_test(f)

    @not_a_test
    def common_test(self, modify_kls):
        class kls(object):
            modify_kls(locals())

        o = kls()
        self.assertRaises(AttributeError, setattr, o, "dar", "foon")
        self.assertRaises(AttributeError, delattr, o, "dar")

        object.__setattr__(o, 'dar', 'foon')
        self.assertRaises(AttributeError, delattr, o, "dar")

        # ensure it only sets it if nothing is in place already.

        class kls(object):
            def __setattr__(self, attr, value):
                raise TypeError(self)

            modify_kls(locals())

        o = kls()
        self.assertRaises(TypeError, setattr, o, "dar", "foon")
        self.assertRaises(AttributeError, delattr, o, "dar")


class TestAliasMethod(TestCase):

    func = staticmethod(klass.alias_method)

    def test_alias_method(self):
        class kls(object):
            __len__ = lambda s: 3
            lfunc = self.func("__len__")

        c = kls()
        self.assertEqual(c.__len__(), c.lfunc())
        c.__len__ = lambda: 4
        self.assertEqual(c.__len__(), c.lfunc())


class TestPatch(TestCase):

    def setUp(self):
        # cache original methods
        self._math_ceil = math.ceil
        self._math_floor = math.floor

    def tearDown(self):
        # restore original methods
        math.ceil = self._math_ceil
        math.floor = self._math_floor

    def test_patch(self):
        n = 0.1
        self.assertEqual(math.ceil(n), 1)

        @klass.patch('math.ceil')
        def ceil(orig_ceil, n):
            return math.floor(n)

        self.assertEqual(math.ceil(n), 0)

    def test_multiple_patches(self):
        n = 1.1
        self.assertEqual(math.ceil(n), 2)
        self.assertEqual(math.floor(n), 1)

        @klass.patch('math.ceil')
        @klass.patch('math.floor')
        def zero(orig_func, n):
            return 0

        self.assertEqual(math.ceil(n), 0)
        self.assertEqual(math.floor(n), 0)
