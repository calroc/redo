import sys, os, errno, glob, stat, fcntl, sqlite3
import vars as vars_
from helpers import unlink, close_on_exec, join, try_stat, possible_do_files
from log import log, warn, err, debug, debug2, debug3

SCHEMA_VER=1
TIMEOUT=60

ALWAYS='//ALWAYS'   # an invalid filename that is always marked as dirty
STAMP_DIR='dir'     # the stamp of a directory; mtime is unhelpful
STAMP_MISSING='0'   # the stamp of a nonexistent file

CLEAN = 0
DIRTY = 1

def _connect(dbfile):
    _db = sqlite3.connect(dbfile, timeout=TIMEOUT)
    _db.execute("pragma synchronous = off")
    _db.execute("pragma journal_mode = PERSIST")
    _db.text_factory = str
    return _db


_db = None
def db():
    global _db
    if _db:
        return _db
        
    dbdir = '%s/.redo' % vars_.BASE
    dbfile = '%s/db.sqlite3' % dbdir
    try:
        os.mkdir(dbdir)
    except OSError, e:
        if e.errno == errno.EEXIST:
            pass  # if it exists, that's okay
        else:
            raise

    must_create = not os.path.exists(dbfile)
    if not must_create:
        _db = _connect(dbfile)
        try:
            row = _db.cursor().execute("select version from Schema").fetchone()
        except sqlite3.OperationalError:
            row = None
        ver = row and row[0] or None
        if ver != SCHEMA_VER:
            err("state database: discarding v%s (wanted v%s)\n"
                % (ver, SCHEMA_VER))
            must_create = True
            _db = None
    if must_create:
        unlink(dbfile)
        _db = _connect(dbfile)
        _db.execute("create table Schema "
                    "    (version int)")
        _db.execute("create table Runid "
                    "    (id integer primary key autoincrement)")
        _db.execute("create table Files "
                    "    (name not null primary key, "
                    "     is_generated int, "
                    "     is_override int, "
                    "     checked_runid int, "
                    "     changed_runid int, "
                    "     failed_runid int, "
                    "     stamp, "
                    "     csum)")
        _db.execute("create table Deps "
                    "    (target int, "
                    "     source int, "
                    "     mode not null, "
                    "     delete_me int, "
                    "     primary key (target,source))")
        _db.execute("insert into Schema (version) values (?)", [SCHEMA_VER])
        # eat the '0' runid and File id
        _db.execute("insert into Runid values "
                    "     ((select max(id)+1 from Runid))")
        _db.execute("insert into Files (name) values (?)", [ALWAYS])

    if not vars_.RUNID:
        _db.execute("insert into Runid values "
                    "     ((select max(id)+1 from Runid))")
        vars_.RUNID = _db.execute("select last_insert_rowid()").fetchone()[0]
        os.environ['REDO_RUNID'] = str(vars_.RUNID)
    
    _db.commit()
    return _db
    

def init():
    db()


_wrote = 0
def _write(q, l):
    if _insane:
        return
    global _wrote
    _wrote += 1
    db().execute(q, l)


def commit():
    if _insane:
        return
    global _wrote
    if _wrote:
        db().commit()
        _wrote = 0


_insane = None
def check_sane():
    global _insane, _writable
    if not _insane:
        _insane = not os.path.exists('%s/.redo' % vars_.BASE)
    return not _insane


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


def warn_override(name):
    warn('%s - you modified it; skipping\n' % name)


_file_cols = ['rowid', 'name', 'is_generated', 'is_override',
              'checked_runid', 'changed_runid', 'failed_runid',
              'stamp', 'csum']
class File(object):
    # use this mostly to avoid accidentally assigning to typos
    __slots__ = ['id', 't'] + _file_cols[1:]

    def _init_from_idname(self, id, name):
        q = ('select %s from Files ' % join(', ', _file_cols))
        if id != None:
            q += 'where rowid=?'
            l = [id]
        elif name != None:
            name = (name==ALWAYS) and ALWAYS or relpath(name, vars_.BASE)
            q += 'where name=?'
            l = [name]
        else:
            raise Exception('name or id must be set')
        d = db()
