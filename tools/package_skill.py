"""Package real full-suite evidence after validation; never certify client images.

Run from any cwd. The --skill default is located relative to this tool, while
explicit --skill/--test-run paths follow normal command-line cwd semantics.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

sys.dont_write_bytecode = True


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_object(path):
    data = Path(path).read_bytes()
    value = json.loads(data.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object: ' + str(path))
    return value, data


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def metadata_version(skill):
    text = (skill / 'SKILL.md').read_text(encoding='utf-8-sig')
    frontmatter = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
    if not frontmatter:
        raise ValueError('SKILL.md has no YAML frontmatter')
    matched = re.search(r'^  version:\s*([^\r\n]+)$', frontmatter.group(1), re.M)
    if not matched:
        raise ValueError('SKILL.md metadata.version is missing')
    return matched.group(1).split(' #', 1)[0].strip().strip('\"\'')


def current_builder_hash(skill):
    path = skill / 'scripts/common.py'
    loader = importlib.util.spec_from_file_location('_package_skill_common', path)
    if loader is None or loader.loader is None:
        raise ValueError('Cannot load current scripts/common.py')
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module.code_hash()


def current_regression_inputs_hash(skill):
    path = skill / 'tests/run_tests.py'
    loader = importlib.util.spec_from_file_location('_package_skill_runner', path)
    if loader is None or loader.loader is None:
        raise ValueError('Cannot load current tests/run_tests.py')
    module = importlib.util.module_from_spec(loader)
    previous_path = sys.path[:]
    previous_common = sys.modules.pop('common', None)
    try:
        loader.loader.exec_module(module)
        return module.regression_inputs_hash(skill_root=skill, tests_dir=skill / 'tests')
    finally:
        sys.path[:] = previous_path
        sys.modules.pop('common', None)
        if previous_common is not None:
            sys.modules['common'] = previous_common


def validate_run(skill, test_run):
    summary, summary_bytes = read_object(test_run / 'test_results.json')
    if summary.get('discovery_pattern') != 'test_*.py':
        raise ValueError('Only a complete test_*.py discovery run can be packaged')
    if summary.get('require_native') is not True:
        raise ValueError('The test run must have --require-native')
    native = summary.get('native_blender')
    if not isinstance(native, dict) or native.get('available') is not True or native.get('returncode') != 0:
        raise ValueError('Native Blender preflight did not pass')
    version_line = str(native.get('probe_stdout', '')).splitlines()
    if not version_line or not version_line[0].startswith('Blender '):
        raise ValueError('The native preflight does not identify a Blender version')
    tests, passed = summary.get('tests_run'), summary.get('passed')
    if type(tests) is not int or tests <= 0 or type(passed) is not int or passed != tests:
        raise ValueError('tests_run must be positive and equal to passed')
    for name in ('failures', 'errors', 'skipped', 'expected_failures', 'unexpected_successes', 'native_skipped'):
        if not isinstance(summary.get(name), list) or summary[name]:
            raise ValueError('Missing or nonempty result field: ' + name)
    if summary.get('status') != 'passed' or summary.get('exit_code') != 0 or summary.get('all_executed_tests_passed') is not True:
        raise ValueError('The test run did not finish with a successful complete result')
    builder = current_builder_hash(skill)
    if summary.get('builder_sha256') != builder or summary.get('builder_sha256_after') != builder:
        raise ValueError('Builder before/after hashes do not match current common.code_hash()')
    inputs_hash = current_regression_inputs_hash(skill)
    if summary.get('regression_inputs_sha256') != inputs_hash or summary.get('regression_inputs_sha256_after') != inputs_hash:
        raise ValueError('Regression inputs before/after hashes do not match current scripts/schema/tests')
    transcript_record = summary.get('transcript')
    if not isinstance(transcript_record, dict) or transcript_record.get('path') != 'test_transcript.txt':
        raise ValueError('The current runner transcript.path must be test_transcript.txt')
    transcript_path = (test_run / 'test_transcript.txt').resolve()
    if not transcript_path.is_relative_to(test_run) or not transcript_path.is_file():
        raise ValueError('Transcript must be an existing file within the test run')
    transcript_bytes = transcript_path.read_bytes()
    if sha(transcript_bytes) != transcript_record.get('sha256'):
        raise ValueError('Transcript SHA-256 mismatch')
    transcript = transcript_bytes.decode('utf-8')
    counts = re.findall(r'^Ran (\d+) tests? in .+$', transcript, re.M)
    if not counts or int(counts[-1]) != tests:
        raise ValueError('Transcript does not contain the matching complete unittest run count')
    if not re.search(r'^OK\s*$', transcript, re.M) or not re.search(r'^Final status: passed\s*$', transcript, re.M):
        raise ValueError('Transcript has no successful completed unittest/runner conclusion')
    if not isinstance(summary.get('executed_at_utc'), str):
        raise ValueError('The actual run completion timestamp is missing')
    return summary, summary_bytes, transcript_bytes, builder, inputs_hash, version_line[0]


def ignored(path):
    return path == Path('FILE_MANIFEST.json') or '__pycache__' in path.parts or path.suffix.lower() == '.pyc'


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def package(skill, test_run, explicit_version=None):
    skill, test_run = Path(skill).resolve(), Path(test_run).resolve()
    version = metadata_version(skill)
    if explicit_version is not None and explicit_version != version:
        raise ValueError('--version must match current SKILL.md metadata.version')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]{0,99}', version):
        raise ValueError('Version must be a safe version identifier')
    summary, summary_bytes, transcript_bytes, builder, inputs_hash, blender_version = validate_run(skill, test_run)
    release, release_bytes = read_object(skill / 'release_status.json')
    iteration, iteration_bytes = read_object(skill / 'validation/iteration_report.json')
    existing_manifest = skill / 'FILE_MANIFEST.json'
    manifest = read_object(existing_manifest)[0] if existing_manifest.exists() else {}
    planned = {}
    archived = []
    old = {'release_status.json': release_bytes,
           'iteration_report.json': iteration_bytes}
    for name in ('test_results.json', 'test_transcript.txt', 'test_output.txt'):
        path = skill / 'validation' / name
        if path.exists():
            old[name] = path.read_bytes()
    if (old.get('test_results.json') != summary_bytes or old.get('test_transcript.txt') != transcript_bytes
            or old.get('test_output.txt') != transcript_bytes
            or release.get('version') != version or release.get('builder_sha256') != builder):
        old_version = str(release.get('version', 'unknown'))
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]{0,99}', old_version):
            raise ValueError('Previous release version is unsafe for archival')
        archive_key = sha(json_bytes({name: sha(data) for name, data in sorted(old.items())}))[:16]
        archive_root = Path('validation/history') / old_version / ('evidence_' + archive_key)
        for name, data in old.items():
            relative = archive_root / name
            path = skill / relative
            if path.exists():
                if path.read_bytes() != data:
                    raise ValueError('Existing history evidence will not be overwritten: ' + str(relative))
            else:
                planned[relative] = data
                archived.append(relative.as_posix())
    provenance = {'source_test_run': str(test_run), 'summary': 'validation/test_results.json',
                  'summary_sha256': sha(summary_bytes), 'transcript': 'validation/test_transcript.txt',
                  'transcript_sha256': sha(transcript_bytes)}
    release.update(version=version, builder_sha256=builder, regression_inputs_sha256=inputs_hash, python_tests=summary,
                   test_run_evidence=provenance)
    release['native_blender_integration'] = 'passed_' + blender_version.lower().replace(' ', '_')
    iteration.update(version=version, builder_sha256=builder, regression_inputs_sha256=inputs_hash, tests=summary,
                     date=summary['executed_at_utc'][:10], blender=blender_version.removeprefix('Blender '),
                     test_run_evidence=provenance)
    planned.update({Path('release_status.json'): json_bytes(release),
                    Path('validation/iteration_report.json'): json_bytes(iteration),
                    Path('validation/test_results.json'): summary_bytes,
                    Path('validation/test_transcript.txt'): transcript_bytes,
                    Path('validation/test_output.txt'): transcript_bytes})
    # Compute the post-update inventory in memory before making any changes.
    inventory = {}
    for path in skill.rglob('*'):
        relative = path.relative_to(skill)
        if path.is_file() and not ignored(relative):
            if not path.resolve().is_relative_to(skill):
                raise ValueError('Package file points outside the skill directory: ' + str(relative))
            inventory[relative] = path.read_bytes()
    inventory.update(planned)
    manifest['files'] = [{'path': path.as_posix(), 'bytes': len(data), 'sha256': sha(data)}
                         for path, data in sorted(inventory.items(), key=lambda item: item[0].as_posix())]
    planned[Path('FILE_MANIFEST.json')] = json_bytes(manifest)
    for relative in planned:
        if not (skill / relative).resolve().is_relative_to(skill):
            raise ValueError('Evidence destination escapes the skill directory: ' + str(relative))
    if current_builder_hash(skill) != builder:
        raise ValueError('Builder source changed during package validation')
    if current_regression_inputs_hash(skill) != inputs_hash:
        raise ValueError('Regression inputs changed during package validation')
    # All input/metadata/history/path/inventory checks above precede every write.
    for relative, data in planned.items():
        path = skill / relative
        if relative.as_posix() in archived:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
        elif not path.exists() or path.read_bytes() != data:
            atomic_write(path, data)
    return {'version': version, 'tests_run': summary['tests_run'], 'builder_sha256': builder,
            'regression_inputs_sha256': inputs_hash,
            'skill': str(skill), 'archived': archived, 'manifest_files': len(manifest['files']),
            'note': 'Real native regression evidence only; no new client-image fidelity or engineering certification.'}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, default=Path(__file__).resolve().parents[1] / 'rebuild-booth-blender')
    parser.add_argument('--test-run', type=Path, required=True, help='Actual completed runner result directory')
    parser.add_argument('--version', help='Release version; defaults to SKILL.md metadata.version')
    args = parser.parse_args(argv)
    try:
        result = package(args.skill, args.test_run, args.version)
    except (OSError, ValueError, KeyError, ImportError) as ex:
        print('Packaging rejected: ' + str(ex), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
