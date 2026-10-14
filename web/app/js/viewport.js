// Browser viewport: scene, lights, orbit, picking, move/rotate gizmo, "match source view", GLB export.
// Z is up (the spec's own axes). Rendering is on demand, so an idle editor costs no CPU/GPU.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { applyTransform, componentObject } from './mesh.js';
import { applySpecCamera } from './camera.js';
import { selectionBounds } from './spec.js';

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

const SELECT_COLOR = 0xff8a00;
const deg = (r) => (r * 180) / Math.PI;

export class Viewport {
  /**
   * hooks: onPick(id | null, { additive, partOnly }), onGizmoStart(info), onGizmoChange(info), onGizmoEnd(),
   *        onViewChange() (the user moved the camera, so "match source view" no longer holds)
   */
  constructor(container, hooks = {}) {
    this.container = container;
    this.hooks = hooks;
    this.parts = new Map();
    this.selection = [];
    this.mode = 'translate';
    this.snap = true;
    this.matching = null;                                  // { spec } while "match source view" is active
    this.errors = [];
    this._dirty = false;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xe9edf1);
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.05, 500);
    this.camera.position.set(8, -10, 6);

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa0aa, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 2.1);
    sun.position.set(6, -8, 12);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 40 });
    sun.shadow.bias = -0.0006;
    sun.shadow.normalBias = 0.04;                           // stops the speckle (shadow acne) on large flat walls
    this.scene.add(sun);

    const ground = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.ShadowMaterial({ opacity: 0.22 }));
    ground.position.z = -0.002;
    ground.receiveShadow = true;
    ground.userData.noPick = true;
    this.scene.add(ground);
    const grid = new THREE.GridHelper(20, 20, 0x9aa3ad, 0xc3c9d0);
    grid.rotation.x = Math.PI / 2;                          // GridHelper lies in XZ; the spec's floor plane is XY
    grid.position.z = -0.004;
    grid.userData.noPick = true;
    this.scene.add(grid);
    const axes = new THREE.AxesHelper(0.6);
    axes.userData.noPick = true;
    this.scene.add(axes);

    this.partsGroup = new THREE.Group();
    this.scene.add(this.partsGroup);
    this.highlight = new THREE.Group();
    this.scene.add(this.highlight);

    this.orbit = new OrbitControls(this.camera, this.renderer.domElement);
    this.orbit.enableDamping = false;
    this.orbit.addEventListener('change', () => this.invalidate());
    this.orbit.addEventListener('start', () => {
      if (this.matching) {
        this.matching = null;
        this.hooks.onViewChange?.();
      }
    });

    this.pivot = new THREE.Object3D();
    this.scene.add(this.pivot);
    this.transform = new TransformControls(this.camera, this.renderer.domElement);
    this.transform.setSize(0.85);
    this.transform.addEventListener('change', () => this.invalidate());
    this.transform.addEventListener('dragging-changed', (e) => { this.orbit.enabled = !e.value; });
    this.transform.addEventListener('mouseDown', () => this._gizmoStart());
    this.transform.addEventListener('objectChange', () => this._gizmoChange());
    this.transform.addEventListener('mouseUp', () => this._gizmoEnd());
    this.scene.add(this.transform.getHelper());
    this._applySnap();

    this.raycaster = new THREE.Raycaster();
    this._down = null;
    const el = this.renderer.domElement;
    el.addEventListener('pointerdown', (e) => {
      this._down = e.button === 0 && !this.transform.axis ? { x: e.clientX, y: e.clientY } : null;
    });
    el.addEventListener('pointerup', (e) => {
      const d = this._down;
      this._down = null;
      if (!d || this.transform.dragging) return;
      if (Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4) return;      // a drag orbits, it does not pick
      this._pick(e);
    });

    this.frameBox = document.createElement('div');
    this.frameBox.className = 'source-frame';
    this.frameBox.hidden = true;
    container.appendChild(this.frameBox);

    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
  }

  // ------------------------------------------------------------ rendering
  invalidate() {
    if (this._dirty) return;
    this._dirty = true;
    requestAnimationFrame(() => {
      this._dirty = false;
      this.renderer.render(this.scene, this.camera);
    });
  }

  resize() {
    const w = Math.max(1, this.container.clientWidth);
    const h = Math.max(1, this.container.clientHeight);
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = `${w}px`;
    this.renderer.domElement.style.height = `${h}px`;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    if (this.matching) this.matchSourceView(this.matching.spec);
    this.invalidate();
  }

  // ------------------------------------------------------------ parts
  loadSpec(spec) {
    for (const mesh of this.parts.values()) this._dispose(mesh);
    this.parts.clear();
    this.partsGroup.clear();
    this.errors = [];
    for (const c of spec.components) this._build(c);
    this._spec = spec;
    this.selection = this.selection.filter((id) => this.parts.has(id));
    this._rebuildHighlight();
    this._attachGizmo();
    this.invalidate();
    return this.errors;
  }

  /** Rebuild the meshes of `ids` (geometry, material and transform) after an edit. */
  updateParts(spec, ids) {
    this._spec = spec;
    for (const id of ids) {
      const old = this.parts.get(id);
      if (old) {
        this.partsGroup.remove(old);
        this._dispose(old);
        this.parts.delete(id);
      }
      this.errors = this.errors.filter((e) => e.id !== id);
      const c = spec.components.find((x) => x.id === id);
      if (c) this._build(c);
    }
    this._rebuildHighlight();
    this._attachGizmo();
    this.invalidate();
    return this.errors;
  }

  /** Cheap path while dragging: only positions and rotations come from the spec. */
  syncTransforms(spec, ids, skip = null) {
    for (const id of ids) {
      if (id === skip) continue;
      const mesh = this.parts.get(id);
      const c = spec.components.find((x) => x.id === id);
      if (mesh && c) applyTransform(mesh, c);
    }
    this._updateBox();
    this.invalidate();
  }

  _build(c) {
    try {
      const mesh = componentObject(c, { makeCanvas: () => document.createElement('canvas') });
      this.parts.set(c.id, mesh);
      this.partsGroup.add(mesh);
    } catch (e) {
      this.errors.push({ id: c.id, message: e.message });
    }
  }

  _dispose(mesh) {
    mesh.geometry.dispose();
    mesh.material.map?.dispose();
    mesh.material.dispose();
  }

  // ------------------------------------------------------------ selection and gizmo
  setSelection(spec, ids) {
    this.selection = ids.filter((id) => this.parts.has(id));
    this._spec = spec;
    this._rebuildHighlight();
    this._attachGizmo();
    this.invalidate();
  }

  setMode(mode) {
    this.mode = mode;
    this._attachGizmo();
    this.invalidate();
  }

  setSnap(on) {
    this.snap = on;
    this._applySnap();
  }

  _applySnap() {
    this.transform.setTranslationSnap(this.snap ? 0.05 : null);
    this.transform.setRotationSnap(this.snap ? (15 * Math.PI) / 180 : null);
  }

  _rebuildHighlight() {
    for (const child of [...this.highlight.children]) {
      this.highlight.remove(child);
      child.geometry?.dispose();
      child.material?.dispose();
    }
    this.boxHelper = null;
    for (const id of this.selection) {
      const mesh = this.parts.get(id);
      if (!mesh || mesh.userData.kind === 'text') continue;
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry, 25),
        new THREE.LineBasicMaterial({ color: SELECT_COLOR, depthTest: false, transparent: true, opacity: 0.95 }));
      edges.renderOrder = 10;
      edges.userData.noPick = true;
      edges.matrixAutoUpdate = false;
      mesh.updateMatrix();
      edges.matrix.copy(mesh.matrix);
      edges.userData.follows = id;
      this.highlight.add(edges);
    }
    if (this.selection.length > 1) {
      this.boxHelper = new THREE.Box3Helper(new THREE.Box3(), 0xffb347);
      this.boxHelper.material.depthTest = false;
      this.boxHelper.renderOrder = 11;
      this.boxHelper.userData.noPick = true;
      this.highlight.add(this.boxHelper);
      this._updateBox();
    }
  }

  _updateBox() {
    for (const child of this.highlight.children) {
      if (child.userData.follows) {
        const mesh = this.parts.get(child.userData.follows);
        if (mesh) {
          mesh.updateMatrix();
          child.matrix.copy(mesh.matrix);
        }
      }
    }
    if (this.boxHelper) {
      const box = new THREE.Box3();
      for (const id of this.selection) {
        const mesh = this.parts.get(id);
        if (mesh) {
          mesh.updateMatrixWorld(true);
          box.union(new THREE.Box3().setFromObject(mesh));
        }
      }
      this.boxHelper.box.copy(box);
    }
  }

  _attachGizmo() {
    const t = this.transform;
    if (!this.selection.length) {
      t.detach();
      return;
    }
    t.setMode(this.mode);
    t.setSpace('world');
    if (this.selection.length === 1) {
      t.showX = t.showY = t.showZ = true;
      t.attach(this.parts.get(this.selection[0]));
    } else {
      const b = selectionBounds(this._spec, this.selection);
      this.pivot.position.set(...(b ? [b.centre[0], b.centre[1], b.min[2]] : [0, 0, 0]));
      this.pivot.rotation.set(0, 0, 0);
      t.showX = t.showY = this.mode === 'translate';          // several parts turn about the vertical axis only
      t.showZ = true;
      t.attach(this.pivot);
    }
  }

  _gizmoStart() {
    this._startPivot = this.pivot.position.clone();
    this.hooks.onGizmoStart?.({ ids: [...this.selection], mode: this.mode, pivot: [this._startPivot.x, this._startPivot.y, this._startPivot.z] });
  }

  _gizmoChange() {
    if (this.selection.length === 1) {
      const mesh = this.parts.get(this.selection[0]);
      this.hooks.onGizmoChange?.({
        type: 'single', id: this.selection[0], location: mesh.position.toArray(),
        rotation_deg: [deg(mesh.rotation.x), deg(mesh.rotation.y), deg(mesh.rotation.z)],
      });
    } else if (this.mode === 'translate') {
      this.hooks.onGizmoChange?.({ type: 'move', delta: this.pivot.position.clone().sub(this._startPivot).toArray() });
    } else {
      this.hooks.onGizmoChange?.({ type: 'yaw', deg: deg(this.pivot.rotation.z), pivot: [this._startPivot.x, this._startPivot.y] });
    }
    this._updateBox();
  }

  _gizmoEnd() {
    this.hooks.onGizmoEnd?.();
    this._attachGizmo();                                        // re-centre the pivot on the moved parts
    this.invalidate();
  }

  _pick(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(ndc, this.camera);
    const hits = this.raycaster.intersectObjects([...this.parts.values()], false);
    const id = hits.length ? hits[0].object.userData.id : null;
    this.hooks.onPick?.(id, { additive: event.ctrlKey || event.metaKey || event.shiftKey, partOnly: event.altKey });
  }

  // ------------------------------------------------------------ camera
  frame(spec, ids = null) {
    const list = ids && ids.length ? ids : spec.components.map((c) => c.id);
    const b = selectionBounds(spec, list);
    if (!b) return;
    const radius = Math.max(0.6, Math.hypot(...b.size) / 2);
    const dist = radius / Math.sin((this.camera.fov * Math.PI) / 360) * 1.05;
    const dir = new THREE.Vector3(0.55, -0.75, 0.55).normalize();
    this.matching = null;
    this.frameBox.hidden = true;
    this.camera.clearViewOffset();
    this.camera.up.set(0, 0, 1);
    this.camera.fov = 40;
    this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
    this.camera.updateProjectionMatrix();
    this.orbit.target.set(...b.centre);
    this.camera.position.copy(this.orbit.target).addScaledVector(dir, dist);
    this.camera.lookAt(this.orbit.target);
    this.orbit.update();
    this.invalidate();
  }

  /** Look at the booth the way the source picture does (position, target, lens, roll). Returns false for unsupported cameras. */
  matchSourceView(spec) {
    const viewport = { width: this.container.clientWidth, height: this.container.clientHeight };
    try {
      const { frame } = applySpecCamera(this.camera, spec.camera, spec.source, viewport);
      this.orbit.target.set(...spec.camera.target);
      this.matching = { spec };
      Object.assign(this.frameBox.style, { left: `${frame.x}px`, top: `${frame.y}px`, width: `${frame.width}px`, height: `${frame.height}px` });
      this.frameBox.hidden = false;
      this.orbit.update();
      this.invalidate();
      return true;
    } catch (e) {
      this.matching = null;
      this.frameBox.hidden = true;
      this.lastCameraError = e.message;
      return false;
    }
  }

  // ------------------------------------------------------------ export
  /** GLB with one node per part (named by component id), group parents, and spec metadata as extras. Y-up for glTF viewers. */
  async exportGlb(spec) {
    const root = new THREE.Group();
    root.name = 'booth';
    root.rotation.x = -Math.PI / 2;                              // Z-up spec -> Y-up glTF: (x, y, z) -> (x, z, -y)
    const groups = new Map();
    for (const c of spec.components) {
      const part = this.parts.get(c.id);
      if (!part || c.kind === 'text') continue;
      const mesh = new THREE.Mesh(part.geometry, part.material);
      mesh.name = c.id;
      applyTransform(mesh, c);
      mesh.userData = { component_id: c.id, role: c.role, scope_id: c.scope_id, evidence: c.evidence.status, kind: c.kind, ...(c.group ? { group: c.group } : {}) };
      let parent = root;
      if (c.group) {
        if (!groups.has(c.group)) {
          const g = new THREE.Group();
          g.name = `group:${c.group}`;
          root.add(g);
          groups.set(c.group, g);
        }
        parent = groups.get(c.group);
      }
      parent.add(mesh);
    }
    root.updateMatrixWorld(true);
    return new GLTFExporter().parseAsync(root, { binary: true });
  }

  /** PNG data URL of the current view (for the smoke test and quick sharing). */
  snapshot() {
    this.renderer.render(this.scene, this.camera);
    return this.renderer.domElement.toDataURL('image/png');
  }
}
