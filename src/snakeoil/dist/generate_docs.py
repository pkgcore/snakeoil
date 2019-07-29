#!/usr/bin/env python3

"""Generate man page and html rst docs for a given project."""

import argparse
import errno
from importlib import import_module
from io import StringIO
import os
import subprocess
import sys
import textwrap

from .generate_man_rsts import ManConverter
from ..contexts import syspath


def _generate_custom(project, docdir, gendir):
    """Generate custom rst docs defined by a project.

    Projects needing custom docs generated should place executable scripts in
    doc/generate that output rst data which gets written to the same
    subdirectory paths under doc/generated.

    For example, during doc build the executable python script
    doc/generate/custom/doc.py gets run and the rst output gets written to
    doc/generated/custom/doc.rst allowing it to be sourced by other rst files.
    """
    custom_dir = os.path.join(docdir, 'generate')
    print(f"Generating custom docs for {project} in {gendir!r}")

    for root, dirs, files in os.walk(custom_dir):
        subdir = root.split(custom_dir, 1)[1].strip('/')
        if subdir:
            try:
                os.mkdir(os.path.join(gendir, subdir))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

        for script in sorted(x for x in files if not x.startswith(('.', '_'))):
            script_path = os.path.join(custom_dir, subdir, script)
            if not os.access(script_path, os.X_OK):
                continue

            fake_file = StringIO()
            with syspath(os.path.dirname(script_path)):
                module = import_module(os.path.basename(os.path.splitext(script_path)[0]))
                module.main(fake_file, docdir=docdir, gendir=gendir)

            fake_file.seek(0)
            data = fake_file.read()
            if data:
                rst = os.path.join(gendir, subdir, os.path.splitext(script)[0] + '.rst')
                print(f"generating {rst}")
                with open(rst, 'w') as f:
                    f.write(data)


def generate_man(repo_dir, package_dir, module):
    """Generate man page rst docs for a module's installed scripts.

    This assumes that all the files in the 'bin' directory under the main
    repo root are targeted scripts.
    """
    docdir = os.path.join(repo_dir, 'doc')
    gendir = os.path.join(docdir, 'generated')

    print(f"Generating files for {module} man pages in {gendir!r}")
    scripts = os.listdir(os.path.abspath(os.path.join(repo_dir, 'bin')))

    # Replace '-' with '_' due to python namespace contraints.
    generated_man_pages = [
        ('%s.scripts.' % (module) + s.replace('-', '_'), s) for s in scripts
    ]

    # generate specified man pages for scripts
    for module, script in generated_man_pages:
        ManConverter.regen_if_needed(gendir, module, out_name=script)

    # run scripts to generate any custom docs
    _generate_custom(module, docdir, gendir)


def generate_html(repo_dir, package_dir, module):
    """Generate API rst docs for a project.

    This uses sphinx-apidoc to auto-generate all the required rst files.
    """
    apidir = os.path.join(repo_dir, 'doc', 'api')
    print(f"Generating {module} API docs in {apidir!r}")
    if subprocess.call(['sphinx-apidoc', '-Tef', '-o', apidir,
                        os.path.join(package_dir, module),
                        os.path.join(package_dir, module, 'test'),
                        os.path.join(package_dir, module, 'scripts')]):
        raise RuntimeError(
            'API doc generation failed for %s' % (module,))


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='generate docs')
    argparser.add_argument('--man', action='store_true', help='generate man files')
    argparser.add_argument('--html', action='store_true', help='generate API files')
    argparser.add_argument(
        'project', nargs=3, metavar='REPO_DIR PACKAGE_DIR MODULE',
        help='package directory and main module name')

    opts = argparser.parse_args()
    opts.repo_dir = os.path.abspath(opts.project[0])
    opts.package_dir = opts.project[1]
    opts.module = opts.project[2]

    libdir = os.path.abspath(os.path.join(opts.repo_dir, 'build', 'lib'))
    if os.path.exists(libdir):
        sys.path.insert(0, libdir)
    sys.path.insert(1, opts.repo_dir)

    # if run with no args, build all docs
    if not opts.man and not opts.html:
        opts.man = opts.html = True

    if opts.man:
        generate_man(opts.repo_dir, opts.package_dir, opts.module)

    if opts.html:
        generate_html(opts.repo_dir, opts.package_dir, opts.module)
