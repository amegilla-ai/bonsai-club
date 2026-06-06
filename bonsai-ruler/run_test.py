#!/usr/bin/env python3
"""VLM-readability test harness for ruler encodings.

Generates N test swatches per encoding, each with a simulated object edge at a
known cm position, sends them to a local vLLM (OpenAI-compatible) endpoint,
parses the model's read, and scores absolute error. Writes report.md + a CSV.

Config via env:
  VLM_URL    default http://localhost:8000/v1/chat/completions
  VLM_MODEL  default google/gemma-3-27b-it  (set to whatever you serve)
  VLM_KEY    default "EMPTY"
  N_PER_ENC  default 12
  SEED       default 7   (deterministic test set; does not use system RNG clock)

Usage:
  python3 run_test.py                 # full run, calls the VLM
  python3 run_test.py --dry-run       # render test set + prompts, no API calls
"""
import os, sys, csv, json, base64, subprocess, re, random
from ruler_encodings import ENCODINGS, render_scene

VLM_URL   = os.environ.get("VLM_URL", "http://localhost:8000/v1/chat/completions")
VLM_MODEL = os.environ.get("VLM_MODEL", "google/gemma-3-27b-it")
VLM_KEY   = os.environ.get("VLM_KEY", "EMPTY")
N_PER_ENC = int(os.environ.get("N_PER_ENC", "12"))
SEED      = int(os.environ.get("SEED", "7"))

OUT = "test_run"
WINDOW = 8                      # cm shown per swatch

LEGEND = {
    "decimal": "Numbers are centimetres.",
    "decimal_color": "Numbers are centimetres; digit colour just groups each ten.",
    "hierarchy": "Numbers are centimetres; multiples of 5 are printed larger.",
    "binary": ("Each centimetre line is labelled in BINARY as a row of 6 boxes, "
               "most-significant bit on the LEFT. A FILLED (black) box = 1, an "
               "EMPTY (white) box = 0. Convert the binary to a decimal number."),
    "gray": ("Each centimetre line is labelled in REFLECTED GRAY CODE as 6 boxes, "
             "MSB on the LEFT, filled=1 empty=0. Decode gray code to decimal: the "
             "first bit is the value's top bit; each subsequent decoded bit = "
             "previous decoded bit XOR current gray bit."),
    "color_base": ("Each centimetre line is labelled by 2 coloured cells in base-8 "
                   "(left cell = eights, right = units). Colour->digit: "
                   "red=0 blue=1 green=2 orange=3 purple=4 teal=5 pink=6 grey=7. "
                   "Value = left*8 + right."),
    "letter_tens": ("Each centimetre line is labelled letter+digit. Letter = tens "
                    "(A=0, B=10, C=20, D=30, E=40), digit = units. E.g. B7 = 17."),
}


def render_png(encoding, height):
    svg = render_scene(encoding, height_cm=height)
    spath = f"{OUT}/{encoding}_{height:.1f}.svg"
    ppath = spath[:-4] + ".png"
    with open(spath, "w") as f:
        f.write(svg)
    subprocess.run(["rsvg-convert", "-h", "1400", spath, "-o", ppath], check=True)
    return ppath


def make_test_set():
    rng = random.Random(SEED)          # seeded; no wall-clock randomness
    # one shared set of heights, reused across every encoding so the comparison
    # is apples-to-apples (same objects, only the ruler markings differ).
    heights = [round(rng.uniform(4, 40), 1) for _ in range(N_PER_ENC)]
    cases = []
    for enc in ENCODINGS:
        for hgt in heights:
            cases.append({"enc": enc, "height": hgt})
    return cases


def prompt_for(enc):
    return (
        "This image shows a plant standing next to a vertical ruler. The ruler "
        "reads in centimetres: 0 is at the bottom (the base, where the plant "
        "sits) and values increase upward. " + LEGEND[enc] + " "
        "Estimate the HEIGHT of the plant - the centimetre level on the ruler "
        "that lines up with the very top of the plant - as accurately as you "
        "can, to one decimal place, using the labelled lines and the small "
        "millimetre ticks on the right. "
        'Answer with ONLY a JSON object: {"cm": <number>}.'
    )


