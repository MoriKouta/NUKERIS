import unittest
from support import core, MemoryStore

class ModeTests(unittest.TestCase):
    def session(self, mode):
        self.now = 0.0
        return core.GameSession(mode, storage=MemoryStore(), clock=lambda: self.now, seed=2)

    def test_normal_clock_only_uses_active_play(self):
        s=self.session(core.NORMAL)
        self.now=300
        s.advance(.05)
        self.assertEqual(s.elapsed_ms,50)
        self.assertFalse(s.finished)

    def test_ranked_focus_pause_time_continues(self):
        s=self.session(core.SCORE_ATTACK)
        self.now=119.999
        s.advance()
        self.assertFalse(s.finished)
        self.now=120
        before=s.engine.score
        s.action('hard_drop')
        self.assertTrue(s.finished)
        self.assertEqual(s.result['time_ms'],120000)
        self.assertEqual(s.engine.score,before)

    def test_sprint_milliseconds_and_terminal_result(self):
        s=self.session(core.SPRINT)
        self.now=42.123
        s.engine.lines=40
        s.advance()
        self.assertEqual(s.result['time_ms'],42123)
        self.now=99
        s.advance()
        self.assertEqual(s.result['time_ms'],42123)
        self.assertEqual(core.format_milliseconds(42123),'00:42.123')

    def test_failed_sprint_has_no_result(self):
        s=self.session(core.SPRINT)
        s.engine.game_over=True
        s.advance()
        self.assertTrue(s.finished)
        self.assertIsNone(s.result)

    def test_clock_regression_cannot_reduce_ranked_time(self):
        s=self.session(core.SPRINT)
        self.now=5
        s.advance()
        self.now=4
        s.advance()
        self.assertEqual(s.elapsed_ms,5000)
