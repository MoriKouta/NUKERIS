import io
import json
import os
import unittest
from collections import deque
from support import core, MemoryStore

class NormalParityTests(unittest.TestCase):
    def test_frozen_v1_1_gameplay_trace(self):
        path=os.path.join(os.path.dirname(__file__),'fixtures','normal_v1_1.json')
        with io.open(path,encoding='utf-8') as f:fixture=json.load(f)
        e=core.GameEngine(MemoryStore(),seed=1)
        e.active=core.Tetromino('T');e.queue=deque(list('IOSZJLT')*8)
        for action,expected in zip(fixture['actions'],fixture['snapshots']):
            getattr(e,action[0])(*action[1:])
            actual=dict(score=e.score,lines=e.lines,level=e.level,combo=e.combo,game_over=e.game_over,
                active=[e.active.kind,e.active.x,e.active.y,e.active.rotation],hold=e.hold_kind,
                board=[[c.kind if c else None for c in row] for row in e.board])
            self.assertEqual(actual,expected)
