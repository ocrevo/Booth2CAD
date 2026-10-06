from __future__ import annotations
import copy
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import trimesh
import jsonschema
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import read_json,write_json,digest,file_sha,code_hash,fingerprints,cache_valid
from geometry import mesh_for,triangulate,transform_point
from validate_spec import validate
from compare import compare_masks,load_mask,landmark_metrics
from boothctl import patch_component,delivery_gate,doctor
from camera_fit import project,fit


def sample():return read_json(ROOT/'examples/legacy-case/candidate_spec.json')
def component(ident):return next(c for c in sample()['components'] if c['id']==ident)
def errors(s):return {e['code'] for e in validate(s)['errors']}


class GeometryTests(unittest.TestCase):
    def mesh(self,c):
        v,f=mesh_for(c);return trimesh.Trimesh(v,triangulate(f),process=False)
    def test_ring_closed_connected_hole(self):
        m=self.mesh(component('top_ring'))
        self.assertTrue(m.is_watertight);self.assertTrue(m.is_winding_consistent)
        self.assertEqual(m.euler_number,0);self.assertEqual(len(m.split(only_watertight=False)),1);self.assertGreater(m.volume,0)
    def test_ring_dimensions_are_driven(self):
        c=component('top_ring');c['params']['outer_size']=[6.2,4.7]
        np.testing.assert_allclose(self.mesh(c).extents,[6.2,4.7,.75],atol=1e-7)
    def test_ring_radius_changes_actual_vertices(self):
        c=component('top_ring');before=mesh_for(c)[0];c['params']['outer_radius']=.8
        self.assertNotEqual(before,mesh_for(c)[0])
    def test_ring_invalid_radius_fails(self):
        c=component('top_ring');c['params']['outer_radius']=99
        with self.assertRaises(ValueError):mesh_for(c)
    def test_ring_closed_opening_fails(self):
        c=component('top_ring');c['params']['inner_size']=[6,5]
        with self.assertRaises(ValueError):mesh_for(c)
    def test_ring_inner_corner_intersection_fails(self):
        c=component('top_ring');c['params']['outer_radius']=2.0;c['params']['inner_size']=[5.44,4.64]
        with self.assertRaises(ValueError):mesh_for(c)
    def test_portal_continuous_watertight(self):
        m=self.mesh(component('main_portal'))
        self.assertTrue(m.is_watertight);self.assertTrue(m.is_winding_consistent);self.assertEqual(m.euler_number,2)
        self.assertGreater(m.volume,0);self.assertEqual(len(m.split(only_watertight=False)),1)
    def test_portal_feet_do_not_close_opening(self):
        c=component('main_portal');m=self.mesh(c);h=c['params']['height'];wi=c['params']['width']-2*c['params']['side_width']
        low=m.triangles[m.triangles[:,:,2].max(axis=1)<-h/2+.05]
        self.assertGreater(len(low),0)
        self.assertTrue(all(np.max(t[:,0])<=-wi/2+1e-6 or np.min(t[:,0])>=wi/2-1e-6 for t in low))
    def test_portal_invalid_side_width(self):
        c=component('main_portal');c['params']['side_width']=2
        with self.assertRaises(ValueError):mesh_for(c)
    def test_cylinder_is_capped_not_tube(self):
        m=self.mesh(component('round_display'))
        self.assertTrue(m.is_watertight);self.assertEqual(m.euler_number,2);self.assertGreater(m.volume,0)
    def test_no_unknown_shape_box_fallback(self):
        c=component('top_ring');c['kind']='spline_canopy'
        with self.assertRaises(ValueError):mesh_for(c)
    def test_euler_transform(self):
        np.testing.assert_allclose(transform_point([1,0,0],[1,2,3],[0,0,90]),[1,3,3],atol=1e-9)


