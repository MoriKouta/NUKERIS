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


