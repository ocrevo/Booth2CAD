// Spec component -> three.js mesh. Needs only three (no DOM, no addons), so Node can test it.
// Z is up everywhere (the spec's own axes): the viewport sets Object3D.DEFAULT_UP to +Z, nothing is converted.

import * as THREE from 'three';
import { meshFor, triangulate } from './geometry.js';

/**
 * Indexed polygon mesh -> non-indexed BufferGeometry with crease-angle normals: neighbouring faces closer than
 * `creaseDeg` share a smooth normal (bevels, cylinders), sharper edges stay crisp (box corners, caps).
 */
export function buildGeometry(vertices, faces, creaseDeg = 35) {
  const tris = triangulate(faces);
  const faceNormal = [];
  const touching = vertices.map(() => []);            // per vertex: [triangle, corner angle at that vertex]
  tris.forEach((tri, t) => {
    const [p, q, r] = tri.map((i) => vertices[i]);
    const u = [q[0] - p[0], q[1] - p[1], q[2] - p[2]];
    const w = [r[0] - p[0], r[1] - p[1], r[2] - p[2]];
    const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const len = Math.hypot(...n);
    faceNormal.push(len > 1e-18 ? n.map((v) => v / len) : [0, 0, 1]);
    tri.forEach((v, corner) => {                      // angle weights keep smooth normals exact on uneven triangulations
      const a = vertices[tri[corner]];
      const b = vertices[tri[(corner + 1) % 3]];
      const c = vertices[tri[(corner + 2) % 3]];
      const e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const e2 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      const cos = (e1[0] * e2[0] + e1[1] * e2[1] + e1[2] * e2[2]) / ((Math.hypot(...e1) * Math.hypot(...e2)) || 1);
      touching[v].push([t, Math.acos(Math.max(-1, Math.min(1, cos)))]);
    });
  });
  const cosCrease = Math.cos((creaseDeg * Math.PI) / 180);
  const positions = new Float32Array(tris.length * 9);
  const normals = new Float32Array(tris.length * 9);
  tris.forEach((tri, t) => {
    tri.forEach((v, corner) => {
      let nx = 0;
      let ny = 0;
      let nz = 0;
      for (const [u, angle] of touching[v]) {
        const d = faceNormal[t][0] * faceNormal[u][0] + faceNormal[t][1] * faceNormal[u][1] + faceNormal[t][2] * faceNormal[u][2];
        if (d >= cosCrease) {
          nx += faceNormal[u][0] * angle;
          ny += faceNormal[u][1] * angle;
          nz += faceNormal[u][2] * angle;
        }
      }
      const len = Math.hypot(nx, ny, nz) || 1;
      const o = t * 9 + corner * 3;
      positions.set(vertices[v], o);
      normals[o] = nx / len;
      normals[o + 1] = ny / len;
      normals[o + 2] = nz / len;
    });
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
  geometry.computeBoundingSphere();
  return geometry;
}

export function materialColor(material) {
  const space = material.color_space === 'srgb' ? THREE.SRGBColorSpace : THREE.LinearSRGBColorSpace;
  return new THREE.Color().setRGB(material.color[0], material.color[1], material.color[2], space);
}

export function materialFor(component) {
  const m = component.material;
  const color = materialColor(m);
  const emission = Number(m.emission) || 0;
  return new THREE.MeshStandardMaterial({
    color,
    roughness: m.roughness ?? 0.5,
    metalness: m.metallic ?? 0,
    emissive: emission > 0 ? color.clone() : new THREE.Color(0x000000),
    emissiveIntensity: emission > 0 ? Math.min(emission, 3) : 0,
    transparent: m.color[3] < 1,
    opacity: m.color[3],
    side: THREE.DoubleSide,
  });
}

/** Text parts are drawn as a flat label (Blender builds real text; the editor only needs to show where it is). */
function textMesh(component, makeCanvas) {
  const { body, size } = component.params;
  const aspect = Math.max(1, String(body).length * 0.62);
  const geometry = new THREE.PlaneGeometry(size * aspect, size);
  const material = materialFor(component);
  if (makeCanvas) {
    const canvas = makeCanvas();
    canvas.width = 512;
    canvas.height = Math.max(32, Math.round(512 / aspect));
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#ffffff';
    ctx.font = `bold ${Math.round(canvas.height * 0.8)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(body), canvas.width / 2, canvas.height / 2, canvas.width - 8);
    material.map = new THREE.CanvasTexture(canvas);
    material.map.colorSpace = THREE.SRGBColorSpace;
    material.transparent = true;
    material.alphaTest = 0.05;
  }
  return new THREE.Mesh(geometry, material);
}

export function applyTransform(object, component) {
  object.position.set(...component.location);
  object.rotation.order = 'ZYX'; // three's R = Rz*Ry*Rx is Blender's XYZ Euler
  object.rotation.set(...component.rotation_deg.map((d) => (d * Math.PI) / 180));
}

/** Build the mesh for one component. Throws GeometryError when its parameters are refused. */
export function componentObject(component, { makeCanvas } = {}) {
  let mesh;
  if (component.kind === 'text') mesh = textMesh(component, makeCanvas);
  else {
    const [vertices, faces] = meshFor(component);
    mesh = new THREE.Mesh(buildGeometry(vertices, faces), materialFor(component));
  }
  mesh.name = component.id;
  mesh.userData = { id: component.id, kind: component.kind, group: component.group || null };
  mesh.castShadow = component.kind !== 'text';
  mesh.receiveShadow = component.kind !== 'text';
  applyTransform(mesh, component);
  return mesh;
}
