"""Run regressions with explicit native configuration and retained UTF-8 logs.

Outputs belong to a fresh run directory, never the packaged validation records.
Native tests retain their existing BLENDER_EXE/PATH interfaces.
"""
from __future__ import annotations
import argparse
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from common import code_hash, digest, file_sha


def regression_inputs_hash(skill_root=ROOT, tests_dir=None):
    """Bind regression evidence to builder, schema and actual test sources."""
    skill_root = Path(skill_root)
    inputs = {}
    for label, root, pattern in (
            ('scripts', skill_root / 'scripts', '*.py'),
            ('schemas', skill_root / 'schemas', '*.json'),
            ('tests', Path(tests_dir or skill_root / 'tests'), '*.py')):
        for path in sorted(root.rglob(pattern)):
            inputs[label + '/' + path.relative_to(root).as_posix()] = file_sha(path)
    return digest(inputs)


class Tee:
    """Retain exactly the text emitted to the runner's stdout/stderr."""
    encoding = 'utf-8'

    def __init__(self, console, transcript):
        self.console, self.transcript = console, transcript

    def write(self, text):
        self.console.write(text)
        self.transcript.write(text)
        self.flush()
        return len(text)

    def flush(self):
        self.console.flush()
        self.transcript.flush()

    def isatty(self):
        return False


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes = []

    def addSuccess(self, test):
        self.successes.append(str(test))
        super().addSuccess(test)


def probe_blender(requested=None):
    candidate = requested or os.environ.get('BLENDER_EXE') or shutil.which('blender')
    result = {'requested': candidate, 'available': False, 'path': None}
    if not candidate:
        result['reason'] = 'No --blender, BLENDER_EXE or blender on PATH'
        return result
    resolved = shutil.which(candidate)
    if not resolved:
        result['reason'] = 'Blender executable does not exist or is not executable: ' + candidate
        return result
    result['path'] = str(Path(resolved).resolve())
    try:
        checked = subprocess.run([result['path'], '--version'], capture_output=True,
                                 text=True, encoding='utf-8', errors='replace', timeout=20)
        result['probe_stdout'] = checked.stdout
        result['probe_stderr'] = checked.stderr
        result['returncode'] = checked.returncode
        result['available'] = checked.returncode == 0
        if not result['available']:
            result['reason'] = 'Blender --version returned ' + str(checked.returncode)
    except (OSError, subprocess.SubprocessError) as ex:
        result['reason'] = str(ex)
    return result


