// Pure spec operations for the editor: no DOM, no three.js, so Node can test every edit.
// The spec stays the single source of truth; operations change it in place and tryEdit() rolls a bad edit back.
// lightValidate() mirrors the main rules of booth-image-to-model/scripts/validate_spec.py; that validator stays authoritative.

import { BUILDERS, GeometryError, meshFor, transformPoint } from './geometry.js';

export const ID_PATTERN = /^[a-z][a-z0-9_]*$/;
export const EDIT_NOTE = 'Edited in the web editor';

// Same table as validate_spec.PARAM_KEYS (a test compares them): [required, allowed].
export const PARAM_KEYS = {
  box: [['size'], ['size', 'bevel_radius', 'bevel_mode', 'segments_per_corner']],
  cylinder: [['radius', 'height'], ['radius', 'height', 'segments']],
  rounded_ring: [['outer_size', 'inner_size', 'outer_radius', 'inner_radius', 'height'],
    ['outer_size', 'inner_size', 'outer_radius', 'inner_radius', 'height', 'segments_per_corner']],
  rounded_portal: [['width', 'height', 'depth', 'side_width', 'beam_height', 'outer_radius', 'inner_radius'],
    ['width', 'height', 'depth', 'side_width', 'beam_height', 'outer_radius', 'inner_radius', 'segments_per_corner']],
  text: [['body', 'size'], ['body', 'size', 'extrude']],
  swept_strip: [['control_points', 'width', 'depth'], ['control_points', 'width', 'depth', 'segments_per_curve']],
  profile_extrusion: [['profile', 'depth'], ['profile', 'depth']],
  arc_panel: [['radius', 'thickness', 'height', 'start_deg', 'end_deg'],
    ['radius', 'thickness', 'height', 'start_deg', 'end_deg', 'segments']],
};

// Parameters that are lengths in metres: they scale with a uniform "scale selection" (angles and counts do not).
export const LENGTH_PARAMS = {
  box: ['size', 'bevel_radius'],
  cylinder: ['radius', 'height'],
  rounded_ring: ['outer_size', 'inner_size', 'outer_radius', 'inner_radius', 'height'],
  rounded_portal: ['width', 'height', 'depth', 'side_width', 'beam_height', 'outer_radius', 'inner_radius'],
  swept_strip: ['control_points', 'width', 'depth'],
  profile_extrusion: ['profile', 'depth'],
  arc_panel: ['radius', 'thickness', 'height'],
  text: ['size', 'extrude'],
};

export class EditError extends Error {}

export const round4 = (v) => Math.round(v * 1e4) / 1e4 + 0; // + 0 turns -0 into 0
const deepScale = (value, f) => (Array.isArray(value) ? value.map((v) => deepScale(v, f)) : round4(value * f));

// ---------------------------------------------------------------- lookups
export const findComponent = (spec, id) => spec.components.find((c) => c.id === id);
export const groupOf = (c) => c.group || null;
export const groupMembers = (spec, group) => spec.components.filter((c) => c.group === group).map((c) => c.id);

/** A click on one part selects its whole group (when it has one); `partOnly` selects just that part. */
export function expandToGroups(spec, ids, partOnly = false) {
  if (partOnly) return [...new Set(ids)];
  const out = new Set(ids);
  for (const id of ids) {
    const c = findComponent(spec, id);
    if (c && c.group) groupMembers(spec, c.group).forEach((m) => out.add(m));
  }
  return [...out];
}

export function groupNames(spec) {
  return [...new Set(spec.components.map((c) => c.group).filter(Boolean))];
}

// ---------------------------------------------------------------- geometry helpers
export function componentBounds(c) {
  const [verts] = meshFor(c);
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  for (const v of verts) {
    const w = transformPoint(v, c.location, c.rotation_deg);
    for (let i = 0; i < 3; i++) {
      lo[i] = Math.min(lo[i], w[i]);
      hi[i] = Math.max(hi[i], w[i]);
    }
  }
  return { min: lo, max: hi };
}

