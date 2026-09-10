# -*- coding: utf-8 -*-
"""
NUKERIS v1.1.0
A small, isolated compositing-themed tetromino game for Foundry Nuke 12+.

Safety design:
- Does not read or modify the current .nk script.
- Does not create/select/change nodes, viewers, frames, knobs, or undo state.
- No Nuke callbacks, no threads, no global event filters, no global shortcuts.
- Uses Qt ShortcutOverride only on this focused widget so Nuke single-key actions do not fire while playing.
- Writes only nukeris_settings.json next to this script to persist the best score.
- The game timer stops while paused or hidden.
- Keyboard input is handled only while this widget owns focus.

Install:
1. Copy nukeris.py directly into your .nuke folder.
   Windows: C:/Users/<USERNAME>/.nuke/nukeris.py
   Linux:   ~/.nuke/nukeris.py
2. Add this line to your existing menu.py:
       import nukeris
3. Restart Nuke, then open Pane > NUKERIS.

No init.py edit is required.

Compatibility:
- Nuke 12.x: Python 2.7 + PySide2
- Nuke 13.x-15.x: Python 3 + PySide2
- Nuke 16.x-17.x: Python 3 + PySide6
"""

from __future__ import division, print_function, unicode_literals

import json
import math
import os
import random
import time
import traceback
from collections import deque

# Python 2.7 has no time.monotonic(). Wall-clock fallback is sufficient because
# every frame delta is clamped and timer state is reset on pause/resume.
_monotonic = getattr(time, "monotonic", time.time)


__version__ = "1.1.0"
PANEL_TITLE = "NUKERIS"
PANEL_ID = "com.mori.nukeris.panel"

BOARD_W = 10
BOARD_H = 20
NEXT_COUNT = 5
CLEAR_FX_SECONDS = 0.28

SETTINGS_FILENAME = "nukeris_settings.json"


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


def _settings_path():
    """Return the settings file beside this Python module."""
    try:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS_FILENAME)
    except Exception:
        return None


def _load_best_score():
    return LegacyScoreStore(_settings_path()).best()


def _save_best_score(best_score):
    return LegacyScoreStore(_settings_path()).save_best(best_score)


# Representative Nuke node-class colors. These are intentionally close to the
# familiar Node Graph palette rather than conventional Tetris colors.
NODE_STYLES = {
    "I": {"label": "Read",      "color": "#A9ADB0"},
    "O": {"label": "Merge",     "color": "#5366B3"},
    "T": {"label": "Transform", "color": "#9B6B99"},
    "S": {"label": "Roto",      "color": "#67A45F"},
    "Z": {"label": "Grade",     "color": "#8DA0BB"},
    "J": {"label": "Blur",      "color": "#C17A3F"},
    "L": {"label": "Write",     "color": "#C3CE12"},
}

# The reference Node Graph screenshots sit at roughly #323232. Keep the playfield
# on that graph color while the surrounding tool chrome still follows Nuke's Qt palette.
NUKE_GRAPH_BG = "#323232"
NUKE_WIRE = "#111111"

