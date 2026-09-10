class StudioRanking(object):
    """Trust-based PB files. Disabled operations do not inspect the filesystem."""
    def __init__(self, enabled=False, folder='', player_id='', profile=None):
        self.enabled = enabled
        self.folder = folder
        self.player_id = player_id
        self.profile = profile or {}

    def _directory(self, mode):
        if not self.enabled or mode not in (SCORE_ATTACK, SPRINT) or not self.folder:
            raise ValueError('Studio ranking is disabled or not configured')
        root = os.path.realpath(os.path.abspath(self.folder))
        path = os.path.join(root, 'scores', mode, RULESET)
        resolved = os.path.realpath(path)
        if not os.path.normcase(resolved).startswith(os.path.normcase(root + os.sep)):
            raise ValueError('Studio path escapes the configured folder')
        return path

    def publish(self, result):
        if not self.enabled:
            return False
        if not valid_result(result) or not re.match(r'^[a-f0-9]{32}$', self.player_id) or not validate_profile(self.profile):
            return False
        try:
            if not os.path.isdir(self.folder):
                return False
            folder = self._directory(result['mode'])
            path = os.path.join(folder, self.player_id + '.json')
            if os.path.islink(path) or os.path.islink(path + '.lockfile'):
                return False
            value = dict(result, schema=1, player_id=self.player_id,
                         nickname=self.profile['nickname'], country=self.profile['country'], region=self.profile['region'])
            def merge(current):
                if valid_result(current) and current.get('player_id') == self.player_id and not better_result(value, current):
                    return current
                return value
            return JsonStore(path).update(merge) is not None
        except Exception:
            return False

    def read(self, mode):
        if not self.enabled:
            return dict(ok=False, entries=[], message='Studio ranking is off.')
        try:
            folder = self._directory(mode)
            if not os.path.isdir(folder):
                # Distinguish an empty score folder from a disconnected configured root.
                if not os.path.isdir(self.folder):
                    raise IOError('unavailable')
                return dict(ok=True, entries=[], message='NO SCORES YET')
            entries = []
            for name in os.listdir(folder)[:5000]:
                if not re.match(r'^[a-f0-9]{32}\.json$', name):
                    continue
                path = os.path.join(folder, name)
                if os.path.islink(path):
                    continue
                value = read_json(path, {}, 8192)
                if (value.get('schema') == 1 and value.get('mode') == mode and valid_result(value) and
                        value.get('player_id') == name[:-5] and validate_profile(value)):
                    entries.append(value)
            entries.sort(key=lambda r: ((r['time_ms'] if mode == SPRINT else -r['score']), r['player_id']))
            return dict(ok=True, entries=entries, message='' if entries else 'NO SCORES YET')
        except Exception:
            return dict(ok=False, entries=[], message='Studio folder is unavailable. Personal records are safe.')
