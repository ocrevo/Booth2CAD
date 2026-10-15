"""Pictures for the reading step: the image itself, and a copy with a labelled pixel grid (it helps a model read coordinates).

Both are JPEGs of the same size. Large images are scaled down (long edge <= max_edge) to keep the request small; the scale is
returned so coordinates read on the sent picture can be converted back to the original pixels.
"""
from __future__ import annotations
import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                                  # Pillow older than 10.1 has a fixed-size default font
        return ImageFont.load_default()


def grid_step(longest):
    return 50 if longest <= 1000 else 100 if longest <= 2000 else 200


def draw_grid(image):
    out = image.convert('RGB').copy()
    w, h = out.size
    step = grid_step(max(w, h))
    layer = Image.new('RGBA', out.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = _font(max(11, step // 4))
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=(0, 255, 255, 150 if x % (2 * step) == 0 else 90), width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=(0, 255, 255, 150 if y % (2 * step) == 0 else 90), width=1)
    for x in range(0, w, step):
        d.text((x + 2, 1), str(x), fill=(255, 255, 0, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0, 255))
    for y in range(step, h, step):
        d.text((2, y + 1), str(y), fill=(255, 255, 0, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0, 255))
    return Image.alpha_composite(out.convert('RGBA'), layer).convert('RGB')


def _jpeg(image):
    buf = io.BytesIO()
    image.save(buf, 'JPEG', quality=92)
    return buf.getvalue()


def data_url(data, mime='image/jpeg'):
    return f'data:{mime};base64,{base64.b64encode(data).decode("ascii")}'


def prepare_images(path, max_edge=2048):
    """-> {'plain': bytes, 'grid': bytes, 'sent': (w, h), 'original': (w, h), 'scale': original / sent}"""
    with Image.open(Path(path)) as im:
        original = im.size
        rgb = im.convert('RGB')
    longest = max(original)
    if longest > max_edge:
        factor = max_edge / longest
        rgb = rgb.resize((max(1, round(original[0] * factor)), max(1, round(original[1] * factor))), Image.LANCZOS)
    sent = rgb.size
    return {'plain': _jpeg(rgb), 'grid': _jpeg(draw_grid(rgb)), 'sent': sent, 'original': original, 'scale': original[0] / sent[0]}
