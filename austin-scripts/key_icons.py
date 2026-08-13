#!/usr/bin/env python3
"""Key the magenta background out of rig-generated icons -> RGBA PNGs.

Samples the actual background color from the image corners (Chroma's
"magenta" varies), converts pixels near it to transparency with a soft
edge, despills magenta fringe, crops to content, pads square.
"""
import sys
from pathlib import Path
from PIL import Image

THRESHOLD = 70   # distance where alpha starts
SOFT = 60        # fade range above threshold


def key_out(path, out_path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    # background = average of the four 8x8 corner patches
    samples = []
    for cx, cy in [(4, 4), (w - 5, 4), (4, h - 5), (w - 5, h - 5)]:
        for dx in range(-4, 4):
            for dy in range(-4, 4):
                samples.append(px[cx + dx, cy + dy])
    bg = tuple(sum(c[i] for c in samples) // len(samples) for i in range(3))

    out = Image.new("RGBA", (w, h))
    opx = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            dist = ((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2) ** 0.5
            if dist <= THRESHOLD:
                a = 0
            elif dist >= THRESHOLD + SOFT:
                a = 255
            else:
                a = int(255 * (dist - THRESHOLD) / SOFT)
            if a > 0:
                # despill: pull the magenta cast out of edge pixels
                if a < 255 and g < min(r, b):
                    m = (r + b) // 2
                    r, b = (r + g) // 2 + (r - m) // 2, (b + g) // 2 + (b - m) // 2
                opx[x, y] = (r, g, b, a)
            else:
                opx[x, y] = (0, 0, 0, 0)

    bbox = out.getbbox()
    out = out.crop(bbox)
    # pad to square with 4% margin
    side = int(max(out.size) * 1.08)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(out, ((side - out.width) // 2, (side - out.height) // 2), out)
    canvas.save(out_path)
    print(f"{Path(path).name}: bg={bg} -> {out_path} {canvas.size}")


for f in sys.argv[1:]:
    p = Path(f)
    name = p.stem.replace("icon-", "").split("_")[0]
    key_out(p, p.parent / f"{name}.png")
