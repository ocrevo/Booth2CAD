"""Shared, deterministic IO and versioned fingerprints; standard library only."""
from __future__ import annotations
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path


def read_json(path):
    def reject(value): raise ValueError(f'Nonfinite JSON value: {value}')
    return json.loads(Path(path).read_text(encoding='utf-8'),parse_constant=reject)


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def digest(value): return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.',suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: f.write(payload)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def finite_vector(value,n):
    return (isinstance(value,list) and len(value)==n and
            all(not isinstance(x,bool) and isinstance(x,(float,int)) and math.isfinite(x) for x in value))


def material_rgba(params):
    """Shader inputs are linear; explicitly sampled display RGB can be sRGB."""
    color=list(params['color'])
    if params.get('color_space','linear')=='srgb':
        color[:3]=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in color[:3]]
    return color


def render_rig(bounds, aspect, reference_camera):
    """Dimension-independent inspection framing and physically scaled area lights.

    Bounds are the actual transformed booth geometry, including the floor. The
    The inspection azimuth differs from the reference by at least 35 degrees.
    Distance fits all eight bounds corners in camera space, rather than a sphere
    that wastes most of a wide image. Wattage scales with area.
    """
    low,high=bounds
    if not finite_vector(low,3) or not finite_vector(high,3) or any(b<a for a,b in zip(low,high)):
        raise ValueError('bounds must be ordered finite XYZ vectors')
    if isinstance(aspect,bool) or not isinstance(aspect,(float,int)) or not math.isfinite(aspect) or aspect<=0:
        raise ValueError('image aspect must be positive')
    spans=[b-a for a,b in zip(low,high)];extent=max(spans)
    if extent<=0:raise ValueError('cannot frame empty geometry')
    centre=[(a+b)/2 for a,b in zip(low,high)]
    direction=[reference_camera['position'][i]-reference_camera['target'][i] for i in range(3)]
    horizontal=math.hypot(direction[0],direction[1])
    if horizontal<1e-9:direction=[-1,-1,.8]
    else:
        x,y=direction[0]/horizontal,direction[1]/horizontal
        reflected=(-x,y)
        gap=math.acos(max(-1,min(1,x*reflected[0]+y*reflected[1])))
        if gap<math.radians(35):
            cross=x*reflected[1]-y*reflected[0]
            turn=math.radians(35)*(1 if cross>=0 else -1)
            reflected=(x*math.cos(turn)-y*math.sin(turn),x*math.sin(turn)+y*math.cos(turn))
        direction=[*reflected,max(.55,abs(direction[2])/horizontal)]
    length=math.sqrt(sum(v*v for v in direction));direction=[v/length for v in direction]
    lens,sensor=40,36
    # Blender uses HORIZONTAL sensor fit, including portrait outputs.
    tan_x=sensor/(2*lens);tan_y=tan_x/aspect
    horizontal=math.hypot(direction[0],direction[1])
    right=[-direction[1]/horizontal,direction[0]/horizontal,0]
    up=[-direction[0]*direction[2]/horizontal,-direction[1]*direction[2]/horizontal,horizontal]
    distance=0
    for x in (low[0],high[0]):
        for y in (low[1],high[1]):
            for z in (low[2],high[2]):
                delta=[v-c for v,c in zip((x,y,z),centre)]
                back=sum(v*d for v,d in zip(delta,direction))
                projected_x=abs(sum(v*d for v,d in zip(delta,right)))
                projected_y=abs(sum(v*d for v,d in zip(delta,up)))
                distance=max(distance,back+1.12*max(projected_x/tan_x,projected_y/tan_y),back+extent*.01)
    inspection={'projection':'perspective','position':[centre[i]+distance*direction[i] for i in range(3)],
                'target':centre,'lens_mm':lens,'sensor_width_mm':sensor,'principal_point':[.5,.5]}
    lights=[]
    for name,offset,energy,size in (
            ('Key',[.35,-.8,1.0],34,.8),('Fill',[-.8,-.2,.65],22,.65),('Rim',[.2,.75,1.0],25,.65)):
        lights.append({'name':name,'position':[centre[i]+offset[i]*extent for i in range(3)],
                       'target':centre,'energy':energy*extent*extent,'size':size*extent})
    return {'bounds':[list(low),list(high)],'centre':centre,'extent':extent,'inspection_camera':inspection,'lights':lights}


