import gc
from types import FrameType

import pytest

from snakeoil.test import mk_cpy_loadable_testcase
from snakeoil import caching


def gen_test(WeakInstMeta):
    class weak_slotted(metaclass=WeakInstMeta):
        __inst_caching__ = True
        __slots__ = ('one',)

    class weak_inst(metaclass=WeakInstMeta):
        __inst_caching__ = True
        counter = 0
        def __new__(cls, *args, **kwargs):
            cls.counter += 1
            return object.__new__(cls)
        def __init__(self, *args, **kwargs):
            pass
        @classmethod
        def reset(cls):
            cls.counter = 0

    class automatic_disabled_weak_inst(weak_inst):
        pass

    class explicit_disabled_weak_inst(weak_inst):
        __inst_caching__ = False

    class reenabled_weak_inst(automatic_disabled_weak_inst):
        __inst_caching__ = True

    class TestWeakInstMeta:

        def test_reuse(self, kls=weak_inst):
            kls.reset()
            o = kls()
            assert o is kls()
            assert kls.counter == 1
            del o
            kls()
            assert kls.counter == 2

        def test_disabling_inst(self):
            weak_inst.reset()
            for x in (1, 2):
                o = weak_inst(disable_inst_caching=True)
                assert weak_inst.counter is x
            del o
            o = weak_inst()
            assert o is not weak_inst(disable_inst_caching=True)

        def test_class_disabling(self):
            automatic_disabled_weak_inst.reset()
            assert automatic_disabled_weak_inst() is not automatic_disabled_weak_inst()
            assert explicit_disabled_weak_inst() is not explicit_disabled_weak_inst()

        def test_reenabled(self):
            self.test_reuse(reenabled_weak_inst)

        # Read this before doing anything with the warnings-related
        # tests unless you really enjoy debugging Heisenbugs.
        #
        # The warnings module is optimized for the common case of
        # warnings that should be ignored: it stores a "key"
        # consisting of the type of warning, the warning message and
        # the module it originates from in a dict (cleverly hidden
        # away in the globals() of the frame calling warn()) if a
        # warning should be ignored, and then immediately ignores
        # warnings matching that key, *without* looking at the current
        # filters list.
        #
        # This means that if our test(s) with warnings ignored run
        # before tests with warnings turned into exceptions (test
        # order is random, enter Heisenbugs) and both tests involve
        # the same exception message they will screw up the tests.
        #
        # To make matters more interesting the warning message we deal
        # with here is not constant. Specifically it contains the
        # repr() of an argument tuple, containing a class instance,
        # which means the message will contain the address that object
        # is stored at!
        #
        # This exposed itself as crazy test failures where running
        # from .py fails and from .pyc works (perhaps related to the
        # warnings module taking a different codepath for this) and
        # creating objects or setting pdb breakpoints before that
        # failure caused the test to pass again.
        #
        # What all this means: Be 100% positively absolutely sure
        # test_uncachable and test_uncachable_warnings do not see the
        # same warning message ever. We do that by making sure their
        # warning messages contain a different classname
        # (RaisingHashFor...).

        # UserWarning is ignored and everything other warning is an error.
        @pytest.mark.filterwarnings('ignore::UserWarning')
        @pytest.mark.filterwarnings('error')
        def test_uncachable(self):
            weak_inst.reset()

            # This name is *important*, see above.
            class RaisingHashForTestUncachable:
                def __init__(self, error):
                    self.error = error
                def __hash__(self):
                    raise self.error

            assert weak_inst([]) is not weak_inst([])
            assert weak_inst.counter == 2
            for x in (TypeError, NotImplementedError):
                assert weak_inst(RaisingHashForTestUncachable(x)) is not \
                    weak_inst(RaisingHashForTestUncachable(x))

        @pytest.mark.filterwarnings('error::UserWarning')
        def test_uncachable_warning_msg(self):
            # This name is *important*, see above.
            class RaisingHashForTestUncachableWarnings:
                def __init__(self, error):
                    self.error = error
                def __hash__(self):
                    raise self.error

            for x in (TypeError, NotImplementedError):
                with pytest.raises(UserWarning):
                    weak_inst(RaisingHashForTestUncachableWarnings(x))

        def test_hash_collision(self):
            class BrokenHash:
                def __hash__(self):
                    return 1
            assert weak_inst(BrokenHash()) is not weak_inst(BrokenHash())

        def test_weak_slot(self):
            weak_slotted()

        def test_keyword_args(self):
            o = weak_inst(argument=1)
            assert o is weak_inst(argument=1)
            assert o is not weak_inst(argument=2)

        def test_existing_weakref_slot(self):
            # The actual test is that the class definition works.
            class ExistingWeakrefSlot:
                __inst_caching__ = True
                __slots__ = ('one', '__weakref__')

            assert ExistingWeakrefSlot()

        def test_weakref(self):
            weak_inst.reset()
            unique = object()
            o = weak_inst(unique)
            # make sure it's only strong ref-ed
            assert weak_inst.counter == 1
            _myid = id(o)
            del o
            o = weak_inst(unique)
            assert weak_inst.counter == 2

    return TestWeakInstMeta

# "Invalid name"
# pylint: disable=C0103

TestNativeWeakInstMeta = gen_test(caching.native_WeakInstMeta)

if caching.cpy_WeakInstMeta is not None:
    Test_CPY_WeakInstMeta = gen_test(caching.cpy_WeakInstMeta)
else:
    # generate fake test and skip it
    @pytest.mark.skip("cpython extension isn't available")
    class Test_CPY_WeakInstMeta(gen_test(type)):
        pass

Test_cpy_loaded = mk_cpy_loadable_testcase(
    "snakeoil._caching", "snakeoil.caching", "WeakInstMeta", "WeakInstMeta")
