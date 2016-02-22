#!/usr/bin/env python

"""Generate man page and html rst docs for a given project."""

import argparse
import errno
import os
import subprocess
import sys
import textwrap

from snakeoil.dist.generate_man_rsts import ManConverter


def generate_man(project, project_dir):
    """Generate man page rst docs for a project's installed scripts.

    This assumes that all the files in the 'bin' directory under the main
    project root are targeted scripts.
    """
    docdir = os.path.join(project_dir, 'doc')
    gendir = os.path.join(docdir, 'generated')
    print("Generating files for {} man pages in '{}'".format(project, gendir))

    try:
        os.mkdir(gendir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    scripts = os.listdir(os.path.abspath(os.path.join(project_dir, 'bin')))

    # Replace '-' with '_' due to python namespace contraints.
    generated_man_pages = [
        ('%s.scripts.' % (project) + s.replace('-', '_'), s) for s in scripts
    ]

    for module, script in generated_man_pages:
        rst = script + '.rst'
        # generate missing, generic man page rst docs
        if not os.path.isfile(os.path.join(docdir, 'man', rst)):
            with open(os.path.join(gendir, rst), 'w') as f:
                f.write(textwrap.dedent("""\
                    {header}
                    {script}
                    {header}

                    .. include:: {script}/main_synopsis.rst
                    .. include:: {script}/main_description.rst
                    .. include:: {script}/main_options.rst
                """.format(header=('=' * len(script)), script=script)))
            os.symlink(os.path.join(gendir, rst), os.path.join(docdir, 'man', rst))
        if not os.path.exists(os.path.join(docdir, 'man', script)):
            os.symlink(os.path.join(gendir, script), os.path.join(docdir, 'man', script))
        ManConverter.regen_if_needed(gendir, module, out_name=script)


def generate_html(project, project_dir):
    """Generate API rst docs for a project.

    This uses sphinx-apidoc to auto-generate all the required rst files.
    """
    apidir = os.path.join(project_dir, 'doc', 'api')
    print("Generating {} API docs in '{}'".format(project, apidir))
    if subprocess.call(['sphinx-apidoc', '-Tef', '-o', apidir,
                        os.path.join(project_dir, project),
                        os.path.join(project_dir, project, 'test'),
                        os.path.join(project_dir, project, 'scripts')]):
        raise RuntimeError('API doc generation failed')


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='generate docs')
    argparser.add_argument('--man', action='store_true', help='generate man files')
    argparser.add_argument('--html', action='store_true', help='generate API files')
    argparser.add_argument(
        'project', nargs=2, metavar='PROJECT_DIR PROJECT',
        help='project root directory and main module name')

    opts = argparser.parse_args()
    opts.project_dir = os.path.abspath(opts.project[0])
    opts.project = opts.project[1]

    libdir = os.path.abspath(os.path.join(opts.project_dir, 'build', 'lib'))
    if os.path.exists(libdir):
        sys.path.insert(0, libdir)
    sys.path.insert(1, opts.project_dir)

    # if run with no args, build all docs
    if not opts.man and not opts.html:
        opts.man = opts.html = True

    if opts.man:
        generate_man(opts.project, opts.project_dir)

    if opts.html:
        generate_html(opts.project, opts.project_dir)
