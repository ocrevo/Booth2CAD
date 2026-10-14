"""One-glance iteration sheet: source | render | 50% blend | silhouette edges + landmark errors.

Requires numpy and Pillow. Visual aid only: it reports landmark reprojection
errors in pixels but no silhouette score, because the source has no reviewed
mask. Works on any run directory written by blender_build.py.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from common import read_json, write_json


def _render_name(run):
    for name in ('preview_render.png', 'reference_render.png'):
        if (run / name).is_file():
            return name
    raise FileNotFoundError('no preview_render.png or reference_render.png in ' + str(run))


def landmark_errors(run, width, height):
    spec = read_json(run / 'spec.json')
    path = run / 'projected_landmarks.json'
    projected = {a['id']: a for a in read_json(path)} if path.is_file() else {}
    rows = []
    for lm in spec.get('landmarks', []):
        p = projected.get(lm['id'])
        if p is None or lm.get('visibility') != 'visible':
            continue
        du = (p['uv'][0] - lm['uv'][0]) * width
        dv = (p['uv'][1] - lm['uv'][1]) * height
        rows.append({'id': lm['id'], 'fit': lm.get('fit', True), 'target_px': [lm['uv'][0] * width, lm['uv'][1] * height],
                     'render_px': [p['uv'][0] * width, p['uv'][1] * height], 'err_px': round(math.hypot(du, dv), 2)})
    return rows


CLIP_LEVEL = 0.98
CLIP_TOLERANCE = 0.05          # share of booth pixels allowed at the top of the range
EV_STEP = 0.5
EV_FLOOR = -2.0


def exposure_advice(luma, clipped_fraction, p95, current_ev):
    """First-order exposure suggestion for the customer image; the display transform is not linear, so preview again."""
    delta = 0.0
    if clipped_fraction > CLIP_TOLERANCE:
        delta = -min(-EV_FLOOR, EV_STEP * math.ceil((clipped_fraction - CLIP_TOLERANCE) / 0.10))
    elif p95 < 0.55:
        delta = EV_STEP
    return {'current_ev': current_ev, 'suggested_delta_ev': delta, 'suggested_client_exposure_ev': round(current_ev + delta, 2)}


def client_look_stats(run, alpha, size):
    path = run / 'preview_client_look.png'
    if not path.is_file():
        return None
    img = Image.open(path).convert('RGB')
    if img.size != size:
        raise ValueError(f'IMAGE_SHAPE_MISMATCH: customer-look preview {img.size} vs source {size}')
    arr = np.asarray(img, dtype=float) / 255.0
    luma = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    inside = luma[alpha]
    if inside.size == 0:
        return None
    clipped = float((inside >= CLIP_LEVEL).mean())
    p95 = float(np.percentile(inside, 95))
    report = run / 'build_report.json'
    try:
        current = float(read_json(report).get('client_exposure_ev', -0.5)) if report.is_file() else -0.5
    except (ValueError, OSError):
        current = -0.5
    return {'clipped_fraction': round(clipped, 4), 'luma_p95': round(p95, 3), 'mean_luma': round(float(inside.mean()), 3),
            'advice': exposure_advice(luma, clipped, p95, current),
            'note': 'Measured on booth pixels of preview_client_look.png. Highlights clip above 5% of booth pixels; '
                    'change --client-exposure and preview again, the display transform is not linear.'}


def sheet(run, render_name=None, out=None):
    run = Path(run).resolve()
    render_name = render_name or _render_name(run)
    src = Image.open(run / 'source_reference.png').convert('RGB')
    rgba = Image.open(run / render_name).convert('RGBA')
    if rgba.size != src.size:
        raise ValueError(f'IMAGE_SHAPE_MISMATCH: render {rgba.size} vs source {src.size}; previews use the source canvas')
    gray = Image.new('RGBA', src.size, (128, 128, 128, 255))
    gray.alpha_composite(rgba)
    flat = gray.convert('RGB')
    blend = Image.blend(src, flat, 0.5)
    alpha = np.asarray(rgba.getchannel('A')) > 127
    edge = alpha ^ np.pad(alpha, 1, mode='edge')[1:-1, :-2] | alpha ^ np.pad(alpha, 1, mode='edge')[:-2, 1:-1]
    # Interior colour edges add the inner structure (counter tops, fins) to the outline.
    lum = np.asarray(flat.convert('L'), dtype=float)
    grad = np.zeros_like(lum)
    grad[:, 1:] = np.abs(np.diff(lum, axis=1))
    grad[1:, :] = np.maximum(grad[1:, :], np.abs(np.diff(lum, axis=0)))
    inner = (grad > 28) & alpha
    edges = np.asarray(src).copy()
    edges[inner] = (255, 220, 0)
    edges[edge] = (0, 255, 255)
    edges_im = Image.fromarray(edges)
    rows = landmark_errors(run, src.width, src.height)
    d = ImageDraw.Draw(edges_im)
    for r in rows:
        (tx, ty), (rx, ry) = r['target_px'], r['render_px']
        d.line([(tx, ty), (rx, ry)], fill=(255, 0, 0), width=1)
        d.ellipse([tx - 3, ty - 3, tx + 3, ty + 3], outline=(0, 255, 0))
        d.line([(rx - 3, ry - 3), (rx + 3, ry + 3)], fill=(255, 0, 0)); d.line([(rx - 3, ry + 3), (rx + 3, ry - 3)], fill=(255, 0, 0))
    w, h = src.size
    canvas = Image.new('RGB', (w * 2, h * 2), (0, 0, 0))
    for im, xy in ((src, (0, 0)), (flat, (w, 0)), (blend, (0, h)), (edges_im, (w, h))):
        canvas.paste(im, xy)
    out = Path(out) if out else run / 'compare_sheet.png'
    canvas.save(out)
    look = client_look_stats(run, alpha, src.size)
    errs = [r['err_px'] for r in rows]
    fit_errs = [r['err_px'] for r in rows if r['fit']]
    check_errs = [r['err_px'] for r in rows if not r['fit']]
    summary = {'sheet': str(out), 'render': render_name, 'landmarks': rows,
               'landmark_median_px': float(np.median(errs)) if errs else None,
               'landmark_max_px': float(max(errs)) if errs else None,
               'landmark_median_fit_px': float(np.median(fit_errs)) if fit_errs else None,
               'landmark_median_check_px': float(np.median(check_errs)) if check_errs else None,
               'landmark_check_count': len(check_errs),
               'landmark_note': 'Fit landmarks drive the camera, so their error is circular; judge the render by the independent check landmarks (fit=false).',
               'booth_pixel_fraction': round(float(alpha.mean()), 4), 'client_look': look,
               'note': 'Panels: source | render on gray | 50% blend | source with render outline (cyan), inner edges (yellow), '
                       'landmark target (green) vs render (red). Visual aid only, no fidelity score.'}
    write_json(run / 'compare.json', summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--run', required=True)
    p.add_argument('--render')
    p.add_argument('--out')
    a = p.parse_args()
    s = sheet(a.run, a.render, a.out)
    print(json.dumps({k: s[k] for k in ('sheet', 'render', 'landmark_median_px', 'landmark_max_px')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
