"""Write the synthetic regression example used by the tests: examples/regression/.

Everything is invented, not taken from any client picture: a generic 8 x 5 m stand with a rounded top ring, a rounded portal and a
round display, seen by an invented camera; the picture is drawn by projecting those invented parts. It keeps the shape of a
half-finished candidate on purpose (unfitted camera, open critical uncertainties), so the tests can check that an unfinished
candidate is never reported as finished. No client picture, brand or measured dimension.

    python booth-image-to-model/tests/make_regression_example.py
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from camera_fit import project  # noqa: E402

OUT = ROOT / 'examples' / 'regression'
W, H = 640, 480
LEGACY_SIZE = (320, 240)
PANEL = [0.8, 0.8, 0.8, 1]
CARPET = [0.3, 0.35, 0.4, 1]
CAMERA = {'projection': 'perspective', 'position': [-7.0, -8.0, 1.8], 'target': [0, 0, 1.6], 'lens_mm': 28,
          'sensor_width_mm': 36, 'principal_point': [0.5, 0.5], 'pixel_aspect': [1, 1], 'fit_status': 'unfitted', 'roll_deg': 0}


def write_json(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def half_extents(kind, p):
    if kind == 'box': return [v / 2 for v in p['size']]
    if kind == 'rounded_ring': return [p['outer_size'][0] / 2, p['outer_size'][1] / 2, p['height'] / 2]
    if kind == 'rounded_portal': return [p['width'] / 2, p['depth'] / 2, p['height'] / 2]
    if kind == 'cylinder': return [p['radius'], p['radius'], p['height'] / 2]
    raise ValueError(kind)


def projected(c):
    """Image points (normalised, y down) of the corners of a part's box; the example camera sees every part."""
    hx, hy, hz = half_extents(c['kind'], c['params'])
    x, y, z = c['location']
    corners = [[x + sx * hx, y + sy * hy, z + sz * hz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    uv, depth = project(corners, CAMERA, W, H)
    assert (depth > 0).all() and ((uv > 0) & (uv < 1)).all(), c['id']
    return [tuple(map(float, p)) for p in uv], float(depth.mean())


def hull(points):
    points = sorted(set(points))
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for seq, out in ((points, lower), (points[::-1], upper)):
        for p in seq:
            while len(out) >= 2 and cross(out[-2], out[-1], p) <= 0: out.pop()
            out.append(p)
    return lower[:-1] + upper[:-1]


def roi(c):
    uv = projected(c)[0]
    return [round(min(p[0] for p in uv), 3), round(min(p[1] for p in uv), 3),
            round(max(p[0] for p in uv), 3), round(max(p[1] for p in uv), 3)]


def picture(path, size, components, label):
    """Flat synthetic drawing of the invented parts, far to near; open parts (ring, portal) are drawn as outlines."""
    w, h = size
    img = Image.new('RGB', size, (96, 104, 120))
    d = ImageDraw.Draw(img)
    for c in sorted(components, key=lambda c: -projected(c)[1]):
        shape = [(u * w, v * h) for u, v in hull(projected(c)[0])]
        colour = tuple(int(255 * v) for v in c['material']['color'][:3])
        if c['kind'] in ('rounded_ring', 'rounded_portal'): d.polygon(shape, outline=colour, width=max(2, h // 60))
        else: d.polygon(shape, fill=colour, outline=(60, 64, 72))
    d.text((8, h - 16), label, fill=(20, 22, 26))
    img.save(path)


def part(ident, kind, role, critical, location, params, material=PANEL):
    c = {'id': ident, 'scope_id': ident, 'owner': 'booth', 'kind': kind, 'role': role, 'critical': critical,
         'evidence': {'status': 'observed', 'roi_xyxy_norm': None, 'note': 'Synthetic regression part; invented size.'},
         'location': location, 'rotation_deg': [0, 0, 0], 'params': params,
         'material': {'color': material, 'roughness': 0.5, 'metallic': 0, 'emission': 0}}
    c['evidence']['roi_xyxy_norm'] = roi(c)
    return c


def px(c):
    r = c['evidence']['roi_xyxy_norm']
    return [round(r[0] * W), round(r[1] * H), round(r[2] * W), round(r[3] * H)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    components = [
        part('booth_carpet', 'box', 'floor', False, [0, 0, 0.01], {'size': [8, 5, 0.02]}, CARPET),
        part('top_ring', 'rounded_ring', 'fascia', True, [0, 0, 3.3],
             {'outer_size': [7.0, 4.0], 'inner_size': [5.6, 2.8], 'outer_radius': 1.0, 'inner_radius': 0.5, 'height': 0.6,
              'segments_per_corner': 16}),
        part('main_portal', 'rounded_portal', 'portal', True, [1.2, 0.3, 1.42],
             {'width': 2.6, 'height': 2.8, 'depth': 0.3, 'side_width': 0.35, 'beam_height': 0.35, 'outer_radius': 0.5,
              'inner_radius': 0.2, 'segments_per_corner': 16}),
        part('rear_wall', 'box', 'wall', True, [0, 2.3, 1.22], {'size': [3.0, 0.15, 2.4]}),
        part('round_display', 'cylinder', 'counter', True, [-1.8, -1.2, 0.47], {'radius': 0.5, 'height': 0.9, 'segments': 64}),
        part('round_display_top', 'cylinder', 'counter', False, [-1.8, -1.2, 0.945], {'radius': 0.55, 'height': 0.05, 'segments': 64}),
        part('reception', 'box', 'counter', False, [2.8, -2.0, 0.62], {'size': [1.6, 0.5, 1.2]}),
        part('storage', 'box', 'cabinet', False, [-3.2, 1.9, 1.02], {'size': [1.0, 0.5, 2.0]}),
    ]
    reference = OUT / 'reference.png'
    picture(reference, (W, H), components, 'synthetic regression picture')
    picture(OUT / 'legacy_proxy.png', LEGACY_SIZE, components, 'synthetic older preview (different canvas)')
    sha = hashlib.sha256(reference.read_bytes()).hexdigest()
    parts = {c['id']: c for c in components}

    decisions = [{'id': c['id'], 'owner': 'booth', 'decision': 'include', 'evidence': 'Synthetic regression part.'} for c in components]
    decisions += [
        {'id': 'venue_ceiling', 'owner': 'venue', 'decision': 'exclude', 'evidence': 'Hall ceiling seen through the open ring; not part of the booth.'},
        {'id': 'neighbor_signs', 'owner': 'neighbor', 'decision': 'exclude', 'evidence': 'Other stands in the distance.'},
        {'id': 'aisle_ground', 'owner': 'venue', 'decision': 'exclude', 'evidence': 'Ground outside the booth carpet.'},
    ]
    spec = {
        'schema_version': '2.0',
        'project': {'id': 'synthetic-regression-candidate', 'status': 'draft_not_image_matched'},
        'source': {'image': reference.name, 'sha256': sha, 'width': W, 'height': H},
        'scale': {'units': 'm', 'basis': 'user_assumption', 'footprint_m': [8, 5],
                  'notes': 'Synthetic: 8 x 5 m is an invented candidate scale, not measured.'},
        'scope': {'decisions': decisions},
        'components': components,
        'camera': dict(CAMERA),
        'requirements': [
            {'id': 'ring_is_continuous', 'component_id': 'top_ring', 'kind': 'rounded_ring', 'must_be_critical': True},
            {'id': 'portal_round_transition', 'component_id': 'main_portal', 'kind': 'rounded_portal', 'must_be_critical': True},
            {'id': 'round_counter_exists', 'component_id': 'round_display', 'kind': 'cylinder', 'must_be_critical': True},
        ],
        'landmarks': [],
        'uncertainties': [
            {'id': 'portal_topology', 'critical': True, 'status': 'open',
             'description': 'How the portal joins the ring is not settled; the candidate must not be reported as finished.'},
            {'id': 'scale', 'critical': False, 'status': 'open', 'description': 'Dimensions are invented.'},
            {'id': 'graphics_and_products', 'critical': True, 'status': 'open',
             'description': 'Screens, graphics and products are left out until the structure is accepted.'},
        ],
        'quality': {'silhouette_iou_min': 0.9, 'part_iou_min': 0.85, 'landmark_median_max': 0.025, 'landmark_p90_max': 0.05,
                    'boundary_distance_max': 0.012,
                    'threshold_basis': 'Initial project heuristics, not industry standards or a calibrated fidelity percentage. '
                                       'Tune against reviewed masks and multiple held-out examples.'},
    }
    write_json(OUT / 'candidate_spec.json', spec)
    write_json(OUT / 'legacy_spec.json', {
        'project': 'synthetic legacy booth (pre-v2 format)', 'units': 'm', 'source': 'synthetic picture; invented dimensions',
        'scope': {'include': ['platform', 'upper rounded fascia', 'portal', 'rear wall', 'round counter'],
                  'exclude': ['hall ceiling', 'hall lighting', 'neighbouring stands']},
        'assumptions': {'footprint': [8.0, 5.0], 'platform_thickness': 0.08, 'maximum_height': 3.6},
        'dimensions': {'platform': {'size': [8.0, 5.0, 0.08], 'location': [0.0, 0.0, 0.04]},
                       'upper_ring': {'size': [7.0, 4.0, 0.6], 'corner_radius_visual': 1.0}}})
    write_json(OUT / 'observations.json', {
        'source_sha256': sha, 'image_size': [W, H], 'review_status': 'draft', 'reviewer': None,
        'reference_status': 'synthetic picture; manual 2D observations only; not ground-truth 3D',
        'priority_observations': [
            {'id': 'ring', 'roi_xyxy_px': px(parts['top_ring']), 'visible_fact': 'Rounded outer contour and a real central opening; do not fill the opening.'},
            {'id': 'portal', 'roi_xyxy_px': px(parts['main_portal']), 'visible_fact': 'Rounded bands; how they join the ring needs review.'},
            {'id': 'circle', 'roi_xyxy_px': px(parts['round_display']), 'visible_fact': 'A solid round display, not an open tube.'},
        ],
        'hard_exclusions': ['ceiling', 'hall lamps', 'neighbouring stands', 'ground outside the booth carpet'],
        'silhouette': {'mask': None, 'valid_mask': None}, 'parts': {},
        'notes': 'No invented masks or 3D anchor labels. Deliberately incomplete; final QA must block until valid annotations exist.'})
    write_json(OUT / 'annotations.template.json', {
        'source_sha256': sha, 'review_status': 'pending', 'reviewer': None,
        'silhouette': {'mask': 'masks/booth_visible.png', 'valid_mask': 'masks/valid.png'},
        'parts': {name: {'mask': f'masks/{name}_visible.png', 'valid_mask': 'masks/valid.png'}
                  for name in ('top_ring', 'main_portal', 'rear_wall', 'round_display')}})
    print('wrote', OUT)


if __name__ == '__main__':
    main()
