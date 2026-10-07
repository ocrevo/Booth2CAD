"""Independent synthetic regressions for the 2026-10-07 functionality audit.

Fixtures are created from scratch; customer examples and frozen audit evidence
are not mutated. Native artifacts/logs remain under output/_validation.
"""
from __future__ import annotations
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import read_json,write_json,file_sha,digest,code_hash
from compare import landmark_metrics
from boothctl import delivery_gate
from camera_fit import project,fit
from assess import assess

ARTIFACT_ROOT=Path(os.environ.get('BOOTH_TEST_RUN_ROOT',ROOT.parent/'output/_validation'))/'audit_functionality'
BLENDER=os.environ.get('BLENDER_EXE') or shutil.which('blender')


def new_run(prefix):
    path=ARTIFACT_ROOT/(prefix+'_'+str(time.time_ns()))
    path.mkdir(parents=True)
    return path


def synthetic_spec(path):
    Image.new('RGB',(160,120),'white').save(path/'source.png')
    components=[]
    for ident,role,params,location in (
            ('floor','floor',{'size':[4,3,.1]},[0,0,-.05]),
            ('display_box','display',{'size':[4,3,3]},[0,0,1.5])):
        components.append({'id':ident,'scope_id':ident,'owner':'booth','kind':'box','role':role,
            'critical':False,'evidence':{'status':'observed','roi_xyxy_norm':[0,0,1,1],
            'note':'Known synthetic audit geometry'},'location':location,'rotation_deg':[0,0,0],
            'params':params,'material':{'color':[.7,.7,.7,1]}})
    return {'schema_version':'2.0','project':{'id':'synthetic_functionality_regression'},
        'source':{'image':'source.png','sha256':file_sha(path/'source.png'),'width':160,'height':120},
        'scale':{'units':'m','basis':'user_dimensions','footprint_m':[4,3],
                 'notes':'Known dimensions in a synthetic fixture'},
        'scope':{'decisions':[{'id':c['id'],'owner':'booth','decision':'include',
                              'evidence':'Known synthetic geometry'} for c in components]},
        'components':components,
        'camera':{'projection':'perspective','position':[10,-12,7.5],'target':[0,0,1.5],
            'lens_mm':40,'sensor_width_mm':36,'principal_point':[.5,.5],
            'pixel_aspect':[1,1],'fit_status':'reviewed'},
        'requirements':[],'landmarks':[],'uncertainties':[],
        'quality':{'silhouette_iou_min':.9,'part_iou_min':.85,'landmark_median_max':.025,
            'landmark_p90_max':.05,'boundary_distance_max':.012,
            'threshold_basis':'Known synthetic fixture; no customer fidelity claim'}}


def anchors(spec,camera=None,fit_count=8):
    local=np.asarray([[-2,-1.5,-1.5],[2,-1.5,-1.5],[2,1.5,-1.5],[-2,1.5,-1.5],
        [-2,-1.5,1.5],[2,-1.5,1.5],[2,1.5,1.5],[-2,1.5,1.5],
        [0,-1.5,0],[0,0,1.5]],dtype=float)
    fit_points=np.asarray([local[i%8] for i in range(fit_count)])
    points=np.vstack((fit_points,local[-2:]))
    uv,depth=project(points+[0,0,1.5],camera or spec['camera'],160,120)
    if not (depth>0).all() or not ((uv>=0)&(uv<=1)).all():
        raise ValueError('Synthetic anchor camera does not frame the geometry')
    return [{'id':f'anchor_{i}','component_id':'display_box','local_xyz':point.tolist(),
        'uv':uv[i].tolist(),'visibility':'visible','fit':i<fit_count}
        for i,point in enumerate(points)]


