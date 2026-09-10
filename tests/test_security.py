import ast
import os
import unittest
from support import core
from build import build
from test_settings import result

class SecurityTests(unittest.TestCase):
    def test_host_api_surface_is_panel_registration_only(self):
        tree=ast.parse(build().encode('utf-8'))
        attributes=[n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='nuke']
        self.assertEqual(attributes,[])
        imports=set()
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):imports.update(a.name for a in n.names)
        self.assertFalse(imports.intersection({'socket','subprocess','requests','urllib','psutil'}))
        source=build()
        for forbidden in ('installEventFilter(', 'addOnCreate(', 'addKnobChanged(', 'addUpdateUI(', 'QShortcut(', 'listen(', 'gethostname(', 'environ['):
            self.assertNotIn(forbidden,source)

    def test_untrusted_profile_values_never_raise(self):
        for value in (None,[],1,{},dict(nickname=1,country='JP',region='SAITAMA'),
                      dict(nickname='MORI',country='ZZ',region='TOKYO')):
            self.assertFalse(core.validate_profile(value))

    def test_impossible_lines_and_scores_rejected(self):
        for changes in (dict(lines=40,pieces=10),dict(score=100000000,pieces=1),dict(score=True),dict(time_ms=float('nan'))):
            r=result();r.update(changes)
            self.assertFalse(core.valid_result(r))

    def test_studio_cancelled_before_dispatch_has_no_io(self):
        s=core.StudioRanking(True,'not-a-folder','a'*32,{},lambda:True)
        self.assertFalse(s.publish(result()))
        self.assertFalse(s.read(core.SCORE_ATTACK)['ok'])

    def test_generated_distribution_matches_sources(self):
        import io
        with io.open(os.path.join(os.path.dirname(os.path.dirname(__file__)),'nukeris.py'),encoding='utf-8') as f:
            self.assertEqual(f.read(),build())
