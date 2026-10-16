"""Finding Blender the same way everywhere (doctor, build, verify, preview, the test runner, the web studio)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import common  # noqa: E402
import boothctl  # noqa: E402


def fake_executable(folder, name):
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('')
    return path


class BlenderLookup(unittest.TestCase):
    def test_an_explicit_path_wins_and_a_wrong_one_is_not_replaced_silently(self):
        with tempfile.TemporaryDirectory() as t:
            exe = fake_executable(t, 'blender-custom')
            self.assertEqual(common.find_blender(str(exe)), os.path.abspath(exe))
            with mock.patch.dict(os.environ, {'BLENDER_EXE': str(exe)}):
                self.assertEqual(common.find_blender(), os.path.abspath(exe))
                self.assertIsNone(common.find_blender(str(Path(t) / 'missing')))          # an argument beats the environment
            with mock.patch.dict(os.environ, {'BLENDER_EXE': str(Path(t) / 'missing')}):
                self.assertIsNone(common.find_blender())                                  # a wrong BLENDER_EXE is reported, not bypassed

    def test_a_macos_app_folder_is_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            inner = fake_executable(t, 'Blender.app/Contents/MacOS/Blender')
            self.assertEqual(common.find_blender(str(Path(t) / 'Blender.app')), os.path.abspath(inner))
            self.assertEqual(common.find_blender(str(Path(t) / 'Blender.app') + os.sep), os.path.abspath(inner))   # 'Blender.app/'
            self.assertEqual(common.find_blender(str(Path(t) / 'Blender.app') + '/'), os.path.abspath(inner))

    def test_the_test_runner_probes_the_executable_inside_an_app_folder_and_records_no_absolute_path(self):
        import importlib.util
        loader = importlib.util.spec_from_file_location('booth_lookup_runner', ROOT / 'tests/run_tests.py')
        runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(runner)
        finished = mock.Mock(stdout='Blender 9.9 (synthetic)', stderr='', returncode=0)
        with tempfile.TemporaryDirectory() as t, mock.patch.object(runner.subprocess, 'run', return_value=finished) as run:
            inner = fake_executable(t, 'Blender.app/Contents/MacOS/Blender')
            native = runner.probe_blender(str(Path(t) / 'Blender.app') + os.sep)
            self.assertTrue(native['available'])
            self.assertEqual(native['path'], os.path.abspath(inner))
            self.assertEqual(run.call_args.args[0], [os.path.abspath(inner), '--version'])
            recorded = runner.redacted_native(native)
            self.assertEqual((recorded['requested'], recorded['path']), ('<blender>/Blender.app', '<blender>/Blender'))
            missing = runner.redacted_native(runner.probe_blender(str(Path(t) / 'missing' / 'blender')))
            self.assertFalse(missing['available'])
            self.assertNotIn(t, json.dumps(missing))
            self.assertIn('<blender>/blender', missing['reason'])

    def test_the_usual_places_are_searched_newest_first(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(sys, 'platform', 'win32'), \
                mock.patch.dict(os.environ, {'ProgramFiles': t}, clear=False):
            os.environ.pop('ProgramFiles(x86)', None)
            for version in ('4.2', '5.2', '4.10'):
                fake_executable(t, f'Blender Foundation/Blender {version}/blender.exe')
            found = common.blender_candidates()
            self.assertEqual([Path(p).parent.name for p in found], ['Blender 5.2', 'Blender 4.10', 'Blender 4.2'])
        with mock.patch.object(sys, 'platform', 'darwin'):
            self.assertIn('/Applications/Blender.app/Contents/MacOS/Blender', common.blender_candidates())
        with mock.patch.object(sys, 'platform', 'linux'):
            self.assertIn('/snap/bin/blender', common.blender_candidates())

    def test_nothing_found_is_none_and_doctor_says_what_to_do(self):
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(common, 'blender_candidates', return_value=[]), \
                mock.patch('shutil.which', return_value=None):
            os.environ.pop('BLENDER_EXE', None)
            self.assertIsNone(common.find_blender())
            report = boothctl.doctor()
        self.assertEqual(report['status'], 'blocked_native_blender')
        self.assertTrue(any('BLENDER_EXE' in step for step in report['next_steps']))
        with self.assertRaises(ValueError):
            with mock.patch.object(boothctl, 'locate_blender', return_value=None):
                boothctl.find_blender()


class BuildAndVerifyCommands(unittest.TestCase):
    """The documented commands wrap the raw Blender calls, so they read the same in bash and PowerShell."""

    def run_main(self, argv):
        with mock.patch.object(boothctl, 'run_blender_script', return_value=(0, '')) as runner, mock.patch.object(sys, 'argv', ['boothctl.py'] + argv), \
                mock.patch('builtins.print'):
            code = boothctl.main()
        return code, runner.call_args

    def test_build_passes_the_options_after_the_separator_to_the_build_script(self):
        code, call = self.run_main(['build', '--spec', 's.json', '--out', 'o', '--blender', 'b', '--', '--render', '--samples', '32', '--hd-scale', '3'])
        self.assertEqual(code, 0)
        script, args, blender, timeout = call.args
        self.assertEqual((script, blender), ('blender_build.py', 'b'))
        self.assertEqual(args, ['--spec', 's.json', '--out', 'o', '--render', '--samples', '32', '--hd-scale', '3'])

    def test_verify_calls_the_verify_script(self):
        code, call = self.run_main(['verify', '--spec', 's.json', '--blend', 'b.blend', '--report', 'r.json'])
        self.assertEqual(code, 0)
        self.assertEqual(call.args[:2], ('blender_verify.py', ['--spec', 's.json', '--blend', 'b.blend', '--report', 'r.json']))

    def test_a_failed_build_is_a_nonzero_exit(self):
        with mock.patch.object(boothctl, 'run_blender_script', return_value=(1, 'boom')), \
                mock.patch.object(sys, 'argv', ['boothctl.py', 'build', '--spec', 's', '--out', 'o']), mock.patch('builtins.print'):
            self.assertEqual(boothctl.main(), 2)


if __name__ == '__main__':
    unittest.main()