def gate_evidence(spec,path):
    # The gate consumes records supplied by assess. These are isolated unit
    # fixtures, not native/reviewer attestations or production delivery records.
    artifacts=[]
    for role in ('blend','reference_render','inspection_render','source_reference'):
        output=path/(role+'.fixture');output.write_bytes(b'synthetic unit fixture')
        artifacts.append({'role':role,'path':output.name,'sha256':file_sha(output)})
    return {'spec_sha256':digest(spec),'builder_sha256':code_hash(),
        'native_blender_reopened':True,'geometry_verified':True,'artifacts':artifacts,
        'metrics':{'silhouette_iou':1.,'boundary_distance_diag':0.,'landmark_median_diag':0.,
            'landmark_p90_diag':0.,'held_out_anchor_count':2,
            'held_out_landmark_median_diag':0.,'held_out_landmark_p90_diag':0.},
        'part_metrics':{},'visual_review':{'topology':'pass','ownership':'pass','layout':'pass',
            'alternate_view':'pass','appearance':'pass','reviewer':'Synthetic unit fixture',
            'notes':'Exercises numeric decision logic only'},'reference_annotation_review':'pass'}


class HeldOutAcceptanceTests(unittest.TestCase):
    def test_fit_anchor_count_cannot_hide_failed_independent_anchors(self):
        reference=[{'id':f'fit_{i}','visibility':'visible','fit':True,'uv':[.5,.5]} for i in range(20)]
        reference += [{'id':f'held_{i}','visibility':'visible','fit':False,'uv':[.1,.1]} for i in range(2)]
        projected=[{'id':r['id'],'uv':[.5,.5],'depth':1} for r in reference]
        metrics=landmark_metrics(reference,projected,160,120)
        self.assertEqual(metrics['median_diag'],0)
        self.assertEqual(metrics['p90_diag'],0)
        self.assertAlmostEqual(metrics['held_out_median_diag'],.4)
        self.assertAlmostEqual(metrics['held_out_p90_diag'],.4)
        path=new_run('held_out_gate');spec=synthetic_spec(path);evidence=gate_evidence(spec,path)
        evidence['metrics'].update(held_out_landmark_median_diag=metrics['held_out_median_diag'],
                                  held_out_landmark_p90_diag=metrics['held_out_p90_diag'])
        result=delivery_gate(spec,evidence,path)
        write_json(path/'evidence.json',evidence);write_json(path/'gate.json',result)
        self.assertFalse(result['deliver_as_finished'])
        self.assertIn('metric_failed:held_out_landmark_median_diag',result['failures'])
        self.assertIn('metric_failed:held_out_landmark_p90_diag',result['failures'])

    def test_verified_numeric_fixture_with_passing_check_anchors_still_passes(self):
        path=new_run('passing_gate');spec=synthetic_spec(path);evidence=gate_evidence(spec,path)
        result=delivery_gate(spec,evidence,path)
        write_json(path/'gate.json',result)
        self.assertTrue(result['deliver_as_finished'],result['failures'])

    def test_old_evidence_without_held_out_errors_requires_reassessment(self):
        path=new_run('old_gate');spec=synthetic_spec(path);evidence=gate_evidence(spec,path)
        del evidence['metrics']['held_out_landmark_median_diag']
        del evidence['metrics']['held_out_landmark_p90_diag']
        result=delivery_gate(spec,evidence,path)
        self.assertFalse(result['deliver_as_finished'])
        self.assertIn('missing_or_invalid_metric:held_out_landmark_median_diag',result['failures'])
        self.assertIn('missing_or_invalid_metric:held_out_landmark_p90_diag',result['failures'])

    def test_missing_or_nonfinite_check_error_does_not_pass(self):
        path=new_run('invalid_gate');spec=synthetic_spec(path);evidence=gate_evidence(spec,path)
        for value in (None,float('nan'),float('inf'),True,-.1):
            with self.subTest(value=value):
                evidence['metrics']['held_out_landmark_median_diag']=value
                self.assertFalse(delivery_gate(spec,evidence,path)['deliver_as_finished'])

    def test_no_check_anchors_has_explicit_empty_subset(self):
        result=landmark_metrics([{'id':'fit','visibility':'visible','fit':True,'uv':[.5,.5]}],
            [{'id':'fit','depth':1,'uv':[.5,.5]}],160,120)
        self.assertEqual(result['held_out_count'],0)
        self.assertIsNone(result['held_out_median_diag'])
        self.assertIsNone(result['held_out_p90_diag'])