export function selectionBounds(spec, ids) {
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  for (const id of ids) {
    const c = findComponent(spec, id);
    if (!c || c.kind === 'text') continue;
    const b = componentBounds(c);
    for (let i = 0; i < 3; i++) {
      lo[i] = Math.min(lo[i], b.min[i]);
      hi[i] = Math.max(hi[i], b.max[i]);
    }
  }
  if (!Number.isFinite(lo[0])) return null;
  return { min: lo, max: hi, centre: lo.map((v, i) => (v + hi[i]) / 2), size: hi.map((v, i) => v - lo[i]) };
}

// ---------------------------------------------------------------- colours
export const srgbToLinear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
export const linearToSrgb = (c) => (c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055);

/** Material colour -> display sRGB triple in 0..1 (the spec colour is linear unless colour_space is "srgb"). */
export function displayRgb(material) {
  const space = material.color_space || 'linear';
  return material.color.slice(0, 3).map((v) => (space === 'srgb' ? v : linearToSrgb(v)));
}

export function toHex(material) {
  return `#${displayRgb(material).map((v) => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, '0')).join('')}`;
}

/** Hex from a colour picker -> colour array in the material's own colour space (alpha is kept). */
export function fromHex(hex, material) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) throw new EditError(`Not a colour: ${hex}`);
  const space = material.color_space || 'linear';
  const rgb = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255);
  return [...rgb.map((v) => round4(space === 'srgb' ? v : srgbToLinear(v))), material.color[3]];
}

// ---------------------------------------------------------------- edit bookkeeping
export function markEdited(spec, c, { geometry = true } = {}) {
  const ev = c.evidence;
  if (ev.status === 'observed') {
    ev.status = 'inferred';
    ev.note = `${EDIT_NOTE}; was observed in the source image.`;
  } else if (!String(ev.note || '').includes(EDIT_NOTE)) {
    ev.note = `${ev.note ? `${ev.note} ` : ''}${EDIT_NOTE}.`;
  }
  // Landmarks and the fitted camera describe the source image, not the edited model.
  if (geometry && spec.camera && spec.camera.fit_status !== 'unfitted') spec.camera.fit_status = 'unfitted';
}

export function syncFootprint(spec) {
  const floor = spec.components.find((c) => c.role === 'floor' && c.kind === 'box');
  if (floor) spec.scale.footprint_m = [round4(floor.params.size[0]), round4(floor.params.size[1])];
}

function checkBuildable(c) {
  if (c.kind === 'text') return;
  if (!BUILDERS[c.kind]) throw new EditError(`${c.id}: unsupported primitive ${c.kind}`);
  try {
    meshFor(c);
  } catch (e) {
    throw new EditError(`${c.id}: ${e.message}`);
  }
}

/** Run an edit; refuse and roll back when a touched part no longer builds. Returns { ok, error }. */
export function tryEdit(spec, fn) {
  const backup = structuredClone(spec);
  try {
    const touched = fn(spec) || [];
    for (const id of touched) {
      const c = findComponent(spec, id);
      if (c) checkBuildable(c);
    }
    syncFootprint(spec);
    return { ok: true };
  } catch (e) {
    for (const key of Object.keys(spec)) delete spec[key];
    Object.assign(spec, backup);
    if (e instanceof EditError || e instanceof GeometryError) return { ok: false, error: e.message };
    throw e; // a programming error, not a refused edit
  }
}

const need = (spec, id) => {
  const c = findComponent(spec, id);
  if (!c) throw new EditError(`Unknown component ${id}`);
  return c;
};

// ---------------------------------------------------------------- edits (use inside tryEdit)
export function translate(spec, ids, delta) {
  for (const id of ids) {
    const c = need(spec, id);
    c.location = c.location.map((v, i) => round4(v + delta[i]));
    markEdited(spec, c);
  }
  return ids;
}

