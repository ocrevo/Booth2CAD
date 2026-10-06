"""Mask-only image-space QA. Never compare venue RGB with isolated booth RGB.

Requires numpy, Pillow, scipy. Same canvas and camera are required; no automatic
resize, crop, registration or per-part warping is performed to conceal a mismatch.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion, distance_transform_edt
from common import read_json,write_json,file_sha


def load_mask(path):
    im=Image.open(path)
    if im.mode=='RGBA': return np.asarray(im.getchannel('A'))>127
    arr=np.asarray(im)
    if arr.ndim==3:
        if not np.all(arr[...,0]==arr[...,1]) or not np.all(arr[...,0]==arr[...,2]):
            raise ValueError('A photo/RGB render is not a mask. Supply an explicit grayscale mask or RGBA alpha.')
        arr=arr[...,0]
    if arr.ndim!=2: raise ValueError('Expected 2D mask')
    return arr>127


def compare_masks(reference, candidate, valid=None):
    if reference.shape!=candidate.shape: raise ValueError(f'IMAGE_SHAPE_MISMATCH: {reference.shape} vs {candidate.shape}; use matched camera/canvas')
    valid=np.ones_like(reference,dtype=bool) if valid is None else np.asarray(valid,dtype=bool)
    if valid.shape!=reference.shape: raise ValueError('VALID_MASK_SHAPE_MISMATCH')
    ref,can=np.asarray(reference,dtype=bool)&valid,np.asarray(candidate,dtype=bool)&valid
    if not valid.any(): raise ValueError('EMPTY_VALID_REGION')
    if not ref.any(): raise ValueError('EMPTY_REFERENCE_MASK: not enough visible evidence')
    union=(ref|can).sum();inter=(ref&can).sum()
    iou=float(inter/union)
    # A valid-region boundary is not an object boundary; discard its immediate rim.
    interior=binary_erosion(valid,border_value=1)
    re=(ref ^ binary_erosion(ref,border_value=0))&interior
    ce=(can ^ binary_erosion(can,border_value=0))&interior
    h,w=ref.shape;diag=float(np.hypot(h,w))
    if not re.any() or not ce.any(): dist=1.0
    else: dist=float((distance_transform_edt(~re)[ce].mean()+distance_transform_edt(~ce)[re].mean())/(2*diag))
    return {'iou':iou,'symmetric_boundary_distance_diag':dist,
            'reference_pixels':int(ref.sum()),'candidate_pixels':int(can.sum()),
            'valid_pixels':int(valid.sum()),'canvas':[int(w),int(h)]}


def landmark_metrics(reference, projected, width, height):
    """IDs must match exactly. Coordinates are normalized top-left uv."""
    expected={r['id']:r for r in reference if r.get('visibility')=='visible'}
    actual={p['id']:p for p in projected}
    missing=sorted(set(expected)-set(actual))
    if missing: raise ValueError('MISSING_LANDMARKS: '+','.join(missing))
    if not expected: raise ValueError('NO_VISIBLE_LANDMARKS')
    errors=[];detail=[]
    for ident,r in expected.items():
        p=actual[ident]
        if p.get('depth',1)<=0: raise ValueError('LANDMARK_BEHIND_CAMERA: '+ident)
        du,dv=np.asarray(p['uv'],float)-np.asarray(r['uv'],float)
        e=float(np.hypot(du*width,dv*height)/np.hypot(width,height))
        errors.append(e);detail.append({'id':ident,'error_diag':e,'used_for_fit':r.get('fit',False)})
    held=[d['error_diag'] for d in detail if not d['used_for_fit']]
    return {'median_diag':float(np.median(errors)),'p90_diag':float(np.quantile(errors,.9)),
            'held_out_count':len(held),'held_out_median_diag':float(np.median(held)) if held else None,
            'detail':detail}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--reference-mask',required=True);p.add_argument('--candidate-mask',required=True)
    p.add_argument('--valid-mask');p.add_argument('--output',required=True)
    a=p.parse_args()
    try:
        result=compare_masks(load_mask(a.reference_mask),load_mask(a.candidate_mask),load_mask(a.valid_mask) if a.valid_mask else None)
        result.update({'status':'measured','reference_sha256':file_sha(a.reference_mask),'candidate_sha256':file_sha(a.candidate_mask),
                       'valid_sha256':file_sha(a.valid_mask) if a.valid_mask else None,
                       'note':'Geometry mask metrics only; not a complete semantic or fabrication verdict.'})
        write_json(a.output,result);return 0
    except (ValueError,OSError) as ex:
        write_json(a.output,{'status':'blocked','reason':str(ex)});return 2

if __name__=='__main__': raise SystemExit(main())
