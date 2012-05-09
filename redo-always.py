#!/usr/bin/env python
import sys, os
import vars as vars_, state
from log import err


try:
    me = os.path.join(vars_.STARTDIR, vars_.PWD, vars_.TARGET)
    f = state.File(name=me)
    f.add_dep('m', state.ALWAYS)
    always = state.File(name=state.ALWAYS)
    always.stamp = state.STAMP_MISSING
    always.set_changed()
    always.save()
    state.commit()
except KeyboardInterrupt:
    sys.exit(200)
