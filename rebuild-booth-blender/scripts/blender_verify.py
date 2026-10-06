"""Reopen and inspect the actual .blend in a separate native Blender process."""
from __future__ import annotations
import argparse
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from common import read_json,write_json,digest,code_hash,file_sha
from geometry import mesh_for


def main():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--blend',required=True);p.add_argument('--report',required=True)
    a=p.parse_args();spec=read_json(a.spec);errors=[]
    if not bpy.app.background:raise RuntimeError('Verification requires a separate background process')
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()),use_scripts=False)
    scene=bpy.context.scene
    if scene.get('spec_sha256')!=digest(spec):errors.append('stale_spec')
    if scene.get('builder_sha256')!=code_hash():errors.append('stale_builder')
    expected={c['id']:c for c in spec['components']};observed={}
    geometry_types={'MESH','FONT','CURVE','SURFACE','META','VOLUME','POINTCLOUD','GREASEPENCIL'}
    for obj in scene.objects:
        owner=obj.get('ownership')
        if owner not in ('booth','render_rig'):errors.append('unclassified_object:'+obj.name)
        if owner=='render_rig' and obj.type not in ('CAMERA','LIGHT'):errors.append('rig_contains_geometry:'+obj.name)
        if obj.type in geometry_types:
            ident=obj.get('component_id')
            if owner!='booth' or ident not in expected:errors.append('unplanned_geometry:'+obj.name);continue
            if ident in observed:errors.append('duplicate_component:'+ident)
            observed[ident]=obj;c=expected[ident]
            if obj.hide_render:errors.append('hidden_required_component:'+ident)
            if obj.get('scope_id')!=c['scope_id']:errors.append('scope_mismatch:'+ident)
            if any(abs(obj.location[i]-c['location'][i])>1e-5 for i in range(3)):errors.append('placement_mismatch:'+ident)
            if any(abs(obj.rotation_euler[i]-math.radians(c['rotation_deg'][i]))>1e-5 for i in range(3)):errors.append('rotation_mismatch:'+ident)
            if any(abs(v-1)>1e-6 for v in obj.scale):errors.append('unplanned_scale:'+ident)
            if obj.modifiers:errors.append('unreviewed_modifiers:'+ident)
            if c['kind']=='text':
                if obj.type!='FONT' or obj.data.body!=c['params']['body']:errors.append('text_mismatch:'+ident)
            elif obj.type!='MESH':errors.append('mesh_type_mismatch:'+ident)
            else:
                v,f=mesh_for(c)
                if len(obj.data.vertices)!=len(v) or len(obj.data.polygons)!=len(f):errors.append('mesh_count_mismatch:'+ident)
                elif any(abs(obj.data.vertices[i].co[j]-v[i][j])>1e-5 for i in range(len(v)) for j in range(3)):errors.append('mesh_shape_mismatch:'+ident)
                elif any(tuple(obj.data.polygons[i].vertices)!=tuple(f[i]) for i in range(len(f))):errors.append('mesh_topology_mismatch:'+ident)
    for ident in set(expected)-set(observed):errors.append('missing_component:'+ident)
    result={'native_blender_reopened':True,'geometry_verified':not errors,'errors':errors,
            'blender_version':bpy.app.version_string,'spec_sha256':digest(spec),'builder_sha256':code_hash(),
            'blend_sha256':file_sha(a.blend),'booth_object_count':len(observed),
            'note':'Native file/geometry verification only. Image fidelity still needs reference QA and visual review.'}
    write_json(a.report,result)
    if errors:raise RuntimeError('Blender verification failed: '+str(errors))

if __name__=='__main__':main()
