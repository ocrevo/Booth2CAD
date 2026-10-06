"""Deterministic metre-based geometry. Standard library only; no Blender dependency.

Rounded forms are explicit profiles, not separate beveled boxes. Object coordinates
are centred; Blender's object transform supplies placement. Quads are planar.
"""
from __future__ import annotations
import math
from typing import Any


def positive(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f'{name}: expected a finite positive number')
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name}: expected a finite positive number')
    return float(value)


def arc_steps(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 4 <= value <= 128:
        raise ValueError('segments_per_corner must be an integer in [4,128]')
    return value


def rounded_loop(width: float, depth: float, radius: float, steps: int = 16):
    w, d, r = (positive(n, v) for n, v in zip(('width','depth','radius'), (width,depth,radius)))
    steps = arc_steps(steps)
    if r >= min(w,d)/2:
        raise ValueError('radius must be smaller than half the smaller outer dimension')
    result = []
    for cx, cy, a0 in ((w/2-r,d/2-r,0),(-w/2+r,d/2-r,90),
                       (-w/2+r,-d/2+r,180),(w/2-r,-d/2+r,270)):
        for k in range(steps+1):
            a = math.radians(a0+90*k/steps)
            result.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return result


def inside_rounded_rect(x, y, w, d, r, clearance=0.0):
    w, d, r = w-2*clearance, d-2*clearance, max(0.0,r-clearance)
    if abs(x)>w/2 or abs(y)>d/2: return False
    dx, dy = max(0.0,abs(x)-(w/2-r)), max(0.0,abs(y)-(d/2-r))
    return dx*dx+dy*dy <= r*r+1e-12


def rounded_ring(params: dict):
    w,d = params['outer_size']
    wi,di = params['inner_size']
    r,ri,h = params['outer_radius'],params['inner_radius'],positive('height',params['height'])
    nseg = params.get('segments_per_corner',16)
    outer = rounded_loop(w,d,r,nseg)
    inner = rounded_loop(wi,di,ri,nseg)
    if wi >= w or di >= d:
        raise ValueError('ring opening must be strictly smaller than outer dimensions')
    if not all(inside_rounded_rect(x,y,w,d,r,0.001) for x,y in inner):
        raise ValueError('ring inner boundary crosses or touches outer boundary')
    n=len(outer)
    v=[(x,y,z) for z in (-h/2,h/2) for loop in (outer,inner) for x,y in loop]
    f=[]
    for i in range(n):
        j=(i+1)%n
        f.extend([(i,j,2*n+j,2*n+i),
                  (n+j,n+i,3*n+i,3*n+j),
                  (j,i,n+i,n+j),
                  (2*n+i,2*n+j,3*n+j,3*n+i)])
    return v,f


def _arch_path(w,h,r,steps):
    if not 0 < r < min(w/2,h): raise ValueError('invalid portal corner radius')
    result=[(-w/2,0.0)]
    for cx,start,end in ((-w/2+r,180,90),(w/2-r,90,0)):
        for k in range(steps+1):
            a=math.radians(start+(end-start)*k/steps)
            result.append((cx+r*math.cos(a),h-r+r*math.sin(a)))
    result.append((w/2,0.0))
    return result


def rounded_portal(params: dict):
    names=('width','height','depth','side_width','beam_height','outer_radius','inner_radius')
    w,h,d,t,b,r,ri=[positive(k,params[k]) for k in names]
    steps=arc_steps(params.get('segments_per_corner',16))
    if 2*t>=w or b>=h: raise ValueError('portal opening is closed or inverted')
    wi,hi=w-2*t,h-b
    outer,inner=_arch_path(w,h,r,steps),_arch_path(wi,hi,ri,steps)
    # Check the inner path lies inside the outer profile, leaving a positive band.
    for x,z in inner[1:-1]:
        if abs(x)>=w/2 or z>=h: raise ValueError('portal contours intersect')
        if z>h-r and abs(x)>w/2-r:
            if (abs(x)-(w/2-r))**2+(z-(h-r))**2 >= r*r:
                raise ValueError('portal inner contour crosses outer rounded corner')
    n=len(outer)
    v=[(x,y,z-h/2) for y in (-d/2,d/2) for path in (outer,inner) for x,z in path]
    f=[]
    for i in range(n-1):
        j=i+1
        f.extend([(i,n+i,n+j,j),
                  (2*n+i,2*n+j,3*n+j,3*n+i),
                  (i,j,2*n+j,2*n+i),
                  (n+j,n+i,3*n+i,3*n+j)])
    # Close the two feet only; never span the central opening.
    f.extend([(0,2*n,3*n,n), (n-1,2*n-1,4*n-1,3*n-1)])
    return v,f


def box(params: dict):
    x,y,z=[positive('size',n)/2 for n in params['size']]
    v=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
       (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    f=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    return v,f


def cylinder(params: dict):
    r,h=positive('radius',params['radius']),positive('height',params['height'])
    n=params.get('segments',64)
    if isinstance(n,bool) or not isinstance(n,int) or not 12<=n<=512: raise ValueError('invalid cylinder segments')
    v=[(r*math.cos(2*math.pi*i/n),r*math.sin(2*math.pi*i/n),z) for z in (-h/2,h/2) for i in range(n)]
    v.extend([(0,0,-h/2),(0,0,h/2)])
    f=[]
    for i in range(n):
        j=(i+1)%n
        f.extend([(i,j,n+j,n+i),(2*n,j,i),(2*n+1,n+i,n+j)])
    return v,f


BUILDERS={'box':box,'cylinder':cylinder,'rounded_ring':rounded_ring,'rounded_portal':rounded_portal}


def mesh_for(component: dict):
    kind=component['kind']
    if kind not in BUILDERS: raise ValueError(f'Unsupported primitive: {kind}; add and test a builder, never substitute a box')
    return BUILDERS[kind](component['params'])


def transform_point(local, location, rotation_deg):
    """Blender XYZ Euler convention, local -> world. No nonuniform scale."""
    x,y,z=map(float,local)
    rx,ry,rz=map(math.radians,rotation_deg)
    y,z=y*math.cos(rx)-z*math.sin(rx),y*math.sin(rx)+z*math.cos(rx)
    x,z=x*math.cos(ry)+z*math.sin(ry),-x*math.sin(ry)+z*math.cos(ry)
    x,y=x*math.cos(rz)-y*math.sin(rz),x*math.sin(rz)+y*math.cos(rz)
    return [x+location[0],y+location[1],z+location[2]]


def triangulate(faces):
    return [(f[0],f[i],f[i+1]) for f in faces for i in range(1,len(f)-1)]
