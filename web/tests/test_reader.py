"""The OpenAI reading step against a local stand-in for the API (tests/mock_openai.py): requests are checked, so no key and no money are needed.

    python -m unittest discover -s web/tests -p "test_*.py"        (from the repository root)
"""
from __future__ import annotations
import base64
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'web' / 'server'))
sys.path.insert(0, str(REPO / 'booth-image-to-model' / 'tests'))
from PIL import Image

import engine                                        # noqa: E402
import grid                                          # noqa: E402
import reader_openai as reader                       # noqa: E402
import test_draft_compile as fixtures                # noqa: E402
from mock_openai import MockOpenAI                   # noqa: E402
from server import Config, create_server             # noqa: E402
from test_server import Api, png_bytes               # noqa: E402

KEY = 'sk-test-secret-0123456789'


def image_file(folder, size=(fixtures.IMG_W, fixtures.IMG_H)):
    path = Path(folder) / 'photo.png'
    path.write_bytes(png_bytes(size))
    return path


def decode(url):
    head, _, data = url.partition(',')
    assert head == 'data:image/jpeg;base64', head
    return Image.open(io.BytesIO(base64.b64decode(data)))


class Pictures(unittest.TestCase):
    def test_small_pictures_are_sent_as_they_are(self):
        with tempfile.TemporaryDirectory() as t:
            r = grid.prepare_images(image_file(t))
        self.assertEqual((r['sent'], r['original'], r['scale']), ((960, 600), (960, 600), 1.0))
        plain, marked = (Image.open(io.BytesIO(r[k])) for k in ('plain', 'grid'))
        self.assertEqual((plain.size, marked.size), ((960, 600), (960, 600)))
        self.assertNotEqual(r['plain'], r['grid'])

    def test_large_pictures_are_scaled_down_and_the_scale_is_returned(self):
        with tempfile.TemporaryDirectory() as t:
            r = grid.prepare_images(image_file(t, (4096, 2560)))
        self.assertEqual((r['sent'], r['original']), ((2048, 1280), (4096, 2560)))
        self.assertAlmostEqual(r['scale'], 2.0)

    def test_the_grid_marks_the_picture(self):
        im = Image.new('RGB', (400, 300), (60, 60, 60))
        marked = grid.draw_grid(im)
        self.assertEqual(marked.size, im.size)
        self.assertEqual(marked.getpixel((125, 125)), (60, 60, 60))         # between lines (every 50 px here) nothing is drawn
        self.assertNotEqual(marked.getpixel((100, 125)), (60, 60, 60))      # on a grid line something is


class Contract(unittest.TestCase):
    def test_the_provider_schema_can_be_used_in_strict_mode(self):
        schema = reader.provider_schema()
        self.assertNotIn('$schema', schema)
        self.assertNotIn('title', schema)
        seen = []

        def walk(node, where):
            if not isinstance(node, dict):
                return
            if node.get('type') == 'object' and 'properties' in node:
                seen.append(where)
                self.assertIs(node.get('additionalProperties'), False, where)
                self.assertEqual(sorted(node['required']), sorted(node['properties']), where)
            for key, value in node.items():
                if key == 'properties':
                    for name, sub in value.items():
                        walk(sub, f'{where}.{name}')
                elif key == 'items':
                    walk(value, f'{where}[]')
        walk(schema, 'scene')
        self.assertGreater(len(seen), 5)
        self.assertEqual(schema['properties']['image']['type'], 'object')

    def test_pixels_are_scaled_back_to_the_original_picture(self):
        scene = fixtures.scene()
        out = reader.scale_scene_pixels(scene, 2.0, 1920, 1200)
        self.assertEqual(out['image'], {'width': 1920, 'height': 1200})
        self.assertEqual(out['corner_points'][0]['uv_px'], [round(v * 2, 2) for v in scene['corner_points'][0]['uv_px']])
        for before, after in zip(scene['components'], out['components']):
            for key in ('roi_px', 'wall_rect_px'):
                if before[key]:
                    self.assertEqual(after[key], [round(v * 2, 2) for v in before[key]])
            if before['base_px']:
                self.assertEqual(after['base_px'], [round(v * 2, 2) for v in before['base_px']])
            if before['points_px']:
                self.assertEqual(after['points_px'], [[round(v * 2, 2) for v in p] for p in before['points_px']])
        self.assertEqual(scene, fixtures.scene())                             # the input is not touched

    def test_a_code_fence_around_the_json_is_tolerated(self):
        self.assertEqual(reader.parse_json('```json\n{"a": 1}\n```'), {'a': 1})
        self.assertEqual(reader.parse_json(' {"a": 1} '), {'a': 1})
        for bad in ('[1]', 'sorry', ''):
            with self.assertRaises(ValueError):
                reader.parse_json(bad)


