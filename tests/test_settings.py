import os
import shutil
import tempfile
import unittest
from support import core

def result(mode=core.SCORE_ATTACK, score=100, time_ms=120000):
    return dict(mode=mode, ruleset=core.RULESET, version=core.__version__, score=score,
                time_ms=time_ms, lines=40 if mode==core.SPRINT else 2, pieces=100)

class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.mkdtemp()
        self.path=os.path.join(self.folder,'user','settings.json')
        self.old=os.path.join(self.folder,'legacy.json')
    def tearDown(self):
        shutil.rmtree(self.folder)
    def store(self):
        return core.SettingsStore(self.path,self.old)
    def test_defaults_off_no_files_created(self):
        s=self.store()
        self.assertFalse(s.read()['global_enabled'])
        self.assertFalse(s.read()['studio_enabled'])
        self.assertFalse(os.path.exists(self.path))
    def test_migration_keeps_source_and_larger_pb(self):
        core.atomic_json(self.old,{'best_score':500})
        s=self.store()
        self.assertEqual(s.best(),500)
        self.assertTrue(os.path.exists(self.old))
        s.save_best(600)
        self.assertEqual(self.store().best(),600)
    def test_modes_independent_and_monotonic(self):
        s=self.store(); other=self.store()
        s.record(result(score=200))
        other.record(result(score=50))
        s.record(result(core.SPRINT,time_ms=30000))
        other.record(result(core.SPRINT,time_ms=40000))
        self.assertEqual(s.read()['pbs'][core.SCORE_ATTACK],200)
        self.assertEqual(s.read()['pbs'][core.SPRINT],30000)
    def test_failure_retains_personal_result_for_retry(self):
        s=self.store(); original=core.replace_file
        def fail(*args): raise OSError('offline')
        core.replace_file=fail
        try:
            self.assertFalse(s.record(result(score=300)))
            self.assertEqual(list(s.personal().values())[0]['score'],300)
        finally: core.replace_file=original
        self.assertTrue(s.record(result(score=100)))
        self.assertEqual(s.read()['pbs'][core.SCORE_ATTACK],300)
    def test_future_schema_preserved(self):
        core.atomic_json(self.path,{'schema':99,'future':'keep'})
        self.assertFalse(self.store().save_best(200))
        self.assertEqual(core.read_json(self.path)['schema'],99)
    def test_invalid_results_and_profiles(self):
        r=result();r['score']=-1
        self.assertFalse(self.store().record(r))
        self.assertFalse(core.validate_profile(dict(nickname='x',country='JP',region='TOKYO')))
        self.assertTrue(core.validate_profile(dict(nickname='MORI',country='JP',region='SAITAMA')))
