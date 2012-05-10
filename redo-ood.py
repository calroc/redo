#!/usr/bin/env python
import sys

import vars_init
vars_init.init([])

import vars as vars_, state
from log import err

if len(sys.argv) != 1:
    err('%s: no arguments expected.\n' % sys.argv[0])
    sys.exit(1)


def make_cache():
    _ = {}
    def is_checked(f):
        return _.get(f.id, 0)
    def set_checked(f):
        _[f.id] = 1
    cache = locals().copy()
    del cache['_']
    return cache


for f in state.files():
    if (f.is_generated and
        f.read_stamp() != state.STAMP_MISSING and
        f.is_dirty(vars_.RUNID, **make_cache())):
        print f.nicename()
