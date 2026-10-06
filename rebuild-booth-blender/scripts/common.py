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
