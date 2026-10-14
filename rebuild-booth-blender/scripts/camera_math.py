"""Blender-consistent pinhole camera maths; standard library only.

Matches blender_build.py: the camera looks from `position` to `target`
(track -Z, up Y), `roll_deg` turns it about its own view axis, sensor fit is
HORIZONTAL and `principal_point` is normalised with v pointing down. Pixel
coordinates use the source canvas (width x height, origin top-left).

Use it to place on-plane parts from pixels (unproject) and to check where a
3D point lands (project). It does not prove depth: a pixel only fixes a ray.
"""
from __future__ import annotations
import math


def _sub(a, b): return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(a):
    n = math.sqrt(_dot(a, a))
    if not math.isfinite(n) or n < 1e-12:
        raise ValueError('degenerate vector')
    return [a[0] / n, a[1] / n, a[2] / n]


def axes(camera):
    """Return (forward, right, up) unit vectors in world space."""
    fwd = _unit(_sub(camera['target'], camera['position']))
    if abs(fwd[2]) > 1 - 1e-9:
        raise ValueError('camera looks straight up/down; roll is undefined')
    right = _unit(_cross(fwd, [0.0, 0.0, 1.0]))
    up = _cross(right, fwd)
    r = math.radians(camera.get('roll_deg', 0))
    c, s = math.cos(r), math.sin(r)
    return fwd, [c * right[i] + s * up[i] for i in range(3)], [c * up[i] - s * right[i] for i in range(3)]


def focal_px(camera, width):
    if camera.get('projection', 'perspective') != 'perspective':
        raise ValueError('only perspective cameras are supported here')
    return camera['lens_mm'] / camera['sensor_width_mm'] * width


def project(point, camera, width, height):
    """World point -> (u_px, v_px, depth along the view axis)."""
    fwd, right, up = axes(camera)
    d = _sub(point, camera['position'])
    z = _dot(d, fwd)
    if z <= 1e-9:
        raise ValueError('point is behind the camera')
    f = focal_px(camera, width)
    pp = camera.get('principal_point', [0.5, 0.5])
    return pp[0] * width + f * _dot(d, right) / z, pp[1] * height - f * _dot(d, up) / z, z


def ray(px, py, camera, width, height):
    """Unit world direction through pixel (px, py)."""
    fwd, right, up = axes(camera)
    f = focal_px(camera, width)
    pp = camera.get('principal_point', [0.5, 0.5])
    a, b = px - pp[0] * width, -(py - pp[1] * height)
    return _unit([f * fwd[i] + a * right[i] + b * up[i] for i in range(3)])


def unproject(px, py, camera, width, height, axis, value):
    """Intersect the pixel ray with the plane {x|y|z} = value. Returns [x, y, z]."""
    k = {'x': 0, 'y': 1, 'z': 2}[axis] if isinstance(axis, str) else int(axis)
    d = ray(px, py, camera, width, height)
    if abs(d[k]) < 1e-12:
        raise ValueError('ray is parallel to the plane')
    t = (value - camera['position'][k]) / d[k]
    if t <= 0:
        raise ValueError('plane is behind the camera along this ray')
    return [camera['position'][i] + t * d[i] for i in range(3)]


def rect_on_plane(top_left, bottom_right, camera, width, height, axis, value):
    """Pixel corners of a wall-parallel rectangle -> ((u_min, u_max), (z_min, z_max)).

    For axis 'y' the first range is world X; for axis 'x' it is world Y. The
    vertical range is world Z. Corners are the visual top-left and bottom-right.
    """
    a = unproject(*top_left, camera, width, height, axis, value)
    b = unproject(*bottom_right, camera, width, height, axis, value)
    h = 0 if axis in ('y', 1) else 1
    return (min(a[h], b[h]), max(a[h], b[h])), (min(a[2], b[2]), max(a[2], b[2]))


def floor_point(px, py, camera, width, height, z=0.0):
    """Where a floor-contact pixel (chair foot, counter base) meets the plane z."""
    return unproject(px, py, camera, width, height, 'z', z)
