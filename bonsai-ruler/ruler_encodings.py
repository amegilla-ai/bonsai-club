#!/usr/bin/env python3
"""Render ruler-scale swatches in several encodings for VLM-readability testing.

Each swatch shows a short vertical scale segment (a window of cm values) with a
simulated OBJECT EDGE drawn across it at a known sub-cm position. The VLM is
later asked where the edge falls; we score against the known truth.

Encodings (each is a function returning SVG element strings for one cm line):
  decimal        - plain cm number (baseline)
  decimal_color  - cm number, colour encodes the tens digit
  hierarchy      - 5cm numbers big/bold, others small
  binary         - cm value as filled/empty bit blocks
  gray           - gray code blocks (neighbours differ by one bit)
  color_base     - 2-3 coloured cells encoding value in base-N
  letter_tens    - letter for tens (A/B/C/D/E) + units digit, e.g. B7 = 17

All encodings share the same geometry so only the marking differs.
"""

# geometry (mm, top-origin SVG)
CM = 14.0                  # px-mm per cm in the swatch (bigger than print, for VLM clarity)
MARGIN = 16.0
BAR_X = 70.0
BAR_W = 34.0
BAR_LEFT = BAR_X - BAR_W / 2
BAR_RIGHT = BAR_X + BAR_W / 2
FONT = "DejaVu Sans, Arial, sans-serif"

TENS_COLORS = ["#d11", "#16c", "#2a2", "#e80", "#92c"]   # 0s,10s,20s,30s,40s
BASE_COLORS = ["#d11", "#16c", "#2a2", "#e80", "#92c", "#0aa", "#c39", "#555"]


def y_for(cm, lo, n):
    """y for a cm line; lo at bottom, n cm tall window."""
    return MARGIN + (n - (cm - lo)) * CM


# ---- per-line markers -------------------------------------------------------

def m_decimal(cm, x, y):
    return (f'<text x="{x:.1f}" y="{y+CM*0.34:.1f}" font-family="{FONT}" '
            f'font-size="{CM*0.72:.1f}" font-weight="700" text-anchor="end" '
            f'fill="#000">{cm}</text>')


