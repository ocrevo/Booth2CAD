"""Validated metre-based procedural surface patterns; no external image assets.

Only Blender graph construction/inspection uses its node API. Validation is
standard-library Python and shared by the spec validator and native builders.
"""
from __future__ import annotations
import math
from common import finite_vector,material_rgba
from geometry import positive


def grid_parameters(material,component):
    if 'pattern' not in material:return None
    pattern=material['pattern']
    required={'type','spacing','line_width','line_color'}
    allowed=required|{'coordinates','offset','arc_origin_deg'}
    if not isinstance(pattern,dict) or required-set(pattern) or set(pattern)-allowed:
        raise ValueError('grid pattern requires type, spacing, line_width, line_color; unknown pattern fields are rejected')
    if pattern['type']!='grid':raise ValueError('only the procedural grid pattern is supported')
    if not finite_vector(pattern['spacing'],2) or min(pattern['spacing'])<=0:
        raise ValueError('grid spacing requires two positive finite metre values')
    width=positive('grid line_width',pattern['line_width'])
    if width>=min(pattern['spacing']):raise ValueError('grid line_width must be smaller than both spacing values')
    color=pattern['line_color']
    if not finite_vector(color,3) or not all(0<=v<=1 for v in color):
        raise ValueError('grid line_color requires three RGB values in [0,1], in material.color_space')
    mode=pattern.get('coordinates','auto')
    if mode not in ('auto','xy','xz','yz','arc_length_z'):
        raise ValueError('unsupported grid coordinate mode')
    if mode=='auto':mode='arc_length_z' if component['kind']=='arc_panel' else 'xz'
    offset=pattern.get('offset',[0,0])
    if not finite_vector(offset,2):raise ValueError('grid offset requires two finite metre values')
    origin=pattern.get('arc_origin_deg',0)
    if isinstance(origin,bool) or not isinstance(origin,(int,float)) or not math.isfinite(origin):
        raise ValueError('grid arc_origin_deg must be finite')
    if mode!='arc_length_z' and 'arc_origin_deg' in pattern:
        raise ValueError('grid arc_origin_deg is only used by arc_length_z coordinates')
    radius=None
    if mode=='arc_length_z':
        if component['kind']!='arc_panel':raise ValueError('arc_length_z grid coordinates require arc_panel geometry')
        p=component['params'];radius=positive('radius',p['radius'])
        span=abs(p['end_deg']-p['start_deg'])
        midpoint=(p['start_deg']+p['end_deg'])/2-origin
        midpoint=(midpoint+180)%360-180
        if midpoint-span/2<-180 or midpoint+span/2>180:
            raise ValueError('arc grid crosses its angular seam; choose a shared arc_origin_deg near the panel group centre')
    return {'spacing':list(pattern['spacing']),'line_width':width,
            'line_color':material_rgba({'color':color+[1],'color_space':material.get('color_space','linear')}),
            'coordinates':mode,'offset':list(offset),'arc_origin_deg':origin,'radius':radius}


def apply_grid(nodes,links,shader,material,component):
    """Attach a repeatable grid to local unscaled coordinates, in metres.

    Arc panels unwrap polar angle into centreline arc length. A shared angular
    origin and offset keep separate material segments aligned. This is surface
    colour, not an invented perforation or fabrication hole.
    """
    p=grid_parameters(material,component)
    if p is None:return
    def node(name,kind):
        result=nodes.new(kind);result.name='grid_'+name;return result
    def math_node(name,operation,left,right=None):
        result=node(name,'ShaderNodeMath');result.operation=operation
        for index,value in enumerate((left,right)):
            if value is None:continue
            if isinstance(value,(int,float)):result.inputs[index].default_value=value
            else:links.new(value,result.inputs[index])
        return result.outputs[0]
    tex=node('coordinates','ShaderNodeTexCoord');separate=node('axes','ShaderNodeSeparateXYZ')
    links.new(tex.outputs['Object'],separate.inputs[0])
    axis={name:separate.outputs[name] for name in ('X','Y','Z')}
    if p['coordinates']=='arc_length_z':
        angle=math.radians(p['arc_origin_deg']);c,s=math.cos(angle),math.sin(angle)
        x=math_node('rotated_x','ADD',math_node('x_cos','MULTIPLY',axis['X'],c),math_node('y_sin','MULTIPLY',axis['Y'],s))
        y=math_node('rotated_y','SUBTRACT',math_node('y_cos','MULTIPLY',axis['Y'],c),math_node('x_sin','MULTIPLY',axis['X'],s))
        u=math_node('arc_length','MULTIPLY',math_node('polar_angle','ARCTAN2',y,x),p['radius'])
        coordinates=(u,axis['Z'])
    else:coordinates=tuple(axis[a.upper()] for a in p['coordinates'])
    masks=[]
    for index,(name,value) in enumerate(zip(('u','v'),coordinates)):
        shifted=math_node(name+'_offset','ADD',value,p['offset'][index])
        frequency=math_node(name+'_frequency','MULTIPLY',shifted,1/p['spacing'][index])
        fraction=math_node(name+'_fraction','FRACT',frequency)
        distance=math_node(name+'_distance','ABSOLUTE',math_node(name+'_centred','SUBTRACT',fraction,.5))
        masks.append(math_node(name+'_line','GREATER_THAN',distance,.5-p['line_width']/(2*p['spacing'][index])))
    mask=math_node('union','MAXIMUM',*masks)
    mix=node('color','ShaderNodeMixRGB');mix.blend_type='MIX'
    mix.inputs[1].default_value=material_rgba(material);mix.inputs[2].default_value=p['line_color']
    links.new(mask,mix.inputs[0]);links.new(mix.outputs[0],shader.inputs['Base Color'])
    links.new(mix.outputs[0],shader.inputs['Emission Color'])


def grid_graph_signature(tree):
    """Canonical native pattern graph, including constants and shader links."""
    def value(socket):
        if not hasattr(socket,'default_value'):return None
        data=socket.default_value
        if isinstance(data,(float,int)):return round(float(data),6)
        try:return [round(float(v),6) for v in data]
        except TypeError:return str(data)
    nodes=[]
    for node in tree.nodes:
        if not node.name.startswith('grid_'):continue
        nodes.append({'name':node.name,'type':node.bl_idname,
                      'operation':getattr(node,'operation',None),'blend_type':getattr(node,'blend_type',None),
                      'inputs':[(s.name,value(s)) for s in node.inputs]})
    links=[(link.from_node.name,link.from_socket.name,link.to_node.name,link.to_socket.name)
           for link in tree.links if link.from_node.name.startswith('grid_') or link.to_node.name.startswith('grid_')]
    return {'nodes':sorted(nodes,key=lambda n:n['name']),'links':sorted(links)}
