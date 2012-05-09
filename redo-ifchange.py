#!/usr/bin/env python
import sys, os

import vars_init
vars_init.init(sys.argv[1:])

import vars as vars_, state, builder, jwack, deps
from helpers import unlink
from log import debug, debug2, err

def should_build(t):
    f = state.File(name=t)
    if f.is_failed():
        raise builder.ImmediateReturn(32)
    dirty = deps.isdirty(f, depth='', max_changed=vars_.RUNID)
    return dirty == [f] and deps.DIRTY or dirty


rv = 202
try:
    if vars_.TARGET and not vars_.UNLOCKED:
        me = os.path.join(vars_.STARTDIR, vars_.PWD, vars_.TARGET)
        f = state.File(name=me)
        debug2('TARGET: %r %r %r\n' % (vars_.STARTDIR, vars_.PWD, vars_.TARGET))
    else:
        f = me = None
        debug2('redo-ifchange: not adding depends.\n')
    try:
        targets = sys.argv[1:]
        if f:
            for t in targets:
                f.add_dep('m', t)
            f.save()
        rv = builder.main(targets, should_build)
    finally:
        jwack.force_return_tokens()
except KeyboardInterrupt:
    sys.exit(200)
state.commit()
sys.exit(rv)
