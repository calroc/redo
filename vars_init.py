import sys
from os import environ, getcwd
from os.path import abspath, realpath, dirname, commonprefix, exists


def init(targets):
    if not environ.get('REDO'):
        # toplevel call to redo
        if not targets:
            targets.append('all')
        exename = sys.argv[0]
        dirnames = map(dirname, (abspath(exename), realpath(exename)))
        trynames = ([abspath(p+'/../lib/redo') for p in dirnames] +
                    [p+'/redo-sh' for p in dirnames] +
                    dirnames)
        dirs = sorted(set(trynames), key=trynames.index)
        dirs.append(environ['PATH'])
        environ['PATH'] = ':'.join(dirs)
        environ['REDO'] = abspath(exename)

    if not environ.get('REDO_BASE'):
        cwd = getcwd()
        base = commonprefix([abspath(dirname(t)) for t in targets] +
                            [cwd])
        bsplit = base.split('/')
        for i in range(len(bsplit)):
            newbase = '/'.join(bsplit[:-i])
            if exists(newbase + '/.redo'):
                base = newbase
                break
        environ['REDO_BASE'] = base
        environ['REDO_STARTDIR'] = cwd

        import state
        state.init()
