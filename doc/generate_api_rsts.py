#!/usr/bin/python
from snakeoil.modules import load_module
import inspect, exceptions, sys

def gen_segment(name, targets):
    l = ["    .. rubric:: %s" % (name,)]
    l.append('')
    l.append("    .. autosummary::")
    l.append('')
    l.extend("       %s" % x for x in sorted(targets))
    l.append("")
    return "\n".join(l)

def generate_rst(modpath):
    module = load_module(modpath)
    target_names = [x for x in dir(module) if not (x.startswith("_")
        or inspect.ismodule(getattr(module, x)))]
    target_names = getattr(module, '__all__', target_names)
    klasses, funcs, exceptions, others = [], [], [], []
    modules = []
    base_exception = globals().get("BaseException", Exception)
    for target in target_names:
        try:
            obj = getattr(module, target)
        except AttributeError, a:
            sys.stderr.write("failed processing %s, accessing %s: %s\n" %
                (modpath, target, a))
            raise
        if inspect.isclass(obj):
            if issubclass(obj, base_exception):
                exceptions.append(target)
            else:
                klasses.append(target)
        elif callable(obj):
            funcs.append(target)
        elif inspect.ismodule(obj):
            modules.append(target)
        else:
            others.append(target)

    print modpath
    print '-' * len(modpath)
    print
    print ".. automodule:: %s" % (modpath,)
    print
    if funcs:
        print gen_segment("Functions", funcs)
    if klasses:
        print gen_segment("Classes", klasses)
    if exceptions:
        print gen_segment("Exceptions", exceptions)
    if modules:
        print gen_segment("Submodules", modules)
    if others:
        print gen_segment("Data", others)

if __name__ == '__main__':
    import sys
    generate_rst(sys.argv[1])
