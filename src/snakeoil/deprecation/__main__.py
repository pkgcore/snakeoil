import importlib
import typing

from snakeoil.cli import arghparse
from snakeoil.cli.tool import Tool
from snakeoil.deprecation import Registry


def parse_import(value):
    l = value.rsplit(".", 1)
    if len(l) <= 1:
        raise ValueError("import path must be <module>.<registry_name>")
    mod = importlib.import_module(l[0])
    return getattr(mod, l[1])


parser = arghparse.ArgumentParser(
    description="tool for outputing the deprecations of a given a registry"
)
parser.add_argument(
    "registry",
    type=parse_import,
    help="the python qualified name of where to find the registry",
)


@parser.bind_main_func
def main(options, out, _err) -> int:
    registry = typing.cast(Registry, options.registry)
    for deprecation in sorted(
        registry.expired_deprecations(
            python_version=(1000, 0, 0), project_version=(1000, 0, 0), with_notes=False
        ),
        key=lambda x: str(x),
    ):
        out.write(f"{deprecation}")

    return 0


if __name__ == "__main__":
    Tool(parser)()