class CameraSeedBoundsTests(unittest.TestCase):
    def test_legal_wide_long_and_rotated_cameras_can_refine_the_seed(self):
        for lens,roll in ((8,0),(180,70),(40,-135)):
            with self.subTest(lens=lens,roll=roll):
                path=new_run('camera_seed');spec=synthetic_spec(path)
                scale=max(1,lens/40)
                true=copy.deepcopy(spec['camera'])
                true.update(position=[10*scale,-12*scale,1.5+6*scale],lens_mm=lens,roll_deg=roll)
                spec['landmarks']=anchors(spec,true)
                seed=copy.deepcopy(true)
                seed.update(position=(np.asarray(true['position'])+[.3,-.2,.15]).tolist(),
                    lens_mm=lens*1.05,roll_deg=roll+4,fit_status='unfitted')
                spec['camera']=seed
                result=fit(spec,max_nfev=200)
                write_json(path/'spec.json',spec);write_json(path/'fit.json',result)
                self.assertTrue(result['optimizer_success'])
                self.assertLess(result['metrics']['held_out_p90_diag'],1e-5)
                self.assertLess(result['metrics']['p90_diag'],1e-5)
                self.assertGreater(result['camera']['lens_mm'],0)

    def test_steep_valid_camera_is_not_rejected_by_an_arbitrary_pitch_limit(self):
        path=new_run('steep_camera');spec=synthetic_spec(path)
        true=copy.deepcopy(spec['camera']);true.update(position=[.2,-.2,8],lens_mm=30,roll_deg=45)
        spec['landmarks']=anchors(spec,true);spec['camera']=copy.deepcopy(true)
        spec['camera']['position']=[.23,-.24,8.1]
        result=fit(spec,max_nfev=200)
        write_json(path/'spec.json',spec);write_json(path/'fit.json',result)
        self.assertTrue(result['optimizer_success'])
        self.assertLess(result['metrics']['held_out_p90_diag'],1e-5)


