"""Build v2 spec in a NEW Blender background process. No venue or ground mesh.

blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python scripts/blender_build.py -- --spec project/spec.json --out runs/001 --render --part-masks

This file requires native Blender. Pure-Python unit tests are not a Blender test.
"""
from __future__ import annotations
import argparse
import json
import math
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Quaternion
from bpy_extras.object_utils import world_to_camera_view
from common import read_json,write_json,digest,code_hash,file_sha
from validate_spec import validate
from geometry import mesh_for


def arguments():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--out',required=True)
    p.add_argument('--render',action='store_true');p.add_argument('--part-masks',action='store_true');p.add_argument('--samples',type=int,default=16)
    return p.parse_args(argv)


def material(name,params,emission_only=False):
    m=bpy.data.materials.new(name);m.use_nodes=True
    n=m.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial')
    if emission_only:
        shader=n.new('ShaderNodeEmission');shader.inputs['Color'].default_value=params['color'];shader.inputs['Strength'].default_value=1
    else:
        shader=n.new('ShaderNodeBsdfPrincipled');shader.inputs['Base Color'].default_value=params['color']
        shader.inputs['Roughness'].default_value=params.get('roughness',.5)
        shader.inputs['Metallic'].default_value=params.get('metallic',0)
        shader.inputs['Emission Color'].default_value=params['color']
        shader.inputs['Emission Strength'].default_value=params.get('emission',0)
    m.node_tree.links.new(shader.outputs[0],out.inputs['Surface']);return m


def point_camera(obj,target,roll_deg=0):
    q=(Vector(target)-obj.location).to_track_quat('-Z','Y')
    obj.rotation_mode='QUATERNION';obj.rotation_quaternion=q@Quaternion((0,0,1),math.radians(roll_deg))