def m_decimal_color(cm, x, y):
    col = TENS_COLORS[(cm // 10) % len(TENS_COLORS)]
    return (f'<text x="{x:.1f}" y="{y+CM*0.34:.1f}" font-family="{FONT}" '
            f'font-size="{CM*0.72:.1f}" font-weight="800" text-anchor="end" '
            f'fill="{col}">{cm}</text>')


def m_hierarchy(cm, x, y):
    big = cm % 5 == 0
    size = CM * 0.95 if big else CM * 0.5
    w = 800 if big else 600
    return (f'<text x="{x:.1f}" y="{y+size*0.34:.1f}" font-family="{FONT}" '
            f'font-size="{size:.1f}" font-weight="{w}" text-anchor="end" '
            f'fill="#000">{cm}</text>')


def _bits(val, nbits):
    return [(val >> (nbits - 1 - i)) & 1 for i in range(nbits)]


def _bit_blocks(bits, x, y):
    cell = CM * 0.7
    gap = 1.0
    out = []
    total_w = len(bits) * (cell + gap)
    x0 = x - total_w
    for i, b in enumerate(bits):
        cx = x0 + i * (cell + gap)
        fill = "#000" if b else "#fff"
        out.append(f'<rect x="{cx:.1f}" y="{y-cell/2:.1f}" width="{cell:.1f}" '
                   f'height="{cell:.1f}" fill="{fill}" stroke="#000" '
                   f'stroke-width="0.4"/>')
    return "".join(out)


def m_binary(cm, x, y):
    return _bit_blocks(_bits(cm, 6), x, y)


def m_gray(cm, x, y):
    g = cm ^ (cm >> 1)
    return _bit_blocks(_bits(g, 6), x, y)


def m_color_base(cm, x, y):
    # base-8, two cells (covers 0..63)
    digits = [(cm // 8) % 8, cm % 8]
    cell = CM * 0.75
    gap = 1.5
    out = []
    x0 = x - len(digits) * (cell + gap)
    for i, d in enumerate(digits):
        cx = x0 + i * (cell + gap)
        out.append(f'<rect x="{cx:.1f}" y="{y-cell/2:.1f}" width="{cell:.1f}" '
                   f'height="{cell:.1f}" fill="{BASE_COLORS[d]}" stroke="#000" '
                   f'stroke-width="0.4"/>')
    return "".join(out)


def m_letter_tens(cm, x, y):
    letter = "ABCDE"[(cm // 10) % 5]
    units = cm % 10
    return (f'<text x="{x:.1f}" y="{y+CM*0.34:.1f}" font-family="{FONT}" '
            f'font-size="{CM*0.72:.1f}" font-weight="800" text-anchor="end" '
            f'fill="#000">{letter}{units}</text>')


ENCODINGS = {
    "decimal": m_decimal,
    "decimal_color": m_decimal_color,
    "hierarchy": m_hierarchy,
    "binary": m_binary,
    "gray": m_gray,
    "color_base": m_color_base,
    "letter_tens": m_letter_tens,
}


def render_swatch(encoding, lo, n, edge_cm):
    """lo: lowest cm in window. n: number of cm shown. edge_cm: float position
    of the simulated object edge (the value we ask the VLM to read)."""
    marker = ENCODINGS[encoding]
    w = 140.0
    h = MARGIN * 2 + n * CM
    el = []

    # alternating squares
    for cm in range(lo, lo + n):
        yt = y_for(cm + 1, lo, n)
        fill = "#fff" if cm % 2 == 0 else "#000"
        el.append(f'<rect x="{BAR_LEFT:.1f}" y="{yt:.1f}" width="{BAR_W:.1f}" '
                  f'height="{CM:.1f}" fill="{fill}"/>')

    el.append(f'<rect x="{BAR_LEFT:.1f}" y="{y_for(lo+n,lo,n):.1f}" '
              f'width="{BAR_W:.1f}" height="{n*CM:.1f}" fill="none" '
              f'stroke="#000" stroke-width="0.5"/>')

    # cm ticks + markers (left), mm ticks (right)
    for cm in range(lo, lo + n + 1):
        y = y_for(cm, lo, n)
        is5 = cm % 5 == 0
        tlen = CM * 0.6 if is5 else CM * 0.35
        el.append(f'<line x1="{BAR_LEFT:.1f}" y1="{y:.1f}" '
                  f'x2="{BAR_LEFT-tlen:.1f}" y2="{y:.1f}" stroke="#000" '
                  f'stroke-width="{0.9 if is5 else 0.5}"/>')
        if cm < lo + n:
            for mm in range(1, 10):
                ym = y_for(cm, lo, n) - mm * (CM / 10)
                hh = CM * 0.4 if mm == 5 else CM * 0.22
                el.append(f'<line x1="{BAR_RIGHT:.1f}" y1="{ym:.1f}" '
                          f'x2="{BAR_RIGHT+hh:.1f}" y2="{ym:.1f}" stroke="#000" '
                          f'stroke-width="0.35"/>')
        el.append(marker(cm, BAR_LEFT - tlen - 2, y))

    # simulated object edge: red dashed line across the bar at edge_cm
    ye = y_for(edge_cm, lo, n)
    el.append(f'<line x1="{BAR_LEFT-CM*0.6:.1f}" y1="{ye:.1f}" '
              f'x2="{BAR_RIGHT+CM*0.6:.1f}" y2="{ye:.1f}" stroke="#e00" '
              f'stroke-width="1.6" stroke-dasharray="3,2"/>')
    el.append(f'<polygon points="{BAR_RIGHT+CM*0.6:.1f},{ye:.1f} '
              f'{BAR_RIGHT+CM*0.6+5:.1f},{ye-3:.1f} '
              f'{BAR_RIGHT+CM*0.6+5:.1f},{ye+3:.1f}" fill="#e00"/>')

    body = "\n  ".join(el)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" '
            f'height="{h}mm" viewBox="0 0 {w} {h}">\n'
            f'  <rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>\n'
            f'  {body}\n</svg>\n')


def render_scene(encoding, height_cm, full=42, obj_color="#3a7d3a"):
    """Realistic test: full upright ruler 0..`full` cm with an OBJECT standing
    beside it, rising from the base (0) to `height_cm`. The VLM is asked how
    tall the object is. Mirrors a bonsai photographed next to the tube.

    0 is at the bottom; values increase upward. The object is a tapering green
    shape (wider base, narrower top) on the LEFT; the ruler is on the RIGHT."""
    marker = ENCODINGS[encoding]
    lo, n = 0, full
    obj_w = 46.0
    obj_x = 6.0
    # shift ruler right to leave room for the object + its labels
    global BAR_X, BAR_LEFT, BAR_RIGHT
    BAR_X = obj_x + obj_w + 40.0
    BAR_LEFT = BAR_X - BAR_W / 2
    BAR_RIGHT = BAR_X + BAR_W / 2

    w = BAR_RIGHT + 30.0
    h = MARGIN * 2 + n * CM
    el = []

    # object: tapering trunk+canopy, base at 0 up to height_cm
    y_base = y_for(0, lo, n)
    y_top = y_for(height_cm, lo, n)
    cx = obj_x + obj_w / 2
    # simple plant silhouette: trunk rectangle + elliptical canopy at the top
    trunk_w = obj_w * 0.18
    el.append(f'<rect x="{cx-trunk_w/2:.1f}" y="{y_top:.1f}" width="{trunk_w:.1f}" '
              f'height="{y_base-y_top:.1f}" fill="#6b4a2b"/>')
    canopy_h = min((y_base - y_top) * 0.55, obj_w * 1.1)
    el.append(f'<ellipse cx="{cx:.1f}" cy="{y_top+canopy_h*0.45:.1f}" '
              f'rx="{obj_w/2:.1f}" ry="{canopy_h*0.5:.1f}" fill="{obj_color}"/>')
    # a thin guide line at the true top, on the object side only (visual aid,
    # does NOT touch the ruler so it can't leak the answer position by snapping)
    el.append(f'<line x1="{obj_x:.1f}" y1="{y_top:.1f}" x2="{cx:.1f}" '
              f'y2="{y_top:.1f}" stroke="#111" stroke-width="0.4" '
              f'stroke-dasharray="2,2"/>')

    # ruler: alternating squares
    for cm in range(lo, lo + n):
        yt = y_for(cm + 1, lo, n)
        fill = "#fff" if cm % 2 == 0 else "#000"
        el.append(f'<rect x="{BAR_LEFT:.1f}" y="{yt:.1f}" width="{BAR_W:.1f}" '
                  f'height="{CM:.1f}" fill="{fill}"/>')
    el.append(f'<rect x="{BAR_LEFT:.1f}" y="{y_for(lo+n,lo,n):.1f}" '
              f'width="{BAR_W:.1f}" height="{n*CM:.1f}" fill="none" '
              f'stroke="#000" stroke-width="0.5"/>')

    for cm in range(lo, lo + n + 1):
        y = y_for(cm, lo, n)
        is5 = cm % 5 == 0
        tlen = CM * 0.6 if is5 else CM * 0.35
        el.append(f'<line x1="{BAR_LEFT:.1f}" y1="{y:.1f}" '
                  f'x2="{BAR_LEFT-tlen:.1f}" y2="{y:.1f}" stroke="#000" '
                  f'stroke-width="{0.9 if is5 else 0.5}"/>')
        if cm < lo + n:
            for mm in range(1, 10):
                ym = y_for(cm, lo, n) - mm * (CM / 10)
                hh = CM * 0.4 if mm == 5 else CM * 0.22
                el.append(f'<line x1="{BAR_RIGHT:.1f}" y1="{ym:.1f}" '
                          f'x2="{BAR_RIGHT+hh:.1f}" y2="{ym:.1f}" stroke="#000" '
                          f'stroke-width="0.35"/>')
        el.append(marker(cm, BAR_LEFT - tlen - 2, y))

    body = "\n  ".join(el)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" '
            f'height="{h}mm" viewBox="0 0 {w} {h}">\n'
            f'  <rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>\n'
            f'  {body}\n</svg>\n')


if __name__ == "__main__":
    import os
    os.makedirs("swatches", exist_ok=True)
    for name in ENCODINGS:
        svg = render_scene(name, height_cm=16.4)
        with open(f"swatches/{name}.svg", "w") as f:
            f.write(svg)
    print("wrote", len(ENCODINGS), "scene swatches to swatches/")
