from snakeoil.test.code_quality import Slots


class TestSlots(Slots):
    namespaces = ["snakeoil"]
    namespace_ignores = (
        # The bulk of the ignores are since the code involved just needs to be rewritten
        "snakeoil.bash",
        "snakeoil.chksum",
        "snakeoil.cli.arghparse",
        "snakeoil.compression",
        "snakeoil.constraints",
        "snakeoil.contexts",
        "snakeoil.data_source",  # oofta on that class, py2k/py3k transition was brutal on that one.
        "snakeoil.demandload",  # needs to be rewritten to descriptor protocol in particular.
        "snakeoil.demandimport",  # may need rewrite, but isn't worth caring.  Py3.15 renders this dead.
        "snakeoil.klass.deprecated",
        "snakeoil.dist",
        "snakeoil.formatters",
        "snakeoil.process",
        "snakeoil.stringio",
        "snakeoil.tar",
        "snakeoil.test",
    )
    ignored_subclasses = (Exception,)
    strict = True
