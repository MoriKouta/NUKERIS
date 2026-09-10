# The maintainer sets the official HTTPS origin after an approved deployment.
# Empty by default: this distribution has no live backend configured.
GLOBAL_ENDPOINT = ''


class GlobalRankingClient(object):
    def __init__(self, settings, transport, endpoint=GLOBAL_ENDPOINT):
        self.settings = settings
        self.transport = transport
        self.endpoint = endpoint.rstrip('/')
        self.enabled = settings.read()['global_enabled']
        self.generation = 0

    def configure(self, enabled):
        self.enabled = bool(enabled)
        self.generation += 1
        if not self.enabled:
            self.transport.cancel()

    def request(self, method, path, body, callback, authenticated=True):
        if not self.enabled:
            callback(dict(ok=False, error='Global ranking is off.'))
            return
        if not re.match(r'^https://[A-Za-z0-9.-]+(?::[0-9]+)?\Z', self.endpoint):
            callback(dict(ok=False, error='The official Global endpoint is not configured.'))
            return
        token = self.settings.read()['player_token'] if authenticated else ''
        if authenticated and not re.match(r'^[a-f0-9]{64}\Z', token):
            callback(dict(ok=False, error='Create an online profile first.'))
            return
        generation = self.generation
        def complete(response):
            if generation != self.generation or not self.enabled:
                callback(dict(ok=False,error='Global ranking was disabled.'))
            elif not isinstance(response, dict) or response.get('ok') is not True:
                callback(dict(ok=False,error='Global request failed. Personal records are safe.'))
            else:
                callback(response)
        self.transport.request(method,self.endpoint+path,body,token,complete)

    def register(self, callback):
        profile = self.settings.read()['profile']
        if not validate_profile(profile):
            callback(dict(ok=False,error='Set your nickname, country and region in Settings.'))
            return
        def done(r):
            if r.get('ok'):
                if not (isinstance(r.get('player_id'), type(u'')) and re.match(r'^[a-f0-9-]{36}\Z',r['player_id']) and
                        isinstance(r.get('player_token'), type(u'')) and re.match(r'^[a-f0-9]{64}\Z',r['player_token'])):
                    r = dict(ok=False,error='Invalid profile response.')
                elif not self.settings.save_preferences(dict(player_id=r['player_id'],player_token=r['player_token'])):
                    r = dict(ok=False,error='Online identity could not be saved. Check local settings permissions.')
            callback(r)
        self.request('POST','/v1/players',dict(profile=profile,version=__version__),done,False)

    def update_profile(self, callback):
        self.request('POST','/v1/profile',dict(profile=self.settings.read()['profile'],version=__version__),callback)

    def start_run(self, mode, callback):
        def done(r):
            if r.get('ok') and not (isinstance(r.get('run_token'),type(u'')) and
                    re.match(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\Z',r['run_token']) and len(r['run_token'])<=2048 and
                    isinstance(r.get('seed'),type(u'')) and re.match(r'^[a-f0-9]{16}\Z',r['seed'])):
                r = dict(ok=False,error='Invalid start response.')
            callback(r)
        self.request('POST','/v1/runs',dict(mode=mode,ruleset=RULESET,version=__version__),done)

    def submit(self, token, result, callback):
        if not valid_result(result):
            callback(dict(ok=False,error='Result is not eligible for Global ranking.'))
            return
        fields = ('mode','ruleset','version','score','time_ms','lines','pieces')
        self.request('POST','/v1/results',dict(run_token=token,result={k:result[k] for k in fields}),callback)

    def leaderboard(self, mode, callback):
        def done(r):
            if r.get('ok'):
                entries, ranks = r.get('entries'), r.get('ranks')
                if (not isinstance(entries,list) or len(entries)>100 or
                        not all(valid_result(row) and row['mode']==mode and validate_profile(row) for row in entries) or
                        not isinstance(ranks,dict) or any(k not in ranks or (ranks[k] is not None and
                        (isinstance(ranks[k],bool) or not isinstance(ranks[k],int) or ranks[k]<1)) for k in ('world','country','region'))):
                    r = dict(ok=False,error='Invalid ranking response.')
            callback(r)
        self.request('GET','/v1/leaderboard?mode='+mode+'&ruleset='+RULESET+'&version='+__version__,None,done)