/** Turn parts about the vertical axis through `pivot` [x, y]; Euler rz simply gains the angle (R = Rz*Ry*Rx). */
export function rotateYaw(spec, ids, deg, pivot) {
  const a = (deg * Math.PI) / 180;
  const [cos, sin] = [Math.cos(a), Math.sin(a)];
  for (const id of ids) {
    const c = need(spec, id);
    const dx = c.location[0] - pivot[0];
    const dy = c.location[1] - pivot[1];
    c.location = [round4(pivot[0] + dx * cos - dy * sin), round4(pivot[1] + dx * sin + dy * cos), c.location[2]];
    c.rotation_deg = [c.rotation_deg[0], c.rotation_deg[1], round4(c.rotation_deg[2] + deg)];
    markEdited(spec, c);
  }
  return ids;
}

export function setTransform(spec, id, { location, rotation_deg: rotation }) {
  const c = need(spec, id);
  if (location) c.location = location.map(round4);
  if (rotation) c.rotation_deg = rotation.map(round4);
  markEdited(spec, c);
  return [id];
}

/** Set one parameter; `path` is e.g. ['radius'] or ['size', 0]. */
export function setParam(spec, id, path, value) {
  const c = need(spec, id);
  let target = c.params;
  for (const key of path.slice(0, -1)) target = target[key];
  target[path[path.length - 1]] = value;
  markEdited(spec, c);
  return [id];
}

export function removeParam(spec, id, key) {
  const c = need(spec, id);
  delete c.params[key];
  markEdited(spec, c);
  return [id];
}

/** patch: { color?: [r,g,b,a], roughness?, metallic?, emission? } applied to every id. */
export function setMaterial(spec, ids, patch) {
  for (const id of ids) {
    const c = need(spec, id);
    for (const [key, value] of Object.entries(patch)) {
      if (value === undefined) continue;
      if (value === null) delete c.material[key];
      else c.material[key] = value;
    }
    markEdited(spec, c, { geometry: false });
  }
  return [];
}

export function setGroup(spec, ids, name) {
  if (name !== null && !ID_PATTERN.test(name)) throw new EditError('Group names use lowercase letters, digits and underscores, starting with a letter');
  for (const id of ids) {
    const c = need(spec, id);
    if (name) c.group = name;
    else delete c.group;
    markEdited(spec, c, { geometry: false });
  }
  return [];
}

/** Uniform scale about `pivot` [x, y, z]: positions and every length parameter; rotations, angles and counts stay. */
export function scaleSelection(spec, ids, factor, pivot) {
  if (!(Number.isFinite(factor) && factor > 0.05 && factor < 20)) throw new EditError('Scale factor must be between 0.05 and 20');
  for (const id of ids) {
    const c = need(spec, id);
    c.location = c.location.map((v, i) => round4(pivot[i] + (v - pivot[i]) * factor));
    for (const key of LENGTH_PARAMS[c.kind] || []) {
      if (key in c.params) c.params[key] = deepScale(c.params[key], factor);
    }
    const pattern = c.material.pattern;
    if (pattern) {
      if (Array.isArray(pattern.spacing)) pattern.spacing = pattern.spacing.map((v) => round4(v * factor));
      if (typeof pattern.line_width === 'number') pattern.line_width = round4(pattern.line_width * factor);
      if (Array.isArray(pattern.offset)) pattern.offset = pattern.offset.map((v) => round4(v * factor));
    }
    markEdited(spec, c);
  }
  return ids;
}

const unusedId = (taken, base) => {
  let n = 2;
  while (taken.has(`${base}_${n}`)) n++;
  return `${base}_${n}`;
};