def main():
    if not bpy.app.background: raise RuntimeError('Use a new background process. Refusing to clear a potentially unsaved interactive scene.')
    a=arguments();spec_path=Path(a.spec).resolve();spec=read_json(spec_path)
    check=validate(spec,spec_path.parent)
    if not check['valid']:raise ValueError(json.dumps(check,ensure_ascii=False))
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    blend=out/'booth.blend'
    if blend.exists():raise FileExistsError('Use a fresh run directory; existing .blend is not overwritten')
    source=(spec_path.parent/spec['source']['image']).resolve()
    shutil.copy2(source,out/'source_reference.png');write_json(out/'spec.json',spec)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=max(1,a.samples)
    scene.cycles.use_denoising=True
    scene.render.resolution_x=spec['source']['width'];scene.render.resolution_y=spec['source']['height'];scene.render.resolution_percentage=100
    scene.render.pixel_aspect_x=1;scene.render.pixel_aspect_y=1;scene.render.film_transparent=True
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    world=bpy.data.worlds.new('Neutral world, no venue geometry');world.use_nodes=True;scene.world=world
    world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.25,.25,.25,1)
    world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.5
    collections={}
    for name in ('BOOTH_STRUCTURE','BOOTH_FURNITURE','BOOTH_GRAPHICS','RENDER_RIG'):
        col=bpy.data.collections.new(name);scene.collection.children.link(col);collections[name]=col
    built={}
    for c in spec['components']:
        if c['kind']=='text':
            data=bpy.data.curves.new(c['id'],'FONT');data.body=c['params']['body'];data.size=c['params']['size']
            data.align_x='CENTER';data.align_y='CENTER';data.extrude=c['params'].get('extrude',.001)
            # Keep Blender's built-in font. No container font files are distributed.
        else:
            v,f=mesh_for(c);data=bpy.data.meshes.new(c['id']);data.from_pydata(v,[],f);data.update()
            if c['kind'] in ('rounded_ring','cylinder'):
                for i,p in enumerate(data.polygons):p.use_smooth=(i%4<2) if c['kind']=='rounded_ring' else (i%3==0)
        obj=bpy.data.objects.new(c['id'],data)
        group='BOOTH_GRAPHICS' if c['kind']=='text' else ('BOOTH_STRUCTURE' if c['critical'] else 'BOOTH_FURNITURE')
        collections[group].objects.link(obj);obj.location=c['location'];obj.rotation_euler=[math.radians(x) for x in c['rotation_deg']]
        obj['ownership']='booth';obj['component_id']=c['id'];obj['scope_id']=c['scope_id'];obj['primitive_kind']=c['kind']
        obj['dimension_basis']=spec['scale']['basis'];obj['evidence_status']=c['evidence']['status']
        obj.data.materials.append(material(c['id']+'_material',c['material']));built[c['id']]=obj
    def camera(name,config):
        data=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,data);collections['RENDER_RIG'].objects.link(obj)
        obj.location=config['position'];point_camera(obj,config['target'],config.get('roll_deg',0));obj['ownership']='render_rig'
        data.type='PERSP' if config['projection']=='perspective' else 'ORTHO';data.sensor_fit='HORIZONTAL'
        data.sensor_width=config.get('sensor_width_mm',36);data.lens=config.get('lens_mm',40);data.ortho_scale=config.get('ortho_scale',8)
        data.shift_x=.5-config['principal_point'][0]
        data.shift_y=(config['principal_point'][1]-.5)*scene.render.resolution_y/scene.render.resolution_x
        data.clip_end=500;return obj
    hero=camera('CAM_REFERENCE',spec['camera'])
    inspection=camera('CAM_INSPECTION',{'projection':'perspective','position':[-9,-11,7.5],'target':[0,0,2],
                                     'lens_mm':40,'sensor_width_mm':36,'principal_point':[.5,.5]})
    for name,location,power,size in [('Key',(2,-5,7),1200,5),('Fill',(-4,-1,5),800,4),('Rim',(1,4,7),900,4)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        obj=bpy.data.objects.new(name,data);collections['RENDER_RIG'].objects.link(obj);obj.location=location;point_camera(obj,[0,0,2]);obj['ownership']='render_rig'
    scene.camera=hero;scene['spec_sha256']=digest(spec);scene['builder_sha256']=code_hash();scene['scope']='booth_only'
    scene['delivery_status']='draft_unverified';scene['scale_basis']=spec['scale']['basis']
    scene['no_venue_geometry']=True
    tx=bpy.data.texts.new('SPEC.json');tx.write(json.dumps(spec,ensure_ascii=False,indent=2))
    im=bpy.data.images.load(str(source));im.name='Source reference (not rendered)';im.pack()
    bpy.context.view_layer.update()
    anchors=[]
    for lm in spec['landmarks']:
        co=built[lm['component_id']].matrix_world@Vector(lm['local_xyz'])
        ndc=world_to_camera_view(scene,hero,co)
        anchors.append({'id':lm['id'],'uv':[float(ndc.x),float(1-ndc.y)],'depth':float(ndc.z)})
    write_json(out/'projected_landmarks.json',anchors)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
    renders=[]
    if a.render:
        for cam,name in ((hero,'reference_render.png'),(inspection,'inspection_render.png')):
            scene.camera=cam;scene.render.filepath=str(out/name);bpy.ops.render.render(write_still=True);renders.append(name)
    if a.part_masks:
        old_view=(scene.view_settings.view_transform,scene.view_settings.look,scene.view_settings.exposure,scene.view_settings.gamma)
        scene.camera=hero;old={obj.name:list(obj.data.materials) for obj in built.values()}
        white=material('MASK_WHITE',{'color':(1,1,1,1)},True);black=material('MASK_BLACK',{'color':(0,0,0,1)},True)
        old_world=world.node_tree.nodes.get('Background').inputs['Strength'].default_value
        world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0
        scene.render.film_transparent=False;scene.render.image_settings.color_mode='BW';scene.cycles.samples=1;scene.cycles.use_denoising=False
        scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
        masks=out/'part_masks';masks.mkdir(exist_ok=True)
        for c in spec['components']:
            if not c['critical']:continue
            for ident,obj in built.items():
                obj.data.materials.clear();obj.data.materials.append(white if ident==c['id'] else black)
            scene.render.filepath=str(masks/(c['id']+'.png'));bpy.ops.render.render(write_still=True)
        for obj in built.values():
            obj.data.materials.clear()
            for m in old[obj.name]:obj.data.materials.append(m)
        world.node_tree.nodes.get('Background').inputs['Strength'].default_value=old_world
        scene.render.film_transparent=True;scene.render.image_settings.color_mode='RGBA';scene.cycles.samples=max(1,a.samples);scene.cycles.use_denoising=True
        scene.view_settings.view_transform=old_view[0];scene.view_settings.look=old_view[1];scene.view_settings.exposure=old_view[2];scene.view_settings.gamma=old_view[3]
    scene.camera=hero
    bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
    artifact_names=['booth.blend','source_reference.png','projected_landmarks.json']+renders
    artifact_names += [str(p.relative_to(out)) for p in sorted((out/'part_masks').glob('*.png'))] if (out/'part_masks').exists() else []
    hashed_artifacts=[{'path':name,'sha256':file_sha(out/name)} for name in artifact_names]
    write_json(out/'build_report.json',{'artifacts':hashed_artifacts,'status':'built_not_verified','blender_version':bpy.app.version_string,
               'spec_sha256':digest(spec),'builder_sha256':code_hash(),'blend_sha256':file_sha(blend),
               'booth_object_count':len(built),'renders':renders,'scope':'booth_only','notes':check['warnings']})

if __name__=='__main__':main()
