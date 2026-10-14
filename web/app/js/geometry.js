// Line-for-line port of booth-image-to-model/scripts/geometry.py (metres, centred object coordinates).
// No dependencies, so Node can test it against the Python builders (web/tests/geometry.parity.test.mjs).
// Same checks, same order, same error cases: the editor must refuse what the Python builder refuses.

export class GeometryError extends Error {}

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const isInt = (v) => typeof v === 'number' && Number.isInteger(v);
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const rad = (deg) => (deg * Math.PI) / 180;

export function positive(name, value) {
  if (!isNum(value) || value <= 0) throw new GeometryError(`${name}: expected a finite positive number`);
  return value;
}

export function arcSteps(value) {
  if (!isInt(value) || value < 4 || value > 128) throw new GeometryError('segments_per_corner must be an integer in [4,128]');
  return value;
}

export function roundedLoop(width, depth, radius, steps = 16) {
  const w = positive('width', width);
  const d = positive('depth', depth);
  const r = positive('radius', radius);
  steps = arcSteps(steps);
  if (r >= Math.min(w, d) / 2) throw new GeometryError('radius must be smaller than half the smaller outer dimension');
  const result = [];
  for (const [cx, cy, a0] of [[w / 2 - r, d / 2 - r, 0], [-w / 2 + r, d / 2 - r, 90],
    [-w / 2 + r, -d / 2 + r, 180], [w / 2 - r, -d / 2 + r, 270]]) {
    for (let k = 0; k <= steps; k++) {
      const a = rad(a0 + (90 * k) / steps);
      result.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
    }
  }
  return result;
}

function insideRoundedRect(x, y, w, d, r, clearance = 0.0) {
  w = w - 2 * clearance;
  d = d - 2 * clearance;
  r = Math.max(0.0, r - clearance);
  if (Math.abs(x) > w / 2 || Math.abs(y) > d / 2) return false;
  const dx = Math.max(0.0, Math.abs(x) - (w / 2 - r));
  const dy = Math.max(0.0, Math.abs(y) - (d / 2 - r));
  return dx * dx + dy * dy <= r * r + 1e-12;
}

export function roundedRing(params) {
  const [w, d] = params.outer_size;
  const [wi, di] = params.inner_size;
  const r = params.outer_radius;
  const ri = params.inner_radius;
  const h = positive('height', params.height);
  const nseg = params.segments_per_corner ?? 16;
  const outer = roundedLoop(w, d, r, nseg);
  const inner = roundedLoop(wi, di, ri, nseg);
  if (wi >= w || di >= d) throw new GeometryError('ring opening must be strictly smaller than outer dimensions');
  if (!inner.every(([x, y]) => insideRoundedRect(x, y, w, d, r, 0.001))) {
    throw new GeometryError('ring inner boundary crosses or touches outer boundary');
  }
  const n = outer.length;
  const v = [];
  for (const z of [-h / 2, h / 2]) for (const loop of [outer, inner]) for (const [x, y] of loop) v.push([x, y, z]);
  const f = [];
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    f.push([i, j, 2 * n + j, 2 * n + i],
      [n + j, n + i, 3 * n + i, 3 * n + j],
      [j, i, n + i, n + j],
      [2 * n + i, 2 * n + j, 3 * n + j, 3 * n + i]);
  }
  return [v, f];
}

function archPath(w, h, r, steps) {
  if (!(0 < r && r < Math.min(w / 2, h))) throw new GeometryError('invalid portal corner radius');
  const result = [[-w / 2, 0.0]];
  for (const [cx, start, end] of [[-w / 2 + r, 180, 90], [w / 2 - r, 90, 0]]) {
    for (let k = 0; k <= steps; k++) {
      const a = rad(start + ((end - start) * k) / steps);
      result.push([cx + r * Math.cos(a), h - r + r * Math.sin(a)]);
    }
  }
  result.push([w / 2, 0.0]);
  return result;
}

