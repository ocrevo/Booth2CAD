"""The only place the studio server touches the skill engine (booth-image-to-model/scripts).

Everything the server needs from the engine goes through the small functions below, so moving the product somewhere else,
or turning the engine into an installable package, means changing this one file.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / 'booth-image-to-model'
SCRIPTS = SKILL / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

DEFAULT_BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
SECRET_ENV = ('OPENAI_API_KEY',)


def child_env():
    """The environment for Blender and other child processes: without the API key, which they have no use for."""
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV}


def blender_path(explicit=None):
    """BLENDER_EXE, then PATH, then the install location this project was developed with; None when nothing is found."""
    for candidate in (explicit, os.environ.get('BLENDER_EXE'), shutil.which('blender'), DEFAULT_BLENDER):
        if candidate and (Path(candidate).exists() or shutil.which(candidate)):
            return str(candidate)
    return None


# ------------------------------------------------------------------ scene description and compile
def scene_schema():
    import draft_compile
    return draft_compile.load_schema()


def validate_scene(scene):
    import draft_compile
    return draft_compile.validate_scene(scene)


def scene_error():
    import draft_compile
    return draft_compile.SceneError


def compile_scene(scene, image_path, out_dir):
    import draft_compile
    return draft_compile.compile_scene(scene, image_path, out_dir)


def draw_overlay(fit, image_path, out_path):
    from overlay import draw_overlay as draw
    return draw(fit, str(image_path), str(out_path))


# ------------------------------------------------------------------ spec
def validate_spec(spec, source_root, source_size=None):
    import validate_spec as v
    return v.validate(spec, source_root, source_size=source_size)


# ------------------------------------------------------------------ Blender and exports
def preview(spec_path, out_root):
    import boothctl
    return boothctl.preview(str(spec_path), str(out_root), blender_path())


def build(spec_path, out_dir, samples=16, hd_scale=1, timeout=3600):
    """One full build with renders in a fresh folder. Returns {returncode, seconds, log_tail, report}."""
    blender = blender_path()
    if not blender:
        raise RuntimeError('Blender was not found: set BLENDER_EXE or put blender on PATH')
    cmd = [blender, '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
           '--python', str(SCRIPTS / 'blender_build.py'), '--', '--spec', str(spec_path), '--out', str(out_dir),
           '--render', '--samples', str(samples)]
    if hd_scale and hd_scale > 1:
        cmd += ['--hd-scale', str(hd_scale), '--hd-views', 'client']
    started = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, check=False, env=child_env())
    report = None
    report_file = Path(out_dir) / 'build_report.json'
    if report_file.is_file():
        import json
        report = json.loads(report_file.read_text(encoding='utf-8'))
    return {'returncode': proc.returncode, 'seconds': round(time.time() - started, 1), 'log_tail': ((proc.stdout or '') + (proc.stderr or ''))[-1500:], 'report': report}


def export_glb(spec_path, out_path):
    import export_glb as exporter
    return exporter.run(str(spec_path), str(out_path))


def open_in_blender(blend_path):
    """Start Blender with the file and return at once (the window belongs to the user from here on)."""
    blender = blender_path()
    if not blender:
        raise RuntimeError('Blender was not found: set BLENDER_EXE or put blender on PATH')
    flags = 0
    if os.name == 'nt':
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([blender, str(blend_path)], creationflags=flags, close_fds=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=child_env())
    return {'launched': str(blend_path)}
