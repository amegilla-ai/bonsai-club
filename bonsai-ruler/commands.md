# bonsai-ruler commands

## Generate the SVGs
```bash
cd ~/Projects/bonsai-ruler && python3 make_ruler.py
```

## Preview as PNG
```bash
cd ~/Projects/bonsai-ruler && rsvg-convert -w 1600 ruler_page1.svg -o preview_page1.png && rsvg-convert -w 1600 ruler_page2.svg -o preview_page2.png
```

## Make print-ready PDF (exact A4, actual size)
```bash
cd ~/Projects/bonsai-ruler && rsvg-convert -f pdf -o ruler_page1.pdf ruler_page1.svg && rsvg-convert -f pdf -o ruler_page2.pdf ruler_page2.svg
```

## Combine into one 2-page PDF (needs pdfunite from poppler)
```bash
cd ~/Projects/bonsai-ruler && pdfunite ruler_page1.pdf ruler_page2.pdf ruler.pdf
```

## Printing
- Print at 100% / Actual Size. Do NOT use "Fit to page" - it rescales and breaks the mm scale.
- After printing, measure cm 0 to cm 10 with a real ruler: it must be exactly 100mm. If not, the print scaling is wrong.
- Cut page 1 at the "21" line, lay page 2's "21" edge against it, glue. Result is a continuous 0-42cm scale.
