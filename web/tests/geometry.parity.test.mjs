// The JS geometry port must agree with the Python builders (fixtures from make_geometry_reference.py).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { meshFor, transformPoint, triangulate } from '../app/js/geometry.js';

const reference = JSON.parse(readFileSync(new URL('./fixtures/geometry_reference.json', import.meta.url), 'utf8'));

function stats(kind, params, location, rotation) {
  const [verts, faces] = meshFor({ kind, params });
  const world = verts.map((v) => transformPoint(v, location, rotation));
  const tris = triangulate(faces);
  let area = 0;
  let volume = 0;
  for (const [a, b, c] of tris) {
    const p = world[a];
    const q = world[b];
    const r = world[c];
    const u = [0, 1, 2].map((i) => q[i] - p[i]);
    const w = [0, 1, 2].map((i) => r[i] - p[i]);
    const cross = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    area += 0.5 * Math.hypot(...cross);
    for (let i = 0; i < 3; i++) volume += p[i] * (q[(i + 1) % 3] * r[(i + 2) % 3] - q[(i + 2) % 3] * r[(i + 1) % 3]) / 6;
  }
  return {
    vertices: verts.length, faces: faces.length, triangles: tris.length,
    bbox_min: [0, 1, 2].map((i) => Math.min(...world.map((p) => p[i]))),
    bbox_max: [0, 1, 2].map((i) => Math.max(...world.map((p) => p[i]))),
    sum: [0, 1, 2].map((i) => world.reduce((s, p) => s + p[i], 0)),
    first: world[0], last: world[world.length - 1],
    index_sum: faces.reduce((s, f) => s + f.reduce((a, b) => a + b, 0), 0),
    area, volume,
  };
}

function close(actual, expected, label) {
  if (Array.isArray(expected)) {
    assert.equal(actual.length, expected.length, label);
    expected.forEach((e, i) => close(actual[i], e, `${label}[${i}]`));
  } else if (typeof expected === 'number' && !Number.isInteger(expected)) {
    assert.ok(Math.abs(actual - expected) <= 1e-9 * Math.max(1, Math.abs(expected)), `${label}: ${actual} vs ${expected}`);
  } else {
    assert.ok(Math.abs(actual - expected) <= 1e-9 * Math.max(1, Math.abs(expected)), `${label}: ${actual} vs ${expected}`);
  }
}

for (const c of reference.cases) {
  test(`parity: ${c.name}`, () => {
    if (c.error) {
      assert.throws(() => meshFor({ kind: c.kind, params: c.params }), (e) => e.message === c.error, c.error);
      return;
    }
    const got = stats(c.kind, c.params, c.location, c.rotation_deg);
    for (const key of Object.keys(c.expect)) close(got[key], c.expect[key], `${c.name}.${key}`);
  });
}

test('the reference covers every primitive and several refusals', () => {
  const kinds = new Set(reference.cases.map((c) => c.kind));
  for (const k of ['box', 'cylinder', 'rounded_ring', 'rounded_portal', 'swept_strip', 'profile_extrusion', 'arc_panel']) {
    assert.ok(kinds.has(k), k);
  }
  assert.ok(reference.cases.filter((c) => c.error).length >= 10);
});
