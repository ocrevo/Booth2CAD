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
    camera fits a bounding sphere against the narrower field of view, preserving
    clearance even for a tall or unusually deep stand. Wattage scales with area.
    """
    low,high=bounds
    if not finite_vector(low,3) or not finite_vector(high,3) or any(b<a for a,b in zip(low,high)):
        raise ValueError('bounds must be ordered finite XYZ vectors')
    if isinstance(aspect,bool) or not isinstance(aspect,(float,int)) or not math.isfinite(aspect) or aspect<=0:
        raise ValueError('image aspect must be positive')
    spans=[b-a for a,b in zip(low,high)];extent=max(spans)
    if extent<=0:raise ValueError('cannot frame empty geometry')
    centre=[(a+b)/2 for a,b in zip(low,high)]
    radius=math.sqrt(sum(v*v for v in spans))/2
    direction=[reference_camera['position'][i]-reference_camera['target'][i] for i in range(3)]
    # Opposite horizontal side gives useful evidence beyond the matched source.
    horizontal=math.hypot(direction[0],direction[1])
    if horizontal<1e-9:direction=[-1,-1,.8]
    else:direction=[-direction[0]/horizontal,direction[1]/horizontal,max(.55,abs(direction[2])/horizontal)]
    length=math.sqrt(sum(v*v for v in direction));direction=[v/length for v in direction]
    lens,sensor=40,36
    half_fov=math.atan(sensor/(2*lens)*min(1,1/aspect))
    distance=radius/math.sin(half_fov)*1.12
    inspection={'projection':'perspective','position':[centre[i]+distance*direction[i] for i in range(3)],
                'target':centre,'lens_mm':lens,'sensor_width_mm':sensor,'principal_point':[.5,.5]}
    lights=[]
    for name,offset,energy,size in (
            ('Key',[.35,-.8,1.0],34,.8),('Fill',[-.8,-.2,.65],22,.65),('Rim',[.2,.75,1.0],25,.65)):
        lights.append({'name':name,'position':[centre[i]+offset[i]*extent for i in range(3)],
                       'target':centre,'energy':energy*extent*extent,'size':size*extent})
    return {'bounds':[list(low),list(high)],'centre':centre,'extent':extent,'inspection_camera':inspection,'lights':lights}


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
