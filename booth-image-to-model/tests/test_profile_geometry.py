"""Generic boundary extrusions and curved panels, including real empty notches."""
from __future__ import annotations
import copy
import math
import os
import subprocess
import sys
import unittest
from pathlib import Path
import jsonschema
import numpy as np
import trimesh
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import read_json,write_json,file_sha
from geometry import mesh_for,triangulate
from validate_spec import validate
from material_patterns import grid_parameters


def notched_profile(steps=24):
    """A synthetic plate with separated bottom-open arch and top-open U cut."""
    points=[[-3,-2],[-1.8,-2],[-1.8,-.8]]
    points.extend([-1.3+.5*math.cos(math.pi-math.pi*i/steps),
                   -.8+.5*math.sin(math.pi-math.pi*i/steps)] for i in range(1,steps+1))
    points.extend([[-.8,-2],[3,-2],[3,2],[.8,2],[.8,.7]])
    points.extend([.8*math.cos(-math.pi*i/steps),
                   .7+.8*math.sin(-math.pi*i/steps)] for i in range(1,steps+1))
    points.extend([[-.8,2],[-3,2]])
    return points


PROFILE={'profile':notched_profile(),'depth':.23}
ARC={'radius':4.2,'thickness':.18,'height':.9,'start_deg':-67,'end_deg':23,'segments':48}
GRID={'type':'grid','spacing':[.14,.11],'line_width':.015,'line_color':[.2,.3,.4]}


def mesh(kind,params):
    vertices,faces=mesh_for({'kind':kind,'params':params})
    return trimesh.Trimesh(vertices,triangulate(faces),process=False)


def cap_covers(vertices,faces,x,z):
    """Test triangulated front caps directly: no optional ray backend needed."""
    depth=min(v[1] for v in vertices)
    for face in faces:
        if len(face)!=3 or any(abs(vertices[i][1]-depth)>1e-10 for i in face):continue
        p=[(vertices[i][0],vertices[i][2]) for i in face]
        cross=[(p[(i+1)%3][0]-p[i][0])*(z-p[i][1])-
               (p[(i+1)%3][1]-p[i][1])*(x-p[i][0]) for i in range(3)]
        if min(cross)>=-1e-10 or max(cross)<=1e-10:return True
    return False


