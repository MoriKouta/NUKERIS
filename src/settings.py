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