export function roundedPortal(params) {
  const names = ['width', 'height', 'depth', 'side_width', 'beam_height', 'outer_radius', 'inner_radius'];
  const [w, h, d, t, b, r, ri] = names.map((k) => positive(k, params[k]));
  const steps = arcSteps(params.segments_per_corner ?? 16);
  if (2 * t >= w || b >= h) throw new GeometryError('portal opening is closed or inverted');
  const wi = w - 2 * t;
  const hi = h - b;
  const outer = archPath(w, h, r, steps);
  const inner = archPath(wi, hi, ri, steps);
  for (const [x, z] of inner.slice(1, -1)) {
    if (Math.abs(x) >= w / 2 || z >= h) throw new GeometryError('portal contours intersect');
    if (z > h - r && Math.abs(x) > w / 2 - r) {
      if ((Math.abs(x) - (w / 2 - r)) ** 2 + (z - (h - r)) ** 2 >= r * r) {
        throw new GeometryError('portal inner contour crosses outer rounded corner');
      }
    }
  }
  const n = outer.length;
  const v = [];
  for (const y of [-d / 2, d / 2]) for (const path of [outer, inner]) for (const [x, z] of path) v.push([x, y, z - h / 2]);
  const f = [];
  for (let i = 0; i < n - 1; i++) {
    const j = i + 1;
    f.push([i, n + i, n + j, j],
      [2 * n + i, 2 * n + j, 3 * n + j, 3 * n + i],
      [i, j, 2 * n + j, 2 * n + i],
      [n + j, n + i, 3 * n + i, 3 * n + j]);
  }
  f.push([0, 2 * n, 3 * n, n], [n - 1, 2 * n - 1, 4 * n - 1, 3 * n - 1]);
  return [v, f];
}

export function box(params) {
  const size = params.size;
  if (!Array.isArray(size) || size.length !== 3) throw new GeometryError('box size must contain three positive dimensions');
  const [x, y, z] = size.map((n) => positive('size', n) / 2);
  const radius = params.bevel_radius ?? 0;
  const mode = params.bevel_mode ?? 'all';
  if (mode !== 'all' && mode !== 'vertical') throw new GeometryError('bevel_mode must be all or vertical');
  if (!isNum(radius) || radius < 0) throw new GeometryError('bevel_radius must be a finite nonnegative number');
  if (radius) {
    const limit = mode === 'vertical' ? Math.min(x, y) : Math.min(x, y, z);
    if (radius >= limit) throw new GeometryError('bevel_radius must be smaller than half the smallest rounded dimension');
    const steps = arcSteps(params.segments_per_corner ?? 8);
    return mode === 'vertical' ? verticalBevelBox(x, y, z, radius, steps) : beveledBox(x, y, z, radius, steps);
  }
  if ('segments_per_corner' in params || 'bevel_mode' in params) {
    throw new GeometryError('bevel segmentation/mode requires a positive bevel_radius');
  }
  const v = [[-x, -y, -z], [x, -y, -z], [x, y, -z], [-x, y, -z],
    [-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z]];
  const f = [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]];
  return [v, f];
}

function verticalBevelBox(x, y, z, r, steps) {
  const loop = roundedLoop(2 * x, 2 * y, r, steps);
  const n = loop.length;
  const verts = [];
  for (const h of [-z, z]) for (const [px, py] of loop) verts.push([px, py, h]);
  const faces = [];
  for (let i = 0; i < n; i++) faces.push([i, (i + 1) % n, n + ((i + 1) % n), n + i]);
  faces.push(Array.from({ length: n }, (_, i) => n - 1 - i), Array.from({ length: n }, (_, i) => n + i));
  return [verts, faces];
}

function beveledBox(x, y, z, r, steps) {
  const rings = [];
  for (let k = 0; k <= steps; k++) {
    const a = (Math.PI * k) / (2 * steps);
    rings.push([-z + r * (1 - Math.cos(a)), r * Math.sin(a)]);
  }
  rings.push([z - r, r]);
  for (let k = 1; k <= steps; k++) {
    const a = (Math.PI * k) / (2 * steps);
    rings.push([z - r + r * Math.sin(a), r * Math.cos(a)]);
  }
  const verts = [];
  const lookup = new Map();
  const loops = [];
  const q = (value) => Math.round(value * 1e12); // template literals print -0 as "0", like Python's -0.0 == 0.0
  for (const [h, rho] of rings) {
    const loop = [];
    for (const [cx, cy, a0] of [[x - r, y - r, 0], [-x + r, y - r, 90], [-x + r, -y + r, 180], [x - r, -y + r, 270]]) {
      for (let k = 0; k <= steps; k++) {
        const a = rad(a0 + (90 * k) / steps);
        const point = [cx + rho * Math.cos(a), cy + rho * Math.sin(a), h];
        const key = `${q(point[0])},${q(point[1])},${q(point[2])}`;
        if (!lookup.has(key)) {
          lookup.set(key, verts.length);
          verts.push(point);
        }
        loop.push(lookup.get(key));
      }
    }
    loops.push(loop);
  }
  const faces = [];
  const add = (face) => {
    const unique = [];
    for (const index of face) if (!unique.includes(index)) unique.push(index);
    if (unique.length >= 3) faces.push(unique);
  };
  for (let l = 0; l < loops.length - 1; l++) {
    const lower = loops[l];
    const upper = loops[l + 1];
    for (let i = 0; i < lower.length; i++) {
      const j = (i + 1) % lower.length;
      add([lower[i], lower[j], upper[j], upper[i]]);
    }
  }
  add([...loops[0]].reverse());
  add(loops[loops.length - 1]);
  return [verts, faces];
}

