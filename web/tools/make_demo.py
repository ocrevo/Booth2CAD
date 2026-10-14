"""Build the synthetic demo booth for the web editor: web/app/demo/demo-booth.spec.json (+ demo_source.png).

Everything here is invented for testing the editor (a generic 6 x 5 m open-front stand made from the skill's macros);
no client image, brand, or measured dimension is involved. Re-run after changing the macros:

    python web/tools/make_demo.py
"""
from __future__ import annotations
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'app' / 'demo'      # the deployable site folder; tools/ and tests/ are not served
sys.path.insert(0, str(HERE.parents[1] / 'booth-image-to-model' / 'scripts'))
import components as cm  # noqa: E402

ZF = 0.1                     # platform top
W, H = 960, 600              # placeholder "source" frame; only its aspect matters to the editor


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / 'demo_source.png'
    img = Image.new('RGB', (W, H), (214, 218, 222))
    ImageDraw.Draw(img).text((24, 24), 'synthetic demo - not a real booth photo', fill=(90, 96, 104))
    img.save(src)

    b = cm.SpecBuilder(str(src), W, H, 'web_editor_demo')
    b.source['image'] = src.name            # relative to the spec, so the folder can move
    for sid, why in (('shell', 'Synthetic platform, back wall, header and screens.'),
                     ('media', 'Synthetic wall screens.'),
                     ('furniture', 'Synthetic counter, tables, chairs and planter.'),
                     ('lighting', 'Synthetic spotlight bodies.')):
        b.scope(sid, why)

    b.box('floor', 'shell', 'floor', (-3.0, 3.0), (-2.5, 2.5), (0.0, ZF), cm.WOOD, critical=True, inferred=True,
          note='Synthetic platform.')
    b.box('back_wall', 'shell', 'back_wall', (-3.0, 3.0), (2.4, 2.5), (ZF, 3.0), cm.WHITE, critical=True, inferred=True,
          note='Synthetic back wall.')
    cm.louvre_wall(b, 'louvres', 'shell', (-1.6, 1.4), (2.78, 2.9), (ZF, 2.6), 8, 0.08, [0.55, 0.40, 0.28, 1], along='y',
                   inferred=True)
    cm.header_band(b, 'header', 'shell', [(-2.6, 1.9), (-2.6, -2.1), (2.6, -2.1), (2.6, 1.9)], 0.4, (2.5, 3.1),
                   posts=[(-2.6, -2.1), (2.6, -2.1)], floor_z=ZF, inferred=True)
    cm.tv(b, 'tv', 'media', 2.4, -2.0, 55, bezel=0.02, depth=0.05, inferred=True)
    cm.led_wall(b, 'led', 'media', 2.4, -1.0, 0.7, cols=4, rows=3, module=0.5, depth=0.12, inferred=True)
    cm.spotlights(b, 'spot', 'lighting', [(-1.5, -2.1), (0.0, -2.1), (1.5, -2.1)], 2.5, inferred=True)
    cm.counter(b, 'counter', 'furniture', (-0.9, 0.9), (-1.9, -1.35), floor_z=ZF, inferred=True)
    for name, tx in (('table_a', 1.7), ('table_b', -1.7)):
        cm.round_table(b, name, 'furniture', tx, 0.3, floor_z=ZF, inferred=True)
    for name, cx, cy, yaw in (('chair_a1', 2.4, 0.3, 90), ('chair_a2', 1.0, 0.3, -90),
                              ('chair_b1', -1.0, 0.3, 90), ('chair_b2', -2.4, 0.3, -90)):
        cm.shell_chair(b, name, 'furniture', cx, cy, yaw, floor_z=ZF, inferred=True)
    cm.planter(b, 'planter', 'furniture', (2.2, 2.8), (-2.0, -1.4), floor_z=ZF, color=cm.WHITE, inferred=True)

    b.scale((6.0, 5.0), 'Synthetic dimensions invented for the editor demo; not measured from anything.')
    b.camera({'projection': 'perspective', 'position': [7.5, -9.0, 4.8], 'target': [0.0, 0.0, 1.2], 'lens_mm': 36.0,
              'sensor_width_mm': 36.0, 'principal_point': [0.5, 0.5], 'pixel_aspect': [1, 1],
              'fit_status': 'unfitted', 'roll_deg': 0.0})
    b.uncertain('synthetic_demo', 'Everything in this file is synthetic test content.')
    b.write(OUT / 'demo-booth.spec.json')
    print('wrote', OUT / 'demo-booth.spec.json')


if __name__ == '__main__':
    main()
