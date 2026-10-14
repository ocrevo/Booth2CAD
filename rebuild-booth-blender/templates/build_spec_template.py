"""Project spec script template: copy to output/<job>/build_spec.py and fill in.

    python output/<job>/build_spec.py output/<job>/spec_work

Inputs from earlier steps (all in output/<job>/):
  box_fit.json  - written by scripts/box_fit.py (camera, W/D/H, free values)
  benchmark/<case>/source.jpg - input snapshot written by benchmark.py prepare

Every number below is a placeholder. Replace it with what this image shows;
fall back to references/design-priors.md only for what the image cannot tell,
and record that in uncertainties. Delete macros the booth does not have.
"""
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / 'rebuild-booth-blender'   # adjust if the job lives elsewhere
sys.path.insert(0, str(SKILL / 'scripts'))
import camera_math as cmath  # noqa: E402
import components as cm      # noqa: E402

HERE = Path(__file__).resolve().parent
SOURCE = next((HERE / 'benchmark').glob('case_*/source.*'))
FIT = json.loads((HERE / 'box_fit.json').read_text(encoding='utf-8'))
CAM, DIMS = FIT['camera'], FIT['dims_m']
W, D, H = DIMS['W'], DIMS['D'], DIMS['H']
X0, X1, Y0, Y1 = -W / 2, W / 2, -D / 2, D / 2
ZF = 0.10                     # walking surface (platform top); placeholder
IMG_W, IMG_H = 738, 415       # source canvas; must match the snapshot


def on_wall_y(top_left, bottom_right, y):
    """Pixel corners of something flat on a wall facing -Y -> ((x0, x1), (z0, z1))."""
    return cmath.rect_on_plane(top_left, bottom_right, CAM, IMG_W, IMG_H, 'y', y)


def floor_xy(px, py, z=ZF):
    p = cmath.floor_point(px, py, CAM, IMG_W, IMG_H, z)
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
b.box('floor', 'booth_floor', 'floor', (X0, X1), (Y0, Y1), (0, ZF), cm.WOOD, critical=True, px=(0, 200, 738, 415))

# ---- L2 walls (examples: back wall and one side wall)
b.box('back_wall', 'shell', 'back_wall', (X0, X1), (Y1 - 0.1, Y1), (ZF, H), cm.WHITE, critical=True, px=(150, 0, 650, 250))
b.box('left_wall', 'shell', 'end_wall', (X0, X0 + 0.1), (Y0, Y1 - 0.1), (ZF, H), cm.WHITE, critical=True, px=(50, 50, 220, 270))

# ---- L4 cabinetry / L6 media / L9 furnishing via macros (positions from floor_xy / on_wall_y)
cm.counter(b, 'reception', 'furniture', (-1.5, -0.3), (Y0 + 0.3, Y0 + 0.85), floor_z=ZF, top_color=[0.9, 0.2, 0.3, 1],
           px=(200, 240, 300, 330))
tx, ty = floor_xy(380, 260)
cm.round_table(b, 'table_a', 'furniture', tx, ty, floor_z=ZF, px=(360, 230, 400, 260))
cm.shell_chair(b, 'chair_a', 'furniture', tx + 0.6, ty, 90, floor_z=ZF, px=(400, 220, 430, 270))
fx, fz = on_wall_y((380, 140), (490, 210), Y1 - 0.1)
cm.wall_screens(b, 'screens', 'media', Y1 - 0.1, (fx, fz), [((fx[0] + 0.05, fx[1] - 0.05), (fz[0] + 0.05, fz[1] - 0.05))],
                px=(380, 140, 490, 210))

# ---- camera, landmarks (fit corners double as reprojection checks), assumptions
b.camera(CAM)
b.landmark('top_back_left', 'back_wall', [X0, Y1, H], (237, 3))
b.scale((W, D), 'Proportions from box_fit.json corner fit; absolute size from '
        + ', '.join(f'{k}={v}' for k, v in DIMS.items() if FIT['dim_source'].get(k) != 'fitted') + '. Not measured.')
b.uncertain('metric_dimensions', 'Single-image estimate; confirm before any BOM or construction use.')

if __name__ == '__main__':
    out = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / 'spec_work')
    spec = b.write(out / 'spec.json')
    print(out / 'spec.json', len(spec['components']), 'components')