@unittest.skipUnless(BLENDER,'Set BLENDER_EXE for independent native functionality regressions')
class NativeFunctionalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=new_run('native');cls.spec=synthetic_spec(cls.path)
        for ident,params in (('label',{'body':'DISPLAY','size':.2,'extrude':.01}),
                             ('default_label',{'body':'DISPLAY','size':.15})):
            c=copy.deepcopy(cls.spec['components'][1]);c.update(id=ident,scope_id=ident,kind='text',
                role='neutral_display',params=params,location=[0,-1.6,2],rotation_deg=[90,0,0])
            cls.spec['components'].append(c)
            cls.spec['scope']['decisions'].append({'id':ident,'owner':'booth','decision':'include',
                                                 'evidence':'Synthetic neutral text'})
        cls.spec['landmarks']=anchors(cls.spec,fit_count=20)
        for lm in cls.spec['landmarks'][-2:]:
            lm['uv']=[v-.35 if v>.5 else v+.35 for v in lm['uv']]
        write_json(cls.path/'spec.json',cls.spec)
        cls.base=[BLENDER,'--background','--factory-startup','--disable-autoexec','--python-exit-code','1']
        cls.commands=[]
        cls.run_native('build',['--python',str(ROOT/'scripts/blender_build.py'),'--','--spec',
            str(cls.path/'spec.json'),'--out',str(cls.path/'run'),'--render','--samples','1'])
        cls.run_native('baseline_verify',['--python',str(ROOT/'scripts/blender_verify.py'),'--','--spec',
            str(cls.path/'spec.json'),'--blend',str(cls.path/'run/booth.blend'),
            '--report',str(cls.path/'run/native_verification.json')])
        if not read_json(cls.path/'run/native_verification.json')['geometry_verified']:
            raise AssertionError('Synthetic baseline did not verify')

    @classmethod
    def run_native(cls,name,args,expected_success=True):
        p=subprocess.run(cls.base+args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        (cls.path/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
        cls.commands.append({'name':name,'command':cls.base+args,'returncode':p.returncode})
        write_json(cls.path/'commands.json',cls.commands)
        if expected_success and p.returncode!=0:
            raise AssertionError(p.stdout+p.stderr)
        return p

    def test_text_size_extrusion_and_each_alignment_are_verified(self):
        cases=(('size',2.,'text_parameter_mismatch:label:size'),
               ('extrude',.5,'text_parameter_mismatch:label:extrude'),
               ('align_x','LEFT','text_alignment_mismatch:label:align_x'),
               ('align_y','TOP','text_alignment_mismatch:label:align_y'))
        script="import bpy\nfrom pathlib import Path\nP=Path(__file__).resolve().parent\n"
        for name,value,_ in cases:
            script += "bpy.ops.wm.open_mainfile(filepath=str(P/'run/booth.blend'),use_scripts=False)\n"
            script += "bpy.data.objects['label'].data."+name+'='+repr(value)+'\n'
            script += "bpy.ops.wm.save_as_mainfile(filepath=str(P/"+repr(name+'.blend')+"),compress=True)\n"
        (self.path/'tamper.py').write_text(script,encoding='utf-8')
        self.run_native('tamper',['--python',str(self.path/'tamper.py')])
        for name,_,error in cases:
            with self.subTest(name=name):
                p=self.run_native('verify_'+name,['--python',str(ROOT/'scripts/blender_verify.py'),'--',
                    '--spec',str(self.path/'spec.json'),'--blend',str(self.path/(name+'.blend')),
                    '--report',str(self.path/(name+'_verification.json'))],expected_success=False)
                self.assertNotEqual(p.returncode,0)
                self.assertIn(error,read_json(self.path/(name+'_verification.json'))['errors'])

    def test_assess_propagates_and_rejects_failed_check_anchors(self):
        run=self.path/'run'
        Image.open(run/'reference_render.png').getchannel('A').save(self.path/'visible.png')
        annotations={'source_sha256':self.spec['source']['sha256'],'silhouette':{'mask':'visible.png'},
            'parts':{},'review_status':'pass','reviewer':'Synthetic QA regression fixture'}
        review={'spec_sha256':digest(self.spec),'builder_sha256':code_hash(),
            'reference_render_sha256':file_sha(run/'reference_render.png'),
            'inspection_render_sha256':file_sha(run/'inspection_render.png'),
            'topology':'pass','ownership':'pass','layout':'pass','alternate_view':'pass','appearance':'pass',
            'reviewer':'Synthetic QA regression fixture','notes':'Known synthetic images; not customer review'}
        write_json(self.path/'annotations.json',annotations);write_json(self.path/'review.json',review)
        result=assess(self.path/'spec.json',run,self.path/'annotations.json',self.path/'review.json')
        evidence=read_json(run/'quality_evidence.json')
        self.assertEqual(evidence['collection_errors'],[])
        self.assertLess(evidence['metrics']['landmark_p90_diag'],1e-5)
        self.assertGreater(evidence['metrics']['held_out_landmark_median_diag'],.3)
        self.assertGreater(evidence['metrics']['held_out_landmark_p90_diag'],.3)
        self.assertFalse(result['deliver_as_finished'])
        self.assertIn('metric_failed:held_out_landmark_median_diag',result['failures'])
        self.assertIn('metric_failed:held_out_landmark_p90_diag',result['failures'])


if __name__=='__main__':unittest.main(verbosity=2)