class ProfileGeometryTests(unittest.TestCase):
    def test_two_edge_notches_remain_empty_and_solid_is_closed(self):
        v,f=mesh_for({'kind':'profile_extrusion','params':PROFILE})
        m=mesh('profile_extrusion',PROFILE)
        self.assertTrue(m.is_watertight);self.assertTrue(m.is_winding_consistent)
        self.assertEqual(m.euler_number,2);self.assertGreater(m.volume,0)
        np.testing.assert_allclose(m.extents,[6,.23,4],atol=1e-10)
        self.assertFalse(cap_covers(v,f,-1.3,-1))
        self.assertFalse(cap_covers(v,f,0,1.7))
        self.assertTrue(cap_covers(v,f,2,0))
        area=24-(1*1.2+math.pi*.5**2/2)-(1.6*1.3+math.pi*.8**2/2)
        self.assertAlmostEqual(m.volume,area*.23,delta=.002)

    def test_reverse_winding_and_collinear_samples_give_same_solid(self):
        a=mesh('profile_extrusion',PROFILE)
        reverse=copy.deepcopy(PROFILE);reverse['profile'].reverse()
        b=mesh('profile_extrusion',reverse)
        self.assertTrue(b.is_volume);self.assertAlmostEqual(a.volume,b.volume)
        rectangle={'profile':[[2,1],[3,1],[4,1],[4,3],[2,3]],'depth':.3}
        v,f=mesh_for({'kind':'profile_extrusion','params':rectangle})
        self.assertEqual(len(v),8)
        self.assertAlmostEqual(mesh('profile_extrusion',rectangle).volume,1.2)
        np.testing.assert_allclose(np.asarray(v).min(axis=0),[2,-.15,1])

    def test_polygon_self_crossing_touching_and_degeneracy_fail_closed(self):
        bad=[[[0,0],[2,2],[0,2],[2,0]],  # crossed boundary
             [[0,0],[2,0],[2,2],[1,0],[0,2]],  # nonadjacent contact
             [[0,0],[2,0],[2,2],[0,2],[0,0]],  # repeated closing point
             [[0,0],[1,0],[2,0]],
             [[0,0],[True,0],[0,2]],
             [[0,0],[2,float('inf')],[0,2]],
             [[0,0],[2,0],[2,2],[2,2],[0,2]],
             [[0,0],[1,0],[.5,0],[0,1]]]
        for points in bad:
            with self.subTest(points=points),self.assertRaises(ValueError):
                mesh('profile_extrusion',{'profile':points,'depth':.2})
        for depth in (0,-.1,True,float('nan')):
            with self.subTest(depth=depth),self.assertRaises(ValueError):
                mesh('profile_extrusion',{'profile':PROFILE['profile'],'depth':depth})

    def test_arc_panel_is_closed_has_positive_volume_and_exact_radial_bounds(self):
        m=mesh('arc_panel',ARC)
        self.assertTrue(m.is_watertight);self.assertTrue(m.is_winding_consistent)
        self.assertEqual(m.euler_number,2);self.assertGreater(m.volume,0)
        radii=np.linalg.norm(m.vertices[:,:2],axis=1)
        self.assertAlmostEqual(radii.min(),4.11);self.assertAlmostEqual(radii.max(),4.29)
        self.assertAlmostEqual(m.extents[2],.9)
        exact_volume=math.radians(90)*4.2*.18*.9
        self.assertAlmostEqual(m.volume,exact_volume,delta=.001)
        reverse=dict(ARC,start_deg=ARC['end_deg'],end_deg=ARC['start_deg'])
        np.testing.assert_allclose(m.vertices,mesh('arc_panel',reverse).vertices)

    def test_arc_adjacent_segments_share_exact_end_boundary(self):
        a=mesh('arc_panel',dict(ARC,start_deg=-70,end_deg=-11))
        b=mesh('arc_panel',dict(ARC,start_deg=-11,end_deg=41))
        angles=np.degrees(np.arctan2(a.vertices[:,1],a.vertices[:,0]))
        seam_a=a.vertices[np.isclose(angles,-11)]
        angles=np.degrees(np.arctan2(b.vertices[:,1],b.vertices[:,0]))
        seam_b=b.vertices[np.isclose(angles,-11)]
        np.testing.assert_allclose(seam_a,seam_b,atol=1e-12)

    def test_arc_invalid_span_radius_thickness_and_segments_fail(self):
        bad=[dict(ARC,end_deg=ARC['start_deg']),dict(ARC,start_deg=0,end_deg=360),
             dict(ARC,start_deg=0,end_deg=400),dict(ARC,radius=0),
             dict(ARC,thickness=2*ARC['radius']),dict(ARC,height=-1),
             dict(ARC,start_deg=float('nan')),dict(ARC,end_deg=True),
             dict(ARC,segments=3),dict(ARC,segments=513),dict(ARC,segments=4.5)]
        for params in bad:
            with self.subTest(params=params),self.assertRaises(ValueError):mesh('arc_panel',params)

    def test_schema_validator_and_unused_parameter_agree(self):
        spec=read_json(ROOT/'examples/regression/candidate_spec.json')
        for kind,params in (('profile_extrusion',PROFILE),('arc_panel',ARC)):
            c=copy.deepcopy(spec['components'][0]);c.update(id='generic_'+kind,kind=kind,
                    role='panel',params=copy.deepcopy(params))
            spec['components'].append(c)
        spec['components'][-1]['material']['pattern']=copy.deepcopy(GRID)
        schema=read_json(ROOT/'schemas/booth-spec-v2.schema.json')
        jsonschema.Draft202012Validator(schema).validate(spec)
        self.assertTrue(validate(spec)['valid'])
        spec['components'][-1]['params']['unused_radius']=3
        self.assertFalse(validate(spec)['valid'])
        self.assertTrue(list(jsonschema.Draft202012Validator(schema).iter_errors(spec)))

    def test_grid_uses_metres_and_arc_unwrap_respects_shared_origin_and_color_space(self):
        material={'color':[1,.8,.3,1],'color_space':'srgb','pattern':copy.deepcopy(GRID)}
        c={'kind':'arc_panel','params':ARC}
        p=grid_parameters(material,c)
        self.assertEqual(p['coordinates'],'arc_length_z');self.assertEqual(p['radius'],4.2)
        self.assertEqual(p['spacing'],GRID['spacing'])
        self.assertAlmostEqual(p['line_color'][0],.033104766570885055)
        self.assertEqual(grid_parameters(material,{'kind':'box'})['coordinates'],'xz')
        crossing={'kind':'arc_panel','params':dict(ARC,start_deg=169,end_deg=194)}
        with self.assertRaises(ValueError):grid_parameters(material,crossing)
        material['pattern']['arc_origin_deg']=180
        self.assertEqual(grid_parameters(material,crossing)['arc_origin_deg'],180)

    def test_grid_invalid_pattern_and_unused_mapping_parameters_fail(self):
        bad=[dict(GRID,line_width=.2),dict(GRID,spacing=[.1,0]),dict(GRID,line_color=[1,1,2]),
             dict(GRID,offset=[float('nan'),0]),dict(GRID,coordinates='uv'),dict(GRID,type='bitmap'),
             dict(GRID,unused_frequency=3),dict(GRID,coordinates='xz',arc_origin_deg=20)]
        for pattern in bad:
            with self.subTest(pattern=pattern),self.assertRaises(ValueError):
                grid_parameters({'pattern':pattern},{'kind':'arc_panel','params':ARC})
        with self.assertRaises(ValueError):
            grid_parameters({'pattern':dict(GRID,coordinates='arc_length_z')},{'kind':'box'})


