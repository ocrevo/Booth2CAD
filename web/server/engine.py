"""The only place the studio server touches the skill engine (booth-image-to-model/scripts).

Everything the server needs from the engine goes through the small functions below, so moving the product somewhere else,
or turning the engine into an installable package, means changing this one file.
"""
from __future__ import annotations
import importlib.util
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / 'booth-image-to-model'
SCRIPTS = SKILL / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SECRET_ENV = ('OPENAI_API_KEY',)


# Python packages the engine needs (import name -> pip name); see booth-image-to-model/requirements.txt.
REQUIRED_PACKAGES = {'PIL': 'Pillow', 'numpy': 'numpy', 'scipy': 'scipy', 'jsonschema': 'jsonschema', 'trimesh': 'trimesh'}
_PYTHON = sys.executable or 'python'          # the interpreter running the studio: python3 or a venv on Linux and macOS
INSTALL_HINT = ((subprocess.list2cmdline([_PYTHON]) if os.name == 'nt' else shlex.quote(_PYTHON))
                + ' -m pip install -r booth-image-to-model/requirements.txt')


def missing_packages():
    """pip names of the required packages that cannot be imported here."""
    return [pip for module, pip in REQUIRED_PACKAGES.items() if importlib.util.find_spec(module) is None]


def child_env():
    """The environment for Blender and other child processes: without the API key, which they have no use for."""
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV}


def blender_path(explicit=None):
    """The skill's own lookup: an explicit path or BLENDER_EXE, then PATH, then the usual install places; None when not found."""
    from common import find_blender
    return find_blender(explicit)


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
    detach = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    subprocess.Popen([blender, str(blend_path)], close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, env=child_env(), **detach)                 # stopping the server must not close the user's Blender
    return {'launched': str(blend_path)}
