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
    size=params['size']
    if not isinstance(size,(list,tuple)) or len(size)!=3:
        raise ValueError('box size must contain three positive dimensions')
    x,y,z=[positive('size',n)/2 for n in size]
    radius=params.get('bevel_radius',0)
    mode=params.get('bevel_mode','all')
    if mode not in ('all','vertical'):
        raise ValueError('bevel_mode must be all or vertical')
    if isinstance(radius,bool) or not isinstance(radius,(int,float)) or not math.isfinite(radius) or radius<0:
        raise ValueError('bevel_radius must be a finite nonnegative number')
    if radius:
        limit=min(x,y) if mode=='vertical' else min(x,y,z)
        if radius>=limit:
            raise ValueError('bevel_radius must be smaller than half the smallest rounded dimension')
        steps=arc_steps(params.get('segments_per_corner',8))
        return _vertical_bevel_box(x,y,z,radius,steps) if mode=='vertical' else _beveled_box(x,y,z,radius,steps)
    if 'segments_per_corner' in params or 'bevel_mode' in params:
        raise ValueError('bevel segmentation/mode requires a positive bevel_radius')
    v=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
       (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    f=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    return v,f


def _vertical_bevel_box(x,y,z,r,steps):
    """Rounded plan profile with level top/bottom cuts, e.g. posts and counters."""
    loop=rounded_loop(2*x,2*y,r,steps);n=len(loop)
    verts=[(px,py,h) for h in (-z,z) for px,py in loop]
    faces=[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
    faces.extend([tuple(reversed(range(n))),tuple(range(n,2*n))])
    return verts,faces


def _beveled_box(x,y,z,r,steps):
    """Cuboid plus spherical radius: planar faces, round edges and round corners.

    All dimensions remain the requested outer dimensions. Collapsed pole loops
    share vertices, so the final mesh is closed without coincident seams.
    """
    rings=[]
    for k in range(steps+1):
        a=math.pi*k/(2*steps)
        rings.append((-z+r*(1-math.cos(a)),r*math.sin(a)))
    rings.append((z-r,r))
    for k in range(1,steps+1):
        a=math.pi*k/(2*steps)
        rings.append((z-r+r*math.sin(a),r*math.cos(a)))
    verts=[];lookup={};loops=[]
    for h,rho in rings:
        loop=[]
        for cx,cy,a0 in ((x-r,y-r,0),(-x+r,y-r,90),(-x+r,-y+r,180),(x-r,-y+r,270)):
            for k in range(steps+1):
                a=math.radians(a0+90*k/steps)
                point=(cx+rho*math.cos(a),cy+rho*math.sin(a),h)
                key=tuple(round(value,12) for value in point)
                if key not in lookup:lookup[key]=len(verts);verts.append(point)
                loop.append(lookup[key])
        loops.append(loop)
    faces=[]
    def add(face):
        unique=[]
        for index in face:
            if index not in unique:unique.append(index)
        if len(unique)>=3:faces.append(tuple(unique))
    for lower,upper in zip(loops,loops[1:]):
        for i in range(len(lower)):
            j=(i+1)%len(lower);add((lower[i],lower[j],upper[j],upper[i]))
    add(reversed(loops[0]));add(loops[-1])
    return verts,faces


def swept_strip(params: dict):
    """Solid rectangular strip swept along a cubic Bezier chain in local XZ.

    A chain has 3*n+1 control points; neighbouring curves must meet with the
    same tangent direction. Width follows the in-plane normal, depth follows Y.
    The caller supplies local control coordinates; no booth-specific path exists.
    """
    points=params['control_points']
    if not isinstance(points,list) or len(points)<4 or (len(points)-1)%3:
        raise ValueError('control_points must contain 3*n+1 local [x,z] coordinates')
    for point in points:
        if not isinstance(point,(list,tuple)) or len(point)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in point):
            raise ValueError('control_points require finite local [x,z] pairs')
    width=positive('width',params['width']);depth=positive('depth',params['depth'])
    steps=arc_steps(params.get('segments_per_curve',24))
    sampled=[];normals=[]
    for start in range(0,len(points)-1,3):
        p=points[start:start+4]
        for k in range(steps+1):
            t=k/steps;u=1-t
            value=tuple(u**3*p[0][axis]+3*u*u*t*p[1][axis]+3*u*t*t*p[2][axis]+t**3*p[3][axis] for axis in (0,1))
            tangent=tuple(3*u*u*(p[1][axis]-p[0][axis])+6*u*t*(p[2][axis]-p[1][axis])+3*t*t*(p[3][axis]-p[2][axis]) for axis in (0,1))
            length=math.hypot(*tangent)
            if length<1e-10:raise ValueError('strip curve contains a zero tangent')
            normal=(-tangent[1]/length,tangent[0]/length)
            if start and k==0:
                if sum(a*b for a,b in zip(normal,normals[-1]))<.999:
                    raise ValueError('strip curves must share a continuous tangent direction')
                continue
            sampled.append(value);normals.append(normal)
    # Offset ribbons fold when the half-width reaches the local bend radius.
    for i in range(1,len(sampled)):
        distance=math.dist(sampled[i-1],sampled[i])
        if distance<1e-10:raise ValueError('strip path contains coincident samples')
        turn=math.acos(max(-1,min(1,sum(a*b for a,b in zip(normals[i-1],normals[i])))))
        if turn and width/2*turn>=distance*.95:
            raise ValueError('strip width is too large for its bend radius')
    outline=[(p[0]+n[0]*width/2,p[1]+n[1]*width/2) for p,n in zip(sampled,normals)]
    outline.extend((p[0]-n[0]*width/2,p[1]-n[1]*width/2) for p,n in reversed(list(zip(sampled,normals))))
    def crosses(a,b,c,d):
        def orient(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
        return orient(a,b,c)*orient(a,b,d)<-1e-14 and orient(c,d,a)*orient(c,d,b)<-1e-14
    n=len(outline)
    for i in range(n):
        for j in range(i+2,n):
            if i==0 and j==n-1:continue
            if crosses(outline[i],outline[(i+1)%n],outline[j],outline[(j+1)%n]):
                raise ValueError('strip path or offset boundary self-intersects')
    verts=[]
    for p,normal in zip(sampled,normals):
        for side,y in ((1,-depth/2),(-1,-depth/2),(-1,depth/2),(1,depth/2)):
            verts.append((p[0]+normal[0]*width/2*side,y,p[1]+normal[1]*width/2*side))
    faces=[]
    for i in range(len(sampled)-1):
        for side in range(4):
            j=(side+1)%4;faces.append((4*i+side,4*i+j,4*(i+1)+j,4*(i+1)+side))
    faces.extend([(3,2,1,0),tuple(4*(len(sampled)-1)+i for i in range(4))])
    return verts,faces


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


BUILDERS={'box':box,'cylinder':cylinder,'rounded_ring':rounded_ring,'rounded_portal':rounded_portal,'swept_strip':swept_strip}


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