##        log("File query(%r) %r", q, l)
        row = d.execute(q, l).fetchone()
        if not row:
            if not name:
                raise Exception('File with id=%r not found and '
                                'name not given' % id)
            try:
                _write('insert into Files (name) values (?)', [name])
            except sqlite3.IntegrityError:
                # some parallel redo probably added it at the same time; no
                # big deal.
                pass
            row = d.execute(q, l).fetchone()
            assert row
        return self._init_from_cols(row)

    def _init_from_cols(self, cols):
        (self.id, self.name, self.is_generated, self.is_override,
         self.checked_runid, self.changed_runid, self.failed_runid,
         self.stamp, self.csum) = cols
        if self.name == ALWAYS and self.changed_runid < vars_.RUNID:
            self.changed_runid = vars_.RUNID
    
    def __init__(self, id=None, name=None, cols=None):
        if cols:
            self._init_from_cols(cols)
        else:
            self._init_from_idname(id, name)
            self.t = name or self.name

    def refresh(self):
        self._init_from_idname(self.id, None)

    def save(self):
        cols = join(', ', ['%s=?'%i for i in _file_cols[2:]])
        _write('update Files set '
               '    %s '
               '    where rowid=?' % cols,
               [self.is_generated, self.is_override,
                self.checked_runid, self.changed_runid, self.failed_runid,
                self.stamp, self.csum,
                self.id])

    def set_checked(self):
        self.checked_runid = vars_.RUNID

    def set_checked_save(self):
        self.set_checked()
        self.save()

    def set_changed(self):
        debug2('BUILT: %r (%r)\n' % (self.name, self.stamp))
        self.changed_runid = vars_.RUNID
        self.failed_runid = None
        self.is_override = False

    def set_failed(self):
        debug2('FAILED: %r\n' % self.name)
        self.update_stamp()
        self.failed_runid = vars_.RUNID
        self.is_generated = True
        self.zap_deps2()
        self.save()

    def set_static(self):
        self.update_stamp(must_exist=True)
        self.is_override = False
        self.is_generated = False

    def set_override(self):
        self.update_stamp()
        self.is_override = True

    def update_stamp(self, must_exist=False):
        newstamp = self.read_stamp()
        if must_exist and newstamp == STAMP_MISSING:
            raise Exception("%r does not exist" % self.name)
        if newstamp != self.stamp:
            debug2("STAMP: %s: %r -> %r\n" % (self.name, self.stamp, newstamp))
            self.stamp = newstamp
            self.set_changed()

    def is_checked(self):
        return self.checked_runid and self.checked_runid >= vars_.RUNID

    def is_changed(self):
        return self.changed_runid and self.changed_runid >= vars_.RUNID

    def is_failed(self):
        return self.failed_runid and self.failed_runid >= vars_.RUNID

    def deps(self):
        q = ('select Deps.mode, Deps.source, %s '
             '  from Files '
             '    join Deps on Files.rowid = Deps.source '
             '  where target=?' % join(', ', _file_cols[1:]))
        for row in db().execute(q, [self.id]).fetchall():
            mode = row[0]
            cols = row[1:]
            assert mode in ('c', 'm')
            yield mode,File(cols=cols)

    def zap_deps1(self):
        debug2('zap-deps1: %r\n' % self.name)
        _write('update Deps set delete_me=? where target=?', [True, self.id])

    def zap_deps2(self):
        debug2('zap-deps2: %r\n' % self.name)
        _write('delete from Deps where target=? and delete_me=1', [self.id])

    def add_dep(self, mode, dep):
        src = File(name=dep)
        debug3('add-dep: "%s" < %s "%s"\n' % (self.name, mode, src.name))
        assert self.id != src.id
        _write("insert or replace into Deps "
               "    (target, mode, source, delete_me) values (?,?,?,?)",
               [self.id, mode, src.id, False])

    def read_stamp(self):
        try:
            st = os.stat(os.path.join(vars_.BASE, self.name))
        except OSError:
            return STAMP_MISSING
        if stat.S_ISDIR(st.st_mode):
            return STAMP_DIR
        else:
            # a "unique identifier" stamp for a regular file
            return str((st.st_ctime, st.st_mtime, st.st_size, st.st_ino))

    def nicename(self):
        return relpath(os.path.join(vars_.BASE, self.name), vars_.STARTDIR)

    def get_tempfilenames(self):
        tmpbase = self.t
        while not os.path.isdir(os.path.dirname(tmpbase) or '.'):
            ofs = tmpbase.rfind('/')
            assert ofs >= 0
            tmpbase = tmpbase[:ofs] + '__' + tmpbase[ofs + 1:]
        return ('%s.redo1.tmp' % tmpbase), ('%s.redo2.tmp' % tmpbase)

    def try_stat(self):
        return try_stat(self.t)

    def check_externally_modified(self):
        newstamp = self.read_stamp()
        return (self.is_generated and
                newstamp != STAMP_MISSING and
                (self.stamp != newstamp or self.is_override))

    def set_externally_modified(self):
        self.set_override()
        self.set_checked()
        self.save()

    def existing_not_generated(self):
        return (os.path.exists(self.t) and
                not os.path.isdir(self.t + '/.') and
                not self.is_generated)

    def set_something_else(self):
        self.set_static()
        self.save()

    def find_do_file(self):
        for dodir, dofile, basedir, basename, ext in possible_do_files(self.name, vars_.BASE):
            dopath = os.path.join(dodir, dofile)
            debug2('%s: %s:%s ?\n' % (self.name, dodir, dofile))
            if os.path.exists(dopath):
                self.add_dep('m', dopath)
                return dodir, dofile, basedir, basename, ext
            self.add_dep('c', dopath)
        return None, None, None, None, None

    def is_dirty(self, max_changed, depth='',
                 is_checked=None, set_checked=None):
        is_checked = is_checked or File.is_checked
        set_checked = set_checked or File.set_checked_save
        if vars_.DEBUG >= 1:
            debug('%s?%s\n' % (depth, self.nicename()))

        if self.failed_runid:
            debug('%s-- DIRTY (failed last time)\n' % depth)
            return DIRTY
        if self.changed_runid is None:
            debug('%s-- DIRTY (never built)\n' % depth)
            return DIRTY
        if self.changed_runid > max_changed:
            debug('%s-- DIRTY (built)\n' % depth)
            return DIRTY  # has been built more recently than parent
        if is_checked(self):
            if vars_.DEBUG >= 1:
                debug('%s-- CLEAN (checked)\n' % depth)
            return CLEAN  # has already been checked during this session
        if not self.stamp:
            debug('%s-- DIRTY (no stamp)\n' % depth)
            return DIRTY

        newstamp = self.read_stamp()
        if self.stamp != newstamp:
            if newstamp == STAMP_MISSING:
                debug('%s-- DIRTY (missing)\n' % depth)
            else:
                debug('%s-- DIRTY (mtime)\n' % depth)
            if self.csum:
                return [self]
            else:
                return DIRTY

        must_build = []
        for mode, f2 in self.deps():
            assert mode in ('c', 'm')
            dirty = CLEAN
            if mode == 'c':
                if os.path.exists(os.path.join(vars_.BASE, f2.name)):
                    debug('%s-- DIRTY (created)\n' % depth)
                    dirty = DIRTY
            elif mode == 'm':
                sub = f2.is_dirty(max(self.changed_runid, self.checked_runid),
                                 depth=depth + '  ',
                                 is_checked=is_checked, set_checked=set_checked)
                if sub:
                    debug('%s-- DIRTY (sub)\n' % depth)
                    dirty = sub

            if not self.csum:
                # self is a "normal" target:
                # dirty f2 means self is instantly dirty
                if dirty:
                    # if dirty==DIRTY, this means self is definitely dirty.
                    # if dirty==[...], it's a list of the uncertain children.
                    return dirty
            else:
                # self is "checksummable": dirty f2 means self needs to redo,
                # but self might turn out to be clean after that (ie. our
                # parent might not be dirty).
                if dirty == DIRTY:
                    # f2 is definitely dirty, so self definitely needs to
                    # redo.  However, after that, self might turn out to be
                    # unchanged.
                    return [self]

                # our child f2 might be dirty, but it's not sure yet.  It's
                # given us a list of targets we have to redo in order to
                # be sure.
                assert isinstance(dirty, list), repr(dirty)
                must_build.extend(dirty)

        if must_build:
            # self is *maybe* dirty because at least one of its children is
            # maybe dirty.  must_build has accumulated a list of "topmost"
            # uncertain objects in the tree.  If we build all those, we can then
            # redo-ifchange self and it won't have any uncertainty next time.
            return must_build

        # if we get here, it's because the target is clean
        if self.is_override:
            warn_override(self.name)
        set_checked(self)
        return CLEAN

    def fin(self):
        self.refresh()
        self.is_generated = True
        self.is_override = False
        if self.is_checked() or self.is_changed():
            # it got checked during the run; someone ran redo-stamp.
            # update_stamp would call set_changed(); we don't want that
            self.stamp = self.read_stamp()
        else:
            self.csum = None
            self.update_stamp()
            self.set_changed()
        self.zap_deps2()
        self.save()


