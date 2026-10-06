"""
make-icon -- render the mark to a Windows .ico for the notebook app.

The mark is two cubic Bezier paths in a 100-unit em (see README.md: fitted to the
mean skeleton of 14 OFL-licensed faces, so nothing here is licensed from anyone).
Two paths is few enough that flattening them by hand beats taking on an SVG
rendering dependency for one asset.

Uses yoneda-mark-bold.svg, stroke 12, which exists precisely for small sizes. The
regular stroke-9 mark closes up and turns to mud at 16px.

    py make-icon.py ../yoneda-notebook/assets/yoneda.ico

Needs Pillow, which is a build-time tool and never a dependency of the notebook.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SVG = HERE / "yoneda-mark-bold.svg"

INK = (26, 26, 25, 255)        # --ink from the site
PAPER = (246, 244, 239, 255)   # --paper from the site
SIZES = [256, 128, 64, 48, 32, 16]
SS = 8                         # supersample factor; downsampling is the antialiasing
MARGIN = 0.13                  # fraction of the canvas left clear on every side
CORNER = 0.20                  # rounded-square radius, fraction of canvas


def cubic(p0, p1, p2, p3, n=400):
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        yield (u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0],
               u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1])


def parse_paths(svg: str) -> tuple[list[list[tuple[float, float]]], float]:
    """Flatten every 'M x y C ...' path into a polyline. Returns (paths, stroke)."""
    stroke = float(re.search(r'stroke-width="([\d.]+)"', svg).group(1))
    polys = []
    for d in re.findall(r'\sd="([^"]+)"', svg):
        nums = [float(x) for x in re.findall(r'-?\d+\.?\d*', d)]
        pts = [(nums[0], nums[1])]
        rest = nums[2:]
        # Every C segment is three points; the current point is the fourth.
        for i in range(0, len(rest) - 5, 6):
            c1 = (rest[i], rest[i+1])
            c2 = (rest[i+2], rest[i+3])
            end = (rest[i+4], rest[i+5])
            pts.extend(list(cubic(pts[-1], c1, c2, end))[1:])
        polys.append(pts)
    return polys, stroke


def render(size: int) -> Image.Image:
    polys, stroke = parse_paths(SVG.read_text(encoding="utf-8"))
    n = size * SS

    # Fit the INKED bounds, not the viewBox: the mark's stroke overflows its own
    # 100-unit box, so fitting the box alone clips the terminals.
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    x0, x1 = min(xs) - stroke/2, max(xs) + stroke/2
    y0, y1 = min(ys) - stroke/2, max(ys) + stroke/2

    avail = n * (1 - 2*MARGIN)
    scale = avail / max(x1 - x0, y1 - y0)
    # Centre whichever axis is the shorter one.
    ox = (n - (x1 - x0) * scale) / 2 - x0 * scale
    oy = (n - (y1 - y0) * scale) / 2 - y0 * scale

    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = n * CORNER
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=r, fill=PAPER)

    # Stamp a disc at every sampled point rather than stroking a polyline. PIL
    # draws a thick line as a rectangle per segment, which scallops the outside
    # of a curve and leaves the terminals square -- visibly wrong for a mark whose
    # whole character is a round brush. Discs give round caps and round joins for
    # free, and the samples are far denser than the radius, so the trail is solid.
    rad = stroke * scale / 2
    for poly in polys:
        for px, py in ((p[0]*scale + ox, p[1]*scale + oy) for p in poly):
            d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=INK)

    return img.resize((size, size), Image.LANCZOS)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__.strip().splitlines()[-4].strip(), file=sys.stderr)
        return 2
    out = Path(args[0])
    out.parent.mkdir(parents=True, exist_ok=True)

    frames = [render(s) for s in SIZES]
    # Largest first, with the rest passed as sizes so one file serves every slot
    # Windows asks for, from the 16px taskbar to the 256px Explorer tile.
    frames[0].save(out, format="ICO",
                   sizes=[(s, s) for s in SIZES],
                   append_images=frames[1:])
    print(f"wrote {out}  ({out.stat().st_size:,} bytes, sizes {SIZES})")

    preview = out.with_suffix(".preview.png")
    frames[0].save(preview)
    print(f"preview {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
