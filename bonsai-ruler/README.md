# bonsai-ruler

A printable 0-42cm ruler designed to sit inside a clear upright tube, so a
vision-language model (VLM) can estimate the height of a plant photographed
beside it - e.g. to categorise bonsai by size (mame, shohin, etc.).

The ruler is generated as SVG, exported to A4 PDF, and tuned by an experiment
that measured how accurately a local VLM reads height off each design.

## The design

A narrow vertical scale built for a **30mm-diameter tube standing upright**.
The tube circumference is ~94mm, so only a narrow front arc (~24mm) faces the
camera; anything wider curves out of view. The whole scale - bar, numbers,
ticks - is kept inside ~22mm so every mark stays readable on the curved front.

- 0 at the bottom (the tube base is the origin), increasing upward to 42.
- All cm numbers in one aligned column up the front.
- 5cm anchors (5, 10, 15, ...) are white numerals on filled circles that abut
  the bar at the cm line - strong landmarks that survive the curve.
- 1cm numbers are small, in the same column.
- A thin alternating black/white square bar for edge contrast.
- Short mm ticks tucked against the bar's right edge.

Two pages: page 1 = cm 0-21 (bottom), page 2 = cm 21-42 (top). Each A4 carries
210mm of scale; glued at the shared 21 line they make a continuous 420mm ruler.

## What the experiment found

A test harness renders a plant beside the ruler at known heights, sends the
image to a local VLM (Gemma, served via llama.cpp), and scores the absolute
error of its height estimate.

Black & white beat colour clearly on the narrow design:

| Mode | mean abs err | within 1cm | worst case |
|---|---|---|---|
| **bw** | **0.46 cm** | 20/20 | 0.90 cm |
| colour | 8.07 cm | 15/20 | 36.70 cm |

The colour version failed badly on short plants (the sizes that matter most),
reading some as the full ruler length. **`ruler_bw.pdf` is the shipped output.**

An earlier round compared seven number encodings (plain decimal, colour-coded
tens, size hierarchy, binary, gray code, base-N colour cells, letter+digit).
The readable decimal designs (hierarchy ~0.19cm) far outperformed every machine
code (binary/gray/base-N all 5-7cm error) - the VLM cannot reliably decode bit
or colour patterns, so the ruler uses plain numbers with large 5cm anchors.

## Files

| File | Purpose |
|---|---|
| `make_ruler.py` | Generates the printable ruler (bw + colour) as two-page A4 SVG. |
| `ruler_bw_page1.pdf` | Bottom half to print: cm 0-21. |
| `ruler_bw_page2.pdf` | Top half to print: cm 21-42. Glue above page 1 at the 21 line. |
| `ruler_encodings.py` | Renders the seven number-encoding variants for the first experiment. |
| `scene_real.py` | Renders a plant-beside-ruler test scene in the real printable layout. |
| `run_test.py` | Encoding comparison: scores VLM height reads across all encodings. |
| `test_bw_vs_colour.py` | Head-to-head bw vs colour on the real layout. |

Generated artifacts (SVGs, PNG previews, colour PDF, test output) are
gitignored - regenerate them with the commands below.

## Usage

### Generate the rulers
```bash
python3 make_ruler.py
# writes ruler_bw_page1.svg, ruler_bw_page2.svg, ruler_colour_page1.svg, ruler_colour_page2.svg
```

### Make the print-ready PDFs (exact A4, one per page)
```bash
for p in 1 2; do rsvg-convert -f pdf -o ruler_bw_page${p}.pdf ruler_bw_page${p}.svg; done
```

### Run the VLM tests
The harness talks to an OpenAI-compatible endpoint (llama.cpp / vLLM). Set the
endpoint and model, then run:
```bash
export VLM_URL=http://localhost:8060/v1/chat/completions
export VLM_MODEL="gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf"

python3 test_bw_vs_colour.py     # bw vs colour, writes test_bwcol/report.md
python3 run_test.py              # all encodings, writes test_run/report.md
```
The model is a reasoner; the harness disables thinking (`enable_thinking=false`)
and forces JSON output so answers parse cleanly.

## Printing and assembly

1. Print `ruler_bw_page1.pdf` and `ruler_bw_page2.pdf` at **100% / Actual
   Size**. Do NOT use "Fit to page" - it rescales and breaks the mm scale.
2. Verify: measure cm 5 to cm 15 with a real ruler - it must be exactly 100mm.
   (0 and the very top are unlabelled; any 10cm span works.)
3. Cut page 1 at the 21 line, lay page 2's 21 edge against it, glue - a
   continuous 0-42cm scale.
4. Roll/trim the paper so the narrow scale sits on the outer wrap facing out,
   insert into the tube standing upright with 0 at the base, fill (sand/beans)
   to hold it.

## Requirements

- Python 3 (standard library only; `requests` for the VLM tests)
- `librsvg` (`rsvg-convert`) for SVG to PNG/PDF
- `poppler` (`pdfunite`, `pdfinfo`) to combine pages
- A local VLM on an OpenAI-compatible endpoint (only for the tests)