class SpecTests(unittest.TestCase):
    def test_candidate_is_valid_but_not_finished(self):
        r=validate(sample(),ROOT/'examples/legacy-case');self.assertTrue(r['valid']);self.assertTrue(r['warnings'])
    def test_formal_schema_accepts_candidate(self):
        jsonschema.Draft202012Validator(read_json(ROOT/'schemas/booth-spec-v2.schema.json')).validate(sample())
    def test_real_legacy_spec_is_rejected(self):
        self.assertIn('SCHEMA_VERSION',errors(read_json(ROOT/'examples/legacy-case/legacy_spec.json')))
    def test_venue_cannot_be_included(self):
        s=sample();s['scope']['decisions'][0]['owner']='venue'
        self.assertIn('NON_BOOTH_INCLUDED',errors(s));self.assertIn('SCOPE_BLOCKED',errors(s))
    def test_unknown_ownership_cannot_be_included(self):
        s=sample();s['scope']['decisions'][0]['owner']='unknown';self.assertIn('SCOPE_BLOCKED',errors(s))
    def test_excluded_component_cannot_be_built(self):
        s=sample();s['scope']['decisions'][0]['decision']='exclude';self.assertIn('SCOPE_BLOCKED',errors(s))
    def test_planned_component_cannot_silently_disappear(self):
        s=sample();s['components']=s['components'][1:];self.assertIn('OMITTED_INCLUDED_OBJECT',errors(s))
    def test_unused_visual_radius_parameter_rejected(self):
        s=sample();s['components'][1]['params']['corner_radius_visual']=.3;self.assertIn('UNUSED_PARAMETER',errors(s))
    def test_wrong_primitive_for_critical_ring(self):
        s=sample();s['components'][1]['kind']='box';s['components'][1]['params']={'size':[5,4,.7]}
        self.assertIn('WRONG_PRIMITIVE',errors(s))
    def test_duplicate_component_rejected(self):
        s=sample();s['components'].append(copy.deepcopy(s['components'][0]));self.assertIn('DUPLICATE_COMPONENT',errors(s))
    def test_bad_observation_roi_rejected(self):
        s=sample();s['components'][0]['evidence']['roi_xyxy_norm']=[0,0,2,1];self.assertIn('OBSERVATION_ROI',errors(s))
    def test_footprint_metadata_must_match_geometry(self):
        s=sample();s['scale']['footprint_m']=[8,6];self.assertIn('FOOTPRINT_MISMATCH',errors(s))
    def test_unknown_camera_field_is_not_silently_ignored(self):
        s=sample();s['camera']['imaginary_focal_length']=25;self.assertIn('UNKNOWN_CAMERA_FIELD',errors(s))
    def test_nonfinite_rejected(self):
        s=sample();s['components'][0]['location'][0]=float('nan');self.assertIn('TRANSFORM',errors(s))
    def test_source_bytes_must_match(self):
        s=sample();s['source']['sha256']='0'*64;self.assertFalse(validate(s,ROOT/'examples/legacy-case')['valid'])
    def test_patch_cannot_change_ownership(self):
        with self.assertRaises(ValueError):patch_component(sample(),'top_ring','owner','venue')
    def test_patch_cannot_create_unused_field(self):
        with self.assertRaises(ValueError):patch_component(sample(),'top_ring','params.visual_radius',.3)
    def test_dimension_patch_invalidates_geometry_and_qa(self):
        s=sample();s['camera']['fit_status']='reviewed';out,log=patch_component(s,'top_ring','params.outer_radius',.8)
        self.assertEqual(out['camera']['fit_status'],'unfitted');self.assertIn('geometry',log['invalidated_stages']);self.assertIn('qa',log['invalidated_stages'])
    def test_material_patch_keeps_geometry_fingerprint(self):
        s=sample();out,log=patch_component(s,'top_ring','material.roughness',.7)
        self.assertNotIn('geometry',log['invalidated_stages']);self.assertIn('render',log['invalidated_stages'])