class ReadScene(unittest.TestCase):
    style = 'responses'

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.image = image_file(self.dir)

    def tearDown(self):
        self._tmp.cleanup()

    def run_with(self, script, **options):
        mock = MockOpenAI(fixtures.scene(), script).start()
        self.addCleanup(mock.stop)
        config = Config(mock.base_url, 'test-model', KEY, style=self.style, retry_wait=0, **options)
        return mock, config

    def read(self, config):
        return reader.read_scene(self.image, config, self.dir / 'reader')

    # -- the request
    def user_parts(self, body):
        if self.style == 'chat':
            return body['messages'][1]['content']
        return body['input'][0]['content']

    def test_a_good_reply_becomes_a_scene_and_the_request_is_right(self):
        mock, config = self.run_with(['good'], effort='low')
        result = self.read(config)
        self.assertEqual(result['attempts'], 1)
        self.assertEqual(result['usage'], {'input_tokens': 4321, 'output_tokens': 987})
        self.assertEqual(engine.validate_scene(result['scene']), [])
        self.assertEqual(result['scene']['image'], {'width': 960, 'height': 600})
        self.assertEqual(result['scene']['components'], fixtures.scene()['components'])
        (request,) = mock.requests
        self.assertEqual(request['headers']['authorization'], f'Bearer {KEY}')
        body = request['body']
        self.assertEqual(body['model'], 'test-model')
        parts = self.user_parts(body)
        self.assertEqual(len(parts), 3)
        self.assertIn('960 x 600', parts[0]['text'])
        images = [p['image_url'] if self.style == 'responses' else p['image_url']['url'] for p in parts[1:]]
        plain, marked = (decode(u) for u in images)
        self.assertEqual((plain.size, marked.size), ((960, 600), (960, 600)))
        self.assert_style_fields(request)

    def assert_style_fields(self, request):
        body = request['body']
        self.assertTrue(request['path'].endswith('/responses'))
        self.assertIs(body['store'], False)
        self.assertTrue(body['instructions'].startswith('You read ONE exhibition-booth render'))
        fmt = body['text']['format']
        self.assertEqual((fmt['type'], fmt['name'], fmt['strict']), ('json_schema', 'booth_scene', True))
        self.assertNotIn('$schema', fmt['schema'])
        self.assertNotIn('title', fmt['schema'])
        self.assertEqual(body['reasoning'], {'effort': 'low'})
        self.assertEqual(body['max_output_tokens'], 32000)
        for part in body['input'][0]['content'][1:]:
            self.assertEqual((part['type'], part['detail']), ('input_image', 'high'))

    # -- repairs and errors
    def test_a_bad_reply_is_sent_back_with_the_errors_and_the_second_try_counts(self):
        mock, config = self.run_with(['bad_scene', 'good'])
        result = self.read(config)
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(result['usage']['input_tokens'], 2 * 4321)
        first, second = (r['body'] for r in mock.requests)
        self.assertEqual(len(self.turns(first)), 1)
        turns = self.turns(second)
        self.assertEqual([t['role'] for t in turns], ['user', 'assistant', 'user'])
        self.assertIn('nowhere', turns[1]['content'])                        # the model's own earlier answer
        self.assertIn('SCOPE', turns[2]['content'])                          # the validator's complaint, with the code
        self.assertIn('back_wall', turns[2]['content'])

    def turns(self, body):
        return body['messages'][1:] if self.style == 'chat' else body['input']

    def test_text_that_is_not_json_is_repaired_the_same_way(self):
        mock, config = self.run_with(['not_json', 'good'])
        self.assertEqual(self.read(config)['attempts'], 2)
        self.assertIn('JSON', self.turns(mock.requests[1]['body'])[2]['content'])

    def test_it_gives_up_after_two_repairs(self):
        mock, config = self.run_with(['bad_scene'])
        with self.assertRaises(reader.ReaderError) as ctx:
            self.read(config)
        self.assertEqual(len(mock.requests), 3)
        self.assertEqual(len(ctx.exception.detail['attempts']), 3)
        self.assertTrue(any(e['code'] == 'SCOPE' for e in ctx.exception.detail['errors']))
        self.assertTrue((self.dir / 'reader' / 'response_3.json').is_file())

    def test_a_refusal_is_reported_and_not_retried(self):
        mock, config = self.run_with(['refusal'])
        with self.assertRaises(reader.ReaderError) as ctx:
            self.read(config)
        self.assertIn('I cannot help with that', str(ctx.exception))
        self.assertEqual(len(mock.requests), 1)

    def test_a_rejected_key_is_reported_and_not_retried(self):
        mock, config = self.run_with(['http401'])
        with self.assertRaises(reader.ReaderError) as ctx:
            self.read(config)
        self.assertIn('key', str(ctx.exception))
        self.assertIn('Incorrect API key', str(ctx.exception))
        self.assertEqual((len(mock.requests), ctx.exception.detail), (1, {'http': 401}))
        self.assertNotIn(KEY, str(ctx.exception))

    def test_a_server_error_is_retried_then_reported(self):
        mock, config = self.run_with(['http500', 'good'])
        self.assertEqual(self.read(config)['attempts'], 1)                   # the retry succeeded
        self.assertEqual(len(mock.requests), 2)
        mock, config = self.run_with(['http500'])
        with self.assertRaises(reader.ReaderError) as ctx:
            self.read(config)
        self.assertEqual((len(mock.requests), ctx.exception.detail), (3, {'http': 500}))

    def test_an_answer_that_was_cut_off_is_reported(self):
        _, config = self.run_with(['incomplete'])
        with self.assertRaises(reader.ReaderError) as ctx:
            self.read(config)
        self.assertIn('max_output_tokens', str(ctx.exception))

    def test_nothing_listening_is_a_clear_error(self):
        config = Config('http://127.0.0.1:9/v1', 'test-model', KEY, style=self.style, retry_wait=0)
        with self.assertRaises(reader.ReaderError) as ctx:
            self.read(config)
        self.assertIn('127.0.0.1:9', str(ctx.exception))

    # -- what stays on disk
    def test_the_log_has_neither_the_key_nor_the_pictures(self):
        _, config = self.run_with(['bad_scene', 'good'])
        self.read(config)
        files = sorted((self.dir / 'reader').iterdir())
        self.assertEqual([f.name for f in files], ['request.json', 'response_1.json', 'response_2.json'])
        for f in files:
            text = f.read_text(encoding='utf-8')
            self.assertNotIn(KEY, text, f.name)
            self.assertNotIn('base64', text, f.name)
        log = json.loads((self.dir / 'reader' / 'request.json').read_text(encoding='utf-8'))
        self.assertEqual((log['model'], log['style'], log['sent'], len(log['attempts'])), ('test-model', self.style, [960, 600], 2))
        self.assertIn('chars>', json.dumps(log['turns']))

    def test_a_large_picture_is_read_small_and_the_result_is_in_original_pixels(self):
        self.image = image_file(self.dir, (4096, 2560))
        mock, config = self.run_with(['good'])
        result = self.read(config)
        sent = decode(self.user_parts(mock.requests[0]['body'])[1]['image_url'] if self.style == 'responses'
                      else self.user_parts(mock.requests[0]['body'])[1]['image_url']['url'])
        self.assertEqual(sent.size, (2048, 1280))
        scene = result['scene']
        self.assertEqual(scene['image'], {'width': 4096, 'height': 2560})
        self.assertEqual(scene['corner_points'][0]['uv_px'], [round(v * 2, 2) for v in fixtures.scene()['corner_points'][0]['uv_px']])


