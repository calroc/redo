import sys, os


def init(targets):
    if not os.environ.get('REDO'):
        # toplevel call to redo
        if not targets:
            targets.append('all')
        exename = sys.argv[0]
        exenames = [os.path.abspath(exename),
                    os.path.realpath(exename)]
        dirnames = [os.path.dirname(p) for p in exenames]
        trynames = ([os.path.abspath(p+'/../lib/redo') for p in dirnames] +
                    [p+'/redo-sh' for p in dirnames] +
                    dirnames)

        dirs = sorted(set(trynames), key=trynames.index)
        dirs.append(os.environ['PATH'])
        os.environ['PATH'] = ':'.join(dirs)
        os.environ['REDO'] = os.path.abspath(exename)

    if not os.environ.get('REDO_BASE'):
        base = os.path.commonprefix([os.path.abspath(os.path.dirname(t))
                                     for t in targets] + [os.getcwd()])
        bsplit = base.split('/')
        for i in range(len(bsplit)):
            newbase = '/'.join(bsplit[:-i])
            if os.path.exists(newbase + '/.redo'):
                base = newbase
                break
        os.environ['REDO_BASE'] = base
        os.environ['REDO_STARTDIR'] = os.getcwd()

        import state
        state.init()
