"""Fast-path tools: camera maths, box fit, component macros, coplanar lint, preview sheet."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import camera_math
import components as cm
from box_fit import solve, parse_token
from camera_fit import project as fit_project
from geometry import transform_point
from validate_spec import validate, coplanar_overlaps
from geometry import mesh_for
from preview_compare import sheet

CAM = {'projection': 'perspective', 'position': [7.0, -11.0, 6.5], 'target': [0.2, 0.3, 1.2], 'lens_mm': 42.0,
       'sensor_width_mm': 36.0, 'principal_point': [0.5, 0.5], 'pixel_aspect': [1, 1], 'fit_status': 'unfitted', 'roll_deg': 3.0}


def tiny_source(path, size=(64, 48)):
    Image.new('RGB', size, (120, 120, 120)).save(path)
    return path


class CameraMathTests(unittest.TestCase):
    def test_matches_camera_fit_projection_including_principal_point(self):
        rng = np.random.default_rng(3)
        for _ in range(20):
            cam = dict(CAM, position=list(rng.uniform([-12, -15, 2], [12, -6, 9])), roll_deg=float(rng.uniform(-8, 8)),
                       lens_mm=float(rng.uniform(20, 80)), principal_point=list(rng.uniform(0.4, 0.6, 2)))
            pts = rng.uniform([-3, -2, 0], [3, 2, 3], (6, 3))
            uv, _ = fit_project(pts, cam, 800, 450)
            for p, ref in zip(pts, uv):
                u, v, _ = camera_math.project(p.tolist(), cam, 800, 450)
                np.testing.assert_allclose([u / 800, v / 450], ref, atol=1e-9)

    def test_unproject_round_trip_on_each_axis(self):
        for p, axis in (([1.2, -0.7, 0.0], 'z'), ([0.4, 2.0, 1.5], 'y'), ([-3.9, 0.5, 2.2], 'x')):
            u, v, _ = camera_math.project(p, CAM, 738, 415)
            back = camera_math.unproject(u, v, CAM, 738, 415, axis, p['xyz'.index(axis)])
            np.testing.assert_allclose(back, p, atol=1e-9)

    def test_plane_behind_camera_is_refused(self):
        with self.assertRaises(ValueError):
            camera_math.unproject(369, 0, CAM, 738, 415, 'z', 50.0)


class BoxFitTests(unittest.TestCase):
    W, D, H, YF = 6.4, 3.2, 3.1, -0.6

    def clicks(self, cam, w=738, h=415):
        sym = {'W/2': self.W / 2, '-W/2': -self.W / 2, 'D/2': self.D / 2, '-D/2': -self.D / 2, 'H': self.H, 'F': 0.0, '?yf': self.YF}
        corners = [('tfl', ['-W/2', '-D/2', 'H']), ('tbl', ['-W/2', 'D/2', 'H']), ('tbr', ['W/2', 'D/2', 'H']),
                   ('ffl', ['-W/2', '-D/2', 'F']), ('fbr', ['W/2', 'D/2', 'F']), ('tfr', ['W/2', '-D/2', 'H']),
                   ('wall_bottom', ['W/2', '?yf', 'F']), ('wall_top', ['W/2', '?yf', 'H'])]
        pts = []
        for name, toks in corners:
            u, v, _ = camera_math.project([sym[t] for t in toks], cam, w, h)
            pts.append({'id': name, 'uv_px': [u, v], 'xyz': toks})
        return {'image': {'width': w, 'height': h}, 'known': {'D': self.D}, 'points': pts}

    def test_recovers_proportions_free_variable_and_camera(self):
        cam = dict(CAM, position=[8.0, -12.0, 7.0], target=[0.0, 0.0, 1.4], lens_mm=48.0, roll_deg=2.0)
        result = solve(self.clicks(cam), seeds=16)
        self.assertEqual(result['status'], 'fitted')
        self.assertLess(result['rms_px'], 0.05)
        self.assertAlmostEqual(result['dims_m']['W'], self.W, places=3)
        self.assertAlmostEqual(result['dims_m']['H'], self.H, places=3)
        self.assertAlmostEqual(result['free']['yf'], self.YF, places=3)
        self.assertAlmostEqual(result['camera']['lens_mm'], 48.0, places=2)
        self.assertEqual(result['dim_source']['D'], 'given')
        # The emitted camera reproduces the clicks through the Blender-consistent model.
        for p in result['points']:
            self.assertLess(p['err_px'], 0.05)

    def test_scale_must_be_anchored(self):
        data = self.clicks(CAM)
        data['known'] = {}
        with self.assertRaisesRegex(ValueError, 'NO_SCALE_ANCHOR'):
            solve(data, seeds=2)

    def test_too_few_points_is_underdetermined(self):
        data = self.clicks(CAM)
        data['points'] = data['points'][:4]
        with self.assertRaisesRegex(ValueError, 'UNDERDETERMINED'):
            solve(data, seeds=2)

    def test_token_grammar(self):
        self.assertEqual(parse_token('-W/2'), ('half', 'W', -1.0))
        self.assertEqual(parse_token(1.05), ('const', 1.05))
        self.assertEqual(parse_token('?cx'), ('free', 'cx'))
        with self.assertRaises(ValueError):
            parse_token('W/3')


def build_fixture(folder):
    return ComponentMacroTests.build(None, folder)


class ComponentMacroTests(unittest.TestCase):
    def build(self, folder):
        src = tiny_source(Path(folder) / 'source.png')
        b = cm.SpecBuilder(str(src), 64, 48, 'macro_fixture')
        b.source['image'] = 'source.png'
        b.scope('shell', 'Synthetic booth shell.')
        b.scope('furniture', 'Synthetic furniture.')
        b.exclude('hall', 'Synthetic hall.')
        b.box('floor', 'shell', 'floor', (-3, 3), (-1.5, 1.5), (0, 0.1), cm.WOOD, critical=True, px=(0, 20, 64, 48))
        b.box('back_wall', 'shell', 'back_wall', (-3, 3), (1.4, 1.5), (0.1, 3.0), cm.WHITE, critical=True, px=(0, 0, 64, 30))
        cm.counter(b, 'counter', 'furniture', (-1.0, 0.2), (-1.2, -0.6), floor_z=0.1, plinth=0.1, top_color=[0.9, 0.2, 0.3, 1], px=(10, 20, 30, 40))
        cm.round_table(b, 'table', 'furniture', 1.2, 0.3, floor_z=0.1, px=(30, 20, 40, 30))
        cm.shell_chair(b, 'chair', 'furniture', 1.8, 0.3, 90, floor_z=0.1, px=(40, 20, 50, 30))
        cm.louvre_wall(b, 'fin', 'shell', (-1.5, 0.5), (2.0, 2.4), (0.1, 2.8), 5, 0.2, [0.9, 0.15, 0.27, 1], stagger=0.08)
        cm.slats(b, 'slat', 'shell', -2.5, 0.25, 4, (-0.3, -0.2), (0.6, 2.8), 0.1, cm.WOOD)
        cm.planter(b, 'planter', 'furniture', (-2.6, -1.6), (-0.6, -0.1), floor_z=0.1, blades=6)
        cm.wall_screens(b, 'tv', 'furniture', 1.4, ((-1.0, 1.2), (1.1, 2.0)), [((-0.9, 0.0), (1.2, 1.9)), ((0.1, 1.1), (1.2, 1.9))])
        cm.shelves(b, 'shelf', 'furniture', -3.0, (-1.0, 0.0), (1.3, 1.6), backing_color=[0.9, 0.1, 0.2, 1])
        b.scale((6, 3), 'Synthetic fixture.')
        b.camera(CAM)
        b.landmark('corner', 'back_wall', [3.0, 1.4, 3.0], (60, 5))
        b.uncertain('fixture', 'Synthetic only.')
        return b

    def test_macro_booth_is_valid_without_z_fighting(self):
        with tempfile.TemporaryDirectory() as d:
            b = self.build(d)
            spec = b.write(Path(d) / 'spec.json')
            report = validate(spec, d)
            self.assertTrue(report['valid'], report['errors'][:3])
            self.assertEqual([w for w in report['warnings'] if w['code'] == 'COPLANAR_OVERLAP'], [])
            self.assertEqual(len({c['id'] for c in spec['components']}), len(spec['components']))
            self.assertTrue(any(r['component_id'] == 'floor' for r in spec['requirements']))

    def test_landmark_local_coordinates_map_back_to_world(self):
        with tempfile.TemporaryDirectory() as d:
            b = self.build(d)
            b.box('turned', 'shell', 'panel', (0, 1), (0, 0.1), (0, 1), cm.WHITE, rot=(10, 20, 30), px=(0, 0, 10, 10))
            world = [0.3, 0.2, 0.9]
            lm = b.landmark('turned_pt', 'turned', world, (5, 5))
            comp = next(c for c in b.components if c['id'] == 'turned')
            np.testing.assert_allclose(transform_point(lm['local_xyz'], comp['location'], comp['rotation_deg']), world, atol=1e-4)

    def test_tv_table_is_sixteen_by_nine(self):
        w, h = cm.TV[55]
        self.assertAlmostEqual(w / h, 16 / 9, places=2)
        self.assertAlmostEqual(math.hypot(w, h), 55 * 0.0254, places=2)


class CoplanarLintTests(unittest.TestCase):
    @staticmethod
    def box(ident, centre, size, rot=(0, 0, 0)):
        return {'id': ident, 'kind': 'box', 'location': list(centre), 'rotation_deg': list(rot), 'params': {'size': list(size)}}

    def lint(self, comps):
        return coplanar_overlaps(comps, {c['id']: mesh_for(c) for c in comps})

    def test_same_facing_overlap_is_reported(self):
        found = self.lint([self.box('wall', (0, 0, 1.5), (4, 0.2, 3)), self.box('rim', (0, 0.1, 2.9), (4, 0.6, 0.2))])
        self.assertTrue(any(f['plane'] == '+z=3' for f in found))

    def test_adjacent_and_opposite_contact_are_not_reported(self):
        found = self.lint([self.box('a', (0, 0, 0.5), (1, 1, 1)), self.box('b', (1, 0, 0.5), (1, 1, 1)),
                           self.box('c', (0, 0, 1.5), (1, 1, 1))])
        self.assertEqual(found, [])

    def test_overlap_hidden_against_another_part_is_not_reported(self):
        # Two bases overlapping on the floor slab and two backs on one wall are invisible.
        found = self.lint([self.box('floor', (0, 0, 0.05), (4, 4, 0.1)), self.box('a', (0, 0, 0.6), (1, 1, 1)),
                           self.box('b', (0.5, 0, 0.35), (1, 0.5, 0.5))])
        self.assertFalse(any(f['plane'] == '-z=0.1' for f in found))

    def test_rotated_strips_on_one_plane_do_not_false_alarm(self):
        found = self.lint([self.box('s1', (0, 0, 1), (0.02, 0.1, 2), rot=(35, 0, 0)),
                           self.box('s2', (0, 0.6, 1), (0.02, 0.1, 2), rot=(35, 0, 0))])
        self.assertEqual(found, [])


class PreviewSheetTests(unittest.TestCase):
    def test_sheet_reports_landmark_error_in_pixels(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            Image.new('RGB', (40, 30), (90, 90, 90)).save(run / 'source_reference.png')
            render = Image.new('RGBA', (40, 30), (0, 0, 0, 0))
            for x in range(10, 30):
                for y in range(5, 25):
                    render.putpixel((x, y), (200, 50, 50, 255))
            render.save(run / 'preview_render.png')
            (run / 'spec.json').write_text(json.dumps({'landmarks': [{'id': 'a', 'uv': [0.5, 0.5], 'visibility': 'visible', 'fit': True}]}))
            (run / 'projected_landmarks.json').write_text(json.dumps([{'id': 'a', 'uv': [0.6, 0.5], 'depth': 3.0}]))
            s = sheet(run)
            self.assertTrue((run / 'compare_sheet.png').is_file())
            self.assertAlmostEqual(s['landmarks'][0]['err_px'], 4.0, places=3)
            self.assertEqual(Image.open(run / 'compare_sheet.png').size, (80, 60))


@unittest.skipUnless(os.environ.get('BLENDER_EXE'), 'Set BLENDER_EXE for native preview/HD checks')
class NativeFastPathTests(unittest.TestCase):
    def run_build(self, spec, out, *extra):
        cmd = [os.environ['BLENDER_EXE'], '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
               '--python', str(ROOT / 'scripts/blender_build.py'), '--', '--spec', str(spec), '--out', str(out), *extra]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    def fixture(self, d):
        b = build_fixture(d)
        b.camera(dict(CAM, position=[7.0, -9.0, 5.0], target=[0.0, 0.0, 1.0]))
        b.write(Path(d) / 'spec.json')
        return Path(d) / 'spec.json'

    def test_preview_writes_one_matched_render_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as d:
            spec = self.fixture(d)
            out = Path(d) / 'preview'
            r = self.run_build(spec, out, '--preview')
            if r.returncode != 0 and 'EXCEPTION_ACCESS_VIOLATION' in r.stdout + r.stderr:
                r = self.run_build(spec, Path(d) / 'preview_cycles', '--preview', '--preview-engine', 'cycles')
                out = Path(d) / 'preview_cycles'
            self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-1500:])
            self.assertEqual(Image.open(out / 'preview_render.png').size, (64, 48))
            self.assertFalse((out / '.build.lock').exists())
            report = json.loads((out / 'build_report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['status'], 'preview_only')
            self.assertFalse((out / 'client_render.png').exists())

    def test_render_with_hd_scale_hashes_hd_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            spec = self.fixture(d)
            out = Path(d) / 'final'
            r = self.run_build(spec, out, '--render', '--samples', '2', '--hd-scale', '2', '--hd-samples', '2')
            self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-1500:])
            self.assertEqual(Image.open(out / 'client_render_hd.png').size, (128, 96))
            self.assertEqual(Image.open(out / 'inspection_render_hd.png').size, (128, 96))
            report = json.loads((out / 'build_report.json').read_text(encoding='utf-8'))
            self.assertIn('client_render_hd.png', {a['path'] for a in report['artifacts']})
            self.assertEqual(report['hd_scale'], 2)

    def test_preview_and_render_flags_are_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_build(self.fixture(d), Path(d) / 'x', '--preview', '--render')
            self.assertNotEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()
