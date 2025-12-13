import snakeoil
import snakeoil._internals
from snakeoil.test import code_quality


class TestSlots(code_quality.Slots):
    namespaces = ("snakeoil",)
    namespace_ignores = (
        # The bulk of the ignores are since the code involved just needs to be rewritten
        "snakeoil.bash",
        "snakeoil.chksum",
        "snakeoil.cli.arghparse",
        "snakeoil.compression",
        "snakeoil.contexts",
        "snakeoil.data_source",  # oofta on that class, py2k/py3k transition was brutal on that one.
        "snakeoil.demandload",  # needs to be rewritten to descriptor protocol in particular
        "snakeoil.klass._deprecated",
        "snakeoil.dist",
        "snakeoil.formatters",
        "snakeoil.process",
        "snakeoil.stringio",
        "snakeoil.struct_compat",
        "snakeoil.tar",
        "snakeoil.test",
        "snakeoil.tools",  # this is CLI stuff which a lot of it intentionally avoids snakeoil internals
    )
    strict = True


class TestModules(code_quality.Modules):
    namespaces = ("snakeoil",)
    namespace_ignores = (
        # dead code only existing to not break versions of down stream
        # packaging.  They'll be removed
        "snakeoil.test.eq_hash_inheritance",
        "snakeoil.test.mixins",
        "snakeoil.test.slot_shadowing",
    )


class TestExpiredDeprecations(code_quality.ExpiredDeprecations):
    namespaces = ("snakeoil",)
    registry = snakeoil._internals.deprecated
