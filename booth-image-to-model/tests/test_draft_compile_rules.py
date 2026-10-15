"""Regression tests for the defects an independent review found in the scene-description compiler (one test per defect)."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import components as cm
import draft_compile as dc
import test_draft_compile as t


def comp(s, cid):
    return next(c for c in s['components'] if c['id'] == cid)


def add(s, **kw):
    s['components'].append(t.part(**kw))
    return s


class Fixed(t.Base):
    def spec_part(self, spec, cid):
        return next(c for c in spec['components'] if c['id'] == cid)

    def refused(self, s, **kw):
        with self.assertRaises(dc.SceneError) as ctx:
            dc.compile_scene(s, self.image, self.dir / 'refused', **kw)
        return ctx.exception.errors


class CrashesBecameResults(Fixed):
    def test_a_critical_uncertainty_compiles_and_is_listed(self):
        spec, report = self.compile()                   # the fixture carries a critical uncertainty
        self.assertTrue(report['valid'])
        self.assertIn('OPEN_CRITICAL_UNCERTAINTY hidden_structure', report['warnings'])

    def test_geometry_the_builder_refuses_drops_the_part(self):
        s = add(t.scene(), id='tiny', type='box', scope='shell', base_px=t.px(0.0, 0.0, t.ZF), size_m=[0.3, 0.3, None], z_range_m=[t.ZF, 1.0],
                bevel_m=0.2, critical=True)
        spec, report = self.compile(s, 'refused_geometry')
        self.assertEqual(report['status'], 'partial')
        self.assertTrue(report['valid'])
        self.assertEqual([d['id'] for d in report['dropped']], ['tiny'])
        self.assertIn('bevel', report['dropped'][0]['reason'])
        self.assertNotIn('tiny', {c['id'] for c in spec['components']})
        self.assertNotIn('keep_tiny', {r['id'] for r in spec['requirements']})

    def test_a_dropped_part_leaves_no_notes_behind(self):
        s = add(t.scene(), id='ribs2', type='louvre_wall', scope='shell', base_px=t.px(-2.0, -1.0, t.ZF), base_px_2=t.px(-2.0, 1.0, t.ZF), count=30,
                width_m=0.1, height_m=2.0)
        spec, report = self.compile(s, 'dropped_notes')
        self.assertEqual([d['id'] for d in report['dropped']], ['ribs2'])
        self.assertIn('do not fit', report['dropped'][0]['reason'])
        self.assertFalse([a for a in report['assumed'] if a['id'] == 'ribs2'])
        self.assertNotIn('ribs2', ' '.join(u['description'] for u in spec['uncertainties']))

    def test_an_unknown_height_is_a_scene_error(self):
        s = t.scene()
        s['known']['H'] = None
        s['corner_points'] = [p for p in s['corner_points'] if p['xyz'][2] == 'F']
        errors = self.refused(s)
        self.assertEqual(errors[0]['code'], 'DIMENSION')
        self.assertIn('H is unknown', errors[0]['message'])

    def test_a_short_size_is_a_shape_error_not_an_exception(self):
        s = t.scene()
        comp(s, 'post')['size_m'] = [0.3, 0.3]
        errors = dc.validate_scene(s)
        self.assertTrue(any(e['code'] == 'SHAPE' and e['where'].endswith('size_m') for e in errors))

    def test_whole_number_floats_are_accepted_and_the_rest_refused(self):
        s = t.scene()
        comp(s, 'ribs')['count'] = 5.0
        spec, report = self.compile(s, 'float_count')
        self.assertEqual(len([c for c in spec['components'] if c['id'].startswith('ribs_')]), 5)
        for key, value, code in (('count', 2.5, 'SCHEMA'), ('count', 100000, 'SHAPE'), ('yaw_deg', float('nan'), 'SHAPE')):
            s = t.scene()
            comp(s, 'ribs' if key == 'count' else 'chair')[key] = value
            self.assertIn(code, self.codes(s), (key, value))
        s = t.scene()
        s['floor_z'] = float('inf')
        self.assertIn('DIMENSION', self.codes(s))

    def test_a_missing_image_or_a_non_image_is_a_scene_error(self):
        bogus = self.dir / 'not_an_image.png'
        bogus.write_text('this is not a picture', encoding='utf-8')
        for path in (bogus, self.dir / 'missing.png'):
            with self.assertRaises(dc.SceneError) as ctx:
                dc.compile_scene(t.scene(), path, self.dir / 'bad_image', fit=copy.deepcopy(self.fit))
            self.assertEqual(ctx.exception.errors[0]['code'], 'IMAGE')


class PlacementDefects(Fixed):
    def test_the_floor_is_never_moved_by_the_coplanar_fix(self):
        s = add(t.scene(), id='edge_post', type='box', scope='shell', base_px=t.px(2.85, -2.0, t.ZF), size_m=[0.3, 0.3, None],
                z_range_m=[0.0, 2.5], bevel_m=0.05, bevel_mode='vertical', color_hex='#ed6617')
        spec, report = self.compile(s, 'floor_kept')
        self.assertTrue(report['valid'], report['validation_errors'])
        self.assertEqual(self.spec_part(spec, 'floor')['params']['size'][:2], [t.W, t.D])
        self.assertTrue(any('edge_post' in w['ids'] for w in report['coplanar_unresolved']), report['coplanar_unresolved'])

    def test_a_turned_box_is_clamped_with_its_turned_extent(self):
        s = add(t.scene(), id='bar', type='box', scope='shell', base_px=t.px(-2.85, 0.0, t.ZF), size_m=[2.0, 0.2, None], yaw_deg=90,
                z_range_m=[t.ZF, 1.0])
        spec, report = self.compile(s, 'turned_box')
        bar = self.spec_part(spec, 'bar')
        self.assertAlmostEqual(bar['location'][0], -2.85, delta=0.04)
        self.assertFalse([a for a in report['adjustments'] if a['id'] == 'bar'], report['adjustments'])

    def test_a_counter_turned_by_90_swaps_width_and_depth_and_odd_angles_warn(self):
        plain, _ = self.compile(name='counter_plain')
        s = t.scene()
        comp(s, 'counter')['yaw_deg'] = 90
        turned, _ = self.compile(s, 'counter_turned')
        a, b = self.spec_part(plain, 'counter_body')['params']['size'], self.spec_part(turned, 'counter_body')['params']['size']
        self.assertEqual((a[0], a[1]), (b[1], b[0]))
        s = t.scene()
        comp(s, 'counter')['yaw_deg'] = 45
        _, report = self.compile(s, 'counter_odd')
        self.assertTrue(any('counter yaw 45' in w for w in report['warnings']), report['warnings'])

    def test_a_single_fin_is_centred_on_the_marked_row(self):
        s = t.scene()
        comp(s, 'ribs')['count'] = 1
        spec, _ = self.compile(s, 'one_fin')
        fin = self.spec_part(spec, 'ribs_0')
        self.assertAlmostEqual(fin['location'][1], 0.0, delta=0.05)

    def test_a_crooked_louvre_row_is_reported(self):
        s = t.scene()
        comp(s, 'ribs')['base_px_2'] = t.px(3.0, 1.0, t.ZF)
        _, report = self.compile(s, 'crooked')
        self.assertTrue(any('degrees off the nearest booth axis' in w for w in report['warnings']), report['warnings'])

    def test_a_louvre_row_beyond_the_booth_is_trimmed_and_recorded(self):
        s = t.scene()
        comp(s, 'ribs')['base_px'] = t.px(2.0, -2.9, t.ZF)
        spec, report = self.compile(s, 'trimmed_row')
        self.assertTrue(any(a['id'] == 'ribs' and 'trimmed' in a['what'] for a in report['adjustments']), report['adjustments'])
        lowest = min(c['location'][1] - c['params']['size'][1] / 2 for c in spec['components'] if c['id'].startswith('ribs_'))
        self.assertGreaterEqual(lowest, -t.D / 2 - 1e-6)

    def test_a_tv_and_an_led_wall_slide_back_inside_the_booth_edge(self):
        face = t.D / 2 - 0.1
        tv_w, tv_h = cm.TV[55]
        s = t.scene()
        comp(s, 'tv')['wall_rect_px'] = t.px(2.9 - tv_w / 2 - 0.02, face, 1.6 + tv_h / 2 + 0.02) + t.px(2.9 + tv_w / 2 + 0.02, face, 1.6 - tv_h / 2 - 0.02)
        comp(s, 'led')['wall_rect_px'] = t.px(1.8, face, 1.8) + t.px(3.3, face, 0.8)
        spec, report = self.compile(s, 'slid')
        frame = self.spec_part(spec, 'tv_frame')
        self.assertLessEqual(frame['location'][0] + frame['params']['size'][0] / 2, t.W / 2 + 1e-6)
        led = self.spec_part(spec, 'led_panel')
        self.assertLessEqual(led['location'][0] + led['params']['size'][0] / 2, t.W / 2 + 1e-6)
        moved = [a['id'] for a in report['adjustments'] if 'moved along the wall' in a['what']]
        self.assertEqual(sorted(moved), ['led', 'tv'])

    def test_a_tv_that_does_not_match_its_class_is_reported(self):
        s = t.scene()
        comp(s, 'tv')['inch'] = 85
        _, report = self.compile(s, 'tv_class')
        self.assertTrue(any(w.startswith('tv: a 85-inch class tv') for w in report['warnings']), report['warnings'])

    def test_a_shallow_roof_frame_still_builds(self):
        s = t.scene()
        comp(s, 'frame').update(inset_m=1.6, width_m=None, radius_m=None)      # the compiler's own defaults: band 0.6, radius 0.8
        spec, report = self.compile(s, 'shallow')                              # outer 2.8 x 1.8 m, opening 1.6 x 0.6 m
        self.assertEqual(report['dropped'], [])
        ring = self.spec_part(spec, 'frame')
        self.assertEqual(ring['params']['outer_size'], [2.8, 1.8])
        self.assertAlmostEqual(ring['params']['inner_radius'], 0.28, places=3)     # clamped below half the short side of the opening

    def test_walls_and_the_other_planes(self):
        """wall, wall_panel and tv on all four booth edges land where the known world points were."""
        face = lambda plane: {'back': ('y', t.D / 2 - 0.1), 'front': ('y', -t.D / 2 + 0.1), 'left': ('x', -t.W / 2 + 0.1), 'right': ('x', t.W / 2 - 0.1)}[plane]
        for plane in ('back', 'front', 'left', 'right'):
            axis, value = face(plane)
            along = (-0.8, 0.8)
            world = (lambda a, z: (a, value, z)) if axis == 'y' else (lambda a, z: (value, a, z))
            rect = t.px(*world(along[0], 1.8)) + t.px(*world(along[1], 0.8))
            if rect[0] > rect[2]:
                rect = [rect[2], rect[1], rect[0], rect[3]]
            s = t.scene()
            s['components'] = [c for c in s['components'] if c['id'] in ('post',)]
            add(s, id='panel', type='wall_panel', scope='shell', plane=plane, wall_rect_px=rect, thickness_m=0.05)
            add(s, id='screen', type='tv', scope='media', plane=plane, inch=43, bezel_m=0.02, depth_m=0.05, wall_rect_px=rect)
            spec, report = self.compile(s, f'plane_{plane}')
            panel = self.spec_part(spec, 'panel')
            k = 0 if axis == 'y' else 1
            n = 1 - k                                           # index of the coordinate across the wall
            self.assertAlmostEqual(panel['location'][k], 0.0, delta=0.06, msg=plane)
            inward = -1 if plane in ('back', 'right') else 1
            self.assertAlmostEqual(panel['location'][n], value + inward * 0.025, delta=0.03, msg=plane)      # body extends into the room
            self.assertAlmostEqual(panel['params']['size'][k], 1.6, delta=0.15, msg=plane)
            display = self.spec_part(spec, 'screen_display')
            frame = self.spec_part(spec, 'screen_frame')
            side = (display['location'][n] - frame['location'][n]) * inward
            self.assertGreater(side, 0, f'{plane}: the display must sit proud of the frame, on the room side')
            self.assertAlmostEqual(display['location'][2], 1.3, delta=0.05, msg=plane)

    def test_a_wall_marked_beyond_the_edge_is_dropped_with_its_requirement(self):
        s = t.scene()
        wall = comp(s, 'back_wall')
        wall.update(base_px=t.px(3.4, 2.5, t.ZF), base_px_2=t.px(3.9, 2.5, t.ZF))
        spec, report = self.compile(s, 'wall_gone')
        self.assertEqual([d['id'] for d in report['dropped']], ['back_wall'])
        self.assertNotIn('back_wall', {c['id'] for c in spec['components']})
        self.assertNotIn('keep_back_wall', {r['id'] for r in spec['requirements']})

    def test_floor_landmarks_follow_their_own_tokens(self):
        s = t.scene()
        s['corner_points'].append({'id': 'odd', 'uv_px': t.px(t.D / 2, -t.W / 2, t.ZF), 'xyz': ['D/2', '-W/2', 'F']})
        spec, report = dc.compile_scene(s, self.image, self.dir / 'odd_landmark')
        lm = next(x for x in spec['landmarks'] if x['id'] == 'odd')
        self.assertAlmostEqual(lm['local_xyz'][0], t.D / 2, places=3)
        self.assertAlmostEqual(lm['local_xyz'][1], -t.W / 2, places=3)


class RecordKeeping(Fixed):
    def test_every_prior_the_compiler_fills_is_recorded(self):
        _, report = self.compile()
        recorded = {(a['id'], a['what']) for a in report['assumed']}
        for key in (('table', 'radius_m'), ('table', 'height_m'), ('counter', 'depth_m'), ('counter', 'height_m'), ('plant', 'height_m'),
                    ('chair', 'seat_height_m'), ('lamps', 'fixture body'), ('ribs', 'thickness_m'), ('back_wall', 'thickness_m')):
            self.assertIn(key, recorded)

    def test_height_m_is_honoured_for_a_counter_and_not_recorded_as_assumed(self):
        s = t.scene()
        comp(s, 'counter').update(height_m=1.2)
        spec, report = self.compile(s, 'tall_counter')
        top = self.spec_part(spec, 'counter_top')
        self.assertAlmostEqual(top['location'][2] + top['params']['size'][2] / 2, t.ZF + 1.2, places=3)
        self.assertNotIn(('counter', 'height_m'), {(a['id'], a['what']) for a in report['assumed']})

    def test_all_assumed_values_reach_the_spec(self):
        s = t.scene()
        for i in range(30):
            add(s, id=f'stool{i:02d}', type='planter', scope='furniture', base_px=t.px(-2.5 + (i % 6) * 0.1, -1.0 + (i // 6) * 0.2, t.ZF))
        spec, report = self.compile(s, 'many_assumed')
        text = next(u['description'] for u in spec['uncertainties'] if u['id'] == 'compile_assumed_values')
        self.assertGreater(len(report['assumed']), 25)
        self.assertIn('more (see compile_report.json)', text)

    def test_fields_a_type_does_not_read_are_reported(self):
        s = t.scene()
        comp(s, 'counter')['critical'] = True
        comp(s, 'counter')['note'] = 'ignored'
        add(s, id='drum', type='cylinder', scope='furniture', base_px=t.px(0.0, 1.0, t.ZF), radius_m=0.3, height_m=0.5, bevel_m=0.05)
        _, report = self.compile(s, 'ignored')
        self.assertIn('counter: critical is not used by type counter and was ignored', report['warnings'])
        self.assertIn('counter: note is not used by type counter and was ignored', report['warnings'])
        self.assertIn('drum: bevel_m is not used by type cylinder and was ignored', report['warnings'])

    def test_a_part_outside_the_footprint_is_found(self):
        spec, _ = self.compile()
        self.assertEqual(dc.outside_footprint(spec), [])
        moved = copy.deepcopy(spec)
        next(c for c in moved['components'] if c['id'] == 'counter_body')['location'][0] += 10
        self.assertEqual([i for i, _ in dc.outside_footprint(moved)], ['counter_body'])


class GivenFitAndFiles(Fixed):
    def test_a_given_fit_must_agree_with_the_scene(self):
        for label, change, expect in (
                ('image size', lambda f: f['image'].update(width=640), 'image'),
                ('known width', lambda f: f['dims_m'].update(W=8.0), 'known.W'),
                ('floor height', lambda f: f.update(floor_z=0.0), 'floor_z'),
                ('no camera', lambda f: f.pop('camera'), 'camera'),
                ('no height', lambda f: f['dims_m'].pop('H'), 'H is unknown')):
            fit = copy.deepcopy(self.fit)
            change(fit)
            errors = self.refused(t.scene(), fit=fit)
            self.assertTrue(any(expect in e['message'] for e in errors), (label, errors))
            self.assertTrue(all(e['code'] == 'FIT_MISMATCH' for e in errors), (label, errors))

    def test_a_blocked_or_empty_fit_is_refused(self):
        errors = self.refused(t.scene(), fit={'status': 'blocked', 'reason': 'no seed converged'})
        self.assertEqual((errors[0]['code'], errors[0]['message']), ('FIT_FAILED', 'no seed converged'))
        errors = self.refused(t.scene(), fit={})
        self.assertTrue(errors and all(e['code'] == 'FIT_MISMATCH' for e in errors))
        self.assertTrue(any('camera' in e['message'] for e in errors))

    def test_scale_checks_run_with_a_fresh_fit_and_are_flagged_when_a_fit_is_given(self):
        s = t.scene()
        s['scale_checks'] = [{'id': 'counter_check', 'base_px': t.px(1.0, -1.2, t.ZF), 'top_px': t.px(1.0, -1.2, t.ZF + 1.05),
                              'expected_height_m': 3.0, 'tolerance': None}]
        _, fresh = dc.compile_scene(s, self.image, self.dir / 'checks_fresh')
        self.assertTrue(any('scale' in w.lower() and w.startswith('fit:') for w in fresh['warnings']), fresh['warnings'])
        _, given = self.compile(s, 'checks_given')
        self.assertIn('scale_checks were not evaluated: a given fit was used (drop --fit to run them)', given['warnings'])

    def test_compiling_again_from_the_output_folder_works(self):
        out = self.dir / 'again'
        dc.compile_scene(t.scene(), self.image, out, fit=copy.deepcopy(self.fit))
        (out / 'source.jpg').write_bytes(b'stale')
        spec, report = dc.compile_scene(t.scene(), out / 'source.png', out, fit=copy.deepcopy(self.fit))
        self.assertTrue(report['valid'])
        self.assertFalse((out / 'source.jpg').exists())

    def test_a_refused_scene_leaves_the_folder_exactly_as_it_was(self):
        out = self.dir / 'untouched'
        dc.compile_scene(t.scene(), self.image, out, fit=copy.deepcopy(self.fit))
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        bad = t.scene()
        comp(bad, 'counter')['evidence'] = 'observed'
        comp(bad, 'counter')['roi_px'] = None
        with self.assertRaises(dc.SceneError):
            dc.compile_scene(bad, self.image, out, fit=copy.deepcopy(self.fit))
        self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)

    def test_a_failure_late_in_the_compile_writes_nothing(self):
        from unittest import mock
        existing = self.dir / 'late_existing'
        dc.compile_scene(t.scene(), self.image, existing, fit=copy.deepcopy(self.fit))
        before = {p.name: p.read_bytes() for p in existing.iterdir()}
        fresh = self.dir / 'late_fresh'
        with mock.patch.object(dc, 'validate', side_effect=RuntimeError('boom')):
            for out in (existing, fresh):
                with self.assertRaises(RuntimeError):
                    dc.compile_scene(t.scene(), self.image, out, fit=copy.deepcopy(self.fit))
        self.assertEqual({p.name: p.read_bytes() for p in existing.iterdir()}, before)
        self.assertFalse(fresh.exists())

    def test_run_reports_input_problems_instead_of_tracebacks(self):
        scene_file = self.dir / 'scene_io.json'
        scene_file.write_text(json.dumps(t.scene()), encoding='utf-8')
        code, summary = dc.run(self.dir / 'nope.json', self.image, self.dir / 'io_out')
        self.assertEqual((code, summary['status']), (2, 'input_error'))
        broken = self.dir / 'broken.json'
        broken.write_text('{not json', encoding='utf-8')
        code, summary = dc.run(broken, self.image, self.dir / 'io_out')
        self.assertEqual((code, summary['status']), (2, 'input_error'))
        code, summary = dc.run(scene_file, self.dir / 'missing.png', self.dir / 'io_out')
        self.assertEqual((code, summary['status']), (2, 'scene_invalid'))
        self.assertEqual(summary['errors'][0]['code'], 'IMAGE')


class SceneRuleCoverage(Fixed):
    def test_each_new_rule_has_a_rejecting_and_an_accepting_case(self):
        names = [c['id'] for c in t.scene()['components']]
        cases = []
        s = t.scene(); s['corner_points'].append(dict(s['corner_points'][0])); cases.append(('POINT', s, 'duplicate corner ids'))
        s = t.scene(); s['scopes'][0]['evidence'] = ' '; cases.append(('SCOPE', s, 'empty scope evidence'))
        s = t.scene(); s['scopes'].append({'id': 'booth_floor', 'decision': 'exclude', 'owner': 'venue', 'evidence': 'x'}); cases.append(('SCOPE', s, 'floor scope excluded'))
        s = t.scene(); comp(s, 'counter')['roi_px'] = [2000, 2000, 2100, 2100]; cases.append(('PIXEL', s, 'roi outside the image'))
        s = t.scene(); comp(s, 'back_wall')['base_px'] = [100.0, 500.0]; cases.append(('MISSING', s, 'wall with only one end'))
        s = t.scene(); comp(s, 'table')['radius_m'] = 0; cases.append(('SHAPE', s, 'zero radius'))
        s = t.scene(); s['uncertainties'][0]['description'] = ''; cases.append(('UNCERTAINTY', s, 'empty uncertainty'))
        s = t.scene(); s['components'] = s['components'] * 50; cases.append(('LIMIT', s, 'too many components'))
        for code, scene_, why in cases:
            self.assertIn(code, self.codes(scene_), why)
        accepted = t.scene()
        add(accepted, id='tvstand', type='box', scope='furniture', base_px=t.px(-2.0, 2.0, t.ZF), size_m=[1.0, 0.4, 0.5], z_range_m=[t.ZF, 0.5])
        self.assertEqual(dc.validate_scene(accepted), [])
        self.assertIn(len(names), (11,))

    def test_the_schema_enum_the_handlers_and_the_docs_agree(self):
        enum = set(t.SCHEMA['properties']['components']['items']['properties']['type']['enum'])
        self.assertEqual(enum, set(dc.USED))
        for name in enum:
            self.assertTrue(callable(getattr(dc.Compiler, name, None)), name)
        doc = (ROOT / 'references' / 'scene-description.md').read_text(encoding='utf-8')
        for name in enum:
            self.assertIn(f'`{name}`', doc, name)
        for name, used in dc.USED.items():
            self.assertTrue(dc.COMMON <= used, name)
            self.assertTrue(used <= set(t.NULLS), (name, used - set(t.NULLS)))

    def test_the_schema_only_uses_keywords_every_strict_provider_accepts(self):
        allowed = {'$schema', 'title', 'description', 'type', 'enum', 'properties', 'required', 'items', 'additionalProperties'}

        def walk(node, path='$'):
            if isinstance(node, dict):
                if 'properties' in node:                        # a properties map: its keys are field names, not keywords
                    self.assertTrue(set(node) - {'properties'} <= allowed, path)
                    for k, v in node['properties'].items():
                        walk(v, f'{path}.{k}')
                    for k in set(node) - {'properties'}:
                        walk(node[k], f'{path}.{k}')
                else:
                    self.assertTrue(set(node) <= allowed | {'properties'}, (path, set(node) - allowed))
                    for k, v in node.items():
                        if isinstance(v, (dict, list)) and k not in ('enum', 'type', 'required'):
                            walk(v, f'{path}.{k}')
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f'{path}[{i}]')
        walk(t.SCHEMA)


if __name__ == '__main__':
    unittest.main()
