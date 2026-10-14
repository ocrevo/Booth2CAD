"""Studio macros (header band, TV, LED wall, spotlights): geometry, lint and advisory checks."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import components as cm
from design_check import run as design_run
from geometry import mesh_for
from validate_spec import validate, coplanar_overlaps

CAM = {'projection': 'perspective', 'position': [7.0, -9.0, 5.0], 'target': [0.0, 0.0, 1.0], 'lens_mm': 42.0,
       'sensor_width_mm': 36.0, 'principal_point': [0.5, 0.5], 'pixel_aspect': [1, 1], 'fit_status': 'unfitted', 'roll_deg': 3.0}
CTX = {'height_limit_m': 4.0, 'hanging_allowed': False, 'open_sides': ['front'], 'led_module_m': 0.5}
ZF = 0.1


def builder(folder):
    src = Path(folder) / 'source.png'
    Image.new('RGB', (64, 48), (120, 120, 120)).save(src)
    b = cm.SpecBuilder(str(src), 64, 48, 'studio_macros')
    for sid in ('shell', 'media'):
        b.scope(sid, 'Synthetic fixture.')
    b.box('floor', 'shell', 'floor', (-3, 3), (-2, 2), (0, ZF), cm.WOOD, critical=True, px=(0, 20, 64, 48))
    b.box('back_wall', 'shell', 'back_wall', (-3, 3), (1.9, 2.0), (ZF, 3.0), cm.WHITE, critical=True, px=(0, 0, 64, 30))
    b.scale((6, 4), 'Synthetic fixture.')
    b.camera(CAM)
    b.uncertain('fixture', 'Synthetic only.')
    return b


def studio_booth(folder):
    b = builder(folder)
    for sid in ('furniture', 'lighting'):
        b.scope(sid, 'Synthetic fixture.')
    cm.header_band(b, 'header', 'shell', [(-2.0, 1.2), (-2.0, -1.5), (2.0, -1.5), (2.0, 1.2)], 0.45, (2.5, 3.1),
                   posts=[(-2.0, 1.0), (2.0, 1.0)], floor_z=ZF, px=(0, 0, 64, 20))
    cm.tv(b, 'tv', 'media', 1.9, -1.0, 55, bezel=0.02, depth=0.05, px=(10, 10, 30, 25))
    cm.led_wall(b, 'led', 'media', 1.9, 0.5, 0.3, cols=2, rows=3, module=0.5, depth=0.12, px=(30, 10, 50, 30))
    cm.spotlights(b, 'spot', 'lighting', [(-1.5, -1.5), (0.0, -1.5), (1.5, -1.5)], 2.5, px=(10, 5, 50, 12))
    cm.counter(b, 'counter', 'furniture', (-1.0, 0.8), (-1.5, -0.95), floor_z=ZF, px=(10, 30, 30, 45))
    return b


def fingerprint(components):
    """Hash of the geometry-bearing fields; the optional editing `group` is additive and left out."""
    plain = [{k: v for k, v in c.items() if k != 'group'} for c in components]
    return hashlib.sha256(json.dumps(plain, sort_keys=True).encode()).hexdigest()


class StudioMacroTests(unittest.TestCase):
    def test_existing_macro_output_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            b.scope('s', 'e')
            b.components.clear()
            b._ids.clear()
            cm.shell_chair(b, 'chair', 's', 1.5, -0.5, -40, floor_z=0.1, px=(1, 1, 5, 5))
            self.assertEqual(fingerprint(b.components),
                             '9641ccd321cedf7dfacd7db0e6ca06684813d90594f77bdae67c2c6e08844302')
            b.components.clear()
            b._ids.clear()
            cm.round_table(b, 't', 's', 0.5, 0.5, floor_z=0.1)
            cm.counter(b, 'c', 's', (0, 1.5), (0, 0.5), floor_z=0.1)
            self.assertEqual(fingerprint(b.components),
                             '1ed2aeeccf24073bacc81aa098a5e46f85670d8956dc5687c1a4e7630387a02d')

    def test_studio_booth_is_valid_without_overlaps_or_advisory_findings(self):
        with tempfile.TemporaryDirectory() as d:
            spec = studio_booth(d).write(Path(d) / 'spec.json')
            report = validate(spec, d)
            self.assertTrue(report['valid'], report['errors'][:3])
            self.assertEqual([w for w in report['warnings'] if w['code'] == 'COPLANAR_OVERLAP'], [])
            result = design_run(spec, CTX)
            self.assertEqual([f for f in result['findings'] if f['level'] == 'advisory'], [], result['findings'])
            self.assertEqual(result['not_checked'], [])
            for name in ('header_band', 'display_size', 'led_whole_modules', 'counter_dimensions', 'support_path'):
                self.assertIn(name, result['checks_run'])

    def test_header_band_u_shape_has_three_runs_and_touching_posts(self):
        with tempfile.TemporaryDirectory() as d:
            b = studio_booth(d)
            runs = [c for c in b.components if c['role'] == 'header_band']
            posts = [c for c in b.components if c['role'] == 'header_post']
            self.assertEqual(len(runs), 3)
            self.assertEqual(len(posts), 2)
            for p in posts:
                self.assertAlmostEqual(p['location'][2] - p['params']['size'][2] / 2, ZF, places=6)
                self.assertAlmostEqual(p['location'][2] + p['params']['size'][2] / 2, 2.5, places=6)

    def test_header_band_rejects_diagonal_and_degenerate_paths(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            with self.assertRaises(ValueError):
                cm.header_band(b, 'h', 'shell', [(0, 0), (1, 1)], 0.4, (2.5, 3.0))
            with self.assertRaises(ValueError):
                cm.header_band(b, 'h', 'shell', [(0, 0), (0, 0)], 0.4, (2.5, 3.0))
            with self.assertRaises(ValueError):
                cm.header_band(b, 'h', 'shell', [(0, 0), (2, 0)], 0.4, (3.0, 2.5))

    def test_tv_uses_the_standard_picture_size_and_sits_proud(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            cm.tv(b, 'tv', 'media', 1.9, 0.0, 55, bezel=0.02, depth=0.05)
            frame = next(c for c in b.components if c['id'] == 'tv_frame')
            disp = next(c for c in b.components if c['id'] == 'tv_display')
            w, h = cm.TV[55]
            self.assertAlmostEqual(disp['params']['size'][0], round(w, 4), places=3)
            self.assertAlmostEqual(disp['params']['size'][2], round(h, 4), places=3)
            self.assertAlmostEqual(disp['location'][2], cm.PRIOR['tv_centre'], places=3)
            front_frame = frame['location'][1] - frame['params']['size'][1] / 2
            front_disp = disp['location'][1] - disp['params']['size'][1] / 2
            self.assertGreater(front_frame - front_disp, 0.002)
            self.assertEqual(frame['role'], 'screen_frame')
            self.assertEqual(disp['role'], 'display')

    def test_tv_rejects_unknown_class_and_needs_bezel_and_depth(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            with self.assertRaises(ValueError):
                cm.tv(b, 'tv', 'media', 1.9, 0.0, 58, bezel=0.02, depth=0.05)
            with self.assertRaises(TypeError):
                cm.tv(b, 'tv', 'media', 1.9, 0.0, 55)

    def test_tv_on_a_side_wall_faces_along_x(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            cm.tv(b, 'tv', 'media', -2.9, 0.0, 50, bezel=0.02, depth=0.05, face='+x')
            frame = next(c for c in b.components if c['id'] == 'tv_frame')
            self.assertAlmostEqual(frame['params']['size'][0], 0.05, places=6)

    def test_led_wall_is_whole_modules_with_aligned_seams(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            cm.led_wall(b, 'led', 'media', 1.9, 0.0, 0.3, cols=3, rows=2, module=0.498, depth=0.1)
            panel = next(c for c in b.components if c['id'] == 'led_panel')
            self.assertAlmostEqual(panel['params']['size'][0], 3 * 0.498, places=4)
            self.assertAlmostEqual(panel['params']['size'][2], 2 * 0.498, places=4)
            pat = panel['material']['pattern']
            self.assertEqual(pat['spacing'], [0.498, 0.498])
            self.assertAlmostEqual(pat['offset'][0], 0.249, places=6)     # odd column count: seams sit half a module off the centre
            self.assertAlmostEqual(pat['offset'][1], 0.0, places=6)       # even row count: a seam crosses the centre

    def test_led_wall_rejects_fractional_or_missing_modules(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            with self.assertRaises(ValueError):
                cm.led_wall(b, 'led', 'media', 1.9, 0.0, 0.3, cols=2.5, rows=2, module=0.5, depth=0.1)
            with self.assertRaises(ValueError):
                cm.led_wall(b, 'led', 'media', 1.9, 0.0, 0.3, cols=2, rows=0, module=0.5, depth=0.1)
            with self.assertRaises(TypeError):
                cm.led_wall(b, 'led', 'media', 1.9, 0.0, 0.3, cols=2, rows=2)

    def test_design_check_flags_a_half_module_led_wall(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            cm.led_wall(b, 'led', 'media', 1.9, 0.0, 0.3, cols=2, rows=2, module=0.5, depth=0.1)
            spec = b.build()
            spec['components'][-1]['params']['size'][0] = 1.25      # 2.5 modules
            result = design_run(spec, CTX)
            self.assertTrue(any(f['check'] == 'led_whole_modules' for f in result['findings']))

    def test_spotlights_are_emissive_bodies_without_a_cone(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            b.scope('lighting', 'Synthetic fixture.')
            cm.spotlights(b, 'spot', 'lighting', [(0, 0), (1.5, 0)], 2.5)
            self.assertEqual(len(b.components) - 2, 2)
            spots = [c for c in b.components if c['role'] == 'spotlight']
            self.assertTrue(all(c['kind'] == 'cylinder' and c['material']['emission'] > 0 for c in spots))
            self.assertAlmostEqual(spots[0]['location'][2] + spots[0]['params']['height'] / 2, 2.5, places=6)


@unittest.skipUnless(os.environ.get('BLENDER_EXE'), 'Set BLENDER_EXE for the native studio-macro preview')
class NativeStudioMacroTests(unittest.TestCase):
    @staticmethod
    def build(spec, out, *extra):
        cmd = [os.environ['BLENDER_EXE'], '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
               '--python', str(ROOT / 'scripts/blender_build.py'), '--', '--spec', str(spec), '--out', str(out), '--preview', *extra]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    def test_studio_booth_builds_a_preview(self):
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / 'spec.json'
            studio_booth(d).write(spec)
            out = Path(d) / 'preview'
            r = self.build(spec, out)
            if r.returncode != 0 and 'EXCEPTION_ACCESS_VIOLATION' in r.stdout + r.stderr:    # integrated-GPU driver crash
                out = Path(d) / 'preview_cycles'
                r = self.build(spec, out, '--preview-engine', 'cycles')
            self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-1500:])
            self.assertEqual(Image.open(out / 'preview_render.png').size, (64, 48))


if __name__ == '__main__':
    unittest.main()