@contextlib.contextmanager
def test_environment(native, output):
    changes = {'BOOTH_TEST_RUN_ROOT': str(output / 'artifacts'),
               'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    if native['available']:
        changes['BLENDER_EXE'] = native['path']
        changes['PATH'] = str(Path(native['path']).parent) + os.pathsep + os.environ.get('PATH', '')
    previous = {key: os.environ.get(key) for key in changes}
    previous_bytecode = sys.dont_write_bytecode
    os.environ.update(changes)
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = previous_bytecode
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main(argv=None, *, tests_dir=None, repository=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', help='Actual Blender executable; configures BLENDER_EXE and PATH')
    parser.add_argument('--output', type=Path, help='Fresh result directory (summary + full console transcript)')
    parser.add_argument('--require-native', action='store_true', help='Block if native Blender cannot run')
    parser.add_argument('--pattern', default='test_*.py', help='unittest discovery pattern for targeted checks')
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    repository = Path(repository) if repository is not None else REPOSITORY
    started = datetime.datetime.now(datetime.timezone.utc)
    output = (args.output or repository / 'output' / '_validation' /
              ('run_' + started.strftime('%Y%m%dT%H%M%S_%fZ') + '_' + str(os.getpid()))).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error('Use a fresh result directory; existing outputs are not overwritten: ' + str(output))
    output.mkdir(parents=True, exist_ok=True)
    transcript_path = output / 'test_transcript.txt'
    summary = {'tests_run': 0, 'passed': 0, 'failures': [], 'errors': [], 'skipped': [],
               'expected_failures': [], 'unexpected_successes': [],
               'all_executed_tests_passed': False, 'python': platform.python_version(),
               'started_at_utc': started.isoformat(), 'require_native': args.require_native,
               'discovery_pattern': args.pattern, 'output_directory': str(output),
               'artifact_root': str(output / 'artifacts'),
               'scope': 'Regression evidence only; does not certify source-image fidelity.',
               'transcript_scope': 'Complete runner stdout/stderr; separately captured native logs remain test artifacts.',
               'builder_sha256': code_hash(),
               'regression_inputs_sha256': regression_inputs_hash(tests_dir=tests_dir)}
    code = 1
    with transcript_path.open('w', encoding='utf-8') as transcript:
        with contextlib.redirect_stdout(Tee(sys.stdout, transcript)), contextlib.redirect_stderr(Tee(sys.stderr, transcript)):
            print('Test results directory: ' + str(output))
            native = probe_blender(args.blender)
            summary['native_blender'] = native
            print('Native preflight: ' + json.dumps(native, ensure_ascii=False))
            configured_invalid = bool(args.blender or os.environ.get('BLENDER_EXE')) and not native['available']
            if (args.require_native and not native['available']) or configured_invalid:
                summary['status'] = 'blocked_native_blender'
                print('BLOCKED: ' + native.get('reason', 'Native Blender is unavailable'))
                code = 2
            else:
                try:
                    with test_environment(native, output):
                        suite = unittest.TestLoader().discover(str(tests_dir or ROOT / 'tests'), pattern=args.pattern)
                        if suite.countTestCases() == 0:
                            raise ValueError('No tests matched discovery pattern: ' + args.pattern)
                        result = unittest.TextTestRunner(verbosity=2, stream=sys.stderr,
                                                         resultclass=RecordingResult).run(suite)
                    native_skips = [(str(t), reason) for t, reason in result.skipped if 'Native' in str(t)]
                    summary.update(tests_run=result.testsRun, passed=len(result.successes),
                                   failures=[(str(t), detail) for t, detail in result.failures],
                                   errors=[(str(t), detail) for t, detail in result.errors],
                                   skipped=[(str(t), reason) for t, reason in result.skipped],
                                   expected_failures=[(str(t), detail) for t, detail in result.expectedFailures],
                                   unexpected_successes=[str(t) for t in result.unexpectedSuccesses],
                                   native_skipped=native_skips,
                                   all_executed_tests_passed=result.wasSuccessful())
                    if args.require_native and native_skips:
                        summary['status'], code = 'blocked_native_blender', 2
                    elif not result.wasSuccessful():
                        summary['status'], code = 'failed', 1
                    else:
                        summary['status'] = 'passed_with_skips' if result.skipped else 'passed'
                        code = 0
                except Exception:
                    import traceback
                    detail = traceback.format_exc()
                    print(detail, file=sys.stderr, end='')
                    summary['errors'].append(('test_runner', detail))
                    summary['status'] = 'failed'
                    code = 1
            summary['executed_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            summary['builder_sha256_after'] = code_hash()
            summary['regression_inputs_sha256_after'] = regression_inputs_hash(tests_dir=tests_dir)
            if (summary['builder_sha256_after'] != summary['builder_sha256'] or
                    summary['regression_inputs_sha256_after'] != summary['regression_inputs_sha256']):
                summary['status'], code = 'source_changed_during_tests', 2
                summary['all_executed_tests_passed'] = False
                print('BLOCKED: builder, schema or test sources changed during the test run')
            summary['exit_code'] = code
            print('Final status: ' + summary['status'])
    summary['transcript'] = {'path': transcript_path.name,
                             'sha256': hashlib.sha256(transcript_path.read_bytes()).hexdigest()}
    (output / 'test_results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
