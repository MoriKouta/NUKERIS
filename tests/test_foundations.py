import json
import os
import random
import shutil
import tempfile
import unittest
from support import core, MemoryStore


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.e = core.GameEngine(storage=self.store, seed=42)

    def test_initial_spawn_and_seven_bag(self):
        e = self.e
        self.assertEqual((len(e.board), len(e.board[0])), (20, 10))
        self.assertEqual((e.score, e.level, e.lines), (0, 1, 0))
        self.assertTrue(e._valid(e.active.cells()))
        self.assertEqual(len(set([e.active.kind] + list(e.queue)[:6])), 7)
        self.assertEqual(len(e.next_pieces()), 5)

    def test_movement_collision_and_ghost(self):
        e = self.e
        for _ in range(20):
            e.move(-1, 0)
        self.assertFalse(e.move(-1, 0))
        self.assertEqual(min(x for x, y in e.active.cells()), 0)
        gy = e.ghost_y()
        self.assertTrue(e._valid(e.active.cells(y=gy)))
        self.assertFalse(e._valid(e.active.cells(y=gy+1)))

    def test_rotation_wall_kick(self):
        e = self.e
        e.active = core.Tetromino('T', x=-1, y=3, rotation=1)
        self.assertTrue(e._valid(e.active.cells()))
        self.assertTrue(e.rotate(-1))
        self.assertEqual((e.active.x, e.active.rotation), (0, 0))

    def test_hold_only_once_per_piece(self):
        e = self.e
        kind = e.active.kind
        self.assertTrue(e.hold())
        self.assertEqual(e.hold_kind, kind)
        self.assertFalse(e.hold())
        e.hard_drop()
        self.assertTrue(e.hold())

    def test_line_clear_score_combo_level(self):
        e = self.e
        for run in range(2):
            e.board[-1] = [core.PlacedCell('I', 0) for _ in range(10)]
            e._score_clear(e._clear_lines())
        self.assertEqual((e.lines, e.score, e.combo), (2, 250, 1))
        e.lines = 9
        e.board[-1] = [core.PlacedCell('I', 0) for _ in range(10)]
        e._clear_lines()
        self.assertEqual(e.level, 2)
        e._score_clear(0)
        self.assertEqual(e.combo, -1)

    def test_drop_lock_best_score_and_reset(self):
        e = self.e
        distance = e.hard_drop()
        self.assertEqual(e.score, distance*2)
        self.assertEqual(sum(c is not None for row in e.board for c in row), 4)
        self.assertEqual(self.store.best(), e.score)
        e.reset()
        self.assertEqual(e.score, 0)
        self.assertGreater(e.best_score, 0)

    def test_game_over_spawn_and_top_out(self):
        e = self.e
        e.board = [[core.PlacedCell('T', 1) for _ in range(10)] for _ in range(20)]
        e._spawn('O')
        self.assertTrue(e.game_over)
        e.reset()
        e.active = core.Tetromino('T', y=-1)
        e.lock_piece()
        self.assertTrue(e.game_over)

    def test_random_isolation_and_seed(self):
        before = random.getstate()
        other = core.GameEngine(storage=MemoryStore(), seed=42)
        self.assertEqual(list(other.queue), list(self.e.queue))
        for _ in range(10):
            other.hard_drop()
        self.assertEqual(before, random.getstate())


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, 'settings.json')
        self.store = core.LegacyScoreStore(self.path)

    def tearDown(self):
        shutil.rmtree(self.folder)

    def test_missing_valid_corrupt(self):
        self.assertEqual(self.store.best(), 0)
        self.assertTrue(self.store.save_best(200))
        self.assertEqual(self.store.best(), 200)
        with open(self.path, 'w') as f:
            f.write('{broken')
        self.assertEqual(self.store.best(), 0)

    def test_stale_engines_never_lower_best(self):
        engines = [core.GameEngine(self.store), core.GameEngine(core.LegacyScoreStore(self.path))]
        for engine, value in zip(engines, (200, 50)):
            engine.score = value
            engine._update_best_score()
        self.assertEqual(self.store.best(), 200)

    def test_failed_replace_keeps_old_bytes(self):
        self.store.save_best(200)
        with open(self.path, 'rb') as f:
            before = f.read()
        original = core.replace_file
        def fail(*args):
            raise OSError('injected failure')
        core.replace_file = fail
        try:
            self.assertFalse(self.store.save_best(300))
        finally:
            core.replace_file = original
        with open(self.path, 'rb') as f:
            self.assertEqual(f.read(), before)
        self.assertFalse(any(n.endswith('.tmp') for n in os.listdir(self.folder)))

    def test_interrupted_temp_write_preserves_final(self):
        self.store.save_best(200)
        original = core.os.fsync
        def fail(*args):
            raise OSError('interrupted')
        core.os.fsync = fail
        try:
            self.assertFalse(self.store.save_best(300))
        finally:
            core.os.fsync = original
        self.assertEqual(self.store.best(), 200)

    def test_lock_contention_preserves_final(self):
        self.store.save_best(200)
        with core.FileLock(self.path):
            self.assertFalse(core.LegacyScoreStore(self.path).save_best(300))
        self.assertEqual(self.store.best(), 200)
        self.assertTrue(self.store.save_best(300))

    def test_old_python_atomic_fallback(self):
        original = getattr(core.os, 'replace', None)
        if original is not None:
            del core.os.replace
        try:
            self.assertTrue(self.store.save_best(200))
            self.assertTrue(self.store.save_best(300))
            self.assertEqual(self.store.best(), 300)
        finally:
            if original is not None:
                core.os.replace = original

if __name__ == '__main__':
    unittest.main()
