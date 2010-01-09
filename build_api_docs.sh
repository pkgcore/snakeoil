#!/bin/bash -x
if [ -z "$2" ] || [ "$#" != 2 ]; then
    echo "need two args- [ html | pdf ], and the directory location to write the results to"
    exit 1
fi

if [ "$1" != "html" ] && [ "$1" != "pdf" ]; then
    echo "first arg must be either html, or pdf; $1 isn't valid."
    exit 2
fi

export SNAKEOIL_DEMANDLOAD_PROTECTION=n
export SNAKEOIL_DEMANDLOAD_DISABLED=y
epydoc --${1} --no-frames --no-frames --graph=all -n snakeoil -u \
    http://pkgcore.org/trac/snakeoil --show-imports --include-log \
    --inheritance=included --quiet --simple-term -o "$2" snakeoil --debug \
        --exclude='snakeoil\.test\..*' -v
