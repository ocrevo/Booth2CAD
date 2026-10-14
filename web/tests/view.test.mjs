// three.js scene pieces that need no browser: meshes, normals, transforms and the spec camera.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as THREE from 'three';
import { meshFor, transformPoint, triangulate } from '../app/js/geometry.js';
import { buildGeometry, componentObject, materialFor } from '../app/js/mesh.js';
import { applySpecCamera, frameRect, projectPoint } from '../app/js/camera.js';

const demo = JSON.parse(readFileSync(new URL('../app/demo/demo-booth.spec.json', import.meta.url), 'utf8'));
const cameras = JSON.parse(readFileSync(new URL('./fixtures/camera_reference.json', import.meta.url), 'utf8'));
const close = (a, b, tol, label) => assert.ok(Math.abs(a - b) <= tol, `${label}: ${a} vs ${b}`);

test('every component of the demo builds a mesh whose world vertices match transformPoint', () => {
  for (const c of demo.components) {
    const mesh = componentObject(c);
    mesh.updateMatrixWorld(true);
    const [vertices, faces] = meshFor(c);
    const position = mesh.geometry.getAttribute('position');
    assert.equal(position.count, triangulate(faces).length * 3, c.id);
    // spot-check the first triangle's first corner (Euler order ZYX must equal Blender's XYZ)
    const first = triangulate(faces)[0][0];
    const world = new THREE.Vector3().fromBufferAttribute(position, 0).applyMatrix4(mesh.matrixWorld);
    const want = transformPoint(vertices[first], c.location, c.rotation_deg);
    [0, 1, 2].forEach((i) => close(world.getComponent(i), want[i], 1e-5, `${c.id}[${i}]`));
  }
});

test('rotated parts keep Blender Euler order for all three angles', () => {
  const c = structuredClone(demo.components.find((x) => x.id === 'counter_body'));
  c.location = [1, 2, 3];
  c.rotation_deg = [20, -35, 110];
  const mesh = componentObject(c);
  mesh.updateMatrixWorld(true);
  const [vertices, faces] = meshFor(c);
  const position = mesh.geometry.getAttribute('position');
  const tris = triangulate(faces);
  for (let t = 0; t < tris.length; t += 5) {
    tris[t].forEach((v, corner) => {
      const world = new THREE.Vector3().fromBufferAttribute(position, t * 3 + corner).applyMatrix4(mesh.matrixWorld);
      const want = transformPoint(vertices[v], c.location, c.rotation_deg);
      [0, 1, 2].forEach((i) => close(world.getComponent(i), want[i], 1e-5, `tri ${t} corner ${corner}`));
    });
  }
});

test('normals are unit length, flat on box faces and smooth around a cylinder', () => {
  const [bv, bf] = meshFor({ kind: 'box', params: { size: [1, 1, 1] } });
  const box = buildGeometry(bv, bf).getAttribute('normal');
  for (let i = 0; i < box.count; i++) close(Math.hypot(box.getX(i), box.getY(i), box.getZ(i)), 1, 1e-6, 'box normal');
  const axisAligned = Array.from({ length: box.count }, (_, i) => [box.getX(i), box.getY(i), box.getZ(i)])
    .every((n) => n.filter((v) => Math.abs(Math.abs(v) - 1) < 1e-6).length === 1);
  assert.ok(axisAligned, 'box corners must stay crisp');
  const [cv, cf] = meshFor({ kind: 'cylinder', params: { radius: 0.5, height: 1, segments: 32 } });
  const cyl = buildGeometry(cv, cf);
  const pos = cyl.getAttribute('position');
  const nor = cyl.getAttribute('normal');
  let sideChecked = 0;
  for (let i = 0; i < pos.count; i++) {
    if (Math.abs(nor.getZ(i)) < 1e-6) {                       // side wall: normal points straight out from the axis
      const r = Math.hypot(pos.getX(i), pos.getY(i));
      close(nor.getX(i), pos.getX(i) / r, 1e-5, 'side nx');
      close(nor.getY(i), pos.getY(i) / r, 1e-5, 'side ny');
      sideChecked++;
    }
  }
  assert.ok(sideChecked > 64);
});

test('materials convert colour space, alpha and emission', () => {
  const c = structuredClone(demo.components.find((x) => x.id === 'spot_0'));
  const m = materialFor(c);
  assert.ok(m.emissiveIntensity > 0 && m.emissiveIntensity <= 3);
  const white = structuredClone(c);
  white.material = { color: [1, 0.5, 0.25, 0.4], roughness: 0.2, metallic: 0.7 };
  const linear = materialFor(white);
  assert.equal(linear.transparent, true);
  close(linear.opacity, 0.4, 1e-9, 'alpha');
  const asLinear = linear.color.getRGB({}, THREE.LinearSRGBColorSpace);
  close(asLinear.g, 0.5, 1e-4, 'linear g');
  white.material.color_space = 'srgb';
  const srgb = materialFor(white).color.getRGB({}, THREE.SRGBColorSpace);
  close(srgb.g, 0.5, 1e-4, 'srgb g');
});

for (const c of cameras.cases) {
  test(`camera: ${c.name}: port of camera_math.project agrees with Python`, () => {
    for (const p of c.points) {
      const [u, v, z] = projectPoint(p.world, c.camera, c.width, c.height);
      close(u, p.u, 1e-6, 'u');
      close(v, p.v, 1e-6, 'v');
      close(z, p.depth, 1e-9, 'depth');
    }
  });

  test(`camera: ${c.name}: the three.js camera lands points on the same pixels`, () => {
    const viewports = [
      { width: c.width, height: c.height },                      // same canvas as the source
      { width: 1400, height: 700 },                              // wider viewport: pillarboxed frame
      { width: 500, height: 900 },                               // taller viewport: letterboxed frame
    ];
    for (const viewport of viewports) {
      const camera = new THREE.PerspectiveCamera();
      camera.up = new THREE.Vector3(0, 0, 1);
      const { frame } = applySpecCamera(camera, c.camera, { width: c.width, height: c.height }, viewport);
      close(frame.width / frame.height, c.width / c.height, 1e-9, 'frame aspect');
      for (const p of c.points) {
        const ndc = new THREE.Vector3(...p.world).project(camera);
        const px = ((ndc.x + 1) / 2) * viewport.width;
        const py = ((1 - ndc.y) / 2) * viewport.height;
        close((px - frame.x) / frame.scale, p.u, 0.05, `u in ${viewport.width}x${viewport.height}`);
        close((py - frame.y) / frame.scale, p.v, 0.05, `v in ${viewport.width}x${viewport.height}`);
      }
    }
  });
}

test('frameRect centres the largest source-shaped rectangle', () => {
  const f = frameRect({ width: 960, height: 600 }, { width: 1400, height: 700 });
  close(f.height, 700, 1e-9, 'height');
  close(f.width, 1120, 1e-9, 'width');
  close(f.x, 140, 1e-9, 'x');
});
