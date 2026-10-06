"""Fail-closed spec validation usable inside Blender without pip dependencies."""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from common import finite_vector,file_sha,read_json,write_json
from geometry import mesh_for,positive

PARAM_KEYS={
 'box':({'size'},{'size'}),
 'cylinder':({'radius','height'},{'radius','height','segments'}),
 'rounded_ring':({'outer_size','inner_size','outer_radius','inner_radius','height'},
                 {'outer_size','inner_size','outer_radius','inner_radius','height','segments_per_corner'}),
 'rounded_portal':({'width','height','depth','side_width','beam_height','outer_radius','inner_radius'},
                   {'width','height','depth','side_width','beam_height','outer_radius','inner_radius','segments_per_corner'}),
 'text':({'body','size'},{'body','size','extrude'}),
}


def validate(spec, source_root=None):
    errors=[]; warnings=[]
    def error(code,path,message): errors.append({'code':code,'path':path,'message':message})
    if not isinstance(spec,dict):
        return {'valid':False,'errors':[{'code':'INVALID_ROOT','path':'','message':'Expected JSON object'}],'warnings':[]}
    required={'schema_version','project','source','scale','scope','components','camera','requirements','landmarks','uncertainties','quality'}
    for k in sorted(required-set(spec)): error('MISSING_FIELD',k,'Required v2 field missing; do not silently migrate an old proxy')
    for k in sorted(set(spec)-required): error('UNKNOWN_FIELD',k,'Unknown root field; likely unused parameter')
    if spec.get('schema_version')!='2.0': error('SCHEMA_VERSION','schema_version','Expected 2.0')
    if errors: return {'valid':False,'errors':errors,'warnings':warnings}
    try:
        source=spec['source']
        for k in ('image','sha256','width','height'):
            if k not in source: error('SOURCE_FIELD','source.'+k,'Missing source identity')
        if not re.fullmatch('[a-f0-9]{64}',source.get('sha256','')): error('SOURCE_HASH','source.sha256','Expected a SHA-256 digest')
        for k in ('width','height'):
            if isinstance(source.get(k),bool) or not isinstance(source.get(k),int) or source[k]<=0: error('SOURCE_SIZE','source.'+k,'Positive integer required')
        if source_root is not None:
            p=(Path(source_root)/source.get('image','')).resolve()
            if not p.is_file(): error('SOURCE_MISSING','source.image',str(p))
            elif file_sha(p)!=source['sha256']: error('SOURCE_CHANGED','source.sha256','Source bytes do not match the recorded input')
        scale=spec['scale']
        if scale.get('units')!='m': error('UNITS','scale.units','Only metres supported')
        if scale.get('basis') not in ('user_dimensions','user_assumption','single_image_estimate'): error('SCALE_BASIS','scale.basis','Record measured versus assumed scale')
        if not finite_vector(scale.get('footprint_m'),2) or min(scale['footprint_m'])<=0: error('FOOTPRINT','scale.footprint_m','Positive dimensions required')
        if not scale.get('notes'): error('SCALE_NOTES','scale.notes','Explain scale anchor and uncertainty')
        scope={}
        for n,d in enumerate(spec['scope']['decisions']):
            path=f'scope.decisions[{n}]'; ident=d.get('id')
            if not ident or ident in scope: error('DUPLICATE_SCOPE',path,'Unique nonempty scope ID required')
            scope[ident]=d
            if d.get('owner') not in ('booth','venue','neighbor','unknown'): error('OWNER',path,'Unknown owner')
            if d.get('decision') not in ('include','exclude','defer'): error('SCOPE_DECISION',path,'Unknown decision')
            if d.get('decision')=='include' and d.get('owner')!='booth': error('NON_BOOTH_INCLUDED',path,'Only confirmed booth components may be built')
            if not d.get('evidence'): error('SCOPE_EVIDENCE',path,'Record the visual or user basis of ownership')
        comps={}
        allowed={'id','scope_id','owner','kind','role','critical','evidence','location','rotation_deg','params','material'}
        for i,c in enumerate(spec['components']):
            path=f'components[{i}]'; ident=c.get('id')
            if not isinstance(ident,str) or not re.fullmatch('[a-z][a-z0-9_]*',ident): error('COMPONENT_ID',path,'Use a stable lowercase identifier')
            if ident in comps: error('DUPLICATE_COMPONENT',path,ident)
            comps[ident]=c
            for k in sorted(allowed-set(c)): error('MISSING_COMPONENT_FIELD',path+'.'+k,'Required field missing')
            for k in sorted(set(c)-allowed): error('UNUSED_COMPONENT_FIELD',path+'.'+k,'Unknown component field')
            decision=scope.get(c.get('scope_id'),{})
            if decision.get('owner')!='booth' or decision.get('decision')!='include' or c.get('owner')!='booth':
                error('SCOPE_BLOCKED',path,'Component does not resolve to a confirmed booth inclusion')
            for key in ('location','rotation_deg'):
                if not finite_vector(c.get(key),3): error('TRANSFORM',path+'.'+key,'Three finite numeric values required')
            ev=c.get('evidence',{})
            if ev.get('status') not in ('observed','inferred'): error('EVIDENCE_STATUS',path,'Use observed or inferred')
            if not ev.get('note'): error('EVIDENCE_NOTE',path,'Document visible basis or hidden-geometry assumption')
            if ev.get('status')=='observed':
                roi=ev.get('roi_xyxy_norm')
                if not finite_vector(roi,4) or not (0<=roi[0]<roi[2]<=1 and 0<=roi[1]<roi[3]<=1): error('OBSERVATION_ROI',path,'Visible components require a valid reference-image ROI')
            if not isinstance(c.get('critical'),bool): error('CRITICAL_FLAG',path,'Boolean required')
            kind=c.get('kind'); params=c.get('params',{})
            if kind not in PARAM_KEYS:
                error('UNSUPPORTED_PRIMITIVE',path,'No box fallback: implement a suitable builder or stop')
                continue
            req,accepted=PARAM_KEYS[kind]
            for k in sorted(req-set(params)): error('MISSING_PARAMETER',path+'.params.'+k,'Required parameter missing')
            for k in sorted(set(params)-accepted): error('UNUSED_PARAMETER',path+'.params.'+k,'Parameter would not drive geometry')
            try:
                if kind=='text':
                    if not isinstance(params['body'],str) or not params['body'].strip(): raise ValueError('text body is empty')
                    positive('size',params['size'])
                    if params.get('extrude',0)<0: raise ValueError('text extrude must be nonnegative')
                else: mesh_for(c)
            except (KeyError,TypeError,ValueError,OverflowError) as ex: error('INVALID_GEOMETRY',path,str(ex))
            mat=c.get('material',{})
            if set(mat)-{'color','roughness','metallic','emission'}: error('UNKNOWN_MATERIAL',path,'Unsupported material field')
            if not finite_vector(mat.get('color'),4) or not all(0<=x<=1 for x in mat['color']): error('MATERIAL_COLOR',path,'RGBA values in [0,1] required')
            for key in ('roughness','metallic'):
                value=mat.get(key,0.5 if key=='roughness' else 0.0)
                if not finite_vector([value],1) or not 0<=value<=1: error('MATERIAL_PARAMETER',path,key)
            val=mat.get('emission',0)
            if not finite_vector([val],1) or val<0: error('MATERIAL_PARAMETER',path,'emission')
        floors=[c for c in comps.values() if c.get('role')=='floor']
        if len(floors)!=1 or floors[0].get('kind')!='box':
            error('FOOTPRINT_GEOMETRY','components','v2.0 requires exactly one rectangular booth-owned floor/carpet component')
        elif any(abs(floors[0]['params']['size'][i]-scale['footprint_m'][i])>1e-6 for i in range(2)):
            error('FOOTPRINT_MISMATCH','scale.footprint_m','Scale metadata must match actual carpet/floor geometry')
        for d in scope.values():
            if d.get('decision')=='include' and not any(c.get('scope_id')==d['id'] for c in comps.values()):
                error('OMITTED_INCLUDED_OBJECT','scope.'+str(d['id']),'Included object has no corresponding geometry')
        for i,r in enumerate(spec['requirements']):
            path=f'requirements[{i}]'; cid=r.get('component_id')
            if cid not in comps: error('MISSING_REQUIRED_COMPONENT',path,str(cid)); continue
            if r.get('kind') is not None and comps[cid]['kind']!=r['kind']: error('WRONG_PRIMITIVE',path,f'{cid} must use {r["kind"]}')
            if r.get('must_be_critical') and not comps[cid]['critical']: error('PRIORITY_DOWNGRADE',path,'Critical structure cannot be downgraded to pass review')
        lmids=set()
        for i,lm in enumerate(spec['landmarks']):
            path=f'landmarks[{i}]'
            if lm.get('id') in lmids: error('DUPLICATE_LANDMARK',path,'Unique IDs required')
            lmids.add(lm.get('id'))
            if lm.get('component_id') not in comps: error('LANDMARK_COMPONENT',path,'Unknown component')
            if not finite_vector(lm.get('local_xyz'),3): error('LANDMARK_3D',path,'Expected a local 3D coordinate')
            if not finite_vector(lm.get('uv'),2) or not all(0<=x<=1 for x in lm['uv']): error('LANDMARK_2D',path,'Use original-image normalized coordinates')
            if lm.get('visibility') not in ('visible','occluded'): error('LANDMARK_VISIBILITY',path,'Explicit visibility required')
            if not isinstance(lm.get('fit'),bool): error('LANDMARK_SPLIT',path,'Mark fit or held-out anchor')
        cam=spec['camera']
        allowed_cam={'projection','position','target','lens_mm','sensor_width_mm','ortho_scale','principal_point','pixel_aspect','fit_status','roll_deg'}
        for key in set(cam)-allowed_cam:error('UNKNOWN_CAMERA_FIELD','camera.'+key,'Unsupported/unused camera parameter')
        for key in ('position','target'):
            if not finite_vector(cam.get(key),3): error('CAMERA_VECTOR','camera.'+key,'Three finite values required')
        if cam.get('position')==cam.get('target'): error('CAMERA_DEGENERATE','camera','Position equals target')
        if cam.get('projection') not in ('perspective','orthographic'): error('CAMERA_PROJECTION','camera','Explicit perspective or orthographic required')
        if cam.get('fit_status') not in ('unfitted','landmark_fitted','reviewed'): error('CAMERA_STATUS','camera.fit_status','Unknown fit state')
        if cam.get('projection')=='perspective':
            positive('lens_mm',cam['lens_mm']); positive('sensor_width_mm',cam['sensor_width_mm'])
        else: positive('ortho_scale',cam['ortho_scale'])
        if not finite_vector(cam.get('principal_point'),2) or not all(0<=x<=1 for x in cam['principal_point']): error('PRINCIPAL_POINT','camera','Expected normalized principal point')
        if not finite_vector([cam.get('roll_deg',0)],1): error('CAMERA_ROLL','camera','Finite roll in degrees required')
        if cam.get('pixel_aspect') != [1,1]: error('PIXEL_ASPECT','camera','v2.0 renderer supports square pixels only')
        for u in spec['uncertainties']:
            if u.get('status') not in ('open','resolved_by_evidence','accepted_by_user'): error('UNCERTAINTY_STATUS','uncertainties','Explicit uncertainty state required')
            if u.get('status')=='open' and u.get('critical'):
                warnings.append({'code':'OPEN_CRITICAL_UNCERTAINTY','id':u.get('id'),'message':u.get('description')})
        quality=spec['quality']
        for k in ('silhouette_iou_min','part_iou_min','landmark_median_max','landmark_p90_max','boundary_distance_max'):
            value=quality.get(k)
            if not finite_vector([value],1) or not 0<value<=1: error('QUALITY_PROFILE','quality.'+k,'Required configurable threshold in (0,1]')
        if not quality.get('threshold_basis'): error('QUALITY_BASIS','quality','Thresholds must be labelled project heuristics, not measured accuracy')
    except (KeyError,TypeError,ValueError,AttributeError,IndexError) as ex:
        error('MALFORMED_SPEC','',str(ex))
    return {'valid':not errors,'errors':errors,'warnings':warnings}


def main():
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--report');p.add_argument('--check-source',action='store_true')
    a=p.parse_args();result=validate(read_json(a.spec),Path(a.spec).parent if a.check_source else None)
    if a.report:write_json(a.report,result)
    import json;print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['valid'] else 2

if __name__=='__main__': raise SystemExit(main())
