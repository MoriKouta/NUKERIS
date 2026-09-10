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
