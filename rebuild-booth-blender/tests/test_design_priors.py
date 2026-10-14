"""The machine-readable priors stay in step with the documented values and the macro defaults."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import components as cm
from design_check import load_priors

JSON_PATH = ROOT / 'schemas' / 'design-priors.v1.json'
DOC = (ROOT / 'references' / 'design-priors.md').read_text(encoding='utf-8')


class DesignPriorsTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(JSON_PATH.read_text(encoding='utf-8'))
        self.priors = load_priors()

    def test_entries_are_well_formed_and_unreviewed(self):
        ids = [e['id'] for e in self.data['entries']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.data['unit'], 'm')
        for e in self.data['entries']:
            self.assertIn(e['kind'], ('value', 'range', 'choice', 'table'), e['id'])
            self.assertIs(e['reviewed'], False, e['id'])
            if e['kind'] == 'value':
                self.assertGreater(e['value'], 0, e['id'])
            if e['kind'] == 'range':
                self.assertLess(0, e['min'])
                self.assertLess(e['min'], e['max'], e['id'])
                self.assertTrue(e.get('default', e['min']) >= e['min'] and e.get('default', e['max']) <= e['max'], e['id'])

    def test_each_source_points_at_an_existing_heading(self):
        for e in self.data['entries']:
            path, _, heading = e['source'].partition('#')
            self.assertEqual(path, 'references/design-priors.md', e['id'])
            self.assertIn('## ' + heading, DOC, f"{e['id']}: heading {heading!r} not found in design-priors.md")

    def test_no_internal_rule_identifiers(self):
        text = JSON_PATH.read_text(encoding='utf-8') + DOC
        import re
        self.assertEqual(re.findall(r'\b(?:N|OVH|CAB|MED|SPC|FLR|WAL|GRA|FUR|LGT|CON|BRF|TYP|CMP|BLD|REG|CDT|RND|STY|LNG)-\d{2}\b', text), [])

    def test_macro_defaults_agree_with_the_priors(self):
        mapping = {'wall_thickness': 'wall_thickness', 'counter_height': 'counter_height_standing', 'counter_depth': 'counter_depth',
                   'table_height': 'round_table_height', 'seat_height': 'seat_height', 'bar_height': 'bar_height',
                   'header_bottom_min': 'header_band_bottom_min', 'tv_centre': 'tv_centre_height', 'eye_height': 'render_eye_height'}
        for key, pid in mapping.items():
            e = self.priors[pid]
            v = cm.PRIOR[key]
            if e['kind'] == 'range':
                self.assertTrue(e['min'] - 1e-9 <= v <= e['max'] + 1e-9, f'{key}={v} outside {pid} {e["min"]}-{e["max"]}')
            else:
                self.assertAlmostEqual(v, e['value'], places=6, msg=key)

    def test_tv_table_agrees_with_listed_sizes(self):
        for inch, (w, h) in self.priors['tv_picture_sizes']['sizes_m'].items():
            mw, mh = cm.TV[int(inch)]
            self.assertAlmostEqual(mw / w, 1.0, delta=0.03, msg=inch)
            self.assertAlmostEqual(mh / h, 1.0, delta=0.03, msg=inch)

    def test_design_check_imports_only_the_standard_library(self):
        code = ("import sys\nsys.path.insert(0," + repr(str(ROOT / 'scripts')) + ")\n"
                "import design_check\nassert not any(name in sys.modules for name in ('PIL','numpy','scipy','jsonschema','trimesh'))\n")
        r = subprocess.run([sys.executable, '-B', '-S', '-c', code], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
