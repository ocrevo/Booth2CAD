"""Regenerate web/tests/fixtures/geometry_reference.json from the Python geometry builders.

The JS port (web/js/geometry.js) is tested against this file: same vertex/face counts, world bounding boxes,
coordinate sums, surface areas, signed volumes, and the same refusals (with the same messages).
Run from anywhere:  python web/tests/make_geometry_reference.py
All inputs are synthetic; no client data.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'booth-image-to-model' / 'scripts'))
from geometry import mesh_for, transform_point, triangulate  # noqa: E402
from validate_spec import PARAM_KEYS  # noqa: E402
import camera_math  # noqa: E402

S_CURVE = [[-0.5, 0.0], [-0.2, 0.0], [-0.1, 0.4], [0.2, 0.4]]
CHAIN = [[0.0, 0.0], [0.3, 0.0], [0.6, 0.0], [0.9, 0.0], [1.2, 0.0], [1.5, 0.3], [1.5, 0.6]]
L_SHAPE = [[0, 0], [1.0, 0], [1.0, 0.3], [0.3, 0.3], [0.3, 1.0], [0, 1.0]]
U_SHAPE = [[0, 0], [1.2, 0], [1.2, 0.8], [0.9, 0.8], [0.9, 0.3], [0.3, 0.3], [0.3, 0.8], [0, 0.8]]
CW_RECT = [[0, 0], [0, 0.5], [0.8, 0.5], [0.8, 0]]
COLLINEAR = [[0, 0], [0.5, 0], [1.0, 0], [1.0, 0.5], [0, 0.5]]
BOWTIE = [[0, 0], [1, 1], [1, 0], [0, 1]]

CASES = [
    ('box plain', 'box', {'size': [1.2, 0.6, 0.9]}, [0.1, -0.2, 0.45], [0, 0, 0]),
    ('box rotated', 'box', {'size': [1.2, 0.6, 0.9]}, [1.0, 2.0, 0.5], [10, 20, 30]),
    ('box bevel all', 'box', {'size': [1.0, 0.6, 0.4], 'bevel_radius': 0.05}, [0, 0, 0.2], [0, 0, 0]),
    ('box bevel all 4 segments', 'box', {'size': [1.0, 0.6, 0.4], 'bevel_radius': 0.08, 'segments_per_corner': 4}, [0, 0, 0], [0, 0, 45]),
    ('box bevel all 16 segments', 'box', {'size': [0.8, 0.8, 0.8], 'bevel_radius': 0.2, 'segments_per_corner': 16}, [0, 0, 0], [0, 0, 0]),
    ('box vertical bevel', 'box', {'size': [1.2, 0.5, 1.0], 'bevel_radius': 0.1, 'bevel_mode': 'vertical'}, [0, 0, 0.5], [0, 0, 90]),
    ('box bevel too large', 'box', {'size': [1.0, 0.4, 0.4], 'bevel_radius': 0.2}, [0, 0, 0], [0, 0, 0]),
    ('box mode without radius', 'box', {'size': [1, 1, 1], 'bevel_mode': 'vertical'}, [0, 0, 0], [0, 0, 0]),
    ('box zero dimension', 'box', {'size': [1, 0, 1]}, [0, 0, 0], [0, 0, 0]),
    ('box two dimensions', 'box', {'size': [1, 1]}, [0, 0, 0], [0, 0, 0]),
    ('cylinder default', 'cylinder', {'radius': 0.3, 'height': 0.72}, [0, 0, 0.36], [0, 0, 0]),
    ('cylinder 12 segments tilted', 'cylinder', {'radius': 0.5, 'height': 0.1, 'segments': 12}, [1, 1, 1], [90, 0, 15]),
    ('cylinder too few segments', 'cylinder', {'radius': 0.3, 'height': 0.7, 'segments': 11}, [0, 0, 0], [0, 0, 0]),
    ('rounded ring', 'rounded_ring', {'outer_size': [1.2, 0.8], 'inner_size': [0.9, 0.5], 'outer_radius': 0.2, 'inner_radius': 0.1, 'height': 0.1}, [0, 0, 2.5], [0, 0, 0]),
    ('rounded ring opening not smaller', 'rounded_ring', {'outer_size': [1.2, 0.8], 'inner_size': [1.2, 0.5], 'outer_radius': 0.2, 'inner_radius': 0.1, 'height': 0.1}, [0, 0, 0], [0, 0, 0]),
    ('rounded ring crossing', 'rounded_ring', {'outer_size': [1.2, 0.8], 'inner_size': [1.19, 0.79], 'outer_radius': 0.3, 'inner_radius': 0.05, 'height': 0.1}, [0, 0, 0], [0, 0, 0]),
    ('rounded portal', 'rounded_portal', {'width': 2.0, 'height': 2.6, 'depth': 0.3, 'side_width': 0.25, 'beam_height': 0.3, 'outer_radius': 0.4, 'inner_radius': 0.25}, [0, 0, 1.3], [0, 0, 0]),
    ('rounded portal closed', 'rounded_portal', {'width': 2.0, 'height': 2.6, 'depth': 0.3, 'side_width': 1.0, 'beam_height': 0.3, 'outer_radius': 0.4, 'inner_radius': 0.25}, [0, 0, 0], [0, 0, 0]),
    ('swept strip single curve', 'swept_strip', {'control_points': S_CURVE, 'width': 0.04, 'depth': 0.2}, [0, 0, 1], [0, 0, 0]),
    ('swept strip chain', 'swept_strip', {'control_points': CHAIN, 'width': 0.05, 'depth': 0.3, 'segments_per_curve': 12}, [0, 0, 0], [0, 0, 20]),
    ('swept strip bad point count', 'swept_strip', {'control_points': S_CURVE[:3], 'width': 0.04, 'depth': 0.2}, [0, 0, 0], [0, 0, 0]),
    ('swept strip too wide', 'swept_strip', {'control_points': S_CURVE, 'width': 2.0, 'depth': 0.2}, [0, 0, 0], [0, 0, 0]),
    ('profile L shape', 'profile_extrusion', {'profile': L_SHAPE, 'depth': 0.2}, [0, 0, 0], [0, 0, 0]),
    ('profile U shape', 'profile_extrusion', {'profile': U_SHAPE, 'depth': 0.4}, [0.5, 0.5, 0.5], [0, 0, 30]),
    ('profile clockwise rectangle', 'profile_extrusion', {'profile': CW_RECT, 'depth': 0.1}, [0, 0, 0], [0, 0, 0]),
    ('profile collinear point', 'profile_extrusion', {'profile': COLLINEAR, 'depth': 0.1}, [0, 0, 0], [0, 0, 0]),
    ('profile self-intersecting', 'profile_extrusion', {'profile': BOWTIE, 'depth': 0.1}, [0, 0, 0], [0, 0, 0]),
    ('profile repeated closing point', 'profile_extrusion', {'profile': CW_RECT + [CW_RECT[0]], 'depth': 0.1}, [0, 0, 0], [0, 0, 0]),
    ('arc panel quarter', 'arc_panel', {'radius': 1.5, 'thickness': 0.05, 'height': 2.4, 'start_deg': 0, 'end_deg': 90}, [0, 0, 1.2], [0, 0, 0]),
    ('arc panel reversed angles', 'arc_panel', {'radius': 1.0, 'thickness': 0.04, 'height': 1.0, 'start_deg': 200, 'end_deg': -40, 'segments': 24}, [0.2, 0.1, 0.5], [0, 0, 10]),
    ('arc panel full circle', 'arc_panel', {'radius': 1.0, 'thickness': 0.04, 'height': 1.0, 'start_deg': 0, 'end_deg': 360}, [0, 0, 0], [0, 0, 0]),
    ('arc panel too thick', 'arc_panel', {'radius': 0.1, 'thickness': 0.25, 'height': 1.0, 'start_deg': 0, 'end_deg': 90}, [0, 0, 0], [0, 0, 0]),
    ('unsupported kind', 'sphere', {'radius': 1}, [0, 0, 0], [0, 0, 0]),
]


def stats(kind, params, location, rotation):
    verts, faces = mesh_for({'kind': kind, 'params': params})
    world = [transform_point(v, location, rotation) for v in verts]
    tris = triangulate(faces)
    area = 0.0
    volume = 0.0
    for a, b, c in tris:
        p, q, r = world[a], world[b], world[c]
        u = [q[i] - p[i] for i in range(3)]
        w = [r[i] - p[i] for i in range(3)]
        cross = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        area += 0.5 * math.sqrt(sum(x * x for x in cross))
        volume += sum(p[i] * (q[(i + 1) % 3] * r[(i + 2) % 3] - q[(i + 2) % 3] * r[(i + 1) % 3]) for i in range(3)) / 6.0
    return {
        'vertices': len(verts), 'faces': len(faces), 'triangles': len(tris),
        'bbox_min': [min(p[i] for p in world) for i in range(3)],
        'bbox_max': [max(p[i] for p in world) for i in range(3)],
        'sum': [sum(p[i] for p in world) for i in range(3)],
        'first': world[0], 'last': world[-1],
        'index_sum': sum(sum(f) for f in faces),
        'area': area, 'volume': volume,
    }


CAMERAS = [
    ('landscape, small roll', {'projection': 'perspective', 'position': [7.0, -9.0, 5.0], 'target': [0.0, 0.0, 1.0], 'lens_mm': 42.0,
                               'sensor_width_mm': 36.0, 'principal_point': [0.5, 0.5], 'pixel_aspect': [1, 1], 'fit_status': 'unfitted', 'roll_deg': 3.0},
     960, 600),
    ('portrait, off-centre principal point', {'projection': 'perspective', 'position': [-4.0, -6.5, 2.2], 'target': [0.5, 0.5, 1.2], 'lens_mm': 28.0,
                                              'sensor_width_mm': 36.0, 'principal_point': [0.52, 0.47], 'pixel_aspect': [1, 1], 'fit_status': 'unfitted', 'roll_deg': -5.0},
     800, 1000),
    ('wide, level', {'projection': 'perspective', 'position': [0.0, -12.0, 3.0], 'target': [0.0, 0.0, 1.5], 'lens_mm': 24.0,
                     'sensor_width_mm': 36.0, 'principal_point': [0.5, 0.5], 'pixel_aspect': [1, 1], 'fit_status': 'unfitted', 'roll_deg': 0.0},
     1280, 720),
]
WORLD_POINTS = [[0, 0, 0], [3, 2.5, 0], [-3, 2.5, 3], [3, -2.5, 0.1], [-3, -2.5, 3], [1.2, -1.0, 1.05], [0, 0, 3]]


def camera_cases():
    out = []
    for name, cam, w, h in CAMERAS:
        points = []
        for point in WORLD_POINTS:
            u, v, depth = camera_math.project(point, cam, w, h)
            points.append({'world': point, 'u': u, 'v': v, 'depth': depth})
        out.append({'name': name, 'camera': cam, 'width': w, 'height': h, 'points': points})
    return out


def write_lf(path, text):
    """Python's text mode writes CRLF on Windows; the repository stores LF."""
    Path(path).write_bytes(text.encode('utf-8'))


def main():
    out = []
    for name, kind, params, location, rotation in CASES:
        case = {'name': name, 'kind': kind, 'params': params, 'location': location, 'rotation_deg': rotation}
        try:
            case['expect'] = stats(kind, params, location, rotation)
        except ValueError as ex:
            case['error'] = str(ex)
        out.append(case)
    path = HERE / 'fixtures' / 'geometry_reference.json'
    path.parent.mkdir(exist_ok=True)
    geometry_doc = {'generated_by': 'web/tests/make_geometry_reference.py',
                    'param_keys': {k: [sorted(v[0]), sorted(v[1])] for k, v in PARAM_KEYS.items()}, 'cases': out}
    write_lf(path, json.dumps(geometry_doc, indent=1) + '\n')
    camera_doc = {'generated_by': 'web/tests/make_geometry_reference.py', 'cases': camera_cases()}
    write_lf(path.parent / 'camera_reference.json', json.dumps(camera_doc, indent=1) + '\n')
    ok = sum('expect' in c for c in out)
    print(f'{len(out)} cases ({ok} meshes, {len(out) - ok} refusals) -> {path}')


if __name__ == '__main__':
    main()