export function sweptStrip(params) {
  const points = params.control_points;
  if (!Array.isArray(points) || points.length < 4 || (points.length - 1) % 3) {
    throw new GeometryError('control_points must contain 3*n+1 local [x,z] coordinates');
  }
  for (const point of points) {
    if (!Array.isArray(point) || point.length !== 2 || !point.every(isNum)) {
      throw new GeometryError('control_points require finite local [x,z] pairs');
    }
  }
  const width = positive('width', params.width);
  const depth = positive('depth', params.depth);
  const steps = arcSteps(params.segments_per_curve ?? 24);
  const sampled = [];
  const normals = [];
  for (let start = 0; start < points.length - 1; start += 3) {
    const p = points.slice(start, start + 4);
    for (let k = 0; k <= steps; k++) {
      const t = k / steps;
      const u = 1 - t;
      const value = [0, 1].map((axis) => u ** 3 * p[0][axis] + 3 * u * u * t * p[1][axis] + 3 * u * t * t * p[2][axis] + t ** 3 * p[3][axis]);
      const tangent = [0, 1].map((axis) => 3 * u * u * (p[1][axis] - p[0][axis]) + 6 * u * t * (p[2][axis] - p[1][axis]) + 3 * t * t * (p[3][axis] - p[2][axis]));
      const length = Math.hypot(tangent[0], tangent[1]);
      if (length < 1e-10) throw new GeometryError('strip curve contains a zero tangent');
      const normal = [-tangent[1] / length, tangent[0] / length];
      if (start && k === 0) {
        const last = normals[normals.length - 1];
        if (normal[0] * last[0] + normal[1] * last[1] < 0.999) {
          throw new GeometryError('strip curves must share a continuous tangent direction');
        }
        continue;
      }
      sampled.push(value);
      normals.push(normal);
    }
  }
  for (let i = 1; i < sampled.length; i++) {
    const distance = dist(sampled[i - 1], sampled[i]);
    if (distance < 1e-10) throw new GeometryError('strip path contains coincident samples');
    const dot = normals[i - 1][0] * normals[i][0] + normals[i - 1][1] * normals[i][1];
    const turn = Math.acos(Math.max(-1, Math.min(1, dot)));
    if (turn && (width / 2) * turn >= distance * 0.95) throw new GeometryError('strip width is too large for its bend radius');
  }
  const outline = sampled.map((p, i) => [p[0] + (normals[i][0] * width) / 2, p[1] + (normals[i][1] * width) / 2]);
  for (let i = sampled.length - 1; i >= 0; i--) {
    outline.push([sampled[i][0] - (normals[i][0] * width) / 2, sampled[i][1] - (normals[i][1] * width) / 2]);
  }
  const orient = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const crosses = (a, b, c, d) => orient(a, b, c) * orient(a, b, d) < -1e-14 && orient(c, d, a) * orient(c, d, b) < -1e-14;
  const n = outline.length;
  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;
      if (crosses(outline[i], outline[(i + 1) % n], outline[j], outline[(j + 1) % n])) {
        throw new GeometryError('strip path or offset boundary self-intersects');
      }
    }
  }
  const verts = [];
  for (let i = 0; i < sampled.length; i++) {
    const p = sampled[i];
    const normal = normals[i];
    for (const [side, y] of [[1, -depth / 2], [-1, -depth / 2], [-1, depth / 2], [1, depth / 2]]) {
      verts.push([p[0] + ((normal[0] * width) / 2) * side, y, p[1] + ((normal[1] * width) / 2) * side]);
    }
  }
  const faces = [];
  for (let i = 0; i < sampled.length - 1; i++) {
    for (let side = 0; side < 4; side++) {
      const j = (side + 1) % 4;
      faces.push([4 * i + side, 4 * i + j, 4 * (i + 1) + j, 4 * (i + 1) + side]);
    }
  }
  faces.push([3, 2, 1, 0], [0, 1, 2, 3].map((i) => 4 * (sampled.length - 1) + i));
  return [verts, faces];
}

