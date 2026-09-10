import os
import shutil
import tempfile
import unittest
from support import core
from test_settings import result

class FakeTransport(object):
    def __init__(self):self.calls=[];self.response={'ok':False};self.cancelled=False
    def request(self,*args):self.calls.append(args[:-1]);args[-1](self.response)
    def cancel(self):self.cancelled=True

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.mkdtemp();self.s=core.SettingsStore(os.path.join(self.folder,'s.json'))
        self.t=FakeTransport();self.c=core.GlobalRankingClient(self.s,self.t,'https://ranking.example.com')
        self.responses=[]
    def tearDown(self):shutil.rmtree(self.folder)
    def enable(self):
        self.s.save_preferences(dict(player_token='a'*64,profile=dict(nickname='MORI',country='JP',region='SAITAMA')))
        self.c.configure(True)
    def test_offline_default_zero_requests(self):
        self.c.leaderboard(core.SCORE_ATTACK,self.responses.append)
        self.c.start_run(core.SCORE_ATTACK,self.responses.append)
        self.c.submit('run',result(),self.responses.append)
        self.assertEqual(self.t.calls,[])
    def test_failure_and_malformed_response(self):
        self.enable()
        for response in (None,[],{'ok':True},{'ok':False}):
            self.t.response=response
            self.c.leaderboard(core.SCORE_ATTACK,self.responses.append)
            self.assertFalse(self.responses[-1]['ok'])
    def test_disable_cancels(self):
        self.enable();self.c.configure(False)
        self.assertTrue(self.t.cancelled)
        self.c.start_run(core.SCORE_ATTACK,self.responses.append)
        self.assertFalse(self.t.calls)
    def test_payload_allowlist(self):
        self.enable();r=result();r['hostname']='must-not-send';r['path']='must-not-send'
        self.c.submit('signed',r,self.responses.append)
        sent=self.t.calls[-1][2]['result']
        self.assertNotIn('hostname',sent);self.assertNotIn('path',sent)
    def test_local_pb_survives_network_failure(self):
        self.enable();self.s.record(result(score=300))
        self.c.submit('run',result(score=300),self.responses.append)
        self.assertEqual(self.s.read()['pbs'][core.SCORE_ATTACK],300)
    def test_endpoint_requires_https_origin(self):
        self.enable()
        for endpoint in ('http://example.com','https://user:pass@example.com','https://example.com?token=x',''):
            self.c.endpoint=endpoint
            self.c.start_run(core.SCORE_ATTACK,self.responses.append)
        self.assertEqual(self.t.calls,[])
