import os
import unittest
from support import core


class LocationTests(unittest.TestCase):
    def test_country_labels_cover_existing_protocol_codes(self):
        self.assertEqual(set(core.COUNTRY_CODES),set(core.COUNTRY_LABELS))
        self.assertEqual(core.country_label('JP'),'Japan')
        self.assertEqual(core.country_label('US'),'United States')

    def test_all_japan_prefectures_have_distinct_codes(self):
        self.assertEqual(len(core.JAPAN_REGIONS),47)
        self.assertEqual(set(code for code,label in core.JAPAN_REGIONS),
                         set('JP-{0:02d}'.format(i) for i in range(1,48)))
        self.assertEqual(core.region_label('JP','JP-11'),'Saitama')
        self.assertEqual(core.region_label('JP','JP-13'),'Tokyo')
        self.assertEqual(core.region_label('JP','TOKYO'),'Tokyo')
        self.assertEqual(core.region_label('JP','SAITAMA-KEN'),'Saitama')
        for code,label in core.JAPAN_REGIONS:
            self.assertTrue(core.validate_profile(dict(nickname='MORI',country='JP',region=code)))

    def test_unknown_and_optional_regions_do_not_change_wire_values(self):
        self.assertEqual(core.canonical_region('JP','CUSTOM'),'CUSTOM')
        self.assertEqual(core.region_label('JP','JP-99'),'Saved region')
        self.assertEqual(core.region_label('US','NEW YORK'),'New York')
        self.assertEqual(core.area_label('US','-'),'United States')
        self.assertTrue(core.validate_profile(dict(nickname='MORI',country='US',region='-')))

    def test_disabled_or_cancelled_folder_probe_has_no_io(self):
        original=core.os.path.isdir
        def unexpected(*args):raise AssertionError('Unexpected folder I/O')
        core.os.path.isdir=unexpected
        try:
            self.assertEqual(core.studio_folder_status(False,'/share')['status'],'Offline')
            self.assertEqual(core.studio_folder_status(True,'/share',lambda:True)['status'],'Offline')
        finally:core.os.path.isdir=original

    def test_folder_probe_reports_permissions_and_disconnect(self):
        isdir,access=core.os.path.isdir,core.os.access
        try:
            core.os.path.isdir=lambda path:True
            core.os.access=lambda path,mode:True
            self.assertEqual(core.studio_folder_status(True,os.path.abspath('share'))['status'],'Available')
            core.os.access=lambda path,mode:mode==os.R_OK
            self.assertEqual(core.studio_folder_status(True,os.path.abspath('share'))['status'],'Read only')
            core.os.path.isdir=lambda path:False
            self.assertIn('Error',core.studio_folder_status(True,os.path.abspath('share'))['status'])
        finally:
            core.os.path.isdir,core.os.access=isdir,access