export function cylinder(params) {
  const r = positive('radius', params.radius);
  const h = positive('height', params.height);
  const n = params.segments ?? 64;
  if (!isInt(n) || n < 12 || n > 512) throw new GeometryError('invalid cylinder segments');
  const v = [];
  for (const z of [-h / 2, h / 2]) {
    for (let i = 0; i < n; i++) v.push([r * Math.cos((2 * Math.PI * i) / n), r * Math.sin((2 * Math.PI * i) / n), z]);
  }
  v.push([0, 0, -h / 2], [0, 0, h / 2]);
  const f = [];
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    f.push([i, j, n + j, n + i], [2 * n, j, i], [2 * n + 1, n + i, n + j]);
  }
  return [v, f];
}

const orient2 = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);

function simpleProfile(input) {
  if (!Array.isArray(input) || input.length < 3 || input.length > 1024) {
    throw new GeometryError('profile must contain 3..1024 local [x,z] coordinates');
  }
  if (input.some((p) => !Array.isArray(p) || p.length !== 2 || !p.every(isNum))) {
    throw new GeometryError('profile coordinates must be finite local [x,z] pairs');
  }
  const points = input.map((p) => [Number(p[0]), Number(p[1])]);
  const extent = Math.max(...[0, 1].map((k) => Math.max(...points.map((p) => p[k])) - Math.min(...points.map((p) => p[k]))));
  if (extent <= 0) throw new GeometryError('profile has zero area');
  const tolerance = extent * 1e-10;
  const areaTolerance = extent * extent * 1e-12;
  const onSegment = (a, b, p) => Math.abs(orient2(a, b, p)) <= areaTolerance
    && [0, 1].every((k) => Math.min(a[k], b[k]) - tolerance <= p[k] && p[k] <= Math.max(a[k], b[k]) + tolerance);
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const a = points[i];
    const b = points[(i + 1) % n];
    if (dist(a, b) <= tolerance) throw new GeometryError('profile has a zero-length edge; do not repeat the closing point');
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;
      const c = points[j];
      const d = points[(j + 1) % n];
      const abC = orient2(a, b, c);
      const abD = orient2(a, b, d);
      const cdA = orient2(c, d, a);
      const cdB = orient2(c, d, b);
      if ((abC * abD < 0 && cdA * cdB < 0) || [onSegment(a, b, c), onSegment(a, b, d), onSegment(c, d, a), onSegment(c, d, b)].some(Boolean)) {
        throw new GeometryError('profile boundary self-intersects or touches itself');
      }
    }
  }
  let changed = true;
  while (changed && points.length > 3) {
    changed = false;
    for (let i = 0; i < points.length; i++) {
      const a = points[(i - 1 + points.length) % points.length];
      const b = points[i];
      const c = points[(i + 1) % points.length];
      if (Math.abs(orient2(a, b, c)) <= areaTolerance) {
        if ((b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) <= 0) {
          throw new GeometryError('profile contains an overlapping boundary reversal');
        }
        points.splice(i, 1);
        changed = true;
        break;
      }
    }
  }
  const origin = points[0];
  const relative = points.map((p) => [p[0] - origin[0], p[1] - origin[1]]);
  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const next = relative[(i + 1) % points.length];
    area += relative[i][0] * next[1] - next[0] * relative[i][1];
  }
  area /= 2;
  if (Math.abs(area) <= areaTolerance) throw new GeometryError('profile has zero area');
  if (area < 0) points.reverse();
  return [points, areaTolerance];
}

function profileTriangles(points, tolerance) {
  const remaining = points.map((_, i) => i);
  const triangles = [];
  while (remaining.length > 3) {
    let clipped = false;
    for (let offset = 0; offset < remaining.length; offset++) {
      const b = remaining[offset];
      const a = remaining[(offset - 1 + remaining.length) % remaining.length];
      const c = remaining[(offset + 1) % remaining.length];
      if (orient2(points[a], points[b], points[c]) <= tolerance) continue;
      const inside = (p) => [[a, b], [b, c], [c, a]].every(([u, v]) => orient2(points[u], points[v], p) >= -tolerance);
      if (remaining.some((index) => index !== a && index !== b && index !== c && inside(points[index]))) continue;
      triangles.push([a, b, c]);
      remaining.splice(offset, 1);
      clipped = true;
      break;
    }
    if (!clipped) throw new GeometryError('profile cannot be triangulated; boundary is degenerate');
  }
  if (orient2(points[remaining[0]], points[remaining[1]], points[remaining[2]]) <= tolerance) {
    throw new GeometryError('profile triangulation contains a degenerate cap');
  }
  return [...triangles, [...remaining]];
}

