#!/usr/bin/env python3
"""Render a realistic test scene using the NARROW printable ruler layout.

Mirrors make_ruler.py: thin bar, 5cm anchors as white-on-circle marks abutting
the bar, 1cm numbers in an aligned column, short mm ticks. A plant stands beside
the full 0..42cm ruler. Modes: 'bw' and 'colour'.
"""

CM = 11.0
MARGIN = 14.0
FULL = 42

OBJ_X = 6.0
OBJ_W = 46.0
# narrow scale near the right; bar thin so it stays on the tube front arc
BAR_LEFT = OBJ_X + OBJ_W + 60.0
BAR_W = 9.0
BAR_RIGHT = BAR_LEFT + BAR_W

NUM_COL_X = BAR_LEFT - 2.0
NUM_SIZE_1 = 5.5
NUM_SIZE_5 = 6.5
CIRCLE_R = 5.0
MM_LEN = 2.4
MM_HALF = 3.6
ZONE_W = 2.0
FONT = "DejaVu Sans, Arial, sans-serif"

TENS_COLORS = ["#d11", "#16c", "#1a8a1a", "#e07000", "#92c"]


def y_for(cm):
    return MARGIN + (FULL - cm) * CM


def render_scene(mode, height_cm, obj_color="#3a7d3a"):
    colour = (mode == "colour")
    w = BAR_RIGHT + 22.0
    h = MARGIN * 2 + FULL * CM
    el = []

    # object
    y_base = y_for(0)
    y_top = y_for(height_cm)
    cx = OBJ_X + OBJ_W / 2
    trunk_w = OBJ_W * 0.18
    el.append(f'<rect x="{cx-trunk_w/2:.1f}" y="{y_top:.1f}" width="{trunk_w:.1f}" '
              f'height="{y_base-y_top:.1f}" fill="#6b4a2b"/>')
    canopy_h = min((y_base - y_top) * 0.55, OBJ_W * 1.1)
    el.append(f'<ellipse cx="{cx:.1f}" cy="{y_top+canopy_h*0.45:.1f}" '
              f'rx="{OBJ_W/2:.1f}" ry="{canopy_h*0.5:.1f}" fill="{obj_color}"/>')

    # ruler squares
    for cm in range(FULL):
        yt = y_for(cm + 1)
        fill = "#fff" if cm % 2 == 0 else "#000"
        el.append(f'<rect x="{BAR_LEFT:.1f}" y="{yt:.1f}" width="{BAR_W:.1f}" '
                  f'height="{CM:.1f}" fill="{fill}"/>')

    if colour:
        cm = 0
        while cm < FULL:
            nxt = min(((cm // 5) + 1) * 5, FULL)
            el.append(f'<rect x="{BAR_RIGHT-ZONE_W:.1f}" y="{y_for(nxt):.1f}" '
                      f'width="{ZONE_W:.1f}" height="{(nxt-cm)*CM:.1f}" '
                      f'fill="{TENS_COLORS[(cm//10)%5]}"/>')
            cm = nxt

    el.append(f'<rect x="{BAR_LEFT:.1f}" y="{y_for(FULL):.1f}" width="{BAR_W:.1f}" '
              f'height="{FULL*CM:.1f}" fill="none" stroke="#000" stroke-width="0.4"/>')

    # mm ticks (right)
    for cm in range(FULL):
        for mm in range(1, 10):
            ym = y_for(cm) - mm * (CM / 10)
            hh = MM_HALF if mm == 5 else MM_LEN
            el.append(f'<line x1="{BAR_RIGHT:.1f}" y1="{ym:.1f}" '
                      f'x2="{BAR_RIGHT+hh:.1f}" y2="{ym:.1f}" stroke="#000" '
                      f'stroke-width="0.3"/>')

    # cm markers (skip 0: the base is the origin and the label would clip)
    for cm in range(1, FULL + 1):
        y = y_for(cm)
        is5 = cm % 5 == 0
        if is5:
            ccol = TENS_COLORS[(cm // 10) % 5] if colour else "#000"
            ccx = BAR_LEFT - CIRCLE_R
            el.append(f'<circle cx="{ccx:.1f}" cy="{y:.1f}" r="{CIRCLE_R:.1f}" '
                      f'fill="{ccol}"/>')
            el.append(f'<text x="{ccx:.1f}" y="{y+NUM_SIZE_5*0.35:.1f}" '
                      f'font-family="{FONT}" font-size="{NUM_SIZE_5:.1f}" '
                      f'font-weight="800" text-anchor="middle" fill="#fff">{cm}</text>')
        else:
            el.append(f'<line x1="{BAR_LEFT:.1f}" y1="{y:.1f}" x2="{BAR_LEFT-2.5:.1f}" '
                      f'y2="{y:.1f}" stroke="#000" stroke-width="0.4"/>')
            el.append(f'<text x="{NUM_COL_X:.1f}" y="{y+NUM_SIZE_1*0.35:.1f}" '
                      f'font-family="{FONT}" font-size="{NUM_SIZE_1:.1f}" '
                      f'font-weight="600" text-anchor="end" fill="#000">{cm}</text>')

    body = "\n  ".join(el)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
            f'viewBox="0 0 {w} {h}">\n'
            f'  <rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>\n'
            f'  {body}\n</svg>\n')


MODES = ["bw", "colour"]

if __name__ == "__main__":
    import os
    os.makedirs("swatches", exist_ok=True)
    for m in MODES:
        with open(f"swatches/scene_{m}.svg", "w") as f:
            f.write(render_scene(m, 16.4))
    print("wrote scene_bw.svg, scene_colour.svg")
