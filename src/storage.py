# Persistence primitives. No Qt, Nuke, network, or background work.
import errno
import tempfile


def read_json(path, default=None, limit=1048576):
    try:
        with open(path, 'rb') as handle:
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            return default
        value = json.loads(raw.decode('utf-8'))
        return value if isinstance(value, dict) else default
    except (IOError, OSError, ValueError, UnicodeError):
        return default


def ensure_directory(path):
    try:
        os.makedirs(path, 0o700)
    except OSError as exc:
        if exc.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def replace_file(source, target):
    """Never unlink the existing target; failure preserves the previous file."""
    if hasattr(os, 'replace'):
        os.replace(source, target)
    elif os.name == 'nt':
        # Python 2.7 Windows: os.rename cannot replace an existing destination.
        import ctypes
        from ctypes import wintypes
        move = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
        move.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
        move.restype = wintypes.BOOL
        def wide(path):
            if isinstance(path, bytes):
                return path.decode(__import__('sys').getfilesystemencoding())
            return path
        if not move(wide(source), wide(target), 0x1 | 0x8):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.rename(source, target)


def atomic_json(path, value, replace=None):
    """Unique same-directory temp, complete/flush/fsync/close, then replace."""
    folder = os.path.dirname(os.path.abspath(path))
    ensure_directory(folder)
    descriptor, temp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.',
                                        suffix='.tmp', dir=folder)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False)
            handle.write((raw + '\n').encode('utf-8'))
            handle.flush()
            os.fsync(handle.fileno())
        (replace or replace_file)(temp, path)
    finally:
        if os.path.exists(temp):
            os.remove(temp)


class FileLock(object):
    """Nonblocking OS lock; a busy store fails safely rather than waiting in UI."""
    def __init__(self, path):
        self.path = path + '.lockfile'
        self.handle = None

    def __enter__(self):
        ensure_directory(os.path.dirname(os.path.abspath(self.path)))
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        self.handle = os.fdopen(fd, 'r+b')
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    self.handle.write(b'0')
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self
        except Exception:
            self.handle.close()
            raise

    def __exit__(self, *args):
        self.handle.close()


class JsonStore(object):
    def __init__(self, path):
        self.path = path
        self.last_error = ''

    def read(self):
        return read_json(self.path, {})

    def update(self, change):
        try:
            with FileLock(self.path):
                value = change(self.read())
                atomic_json(self.path, value)
            self.last_error = ''
            return value
        except Exception:
            self.last_error = 'Settings could not be saved. The previous file was preserved.'
            return None


def nonnegative_int(value, default=0):
    try:
        return max(0, int(value))
    except (ValueError, TypeError, OverflowError):
        return default


class LegacyScoreStore(JsonStore):
    def best(self):
        return nonnegative_int(self.read().get('best_score', 0))

    def save_best(self, score):
        def merge(current):
            current['best_score'] = max(nonnegative_int(current.get('best_score')),
                                        nonnegative_int(score))
            return current
        result = self.update(merge)
        return result is not None