class CompareTests(unittest.TestCase):
    def test_identity_mask_is_one(self):
        mask=np.zeros((100,120),bool);mask[10:90,20:100]=True
        r=compare_masks(mask,mask);self.assertEqual(r['iou'],1);self.assertEqual(r['symmetric_boundary_distance_diag'],0)
    def test_filled_fascia_hole_is_penalized(self):
        ref=np.zeros((100,100),bool);ref[10:90,10:90]=True;ref[20:80,20:80]=False
        candidate=np.zeros_like(ref);candidate[10:90,10:90]=True
        self.assertLess(compare_masks(ref,candidate)['iou'],.5)
    def test_empty_candidate_is_zero(self):
        ref=np.ones((40,40),bool);r=compare_masks(ref,np.zeros_like(ref));self.assertEqual(r['iou'],0)
    def test_empty_reference_blocks(self):
        with self.assertRaises(ValueError):compare_masks(np.zeros((20,20),bool),np.zeros((20,20),bool))
    def test_real_legacy_canvas_cannot_be_silently_compared(self):
        a=Image.open(ROOT/'examples/legacy-case/reference.png');b=Image.open(ROOT/'examples/legacy-case/legacy_proxy.png')
        with self.assertRaisesRegex(ValueError,'IMAGE_SHAPE_MISMATCH'):
            compare_masks(np.ones((a.height,a.width),bool),np.ones((b.height,b.width),bool))
    def test_rgb_photo_is_not_auto_thresholded(self):
        with self.assertRaises(ValueError):load_mask(ROOT/'examples/legacy-case/reference.png')
    def test_unknown_region_can_be_excluded(self):
        ref=np.zeros((40,40),bool);ref[5:20,5:20]=True;can=ref.copy();can[25:35,25:35]=True
        valid=np.ones_like(ref);valid[20:,:]=False
        self.assertEqual(compare_masks(ref,can,valid)['iou'],1)
    def test_missing_anchor_blocks(self):
        with self.assertRaisesRegex(ValueError,'MISSING_LANDMARKS'):
            landmark_metrics([{'id':'corner','visibility':'visible','uv':[.5,.5],'fit':False}],[],100,100)
    def test_camera_fit_recovers_synthetic_projection(self):
        s=sample();cid='booth_carpet';c=s['components'][0]
        local=np.asarray([[-2,-2,0],[2,-2,0],[2,2,0],[-2,2,0],[-2,-2,3],[2,-2,3],[2,2,3],[-2,2,3],[0,1,1.5],[1,0,2]])
        world=local+np.asarray(c['location']);true=copy.deepcopy(s['camera'])
        uv,depth=project(world,true,495,394)
        self.assertTrue((depth>0).all());self.assertTrue(((uv>=0)&(uv<=1)).all())
        s['landmarks']=[{'id':f'a{i}','component_id':cid,'local_xyz':xyz.tolist(),'uv':uv[i].tolist(),'visibility':'visible','fit':i<8} for i,xyz in enumerate(local)]
        s['camera']['position']=[6.8,-9.1,2.55];s['camera']['lens_mm']=38
        result=fit(s);self.assertLess(result['metrics']['median_diag'],1e-5);self.assertEqual(result['metrics']['held_out_count'],2)
    def test_camera_fit_refuses_unannotated_photo(self):
        with self.assertRaisesRegex(ValueError,'anchors'):fit(sample())


class EvidenceTests(unittest.TestCase):
    def test_missing_native_evidence_never_passes(self):
        with tempfile.TemporaryDirectory() as d:
            r=delivery_gate(sample(),{},d);self.assertFalse(r['deliver_as_finished']);self.assertIn('native_blend_not_reopened',r['failures'])
    def test_cache_rejects_incomplete_run(self):
        with tempfile.TemporaryDirectory() as d:self.assertFalse(cache_valid({'status':'building','key':'x'},'x',d))
    def test_cache_checks_actual_output_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.txt';p.write_text('one');m={'status':'complete','key':'x','outputs':[{'path':'a.txt','sha256':file_sha(p)}]}
            self.assertTrue(cache_valid(m,'x',d));p.write_text('two');self.assertFalse(cache_valid(m,'x',d))
    def test_cache_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(cache_valid({'status':'complete','key':'x','outputs':[{'path':'../outside','sha256':'x'}]},'x',d))
    def test_doctor_missing_blender_is_explicit(self):
        r=doctor('/definitely/not/a/blender');self.assertEqual(r['status'],'blocked_native_blender');self.assertFalse(r['hosted_skill_updated'])


@unittest.skipUnless(shutil.which('blender'),'Native Blender unavailable; API execution is not verified by Python tests')
class NativeBlenderTests(unittest.TestCase):
    def test_build_reopen_native_file(self):
        with tempfile.TemporaryDirectory() as d:
            binary=shutil.which('blender');base=[binary,'--background','--factory-startup','--disable-autoexec','--python-exit-code','1']
            spec=str(ROOT/'examples/legacy-case/candidate_spec.json')
            subprocess.run(base+['--python',str(ROOT/'scripts/blender_build.py'),'--','--spec',spec,'--out',d],check=True,timeout=180,capture_output=True)
            subprocess.run(base+['--python',str(ROOT/'scripts/blender_verify.py'),'--','--spec',spec,'--blend',str(Path(d)/'booth.blend'),'--report',str(Path(d)/'native_verification.json')],check=True,timeout=180,capture_output=True)
            self.assertTrue(read_json(Path(d)/'native_verification.json')['geometry_verified'])
