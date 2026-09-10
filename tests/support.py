import os
import sys
import types
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools'))
from build import build

core = types.ModuleType('nukeris_test_core')
core.__file__ = os.path.join(os.path.dirname(__file__), 'unused_module.py')
eval(compile(build(False), 'nukeris-core', 'exec'), core.__dict__)

class MemoryStore(object):
    def __init__(self):
        self.score = 0
    def best(self):
        return self.score
    def save_best(self, score):
        self.score = max(score, self.score)
        return True
