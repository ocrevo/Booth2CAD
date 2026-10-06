"""Bounded perspective-camera fitting with fixed geometry and held-out anchors.
Requires numpy/scipy. Does not infer 3D truth from a photograph. Inputs must be
reviewed 2D/3D correspondences. Occluded anchors are excluded from optimization.
"""
from __future__ import annotations
import argparse
import math
import numpy as np
from scipy.optimize import least_squares
from common import read_json,write_json,digest
from geometry import transform_point
from validate_spec import validate
from compare import landmark_metrics


def camera_vector(camera):
    pos=np.asarray(camera['position'],float)
    direction=np.asarray(camera['target'],float)-pos
    direction/=np.linalg.norm(direction)
    yaw=math.atan2(direction[0],direction[1]);pitch=math.asin(direction[2])
    return np.r_[pos,yaw,pitch,math.radians(camera.get('roll_deg',0)),camera['lens_mm']]


def vector_camera(x, original):
    c=dict(original)
    yaw,pitch=x[3:5]
    fwd=np.array([math.cos(pitch)*math.sin(yaw),math.cos(pitch)*math.cos(yaw),math.sin(pitch)])
    c.update(position=x[:3].tolist(),target=(x[:3]+fwd*5).tolist(),lens_mm=float(x[6]),roll_deg=float(math.degrees(x[5])),fit_status='landmark_fitted')
    return c


def project(points, camera, width, height):
    pts=np.asarray(points,float);x=camera_vector(camera)
    yaw,pitch,roll=x[3:6]
    f=np.array([math.cos(pitch)*math.sin(yaw),math.cos(pitch)*math.cos(yaw),math.sin(pitch)])
    right=np.cross(f,[0,0,1]);right/=np.linalg.norm(right)
    up=np.cross(right,f)
    r=right*math.cos(roll)+up*math.sin(roll)
    u=up*math.cos(roll)-right*math.sin(roll)
    delta=pts-x[:3];z=delta@f
    safe=np.maximum(z,1e-6);fx=camera['lens_mm']/camera['sensor_width_mm']
    principal=camera['principal_point']
    uv=np.c_[principal[0]+fx*(delta@r)/safe,
             principal[1]-fx*width/height*(delta@u)/safe]
    return uv,z


def fit(spec, max_nfev=400):
    report=validate(spec)
    if not report['valid']: raise ValueError('Invalid spec: '+str(report['errors'][0]))
    camera=spec['camera']
    if camera['projection']!='perspective': raise ValueError('Orthographic automatic fitting is not implemented; use manually reviewed orthographic camera')
    comps={c['id']:c for c in spec['components']}
    landmarks=[l for l in spec['landmarks'] if l['visibility']=='visible']
    fit_idx=[i for i,l in enumerate(landmarks) if l['fit']]
    held_idx=[i for i,l in enumerate(landmarks) if not l['fit']]
    if len(fit_idx)<8 or len(held_idx)<2: raise ValueError('Need >=8 visible fit anchors and >=2 held-out anchors; do not fabricate hidden corners')
    xyz=np.asarray([transform_point(l['local_xyz'],comps[l['component_id']]['location'],comps[l['component_id']]['rotation_deg']) for l in landmarks])
    if np.linalg.matrix_rank(xyz[fit_idx]-xyz[fit_idx].mean(axis=0),tol=1e-5)<3:
        raise ValueError('DEGENERATE_ANCHORS: fitted points are coplanar; constrain camera manually or add trusted depth-separated points')
    target=np.asarray([l['uv'] for l in landmarks]);w,h=spec['source']['width'],spec['source']['height']
    x0=camera_vector(camera)
    lower=np.r_[x0[:3]-20,x0[3]-math.pi/2,-1.45,-.35,16.0]
    upper=np.r_[x0[:3]+20,x0[3]+math.pi/2,1.45,.35,120.0]
    if np.any(x0<=lower) or np.any(x0>=upper): raise ValueError('Initial camera outside fitting bounds')
    weights=np.asarray([math.sqrt(float(l.get('weight',1))) for l in landmarks])[fit_idx,None]
    def residual(x):
        c=vector_camera(x,camera);uv,z=project(xyz,c,w,h)
        err=(uv[fit_idx]-target[fit_idx])*np.array([w,h])/math.hypot(w,h)
        penalty=np.maximum(0,.05-z[fit_idx])*0.1
        return np.r_[(err*weights).ravel(),penalty]
    before_uv,_=project(xyz,camera,w,h)
    result=least_squares(residual,x0,bounds=(lower,upper),loss='huber',f_scale=.015,
                         max_nfev=max_nfev,xtol=1e-11,ftol=1e-11,gtol=1e-11)
    fitted=vector_camera(result.x,camera);uv,z=project(xyz,fitted,w,h)
    projected=[{'id':l['id'],'uv':uv[i].tolist(),'depth':float(z[i])} for i,l in enumerate(landmarks)]
    metric=landmark_metrics(landmarks,projected,w,h)
    return {'status':'candidate_camera','optimizer_success':bool(result.success),'spec_sha256':digest(spec),
            'iterations':int(result.nfev),'camera':fitted,'landmarks':projected,'metrics':metric,
            'initial_uv':before_uv.tolist(),'note':'Fit only the supplied fixed geometry. Human/vision review still required; no silhouette or topology acceptance is implied.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--output',required=True);p.add_argument('--max-evaluations',type=int,default=400)
    a=p.parse_args()
    try: write_json(a.output,fit(read_json(a.spec),a.max_evaluations));return 0
    except (ValueError,KeyError,OSError) as ex:write_json(a.output,{'status':'blocked','reason':str(ex)});return 2

if __name__=='__main__':raise SystemExit(main())