export function profileExtrusion(params) {
  const [points, tolerance] = simpleProfile(params.profile);
  const depth = positive('depth', params.depth);
  const n = points.length;
  const caps = profileTriangles(points, tolerance);
  const vertices = [];
  for (const y of [-depth / 2, depth / 2]) for (const [x, z] of points) vertices.push([x, y, z]);
  const faces = [...caps, ...caps.map((face) => [...face].reverse().map((i) => n + i))];
  for (let i = 0; i < n; i++) faces.push([i, n + i, n + ((i + 1) % n), (i + 1) % n]);
  return [vertices, faces];
}

export function arcPanel(params) {
  const radius = positive('radius', params.radius);
  const thickness = positive('thickness', params.thickness);
  const height = positive('height', params.height);
  if (thickness >= 2 * radius) throw new GeometryError('arc_panel thickness must be smaller than twice its centreline radius');
  const angles = [params.start_deg, params.end_deg];
  if (!angles.every(isNum)) throw new GeometryError('arc_panel angles must be finite numbers');
  const span = Math.abs(angles[1] - angles[0]);
  if (!(span > 1e-6 && span < 360)) throw new GeometryError('arc_panel angular span must be positive and smaller than 360 degrees');
  const steps = params.segments ?? 64;
  if (!isInt(steps) || steps < 4 || steps > 512) throw new GeometryError('arc_panel segments must be an integer in [4,512]');
  const [start, end] = [...angles].sort((a, b) => a - b).map(rad);
  const n = steps + 1;
  const loops = [radius + thickness / 2, radius - thickness / 2].map((r) => Array.from({ length: n }, (_, i) => [
    r * Math.cos(start + ((end - start) * i) / steps), r * Math.sin(start + ((end - start) * i) / steps)]));
  const vertices = [];
  for (const z of [-height / 2, height / 2]) for (const loop of loops) for (const [x, y] of loop) vertices.push([x, y, z]);
  const faces = [];
  for (let i = 0; i < n - 1; i++) {
    const j = i + 1;
    faces.push([i, j, 2 * n + j, 2 * n + i], [n + j, n + i, 3 * n + i, 3 * n + j],
      [j, i, n + i, n + j], [2 * n + i, 2 * n + j, 3 * n + j, 3 * n + i]);
  }
  faces.push([0, 2 * n, 3 * n, n], [n - 1, 2 * n - 1, 4 * n - 1, 3 * n - 1]);
  return [vertices, faces];
}

export const BUILDERS = {
  box, cylinder, rounded_ring: roundedRing, rounded_portal: roundedPortal,
  swept_strip: sweptStrip, profile_extrusion: profileExtrusion, arc_panel: arcPanel,
};

/** Returns [vertices, faces]; text components have no solid geometry here (they throw like the Python builder). */
export function meshFor(component) {
  const builder = BUILDERS[component.kind];
  if (!builder) throw new GeometryError(`Unsupported primitive: ${component.kind}; add and test a builder, never substitute a box`);
  return builder(component.params);
}

/** Blender XYZ Euler convention (R = Rz*Ry*Rx), local -> world. No nonuniform scale. */
export function transformPoint(local, location, rotationDeg) {
  let [x, y, z] = local.map(Number);
  const [rx, ry, rz] = rotationDeg.map(rad);
  [y, z] = [y * Math.cos(rx) - z * Math.sin(rx), y * Math.sin(rx) + z * Math.cos(rx)];
  [x, z] = [x * Math.cos(ry) + z * Math.sin(ry), -x * Math.sin(ry) + z * Math.cos(ry)];
  [x, y] = [x * Math.cos(rz) - y * Math.sin(rz), x * Math.sin(rz) + y * Math.cos(rz)];
  return [x + location[0], y + location[1], z + location[2]];
}

export function triangulate(faces) {
  const out = [];
  for (const f of faces) for (let i = 1; i < f.length - 1; i++) out.push([f[0], f[i], f[i + 1]]);
  return out;
}