/** Copy parts (offset by `offset`); a copied group gets a new group name. Returns the new ids. */
export function duplicate(spec, ids, offset = [0.6, 0, 0]) {
  const takenIds = new Set(spec.components.map((c) => c.id));
  const takenGroups = new Set(groupNames(spec));
  const groupMap = new Map();
  const created = [];
  for (const id of ids) {
    const src = need(spec, id);
    let group = null;
    if (src.group) {
      if (!groupMap.has(src.group)) {
        const g = unusedId(new Set([...takenGroups, ...takenIds]), src.group);
        groupMap.set(src.group, g);
        takenGroups.add(g);
      }
      group = groupMap.get(src.group);
    }
    let base = src.id;
    if (src.group && src.id.startsWith(src.group)) base = group + src.id.slice(src.group.length);
    const newId = takenIds.has(base) ? unusedId(takenIds, base) : base;
    takenIds.add(newId);
    const copy = structuredClone(src);
    copy.id = newId;
    copy.critical = false;
    if (group) copy.group = group;
    else delete copy.group;
    copy.location = copy.location.map((v, i) => round4(v + offset[i]));
    copy.evidence = { status: 'inferred', note: `Duplicated in the web editor from ${src.id}.` };
    spec.components.push(copy);
    created.push(newId);
  }
  spec.camera.fit_status = 'unfitted';
  return created;
}

/** Remove parts and everything that points at them. Critical parts need `force`; the floor can never go. */
export function remove(spec, ids, { force = false } = {}) {
  const set = new Set(ids);
  const doomed = spec.components.filter((c) => set.has(c.id));
  if (doomed.some((c) => c.role === 'floor')) throw new EditError('The floor defines the footprint and cannot be deleted');
  const critical = doomed.filter((c) => c.critical).map((c) => c.id);
  if (critical.length && !force) throw new EditError(`Critical parts selected (${critical.join(', ')}): confirm to delete them`);
  const summary = { removed: doomed.map((c) => c.id), requirements: 0, landmarks: 0, scopes: [] };
  spec.components = spec.components.filter((c) => !set.has(c.id));
  const reqs = spec.requirements.length;
  spec.requirements = spec.requirements.filter((r) => !set.has(r.component_id));
  summary.requirements = reqs - spec.requirements.length;
  const marks = spec.landmarks.length;
  spec.landmarks = spec.landmarks.filter((l) => !set.has(l.component_id));
  summary.landmarks = marks - spec.landmarks.length;
  const used = new Set(spec.components.map((c) => c.scope_id));
  const before = spec.scope.decisions;
  spec.scope.decisions = before.filter((d) => d.decision !== 'include' || used.has(d.id));
  summary.scopes = before.filter((d) => !spec.scope.decisions.includes(d)).map((d) => d.id);
  if (spec.components.length === 0) throw new EditError('A spec needs at least one component');
  if (doomed.length) spec.camera.fit_status = 'unfitted';
  return summary;
}

// ---------------------------------------------------------------- validation (light)
const finiteVec = (v, n) => Array.isArray(v) && v.length === n && v.every((x) => typeof x === 'number' && Number.isFinite(x));

