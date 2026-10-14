"""Reusable spec builder and semantic component macros; standard library only.

A project script calls these with the dimensions read from its own image, so
a 100-object booth is ~40 lines instead of hand-written JSON. Macros only emit
the existing v2 primitives (box, cylinder, arc_panel ...); they add no new
kinds and carry no client answers. Defaults are generic priors in metres from
references/design-priors.md and are overridden by what the image shows.

Convention: metres, footprint centre at the origin, X right, Y back, Z up.
Colours are sRGB RGBA picked from the photo (material color_space=srgb).
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from geometry import transform_point

# Generic priors (metres). Override per image; never present them as measured.
PRIOR = {
    'wall_thickness': 0.10, 'platform': 0.10, 'counter_height': 1.05, 'counter_depth': 0.55,
    'table_height': 0.74, 'table_radius_4p': 0.45, 'seat_height': 0.45, 'bar_height': 1.10,
    'header_bottom_min': 2.40, 'tv_centre': 1.60, 'eye_height': 1.60,
}
# 16:9 picture sizes (width, height) in metres for common TV diagonals.
TV = {inch: (round(inch * 0.0254 * 16 / math.hypot(16, 9), 3), round(inch * 0.0254 * 9 / math.hypot(16, 9), 3))
      for inch in (43, 50, 55, 65, 75, 85)}

WHITE = [0.95, 0.94, 0.93, 1]
WOOD = [0.62, 0.47, 0.35, 1]
GREEN = [0.42, 0.55, 0.20, 1]
SOIL = [0.20, 0.15, 0.12, 1]
DARK_SCREEN = [0.20, 0.20, 0.22, 1]
METAL_DARK = [0.30, 0.30, 0.32, 1]


def _clamp01(v):
    return min(1.0, max(0.0, v))


def inverse_transform(world, location, rotation_deg):
    """World point -> local coordinates for a component (inverse of transform_point)."""
    x, y, z = (world[i] - location[i] for i in range(3))
    rx, ry, rz = (math.radians(a) for a in rotation_deg)
    x, y = x * math.cos(-rz) - y * math.sin(-rz), x * math.sin(-rz) + y * math.cos(-rz)
    x, z = x * math.cos(-ry) + z * math.sin(-ry), -x * math.sin(-ry) + z * math.cos(-ry)
    y, z = y * math.cos(-rx) - z * math.sin(-rx), y * math.sin(-rx) + z * math.cos(-rx)
    return [x, y, z]


class SpecBuilder:
    """Collects scope, components, landmarks and uncertainties into a v2 spec."""

    def __init__(self, source_image, width, height, project_id, sha256=None):
        path = Path(source_image)
        self.source = {'image': str(source_image),
                       'sha256': sha256 or hashlib.sha256(path.read_bytes()).hexdigest(),
                       'width': int(width), 'height': int(height)}
        self.project_id = project_id
        self.scopes, self.components, self.landmarks = {}, [], []
        self.uncertainties, self.requirements = [], []
        self.scale_block = None
        self.camera_block = None
        self._ids = set()

    # ---- metadata
    def scope(self, sid, evidence, owner='booth', decision='include'):
        self.scopes[sid] = {'id': sid, 'owner': owner, 'decision': decision, 'evidence': evidence}
        return sid

    def exclude(self, sid, evidence, owner='venue'):
        return self.scope(sid, evidence, owner=owner, decision='exclude')

    def scale(self, footprint, notes, basis='single_image_estimate'):
        self.scale_block = {'units': 'm', 'basis': basis, 'footprint_m': [float(footprint[0]), float(footprint[1])], 'notes': notes}

    def camera(self, camera):
        keys = ('projection', 'position', 'target', 'lens_mm', 'sensor_width_mm', 'ortho_scale',
                'principal_point', 'pixel_aspect', 'fit_status', 'roll_deg')
        self.camera_block = {k: camera[k] for k in keys if k in camera}

    def uncertain(self, uid, description, critical=False, status='open'):
        self.uncertainties.append({'id': uid, 'critical': critical, 'status': status, 'description': description})

    def roi(self, px):
        x0, y0, x1, y1 = px
        w, h = self.source['width'], self.source['height']
        return [round(_clamp01(x0 / w), 4), round(_clamp01(y0 / h), 4), round(_clamp01(x1 / w), 4), round(_clamp01(y1 / h), 4)]

    # ---- geometry
    def add(self, cid, scope, kind, role, centre, params, color, *, critical=False, px=None, note=None,
            inferred=False, rot=(0, 0, 0), roughness=0.55, metallic=0.0, emission=0.0, pattern=None):
        if cid in self._ids:
            raise ValueError(f'duplicate component id {cid}')
        if scope not in self.scopes:
            raise ValueError(f'unknown scope {scope}; call scope() first')
        self._ids.add(cid)
        ev = {'status': 'inferred' if inferred or px is None else 'observed',
              'note': note or ('Hidden or assumed part.' if inferred or px is None else 'Visible in the source image.')}
        if px is not None:
            ev['roi_xyxy_norm'] = self.roi(px)
        mat = {'color': [round(float(c), 4) for c in color], 'color_space': 'srgb', 'roughness': roughness, 'metallic': metallic}
        if emission:
            mat['emission'] = emission
        if pattern:
            mat['pattern'] = pattern
        comp = {'id': cid, 'scope_id': scope, 'owner': 'booth', 'kind': kind, 'role': role, 'critical': bool(critical),
                'evidence': ev, 'location': [round(float(v), 4) for v in centre],
                'rotation_deg': [round(float(v), 4) for v in rot], 'params': params, 'material': mat}
        self.components.append(comp)
        if critical:
            self.requirements.append({'id': f'keep_{cid}', 'component_id': cid, 'kind': kind, 'must_be_critical': True})
        return comp

    def box(self, cid, scope, role, x, y, z, color, *, bevel=None, **kw):
        """Axis-aligned box from (min, max) ranges; bevel=(radius, 'all'|'vertical')."""
        size = [round(x[1] - x[0], 4), round(y[1] - y[0], 4), round(z[1] - z[0], 4)]
        if min(size) <= 0:
            raise ValueError(f'{cid}: empty range {x} {y} {z}')
        params = {'size': size}
        if bevel:
            params.update(bevel_radius=bevel[0], bevel_mode=bevel[1], segments_per_corner=12)
        return self.add(cid, scope, 'box', role, [(x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2], params, color, **kw)

    def cylinder(self, cid, scope, role, x, y, z_range, radius, color, segments=48, **kw):
        h = z_range[1] - z_range[0]
        return self.add(cid, scope, 'cylinder', role, [x, y, (z_range[0] + z_range[1]) / 2],
                        {'radius': radius, 'height': round(h, 4), 'segments': segments}, color, **kw)

    def landmark(self, lid, cid, world_xyz, uv_px, fit=True, weight=None):
        comp = next(c for c in self.components if c['id'] == cid)
        local = inverse_transform(world_xyz, comp['location'], comp['rotation_deg'])
        lm = {'id': lid, 'component_id': cid, 'local_xyz': [round(v, 5) for v in local],
              'uv': [round(uv_px[0] / self.source['width'], 5), round(uv_px[1] / self.source['height'], 5)],
              'visibility': 'visible', 'fit': fit}
        if weight is not None:
            lm['weight'] = weight
        if not all(0 <= v <= 1 for v in lm['uv']):
            raise ValueError(f'{lid}: landmark must lie inside the canvas')
        self.landmarks.append(lm)
        return lm

    # ---- output
    def build(self, status='review_required', quality=None):
        if self.scale_block is None or self.camera_block is None:
            raise ValueError('call scale() and camera() before build()')
        q = quality or {'silhouette_iou_min': 0.9, 'part_iou_min': 0.85, 'landmark_median_max': 0.025,
                        'landmark_p90_max': 0.05, 'boundary_distance_max': 0.012,
                        'threshold_basis': 'Heuristic defaults; no reviewed masks or pixel acceptance are claimed.'}
        return {'schema_version': '2.0', 'project': {'id': self.project_id, 'status': status},
                'source': self.source, 'scale': self.scale_block, 'scope': {'decisions': list(self.scopes.values())},
                'components': self.components, 'camera': self.camera_block, 'requirements': self.requirements,
                'landmarks': self.landmarks, 'uncertainties': self.uncertainties, 'quality': q}

    def write(self, path, **kw):
        spec = self.build(**kw)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return spec


# ====================================================================== macros

def _lcg(seed):
    s = seed
    while True:
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        yield s / 0x7FFFFFFF


def round_table(b, prefix, scope, x, y, floor_z=0.0, radius=None, height=None, color=WHITE,
                stem_color=METAL_DARK, px=None, inferred=False):
    """Pedestal table: top disc, stem, base disc."""
    radius = radius or PRIOR['table_radius_4p']
    height = height or PRIOR['table_height']
    top = floor_z + height
    b.cylinder(f'{prefix}_top', scope, 'table', x, y, (top - 0.03, top), radius, color, segments=64, px=px, inferred=inferred, roughness=0.35)
    b.cylinder(f'{prefix}_stem', scope, 'table', x, y, (floor_z + 0.02, top - 0.03), 0.035, stem_color, segments=24,
               inferred=True, metallic=0.6, roughness=0.3, note='Pedestal stem assumed.')
    b.cylinder(f'{prefix}_base', scope, 'table', x, y, (floor_z, floor_z + 0.02), radius * 0.6, stem_color,
               inferred=True, metallic=0.6, roughness=0.3, note='Base disc assumed.')


def shell_chair(b, prefix, scope, x, y, yaw_deg, floor_z=0.0, color=WHITE, leg_color=WOOD, px=None, inferred=False,
                seat_height=None):
    """Moulded shell chair: round seat, wrap-around back (arc_panel), four splayed legs.

    yaw_deg = 0 faces -Y (towards the front aisle); positive turns anticlockwise.
    """
    sh = seat_height or PRIOR['seat_height']
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))

    def place(lx, ly):
        return x + lx * c - ly * s, y + lx * s + ly * c
    note = 'Shell chair from the visible silhouette.' if not inferred else 'Chair placement assumed (hidden).'
    sx, sy = place(0, 0)
    b.add(f'{prefix}_seat', scope, 'cylinder', 'chair', [sx, sy, floor_z + sh + 0.01], {'radius': 0.25, 'height': 0.05, 'segments': 48},
          color, rot=(0, 0, yaw_deg), px=px, inferred=inferred, note=note, roughness=0.4)
    bx, by = place(0, 0.02)
    b.add(f'{prefix}_back', scope, 'arc_panel', 'chair', [bx, by, floor_z + sh + 0.21],
          {'radius': 0.245, 'thickness': 0.035, 'height': 0.30, 'start_deg': -15, 'end_deg': 195, 'segments': 32},
          color, rot=(-10, 0, yaw_deg), px=px, inferred=inferred, note=note, roughness=0.4)
    for j, (kx, ky) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        top = (kx * 0.12, ky * 0.10, floor_z + sh - 0.01)
        bot = (kx * 0.21, ky * 0.19, floor_z)
        d = [bot[i] - top[i] for i in range(3)]
        n = math.sqrt(sum(v * v for v in d))
        dx, dy, dz = (v / n for v in d)
        mx, my = place((top[0] + bot[0]) / 2, (top[1] + bot[1]) / 2)
        b.add(f'{prefix}_leg_{j}', scope, 'cylinder', 'chair', [mx, my, (top[2] + bot[2]) / 2],
              {'radius': 0.013, 'height': round(n, 4), 'segments': 12}, leg_color,
              rot=(round(math.degrees(math.asin(-dy)), 3), round(math.degrees(math.atan2(dx, dz)), 3), yaw_deg),
              px=px, inferred=inferred, note=note, metallic=0.3, roughness=0.4)


def counter(b, prefix, scope, x, y, floor_z=0.0, height=None, body_color=WHITE, top_color=None,
            plinth=0.0, plinth_color=None, top_thickness=0.04, px=None, inferred=False, bevel=None):
    """Reception counter: optional recessed plinth, body, top slab."""
    height = height or PRIOR['counter_height']
    z0 = floor_z
    if plinth:
        b.box(f'{prefix}_plinth', scope, 'counter', (x[0] + 0.05, x[1] - 0.05), (y[0] + 0.05, y[1] - 0.05), (z0, z0 + plinth),
              plinth_color or body_color, px=px, inferred=inferred)
        z0 += plinth
    b.box(f'{prefix}_body', scope, 'counter', x, y, (z0, floor_z + height - top_thickness), body_color, px=px, inferred=inferred,
          bevel=bevel)
    b.box(f'{prefix}_top', scope, 'counter', (x[0] - 0.02, x[1] + 0.02), (y[0] - 0.02, y[1] + 0.02),
          (floor_z + height - top_thickness, floor_z + height), top_color or body_color, px=px, inferred=inferred, roughness=0.35)


def louvre_wall(b, prefix, scope, span, depth, z, count, fin_width, color, along='y', stagger=0.0, px=None, inferred=False):
    """Row of vertical fins spread over `span` (along 'y' or 'x'); `depth` is the other-axis range.

    Fins are spaced edge to edge so the first and last touch the span ends.
    `stagger` pushes every second fin back by that amount (corrugated look).
    """
    if count < 1:
        raise ValueError('louvre needs at least one fin')
    pitch = 0 if count == 1 else (span[1] - span[0] - fin_width) / (count - 1)
    for i in range(count):
        a = span[0] + i * pitch
        off = stagger if i % 2 else 0.0
        d = (depth[0] - off, depth[1] - off)
        rng = (a, a + fin_width)
        if along == 'y':
            b.box(f'{prefix}_{i}', scope, 'fin', d, rng, z, color, px=px, inferred=inferred)
        else:
            b.box(f'{prefix}_{i}', scope, 'fin', rng, d, z, color, px=px, inferred=inferred)


def slats(b, prefix, scope, first_centre, pitch, count, y, z, width, color, along='x', px=None, inferred=False):
    """Repeated vertical slats with centre spacing `pitch` (screen along X by default)."""
    for i in range(count):
        cpos = first_centre + i * pitch
        rng = (cpos - width / 2, cpos + width / 2)
        if along == 'x':
            b.box(f'{prefix}_{i}', scope, 'slat', rng, y, z, color, px=px, inferred=inferred, roughness=0.6)
        else:
            b.box(f'{prefix}_{i}', scope, 'slat', y, rng, z, color, px=px, inferred=inferred, roughness=0.6)


def planter(b, prefix, scope, x, y, floor_z=0.0, height=0.45, color=WHITE, blades=24, grass_height=(0.30, 0.55),
            seed=7, px=None, inferred=False):
    """Planter box with soil and a deterministic clump of grass blades."""
    b.box(f'{prefix}_box', scope, 'planter', x, y, (floor_z, floor_z + height), color, px=px, inferred=inferred)
    top = floor_z + height
    b.box(f'{prefix}_soil', scope, 'soil', (x[0] + 0.04, x[1] - 0.04), (y[0] + 0.04, y[1] - 0.04), (top - 0.03, top + 0.01), SOIL,
          inferred=True, note='Soil surface hidden by grass.')
    rnd = _lcg(seed)
    for i in range(blades):
        gx = x[0] + 0.07 + next(rnd) * (x[1] - x[0] - 0.14)
        gy = y[0] + 0.07 + next(rnd) * (y[1] - y[0] - 0.14)
        h = grass_height[0] + next(rnd) * (grass_height[1] - grass_height[0])
        tx, ty = (next(rnd) - 0.5) * 24, (next(rnd) - 0.5) * 24
        tone = 0.85 + 0.3 * next(rnd)
        col = [min(1, GREEN[k] * tone) for k in range(3)] + [1]
        b.add(f'{prefix}_grass_{i:02d}', scope, 'cylinder', 'grass_blade',
              [gx, gy, top + h / 2 * math.cos(math.radians(max(abs(tx), abs(ty))))],
              {'radius': 0.011, 'height': round(h, 3), 'segments': 12}, col, rot=(round(tx, 2), round(ty, 2), 0),
              inferred=True, note='Representative grass blade (count and lean are artistic).', roughness=0.7)


def wall_screens(b, prefix, scope, wall_y, frame, displays, frame_color=METAL_DARK, screen_color=DARK_SCREEN,
                 frame_depth=0.06, px=None, display_px=None, inferred=False):
    """Frame band and neutral displays on a wall whose visible face is at y=wall_y, facing -Y.

    frame = ((x0, x1), (z0, z1)); displays = list of the same; content stays neutral.
    """
    b.box(f'{prefix}_frame', scope, 'screen_frame', frame[0], (wall_y - frame_depth, wall_y), frame[1], frame_color, px=px, inferred=inferred)
    for i, (dx, dz) in enumerate(displays):
        b.box(f'{prefix}_display_{i}', scope, 'display', dx, (wall_y - frame_depth - 0.03, wall_y - frame_depth), dz, screen_color,
              px=(display_px[i] if display_px else px), inferred=inferred, roughness=0.2, emission=0.35,
              note='Display kept; media content neutralised.')


def shelves(b, prefix, scope, wall_x, y, levels, color=WHITE, depth=0.35, thickness=0.04, face='+x',
            backing_color=None, px=None, inferred=False):
    """Floating shelves on a side wall face at x=wall_x (face '+x' or '-x'), optional backing strips."""
    sgn = 1 if face == '+x' else -1
    for i, z in enumerate(levels):
        xr = sorted((wall_x, wall_x + sgn * depth))
        b.box(f'{prefix}_{i}', scope, 'shelf', xr, y, (z - thickness / 2, z + thickness / 2), color, px=px, inferred=inferred)
        if backing_color:
            br = sorted((wall_x, wall_x + sgn * 0.03))
            b.box(f'{prefix}_back_{i}', scope, 'wall_panel', br, y, (z + thickness / 2, z + thickness / 2 + 0.14), backing_color,
                  px=px, inferred=inferred)
