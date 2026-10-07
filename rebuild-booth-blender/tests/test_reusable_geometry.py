"""Geometry regressions for editable customer render building blocks."""
from __future__ import annotations
import copy
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import jsonschema
import numpy as np
import trimesh
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import read_json,write_json,material_rgba,render_rig,file_sha
from geometry import mesh_for,triangulate
from validate_spec import validate


def solid(kind,params):
    vertices,faces=mesh_for({'kind':kind,'params':params})
    return trimesh.Trimesh(vertices,triangulate(faces),process=False)


STRIP={'control_points':[[0,-2],[0,-1],[0,0],[0,1],[0,1.6],[.55,1.5],[.55,2.05]],
       'width':.085,'depth':.12,'segments_per_curve':16}


class ReusableGeometryTests(unittest.TestCase):
    def test_beveled_box_is_closed_with_requested_outer_dimensions(self):
        mesh=solid('box',{'size':[2.6,1.4,.9],'bevel_radius':.12})
        self.assertTrue(mesh.is_watertight);self.assertTrue(mesh.is_winding_consistent)
        self.assertEqual(mesh.euler_number,2);self.assertGreater(mesh.volume,0)
        np.testing.assert_allclose(mesh.extents,[2.6,1.4,.9],atol=1e-9)
        self.assertLess(mesh.volume,2.6*1.4*.9)

    def test_bevel_radius_moves_vertices_and_changes_volume(self):
        a=solid('box',{'size':[2,1,3],'bevel_radius':.1})
        b=solid('box',{'size':[2,1,3],'bevel_radius':.2})
        self.assertFalse(np.allclose(a.vertices,b.vertices));self.assertLess(b.volume,a.volume)

    def test_box_without_bevel_keeps_original_topology(self):
        vertices,faces=mesh_for({'kind':'box','params':{'size':[1,2,3]}})
        self.assertEqual(len(vertices),8);self.assertEqual(len(faces),6)

    def test_vertical_bevel_has_flat_endcuts_and_allows_thin_countertop(self):
        params={'size':[2.6,1.4,.08],'bevel_radius':.35,'bevel_mode':'vertical'}
        vertices,faces=mesh_for({'kind':'box','params':params});mesh=solid('box',params)
        self.assertTrue(mesh.is_watertight);self.assertTrue(mesh.is_winding_consistent)
        self.assertEqual(mesh.euler_number,2);self.assertGreater(mesh.volume,0)
        np.testing.assert_allclose(mesh.extents,params['size'],atol=1e-9)
        for cap in faces[-2:]:self.assertEqual(len({round(vertices[i][2],10) for i in cap}),1)
        self.assertEqual({round(v[2],10) for v in vertices},{-.04,.04})

    def test_invalid_bevel_and_unused_segmentation_fail(self):
        for params in ({'size':[1,2,3],'bevel_radius':.5},{'size':[1,2,3],'bevel_radius':-1},
                       {'size':[1,2,3],'bevel_radius':True},{'size':[1,2,3],'segments_per_corner':8},
                       {'size':[1,2,3],'bevel_radius':.1,'bevel_mode':'unused'},
                       {'size':[1,2,3],'bevel_radius':.5,'bevel_mode':'vertical'}):
            with self.assertRaises(ValueError):solid('box',params)

    def test_swept_strip_is_solid_and_control_points_drive_curve(self):
        mesh=solid('swept_strip',STRIP)
        self.assertTrue(mesh.is_watertight);self.assertTrue(mesh.is_winding_consistent)
        self.assertGreater(mesh.volume,0);self.assertEqual(mesh.euler_number,2)
        self.assertAlmostEqual(mesh.extents[1],STRIP['depth'])
        changed=copy.deepcopy(STRIP);changed['control_points'][-2][0]+=.1
        self.assertFalse(np.allclose(mesh.vertices,solid('swept_strip',changed).vertices))

    def test_strip_discontinuous_joint_and_zero_tangent_fail(self):
        zero=copy.deepcopy(STRIP);zero['control_points'][1]=zero['control_points'][0]
        discontinuous=copy.deepcopy(STRIP);discontinuous['control_points'][4]=[1,1]
        for params in (zero,discontinuous):
            with self.assertRaises(ValueError):solid('swept_strip',params)

    def test_strip_width_cannot_fold_around_tight_bend(self):
        params={'control_points':[[0,0],[0,.1],[.1,.1],[.1,0]],'width':1,'depth':.1}
        with self.assertRaises(ValueError):solid('swept_strip',params)

    def test_new_geometry_matches_schema_and_validator(self):
        spec=read_json(ROOT/'examples/legacy-case/candidate_spec.json')
        c=copy.deepcopy(spec['components'][0]);c.update(id='generic_rib',kind='swept_strip',role='decorative_rib',params=copy.deepcopy(STRIP))
        spec['components'].append(c)
        spec['components'][0]['params']['bevel_radius']=.005
        spec['components'][0]['params']['bevel_mode']='vertical'
        schema=read_json(ROOT/'schemas/booth-spec-v2.schema.json')
        jsonschema.Draft202012Validator(schema).validate(spec)
        self.assertTrue(validate(spec)['valid'])

    def test_rig_scales_and_translates_with_model(self):
        camera={'position':[8,-10,6],'target':[0,0,2]}
        a=render_rig([[-2,-1,0],[2,1,4]],1.5,camera)
        b=render_rig([[6,18,30],[14,22,38]],1.5,camera)
        np.testing.assert_allclose(np.asarray(b['inspection_camera']['position']),
                                   2*np.asarray(a['inspection_camera']['position'])+[10,20,30])
        self.assertAlmostEqual(b['lights'][0]['energy']/a['lights'][0]['energy'],4)
        self.assertAlmostEqual(b['lights'][0]['size']/a['lights'][0]['size'],2)

    def test_rig_fits_bounds_in_portrait_and_landscape_without_excess_space(self):
        for bounds in ([[-1,-1,0],[1,1,18]],[[-8,-2,0],[8,2,4]],[[-2,-8,0],[2,8,4]]):
            for aspect in (.5,1,2,4):
                rig=render_rig(bounds,aspect,{'position':[6,-8,4],'target':[0,0,3]})
                camera=np.array(rig['inspection_camera']['position']);centre=np.array(rig['centre'])
                forward=centre-camera;forward/=np.linalg.norm(forward)
                right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right)
                up=np.cross(right,forward)
                points=np.array([[x,y,z] for x in (bounds[0][0],bounds[1][0])
                                 for y in (bounds[0][1],bounds[1][1]) for z in (bounds[0][2],bounds[1][2])])
                offsets=points-camera;depth=offsets@forward
                self.assertTrue(np.all(depth>0))
                projected=np.column_stack((offsets@right/depth/.45,offsets@up/depth/(.45/aspect)))
                self.assertLessEqual(np.max(np.abs(projected)),1/1.12+1e-9)
                self.assertGreater(np.max(np.abs(projected)),.85)

    def test_inspection_azimuth_changes_even_for_frontal_source(self):
        for position in ([0,-10,3],[.01,-10,3],[8,-10,6],[0,10,3]):
            reference=np.array(position[:2],dtype=float);reference/=np.linalg.norm(reference)
            rig=render_rig([[-5,-2,0],[5,2,4]],2,{'position':position,'target':[0,0,2]})
            inspection=np.array(rig['inspection_camera']['position'][:2])-np.array(rig['centre'][:2])
            inspection/=np.linalg.norm(inspection)
            angle=math.degrees(math.acos(np.clip(np.dot(reference,inspection),-1,1)))
            self.assertGreaterEqual(angle,35-1e-8)

    def test_explicit_srgb_preserves_alpha_and_defaults_remain_linear(self):
        rgba=material_rgba({'color':[.5,.04045,1,.3],'color_space':'srgb'})
        self.assertAlmostEqual(rgba[0],.21404114048223255);self.assertAlmostEqual(rgba[1],.04045/12.92)
        self.assertEqual(rgba[3],.3);self.assertEqual(material_rgba({'color':[.5,0,1,1]}),[.5,0,1,1])