@unittest.skipUnless(os.environ.get('BLENDER_EXE'),'Set BLENDER_EXE for native reopened geometry verification')
class NativeProfileGeometryTests(unittest.TestCase):
    def test_native_notched_plate_curved_panel_and_flat_caps(self):
        # Persist every local native-validation artifact in the ignored test tree.
        # A unique run path avoids overwriting a reviewed .blend.
        import time
        repository=ROOT.parent
        run_root=Path(os.environ.get('BOOTH_TEST_RUN_ROOT',repository/'output/_validation'))
        path=run_root/'component_validation'/('native_'+str(time.time_ns()))
        path.mkdir(parents=True)
        spec=read_json(ROOT/'examples/regression/candidate_spec.json')
        source=path/'synthetic_source.png';Image.new('RGB',(120,80),'white').save(source)
        spec['source'].update(image=str(source),sha256=file_sha(source),width=120,height=80)
        for kind,params in (('profile_extrusion',PROFILE),('arc_panel',ARC)):
            c=copy.deepcopy(spec['components'][0]);c.update(id='generic_'+kind,kind=kind,
                    role='panel',critical=False,params=copy.deepcopy(params),location=[0,0,2])
            spec['components'].append(c)
        spec['components'][-1]['material']['pattern']=copy.deepcopy(GRID)
        write_json(path/'spec.json',spec)
        base=[os.environ['BLENDER_EXE'],'--background','--factory-startup','--disable-autoexec','--python-exit-code','1']
        built=subprocess.run(base+['--python',str(ROOT/'scripts/blender_build.py'),'--','--spec',str(path/'spec.json'),
                   '--out',str(path/'run'),'--render','--samples','1'],timeout=240,capture_output=True,text=True)
        (path/'build.log').write_text(built.stdout+built.stderr,encoding='utf-8')
        self.assertEqual(built.returncode,0,built.stdout+built.stderr)
        reopened=subprocess.run(base+['--python',str(ROOT/'scripts/blender_verify.py'),'--','--spec',str(path/'spec.json'),
                   '--blend',str(path/'run/booth.blend'),'--report',str(path/'native.json')],timeout=120,capture_output=True,text=True)
        (path/'reopen.log').write_text(reopened.stdout+reopened.stderr,encoding='utf-8')
        self.assertEqual(reopened.returncode,0,reopened.stdout+reopened.stderr)
        self.assertTrue(read_json(path/'native.json')['geometry_verified'])
        tamper=path/'tamper_pattern.py'
        tamper.write_text("import bpy\n"+
            "bpy.ops.wm.open_mainfile(filepath="+repr(str(path/'run/booth.blend'))+",use_scripts=False)\n"+
            "m=bpy.data.objects['generic_arc_panel'].data.materials[0]\n"+
            "m.node_tree.nodes['grid_u_frequency'].inputs[1].default_value*=2\n"+
            "bpy.ops.wm.save_as_mainfile(filepath="+repr(str(path/'tampered.blend'))+")\n",encoding='utf-8')
        result=subprocess.run(base+['--python',str(tamper)],timeout=120,capture_output=True,text=True)
        (path/'tamper.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run(base+['--python',str(ROOT/'scripts/blender_verify.py'),'--','--spec',str(path/'spec.json'),
                   '--blend',str(path/'tampered.blend'),'--report',str(path/'tampered_report.json')],timeout=120,capture_output=True,text=True)
        (path/'tamper_verify.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('material_pattern_mismatch:generic_arc_panel',read_json(path/'tampered_report.json')['errors'])


if __name__=='__main__':unittest.main()
