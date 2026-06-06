#!/usr/bin/env python3
"""Generate a NARROW vertical 0-42cm tube ruler as two A4-portrait SVG pages.

Built for a 30mm-diameter tube standing upright. Circumference ~94mm, so only a
narrow front arc (~24mm) faces the camera; anything wider curves out of view.
Everything - bar, numbers, ticks - is kept inside ~22mm so it stays readable on
the curved surface. You cut/wrap the paper yourself; this just keeps all the
numbers aligned in one vertical column up the front.

Design (best from the VLM read test - hierarchy):
- All cm numbers sit in ONE aligned column just left of a thin bar.
- 5cm anchors (0,5,10,...) are WHITE numerals on filled BLACK circles - strong
  landmarks that survive the curve.
- 1cm numbers are small, same column.
- Thin alternating black/white square bar for edge contrast.
- Short mm ticks tucked right against the bar's right edge.

Two modes:
  bw      - black/white only.
  colour  - 5cm anchor circles tinted by tens group (0s/10s/20s/30s/40s) and a
            thin colour zone strip on the bar's right edge.

Layout: A4 portrait 210x297mm. Each page = 21cm (210mm). The whole scale sits
near the page centre; trim/position the paper as you like when wrapping.
Page 1 (BOTTOM) = cm 0-21, Page 2 (TOP) = cm 21-42. Glue so the two 21 ticks
coincide.
"""

PAGE_W = 210.0
PAGE_H = 297.0

CM = 10.0
SPANS = 21
SCALE_LEN = SPANS * CM

MARGIN_BOTTOM = 40.0

# narrow scale: keep total marked width within ~22mm of the front arc
BAR_LEFT = 110.0
BAR_W = 9.0
BAR_RIGHT = BAR_LEFT + BAR_W

NUM_COL_X = BAR_LEFT - 2.0      # right edge of the aligned number column
NUM_SIZE_1 = 5.0
NUM_SIZE_5 = 6.0               # numeral inside the anchor circle
CIRCLE_R = 4.6                 # 5cm anchor circle radius

MM_LEN = 2.2                   # mm ticks, short so they stay on the front arc
MM_HALF = 3.4
ZONE_W = 2.0

FONT = "Arial, Helvetica, sans-serif"
TENS_COLORS = ["#d11", "#16c", "#1a8a1a", "#e07000", "#92c"]


def y_for_line(line_cm, base):
    return PAGE_H - MARGIN_BOTTOM - (line_cm - base) * CM


def square(line_lo, base, color):
    y_top = y_for_line(line_lo + 1, base)
    return (f'<rect x="{BAR_LEFT:.2f}" y="{y_top:.2f}" width="{BAR_W:.2f}" '
            f'height="{CM:.2f}" fill="{color}"/>')


def zone(line_lo, line_hi, base, color):
    y_top = y_for_line(line_hi, base)
    h = (line_hi - line_lo) * CM
    return (f'<rect x="{BAR_RIGHT - ZONE_W:.2f}" y="{y_top:.2f}" '
            f'width="{ZONE_W:.2f}" height="{h:.2f}" fill="{color}"/>')


def cm_marker(line_cm, base, colour):
    y = y_for_line(line_cm, base)
    is5 = line_cm % 5 == 0
    out = []
    if is5:
        # circle abuts the bar: its right edge touches BAR_LEFT at the cm line,
        # so the circle itself marks the position - no separate tick needed.
        circ_col = TENS_COLORS[(line_cm // 10) % len(TENS_COLORS)] if colour else "#000"
        cx = BAR_LEFT - CIRCLE_R
        out.append(f'<circle cx="{cx:.2f}" cy="{y:.2f}" r="{CIRCLE_R:.2f}" '
                   f'fill="{circ_col}"/>')
        out.append(f'<text x="{cx:.2f}" y="{y + NUM_SIZE_5*0.35:.2f}" '
                   f'font-family="{FONT}" font-size="{NUM_SIZE_5:.2f}" '
                   f'font-weight="800" text-anchor="middle" fill="#fff">{line_cm}</text>')
    else:
        # short tick at the bar's left edge for the 1cm lines
        out.append(f'<line x1="{BAR_LEFT:.2f}" y1="{y:.2f}" x2="{BAR_LEFT-2.5:.2f}" '
                   f'y2="{y:.2f}" stroke="#000" stroke-width="0.4"/>')
        out.append(f'<text x="{NUM_COL_X:.2f}" y="{y + NUM_SIZE_1*0.35:.2f}" '
                   f'font-family="{FONT}" font-size="{NUM_SIZE_1:.2f}" '
                   f'font-weight="600" text-anchor="end" fill="#000">{line_cm}</text>')
    return "".join(out)


def mm_tick(line_cm, base, m):
    y = y_for_line(line_cm, base) - m
    h = MM_HALF if m == 5 else MM_LEN
    return (f'<line x1="{BAR_RIGHT:.2f}" y1="{y:.2f}" x2="{BAR_RIGHT + h:.2f}" '
            f'y2="{y:.2f}" stroke="#000" stroke-width="0.25"/>')


def build_page(base, label, colour):
    el = []
    for line in range(base, base + SPANS):
        el.append(square(line, base, "#fff" if line % 2 == 0 else "#000"))
    if colour:
        line = base
        while line < base + SPANS:
            nxt = min(((line // 5) + 1) * 5, base + SPANS)
            el.append(zone(line, nxt, base, TENS_COLORS[(line // 10) % len(TENS_COLORS)]))
            line = nxt
    y_top = y_for_line(base + SPANS, base)
    el.append(f'<rect x="{BAR_LEFT:.2f}" y="{y_top:.2f}" width="{BAR_W:.2f}" '
              f'height="{SCALE_LEN:.2f}" fill="none" stroke="#000" stroke-width="0.4"/>')
    for line in range(base, base + SPANS):
        for m in range(1, 10):
            el.append(mm_tick(line, base, m))
    for line in range(base, base + SPANS + 1):
        if line == 0:
            continue          # the tube base IS 0; label would clip at the edge
        el.append(cm_marker(line, base, colour))

    el.append(f'<text x="8" y="{PAGE_H - 6:.2f}" font-family="{FONT}" '
              f'font-size="4" fill="#000">{label}</text>')

    body = "\n  ".join(el)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{PAGE_W}mm" height="{PAGE_H}mm" '
            f'viewBox="0 0 {PAGE_W} {PAGE_H}">\n'
            f'  <rect x="0" y="0" width="{PAGE_W}" height="{PAGE_H}" fill="#fff"/>\n'
            f'  {body}\n</svg>\n')


def emit(colour, suffix):
    p1 = build_page(0, "PAGE 1 (BOTTOM)  cm 0-21  | 0 = base; glue PAGE 2 above so the 21 ticks meet",
                    colour)
    p2 = build_page(21, "PAGE 2 (TOP)  cm 21-42  | glue this 21 edge onto PAGE 1's 21 edge",
                    colour)
    with open(f"ruler_{suffix}_page1.svg", "w") as f:
        f.write(p1)
    with open(f"ruler_{suffix}_page2.svg", "w") as f:
        f.write(p2)
    print(f"wrote ruler_{suffix}_page1.svg, ruler_{suffix}_page2.svg")


if __name__ == "__main__":
    emit(colour=False, suffix="bw")
    emit(colour=True, suffix="colour")
