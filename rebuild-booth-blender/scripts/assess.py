"""Compute delivery evidence from real run artifacts and reviewed reference masks.
Usage: python scripts/assess.py --spec project/spec.json --run runs/001 \
 --annotations project/annotations.json --review runs/001/visual_review.json
Missing masks/runtime records produce review_required, never an automatic pass.
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path
from common import read_json,write_json,digest,code_hash,file_sha
from compare import load_mask,compare_masks,landmark_metrics
from boothctl import delivery_gate


def assess(spec_path,run_path,annotation_path,review_path):
    spec=read_json(spec_path);run=Path(run_path).resolve();run.mkdir(parents=True,exist_ok=True)
    errors=[];artifacts=[];parts={};metrics={}
    def artifact(role,path):
        p=Path(path)
        if p.is_file():artifacts.append({'role':role,'path':str(p.relative_to(run)),'sha256':file_sha(p)})
    for role,name in [('blend','booth.blend'),('reference_render','reference_render.png'),('inspection_render','inspection_render.png'),('source_reference','source_reference.png')]:
        artifact(role,run/name)
    try:verify=read_json(run/'native_verification.json');artifact('native_verification',run/'native_verification.json')
    except (OSError,ValueError):verify={};errors.append('missing_native_verification')
    if verify.get('spec_sha256')!=digest(spec) or verify.get('builder_sha256')!=code_hash():
        verify={};errors.append('stale_native_verification')
    if (run/'booth.blend').is_file() and verify.get('blend_sha256')!=file_sha(run/'booth.blend'):
        verify={};errors.append('changed_blend_after_verification')
    try:
        build=read_json(run/'build_report.json');artifact('build_report',run/'build_report.json')
        if build.get('spec_sha256')!=digest(spec) or build.get('builder_sha256')!=code_hash():
            raise ValueError('stale_build_report')
        bound={x['path'] for x in build.get('artifacts',[])}
        for name in ('booth.blend','reference_render.png','inspection_render.png','projected_landmarks.json'):
            if name not in bound:raise ValueError('unbound_build_artifact:'+name)
        for item in build['artifacts']:
            p=(run/item['path']).resolve()
            if not p.is_relative_to(run) or not p.is_file() or file_sha(p)!=item['sha256']:
                raise ValueError('changed_build_artifact:'+item['path'])
    except (OSError,ValueError,KeyError) as ex:
        verify={};errors.append('build_provenance:'+str(ex))
    try:annotations=read_json(annotation_path)
    except (OSError,ValueError):annotations={};errors.append('missing_reference_annotations')
    if annotations.get('source_sha256')!=spec['source']['sha256']:
        annotations={};errors.append('annotation_source_mismatch')
    try:review=read_json(review_path)
    except (OSError,ValueError):review={};errors.append('missing_visual_review')
    if review.get('spec_sha256')!=digest(spec) or review.get('builder_sha256')!=code_hash():
        review={};errors.append('stale_visual_review')
    if review:
        for key,name in [('reference_render_sha256','reference_render.png'),('inspection_render_sha256','inspection_render.png')]:
            if not (run/name).is_file() or review.get(key)!=file_sha(run/name):
                review={};errors.append('visual_review_render_mismatch');break
    if review:
        dst=run/'visual_review_evidence.json';write_json(dst,review);artifact('visual_review',dst)
    qa_inputs=run/'qa_inputs';qa_inputs.mkdir(exist_ok=True)
    def ref_path(name):
        src=(Path(annotation_path).parent/name).resolve();dst=qa_inputs/(file_sha(src)[:12]+'_'+src.name)
        if src!=dst:shutil.copy2(src,dst)
        artifact('annotation_mask',dst);return dst
    def measurement(item,candidate):
        r=ref_path(item['mask']);valid=ref_path(item['valid_mask']) if item.get('valid_mask') else None
        artifact('candidate_mask',candidate)
        return compare_masks(load_mask(r),load_mask(candidate),load_mask(valid) if valid else None)
    try:
        m=measurement(annotations['silhouette'],run/'reference_render.png')
        metrics.update(silhouette_iou=m['iou'],boundary_distance_diag=m['symmetric_boundary_distance_diag'])
    except (OSError,ValueError,KeyError) as ex:errors.append('silhouette:'+str(ex))
    for c in spec['components']:
        if not c['critical'] or c['evidence']['status']!='observed':continue
        try:parts[c['id']]=measurement(annotations['parts'][c['id']],run/'part_masks'/(c['id']+'.png'))
        except (OSError,ValueError,KeyError) as ex:errors.append(c['id']+':'+str(ex))
    try:
        projected=read_json(run/'projected_landmarks.json');artifact('projected_landmarks',run/'projected_landmarks.json')
        lm=landmark_metrics(spec['landmarks'],projected,spec['source']['width'],spec['source']['height'])
        metrics.update(landmark_median_diag=lm['median_diag'],landmark_p90_diag=lm['p90_diag'],
                       held_out_anchor_count=lm['held_out_count'],
                       held_out_landmark_median_diag=lm['held_out_median_diag'],
                       held_out_landmark_p90_diag=lm['held_out_p90_diag'])
    except (OSError,ValueError,KeyError) as ex:errors.append('landmarks:'+str(ex))
    evidence={'spec_sha256':digest(spec),'builder_sha256':code_hash(),
              'native_blender_reopened':verify.get('native_blender_reopened',False),
              'geometry_verified':verify.get('geometry_verified',False),
              'artifacts':artifacts,'metrics':metrics,'part_metrics':parts,'visual_review':review,
              'reference_annotation_review':'pass' if annotations.get('review_status')=='pass' and annotations.get('reviewer') else 'pending',
              'collection_errors':errors}
    write_json(run/'quality_evidence.json',evidence)
    result=delivery_gate(spec,evidence,run)
    if errors:result['deliver_as_finished']=False;result['status']='review_required';result['failures']+=errors
    write_json(run/'delivery_gate.json',result);return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--run',required=True)
    p.add_argument('--annotations',required=True);p.add_argument('--review',required=True);a=p.parse_args()
    result=assess(a.spec,a.run,a.annotations,a.review)
    print(result['status']);return 0 if result['deliver_as_finished'] else 2

if __name__=='__main__':raise SystemExit(main())
