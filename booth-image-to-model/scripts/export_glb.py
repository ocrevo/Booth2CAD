"""Export a booth spec as a GLB (glTF binary) for viewers and the web editor, without Blender.

Needs numpy and trimesh (trimesh is an optional dependency, imported only when exporting).
Axes: the spec is Z-up (X right, Y back); glTF is Y-up, so (x, y, z) -> (x, z, -y). That is a pure rotation, so the
triangle winding of the geometry builders is kept as is. Colours are converted from sRGB to linear when the material
says so. Each component becomes one node named after its id, with extras (component_id, role, scope_id, evidence,
kind, group); components that share a `group` hang below one parent node named `group:<name>`.

Not carried over (listed in the report, never silently dropped): text components (no glyph geometry here), grid
patterns (procedural shader in Blender), emission strength above 1 (clamped; glTF colour factors are 0..1).
Shading is flat (normals are omitted so every viewer derives face normals); Blender smooths bevel patches.
"""
from __future__ import annotations
import argparse
import json
import struct
import sys
import time
from pathlib import Path

import numpy as np

from geometry import mesh_for, transform_point, triangulate


def _linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _yup(world: np.ndarray) -> np.ndarray:
    return np.column_stack([world[:, 0], world[:, 2], -world[:, 1]])


def gltf_material(component: dict) -> dict:
    """The component's material as a glTF material object (exact floats, linear colour)."""
    m = component['material']
    rgb = list(m['color'][:3])
    if m.get('color_space', 'linear') == 'srgb':
        rgb = [_linear(v) for v in rgb]
    alpha = m['color'][3]
    mat = {'pbrMetallicRoughness': {'baseColorFactor': [round(v, 6) for v in (*rgb, alpha)],
                                    'metallicFactor': round(float(m.get('metallic', 0.0)), 6),
                                    'roughnessFactor': round(float(m.get('roughness', 0.5)), 6)}}
    if float(m.get('emission', 0) or 0) > 0:
        mat['emissiveFactor'] = [round(min(1.0, v), 6) for v in rgb]
    if alpha < 1:
        mat['alphaMode'] = 'BLEND'
    return mat


def component_mesh(component: dict):
    """World-space, Y-up vertices and triangles of one component (numpy arrays)."""
    verts, faces = mesh_for(component)
    world = np.array([transform_point(v, component['location'], component['rotation_deg']) for v in verts], dtype=float)
    return _yup(world), np.array(triangulate(faces), dtype=np.int64)


def build_scene(spec: dict):
    """Return (trimesh.Scene, report). The spec is not modified."""
    import trimesh  # lazy: only the GLB exporter needs it
    scene = trimesh.Scene()
    report = {'components': len(spec['components']), 'exported': 0, 'skipped_text': [], 'pattern_omitted': [],
              'emission_clamped': [], 'groups': []}
    groups = {}
    for c in spec['components']:
        if c['kind'] == 'text':
            report['skipped_text'].append(c['id'])
            continue
        m = c['material']
        verts, tris = component_mesh(c)
        emission = float(m.get('emission', 0) or 0)
        if emission > 1:
            report['emission_clamped'].append(c['id'])
        if m.get('pattern'):
            report['pattern_omitted'].append(c['id'])
        mesh = trimesh.Trimesh(vertices=verts, faces=tris, process=False)
        mesh.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial())  # replaced by exact_materials()
        extras = {'component_id': c['id'], 'role': c['role'], 'scope_id': c['scope_id'],
                  'evidence': c['evidence']['status'], 'kind': c['kind']}
        parent = 'world'
        if c.get('group'):
            extras['group'] = c['group']
            parent = 'group:' + c['group']
            if c['group'] not in groups:
                groups[c['group']] = parent
                scene.graph.update(frame_to=parent, frame_from='world', matrix=np.eye(4))
        mesh.metadata.update(extras)   # becomes the glTF mesh `extras` object
        scene.add_geometry(mesh, node_name=c['id'], geom_name=c['id'], parent_node_name=parent)
        report['exported'] += 1
    report['groups'] = sorted(groups)
    return scene, report


def exact_materials(glb: bytes, spec: dict) -> bytes:
    """Rewrite the material table of a GLB with the exact float factors (trimesh keeps colours as 8-bit, which bands
    dark linear colours). One material per distinct appearance; every mesh is pointed at its own."""
    magic, version, _ = struct.unpack('<4sII', glb[:12])
    json_length, json_type = struct.unpack('<II', glb[12:20])
    doc = json.loads(glb[20:20 + json_length])
    rest = glb[20 + json_length:]
    wanted = {c['id']: gltf_material(c) for c in spec['components'] if c['kind'] != 'text'}
    materials, index = [], {}
    for mesh in doc['meshes']:
        material = wanted[mesh['extras']['component_id']]
        key = json.dumps(material, sort_keys=True)
        if key not in index:
            index[key] = len(materials)
            materials.append(material)
        for primitive in mesh['primitives']:
            primitive['material'] = index[key]
    doc['materials'] = materials
    body = json.dumps(doc, separators=(',', ':')).encode('utf-8')
    body += b' ' * (-len(body) % 4)
    header = struct.pack('<4sII', magic, version, 12 + 8 + len(body) + len(rest))
    return header + struct.pack('<II', len(body), json_type) + body + rest


def export_glb(spec: dict, out_path) -> dict:
    t0 = time.perf_counter()
    scene, report = build_scene(spec)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(exact_materials(scene.export(file_type='glb', include_normals=False), spec))
    report.update({'out': str(out), 'bytes': out.stat().st_size, 'seconds': round(time.perf_counter() - t0, 2),
                   'axes': 'glTF Y-up metres: (x, y, z) -> (x, z, -y)'})
    return report


def run(spec_path, out_path):
    """Validate the spec file, then export. Returns (exit_code, report); never writes a GLB for an invalid spec."""
    from validate_spec import validate
    spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    check = validate(spec, Path(spec_path).resolve().parent)
    if not check['valid']:
        return 2, {'status': 'invalid_spec', 'errors': check['errors'][:10]}
    try:
        report = export_glb(spec, out_path)
    except ImportError as ex:
        return 2, {'status': 'missing_dependency', 'detail': f'GLB export needs trimesh (pip install trimesh): {ex}'}
    report['status'] = 'glb_ready'
    return 0, report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--spec', required=True)
    p.add_argument('--out', required=True, help='Output .glb path')
    a = p.parse_args()
    code, report = run(a.spec, a.out)
    print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr if code else sys.stdout)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
