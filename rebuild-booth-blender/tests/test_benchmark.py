import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from benchmark import prepare,report

class BenchmarkTests(unittest.TestCase):
    def test_single_image_does_not_read_other_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(30,20),'white').save(root/'one.png')
            (root/'unrelated.png').write_bytes(b'not a readable image')
            manifest=prepare(None,root/'run',root/'one.png')
            self.assertEqual(len(manifest['cases']),1)
            self.assertEqual(manifest['cases'][0]['title'],'one')

    def test_previous_outputs_are_not_new_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(30,20),'white').save(root/'source.png')
            old=root/'runs/old';old.mkdir(parents=True);Image.new('RGB',(30,20),'red').save(old/'render.png')
            manifest=prepare(root,root/'runs/new')
            self.assertEqual(len(manifest['cases']),1)
            self.assertEqual(manifest['cases'][0]['source_size'],[30,20])
            with self.assertRaises(FileExistsError):prepare(root,root/'runs/new')

    def test_report_binds_bytes_and_records_different_ai_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.png';Image.new('RGBA',(30,20),'white').save(source)
            out=root/'run';manifest=prepare(root,out);case=manifest['cases'][0]
            Image.new('RGBA',(40,40),'blue').save(out/'ai.png')
            case.update(baseline='../source.png',blender='../source.png',ai='ai.png',title='<unsafe>')
            path=out/'cases.json';path.write_text(json.dumps(manifest),encoding='utf-8')
            report(path,out/'comparison.html')
            evidence=json.loads((out/'comparison.evidence.json').read_text(encoding='utf-8'))
            self.assertFalse(evidence['cases'][0]['assets'][3]['same_dimensions_as_source'])
            self.assertIn('&lt;unsafe&gt;',(out/'comparison.html').read_text(encoding='utf-8'))
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Original source changed'):report(path,out/'comparison.html')

    def test_missing_render_route_does_not_create_success_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(30,20)).save(root/'source.png')
            prepare(root,root/'run')
            with self.assertRaisesRegex(ValueError,'Missing render route'):
                report(root/'run/cases.json',root/'run/comparison.html')
            self.assertFalse((root/'run/comparison.html').exists())