class ReadSceneChat(ReadScene):
    """The Chat Completions wire format, for compatible services."""
    style = 'chat'

    def assert_style_fields(self, request):
        body = request['body']
        self.assertTrue(request['path'].endswith('/chat/completions'))
        self.assertEqual([m['role'] for m in body['messages']], ['system', 'user'])
        self.assertTrue(body['messages'][0]['content'].startswith('You read ONE exhibition-booth render'))
        fmt = body['response_format']
        self.assertEqual(fmt['type'], 'json_schema')
        self.assertEqual((fmt['json_schema']['name'], fmt['json_schema']['strict']), ('booth_scene', True))
        self.assertNotIn('$schema', fmt['json_schema']['schema'])
        self.assertEqual(body['reasoning_effort'], 'low')
        self.assertEqual(body['max_completion_tokens'], 32000)
        for part in body['messages'][1]['content'][1:]:
            self.assertEqual(part['type'], 'image_url')
            self.assertEqual(part['image_url']['detail'], 'high')


class ThroughTheServer(unittest.TestCase):
    """Key and consent in the page -> the server reads -> the scene is stored -> it compiles. Nothing secret reaches a file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.mock = MockOpenAI(fixtures.scene(), ['good']).start()
        self.config = Config(self.mock.base_url, 'test-model', None, retry_wait=0)
        self.server = create_server(Path(self._tmp.name) / 'jobs', self.config, port=0)
        self.api = Api(f'http://127.0.0.1:{self.server.server_address[1]}')
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.mock.stop()
        self._tmp.cleanup()

    def wait(self, job):
        end = time.time() + 120
        while time.time() < end:
            st = self.api.call('GET', f'/api/jobs/{job}')[1]
            if not any(s['state'] in ('running', 'queued') for s in st['steps'].values()):
                return st
            time.sleep(0.1)
        self.fail('timeout')

    def new_job(self):
        status, job = self.api.call('POST', '/api/jobs?name=booth.png', raw=png_bytes(), headers={'Content-Type': 'image/png'})
        self.assertEqual(status, 201)
        return job['id']

    def test_paste_a_key_read_and_compile(self):
        job = self.new_job()
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/read', {'mode': 'openai', 'consent': True})[0], 422)       # no key yet
        self.assertEqual(self.mock.requests, [])
        self.assertEqual(self.api.call('POST', '/api/config', {'openai_api_key': KEY})[0], 200)
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/read', {'mode': 'openai'})[0], 422)                          # no consent
        self.assertEqual(self.mock.requests, [])                                                                              # nothing was sent
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/read', {'mode': 'openai', 'consent': True})[0], 202)
        st = self.wait(job)
        self.assertEqual(st['steps']['scene']['state'], 'done', st['steps']['scene'])
        detail = st['steps']['scene']['detail']
        self.assertEqual((detail['attempts'], detail['usage']['input_tokens']), (1, 4321))
        self.assertEqual(len(self.mock.requests), 1)
        self.assertEqual(self.mock.requests[0]['headers']['authorization'], f'Bearer {KEY}')
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/compile', {})[0], 202)
        st = self.wait(job)
        self.assertEqual(st['steps']['compile']['state'], 'done', st['steps']['compile'])
        self.assertEqual(st['steps']['compile']['detail']['fit']['status'], 'fitted')
        for path in Path(self._tmp.name).rglob('*'):
            if path.is_file() and path.suffix in ('.json', '.txt', '.md', '.log'):
                self.assertNotIn(KEY, path.read_text(encoding='utf-8', errors='ignore'), str(path))
        self.assertNotIn(KEY, json.dumps(self.api.call('GET', '/api/health')[1]))
        self.assertNotIn(KEY, json.dumps(st))

    def test_a_failed_reading_is_an_error_on_the_card_and_keeps_the_job_usable(self):
        self.mock.script[:] = ['http401']
        self.api.call('POST', '/api/config', {'openai_api_key': KEY})
        job = self.new_job()
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/read', {'mode': 'openai', 'consent': True})[0], 202)
        st = self.wait(job)
        self.assertEqual(st['steps']['scene']['state'], 'error')
        self.assertIn('key', st['steps']['scene']['message'])
        self.assertNotIn(KEY, json.dumps(st))
        self.assertEqual(self.api.call('PUT', f'/api/jobs/{job}/scene', fixtures.scene())[0], 200)       # the manual route still works
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/compile', {})[0], 202)
        self.assertEqual(self.wait(job)['steps']['compile']['state'], 'done')

    def test_a_failed_reading_leaves_finished_steps_valid_and_a_good_one_marks_them_stale(self):
        job = self.new_job()
        self.assertEqual(self.api.call('PUT', f'/api/jobs/{job}/scene', fixtures.scene())[0], 200)
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/compile', {})[0], 202)
        self.wait(job)
        jobs = self.server.studio.jobs
        for step in ('preview', 'build', 'glb'):
            jobs.set_step(job, step, 'done', message='fine')
        self.api.call('POST', '/api/config', {'openai_api_key': KEY})
        self.mock.script[:] = ['http401']
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/read', {'mode': 'openai', 'consent': True})[0], 202)
        st = self.wait(job)
        self.assertEqual(st['steps']['scene']['state'], 'error')
        self.assertEqual([st['steps'][s]['state'] for s in ('compile', 'preview', 'build', 'glb')], ['done'] * 4)        # nothing changed, nothing stale
        self.mock.script[:] = ['good']
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/read', {'mode': 'openai', 'consent': True})[0], 202)
        st = self.wait(job)
        self.assertEqual(st['steps']['scene']['state'], 'done')
        self.assertEqual([st['steps'][s]['state'] for s in ('compile', 'preview', 'build', 'glb')], ['stale'] * 4)      # a new scene: the rest is out of date

    def test_the_chat_style_works_through_the_server_too(self):
        self.config.style = 'chat'
        self.api.call('POST', '/api/config', {'openai_api_key': KEY})
        job = self.new_job()
        self.assertEqual(self.api.call('POST', f'/api/jobs/{job}/read', {'mode': 'openai', 'consent': True})[0], 202)
        self.assertEqual(self.wait(job)['steps']['scene']['state'], 'done')
        self.assertTrue(self.mock.requests[0]['path'].endswith('/chat/completions'))


if __name__ == '__main__':
    unittest.main()
