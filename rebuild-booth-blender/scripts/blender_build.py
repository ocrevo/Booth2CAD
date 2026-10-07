"""Build v2 spec in a NEW Blender background process. No venue or ground mesh.

blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python scripts/blender_build.py -- --spec project/spec.json --out runs/001 --render --part-masks

This file requires native Blender. Pure-Python unit tests are not a Blender test.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Quaternion
from bpy_extras.object_utils import world_to_camera_view
from common import read_json,write_json,digest,code_hash,file_sha,render_rig,material_rgba
from validate_spec import validate
from geometry import mesh_for
from material_patterns import apply_grid


def arguments():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--out',required=True)
    p.add_argument('--render',action='store_true');p.add_argument('--part-masks',action='store_true');p.add_argument('--samples',type=int,default=16)
    p.add_argument('--client-exposure',type=float,default=-.5,help='Exposure offset in EV, applied only to client_render.png')
    return p.parse_args(argv)


def material(name,params,emission_only=False,component=None):
    m=bpy.data.materials.new(name);m.use_nodes=True
    n=m.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial')
    color=material_rgba(params)
    if emission_only:
        shader=n.new('ShaderNodeEmission');shader.inputs['Color'].default_value=color;shader.inputs['Strength'].default_value=1
    else:
        shader=n.new('ShaderNodeBsdfPrincipled');shader.inputs['Base Color'].default_value=color
        shader.inputs['Alpha'].default_value=color[3]
        shader.inputs['Roughness'].default_value=params.get('roughness',.5)
        shader.inputs['Metallic'].default_value=params.get('metallic',0)
        shader.inputs['Emission Color'].default_value=color
        shader.inputs['Emission Strength'].default_value=params.get('emission',0)
        if component is not None:apply_grid(n,m.node_tree.links,shader,params,component)
    m.node_tree.links.new(shader.outputs[0],out.inputs['Surface']);return m


def point_camera(obj,target,roll_deg=0):
    q=(Vector(target)-obj.location).to_track_quat('-Z','Y')
    obj.rotation_mode='QUATERNION';obj.rotation_quaternion=q@Quaternion((0,0,1),math.radians(roll_deg))


def main():
    if not bpy.app.background: raise RuntimeError('Use a new background process. Refusing to clear a potentially unsaved interactive scene.')
    a=arguments();spec_path=Path(a.spec).resolve();spec=read_json(spec_path)
    if not math.isfinite(a.client_exposure):raise ValueError('client exposure must be a finite EV offset')
    check=validate(spec,spec_path.parent)
    if not check['valid']:raise ValueError(json.dumps(check,ensure_ascii=False))
    source=(spec_path.parent/spec['source']['image']).resolve()
    # Blender decodes the real input; no Pillow/pip dependency is needed here.
    source_probe=bpy.data.images.load(str(source),check_existing=False)
    try:
        if not source_probe.has_data:_=source_probe.pixels[0]
        source_size=list(source_probe.size)
    finally:bpy.data.images.remove(source_probe)
    check=validate(spec,spec_path.parent,source_size=source_size)
    if not check['valid']:raise ValueError(json.dumps(check,ensure_ascii=False))
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    blend=out/'booth.blend'
    if blend.exists():raise FileExistsError('Use a fresh run directory; existing .blend is not overwritten')
    write_json(out/'spec.json',spec)
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
            elif c['kind']=='arc_panel':
                # Only the curved inner/outer sides interpolate normals;
                # level caps and radial end cuts remain flat.
                for i,p in enumerate(data.polygons):p.use_smooth=i<len(data.polygons)-2 and i%4<2
            elif c['kind']=='swept_strip':
                for i,p in enumerate(data.polygons):p.use_smooth=i<len(data.polygons)-2 and i%4 in (1,3)
            elif c['kind']=='box' and c['params'].get('bevel_radius',0)>0:
                for p in data.polygons:
                    coords=[data.vertices[i].co for i in p.vertices]
                    # Large planar panels stay flat; spherical and cylindrical
                    # bevel patches shade continuously without live modifiers.
                    p.use_smooth=not any(max(v[axis] for v in coords)-min(v[axis] for v in coords)<1e-7 for axis in range(3))
        obj=bpy.data.objects.new(c['id'],data)
        group='BOOTH_GRAPHICS' if c['kind']=='text' else ('BOOTH_STRUCTURE' if c['critical'] else 'BOOTH_FURNITURE')
        collections[group].objects.link(obj);obj.location=c['location'];obj.rotation_euler=[math.radians(x) for x in c['rotation_deg']]
        obj['ownership']='booth';obj['component_id']=c['id'];obj['scope_id']=c['scope_id'];obj['primitive_kind']=c['kind']
        obj['dimension_basis']=spec['scale']['basis'];obj['evidence_status']=c['evidence']['status']
        obj.data.materials.append(material(c['id']+'_material',c['material'],component=c));built[c['id']]=obj
    bpy.context.view_layer.update()
    corners=[obj.matrix_world@Vector(corner) for obj in built.values() for corner in obj.bound_box]
    bounds=[[min(v[i] for v in corners) for i in range(3)],[max(v[i] for v in corners) for i in range(3)]]
    rig=render_rig(bounds,scene.render.resolution_x/scene.render.resolution_y,spec['camera'])
    def camera(name,config):
        data=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,data);collections['RENDER_RIG'].objects.link(obj)
        obj.location=config['position'];point_camera(obj,config['target'],config.get('roll_deg',0));obj['ownership']='render_rig'
        data.type='PERSP' if config['projection']=='perspective' else 'ORTHO';data.sensor_fit='HORIZONTAL'
        data.sensor_width=config.get('sensor_width_mm',36);data.lens=config.get('lens_mm',40);data.ortho_scale=config.get('ortho_scale',8)
        data.shift_x=.5-config['principal_point'][0]
        data.shift_y=(config['principal_point'][1]-.5)*scene.render.resolution_y/scene.render.resolution_x
        data.clip_start=max(rig['extent']*.00001,.00001)
        data.clip_end=max((Vector(config['position'])-Vector(rig['centre'])).length+rig['extent']*3,rig['extent']*5)
        return obj
    hero=camera('CAM_REFERENCE',spec['camera'])
    inspection=camera('CAM_INSPECTION',rig['inspection_camera'])
    for light in rig['lights']:
        data=bpy.data.lights.new(light['name'],'AREA');data.energy=light['energy'];data.shape='DISK';data.size=light['size']
        obj=bpy.data.objects.new(light['name'],data);collections['RENDER_RIG'].objects.link(obj)
        obj.location=light['position'];point_camera(obj,light['target']);obj['ownership']='render_rig'
    scene.camera=hero;scene['spec_sha256']=digest(spec);scene['builder_sha256']=code_hash();scene['scope']='booth_only'
    scene['delivery_status']='draft_unverified';scene['scale_basis']=spec['scale']['basis']
    scene['no_venue_geometry']=True
    scene['render_rig_json']=json.dumps(rig,ensure_ascii=False)
    tx=bpy.data.texts.new('SPEC.json');tx.write(json.dumps(spec,ensure_ascii=False,indent=2))
    im=bpy.data.images.load(str(source));im.name='Source reference (not rendered)'
    # Blender may lazily load the buffer. Read it before changing filepath_raw,
    # otherwise save() tries to load the as-yet nonexistent destination.
    if not im.has_data:_=im.pixels[0]
    # Encode a genuine PNG without a render/view transform. Renaming JPEG bytes
    # to .png confuses downstream file readers and is not a faithful artifact.
    im.file_format='PNG';im.filepath_raw=str(out/'source_reference.png');im.save();im.pack()
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
        # Customer display is a separate image, preserving the exact transparent
        # acceptance camera/image above and adding no venue or studio geometry.
        background=world.node_tree.nodes.get('Background')
        old_color=tuple(background.inputs['Color'].default_value)
        old_strength=background.inputs['Strength'].default_value
        old_transform=scene.view_settings.view_transform
        old_exposure=scene.view_settings.exposure
        try:scene.view_settings.view_transform='Khronos PBR Neutral'
        except TypeError:scene.view_settings.view_transform='Standard'
        scene.view_settings.exposure=old_exposure+a.client_exposure
        background.inputs['Color'].default_value=(.8,.8,.8,1);background.inputs['Strength'].default_value=.8
        scene.render.film_transparent=False;scene.camera=hero
        scene.render.filepath=str(out/'client_render.png');bpy.ops.render.render(write_still=True);renders.append('client_render.png')
        background.inputs['Color'].default_value=old_color;background.inputs['Strength'].default_value=old_strength
        scene.view_settings.view_transform=old_transform
        scene.view_settings.exposure=old_exposure
        scene.render.film_transparent=True
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
               'booth_object_count':len(built),'renders':renders,'scope':'booth_only','render_rig':rig,
               'client_exposure_ev':a.client_exposure,
               'render_purposes':{'reference_render.png':'transparent_acceptance','inspection_render.png':'transparent_secondary_view',
                                  'client_render.png':'neutral_customer_display'},'notes':check['warnings']})

if __name__=='__main__':main()
