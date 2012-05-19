import sys, os, errno, fcntl


def atoi(v):
    try:
        return int(v or 0)
    except ValueError:
        return 0


def join(between, l):
    return between.join(l)


def unlink(f):
    """Delete a file at path 'f' if it currently exists.

    Unlike os.unlink(), does not throw an exception if the file didn't already
    exist or if it is actually a directory.
    """
    try:
        os.unlink(f)
    except OSError, e:
        if e.errno not in (errno.ENOENT, errno.EISDIR):
            raise
        # else: it doesn't exist, that's what you asked for


def unique(N, in_order=False):
    if in_order:
        N = list(N)
        return sorted(set(N), key=N.index)
    return list(set(N))


def close_on_exec(fd, yes):
    fl = fcntl.fcntl(fd, fcntl.F_GETFD)
    fl &= ~fcntl.FD_CLOEXEC
    if yes:
        fl |= fcntl.FD_CLOEXEC
    fcntl.fcntl(fd, fcntl.F_SETFD, fl)


def try_stat(filename):
    try:
        return os.stat(filename)
    except OSError, e:
        if e.errno == errno.ENOENT:
            return None
        else:
            raise


def possible_do_files(t, base):
    dirname,filename = os.path.split(t)
    yield (os.path.join(base, dirname), "%s.do" % filename,
           '', filename, '')

    # It's important to try every possibility in a directory before resorting
    # to a parent directory.  Think about nested projects: I don't want
    # ../../default.o.do to take precedence over ../default.do, because
    # the former one might just be an artifact of someone embedding my project
    # into theirs as a subdir.  When they do, my rules should still be used
    # for building my project in *all* cases.
    t = os.path.normpath(os.path.join(base, t))
    dirname, filename = os.path.split(t)
    dirbits = dirname.split('/')
    for i in range(len(dirbits), -1, -1):
        basedir = join('/', dirbits[:i])
        subdir = join('/', dirbits[i:])
        for dofile, basename, ext in default_do_files(filename):
            yield (basedir, dofile,
                   subdir, os.path.join(subdir, basename), ext)


def default_do_files(filename):
    l = filename.split('.')
    for i in range(1, len(l)+1):
        basename = join('.', l[:i])
        ext = join('.', l[i:])
        if ext:
            ext = '.' + ext
        yield ("default%s.do" % ext), basename, ext


_cwd = None
def relpath(t, base):
    global _cwd
    if not _cwd:
        _cwd = os.getcwd()
    t = os.path.normpath(os.path.join(_cwd, t))
    base = os.path.normpath(base)
    tparts = t.split('/')
    bparts = base.split('/')
    for tp, bp in zip(tparts, bparts):
        if tp != bp:
            break
        tparts.pop(0)
        bparts.pop(0)
    tparts = ['..'] * len(bparts) + tparts
    return tparts and os.path.join(*tparts) or ''