def hd_scale_for(width, height, requested, max_megapixels=5.0):
    """Largest integer HD scale <= requested whose frame stays within max_megapixels (1 means no HD).

    Measured on a 16 GB CPU-only machine: a 4.9 MP HD frame rendered, a 6.9 MP frame ran the OIDN denoiser
    out of memory and killed the process, so the default cap is 5 MP.
    """
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError('requested HD scale must be an integer >= 1')
    if not (isinstance(max_megapixels, (int, float)) and math.isfinite(max_megapixels) and max_megapixels > 0):
        raise ValueError('max_megapixels must be positive')
    for scale in range(requested, 1, -1):
        if width * scale * height * scale <= max_megapixels * 1e6:
            return scale
    return 1


def _blender_version_key(path):
    import re
    return [int(n) for n in re.findall(r'\d+', Path(path).parent.name)] or [0]


def blender_candidates():
    """Where Blender usually is on this operating system, newest first where several versions sit side by side."""
    import glob
    import sys
    if sys.platform == 'win32':
        found = []
        for base in (os.environ.get('ProgramFiles') or 'C:/Program Files', os.environ.get('ProgramFiles(x86)')):
            if base:
                found += glob.glob(os.path.join(base, 'Blender Foundation', 'Blender*', 'blender.exe'))
        return sorted(found, key=_blender_version_key, reverse=True)
    if sys.platform == 'darwin':
        return ['/Applications/Blender.app/Contents/MacOS/Blender', os.path.expanduser('~/Applications/Blender.app/Contents/MacOS/Blender')]
    return ['/snap/bin/blender', '/usr/bin/blender', '/usr/local/bin/blender', '/opt/blender/blender']


def find_blender(explicit=None):
    """The Blender executable: an explicit path (argument, else BLENDER_EXE), then PATH, then the usual install places.
    An explicit path that does not exist gives None rather than silently another Blender. A macOS .app folder is accepted."""
    import shutil

    def usable(candidate):
        folder = candidate.rstrip(os.sep + (os.altsep or '')) or candidate     # '/Applications/Blender.app/' is the same folder
        if folder.endswith('.app') and os.path.isdir(folder):
            candidate = os.path.join(folder, 'Contents', 'MacOS', 'Blender')
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
        found = shutil.which(candidate)
        return os.path.abspath(found) if found else None
    chosen = explicit or os.environ.get('BLENDER_EXE')
    if chosen:
        return usable(chosen)
    for candidate in [shutil.which('blender'), *blender_candidates()]:
        if candidate and usable(candidate):
            return usable(candidate)
    return None


def code_hash():
    root=Path(__file__).resolve().parent
    return digest({p.name:file_sha(p) for p in sorted(root.glob('*.py'))})


def fingerprints(spec):
    """Invalidation plan, not a promise of per-object incremental Blender builds."""
    comps=spec.get('components',[])
    geom=[{k:c.get(k) for k in ('id','kind','scope_id','owner','location','rotation_deg','params')} for c in comps]
    source=spec.get('source',{})
    version=code_hash()
    analysis=digest({'source':source,'scope':spec.get('scope'),'uncertainties':spec.get('uncertainties')})
    geometry=digest({'source_sha':source.get('sha256'),'geometry':geom,'scope':spec.get('scope'),'builder':version})
    camera=digest({'geometry':geometry,'camera':spec.get('camera'),'landmarks':spec.get('landmarks'),'source':source})
    render=digest({'geometry':geometry,'camera':camera,'components':comps,'builder':version})
    qa=digest({'render':render,'quality':spec.get('quality'),'source':source,'requirements':spec.get('requirements')})
    return {'analysis':analysis,'geometry':geometry,'camera':camera,'render':render,'qa':qa}


def cache_valid(manifest, expected_key, root):
    """Only complete outputs with matching bytes count as cache hits."""
    if manifest.get('status')!='complete' or manifest.get('key')!=expected_key: return False
    outputs=manifest.get('outputs')
    if not isinstance(outputs,list) or not outputs: return False
    root=Path(root).resolve()
    for item in outputs:
        p=(root/item.get('path','')).resolve()
        if not p.is_relative_to(root) or not p.is_file(): return False
        if p.stat().st_size==0 or file_sha(p)!=item.get('sha256'): return False
    return True
