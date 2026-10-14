"""Prepare image cases and a local visual comparison report, without model calls.

Sample-specific observations/specs belong in the output directory, never here.
AI renders are comparison candidates, not a source of geometry or BOM evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
import shutil
from pathlib import Path
from urllib.parse import quote
from PIL import Image

IMAGE_EXTENSIONS={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}
CLEAN_PROMPT='''Use case: precise-object-edit.
Asset type: client presentation architectural render of the source exhibition booth.
Input image is the edit target and sole design evidence.
Preserve source camera, framing, main silhouette, proportions, structural openings,
booth-owned floor, furniture counts and positions, screen frames and integrated lighting.
Remove exhibition hall, neighbors, venue lights/trusses, aisle floor, all logos,
text, advertising, watermarks, dimension arrows and people, including screen media.
Use neutral blank screens; keep their sizes and locations. Do not add furniture,
walls, roof panels or support structures. Keep holes and gaps open. Use actual
transparent alpha outside the booth and soft neutral studio illumination.
Do not redesign. Per-case geometry invariants and treatment of loose products
must be added from actual source observation before calling the image model.
'''

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def save(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def relative(path,root):
    try:return Path(os.path.relpath(path,root)).as_posix()
    except ValueError:return Path(path).resolve().as_posix()


def asset_url(path,root):
    """Local HTML can refer to another Windows drive without a relative path."""
    value=relative(path,root)
    return Path(value).as_uri() if Path(value).is_absolute() else quote(value,safe='/.:')

def prepare(input_dir,out,image_path=None):
    out=Path(out).resolve()
    if image_path is not None:
        source=Path(image_path).resolve()
        if not source.is_file() or source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError('image must be an existing supported image file')
        sources=[source]
    else:
        input_dir=Path(input_dir).resolve()
        # Direct children only: previous run outputs cannot become fresh cases.
        sources=sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    if not sources:raise ValueError('No input images found; place source images directly in input-dir')
    if (out/'cases.json').exists():
        try:held=[c['id'] for c in json.loads((out/'cases.json').read_text(encoding='utf-8'))['cases']]
        except (ValueError,KeyError,OSError):held=[]
        raise FileExistsError('Use a fresh output directory; previous cases are retained. '+str(out)+' already holds '+(', '.join(held) or 'a cases.json')+
                              ': keep working from it for the same image, or choose a new output directory.')
    out.mkdir(parents=True,exist_ok=True);cases=[]
    for source in sources:
        digest=sha(source);case_id='case_'+digest[:12];folder=out/case_id;folder.mkdir(exist_ok=True)
        snapshot=folder/('source'+source.suffix.lower())
        if not snapshot.exists():shutil.copy2(source,snapshot)
        if sha(snapshot)!=digest:raise ValueError('Input changed while snapshotting: '+str(source))
        with Image.open(snapshot) as im:width,height=im.size
        (folder/'ai_prompt.txt').write_text(CLEAN_PROMPT,encoding='utf-8')
        cases.append({'id':case_id,'title':source.stem,'source':relative(snapshot,out),
                      'source_original':str(source),'source_sha256':digest,
                      'source_size':[width,height],'baseline':None,'blender':None,'ai':None,
                      'spec':None,'native_verification':None,'notes':[],
                      'status':'observation_and_two_render_routes_pending'})
    manifest={'policy':'booth_only_clean_client_presentation','cases':cases}
    save(out/'cases.json',manifest)
    return manifest

def report(manifest_path,output):
    manifest_path=Path(manifest_path).resolve();root=manifest_path.parent;output=Path(output).resolve()
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'));records=[];sections=[]
    labels=[('source','原始图片'),('baseline','Skill 基线'),('blender','Skill 优化'),('ai','AI 大模型')]
    for case in manifest['cases']:
        if not case.get('source') or not case.get('source_sha256'):raise ValueError('Source path and original hash are required')
        if sha(root/case['source'])!=case['source_sha256']:raise ValueError('Original source changed: '+case['id'])
        assets=[];cards=[]
        for role,label in labels:
            path=case.get(role)
            if not path:raise ValueError('Missing render route: '+case['id']+':'+role)
            path=(root/path).resolve()
            if not path.is_file():raise FileNotFoundError(path)
            with Image.open(path) as im:size=list(im.size)
            url=asset_url(path,output.parent)
            assets.append({'role':role,'path':relative(path,root),'sha256':sha(path),'size':size,
                           'same_dimensions_as_source':size==case.get('source_size')})
            cards.append('<figure><figcaption>'+label+'</figcaption><a href="'+html.escape(url,quote=True)+'">'
                         '<img loading="lazy" src="'+html.escape(url,quote=True)+'" alt="'+html.escape(label)+'"></a>'
                         '<small>'+str(size[0])+' × '+str(size[1])+'</small></figure>')
        links=[]
        for role,label in [('client','客户展示图'),('inspection','第二视角'),('spec','参数与尺寸依据'),('native_verification','Blender重新打开检查'),('blend','可编辑模型')]:
            if case.get(role):
                path=(root/case[role]).resolve()
                if not path.is_file():raise FileNotFoundError(path)
                assets.append({'role':role,'path':relative(path,root),'sha256':sha(path)})
                links.append('<a href="'+html.escape(asset_url(path,output.parent),quote=True)+'">'+label+'</a>')
        notes=''.join('<li>'+html.escape(str(n))+'</li>' for n in case.get('notes',[]))
        sections.append('<section><h2>'+html.escape(case.get('title',case['id']))+'</h2><div class="grid">'+''.join(cards)
                        +'</div><p>'+' · '.join(links)+'</p><ul>'+notes+'</ul><p class="status">'+html.escape(case.get('status','review_required'))+'</p></section>')
        records.append({'id':case['id'],'assets':assets,'status':case.get('status','review_required')})
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Booth2CAD 渲染对比</title><style>
body{font:15px/1.6 system-ui,sans-serif;background:#edf0f3;color:#202b36;margin:0;padding:28px;max-width:1800px;margin:auto}
h1{font-size:26px}h2{font-size:20px}section{background:white;padding:22px;border-radius:12px;margin:24px 0}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}figure{margin:0;min-width:0;background:#e7e9eb;border-radius:8px;overflow:hidden}
figcaption,small{display:block;padding:8px 12px}figcaption{font-weight:600;background:#f5f6f7}img{width:100%;height:350px;object-fit:contain;display:block}
a{color:#145f9b}button{font:inherit;padding:7px 12px;border:1px solid #b2bdc8;border-radius:6px;cursor:pointer}.dark figure{background:#22272d}
.status{font-size:13px;color:#52606e}@media(max-width:1000px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:550px){.grid{grid-template-columns:1fr}}
</style><h1>Booth2CAD：原图、Skill基线、Skill优化、AI大模型</h1>
<p>点击图片查看原尺寸。缩略图只用于视觉比较；不同尺寸/构图的AI图不能直接计算像素相似度。原图是唯一几何证据。</p>
<button onclick="document.body.classList.toggle('dark')">切换深色 / 浅色底，检查透明边缘</button>
'''+''.join(sections)+'</html>'
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(doc,encoding='utf-8')
    save(output.with_suffix('.evidence.json'),{'manifest_sha256':sha(manifest_path),'cases':records,
         'note':'Artifact inventory and human visual comparison only. No inferred fidelity percentage, automatic pass, measured BOM or construction certification.'})
    return {'report':str(output),'cases':len(records)}

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');inputs=p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--input-dir');inputs.add_argument('--image');p.add_argument('--out',required=True)
    p=sub.add_parser('report');p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    args=parser.parse_args()
    result=prepare(args.input_dir,args.out,args.image) if args.command=='prepare' else report(args.manifest,args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