export function lightValidate(spec) {
  const issues = [];
  const add = (level, code, where, message) => issues.push({ level, code, where, message });
  for (const key of ['schema_version', 'project', 'source', 'scale', 'scope', 'components', 'camera', 'requirements', 'landmarks', 'uncertainties', 'quality']) {
    if (!(key in spec)) add('error', 'MISSING_FIELD', key, 'Required top-level field missing');
  }
  if (issues.length) return issues;
  const scopes = new Map(spec.scope.decisions.map((d) => [d.id, d]));
  const ids = new Set();
  for (const c of spec.components) {
    const where = c.id || '(no id)';
    if (typeof c.id !== 'string' || !ID_PATTERN.test(c.id)) add('error', 'COMPONENT_ID', where, 'Use a stable lowercase identifier');
    if (ids.has(c.id)) add('error', 'DUPLICATE_COMPONENT', where, 'Duplicate component id');
    ids.add(c.id);
    if ('group' in c && !(typeof c.group === 'string' && ID_PATTERN.test(c.group))) add('error', 'COMPONENT_GROUP', where, 'Group must be a lowercase identifier');
    const scope = scopes.get(c.scope_id);
    if (!scope || scope.owner !== 'booth' || scope.decision !== 'include') add('error', 'SCOPE_BLOCKED', where, 'Component does not resolve to a confirmed booth inclusion');
    if (!finiteVec(c.location, 3)) add('error', 'TRANSFORM', where, 'location needs three finite numbers');
    if (!finiteVec(c.rotation_deg, 3)) add('error', 'TRANSFORM', where, 'rotation_deg needs three finite numbers');
    if (!c.evidence || !['observed', 'inferred'].includes(c.evidence.status)) add('error', 'EVIDENCE_STATUS', where, 'Use observed or inferred');
    else if (!c.evidence.note) add('error', 'EVIDENCE_NOTE', where, 'Document the basis of the part');
    const roi = c.evidence && c.evidence.roi_xyxy_norm;
    if (c.evidence && (c.evidence.status === 'observed' || roi) && !(finiteVec(roi, 4) && roi[0] >= 0 && roi[0] < roi[2] && roi[2] <= 1 && roi[1] >= 0 && roi[1] < roi[3] && roi[3] <= 1)) {
      add('error', 'OBSERVATION_ROI', where, 'Observed parts need a valid source-image region');
    }
    if (!c.material || !finiteVec(c.material.color, 4)) add('error', 'MATERIAL', where, 'material.color needs four numbers');
    const keys = PARAM_KEYS[c.kind];
    if (!keys) {
      add('error', 'UNSUPPORTED_PRIMITIVE', where, `No builder for ${c.kind}`);
      continue;
    }
    for (const k of keys[0]) if (!(k in (c.params || {}))) add('error', 'MISSING_PARAMETER', `${where}.params.${k}`, 'Required parameter missing');
    for (const k of Object.keys(c.params || {})) if (!keys[1].includes(k)) add('error', 'UNUSED_PARAMETER', `${where}.params.${k}`, 'Parameter is not used by this primitive');
    if (c.kind !== 'text') {
      try {
        meshFor(c);
      } catch (e) {
        add('error', 'GEOMETRY', where, e.message);
      }
    }
  }
  const floors = spec.components.filter((c) => c.role === 'floor');
  if (floors.length !== 1 || floors[0].kind !== 'box') add('error', 'FOOTPRINT_GEOMETRY', 'components', 'Exactly one rectangular floor component is required');
  else if ([0, 1].some((i) => Math.abs(floors[0].params.size[i] - spec.scale.footprint_m[i]) > 1e-6)) {
    add('error', 'FOOTPRINT_MISMATCH', 'scale.footprint_m', 'Footprint must equal the floor size');
  }
  for (const d of scopes.values()) {
    if (d.decision === 'include' && !spec.components.some((c) => c.scope_id === d.id)) add('error', 'OMITTED_INCLUDED_OBJECT', `scope.${d.id}`, 'Included scope has no geometry');
  }
  for (const r of spec.requirements) {
    const c = findComponent(spec, r.component_id);
    if (!c) add('error', 'MISSING_REQUIRED_COMPONENT', r.id, `Requirement points at missing ${r.component_id}`);
    else {
      if (r.kind && c.kind !== r.kind) add('error', 'WRONG_PRIMITIVE', r.id, `${c.id} must use ${r.kind}`);
      if (r.must_be_critical && !c.critical) add('error', 'PRIORITY_DOWNGRADE', r.id, `${c.id} must stay critical`);
    }
  }
  for (const l of spec.landmarks) if (!findComponent(spec, l.component_id)) add('error', 'LANDMARK_COMPONENT', l.id, `Landmark points at missing ${l.component_id}`);
  return issues;
}