def files():
    q = ('select %s from Files order by name' % join(', ', _file_cols))
    for cols in db().execute(q).fetchall():
        yield File(cols=cols)


# FIXME: I really want to use fcntl F_SETLK, F_SETLKW, etc here.  But python
# doesn't do the lockdata structure in a portable way, so we have to use
# fcntl.lockf() instead.  Usually this is just a wrapper for fcntl, so it's
# ok, but it doesn't have F_GETLK, so we can't report which pid owns the lock.
# The makes debugging a bit harder.  When we someday port to C, we can do that.
_locks = {}
class Lock:
    def __init__(self, fid):
        self.owned = False
        self.fid = fid
        self.lockfile = os.open(os.path.join(vars_.BASE, '.redo/lock.%d' % fid),
                                os.O_RDWR | os.O_CREAT, 0666)
        close_on_exec(self.lockfile, True)
        assert _locks.get(fid, 0) == 0
        _locks[fid] = 1

    def __del__(self):
        _locks[self.fid] = 0
        if self.owned:
            self.unlock()
        os.close(self.lockfile)

    def trylock(self):
        assert not self.owned
        try:
            fcntl.lockf(self.lockfile, fcntl.LOCK_EX|fcntl.LOCK_NB, 0, 0)
        except IOError, e:
            if e.errno in (errno.EAGAIN, errno.EACCES):
                pass  # someone else has it locked
            else:
                raise
        else:
            self.owned = True

    def waitlock(self):
        assert not self.owned
        fcntl.lockf(self.lockfile, fcntl.LOCK_EX, 0, 0)
        self.owned = True
            
    def unlock(self):
        if not self.owned:
            raise Exception("can't unlock %r - we don't own it" 
                            % self.lockname)
        fcntl.lockf(self.lockfile, fcntl.LOCK_UN, 0, 0)
        self.owned = False
