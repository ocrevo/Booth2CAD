"""Fit the source camera and the booth box proportions from a few clicked corners.

Requires numpy/scipy. Usually the first modelling step: 6-10 reviewed corner
clicks give camera pose, focal length and the booth W/D/H in about a second,
instead of reading the whole layout by eye.

points.json:
{
  "image": {"width": 1280, "height": 720},
  "known": {"D": 3.0},          # any of W (x), D (y), H (top z); measured or assumed
  "assumed": ["D"],             # names in `known` that are assumptions, not client facts
  "floor_z": 0.1,               # z of the walking surface (default 0)
  "points": [
    {"id": "top_front_left", "uv_px": [140, 95], "xyz": ["-W/2", "-D/2", "H"]},
    {"id": "wall_front_bottom", "uv_px": [910, 520], "xyz": ["W/2", "?yf", "F"]},
    {"id": "counter_top", "uv_px": [420, 380], "xyz": ["?cx", "?cy", 1.05]}
  ]
}
Coordinate tokens: a number; 0; W/2, -W/2, D/2, -D/2; H; F (floor_z); ?name for
a free unknown shared by every point that uses it. Origin is the footprint
centre, X right, Y back, Z up, metres (the v2 spec convention). Pixel corners
may lie slightly outside the canvas when extrapolated; give them lower weight.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import numpy as np
from scipy.optimize import least_squares
from common import read_json, write_json
import camera_math

DIMS = ('W', 'D', 'H')
TOKEN = re.compile(r'^\s*([+-]?)\s*(W|D)\s*/\s*2\s*$|^\s*(H|F)\s*$|^\s*\?([A-Za-z_][A-Za-z0-9_]*)\s*$')
SENSOR_MM = 36.0


def parse_token(token):
    """-> ('const', v) | ('half', dim, sign) | ('dim', 'H') | ('floor',) | ('free', name)."""
    if isinstance(token, bool):
        raise ValueError('boolean is not a coordinate')
    if isinstance(token, (int, float)):
        if not math.isfinite(token):
            raise ValueError('non-finite coordinate')
        return ('const', float(token))
    if not isinstance(token, str):
        raise ValueError(f'bad coordinate token: {token!r}')
    try:
        return ('const', float(token))
    except ValueError:
        pass
    m = TOKEN.match(token)
    if not m:
        raise ValueError(f'bad coordinate token: {token!r}; use number, W/2, -D/2, H, F or ?name')
    if m.group(2):
        return ('half', m.group(2), -1.0 if m.group(1) == '-' else 1.0)
    if m.group(3) == 'H':
        return ('dim', 'H')
    if m.group(3) == 'F':
        return ('floor',)
    return ('free', m.group(4))


def _forward(yaw, pitch):
    return np.array([-math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), -math.sin(pitch)])


def _camera_dict(pos, yaw, pitch, roll, focal, width, distance):
    fwd = _forward(yaw, pitch)
    return {'projection': 'perspective', 'position': [round(float(v), 5) for v in pos],
            'target': [round(float(v), 5) for v in pos + fwd * distance],
            'lens_mm': round(float(focal / width * SENSOR_MM), 4), 'sensor_width_mm': SENSOR_MM,
            'principal_point': [0.5, 0.5], 'pixel_aspect': [1, 1], 'fit_status': 'landmark_fitted',
            'roll_deg': round(math.degrees(roll), 4)}


class Problem:
    def __init__(self, data):
        img = data.get('image') or {}
        self.width, self.height = int(img['width']), int(img['height'])
        if self.width <= 0 or self.height <= 0:
            raise ValueError('image width/height must be positive')
        self.floor_z = float(data.get('floor_z', 0.0))
        known = data.get('known') or {}
        for k in known:
            if k not in DIMS:
                raise ValueError(f'unknown dimension {k!r}; use W, D or H')
            if not (isinstance(known[k], (int, float)) and known[k] > 0):
                raise ValueError(f'known {k} must be a positive number')
        self.known = {k: float(v) for k, v in known.items()}
        self.assumed = list(data.get('assumed') or [])
        pts = data.get('points') or []
        if len(pts) < 4:
            raise ValueError('need at least 4 points; 6-10 spread over near/far and top/bottom is better')
        self.points, frees, numeric_scale = [], [], False
        for p in pts:
            toks = [parse_token(t) for t in p['xyz']]
            if len(toks) != 3:
                raise ValueError(f"{p.get('id')}: xyz needs three tokens")
            for t in toks:
                if t[0] == 'free' and t[1] not in frees:
                    frees.append(t[1])
                if t[0] == 'const' and abs(t[1]) > 1e-9:
                    numeric_scale = True
            w = float(p.get('weight', 1.0))
            if not (math.isfinite(w) and w > 0):
                raise ValueError(f"{p.get('id')}: weight must be positive")
            self.points.append({'id': p['id'], 'uv': np.asarray(p['uv_px'], float), 'tokens': toks, 'weight': w})
        self.free_dims = [d for d in DIMS if d not in self.known and any(
            (t[0] == 'half' and t[1] == d) or (t[0] == 'dim' and t[1] == d) for p in self.points for t in p['tokens'])]
        self.frees = frees
        if not self.known and not numeric_scale:
            raise ValueError('NO_SCALE_ANCHOR: give a known W/D/H or a point with a measured coordinate '
                             '(e.g. counter top z=1.05); an assumed value must be listed in "assumed"')
        self.n_unknown = 7 + len(self.free_dims) + len(self.frees)
        if 2 * len(self.points) < self.n_unknown + 1:
            raise ValueError(f'UNDERDETERMINED: {len(self.points)} points for {self.n_unknown} unknowns; add corners')

        # Every coordinate is linear in (W, D, H, free...): world = C @ v + b.
        k = 3 + len(self.frees)
        self.C = np.zeros((len(self.points), 3, k))
        self.b = np.zeros((len(self.points), 3))
        for i, p in enumerate(self.points):
            for j, t in enumerate(p['tokens']):
                if t[0] == 'const':
                    self.b[i, j] = t[1]
                elif t[0] == 'half':
                    self.C[i, j, DIMS.index(t[1])] = t[2] / 2
                elif t[0] == 'dim':
                    self.C[i, j, 2] = 1.0
                elif t[0] == 'floor':
                    self.b[i, j] = self.floor_z
                else:
                    self.C[i, j, 3 + self.frees.index(t[1])] = 1.0
        self.uv = np.asarray([p['uv'] for p in self.points])
        self.sqrt_w = np.sqrt([p['weight'] for p in self.points])[:, None]

    def values(self, x):
        dims = dict(self.known)
        for i, d in enumerate(self.free_dims):
            dims[d] = x[7 + i]
        free = {n: x[7 + len(self.free_dims) + i] for i, n in enumerate(self.frees)}
        return dims, free

    def all_world(self, x):
        dims, free = self.values(x)
        v = np.array([dims.get(d, 0.0) for d in DIMS] + [free[n] for n in self.frees])
        return self.C @ v + self.b

    def project(self, x, world):
        pos, yaw, pitch, roll, f = x[0:3], x[3], x[4], x[5], x[6]
        fwd = _forward(yaw, pitch)
        right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        c, s = math.cos(roll), math.sin(roll)
        r2, u2 = c * right + s * up, c * up - s * right
        d = world - pos
        z = d @ fwd
        zs = np.maximum(z, 1e-3)
        return np.c_[self.width / 2 + f * (d @ r2) / zs, self.height / 2 - f * (d @ u2) / zs], z

    def residual(self, x):
        uv, z = self.project(x, self.all_world(x))
        return np.r_[((uv - self.uv) * self.sqrt_w).ravel(), np.maximum(0, 0.3 - z) * 100]


def ambiguous_dims(spread, dims, free_dims, tol=0.05):
    """Fitted dimensions whose value varies by more than tol (relative) across equally good solutions."""
    return [d for d in free_dims if spread.get(d, 0.0) > tol * dims[d]]


def ambiguity_hint(names):
    if not names:
        return None
    parts = {'W': 'a point on a known plane at the far left/right end', 'D': 'a known depth or a point on the front/back edge',
             'H': 'a point whose z is numeric (a hidden-base tie, a counter top at a standard height) or a known height'}
    return 'Not constrained by the clicks: ' + ', '.join(names) + '. Add ' + '; '.join(parts[n] for n in names) + ', or give the value as known/assumed.'


def solve(data, seeds=40, rng_seed=1):
    pb = Problem(data)
    rng = np.random.default_rng(rng_seed)
    size_guess = max(list(pb.known.values()) + [4.0])
    lo = [-300, -300, -50, -4 * math.pi, -math.radians(30), -math.radians(45), 0.3 * pb.width]
    hi = [300, 300, 300, 4 * math.pi, math.radians(89), math.radians(45), 8.0 * pb.width]
    lo += [0.3] * len(pb.free_dims) + [-100] * len(pb.frees)
    hi += [80] * len(pb.free_dims) + [100] * len(pb.frees)
    sols = []
    for _ in range(seeds):
        yaw = rng.uniform(-math.pi, math.pi)
        pitch = math.radians(rng.uniform(5, 50))
        dist = size_guess * rng.uniform(1.5, 6)
        pos = -_forward(yaw, pitch) * dist + np.array([0, 0, size_guess * 0.4])
        x0 = list(pos) + [yaw, pitch, 0.0, pb.width * rng.uniform(0.7, 2.5)]
        x0 += [size_guess * rng.uniform(0.5, 2.0) for _ in pb.free_dims] + [rng.uniform(-1, 1) for _ in pb.frees]
        x0 = np.clip(x0, np.array(lo) + 1e-6, np.array(hi) - 1e-6)
        try:
            r = least_squares(pb.residual, x0, bounds=(lo, hi), max_nfev=600)
        except (ValueError, FloatingPointError):
            continue
        sols.append(r)
    if not sols:
        raise ValueError('FIT_FAILED: no seed converged')
    best = min(sols, key=lambda r: r.cost)
    x = best.x
    dims, free = pb.values(x)
    world = pb.all_world(x)
    centre = world.mean(axis=0)
    distance = float(np.linalg.norm(centre - x[0:3]))
    camera = _camera_dict(x[0:3], x[3], x[4], x[5], x[6], pb.width, distance)
    per_point, errs = [], []
    for i, p in enumerate(pb.points):
        try:
            u, v, _ = camera_math.project(world[i].tolist(), camera, pb.width, pb.height)
        except ValueError:
            u = v = float('nan')
        e = float(math.hypot(u - p['uv'][0], v - p['uv'][1]))
        errs.append(e)
        per_point.append({'id': p['id'], 'uv_px': p['uv'].tolist(), 'fitted_px': [round(u, 2), round(v, 2)],
                          'err_px': round(e, 2), 'world_xyz': [round(float(c), 4) for c in world[i]]})
    good = [r for r in sols if r.cost <= best.cost * 1.5 + 1.0]
    spread = {}
    for i, d in enumerate(pb.free_dims):
        vals = [r.x[7 + i] for r in good]
        spread[d] = round(float(max(vals) - min(vals)), 4)
    fvals = [r.x[6] for r in good]
    spread['lens_mm'] = round(float((max(fvals) - min(fvals)) / pb.width * SENSOR_MM), 3)
    ambiguous = bool(ambiguous_dims(spread, dims, pb.free_dims)) or len(good) < 3
    rms = float(math.sqrt(np.mean(np.square(errs))))
    return {
        'status': 'ambiguous' if ambiguous else 'fitted',
        'rms_px': round(rms, 3), 'max_px': round(float(max(errs)), 3),
        'dims_m': {d: round(float(dims[d]), 4) for d in DIMS if d in dims},
        'dim_source': {d: ('assumed' if d in pb.assumed else 'given') if d in pb.known else 'fitted' for d in DIMS if d in dims},
        'free': {k: round(float(v), 4) for k, v in free.items()},
        'image': {'width': pb.width, 'height': pb.height}, 'floor_z': pb.floor_z,
        'ambiguous_dims': ambiguous_dims(spread, dims, pb.free_dims), 'ambiguity_hint': ambiguity_hint(ambiguous_dims(spread, dims, pb.free_dims)),
        'camera': camera, 'points': per_point,
        'solution_spread': spread, 'converged_seeds': len(good), 'seeds': seeds,
        'note': 'Proportions and pose come from the clicked corners; absolute size only from known/assumed values. '
                'Review the reprojection before building; this is not a measurement.'}


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--points', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--assume', action='append', default=[], help='NAME=VALUE for W/D/H; recorded as assumed')
    p.add_argument('--seeds', type=int, default=40)
    a = p.parse_args()
    data = read_json(a.points)
    for item in a.assume:
        name, _, value = item.partition('=')
        data.setdefault('known', {})[name.strip()] = float(value)
        data.setdefault('assumed', []).append(name.strip())
    try:
        result = solve(data, a.seeds)
    except (ValueError, KeyError) as ex:
        write_json(a.output, {'status': 'blocked', 'reason': str(ex)})
        print(str(ex))
        return 2
    write_json(a.output, result)
    print(json.dumps({k: result[k] for k in ('status', 'rms_px', 'max_px', 'dims_m', 'dim_source', 'free')}, ensure_ascii=False))
    print(json.dumps(result['camera'], ensure_ascii=False))
    return 0 if result['status'] == 'fitted' else 3


if __name__ == '__main__':
    raise SystemExit(main())
