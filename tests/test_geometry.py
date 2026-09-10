import unittest
from support import core

class GeometryTests(unittest.TestCase):
    def test_cardinal_edges_and_direction(self):
        for delta in ((1,0),(-1,0),(0,1),(0,-1)):
            a,b = core.wire_endpoints((2,2),(2+delta[0],2+delta[1]),20)
            if delta[0]:
                self.assertEqual(a[1],b[1])
                self.assertGreater((b[0]-a[0])*delta[0],0)
                self.assertNotEqual(a[0],50)
            else:
                self.assertEqual(a[0],b[0])
                self.assertGreater((b[1]-a[1])*delta[1],0)
                self.assertNotEqual(a[1],50)
        self.assertIsNone(core.wire_endpoints((0,0),(1,1),20))

    def test_layout_fits_minimum_and_wide_sizes(self):
        for width,height in ((360,600),(500,700),(650,600),(900,900)):
            m=core.panel_layout(width,height)
            x,y,w,h=m['board']
            self.assertGreaterEqual(x,0)
            self.assertLessEqual(x+w,width)
            self.assertLessEqual(y+h+190,height)
            self.assertEqual(w/h,.5)
            self.assertEqual(m['compact'],width<650)
