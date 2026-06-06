#!/usr/bin/env python3
"""Head-to-head: bw vs colour printable ruler, VLM height-reading accuracy.

Same plant heights shown against each ruler mode; the VLM estimates height;
we score absolute error. Mirrors run_test.py but only the two real designs.

Env: VLM_URL, VLM_MODEL, VLM_KEY, N (cases per mode, default 20), SEED (7).
"""
import os, sys, csv, base64, subprocess, re, random
from scene_real import render_scene, MODES

VLM_URL   = os.environ.get("VLM_URL", "http://localhost:8060/v1/chat/completions")
VLM_MODEL = os.environ.get("VLM_MODEL", "gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf")
VLM_KEY   = os.environ.get("VLM_KEY", "EMPTY")
N         = int(os.environ.get("N", "20"))
SEED      = int(os.environ.get("SEED", "7"))
OUT       = "test_bwcol"

PROMPT = (
    "This image shows a plant standing next to a vertical ruler marked in "
    "centimetres. 0 is at the bottom (the base, where the plant sits) and "
    "values increase upward; multiples of 5 are printed larger. Estimate the "
    "HEIGHT of the plant - the centimetre level on the ruler that lines up with "
    "the very top of the plant - as accurately as you can, to one decimal "
    "place, using the labelled lines and the small millimetre ticks on the "
    'right. Answer with ONLY a JSON object: {"cm": <number>}.'
)


def render_png(mode, height):
    spath = f"{OUT}/{mode}_{height:.1f}.svg"
    ppath = spath[:-4] + ".png"
    with open(spath, "w") as f:
        f.write(render_scene(mode, height))
    subprocess.run(["rsvg-convert", "-h", "1500", spath, "-o", ppath], check=True)
    return ppath


def call_vlm(ppath):
    import requests
    b64 = base64.b64encode(open(ppath, "rb").read()).decode()
    payload = {
        "model": VLM_MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]}],
        "max_tokens": 512, "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(VLM_URL, json=payload,
                      headers={"Authorization": f"Bearer {VLM_KEY}"}, timeout=180)
    r.raise_for_status()
    m = r.json()["choices"][0]["message"]
    return m.get("content") or m.get("reasoning_content") or ""


def parse_cm(text):
    ms = re.findall(r'"cm"\s*:\s*(-?\d+(?:\.\d+)?)', text)
    if ms:
        return float(ms[-1])
    ms = re.findall(r'(-?\d+(?:\.\d+)?)', text)
    return float(ms[-1]) if ms else None


def main():
    dry = "--dry-run" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(SEED)
    heights = [round(rng.uniform(4, 40), 1) for _ in range(N)]  # shared heights
    rows = []
    open(f"{OUT}/live.log", "w").close()
    i = 0
    total = len(MODES) * len(heights)
    for mode in MODES:
        for hgt in heights:
            i += 1
            ppath = render_png(mode, hgt)
            read = err = None
            raw = ""
            if not dry:
                try:
                    raw = call_vlm(ppath)
                    read = parse_cm(raw)
                    if read is not None:
                        err = abs(read - hgt)
                except Exception as e:
                    raw = f"ERROR: {e}"
            rows.append({"mode": mode, "height": hgt, "read": read,
                         "abs_err": err, "img": ppath, "raw": raw})
            line = f"[{i}/{total}] {mode:6s} truth={hgt:.1f} read={read} err={err}"
            print(line, flush=True)
            with open(f"{OUT}/live.log", "a") as lf:
                lf.write(line + "\n")

    with open(f"{OUT}/results.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["mode", "height", "read", "abs_err", "img", "raw"])
        wr.writeheader()
        wr.writerows(rows)

    report(rows, heights, dry)
    print(f"\nwrote {OUT}/report.md and {OUT}/results.csv")


def report(rows, heights, dry):
    by = {m: [r for r in rows if r["mode"] == m] for m in MODES}
    L = ["# bw vs colour ruler - VLM height reading", "",
         f"- Model: `{VLM_MODEL}`", f"- Cases per mode: {len(heights)} | Seed: {SEED} | shared heights",
         ""]
    if dry:
        L.append("- **DRY RUN** (no VLM calls)\n")
    L += ["## Summary (lower error = better)", "",
          "| Mode | n | mean abs err (cm) | median | max | within 0.5cm | within 1cm |",
          "|---|---|---|---|---|---|---|"]
    for m in MODES:
        errs = sorted(r["abs_err"] for r in by[m] if r["abs_err"] is not None)
        if not errs:
            L.append(f"| {m} | 0 | - | - | - | - | - |"); continue
        mean = sum(errs) / len(errs)
        med = errs[len(errs)//2]
        L.append(f"| {m} | {len(errs)} | {mean:.2f} | {med:.2f} | {max(errs):.2f} | "
                 f"{sum(e<=0.5 for e in errs)}/{len(errs)} | {sum(e<=1.0 for e in errs)}/{len(errs)} |")

    # paired per-height comparison (same height, both modes)
    L += ["", "## Per-height (same plant, both rulers)", "",
          "| height | bw read | bw err | colour read | colour err | better |",
          "|---|---|---|---|---|---|"]
    bw = {r["height"]: r for r in by["bw"]}
    co = {r["height"]: r for r in by["colour"]}
    for hgt in heights:
        b, c = bw.get(hgt), co.get(hgt)
        be = b["abs_err"] if b else None
        ce = c["abs_err"] if c else None
        better = "-"
        if be is not None and ce is not None:
            better = "bw" if be < ce else ("colour" if ce < be else "tie")
        f = lambda x: "-" if x is None else f"{x:.2f}"
        L.append(f"| {hgt:.1f} | {f(b['read'] if b else None)} | {f(be)} | "
                 f"{f(c['read'] if c else None)} | {f(ce)} | {better} |")

    with open(f"{OUT}/report.md", "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
