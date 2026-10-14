"""Project spec script template: copy to output/<job>/build_spec.py and fill in.

    python output/<job>/build_spec.py output/<job>/spec_work

Inputs from earlier steps (all in output/<job>/):
  box_fit.json  - written by scripts/box_fit.py (camera, image size, W/D/H, free values)
  benchmark/<case>/source.* - input snapshot written by benchmark.py prepare

Every number below is a placeholder. Pixel positions are given as fractions of the
canvas (fx, fy) so the template stays resolution independent: replace them with
what this image shows. Fall back to references/design-priors.md only for what the
image cannot tell, and record that in uncertainties. Delete macros the booth does
not have. Set BOOTH_SKILL to the skill folder if the job does not live under the
same project root as rebuild-booth-blender.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = (Path(os.environ['BOOTH_SKILL']) if os.environ.get('BOOTH_SKILL')
         else next(p / 'rebuild-booth-blender' for p in HERE.parents if (p / 'rebuild-booth-blender').is_dir()))
sys.path.insert(0, str(SKILL / 'scripts'))
import camera_math as cmath  # noqa: E402
import components as cm      # noqa: E402
from PIL import Image        # noqa: E402

SOURCE = next((HERE / 'benchmark').glob('case_*/source.*'))
FIT = json.loads((HERE / 'box_fit.json').read_text(encoding='utf-8'))
CAM, DIMS = FIT['camera'], FIT['dims_m']
IMG_W, IMG_H = FIT['image']['width'], FIT['image']['height']
with Image.open(SOURCE) as _im:
    assert _im.size == (IMG_W, IMG_H), f'box_fit.json is for {IMG_W}x{IMG_H} but the snapshot is {_im.size}'
W, D, H = DIMS['W'], DIMS['D'], DIMS['H']
X0, X1, Y0, Y1 = -W / 2, W / 2, -D / 2, D / 2
ZF = FIT.get('floor_z', 0.0)    # walking surface (platform top); the floor slab sits below it
FLOOR_T = 0.10                  # slab thickness placeholder


def px(fx0, fy0, fx1, fy1):
    """Canvas fractions -> pixel ROI box."""
    return (fx0 * IMG_W, fy0 * IMG_H, fx1 * IMG_W, fy1 * IMG_H)


def pt(fx, fy):
    return fx * IMG_W, fy * IMG_H


def on_wall_y(top_left, bottom_right, y):
    """Pixel corners of something flat on a wall facing -Y -> ((x0, x1), (z0, z1))."""
    return cmath.rect_on_plane(top_left, bottom_right, CAM, IMG_W, IMG_H, 'y', y)


def floor_xy(fx, fy, z=ZF):
    p = cmath.floor_point(*pt(fx, fy), CAM, IMG_W, IMG_H, z)
    return round(p[0], 3), round(p[1], 3)


b = cm.SpecBuilder(SOURCE, IMG_W, IMG_H, project_id='job_id_here')

# ---- scope: what is built, what is removed (default clean customer render)
b.scope('booth_floor', 'Visible floor/platform of the booth.')
b.scope('shell', 'Booth-owned walls, headers and roof elements.')
b.scope('furniture', 'Booth-owned counters, tables, chairs and planters.')
b.scope('media', 'Screens kept with neutral content.')
b.exclude('venue', 'Hall, aisle floor, neighbours and backdrop are not booth geometry.')
b.exclude('brand_text', 'Logos, lettering, captions and watermarks removed; carriers kept.', owner='booth')

# ---- L1 floor (exactly one role=floor box matching the footprint)
b.box('floor', 'booth_floor', 'floor', (X0, X1), (Y0, Y1), (ZF - FLOOR_T, ZF), cm.WOOD, critical=True, px=px(0, 0.5, 1, 1))

# ---- L2 walls (examples: back wall and one side wall)
b.box('back_wall', 'shell', 'back_wall', (X0, X1), (Y1 - 0.1, Y1), (ZF, H), cm.WHITE, critical=True, px=px(0.2, 0, 0.9, 0.6))
b.box('left_wall', 'shell', 'end_wall', (X0, X0 + 0.1), (Y0, Y1 - 0.1), (ZF, H), cm.WHITE, critical=True, px=px(0.05, 0.1, 0.3, 0.7))

# ---- L4 cabinetry / L6 media / L9 furnishing via macros (positions from floor_xy / on_wall_y)
cm.counter(b, 'reception', 'furniture', (-1.5, -0.3), (Y0 + 0.3, Y0 + 0.85), floor_z=ZF, top_color=[0.9, 0.2, 0.3, 1],
           px=px(0.25, 0.55, 0.4, 0.8))
tx, ty = floor_xy(0.5, 0.65)
cm.round_table(b, 'table_a', 'furniture', tx, ty, floor_z=ZF, px=px(0.48, 0.55, 0.54, 0.65))
cm.shell_chair(b, 'chair_a', 'furniture', tx + 0.6, ty, 90, floor_z=ZF, px=px(0.54, 0.5, 0.6, 0.65))
fx, fz = on_wall_y(pt(0.5, 0.34), pt(0.66, 0.5), Y1 - 0.1)
cm.wall_screens(b, 'screens', 'media', Y1 - 0.1, (fx, fz), [((fx[0] + 0.05, fx[1] - 0.05), (fz[0] + 0.05, fz[1] - 0.05))],
                px=px(0.5, 0.34, 0.66, 0.5))

# ---- camera, landmarks (fit corners double as reprojection checks), assumptions
b.camera(CAM)
b.landmark('top_back_left', 'back_wall', [X0, Y1, H], pt(0.3, 0.05))
anchors = ', '.join(f'{k}={v}' for k, v in DIMS.items() if FIT['dim_source'].get(k) != 'fitted') or 'numeric point anchors'
assumed = ', '.join(FIT.get('assumed') or []) or 'none listed'
b.scale((W, D), f'Proportions from box_fit.json corner fit; absolute size from {anchors}. Assumed items: {assumed}. Not measured.')
b.uncertain('metric_dimensions', 'Single-image estimate; confirm before any BOM or construction use.')

if __name__ == '__main__':
    out = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / 'spec_work')
    spec = b.write(out / 'spec.json')
    print(out / 'spec.json', len(spec['components']), 'components')