def call_vlm(ppath, prompt):
    import requests
    with open(ppath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {
        "model": VLM_MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]}],
        "max_tokens": 512, "temperature": 0.0,
        # force clean parseable output; disable the model's chain-of-thought
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(VLM_URL, json=payload,
                      headers={"Authorization": f"Bearer {VLM_KEY}"}, timeout=180)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    # this model is a reasoner: final answer in content, trace in reasoning_content.
    # fall back to the trace if content is empty (answer may be the last JSON there).
    return msg.get("content") or msg.get("reasoning_content") or ""


def parse_cm(text):
    # prefer the explicit JSON answer; take the LAST one if several appear
    ms = re.findall(r'"cm"\s*:\s*(-?\d+(?:\.\d+)?)', text)
    if ms:
        return float(ms[-1])
    # fallback (e.g. reasoning trace): the final number mentioned
    ms = re.findall(r'(-?\d+(?:\.\d+)?)', text)
    return float(ms[-1]) if ms else None


def main():
    dry = "--dry-run" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    cases = make_test_set()
    rows = []
    for i, c in enumerate(cases):
        ppath = render_png(c["enc"], c["height"])
        prompt = prompt_for(c["enc"])
        read, err, raw = None, None, ""
        if not dry:
            try:
                raw = call_vlm(ppath, prompt)
                read = parse_cm(raw)
                if read is not None:
                    err = abs(read - c["height"])
            except Exception as e:
                raw = f"ERROR: {e}"
        rows.append({**c, "read": read, "abs_err": err, "raw": raw, "img": ppath})
        line = (f"[{i+1}/{len(cases)}] {c['enc']:13s} truth={c['height']:.1f} "
                f"read={read} err={err}")
        print(line, flush=True)
        with open(f"{OUT}/live.log", "a") as lf:
            lf.write(line + "\n")

    with open(f"{OUT}/results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["enc", "height", "read", "abs_err", "img", "raw"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    write_report(rows, dry)
    print(f"\nwrote {OUT}/results.csv and {OUT}/report.md")


def write_report(rows, dry):
    by = {}
    for r in rows:
        by.setdefault(r["enc"], []).append(r)
    lines = ["# Ruler encoding VLM-readability report", ""]
    lines.append(f"- Model: `{VLM_MODEL}`  |  Endpoint: `{VLM_URL}`")
    lines.append(f"- Cases per encoding: {N_PER_ENC}  |  Seed: {SEED}  |  Window: {WINDOW} cm")
    if dry:
        lines.append("- **DRY RUN** - no VLM calls made; swatches + prompts only.")
    lines += ["", "## Summary (lower error = better)", "",
              "| Encoding | n | mean abs err (cm) | median | within 0.5cm | parse fails |",
              "|---|---|---|---|---|---|"]

    def fmt(x):
        return "-" if x is None else f"{x:.2f}"

    ranked = []
    for enc, rs in by.items():
        errs = [r["abs_err"] for r in rs if r["abs_err"] is not None]
        fails = sum(1 for r in rs if r["read"] is None)
        mean = sum(errs)/len(errs) if errs else None
        errs_sorted = sorted(errs)
        med = errs_sorted[len(errs_sorted)//2] if errs_sorted else None
        within = sum(1 for e in errs if e <= 0.5)
        ranked.append((mean if mean is not None else 1e9, enc, len(rs), mean, med, within, fails))
    ranked.sort()
    for _, enc, n, mean, med, within, fails in ranked:
        lines.append(f"| {enc} | {n} | {fmt(mean)} | {fmt(med)} | {within}/{n} | {fails} |")

    lines += ["", "## Per-case detail", ""]
    for enc, rs in by.items():
        lines.append(f"### {enc}")
        lines.append("| truth cm | read cm | abs err | image |")
        lines.append("|---|---|---|---|")
        for r in rs:
            lines.append(f"| {r['height']:.1f} | {fmt(r['read'])} | {fmt(r['abs_err'])} "
                         f"| `{r['img']}` |")
        lines.append("")

    with open(f"{OUT}/report.md", "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
