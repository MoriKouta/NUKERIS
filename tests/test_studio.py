import os
import shutil
import tempfile
import unittest
from support import core
from test_settings import result

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.mkdtemp()
        self.id='a'*32
        self.s=core.StudioRanking(True,self.folder,self.id,dict(nickname='MORI',country='JP',region='SAITAMA'))
    def tearDown(self): shutil.rmtree(self.folder)
    def test_disabled_never_accesses_path(self):
        s=core.StudioRanking(False,'not-a-folder')
        original=core.os.path.realpath
        def fail(*args): raise AssertionError('filesystem access while OFF')
        core.os.path.realpath=fail
        try:
            self.assertFalse(s.publish(result()))
            self.assertFalse(s.read(core.SCORE_ATTACK)['ok'])
        finally: core.os.path.realpath=original
    def test_pb_only_and_sort(self):
        self.assertTrue(self.s.publish(result(score=200)))
        self.assertTrue(self.s.publish(result(score=100)))
        self.assertEqual(self.s.read(core.SCORE_ATTACK)['entries'][0]['score'],200)
    def test_corrupt_partial_schema_and_ruleset_ignored(self):
        self.s.publish(result())
        folder=self.s._directory(core.SCORE_ATTACK)
        for name,content in [('b'*32+'.json','{'),('c'*32+'.json','[]'),('d'*32+'.tmp','{}')]:
            with open(os.path.join(folder,name),'w') as f:f.write(content)
        bad=dict(result(),schema=2,player_id='e'*32)
        core.atomic_json(os.path.join(folder,'e'*32+'.json'),bad)
        self.assertEqual(len(self.s.read(core.SCORE_ATTACK)['entries']),1)
    def test_read_only_write_failure_keeps_pb(self):
        self.s.publish(result(score=200));original=core.atomic_json
        def fail(*args,**kwargs):raise IOError('permission denied')
        core.atomic_json=fail
        try:self.assertFalse(self.s.publish(result(score=300)))
        finally:core.atomic_json=original
        self.assertEqual(self.s.read(core.SCORE_ATTACK)['entries'][0]['score'],200)
    def test_disconnected_folder(self):
        self.s.folder=os.path.join(self.folder,'missing')
        self.assertFalse(self.s.read(core.SCORE_ATTACK)['ok'])
    def test_invalid_identity_cannot_escape_folder(self):
        self.s.player_id='../escape'
        self.assertFalse(self.s.publish(result()))
