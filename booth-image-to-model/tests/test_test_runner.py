"""Behavioral runner checks; synthetic suites never launch a native render."""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('booth_regression_runner', ROOT / 'tests/run_tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestRunnerTests(unittest.TestCase):
    def setUp(self):
        area = Path(os.environ.get('BOOTH_TEST_RUN_ROOT', ROOT.parent / 'output/_validation/runner_checks'))
        area.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='runner_check_', dir=area)
        self.addCleanup(self.temporary.cleanup)
        self.area = Path(self.temporary.name)
        self.tests = self.area / 'tests'
        self.tests.mkdir()
        self.fixture = self.tests / ('test_fixture_' + uuid.uuid4().hex + '.py')
        self.output = self.area / 'results'

    def write_suite(self, body):
        self.fixture.write_text('import unittest, os, sys, shutil\n' + body, encoding='utf-8')

    def execute(self, arguments=(), native=None):
        native = native or {'available': False, 'path': None, 'reason': 'Synthetic probe: no native executable'}
        console = io.StringIO()
        with patch.object(runner, 'probe_blender', return_value=native), \
                contextlib.redirect_stdout(console), contextlib.redirect_stderr(console), \
                patch.dict(os.environ, {}, clear=True):
            code = runner.main(['--output', str(self.output), *arguments], tests_dir=self.tests)
        summary = json.loads((self.output / 'test_results.json').read_text(encoding='utf-8'))
        transcript = (self.output / 'test_transcript.txt').read_text(encoding='utf-8')
        self.assertEqual(summary['transcript']['sha256'], hashlib.sha256((self.output / 'test_transcript.txt').read_bytes()).hexdigest())
        self.assertEqual(console.getvalue(), transcript)
        return code, summary, transcript

    def test_unrelated_cwd_retains_unicode_stdout_stderr_and_test_details(self):
        self.write_suite("class Fixture(unittest.TestCase):\n"
                         " def test_success(self):\n"
                         "  print('客户日志')\n"
                         "  print('错误流日志', file=sys.stderr)\n"
                         "  self.assertTrue(os.environ['BOOTH_TEST_RUN_ROOT'].endswith('artifacts'))\n")
        elsewhere = self.area / 'unrelated_cwd'
        elsewhere.mkdir()
        previous = Path.cwd()
        try:
            os.chdir(elsewhere)
            code, summary, transcript = self.execute()
        finally:
            os.chdir(previous)
        self.assertEqual(code, 0)
        self.assertEqual(summary['passed'], 1)
        self.assertEqual(summary['status'], 'passed')
        self.assertIn('客户日志', transcript)
        self.assertIn('错误流日志', transcript)
        self.assertIn('test_success', transcript)
        self.assertIn('Ran 1 test', transcript)

    def test_failures_skips_and_expected_failures_are_not_passes(self):
        self.write_suite("class Fixture(unittest.TestCase):\n"
                         " def test_failure(self): self.fail('distinct failure detail')\n"
                         " @unittest.skip('distinct skip detail')\n"
                         " def test_skipped(self): pass\n"
                         " @unittest.expectedFailure\n"
                         " def test_expected_failure(self): self.fail('expected failure detail')\n")
        code, summary, transcript = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(summary['tests_run'], 3)
        self.assertEqual(summary['passed'], 0)
        self.assertEqual(len(summary['failures']), 1)
        self.assertEqual(len(summary['skipped']), 1)
        self.assertEqual(len(summary['expected_failures']), 1)
        self.assertFalse(summary['all_executed_tests_passed'])
        self.assertEqual(summary['status'], 'failed')
        self.assertIn('distinct failure detail', transcript)
        self.assertIn('distinct skip detail', transcript)

    def test_require_native_blocks_before_discovery(self):
        # Invalid Python proves blocked preflight does not discover/run tests.
        self.fixture.write_text('this is not valid Python !!!', encoding='utf-8')
        code, summary, transcript = self.execute(['--require-native'])
        self.assertEqual(code, 2)
        self.assertEqual(summary['tests_run'], 0)
        self.assertEqual(summary['passed'], 0)
        self.assertEqual(summary['status'], 'blocked_native_blender')
        self.assertFalse(summary['all_executed_tests_passed'])
        self.assertIn('BLOCKED', transcript)

    def test_empty_discovery_is_not_a_success_record(self):
        self.fixture.write_text('# No test cases in this synthetic module.\n', encoding='utf-8')
        code, summary, transcript = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(summary['tests_run'], 0)
        self.assertEqual(summary['passed'], 0)
        self.assertEqual(summary['status'], 'failed')
        self.assertFalse(summary['all_executed_tests_passed'])
        self.assertIn('No tests matched discovery pattern', transcript)

    def test_source_change_during_execution_blocks_release_evidence(self):
        self.write_suite("class Fixture(unittest.TestCase):\n"
                         " def test_changes_its_source(self):\n"
                         "  with open(__file__, 'a', encoding='utf-8') as source:\n"
                         "   source.write('# Changed during execution.\\n')\n")
        code, summary, transcript = self.execute()
        self.assertEqual(summary['passed'], 1)
        self.assertEqual(code, 2)
        self.assertEqual(summary['status'], 'source_changed_during_tests')
        self.assertNotEqual(summary['regression_inputs_sha256'], summary['regression_inputs_sha256_after'])
        self.assertFalse(summary['all_executed_tests_passed'])
        self.assertIn('sources changed during the test run', transcript)

    def test_selected_blender_configures_both_native_interfaces(self):
        binary = self.area / ('blender.exe' if os.name == 'nt' else 'blender')
        binary.write_text('Synthetic executable; never invoked.', encoding='utf-8')
        binary.chmod(0o755)
        self.write_suite("class Fixture(unittest.TestCase):\n"
                         " def test_native_interfaces(self):\n"
                         "  self.assertEqual(os.environ['BLENDER_EXE'], " + repr(str(binary)) + ")\n"
                         "  self.assertEqual(os.path.realpath(shutil.which('blender')), " + repr(str(binary.resolve())) + ")\n")
        native = {'available': True, 'path': str(binary), 'probe_stdout': 'Synthetic successful preflight'}
        code, summary, transcript = self.execute(['--blender', str(binary), '--require-native'], native=native)
        self.assertEqual(code, 0)
        self.assertEqual(summary['status'], 'passed')
        self.assertEqual(summary['passed'], 1)
        self.assertEqual(summary['native_skipped'], [])

    def test_default_run_is_under_repository_output_and_old_results_are_preserved(self):
        self.write_suite('class Fixture(unittest.TestCase):\n def test_ok(self): pass\n')
        console = io.StringIO()
        with patch.object(runner, 'probe_blender', return_value={'available': False, 'path': None}), \
                contextlib.redirect_stdout(console), contextlib.redirect_stderr(console), \
                patch.dict(os.environ, {}, clear=True):
            self.assertEqual(runner.main([], tests_dir=self.tests, repository=self.area), 0)
        runs = list((self.area / 'output/_validation').iterdir())
        self.assertEqual(len(runs), 1)
        original = (runs[0] / 'test_results.json').read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            runner.main(['--output', str(runs[0])], tests_dir=self.tests)
        self.assertEqual(error.exception.code, 2)
        self.assertEqual((runs[0] / 'test_results.json').read_bytes(), original)
        self.assertFalse((self.area / 'booth-image-to-model/validation').exists())


if __name__ == '__main__':
    unittest.main()
