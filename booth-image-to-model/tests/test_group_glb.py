"""Optional component `group` (macros, validation, schema) and the spec-to-GLB exporter."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from jsonschema import Draft202012Validator
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import components as cm
import export_glb
from geometry import mesh_for, transform_point
from test_studio_macros import builder, studio_booth, ZF
from validate_spec import validate

SCHEMA = json.loads((ROOT / 'schemas' / 'booth-spec-v2.schema.json').read_text(encoding='utf-8'))


def read_glb_json(path):
    data = Path(path).read_bytes()
    magic, _, _ = struct.unpack('<4sII', data[:12])
    assert magic == b'glTF'
    length = struct.unpack('<I', data[12:16])[0]
    return json.loads(data[20:20 + length])


class GroupTests(unittest.TestCase):
    def test_macro_parts_share_the_macro_prefix_as_group(self):
        with tempfile.TemporaryDirectory() as d:
            b = studio_booth(d)
            by_group = {}
            for c in b.components:
                by_group.setdefault(c.get('group'), []).append(c['id'])
            self.assertEqual(sorted(k for k in by_group if k), ['counter', 'header', 'led', 'spot', 'tv'])
            self.assertEqual(by_group[None], ['floor', 'back_wall'])
            self.assertEqual(by_group['spot'], ['spot_0', 'spot_1', 'spot_2'])
            self.assertTrue(all(i.startswith('counter') for i in by_group['counter']))

    def test_grouped_block_explicit_argument_and_restore(self):
        with tempfile.TemporaryDirectory() as d:
            b = builder(d)
            b.scope('furniture', 'Synthetic fixture.')
            with b.grouped('shelf_unit'):
                b.box('shelf_a', 'furniture', 'shelf', (0, 1), (0, 0.3), (ZF, ZF + 0.5), cm.WHITE)
                with b.grouped('inner'):
                    b.box('shelf_b', 'furniture', 'shelf', (0, 1), (0, 0.3), (ZF + 0.6, ZF + 1.0), cm.WHITE)
                b.box('shelf_c', 'furniture', 'shelf', (0, 1), (0, 0.3), (ZF + 1.1, ZF + 1.5), cm.WHITE, group='override')
            b.box('loose', 'furniture', 'shelf', (2, 3), (0, 0.3), (ZF, ZF + 0.5), cm.WHITE)
            got = {c['id']: c.get('group') for c in b.components if c['id'].startswith(('shelf_', 'loose'))}
            self.assertEqual(got, {'shelf_a': 'shelf_unit', 'shelf_b': 'inner', 'shelf_c': 'override', 'loose': None})

    def test_group_is_optional_valid_and_schema_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            spec = studio_booth(d).write(Path(d) / 'spec.json')
            self.assertTrue(validate(spec, d)['valid'])
            self.assertEqual([e.message for e in Draft202012Validator(SCHEMA).iter_errors(spec)], [])
            plain = copy.deepcopy(spec)
            for c in plain['components']:
                c.pop('group', None)
            self.assertTrue(validate(plain, d)['valid'])
            self.assertEqual([e.message for e in Draft202012Validator(SCHEMA).iter_errors(plain)], [])

    def test_bad_group_values_are_rejected_by_validator_and_schema(self):
        with tempfile.TemporaryDirectory() as d:
            spec = studio_booth(d).write(Path(d) / 'spec.json')
            for bad in ('Counter', '1table', 'a-b', '', 7):
                broken = copy.deepcopy(spec)
                broken['components'][0]['group'] = bad
                self.assertFalse(validate(broken, d)['valid'], bad)
                self.assertTrue(list(Draft202012Validator(SCHEMA).iter_errors(broken)), bad)


class GlbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        b = studio_booth(self.dir)
        b.scope('graphics', 'Synthetic fixture.')
        b.add('sign_text', 'graphics', 'text', 'sign', (0.0, -1.9, 2.0), {'body': 'TEST', 'size': 0.2}, cm.WHITE)
        self.spec = b.write(self.dir / 'spec.json')
        self.glb = self.dir / 'booth.glb'
        self.report = export_glb.export_glb(self.spec, self.glb)
        self.gltf = read_glb_json(self.glb)

    def test_report_lists_what_was_not_carried_over(self):
        self.assertEqual(self.report['skipped_text'], ['sign_text'])
        self.assertEqual(self.report['pattern_omitted'], ['led_panel'])
        self.assertEqual(self.report['emission_clamped'], ['spot_0', 'spot_1', 'spot_2'])
        self.assertEqual(self.report['exported'], len(self.spec['components']) - 1)
        self.assertEqual(self.report['groups'], ['counter', 'header', 'led', 'spot', 'tv'])

    def test_nodes_follow_component_ids_and_group_parents(self):
        nodes = self.gltf['nodes']
        by_name = {n['name']: i for i, n in enumerate(nodes)}
        for c in self.spec['components']:
            if c['kind'] == 'text':
                self.assertNotIn(c['id'], by_name)
                continue
            self.assertIn(c['id'], by_name)
        parent = {child: i for i, n in enumerate(nodes) for child in n.get('children', [])}
        for c in self.spec['components']:
            if c['kind'] == 'text':
                continue
            expected = 'group:' + c['group'] if c.get('group') else 'world'
            self.assertEqual(nodes[parent[by_name[c['id']]]]['name'], expected, c['id'])

    def test_mesh_extras_carry_spec_metadata(self):
        extras = {m['extras']['component_id']: m['extras'] for m in self.gltf['meshes']}
        c = next(c for c in self.spec['components'] if c['id'] == 'tv_frame')
        self.assertEqual(extras['tv_frame'], {'component_id': 'tv_frame', 'role': c['role'], 'scope_id': c['scope_id'],
                                              'evidence': c['evidence']['status'], 'kind': 'box', 'group': 'tv'})
        self.assertNotIn('group', extras['floor'])

    def test_axes_and_winding_match_the_spec_geometry(self):
        lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
        for c in self.spec['components']:
            if c['kind'] == 'text':
                continue
            v, _ = mesh_for(c)
            w = np.array([transform_point(p, c['location'], c['rotation_deg']) for p in v])
            lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
        scene = trimesh.load(self.glb, force='scene')
        np.testing.assert_allclose(scene.bounds[0], [lo[0], lo[2], -hi[1]], atol=1e-5)
        np.testing.assert_allclose(scene.bounds[1], [hi[0], hi[2], -lo[1]], atol=1e-5)
        for name, mesh in scene.geometry.items():
            self.assertGreater(mesh.volume, 0, f'{name}: triangles wound inwards')

    def test_material_conversion(self):
        by_mesh = {}
        for mesh in self.gltf['meshes']:
            by_mesh[mesh['extras']['component_id']] = self.gltf['materials'][mesh['primitives'][0]['material']]
        floor = next(c for c in self.spec['components'] if c['id'] == 'floor')
        got = by_mesh['floor']['pbrMetallicRoughness']['baseColorFactor']
        srgb = floor['material']['color']
        want = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in srgb[:3]]
        np.testing.assert_allclose(got[:3], want, atol=1e-6)
        self.assertEqual(floor['material'].get('color_space'), 'srgb')
        self.assertTrue(all(0 <= v <= 1 for v in by_mesh['spot_0']['emissiveFactor']))
        self.assertNotIn('emissiveFactor', by_mesh['floor'])

    def test_cli_and_boothctl_export_valid_specs_and_refuse_invalid_ones(self):
        spec_file = self.dir / 'spec_file.json'
        spec_file.write_text(json.dumps(self.spec), encoding='utf-8')
        for argv, out in ((['export_glb.py'], 'a.glb'), (['boothctl.py', 'glb'], 'b.glb')):
            r = subprocess.run([sys.executable, str(ROOT / 'scripts' / argv[0]), *argv[1:], '--spec', str(spec_file),
                                '--out', str(self.dir / out)], capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)['status'], 'glb_ready')
            self.assertTrue((self.dir / out).stat().st_size > 1000)
        broken = copy.deepcopy(self.spec)
        broken['components'][0]['group'] = 'Bad Group'
        spec_file.write_text(json.dumps(broken), encoding='utf-8')
        r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'boothctl.py'), 'glb', '--spec', str(spec_file),
                            '--out', str(self.dir / 'c.glb')], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)['status'], 'invalid_spec')
        self.assertFalse((self.dir / 'c.glb').exists())


if __name__ == '__main__':
    unittest.main()
