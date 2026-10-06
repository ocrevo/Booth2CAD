"""Small deterministic CLI: runtime probe, guarded edits, fingerprints, delivery gate.
Does not make model-provider calls or claim to install a hosted ChatGPT Skill.
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from common import read_json,write_json,digest,file_sha,code_hash,fingerprints,cache_valid
from validate_spec import validate


def doctor(blender=None):
    candidate=blender or shutil.which('blender')
    result={'python':sys.version.split()[0],'blender_path':candidate,'blender_available':False,
            'dependencies':{k:importlib.util.find_spec(k) is not None for k in ('numpy','PIL','scipy')},
            'hosted_skill_updated':False}
    if candidate:
        try:
            p=subprocess.run([candidate,'--version'],capture_output=True,text=True,timeout=20,check=False)
            result['blender_available']=p.returncode==0
            result['blender_version']=p.stdout.splitlines()[0] if p.stdout else p.stderr[:200]
        except (OSError,subprocess.SubprocessError) as ex:result['blender_error']=str(ex)
    result['status']='ready_for_build' if result['blender_available'] else 'blocked_native_blender'
    return result


def patch_component(spec, ident, field, value):
    """Allow only real, existing geometry/appearance fields. Metadata cannot be
    edited through this shortcut to bypass scope/evidence/quality obligations."""
    allowed_roots={'params','location','rotation_deg','material'}
    keys=field.split('.')
    if keys[0] not in allowed_roots or any(k.startswith('_') for k in keys):
        raise ValueError('PROTECTED_PATCH: scope, source, evidence, IDs and quality require explicit re-review')
    out=copy.deepcopy(spec);matches=[c for c in out['components'] if c['id']==ident]
    if len(matches)!=1:raise ValueError('Unknown or duplicate component ID: '+ident)
    dest=matches[0]
    for key in keys[:-1]:
        if not isinstance(dest,dict) or key not in dest:raise ValueError('Patch path does not exist')
        dest=dest[key]
    if not isinstance(dest,dict) or keys[-1] not in dest:raise ValueError('Patch path does not exist; no silently unused parameters')
    dest[keys[-1]]=value
    if keys[0] in ('params','location','rotation_deg'):out['camera']['fit_status']='unfitted'
    result=validate(out)
    if not result['valid']:raise ValueError('PATCH_REJECTED: '+json.dumps(result['errors'],ensure_ascii=False))
    old,new=fingerprints(spec),fingerprints(out)
    return out,{'component_id':ident,'field':field,'invalidated_stages':[k for k in old if old[k]!=new[k]],
                'before_sha256':digest(spec),'after_sha256':digest(out)}


def delivery_gate(spec, evidence, root):
    """Evidence-based gate, not a numerical aesthetic score. Missing proof fails.
    An unsigned reviewer record documents a review, not cryptographic attestation.
    """
    failures=[];root=Path(root).resolve();validation=validate(spec)
    if not validation['valid']:failures.append('invalid_spec')
    if evidence.get('spec_sha256')!=digest(spec):failures.append('stale_or_missing_spec_hash')
    if evidence.get('builder_sha256')!=code_hash():failures.append('stale_or_missing_builder_hash')
    if evidence.get('native_blender_reopened') is not True:failures.append('native_blend_not_reopened')
    if evidence.get('geometry_verified') is not True:failures.append('actual_geometry_not_verified')
    artifacts=evidence.get('artifacts',[]);roles=[]
    if not artifacts:failures.append('missing_artifacts')
    for a in artifacts:
        role=a.get('role');roles.append(role)
        p=(root/a.get('path','')).resolve()
        if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size==0:
            failures.append('missing_or_unsafe_artifact:'+str(role));continue
        if file_sha(p)!=a.get('sha256'):failures.append('artifact_hash_mismatch:'+str(role))
    for role in ('blend','reference_render','inspection_render','source_reference'):
        if role not in roles:failures.append('missing_role:'+role)
    if spec.get('camera',{}).get('fit_status')!='reviewed':failures.append('camera_not_reviewed')
    for u in spec.get('uncertainties',[]):
        if u.get('critical') and u.get('status')=='open':failures.append('open_critical_uncertainty:'+u['id'])
    metric=evidence.get('metrics',{});q=spec.get('quality',{})
    checks=(('silhouette_iou','silhouette_iou_min',True),('boundary_distance_diag','boundary_distance_max',False),
            ('landmark_median_diag','landmark_median_max',False),('landmark_p90_diag','landmark_p90_max',False))
    for key,threshold,is_min in checks:
        val=metric.get(key);limit=q.get(threshold)
        if not isinstance(val,(float,int)) or isinstance(val,bool) or not 0<=val<=1 or limit is None:
            failures.append('missing_or_invalid_metric:'+key)
        elif (val<limit if is_min else val>limit):failures.append('metric_failed:'+key)
    if metric.get('held_out_anchor_count',0)<2:failures.append('missing_held_out_anchors')
    for c in spec.get('components',[]):
        if c.get('critical') and c.get('evidence',{}).get('status')=='observed':
            pm=evidence.get('part_metrics',{}).get(c['id'],{})
            if isinstance(pm.get('iou'),bool) or not isinstance(pm.get('iou'),(float,int)) or not q.get('part_iou_min',1)<=pm['iou']<=1:
                failures.append('critical_part_metric_failed:'+c['id'])
    review=evidence.get('visual_review',{})
    for key in ('topology','ownership','layout','alternate_view','appearance'):
        if review.get(key)!='pass':failures.append('visual_review_not_passed:'+key)
    if not review.get('reviewer') or not review.get('notes'):failures.append('missing_visual_review_record')
    # Mask correctness is independently reviewed, not inferred from mask IoU.
    if evidence.get('reference_annotation_review')!='pass':failures.append('unreviewed_reference_annotations')
    return {'status':'review_required' if failures else 'verified_visual_reconstruction',
            'deliver_as_finished':not failures,'failures':failures,
            'note':'Only visual reconstruction; no inference of measured dimensions or engineering certification.'}


def main():
    p=argparse.ArgumentParser();sp=p.add_subparsers(dest='command',required=True)
    s=sp.add_parser('doctor');s.add_argument('--blender');s.add_argument('--output')
    s=sp.add_parser('fingerprint');s.add_argument('--spec',required=True);s.add_argument('--output')
    s=sp.add_parser('patch');s.add_argument('--spec',required=True);s.add_argument('--component',required=True);s.add_argument('--field',required=True);s.add_argument('--value',required=True);s.add_argument('--output',required=True)
    s=sp.add_parser('gate');s.add_argument('--spec',required=True);s.add_argument('--evidence',required=True);s.add_argument('--root',required=True);s.add_argument('--output',required=True)
    a=p.parse_args()
    try:
        if a.command=='doctor':result=doctor(a.blender)
        elif a.command=='fingerprint':result=fingerprints(read_json(a.spec))
        elif a.command=='patch':
            spec,result=patch_component(read_json(a.spec),a.component,a.field,json.loads(a.value));write_json(a.output,spec)
            write_json(str(a.output)+'.patch.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        else:result=delivery_gate(read_json(a.spec),read_json(a.evidence),a.root)
        if getattr(a,'output',None):write_json(a.output,result)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get('status') in ('review_required','blocked_native_blender') else 0
    except (ValueError,KeyError,OSError) as ex:print(str(ex),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
