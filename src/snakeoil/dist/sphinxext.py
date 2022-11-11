"""small sphinx extension to generate docs from argparse scripts"""

import sys
from importlib import import_module
from pathlib import Path

from sphinx.application import Sphinx
from sphinx.ext.apidoc import main as sphinx_apidoc

from .generate_docs import _generate_custom
from .generate_man_rsts import ManConverter
from .utilities import module_version

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def prepare_scripts_man(repo_dir: Path, man_pages: list[tuple]):
    # Workaround for sphinx doing include directive path mangling in
    # order to interpret absolute paths "correctly", but at the same
    # time causing relative paths to fail. This just bypasses the
    # sphinx mangling and lets docutils handle include directives
    # directly which works as expected.
    from docutils.parsers.rst.directives.misc import Include as BaseInclude
    from sphinx.directives.other import Include
    Include.run = BaseInclude.run

    with open(repo_dir / 'pyproject.toml', 'rb') as file:
        pyproj = tomllib.load(file)

    authors_list = [
        f'{author["name"]} <{author["email"]}>' for author in pyproj['project']['authors']
    ]

    for i, man_page in enumerate(man_pages):
        if man_page[3] is None:
            m = list(man_page)
            m[3] = authors_list
            man_pages[i] = tuple(m)

    man_gen_dir = str(repo_dir / 'doc' / 'generated')

    for name, entry in pyproj['project']['scripts'].items():
        module: str = entry.split(':')[0]
        man_pages.append((f'man/{name}', name, import_module(module).__doc__.strip().split('\n', 1)[0], authors_list, 1))
        ManConverter.regen_if_needed(man_gen_dir, module.replace('__init__', name), out_name=name)


def generate_html(repo_dir: Path, module: str):
    """Generate API rst docs for a project.

    This uses sphinx-apidoc to auto-generate all the required rst files.
    """
    apidir = repo_dir / 'doc' / 'api'
    package_dir = repo_dir / 'src' / module
    sphinx_apidoc(['-Tef', '-o', str(apidir),
                   str(package_dir), str(package_dir / 'test'),
                   str(package_dir / 'scripts')])


def doc_backend(app: Sphinx):
    repo_dir = Path(app.config.repodir)
    if not app.config.version:
        app.config.version = module_version(repo_dir, repo_dir / 'src' / app.config.project)

    prepare_scripts_man(repo_dir, app.config.man_pages)

    if app.builder.name in ('man', 'html'):
        docdir = repo_dir / 'doc'
        _generate_custom(app.config.project, str(docdir), str(docdir / 'generated'))

    if app.builder.name == 'html':
        generate_html(repo_dir, app.config.project)


def setup(app: Sphinx):
    app.connect('builder-inited', doc_backend)
    app.add_config_value(name="repodir", default=Path.cwd(), rebuild=True)
