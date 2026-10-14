"""Independent synthetic contracts; no customer images or sample answers."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import jsonschema
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import file_sha,read_json,write_json
from validate_spec import validate


def synthetic_spec():
    return {
        'schema_version':'2.0','project':{'id':'synthetic_contract'},
        'source':{'image':'source.png','sha256':'0'*64,'width':64,'height':48},
        'scale':{'units':'m','basis':'user_dimensions','footprint_m':[2,2],'notes':'Synthetic 2 m square.'},
        'scope':{'decisions':[{'id':'floor_scope','owner':'booth','decision':'include','evidence':'Synthetic isolated floor.'}]},
        'components':[{'id':'floor','scope_id':'floor_scope','owner':'booth','kind':'box','role':'floor','critical':False,
            'evidence':{'status':'inferred','note':'Synthetic geometry.'},'location':[0,0,0],'rotation_deg':[0,0,0],
            'params':{'size':[2,2,.1]},'material':{'color':[.5,.5,.5,1]}}],
        'camera':{'projection':'perspective','position':[3,-4,3],'target':[0,0,0],
            'lens_mm':50,'sensor_width_mm':36,'principal_point':[.5,.5],'pixel_aspect':[1,1],'fit_status':'unfitted'},
        'requirements':[{'id':'floor_required','component_id':'floor','kind':'box','must_be_critical':False}],
        'landmarks':[{'id':'floor_corner','component_id':'floor','local_xyz':[1,1,.05],
            'uv':[.5,.5],'visibility':'visible','fit':True,'weight':1}],
        'uncertainties':[{'id':'assumption','critical':False,'status':'accepted_by_user','description':'Synthetic fixture.'}],
        'quality':{'silhouette_iou_min':.8,'part_iou_min':.7,'landmark_median_max':.03,
            'landmark_p90_max':.06,'boundary_distance_max':.03,'threshold_basis':'Synthetic thresholds.'}}


def text_spec():
    spec=synthetic_spec();c=copy.deepcopy(spec['components'][0])
    c.update(id='caption',kind='text',role='neutral_caption',params={'body':'Example','size':.2,'extrude':0})
    spec['components'].append(c)
    return spec


def run_directory():
    value=os.environ.get('BOOTH_TEST_RUN_ROOT')
    if value:
        root=Path(value);root.mkdir(parents=True,exist_ok=True);return root
    return None


def write_source_fixture(path,spec):
    Image.new('RGB',(64,48),(128,128,128)).save(path/'source.png')
    spec['source']['sha256']=file_sha(path/'source.png')
    write_json(path/'spec.json',spec)


class SyntheticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema=jsonschema.Draft202012Validator(read_json(ROOT/'schemas/booth-spec-v2.schema.json'))
        jsonschema.Draft202012Validator.check_schema(cls.schema.schema)

    def assert_both_reject(self,spec):
        self.assertFalse(validate(spec)['valid'])
        self.assertTrue(list(self.schema.iter_errors(spec)))

    def test_minimal_perspective_and_orthographic_are_supported(self):
        spec=synthetic_spec()
        self.assertTrue(validate(spec)['valid']);self.schema.validate(spec)
        spec['camera']={k:v for k,v in spec['camera'].items() if k not in ('lens_mm','sensor_width_mm')}
        spec['camera'].update(projection='orthographic',ortho_scale=4)
        self.assertTrue(validate(spec)['valid']);self.schema.validate(spec)

    def test_missing_and_unknown_nested_fields_rejected_by_both(self):
        paths=[('project',),('source',),('scale',),('scope',),('scope','decisions',0),
               ('components',0),('components',0,'evidence'),('components',0,'params'),
               ('components',0,'material'),('requirements',0),('landmarks',0),('uncertainties',0),('camera',),('quality',)]
        for path in paths:
            original=synthetic_spec();node=original
            for part in path:node=node[part]
            with self.subTest(path=path,mutation='unknown'):
                node['unsupported_field']=1;self.assert_both_reject(original)
            original=synthetic_spec();node=original
            for part in path:node=node[part]
            # Every fixture has at least one required field at this location.
            key=next(iter(node))
            with self.subTest(path=path,mutation='missing',field=key):
                del node[key];self.assert_both_reject(original)

    def test_wrong_nested_types_rejected_by_both(self):
        cases=[(('project',),None),(('project','id'),42),(('source','image'),42),(('source','width'),True),
               (('scale','notes'),[]),(('scope','decisions'),{}),(('scope','decisions',0,'evidence'),False),
               (('components',0,'role'),[]),(('components',0,'critical'),1),
               (('components',0,'evidence','note'),{}),(('components',0,'params','size'),{}),
               (('components',0,'material','color'),{}),(('requirements',0,'must_be_critical'),'false'),
               (('landmarks',0,'id'),None),(('uncertainties',0,'critical'),1),
               (('camera','pixel_aspect'),[True,True]),(('quality','threshold_basis'),[])]
        for path,value in cases:
            spec=synthetic_spec();node=spec
            for part in path[:-1]:node=node[part]
            node[path[-1]]=value
            with self.subTest(path=path,value=value):self.assert_both_reject(spec)

    def test_weight_is_finite_positive_numeric(self):
        for value in (-1,0,True,'1'):
            spec=synthetic_spec();spec['landmarks'][0]['weight']=value
            with self.subTest(value=value):self.assert_both_reject(spec)
        for value in (float('nan'),float('inf')):
            spec=synthetic_spec();spec['landmarks'][0]['weight']=value
            with self.subTest(value=value):self.assertFalse(validate(spec)['valid'])
        spec=synthetic_spec();spec['landmarks'][0]['weight']=.25
        self.assertTrue(validate(spec)['valid']);self.schema.validate(spec)

    def test_text_extrude_is_finite_nonnegative_numeric(self):
        for value in (-1,True,'0'):
            spec=text_spec();spec['components'][1]['params']['extrude']=value
            with self.subTest(value=value):self.assert_both_reject(spec)
        for value in (float('nan'),float('inf')):
            spec=text_spec();spec['components'][1]['params']['extrude']=value
            with self.subTest(value=value):self.assertFalse(validate(spec)['valid'])
        for value in (0,.01):
            spec=text_spec();spec['components'][1]['params']['extrude']=value
            self.assertTrue(validate(spec)['valid']);self.schema.validate(spec)

    def test_camera_projection_requires_its_parameters(self):
        for key in ('lens_mm','sensor_width_mm'):
            spec=synthetic_spec();del spec['camera'][key]
            with self.subTest(projection='perspective',field=key):self.assert_both_reject(spec)
        spec=synthetic_spec();spec['camera']['projection']='orthographic'
        self.assert_both_reject(spec)
        spec['camera']['ortho_scale']=4
        self.assertTrue(validate(spec)['valid']);self.schema.validate(spec)

    def test_observed_evidence_requires_roi_in_both_contracts(self):
        spec=synthetic_spec();spec['components'][0]['evidence']['status']='observed'
        self.assert_both_reject(spec)
        spec['components'][0]['evidence']['roi_xyxy_norm']=[0,0,1,1]
        self.assertTrue(validate(spec)['valid']);self.schema.validate(spec)

    def test_optional_decoded_size_rejects_wrong_source_frame(self):
        spec=synthetic_spec()
        self.assertTrue(validate(spec,source_size=[64,48])['valid'])
        result=validate(spec,source_size=[128,96])
        self.assertFalse(result['valid']);self.assertIn('SOURCE_DIMENSIONS',[e['code'] for e in result['errors']])

    def test_check_source_cli_decodes_real_synthetic_image_size(self):
        with tempfile.TemporaryDirectory(dir=run_directory()) as directory:
            path=Path(directory);spec=synthetic_spec();write_source_fixture(path,spec)
            command=[sys.executable,'-B',str(ROOT/'scripts/validate_spec.py'),'--spec',str(path/'spec.json'),
                     '--check-source','--report',str(path/'report.json')]
            good=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertEqual(good.returncode,0,good.stdout+good.stderr)
            spec['source'].update(width=128,height=96);write_json(path/'spec.json',spec)
            bad=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertEqual(bad.returncode,2,bad.stdout+bad.stderr)
            self.assertIn('SOURCE_DIMENSIONS',[e['code'] for e in read_json(path/'report.json')['errors']])

    def test_validator_import_keeps_blender_path_free_of_third_party_dependencies(self):
        code=("import sys\nsys.path.insert(0,"+repr(str(ROOT/'scripts'))+")\n"
              "import validate_spec\nassert not any(name in sys.modules for name in ('PIL','numpy','scipy','jsonschema'))\n")
        result=subprocess.run([sys.executable,'-B','-S','-c',code],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


@unittest.skipUnless(os.environ.get('BLENDER_EXE'),'Set BLENDER_EXE for native source-frame contract tests')
class NativeSourceContractTests(unittest.TestCase):
    def test_builder_checks_real_source_size_before_writing_scene(self):
        path=Path(tempfile.mkdtemp(prefix='contract_native_',dir=run_directory()))
        spec=synthetic_spec();write_source_fixture(path,spec)
        base=[os.environ['BLENDER_EXE'],'--background','--factory-startup','--disable-autoexec','--python-exit-code','1',
              '--python',str(ROOT/'scripts/blender_build.py'),'--','--spec',str(path/'spec.json')]
        good=subprocess.run(base+['--out',str(path/'valid')],capture_output=True,text=True,timeout=120)
        (path/'valid_build.log').write_text(good.stdout+good.stderr,encoding='utf-8')
        self.assertEqual(good.returncode,0,good.stdout+good.stderr)
        self.assertTrue((path/'valid/booth.blend').is_file())
        spec['source'].update(width=128,height=96);write_json(path/'spec.json',spec)
        bad=subprocess.run(base+['--out',str(path/'mismatch')],capture_output=True,text=True,timeout=120)
        (path/'mismatch_build.log').write_text(bad.stdout+bad.stderr,encoding='utf-8')
        self.assertNotEqual(bad.returncode,0)
        self.assertIn('SOURCE_DIMENSIONS',bad.stdout+bad.stderr)
        self.assertFalse((path/'mismatch').exists())


if __name__=='__main__':unittest.main()