# SRS-compatible piece states in a 4x4 local grid.
PIECE_CELLS = {
    "I": (
        ((0, 1), (1, 1), (2, 1), (3, 1)),
        ((2, 0), (2, 1), (2, 2), (2, 3)),
        ((0, 2), (1, 2), (2, 2), (3, 2)),
        ((1, 0), (1, 1), (1, 2), (1, 3)),
    ),
    "O": (
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
    ),
    "T": (
        ((1, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (1, 2)),
        ((1, 0), (0, 1), (1, 1), (1, 2)),
    ),
    "S": (
        ((1, 0), (2, 0), (0, 1), (1, 1)),
        ((1, 0), (1, 1), (2, 1), (2, 2)),
        ((1, 1), (2, 1), (0, 2), (1, 2)),
        ((0, 0), (0, 1), (1, 1), (1, 2)),
    ),
    "Z": (
        ((0, 0), (1, 0), (1, 1), (2, 1)),
        ((2, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (1, 2), (2, 2)),
        ((1, 0), (0, 1), (1, 1), (0, 2)),
    ),
    "J": (
        ((0, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (2, 2)),
        ((1, 0), (1, 1), (0, 2), (1, 2)),
    ),
    "L": (
        ((2, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (1, 2), (2, 2)),
        ((0, 1), (1, 1), (2, 1), (0, 2)),
        ((0, 0), (1, 0), (1, 1), (1, 2)),
    ),
}

# SRS kick data converted to a screen coordinate system where +Y is downward.
JLSTZ_KICKS = {
    (0, 1): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (1, 0): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    (1, 2): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    (2, 1): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (2, 3): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (3, 2): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (3, 0): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (0, 3): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
}

I_KICKS = {
    (0, 1): ((0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)),
    (1, 0): ((0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)),
    (1, 2): ((0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)),
    (2, 1): ((0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)),
    (2, 3): ((0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)),
    (3, 2): ((0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)),
    (3, 0): ((0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)),
    (0, 3): ((0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)),
}


class Tetromino(object):
    def __init__(self, kind, x=3, y=-1, rotation=0):
        self.kind = kind
        self.x = x
        self.y = y
        self.rotation = rotation

    def cells(self, x=None, y=None, rotation=None):
        px = self.x if x is None else x
        py = self.y if y is None else y
        pr = self.rotation if rotation is None else rotation % 4
        return [(px + cx, py + cy) for cx, cy in PIECE_CELLS[self.kind][pr]]


class PlacedCell(object):
    __slots__ = ("kind", "group_id")

    def __init__(self, kind, group_id):
        self.kind = kind
        self.group_id = group_id


class GameEngine(object):
    """Pure-Python game state. Intentionally has no Nuke or Qt dependency."""

    def __init__(self, storage=None, seed=None) :
        self.storage = storage if storage is not None else LegacyScoreStore(_settings_path())
        self.seed = seed
        self.rng = random.Random(seed)
        self.best_score = self.storage.best()
        self.reset()

    def _update_best_score(self) :
        if self.score > self.best_score:
            self.best_score = self.score
            self.storage.save_best(self.best_score)
            self.best_score = max(self.best_score, self.storage.best())

    def reset(self) :
        self.board = [
            [None for _ in range(BOARD_W)] for _ in range(BOARD_H)
        ]
        self.queue = deque()
        self.active = None
        self.hold_kind = None
        self.hold_used = False
        self.score = 0
        self.lines = 0
        self.level = 1
        self.combo = -1
        self.game_over = False
        self.last_clear = 0
        self.last_clear_rows = []
        self.clear_event_id = 0
        self._next_group_id = 1
        self.pieces_locked = 0
        self._fill_queue()
        self._spawn()

    @property
    def fall_interval_ms(self) :
        return max(70, int(760 * (0.82 ** (self.level - 1))))

    def _fill_queue(self) :
        while len(self.queue) < 14:
            bag = sorted(PIECE_CELLS.keys())
            self.rng.shuffle(bag)
            self.queue.extend(bag)

    def next_pieces(self, count = NEXT_COUNT) :
        self._fill_queue()
        return list(self.queue)[:count]

    def _spawn(self, forced_kind = None) :
        if forced_kind is None:
            self._fill_queue()
            kind = self.queue.popleft()
            self._fill_queue()
        else:
            kind = forced_kind

        self.active = Tetromino(kind=kind, x=3, y=-1, rotation=0)
        self.hold_used = False
        if not self._valid(self.active.cells()):
            self.game_over = True
            self._update_best_score()

    def _valid(self, cells) :
        for x, y in cells:
            if x < 0 or x >= BOARD_W or y >= BOARD_H:
                return False
            if y >= 0 and self.board[y][x] is not None:
                return False
        return True

    def move(self, dx, dy) :
        if self.game_over or self.active is None:
            return False
        nx = self.active.x + dx
        ny = self.active.y + dy
        if self._valid(self.active.cells(x=nx, y=ny)):
            self.active.x = nx
            self.active.y = ny
            return True
        return False

    def rotate(self, direction) :
        if self.game_over or self.active is None:
            return False
        piece = self.active
        if piece.kind == "O":
            return True

        old_r = piece.rotation
        new_r = (old_r + direction) % 4
        kicks = I_KICKS if piece.kind == "I" else JLSTZ_KICKS
        tests = kicks.get((old_r, new_r), ((0, 0),))
        for dx, dy in tests:
            if self._valid(piece.cells(x=piece.x + dx, y=piece.y + dy, rotation=new_r)):
                piece.x += dx
                piece.y += dy
                piece.rotation = new_r
                return True
        return False

    def soft_drop(self) :
        if self.move(0, 1):
            self.score += 1
            return True
        self.lock_piece()
        return False

    def gravity_step(self) :
        if not self.move(0, 1):
            self.lock_piece()

    def hard_drop(self) :
        if self.game_over or self.active is None:
            return 0
        distance = 0
        while self.move(0, 1):
            distance += 1
        self.score += distance * 2
        self.lock_piece()
        return distance

    def ghost_y(self) :
        if self.active is None:
            return None
        gy = self.active.y
        while self._valid(self.active.cells(y=gy + 1)):
            gy += 1
        return gy

    def hold(self) :
        if self.game_over or self.active is None or self.hold_used:
            return False

        current = self.active.kind
        if self.hold_kind is None:
            self.hold_kind = current
            self._spawn()
        else:
            swap = self.hold_kind
            self.hold_kind = current
            self._spawn(forced_kind=swap)
        self.hold_used = True
        return True

    def lock_piece(self) :
        if self.game_over or self.active is None:
            return

        cells = self.active.cells()
        if any(y < 0 for _, y in cells):
            self.game_over = True
            self._update_best_score()
            return

        group_id = self._next_group_id
        self._next_group_id += 1
        for x, y in cells:
            self.board[y][x] = PlacedCell(self.active.kind, group_id)

        self.pieces_locked += 1
        cleared = self._clear_lines()
        self.last_clear = cleared
        self._score_clear(cleared)
        self._update_best_score()
        self._spawn()

    def _clear_lines(self) :
        full_rows = [i for i, row in enumerate(self.board) if all(cell is not None for cell in row)]
        self.last_clear_rows = full_rows
        cleared = len(full_rows)

        if cleared:
            full_set = set(full_rows)
            remaining = [row for i, row in enumerate(self.board) if i not in full_set]
            for _ in range(cleared):
                remaining.insert(0, [None for _ in range(BOARD_W)])
            self.board = remaining
            self.clear_event_id += 1

        self.lines += cleared
        self.level = 1 + self.lines // 10
        return cleared

    def _score_clear(self, cleared) :
        table = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}
        if cleared > 0:
            self.combo += 1
            self.score += table.get(cleared, 0) * self.level
            if self.combo > 0:
                self.score += 50 * self.combo * self.level
        else:
            self.combo = -1

# Pure geometry shared by rendering and regression tests.
def wire_endpoints(source, target, cell, origin=(0, 0)):
    dx, dy = target[0] - source[0], target[1] - source[1]
    if abs(dx) + abs(dy) != 1:
        return None
    sx = origin[0] + (source[0] + 0.5) * cell
    sy = origin[1] + (source[1] + 0.5) * cell
    tx = origin[0] + (target[0] + 0.5) * cell
    ty = origin[1] + (target[1] + 0.5) * cell
    half_w, half_h = max(7.0, cell * .78) / 2, max(5.0, cell * .46) / 2
    return ((sx + dx * half_w, sy + dy * half_h),
            (tx - dx * half_w, ty - dy * half_h))


def panel_layout(width, height):
    margin = 12.0
    compact = width < 650
    side = 0.0 if compact else 132.0
    gutter = 12.0 if side else 0.0
    top = 166.0 if compact else 94.0
    cell = max(7.0, math.floor(min((width - 2*margin - 2*side - 2*gutter)/BOARD_W,
                                   (height - top - 204.0)/BOARD_H)))
    bw, bh = cell*BOARD_W, cell*BOARD_H
    return dict(margin=margin, compact=compact, side=side, gutter=gutter, cell=cell,
                board=((width-bw)/2, top, bw, bh))

NORMAL = 'normal'
SCORE_ATTACK = 'score_attack_120'
SPRINT = 'sprint_40'
RULESET = 'ruleset_1'
MODES = (NORMAL, SCORE_ATTACK, SPRINT)
MODE_LABELS = ('NORMAL', 'SCORE ATTACK - 2:00', '40 LINE SPRINT')


class MemoryScoreStore(object):
    def __init__(self):
        self.score = 0
    def best(self):
        return self.score
    def save_best(self, score):
        self.score = max(self.score, score)
        return True


class GameSession(object):
    """Competition time is derived from the clock, never from UI timer ticks."""
    def __init__(self, mode=NORMAL, storage=None, clock=None, seed=None):
        if mode not in MODES:
            raise ValueError('Unsupported mode')
        self.mode = mode
        self.clock = clock or _monotonic
        self.start_time = self.clock()
        self.latest_time = self.start_time
        self.active_ms = 0.0
        self.elapsed_ms = 0
        self.finished = False
        self.result = None
        self.engine = GameEngine(storage=storage if mode == NORMAL else MemoryScoreStore(), seed=seed)

    @property
    def ranked(self):
        return self.mode != NORMAL

    def advance(self, active_seconds=0):
        if self.finished:
            return
        self.latest_time = max(self.latest_time, self.clock())
        self.active_ms += max(0, active_seconds)*1000
        self.elapsed_ms = int(round((self.latest_time-self.start_time)*1000)) if self.ranked else int(self.active_ms)
        e = self.engine
        done = e.game_over or (self.mode == SCORE_ATTACK and self.elapsed_ms >= 120000) or (self.mode == SPRINT and e.lines >= 40)
        if done:
            self.finished = True
            if self.mode == SCORE_ATTACK:
                self.elapsed_ms = min(120000, self.elapsed_ms)
            if self.mode != SPRINT or e.lines >= 40:
                self.result = dict(mode=self.mode, ruleset=RULESET, version=__version__,
                                   score=e.score, time_ms=self.elapsed_ms, lines=e.lines,
                                   pieces=e.pieces_locked)

    def action(self, name, *args):
        self.advance()
        if self.finished:
            return False
        result = getattr(self.engine, name)(*args)
        self.advance()
        return result


def format_milliseconds(value):
    value = max(0, int(value))
    minutes, rest = divmod(value, 60000)
    seconds, milliseconds = divmod(rest, 1000)
    return '{0:02d}:{1:02d}.{2:03d}'.format(minutes, seconds, milliseconds)

import re
import uuid

def settings_defaults():
    return dict(schema=2, pbs={NORMAL: 0, SCORE_ATTACK: 0, SPRINT: None},
                ranked_pbs={}, grid=False, global_enabled=False, studio_enabled=False,
                studio_folder='', studio_player_id='', profile={}, player_id='', player_token='')


def user_settings_path():
    return os.path.join(os.path.expanduser('~'), '.nuke', 'NUKERIS', 'settings.json')


def validate_profile(profile):
    return (isinstance(profile, dict) and
            re.match(r'^[A-Za-z0-9_.-]{2,16}$', profile.get('nickname', '')) is not None and
            re.match(r'^[A-Z]{2}$', profile.get('country', '')) is not None and
            re.match(r'^[A-Z0-9 ._-]{1,32}$', profile.get('region', '')) is not None)


def valid_result(result, ranked_only=True):
    if not isinstance(result, dict):
        return False
    if result.get('mode') not in ((SCORE_ATTACK, SPRINT) if ranked_only else MODES):
        return False
    if result.get('ruleset') != RULESET or result.get('version') != __version__:
        return False
    for field, maximum in (('score', 100000000), ('time_ms', 86400000), ('lines', 10000), ('pieces', 25000)):
        value = result.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
            return False
    if result['lines'] > result['pieces'] * 4 or result['score'] > result['pieces'] * 50000:
        return False
    if result['mode'] == SCORE_ATTACK:
        return 0 < result['time_ms'] <= 120000 and result['pieces'] <= 2400
    if result['mode'] == SPRINT:
        return 1000 <= result['time_ms'] <= 86400000 and 40 <= result['lines'] <= 43 and result['pieces'] >= 10
    return True


def better_result(new, old):
    if old is None:
        return True
    return new['time_ms'] < old['time_ms'] if new['mode'] == SPRINT else new['score'] > old['score']


class SettingsStore(JsonStore):
    def __init__(self, path=None, legacy_path=None):
        JsonStore.__init__(self, path or user_settings_path())
        self.legacy_path = legacy_path or _settings_path()
        self.pending_results = {}
        self.pending_normal = 0
        self.migrate()

    def read(self):
        current = JsonStore.read(self)
        defaults = settings_defaults()
        if current.get('schema', 2) != 2:
            return defaults
        for key in defaults:
            if key in current and isinstance(current[key], type(defaults[key])):
                defaults[key] = current[key]
        # Python 2 JSON strings are unicode; accept strings without mixing bool/int.
        for key in ('studio_folder','studio_player_id','player_id','player_token'):
            if isinstance(current.get(key), type(u'')) or isinstance(current.get(key), str):
                defaults[key] = current[key]
        defaults['pbs'] = dict(settings_defaults()['pbs'], **defaults['pbs'])
        return defaults

    def update(self, change):
        def guarded(current):
            raw = read_json(self.path, {})
            if raw.get('schema', 2) != 2:
                raise ValueError('Newer settings schema')
            return change(current)
        return JsonStore.update(self, guarded)

    def migrate(self):
        legacy = read_json(self.legacy_path, {})
        value = nonnegative_int(legacy.get('best_score'))
        if value > self.best():
            self.save_best(value)

    def best(self):
        return max(self.pending_normal, nonnegative_int(self.read()['pbs'][NORMAL]))

    def save_best(self, score):
        self.pending_normal = max(self.pending_normal, nonnegative_int(score))
        def merge(current):
            current['pbs'][NORMAL] = max(nonnegative_int(current['pbs'].get(NORMAL)), self.pending_normal)
            return current
        return self.update(merge) is not None

    def save_preferences(self, preferences):
        allowed = ('grid','global_enabled','studio_enabled','studio_folder','profile',
                   'player_id','player_token','studio_player_id')
        def merge(current):
            for key in allowed:
                if key in preferences:
                    current[key] = preferences[key]
            return current
        return self.update(merge) is not None

    def record(self, result):
        if not valid_result(result):
            return False
        key = result['mode'] + '/' + result['ruleset']
        if better_result(result, self.pending_results.get(key)):
            self.pending_results[key] = dict(result)
        def merge(current):
            for k, pending in self.pending_results.items():
                old = current['ranked_pbs'].get(k)
                if not valid_result(old) or better_result(pending, old):
                    current['ranked_pbs'][k] = dict(pending)
                    current['pbs'][pending['mode']] = pending['time_ms'] if pending['mode'] == SPRINT else pending['score']
            return current
        return self.update(merge) is not None

    def personal(self):
        results = self.read()['ranked_pbs']
        for key, value in self.pending_results.items():
            if not valid_result(results.get(key)) or better_result(value, results[key]):
                results[key] = value
        return results

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    QT_BINDING = "PySide6"
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    QT_BINDING = "PySide2"


def _enum_value(root, group_name, value_name):
    """Return a scoped Qt6 enum or its legacy Qt5 equivalent."""
    group = getattr(root, group_name, None)
    if group is not None and hasattr(group, value_name):
        return getattr(group, value_name)
    return getattr(root, value_name)


class _QtCompat(object):
    pass


QC = _QtCompat()
# QtCore.Qt enums
QC.StrongFocus = _enum_value(QtCore.Qt, "FocusPolicy", "StrongFocus")
QC.NoFocus = _enum_value(QtCore.Qt, "FocusPolicy", "NoFocus")
QC.MouseFocusReason = _enum_value(QtCore.Qt, "FocusReason", "MouseFocusReason")
QC.PointingHandCursor = _enum_value(QtCore.Qt, "CursorShape", "PointingHandCursor")
QC.PreciseTimer = _enum_value(QtCore.Qt, "TimerType", "PreciseTimer")
QC.LeftButton = _enum_value(QtCore.Qt, "MouseButton", "LeftButton")
QC.ControlModifier = _enum_value(QtCore.Qt, "KeyboardModifier", "ControlModifier")
QC.AltModifier = _enum_value(QtCore.Qt, "KeyboardModifier", "AltModifier")
QC.MetaModifier = _enum_value(QtCore.Qt, "KeyboardModifier", "MetaModifier")
QC.NoPen = _enum_value(QtCore.Qt, "PenStyle", "NoPen")
QC.DashLine = _enum_value(QtCore.Qt, "PenStyle", "DashLine")
QC.DotLine = _enum_value(QtCore.Qt, "PenStyle", "DotLine")
QC.NoBrush = _enum_value(QtCore.Qt, "BrushStyle", "NoBrush")
QC.FlatCap = _enum_value(QtCore.Qt, "PenCapStyle", "FlatCap")
QC.AlignCenter = _enum_value(QtCore.Qt, "AlignmentFlag", "AlignCenter")
QC.AlignLeft = _enum_value(QtCore.Qt, "AlignmentFlag", "AlignLeft")
QC.AlignRight = _enum_value(QtCore.Qt, "AlignmentFlag", "AlignRight")
QC.AlignVCenter = _enum_value(QtCore.Qt, "AlignmentFlag", "AlignVCenter")
QC.ElideRight = _enum_value(QtCore.Qt, "TextElideMode", "ElideRight")
for _key_name in (
    "Key_A", "Key_C", "Key_D", "Key_Down", "Key_E", "Key_Enter",
    "Key_Escape", "Key_Left", "Key_Q", "Key_Return",
    "Key_Right", "Key_S", "Key_Space", "Key_Up", "Key_W"
):
    setattr(QC, _key_name, _enum_value(QtCore.Qt, "Key", _key_name))

# QEvent enums
QC.PaletteChange = _enum_value(QtCore.QEvent, "Type", "PaletteChange")
QC.ApplicationPaletteChange = _enum_value(QtCore.QEvent, "Type", "ApplicationPaletteChange")
QC.ShortcutOverride = _enum_value(QtCore.QEvent, "Type", "ShortcutOverride")

# QPalette roles
for _role in ("Window", "WindowText", "ButtonText", "Highlight", "Base", "Button", "Shadow", "Light"):
    setattr(QC, "Palette" + _role, _enum_value(QtGui.QPalette, "ColorRole", _role))

# QFont weights and QPainter render hint
QC.FontNormal = _enum_value(QtGui.QFont, "Weight", "Normal")
QC.FontMedium = _enum_value(QtGui.QFont, "Weight", "Medium")
QC.FontDemiBold = _enum_value(QtGui.QFont, "Weight", "DemiBold")
QC.Antialiasing = _enum_value(QtGui.QPainter, "RenderHint", "Antialiasing")


class NukerisPanel(QtWidgets.QWidget):
    """Dockable Qt game widget. No Nuke script access is performed here."""

    def __init__(self, parent=None) :
        QtWidgets.QWidget.__init__(self, parent)
        self.setObjectName("NukerisPanel")
        self.setFocusPolicy(QC.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(360, 600)

        self.settings = SettingsStore()
        self.preferences = self.settings.read()
        self.session = None
        self.engine = GameEngine(storage=self.settings)
        self.started = False
        self.paused = True
        self.input_active = False
        self.error_text = ""

        self._last_tick = _monotonic()
        self._fall_accum_ms = 0.0
        self._active_seconds = 0.0
        self._seen_clear_event = 0
        self._clear_fx_started = 0.0
        self._clear_fx_rows = []

        self._timer = QtCore.QTimer(self)
        self._timer.setTimerType(QC.PreciseTimer)
        self._timer.setInterval(33)  # ~30 fps maximum while playing.
        self._timer.timeout.connect(self._on_timer)

        self._new_game_button = QtWidgets.QPushButton("NEW GAME", self)
        self._new_game_button.setObjectName("NukerisNewGame")
        self._new_game_button.setFocusPolicy(QC.NoFocus)
        self._new_game_button.setCursor(QC.PointingHandCursor)
        self._new_game_button.clicked.connect(self._new_game_from_button)

        # Real UI option: unlike the decorative Properties-inspired chrome, this is
        # intentionally a genuine checkbox. It affects drawing only and never touches Nuke.
        self._grid_checkbox = QtWidgets.QCheckBox("Node Graph grid", self)
        self._grid_checkbox.setObjectName("NukerisNodeGraphGrid")
        self._grid_checkbox.setChecked(self.preferences['grid'])
        self._grid_checkbox.setFocusPolicy(QC.NoFocus)
        self._grid_checkbox.setCursor(QC.PointingHandCursor)
        self._grid_checkbox.setToolTip(
            "Show a Nuke-style dotted grid aligned exactly to the one-cell movement step."
        )
        self._grid_checkbox.toggled.connect(self._grid_changed)

        self._mode_combo = QtWidgets.QComboBox(self)
        self._mode_combo.addItems(MODE_LABELS)
        self._mode_combo.setFocusPolicy(QC.NoFocus)
        self._mode_combo.setToolTip('Select a mode, then start a new game.')
        self._ranking_button = QtWidgets.QPushButton('RANKING', self)
        self._ranking_button.setFocusPolicy(QC.NoFocus)
        self._ranking_button.clicked.connect(self._show_ranking)
        self._apply_button_style()

    # ---------- Palette / Nuke look ----------

    @staticmethod
    def _mix(a, b, t) :
        t = max(0.0, min(1.0, t))
        return QtGui.QColor(
            int(round(a.red() * (1.0 - t) + b.red() * t)),
            int(round(a.green() * (1.0 - t) + b.green() * t)),
            int(round(a.blue() * (1.0 - t) + b.blue() * t)),
            int(round(a.alpha() * (1.0 - t) + b.alpha() * t)),
        )

    def _theme(self) :
        pal = QtWidgets.QApplication.palette()
        window = pal.color(QC.PaletteWindow)
        text = pal.color(QC.PaletteWindowText)
        button_text = pal.color(QC.PaletteButtonText)
        highlight = pal.color(QC.PaletteHighlight)
        base = pal.color(QC.PaletteBase)
        button = pal.color(QC.PaletteButton)
        shadow = pal.color(QC.PaletteShadow)
        light = pal.color(QC.PaletteLight)

        graph = QtGui.QColor(NUKE_GRAPH_BG)
        # Follow Nuke's actual palette roles rather than inventing a separate game skin:
        # Window = panel background, Base = recessed/value areas, Button = real controls.
        panel = self._mix(window, QtGui.QColor("#303030"), 0.28)
        titlebar = self._mix(window, QtGui.QColor("#353535"), 0.30)
        raised = self._mix(button, QtGui.QColor("#424242"), 0.22)
        # Nuke's UI borders are dark, but not pure black. Keep them close to the
        # surrounding panel so recessed areas feel shallow rather than outlined.
        border = self._mix(window, QtGui.QColor("#000000"), 0.28)
        soft_border = self._mix(window, QtGui.QColor("#000000"), 0.18)
        section_line = self._mix(text, panel, 0.72)
        row_line = self._mix(text, panel, 0.90)

        return {
            "window": window,
            "panel": panel,
            "titlebar": titlebar,
            "base": base,
            "board": graph,
            "raised": raised,
            "text": text,
            "button_text": button_text,
            "muted": self._mix(text, graph, 0.42),
            "faint": self._mix(text, graph, 0.74),
            "border": border,
            "soft_border": soft_border,
            "section_line": section_line,
            "row_line": row_line,
            "shadow": shadow,
            "light": light,
            "grid": QtGui.QColor("#3A3A3A"),
            "highlight": highlight,
            "wire": QtGui.QColor(NUKE_WIRE),
        }

    def _apply_button_style(self) :
        t = self._theme()
        bg = t["raised"].name()
        hover = self._mix(t["raised"], t["text"], 0.08).name()
        pressed = self._mix(t["raised"], t["board"], 0.20).name()
        border = t["border"].name()
        text = t["button_text"].name()
        self._new_game_button.setStyleSheet(
            ("QPushButton#NukerisNewGame {{"
             "background:{0}; color:{1}; border:1px solid {2};"
             "border-radius:1px; padding:3px 10px; font-size:13px; font-weight:600;"
             "}}"
             "QPushButton#NukerisNewGame:hover {{ background:{3}; }}"
             "QPushButton#NukerisNewGame:pressed {{ background:{4}; }}").format(
                bg, text, border, hover, pressed
            )
        )
        # Keep Nuke's native checkbox indicator and only enlarge its label.
        if hasattr(self, "_grid_checkbox"):
            self._grid_checkbox.setStyleSheet(
                "QCheckBox#NukerisNodeGraphGrid { font-size:13px; spacing:7px; }"
            )

    def changeEvent(self, event) :
        if event.type() in (
            QC.PaletteChange,
            QC.ApplicationPaletteChange,
        ):
            self._apply_button_style()
        QtWidgets.QWidget.changeEvent(self, event)

    def resizeEvent(self, event) :
        w = float(self.width())
        layout = panel_layout(w, float(self.height()))
        margin = layout['margin']
        bx, by, board_w, board_h = layout['board']
        board_bottom = by + board_h

        # GAME follows the board instead of being pinned to the bottom of a tall pane.
        # This removes large dead zones while keeping all real widgets inside the viewport.
        game_y = board_bottom + (28.0 if layout["compact"] else 16.0)
        button_y = game_y + 21.0
        button_w = min(132.0, max(92.0, w - 2.0 * margin))
        button_x = margin
        self._new_game_button.setGeometry(
            int(round(button_x)), int(round(button_y)), int(round(button_w)), 28
        )

        checkbox_w = min(190.0, max(132.0, w - 2.0 * margin))
        self._grid_checkbox.setGeometry(
            int(round(margin)), int(round(button_y + 35.0)), int(round(checkbox_w)), 24
        )
        self._ranking_button.setGeometry(int(margin+button_w+8), int(button_y), 100, 28)
        self._mode_combo.setGeometry(12, 54, min(220, int(w)-140), 26)
        QtWidgets.QWidget.resizeEvent(self, event)

    # ---------- Lifecycle / safety ----------

    def _start_timer(self) :
        self._last_tick = _monotonic()
        if self.started and not self.paused and self.isVisible() and not self.engine.game_over:
            if not self._timer.isActive():
                self._timer.start()

    def _stop_timer(self) :
        if self._timer.isActive():
            self._timer.stop()
        self._last_tick = _monotonic()
        self._fall_accum_ms = 0.0

    def _set_paused(self, paused, release_input = False) :
        self.paused = paused
        if paused:
            self._stop_timer()
        else:
            self.input_active = self.hasFocus()
            self._start_timer()
        if release_input:
            self.input_active = False
        self.update()

    def _new_game(self) :
        mode = MODES[self._mode_combo.currentIndex()]
        self.session = GameSession(mode, storage=self.settings)
        self._result_recorded = False
        self.engine = self.session.engine
        self.started = True
        self.paused = False
        self.error_text = ""
        self._fall_accum_ms = 0.0
        self._active_seconds = 0.0
        self._seen_clear_event = self.engine.clear_event_id
        self._clear_fx_started = 0.0
        self._clear_fx_rows = []
        self.input_active = self.hasFocus()
        self._start_timer()
        self.update()

    def _new_game_from_button(self) :
        self.setFocus(QC.MouseFocusReason)
        self._new_game()

    def _fail_safe_pause(self, exc) :
        self.error_text = "{0}: {1}".format(type(exc).__name__, exc)
        self.paused = True
        self.input_active = False
        self._stop_timer()
        traceback.print_exc()
        self.update()

    def _capture_clear_fx(self) :
        if self.engine.clear_event_id != self._seen_clear_event:
            self._seen_clear_event = self.engine.clear_event_id
            self._clear_fx_rows = list(self.engine.last_clear_rows)
            self._clear_fx_started = _monotonic()

    def showEvent(self, event) :
        self._check_session()
        QtWidgets.QWidget.showEvent(self, event)
        self.update()

    def hideEvent(self, event) :
        if self.started and not self.engine.game_over:
            self.paused = True
        self.input_active = False
        self._stop_timer()
        QtWidgets.QWidget.hideEvent(self, event)

    def focusInEvent(self, event) :
        self._check_session()
        self.input_active = True
        QtWidgets.QWidget.focusInEvent(self, event)
        self.update()

    def focusOutEvent(self, event) :
        self.input_active = False
        if self.started and not self.engine.game_over:
            self.paused = True
        self._stop_timer()
        QtWidgets.QWidget.focusOutEvent(self, event)
        self.update()

    def mousePressEvent(self, event) :
        if event.button() == QC.LeftButton:
            self.setFocus(QC.MouseFocusReason)
            self.input_active = True
            if not self.started:
                self._new_game()
            elif self.paused and not self.engine.game_over and not self.error_text:
                self._set_paused(False)
            self.update()
            event.accept()
            return
        QtWidgets.QWidget.mousePressEvent(self, event)

    # ---------- Keyboard input ----------

    _GAME_KEYS = {
        QC.Key_A, QC.Key_D, QC.Key_S, QC.Key_W,
        QC.Key_Q, QC.Key_E, QC.Key_C,
        QC.Key_Space, QC.Key_Left,
        QC.Key_Right, QC.Key_Down, QC.Key_Up,
        QC.Key_Escape, QC.Key_Return, QC.Key_Enter,
    }

    def event(self, event) :
        # Nuke has single-key QAction shortcuts (S, D, etc.) that are resolved before
        # QWidget.keyPressEvent(). ShortcutOverride is Qt's local mechanism for a focused
        # widget to say "I own this key" without installing a global event filter or
        # disabling Nuke actions. Ctrl/Alt/Meta combinations are deliberately left to Nuke.
        if event.type() == QC.ShortcutOverride and self.hasFocus():
            key_event = event  # QShortcutOverride is delivered as QKeyEvent.
            blocked_mods = (
                QC.ControlModifier
                | QC.AltModifier
                | QC.MetaModifier
            )
            if not (key_event.modifiers() & blocked_mods) and key_event.key() in self._GAME_KEYS:
                key_event.accept()
                return True
        return QtWidgets.QWidget.event(self, event)

    def keyPressEvent(self, event) :
        try:
            if not self.hasFocus() or event.modifiers() & (QC.ControlModifier | QC.AltModifier | QC.MetaModifier):
                event.ignore()
                return
            key = event.key()

            if key == QC.Key_Escape:
                if self.started and not self.engine.game_over:
                    self._set_paused(True, release_input=True)
                self.clearFocus()
                event.accept()
                return

            if self.error_text:
                event.ignore()
                return

            if not self.started:
                if key in (QC.Key_Space, QC.Key_Return, QC.Key_Enter):
                    self._new_game()
                    event.accept()
                    return
                event.ignore()
                return

            if self.engine.game_over or (self.session and self.session.finished):
                if key in (
                    QC.Key_Space,
                    QC.Key_Return,
                    QC.Key_Enter,
                ):
                    self._new_game()
                    event.accept()
                    return
                event.ignore()
                return

            if self.paused:
                if key in (QC.Key_Space, QC.Key_Return, QC.Key_Enter):
                    self._set_paused(False)
                    event.accept()
                    return
                event.ignore()
                return

            if self._check_session():
                event.accept()
                return
            handled = True

            # WASD + Q/E layout. Arrow keys remain available as a fallback.
            if key in (QC.Key_A, QC.Key_Left):
                self.session.action('move', -1, 0)
            elif key in (QC.Key_D, QC.Key_Right):
                self.session.action('move', 1, 0)
            elif key in (QC.Key_S, QC.Key_Down):
                self.session.action('soft_drop')
                self._capture_clear_fx()
            elif key == QC.Key_Q:
                if not event.isAutoRepeat():
                    self.session.action('rotate', -1)
            elif key in (QC.Key_E, QC.Key_Up):
                if not event.isAutoRepeat():
                    self.session.action('rotate', 1)
            elif key == QC.Key_C:
                if not event.isAutoRepeat():
                    self.session.action('hold')
            elif key in (QC.Key_W, QC.Key_Space):
                if not event.isAutoRepeat():
                    self.session.action('hard_drop')
                    self._capture_clear_fx()
            else:
                handled = False

            if handled:
                self.update()
                event.accept()
            else:
                event.ignore()
        except Exception as exc:
            self._fail_safe_pause(exc)
            event.accept()

    # ---------- Game timer ----------

    def _grid_changed(self, checked):
        self.preferences['grid'] = bool(checked)
        self.settings.save_preferences({'grid': bool(checked)})
        self.update()

    def _record_result(self, result):
        if result and result['mode'] != NORMAL:
            self.settings.record(result)

    def _show_ranking(self):
        self._set_paused(True, release_input=True)
        values = self.settings.personal()
        lines = ['NORMAL BEST  {0:,}'.format(self.settings.best())]
        for mode, label in zip(MODES[1:], MODE_LABELS[1:]):
            r = values.get(mode + '/' + RULESET)
            value = 'NO RECORD' if r is None else (format_milliseconds(r['time_ms']) if mode == SPRINT else '{0:,}'.format(r['score']))
            lines.append(label + '  ' + value)
        QtWidgets.QMessageBox.information(self, 'PERSONAL RANKING', '\n\n'.join(lines))

    def _check_session(self):
        if self.session is None:
            return False
        self.session.advance()
        if self.session.finished:
            if not self._result_recorded:
                self._result_recorded = True
                self._record_result(self.session.result)
            self.paused = True
            self.input_active = False
            self._stop_timer()
            self.update()
            return True
        return False

    def _on_timer(self) :
        try:
            if self._check_session():
                return
            if self.paused or not self.started or self.engine.game_over or not self.isVisible():
                self._stop_timer()
                return

            now = _monotonic()
            dt = max(0.0, min(now - self._last_tick, 0.100))
            self._last_tick = now
            self.session.advance(dt)
            self._active_seconds = self.session.elapsed_ms / 1000.0
            self._fall_accum_ms += dt * 1000.0

            interval = self.engine.fall_interval_ms
            if self._fall_accum_ms >= interval:
                self._fall_accum_ms = 0.0
                self.session.action('gravity_step')
                self._capture_clear_fx()

            if self.engine.game_over or (self.session and self.session.finished):
                self.paused = True
                self.input_active = False
                self._stop_timer()

            self.update()
        except Exception as exc:
            self._fail_safe_pause(exc)

    # ---------- Painting ----------

    @staticmethod
    def _font(size, weight=QC.FontNormal) :
        app = QtWidgets.QApplication.instance()
        f = QtGui.QFont(app.font() if app is not None else QtGui.QFont())
        f.setPixelSize(max(8, int(size)))
        f.setWeight(weight)
        return f

    def paintEvent(self, event) :
        # Do not allow Python exceptions to escape a Qt paint callback inside Nuke.
        # A failed paint should disable the game UI safely, not destabilize the host.
        p = QtGui.QPainter(self)
        try:
            p.setRenderHint(QC.Antialiasing, True)
            t = self._theme()
            p.fillRect(self.rect(), t["window"])

            w = float(self.width())
            h = float(self.height())
            layout = panel_layout(w, h)
            margin, side, gutter, cell = (layout[k] for k in ('margin','side','gutter','cell'))
            board_rect = QtCore.QRectF(*layout['board'])

            self._draw_header(p, margin, w, t)
            self._draw_board(p, board_rect, cell, t)

            if side > 0:
                self._draw_side_panels(p, board_rect, side, gutter, t)
            else:
                self._draw_compact_previews(p, margin, w, board_rect, t)
                self._draw_compact_stats(p, margin, w, board_rect, t)

            self._draw_footer(p, margin, w, h, board_rect, t)
            self._draw_overlay(p, board_rect, t)
        except Exception as exc:
            self.error_text = "{0}: {1}".format(type(exc).__name__, exc)
            self.paused = True
            self.input_active = False
            self._stop_timer()
            traceback.print_exc()
        finally:
            if p.isActive():
                p.end()

    @staticmethod
    def _format_time(seconds) :
        total = max(0, int(seconds))
        mins, secs = divmod(total, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return "{0:02d}:{1:02d}:{2:02d}".format(hours, mins, secs)
        return "{0:02d}:{1:02d}".format(mins, secs)

    def _draw_header(self, p, margin, width,
                     t) :
        # Properties-style node-name field: shallow inset with a soft top-light vertical
        # gradient. No heavy left shadow; the lighting reads as coming from above.
        title_h = 48.0
        p.fillRect(QtCore.QRectF(0.0, 0.0, width, title_h), t["titlebar"])

        accent = self._mix(t["highlight"], t["text"], 0.10)
        p.setPen(QC.NoPen)
        p.setBrush(accent)
        p.drawRect(QtCore.QRectF(0.0, 0.0, width, 2.0))

        field_w = max(150.0, width - (2.0 * margin))
        name_rect = QtCore.QRectF(margin, 8.0, field_w, 34.0)
        name_base = self._mix(t["base"], t["titlebar"], 0.14)
        grad = QtGui.QLinearGradient(name_rect.topLeft(), name_rect.bottomLeft())
        grad.setColorAt(0.0, self._mix(name_base, QtGui.QColor("#000000"), 0.045))
        grad.setColorAt(0.22, name_base)
        grad.setColorAt(1.0, self._mix(name_base, t["text"], 0.015))
        p.setBrush(QtGui.QBrush(grad))
        p.setPen(QtGui.QPen(t.get("soft_border", t["border"]), 1.0))
        p.drawRect(name_rect)

        # Shallow inset: the upper inner lip is shadowed because the light source is
        # above; the bottom gets only a tiny reflected highlight.
        top_shadow = self._mix(name_base, QtGui.QColor("#000000"), 0.18)
        top_shadow.setAlpha(150)
        p.setPen(QtGui.QPen(top_shadow, 1.0))
        p.drawLine(
            QtCore.QPointF(name_rect.left() + 1.0, name_rect.top() + 1.0),
            QtCore.QPointF(name_rect.right() - 1.0, name_rect.top() + 1.0),
        )
        bottom_light = self._mix(name_base, t["text"], 0.05)
        bottom_light.setAlpha(80)
        p.setPen(QtGui.QPen(bottom_light, 1.0))
        p.drawLine(
            QtCore.QPointF(name_rect.left() + 1.0, name_rect.bottom() - 1.0),
            QtCore.QPointF(name_rect.right() - 1.0, name_rect.bottom() - 1.0),
        )

        title_font = self._font(21, QC.FontMedium)
        p.setFont(title_font)
        p.setPen(t["text"])
        title_text = PANEL_TITLE
        title_x = name_rect.left() + 10.0
        p.drawText(
            QtCore.QRectF(title_x, name_rect.top(), name_rect.width() - 20.0, name_rect.height()),
            QC.AlignLeft | QC.AlignVCenter,
            title_text,
        )

        title_w = float(QtGui.QFontMetrics(title_font).horizontalAdvance(title_text))
        p.setFont(self._font(9, QC.FontMedium))
        p.setPen(t["muted"])
        version_x = title_x + title_w + 9.0
        p.drawText(
            QtCore.QRectF(version_x, name_rect.top() + 1.0, max(0.0, name_rect.right() - version_x - 8.0), name_rect.height()),
            QC.AlignLeft | QC.AlignVCenter,
            "v{0}".format(__version__),
        )

        p.setFont(self._font(13, QC.FontMedium))
        warning = self.session and self.session.mode == SCORE_ATTACK and 0 < 120000-self.session.elapsed_ms <= 10000
        p.setPen(QtGui.QColor('#D5A34B') if warning else t['text'])
        p.drawText(QtCore.QRectF(width-126, 54, 114, 26), QC.AlignRight | QC.AlignVCenter, self._time_display())
        if width >= 720:
            status = "INPUT ACTIVE" if self.input_active and not self.paused else "INPUT RELEASED"
            p.setPen(t["muted"])
            p.setFont(self._font(10, QC.FontMedium))
            p.drawText(
                QtCore.QRectF(name_rect.right() - 155.0, name_rect.top(), 143.0, name_rect.height()),
                QC.AlignRight | QC.AlignVCenter,
                status,
            )

    def _time_display(self):
        if self.session and self.session.mode == SCORE_ATTACK:
            return format_milliseconds(max(0, 120000-self.session.elapsed_ms))
        if self.session and self.session.mode == SPRINT:
            return format_milliseconds(self.session.elapsed_ms)
        return self._format_time(self._active_seconds)

    def _draw_board(self, p, rect, cell,
                    t) :
        # Node Graph-like playfield: no visible Tetris squares. The mechanics remain
        # grid based, but only node chunks and wires are rendered.
        p.setPen(QC.NoPen)
        p.setBrush(t["board"])
        p.drawRect(rect)

        # Give the active playfield a slightly more present recessed frame than the
        # side wells so it reads as the primary working area without going too black.
        frame_border = self._mix(t["border"], QtGui.QColor("#000000"), 0.12)
        p.setBrush(QC.NoBrush)
        p.setPen(QtGui.QPen(frame_border, 1.0))
        p.drawRect(rect)

        top_shadow = self._mix(t["board"], QtGui.QColor("#000000"), 0.24)
        top_shadow.setAlpha(170)
        p.setPen(QtGui.QPen(top_shadow, 1.0))
        p.drawLine(
            QtCore.QPointF(rect.left() + 1.0, rect.top() + 1.0),
            QtCore.QPointF(rect.right() - 1.0, rect.top() + 1.0),
        )
        bottom_light = self._mix(t["board"], t["text"], 0.05)
        bottom_light.setAlpha(88)
        p.setPen(QtGui.QPen(bottom_light, 1.0))
        p.drawLine(
            QtCore.QPointF(rect.left() + 1.0, rect.bottom() - 1.0),
            QtCore.QPointF(rect.right() - 1.0, rect.bottom() - 1.0),
        )

        outer_shadow = self._mix(t["window"], QtGui.QColor("#000000"), 0.14)
        outer_shadow.setAlpha(95)
        p.setPen(QtGui.QPen(outer_shadow, 1.0))
        p.drawLine(
            QtCore.QPointF(rect.left() + 1.0, rect.bottom() + 1.0),
            QtCore.QPointF(rect.right() + 1.0, rect.bottom() + 1.0),
        )
        p.drawLine(
            QtCore.QPointF(rect.right() + 1.0, rect.top() + 1.0),
            QtCore.QPointF(rect.right() + 1.0, rect.bottom() + 1.0),
        )

        if self._grid_checkbox.isChecked():
            self._draw_node_graph_grid(p, rect, cell, t)

        self._draw_locked_graph(p, rect, cell, t)

        if not self.engine.game_over and self.engine.active is not None:
            ghost_y = self.engine.ghost_y()
            if ghost_y is not None:
                ghost_cells = [(x, y) for x, y in self.engine.active.cells(y=ghost_y) if y >= 0]
                self._draw_piece_graph(
                    p, rect, cell, ghost_cells, self.engine.active.kind, t,
                    active=False, ghost=True,
                )

            active_cells = [(x, y) for x, y in self.engine.active.cells() if y >= 0]
            self._draw_piece_graph(
                p, rect, cell, active_cells, self.engine.active.kind, t,
                active=True, ghost=False,
            )

        self._draw_clear_effect(p, rect, cell, t)

        p.setBrush(QC.NoBrush)
        p.setPen(QtGui.QPen(self._mix(frame_border, t["text"], 0.05), 1.0))
        p.drawRect(rect)

    def _draw_node_graph_grid(self, p, rect, cell,
                              t) :
        """Draw a Nuke-like dotted grid whose intersections are the node centers.

        One grid interval is exactly one game-cell move. Because node centers are also
        at (index + 0.5) * cell, every tetromino node lands precisely on a cross point.
        """
        grid = self._mix(t["text"], t["board"], 0.54)
        grid.setAlpha(125)
        pen = QtGui.QPen(grid, 1.0)
        pen.setStyle(QC.DotLine)
        pen.setCapStyle(QC.FlatCap)

        p.save()
        p.setClipRect(rect.adjusted(1.0, 1.0, -1.0, -1.0))
        p.setPen(pen)
        p.setBrush(QC.NoBrush)

        # Vertical and horizontal lines pass through the same centers used by _node_rect.
        for x in range(BOARD_W):
            px = rect.left() + (x + 0.5) * cell
            p.drawLine(QtCore.QPointF(px, rect.top()), QtCore.QPointF(px, rect.bottom()))
        for y in range(BOARD_H):
            py = rect.top() + (y + 0.5) * cell
            p.drawLine(QtCore.QPointF(rect.left(), py), QtCore.QPointF(rect.right(), py))

        p.restore()

    @staticmethod
    def _node_rect(board_rect, cell, x, y) :
        cx = board_rect.left() + (x + 0.5) * cell
        cy = board_rect.top() + (y + 0.5) * cell
        node_w = max(7.0, cell * 0.78)
        node_h = max(5.0, cell * 0.46)
        return QtCore.QRectF(cx - node_w * 0.5, cy - node_h * 0.5, node_w, node_h)

    @staticmethod
    def _spanning_edges(cells) :
        points = set(cells)
        if len(points) <= 1:
            return []
        root = min(points, key=lambda pt: (pt[1], pt[0]))
        queue = deque([root])
        seen = {root}
        edges = []
        # Prefer Nuke-like top-down flow, then branch horizontally.
        neighbor_order = ((0, 1), (-1, 0), (1, 0), (0, -1))
        while queue:
            current = queue.popleft()
            for dx, dy in neighbor_order:
                nxt = (current[0] + dx, current[1] + dy)
                if nxt in points and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
                    edges.append((current, nxt))
        return edges

    def _draw_wire(self, p, board_rect, cell,
                   source, target,
                   t, active = False,
                   ghost = False, subtle = False) :
        self._draw_nuke_wire(p, board_rect, cell, source, target, t, active, ghost, subtle)

    def _draw_nuke_wire(self, p, board_rect, cell, source, target, t,
                        active=False, ghost=False, subtle=False):
        endpoints = wire_endpoints(source, target, cell, (board_rect.left(), board_rect.top()))
        if endpoints is None:
            return
        start, end = (QtCore.QPointF(*pt) for pt in endpoints)
        color = QtGui.QColor(t['wire'])
        if ghost:
            color = QtGui.QColor(t['faint'])
            color.setAlpha(70)
        elif subtle:
            color.setAlpha(75)
        pen = QtGui.QPen(color, 1.1 if active else 1.0)
        if ghost:
            pen.setStyle(QC.DashLine)
        p.setPen(pen)
        p.setBrush(QC.NoBrush)
        p.drawLine(start, end)
        self._draw_nuke_arrow(p, start, end, color, cell)

    def _draw_nuke_arrow(self, p, start, end, color, cell):
        dx, dy = end.x()-start.x(), end.y()-start.y()
        length = math.hypot(dx, dy)
        if length < 1.0:
            return
        ux, uy = dx/length, dy/length
        size = min(max(2.0, cell*.12), length*.65)
        tip = QtCore.QPointF(end.x()-ux*.4, end.y()-uy*.4)
        base = QtCore.QPointF(tip.x()-ux*size, tip.y()-uy*size)
        wing = size*.5
        points = [tip, QtCore.QPointF(base.x()-uy*wing, base.y()+ux*wing),
                  QtCore.QPointF(base.x()+uy*wing, base.y()-ux*wing)]
        p.setPen(QC.NoPen)
        p.setBrush(color)
        p.drawPolygon(QtGui.QPolygonF(points))

    def _draw_locked_graph(self, p, board_rect, cell,
                           t) :
        groups = {}
        occupied = {}
        for y, row in enumerate(self.engine.board):
            for x, placed in enumerate(row):
                if placed is None:
                    continue
                groups.setdefault(placed.group_id, []).append((x, y, placed.kind))
                occupied[(x, y)] = placed

        # Very subtle contact links between stacked chunks make the settled pile read as
        # one larger node graph without erasing the original tetromino grouping.
        for (x, y), placed in occupied.items():
            below = occupied.get((x, y + 1))
            if below is not None and below.group_id != placed.group_id:
                self._draw_wire(
                    p, board_rect, cell, (x, y), (x, y + 1), t,
                    active=False, ghost=False, subtle=True,
                )

        for entries in groups.values():
            coords = [(x, y) for x, y, _ in entries]
            for source, target in self._spanning_edges(coords):
                self._draw_wire(p, board_rect, cell, source, target, t)

        for entries in groups.values():
            for x, y, kind in entries:
                self._draw_node(p, board_rect, cell, x, y, kind, t)

    def _draw_piece_graph(self, p, board_rect, cell,
                          cells, kind,
                          t, active = False,
                          ghost = False, show_label = True) :
        for source, target in self._spanning_edges(cells):
            self._draw_wire(
                p, board_rect, cell, source, target, t,
                active=active, ghost=ghost,
            )
        for x, y in cells:
            self._draw_node(
                p, board_rect, cell, x, y, kind, t,
                active=active, ghost=ghost, show_label=show_label,
            )

    def _draw_node(self, p, board_rect, cell,
                   x, y, kind, t,
                   active = False, ghost = False,
                   show_label = True) :
        r = self._node_rect(board_rect, cell, x, y)
        style = NODE_STYLES[kind]
        base = QtGui.QColor(style["color"])

        if ghost:
            outline = self._mix(base, t["board"], 0.48)
            outline.setAlpha(118)
            p.setBrush(QC.NoBrush)
            pen = QtGui.QPen(outline, 1.0)
            pen.setStyle(QC.DashLine)
            p.setPen(pen)
            p.drawRect(r)
            return

        if active:
            base = base.lighter(106)

        grad = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0.0, base.lighter(105))
        grad.setColorAt(0.36, base)
        grad.setColorAt(1.0, base.darker(106))
        p.setBrush(grad)
        border = QtGui.QColor("#141414")
        if active:
            border = self._mix(border, t["text"], 0.28)
        p.setPen(QtGui.QPen(border, 1.0))
        p.drawRect(r)

        # Thin top highlight and bottom shadow are closer to the flat/gradient Nuke nodes
        # than the previous game-like header strip.
        top_line = QtGui.QColor(base.lighter(112))
        top_line.setAlpha(145)
        p.setPen(QtGui.QPen(top_line, 1.0))
        p.drawLine(QtCore.QPointF(r.left() + 1, r.top() + 1), QtCore.QPointF(r.right() - 1, r.top() + 1))
        p.setPen(QtGui.QPen(QtGui.QColor("#202020"), 1.0))
        p.drawLine(QtCore.QPointF(r.left() + 1, r.bottom() - 1), QtCore.QPointF(r.right() - 1, r.bottom() - 1))

        # Nuke node-like input/output connector ticks.
        port = QtGui.QColor("#0D0D0D")
        p.setPen(QC.NoPen)
        p.setBrush(port)
        port_r = max(0.8, min(1.4, cell * 0.045))
        p.drawEllipse(QtCore.QPointF(r.center().x(), r.top() - 0.2), port_r, port_r)
        p.drawEllipse(QtCore.QPointF(r.center().x(), r.bottom() + 0.2), port_r, port_r)

        if show_label:
            label = style["label"]
            # The node name is decorative, but never abbreviated or clipped. Scale the
            # complete word to the node body instead of eliding it at small pane sizes.
            text_color = QtGui.QColor("#111111") if base.lightness() >= 82 else QtGui.QColor("#E7E7E7")
            self._draw_fitted_node_label(p, r.adjusted(2.0, 1.0, -2.0, -1.0), label, text_color)

    def _draw_fitted_node_label(self, p, rect,
                                text, color) :
        if rect.width() <= 1.0 or rect.height() <= 1.0 or not text:
            return
        font = self._font(12, QC.FontMedium)
        path = QtGui.QPainterPath()
        path.addText(0.0, 0.0, font, text)
        bounds = path.boundingRect()
        if bounds.width() <= 0.0 or bounds.height() <= 0.0:
            return
        sx = max(0.02, rect.width() / bounds.width())
        sy = max(0.02, rect.height() / bounds.height())
        scale = min(1.0, sx, sy)
        draw_w = bounds.width() * scale
        draw_h = bounds.height() * scale
        tx = rect.center().x() - draw_w * 0.5 - bounds.left() * scale
        ty = rect.center().y() - draw_h * 0.5 - bounds.top() * scale
        p.save()
        p.translate(tx, ty)
        p.scale(scale, scale)
        p.setPen(QC.NoPen)
        p.setBrush(color)
        p.drawPath(path)
        p.restore()

    def _draw_clear_effect(self, p, board, cell,
                           t) :
        if not self._clear_fx_rows or self._clear_fx_started <= 0.0:
            return

        elapsed = _monotonic() - self._clear_fx_started
        if elapsed >= CLEAR_FX_SECONDS:
            self._clear_fx_rows = []
            self._clear_fx_started = 0.0
            return

        phase = max(0.0, min(1.0, elapsed / CLEAR_FX_SECONDS))
        fade = 1.0 - phase
        accent = self._mix(t["highlight"], t["text"], 0.25)

        p.save()
        p.setClipRect(board)

        for row in self._clear_fx_rows:
            row_top = board.top() + row * cell
            center_y = row_top + cell * 0.5

            # A horizontal scan that races across the cleared row.
            scan_x = board.left() + board.width() * min(1.0, phase * 1.35)
            scan = QtGui.QColor(accent)
            scan.setAlpha(int(210 * fade))
            p.setPen(QtGui.QPen(scan, max(1.0, cell * 0.055)))
            p.drawLine(
                QtCore.QPointF(board.left(), center_y),
                QtCore.QPointF(scan_x, center_y),
            )

            # Node fragments shear away from the center; deterministic per cell.
            for x in range(BOARD_W):
                direction = -1.0 if x < BOARD_W / 2 else 1.0
                stagger = (x % 3) * 0.035
                local = max(0.0, min(1.0, (phase - stagger) / max(0.01, 1.0 - stagger)))
                shift = direction * local * cell * (0.35 + 0.05 * (x % 2))
                shrink = local * cell * 0.28
                frag = QtCore.QRectF(
                    board.left() + x * cell + cell * 0.12 + shift,
                    row_top + cell * 0.22,
                    max(1.0, cell * 0.76 - shrink),
                    cell * 0.56,
                )
                c = QtGui.QColor("#A0A0A0")
                c.setAlpha(int(105 * fade))
                p.setPen(QC.NoPen)
                p.setBrush(c)
                p.drawRoundedRect(frag, 1.5, 1.5)

            line = QtGui.QColor(t["text"])
            line.setAlpha(int(110 * fade))
            p.setPen(QtGui.QPen(line, 1.0))
            p.drawLine(
                QtCore.QPointF(board.left(), row_top + cell * 0.16),
                QtCore.QPointF(board.right(), row_top + cell * 0.16),
            )

        p.restore()

    def _draw_group_box(self, p, rect,
                        t) :
        # Preview wells are only a shallow recessed panel. Avoid the heavy black
        # outline that makes them look like separate game cards.
        fill = self._mix(t["base"], t["window"], 0.20)
        p.setBrush(fill)
        p.setPen(QtGui.QPen(t.get("soft_border", t["border"]), 1.0))
        p.drawRect(rect)

        # Very subtle inner top shadow + lower highlight, matching a recessed Nuke field.
        top_shadow = self._mix(fill, QtGui.QColor("#000000"), 0.16)
        top_shadow.setAlpha(145)
        p.setPen(QtGui.QPen(top_shadow, 1.0))
        p.drawLine(
            QtCore.QPointF(rect.left() + 1.0, rect.top() + 1.0),
            QtCore.QPointF(rect.right() - 1.0, rect.top() + 1.0),
        )
        lower = self._mix(fill, t["text"], 0.055)
        lower.setAlpha(95)
        p.setPen(QtGui.QPen(lower, 1.0))
        p.drawLine(
            QtCore.QPointF(rect.left() + 1.0, rect.bottom() - 1.0),
            QtCore.QPointF(rect.right() - 1.0, rect.bottom() - 1.0),
        )

    def _draw_section_header(self, p, x, y, width,
                             text, t) :
        p.setPen(t["text"])
        p.setFont(self._font(14, QC.FontDemiBold))
        fm = QtGui.QFontMetrics(p.font())
        label_w = float(fm.horizontalAdvance(text)) + 8.0
        p.drawText(
            QtCore.QRectF(x, y, label_w, 20.0),
            QC.AlignLeft | QC.AlignVCenter,
            text,
        )
        line_y = y + 10.0
        p.setPen(QtGui.QPen(t["section_line"], 1.0))
        p.drawLine(
            QtCore.QPointF(min(x + label_w, x + width), line_y),
            QtCore.QPointF(x + width, line_y),
        )
        return y + 22.0

    def _draw_static_row(self, p, x, y, width,
                         label, value, t,
                         emphasize = False) :
        # Nuke Grade-style label/value row. The value field uses a restrained vertical
        # gradient and a top-light cue; there is no exaggerated left-side shadow.
        row_h = 29.0
        label_w = min(74.0, width * 0.47)
        gap = 8.0
        box_h = 24.0
        box_y = y + (row_h - box_h) * 0.5
        box_rect = QtCore.QRectF(x + label_w + gap, box_y, width - label_w - gap, box_h)

        font_px = 13
        row_font = self._font(font_px, QC.FontNormal)
        p.setFont(row_font)
        p.setPen(t["text"])
        p.drawText(
            QtCore.QRectF(x, y, label_w, row_h),
            QC.AlignRight | QC.AlignVCenter,
            label.lower(),
        )

        field_base = self._mix(t["base"], t["window"], 0.08)
        # The field body stays almost flat. A recess is communicated by the dark
        # inner top edge (the cavity blocks the light from above), not by a bright top.
        field_grad = QtGui.QLinearGradient(box_rect.topLeft(), box_rect.bottomLeft())
        field_grad.setColorAt(0.0, self._mix(field_base, QtGui.QColor("#000000"), 0.055))
        field_grad.setColorAt(0.22, field_base)
        field_grad.setColorAt(1.0, self._mix(field_base, t["text"], 0.018))
        p.setPen(QtGui.QPen(t.get("soft_border", t["border"]), 1.0))
        p.setBrush(QtGui.QBrush(field_grad))
        p.drawRect(box_rect)

        top_shadow = self._mix(field_base, QtGui.QColor("#000000"), 0.20)
        top_shadow.setAlpha(150)
        p.setPen(QtGui.QPen(top_shadow, 1.0))
        p.drawLine(
            QtCore.QPointF(box_rect.left() + 1.0, box_rect.top() + 1.0),
            QtCore.QPointF(box_rect.right() - 1.0, box_rect.top() + 1.0),
        )
        bottom_light = self._mix(field_base, t["text"], 0.055)
        bottom_light.setAlpha(85)
        p.setPen(QtGui.QPen(bottom_light, 1.0))
        p.drawLine(
            QtCore.QPointF(box_rect.left() + 1.0, box_rect.bottom() - 1.0),
            QtCore.QPointF(box_rect.right() - 1.0, box_rect.bottom() - 1.0),
        )

        value_font = self._font(font_px, QC.FontNormal)
        text_rect = box_rect.adjusted(6.0, 0.0, -4.0, 0.0)
        while value_font.pixelSize() > 10:
            fm = QtGui.QFontMetrics(value_font)
            if fm.horizontalAdvance(value) <= max(1.0, text_rect.width() - 1.0):
                break
            value_font.setPixelSize(value_font.pixelSize() - 1)
        p.setFont(value_font)
        p.setPen(t["text"])
        p.drawText(
            text_rect,
            QC.AlignLeft | QC.AlignVCenter,
            value,
        )

    def _draw_side_panels(self, p, board,
                          side, gutter, t) :
        left_x = board.left() - gutter - side
        right_x = board.right() + gutter
        top = board.top()

        # HOLD
        y = self._draw_section_header(p, left_x, top, side, "HOLD", t)
        preview_h = min(66.0, max(54.0, board.height() * 0.145))
        self._draw_piece_preview(p, self.engine.hold_kind, left_x, y, side, preview_h, t)

        # STATS — TIME intentionally sits directly beneath LINES.
        stats_y = y + preview_h + 7.0
        stats_y = self._draw_section_header(p, left_x, stats_y, side, "STATS", t)
        rows = [
            ("score", "{0:,}".format(self.engine.score), True),
            ("best", "{0:,}".format(self.engine.best_score), False),
            ("level", "{0:02d}".format(self.engine.level), False),
            ("lines", "{0:03d}".format(self.engine.lines), False),
            ("time", self._time_display(), True),
        ]
        for label, value, emphasize in rows:
            self._draw_static_row(p, left_x, stats_y, side, label, value, t, emphasize)
            stats_y += 29.0

        if self.engine.combo > 0 and stats_y + 29.0 <= board.bottom():
            self._draw_static_row(
                p, left_x, stats_y, side, "combo", "x{0}".format(self.engine.combo + 1), t, False
            )

        # NEXT
        y = self._draw_section_header(p, right_x, top, side, "NEXT", t)
        available = max(160.0, board.bottom() - y)
        item_h = min(59.0, max(42.0, (available - (NEXT_COUNT - 1) * 5.0) / NEXT_COUNT))
        for kind in self.engine.next_pieces(NEXT_COUNT):
            self._draw_piece_preview(
                p, kind, right_x, y, side, item_h, t, show_label=False
            )
            y += item_h + 3.0

    def _draw_compact_previews(self, p, margin, width, board, t):
        p.setFont(self._font(10, QC.FontMedium))
        p.setPen(t['muted'])
        p.drawText(QtCore.QRectF(margin, 90, 80, 16), QC.AlignLeft, 'HOLD')
        p.drawText(QtCore.QRectF(width-192, 90, 180, 16), QC.AlignLeft, 'NEXT')
        self._draw_piece_preview(p, self.engine.hold_kind, margin, 107, 88, 48, t)
        for i, kind in enumerate(self.engine.next_pieces(3)):
            self._draw_piece_preview(p, kind, width-192+i*60, 107, 56, 48, t, False)

    def _draw_compact_stats(self, p, margin, width,
                            board, t) :
        # Narrow-pane fallback. Keep LINES immediately followed by TIME in reading order.
        y = board.bottom() + 2
        p.setFont(self._font(13, QC.FontMedium))
        p.setPen(t["text"])
        text = (
            "SCORE {0:,}    LV {1:02d}    LINES {2:03d}    TIME {3}".format(
                self.engine.score, self.engine.level, self.engine.lines,
                self._time_display()
            )
        )
        p.drawText(
            QtCore.QRectF(margin, y, width - 2 * margin, 18),
            QC.AlignCenter,
            text,
        )

    def _draw_label(self, p, x, y, width,
                    text, t) :
        # Retained for small utility labels; section headings use _draw_section_header.
        p.setPen(t["muted"])
        p.setFont(self._font(8, QC.FontDemiBold))
        p.drawText(QtCore.QRectF(x, y, width, 16), QC.AlignLeft, text)

    def _draw_stat(self, p, x, y, width,
                   label, value, t) :
        self._draw_static_row(p, x, y, width, label, value, t, False)

    def _draw_piece_preview(self, p, kind, x, y,
                            width, height, t,
                            show_label = True) :
        r = QtCore.QRectF(x, y, width, height)
        preview_t = t
        if not show_label:
            preview_t = dict(t)
            preview_t["soft_border"] = self._mix(t.get("soft_border", t["border"]), t["window"], 0.28)
        self._draw_group_box(p, r, preview_t)
        if not kind:
            p.setPen(t["faint"])
            p.setFont(self._font(9, QC.FontMedium))
            p.drawText(r, QC.AlignCenter, "—")
            return

        cells = list(PIECE_CELLS[kind][0])
        min_x = min(cx for cx, _ in cells)
        max_x = max(cx for cx, _ in cells)
        min_y = min(cy for _, cy in cells)
        max_y = max(cy for _, cy in cells)
        pw = max_x - min_x + 1
        ph = max_y - min_y + 1
        c = min((width - 14) / max(pw, 1), (height - 14) / max(ph, 1), 20.0)
        ox = x + (width - pw * c) / 2.0 - min_x * c
        oy = y + (height - ph * c) / 2.0 - min_y * c
        fake_board = QtCore.QRectF(ox, oy, c * 4, c * 4)
        self._draw_piece_graph(
            p, fake_board, c, cells, kind, t, active=False, ghost=False, show_label=show_label
        )

    def _draw_keycap(self, p, x, y, text,
                     t, wide = False) :
        width = 42.0 if wide else max(22.0, 11.0 + len(text) * 7.0)
        rect = QtCore.QRectF(x, y, width, 20.0)
        p.setBrush(self._mix(t["base"], t["panel"], 0.10))
        p.setPen(QtGui.QPen(self._mix(t["border"], t["text"], 0.08), 1.0))
        p.drawRoundedRect(rect, 2.0, 2.0)
        p.setPen(t["text"])
        p.setFont(self._font(10, QC.FontDemiBold))
        p.drawText(rect, QC.AlignCenter, text)
        return width

    def _draw_bind(self, p, x, y, keys,
                   icon, label, t) :
        start_x = x
        p.setPen(t["muted"])
        p.setFont(self._font(13, QC.FontDemiBold))
        icon_rect = QtCore.QRectF(x, y, 18, 20)
        p.drawText(icon_rect, QC.AlignCenter, icon)
        x += 22

        for i, key in enumerate(keys):
            kw = self._draw_keycap(p, x, y, key, t, wide=(key == "SPACE"))
            x += kw
            if i < len(keys) - 1:
                x += 3

        x += 6
        p.setPen(t["text"])
        p.setFont(self._font(12, QC.FontNormal))
        label_w = max(34.0, float(QtGui.QFontMetrics(p.font()).horizontalAdvance(label)) + 2.0)
        p.drawText(
            QtCore.QRectF(x, y, label_w, 20),
            QC.AlignLeft | QC.AlignVCenter,
            label,
        )
        return (x + label_w) - start_x

    def _draw_footer(self, p, margin, width, height,
                     board, t) :
        game_y = board.bottom() + (28.0 if width < 650 else 16.0)
        controls_y = game_y + 94.0

        self._draw_section_header(
            p, margin, game_y, width - 2.0 * margin, "GAME", t
        )

        self._draw_section_header(
            p, margin, controls_y, width - 2.0 * margin, "CONTROLS", t
        )
        base_y = controls_y + 24.0

        rows = [
            [
                (("A", "D"), "↔", "MOVE"),
                (("S",), "↓", "DOWN"),
                (("Q", "E"), "↻", "ROTATE"),
            ],
            [
                (("C",), "◇", "HOLD"),
                (("SPACE",), "⇊", "DROP"),
                (("ESC",), "Ⅱ", "PAUSE"),
            ],
        ]

        available = max(1.0, width - 2.0 * margin)
        for row_index, row in enumerate(rows):
            widths = []
            for keys, icon, label in row:
                key_w = sum(42.0 if k == "SPACE" else max(22.0, 11.0 + len(k) * 7.0) for k in keys)
                key_w += max(0, len(keys) - 1) * 3.0
                label_w = max(42.0, len(label) * 6.3 + 3.0)
                widths.append(22.0 + key_w + 6.0 + label_w)
            raw_gap = (available - sum(widths)) / max(1, len(row) - 1)
            gap = max(4.0, min(14.0, raw_gap))
            x = margin + 4.0
            y = base_y + row_index * 25.0
            for (keys, icon, label), item_w in zip(row, widths):
                self._draw_bind(p, x, y, keys, icon, label, t)
                x += item_w + gap

        copyright_y = base_y + 53.0
        if copyright_y + 13.0 < height - 2.0:
            p.setPen(t["faint"])
            p.setFont(self._font(9, QC.FontNormal))
            p.drawText(
                QtCore.QRectF(margin, copyright_y, width - (2.0 * margin), 13.0),
                QC.AlignRight | QC.AlignVCenter,
                "© 2026 Kota Mori",
            )

    def _draw_overlay(self, p, board,
                      t) :
        title = ""
        sub = ""

        if self.error_text:
            title = "SAFE PAUSE"
            sub = "GAME ERROR — USE NEW GAME"
        elif not self.started:
            title = "READY"
            sub = "CLICK BOARD OR PRESS SPACE"
        elif self.session and self.session.finished:
            title = "FINISHED" if self.session.result else "GAME OVER"
            sub = (self._time_display() if self.session.mode == SPRINT else "SCORE {0:,}".format(self.engine.score)) + " - NEW GAME"
        elif self.engine.game_over:
            title = "GAME OVER"
            sub = "{0:,}  ·  SPACE / NEW GAME".format(self.engine.score)
        elif self.paused:
            title = "PAUSED"
            sub = "Ranked timer is still running." if self.session and self.session.ranked else "CLICK BOARD OR PRESS SPACE"

        if not title:
            return

        veil = QtGui.QColor(t["board"])
        veil.setAlpha(224)
        p.setPen(QC.NoPen)
        p.setBrush(veil)
        p.drawRoundedRect(board, 2.0, 2.0)

        p.setPen(t["text"])
        p.setFont(self._font(20, QC.FontDemiBold))
        center_y = board.center().y() - 19
        p.drawText(
            QtCore.QRectF(board.left(), center_y, board.width(), 28),
            QC.AlignCenter,
            title,
        )

        p.setPen(t["muted"])
        p.setFont(self._font(10, QC.FontMedium))
        p.drawText(
            QtCore.QRectF(board.left(), center_y + 31, board.width(), 20),
            QC.AlignCenter,
            sub,
        )

        if self.error_text:
            p.setPen(t["faint"])
            p.setFont(self._font(8))
            elided = QtGui.QFontMetrics(p.font()).elidedText(
                self.error_text,
                QC.ElideRight,
                int(board.width() - 40),
            )
            p.drawText(
                QtCore.QRectF(board.left() + 20, center_y + 56, board.width() - 40, 20),
                QC.AlignCenter,
                elided,
            )


# ---------- Nuke integration: panel registration only ----------

def register_panel() :
    """Register NUKERIS in Nuke's Pane menu. No script data is touched."""
    try:
        import nuke
        from nukescripts import panels

        if not getattr(nuke, "GUI", False):
            return

        widget_expr = "__import__({0!r}).NukerisPanel".format(__name__)
        panels.registerWidgetAsPanel(widget_expr, PANEL_TITLE, PANEL_ID)
    except Exception:
        # A registration problem should never block Nuke startup.
        traceback.print_exc()


register_panel()