@unittest.skipUnless(os.environ.get('BLENDER_EXE'),'Set BLENDER_EXE for the native material/geometry/render regression')
class NativeReusableGeometryTests(unittest.TestCase):
    def test_native_bevel_strip_material_and_client_render(self):
        spec=read_json(ROOT/'examples/legacy-case/candidate_spec.json')
        spec['source']['image']=str(ROOT/'examples/legacy-case/reference.png')
        spec['components'][0]['params']['bevel_radius']=.005
        c=copy.deepcopy(spec['components'][0]);c.update(id='generic_rib',kind='swept_strip',role='decorative_rib',
                critical=False,params=copy.deepcopy(STRIP),location=[0,0,2.1])
        c['material']={'color':[1,.25,.01,1],'color_space':'srgb','roughness':.4}
        spec['components'].append(c)
        counter=copy.deepcopy(c);counter.update(id='generic_counter',kind='box',role='counter',
                params={'size':[1.3,.8,.12],'bevel_radius':.2,'bevel_mode':'vertical'},location=[0,0,1.1])
        spec['components'].append(counter)
        binary=os.environ['BLENDER_EXE'];base=[binary,'--background','--factory-startup','--disable-autoexec','--python-exit-code','1']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            source=path/'synthetic_source.png';Image.new('RGBA',(160,128),'white').save(source)
            spec['source'].update(image=str(source),sha256=file_sha(source),width=160,height=128)
            write_json(path/'spec.json',spec)
            build=subprocess.run(base+['--python',str(ROOT/'scripts/blender_build.py'),'--','--spec',str(path/'spec.json'),
                         '--out',str(path/'run'),'--render','--samples','1','--client-exposure','-.75'],timeout=180,capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            check=subprocess.run(base+['--python',str(ROOT/'scripts/blender_verify.py'),'--','--spec',str(path/'spec.json'),
                         '--blend',str(path/'run/booth.blend'),'--report',str(path/'run/native.json')],timeout=180,capture_output=True,text=True)
            self.assertEqual(check.returncode,0,check.stdout+check.stderr)
            self.assertTrue(read_json(path/'run/native.json')['geometry_verified'])
            self.assertEqual(read_json(path/'run/build_report.json')['client_exposure_ev'],-.75)
            self.assertEqual((path/'run/source_reference.png').read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
            with Image.open(path/'run/reference_render.png') as reference,Image.open(path/'run/client_render.png') as client:
                self.assertEqual(reference.size,client.size)
                self.assertEqual(reference.getchannel('A').getextrema()[0],0)
                self.assertEqual(client.getchannel('A').getextrema(),(255,255))


if __name__=='__main__':unittest.main()
