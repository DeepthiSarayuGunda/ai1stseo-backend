"""
batch_generate_v2.py - Generate 15 social media images from copy_library.
Reuses existing backgrounds. No AI regeneration.
Usage: python dev4-local-ai-tests/batch_generate_v2.py
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(SCRIPT_DIR, "outputs")
FONTS_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
BG_BANNER = os.path.join(OUTPUTS_DIR, "bg_seo_banner.png")
BG_SOCIAL = os.path.join(OUTPUTS_DIR, "bg_social_post.png")

sys.path.insert(0, SCRIPT_DIR)
from copy_library import COPY

def ft(name, size):
    p = os.path.join(FONTS_DIR, name)
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()

def ctrx(d, txt, f, w):
    bb = d.textbbox((0, 0), txt, font=f)
    return (w - (bb[2] - bb[0])) // 2

COLORS = [
    (59,130,246),(16,185,129),(139,92,246),(236,72,153),
    (14,165,233),(245,158,11),(34,197,94),(99,102,241),
    (234,88,12),(22,163,74),(79,70,229),(6,182,212),
    (217,70,239),(37,99,235),(225,29,72),
]



def layout_center(img, hl, sub, cta, acc):
    w, h = img.size
    ov = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(ov)
    bt, bb = int(h*0.25), int(h*0.75)
    d.rectangle([int(w*0.07), bt, int(w*0.93), bb], fill=(0,0,0,145))
    d.rectangle([int(w*0.07), bt, int(w*0.93), bt+5], fill=(*acc,220))
    fh = ft("arialbd.ttf", 68)
    fs = ft("calibrib.ttf", 34)
    fc = ft("segoeuib.ttf", 28)
    hx = ctrx(d, hl, fh, w)
    hy = bt + 50
    d.text((hx+2, hy+2), hl, font=fh, fill=(0,0,0,140))
    d.text((hx, hy), hl, font=fh, fill=(255,255,255,255))
    sx = ctrx(d, sub, fs, w)
    sy = hy + 100
    d.text((sx, sy), sub, font=fs, fill=(200,220,255,230))
    ccx = ctrx(d, cta, fc, w)
    ccy = bb - 80
    cb = d.textbbox((ccx, ccy), cta, font=fc)
    d.rounded_rectangle([cb[0]-36, cb[1]-18, cb[2]+36, cb[3]+18], radius=22, fill=(*acc,220))
    d.text((ccx, ccy), cta, font=fc, fill=(255,255,255,255))
    return Image.alpha_composite(img, ov)

def layout_top(img, hl, sub, cta, acc):
    w, h = img.size
    ov = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(ov)
    for y in range(int(h*0.55)):
        a = int(150*(1 - y/(h*0.55)))
        d.line([(0,y),(w,y)], fill=(0,0,0,a))
    fh = ft("impact.ttf", 80)
    fs = ft("arialbd.ttf", 38)
    fc = ft("segoeuib.ttf", 26)
    hx = ctrx(d, hl, fh, w)
    hy = int(h*0.12)
    d.text((hx+3, hy+3), hl, font=fh, fill=(0,0,0,180))
    d.text((hx, hy), hl, font=fh, fill=(255,255,255,255))
    bb = d.textbbox((hx, hy), hl, font=fh)
    ly = bb[3]+12
    lx = (w-(bb[2]-bb[0]))//2
    d.rectangle([lx, ly, lx+(bb[2]-bb[0]), ly+4], fill=(*acc,200))
    sx = ctrx(d, sub, fs, w)
    sy = ly + 30
    d.text((sx+2, sy+2), sub, font=fs, fill=(0,0,0,120))
    d.text((sx, sy), sub, font=fs, fill=(220,235,255,245))
    ccx = ctrx(d, cta, fc, w)
    ccy = int(h*0.85)
    cb = d.textbbox((ccx, ccy), cta, font=fc)
    d.rounded_rectangle([cb[0]-32, cb[1]-16, cb[2]+32, cb[3]+16], radius=20, fill=(*acc,210))
    d.text((ccx, ccy), cta, font=fc, fill=(255,255,255,255))
    return Image.alpha_composite(img, ov)

def layout_bar(img, hl, sub, cta, acc):
    w, h = img.size
    ov = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(ov)
    for y in range(int(h*0.45)):
        a = int(130*(1 - y/(h*0.45)))
        d.line([(0,y),(w,y)], fill=(0,0,0,a))
    fh = ft("arialbd.ttf", 64)
    fs = ft("calibrib.ttf", 32)
    fc = ft("arialbd.ttf", 36)
    fb = ft("calibrib.ttf", 20)
    hx = ctrx(d, hl, fh, w)
    hy = int(h*0.15)
    d.text((hx+2, hy+2), hl, font=fh, fill=(0,0,0,150))
    d.text((hx, hy), hl, font=fh, fill=(255,255,255,255))
    sx = ctrx(d, sub, fs, w)
    sy = hy + 90
    d.text((sx, sy), sub, font=fs, fill=(210,225,255,230))
    bar_y = h - 120
    d.rectangle([0, bar_y, w, h], fill=(*acc,220))
    ccx = ctrx(d, cta, fc, w)
    ccy = bar_y + 20
    d.text((ccx, ccy), cta, font=fc, fill=(255,255,255,255))
    bx = ctrx(d, "ai1stseo.com", fb, w)
    d.text((bx, ccy+46), "ai1stseo.com", font=fb, fill=(255,255,255,180))
    return Image.alpha_composite(img, ov)



LAYOUTS = [layout_center, layout_top, layout_bar]

# Pick 15 items: 4 promotional, 4 stats, 4 educational, 3 brand
PICKS = [1,3,5,7, 9,11,13,15, 17,19,21,23, 25,27,29]

def main():
    print("=" * 60)
    print("BATCH GENERATE V2 - 15 new social media images")
    print("=" * 60)
    bgs = [BG_BANNER, BG_SOCIAL]
    for bg in bgs:
        if not os.path.exists(bg):
            print(f"ERROR: {bg} not found")
            return
    results = []
    for idx, pick_id in enumerate(PICKS):
        entry = None
        for c in COPY:
            if c["id"] == pick_id:
                entry = c
                break
        if not entry:
            continue
        num = idx + 1
        bg_path = bgs[idx % 2]
        layout_fn = LAYOUTS[idx % 3]
        accent = COLORS[idx % len(COLORS)]
        bg_img = Image.open(bg_path).convert("RGBA")
        result = layout_fn(bg_img, entry["headline"], entry["subtitle"], entry["cta"], accent)
        result = result.convert("RGB")
        fname = f"final_v2_{num:02d}.png"
        out_path = os.path.join(OUTPUTS_DIR, fname)
        result.save(out_path, quality=95)
        kb = os.path.getsize(out_path) / 1024
        bg_short = os.path.basename(bg_path)
        style = layout_fn.__name__
        print(f"  [{num:02d}] {fname} | {entry['headline']}")
        print(f"        {entry['cat']} | {style} | {bg_short} | {kb:.0f} KB")
        results.append({
            "num": num,
            "file": fname,
            "headline": entry["headline"],
            "subtitle": entry["subtitle"],
            "cta": entry["cta"],
            "cat": entry["cat"],
            "style": style,
            "bg": bg_short,
            "kb": round(kb),
        })
    print(f"\n{'='*60}")
    print(f"DONE - {len(results)} images generated in {OUTPUTS_DIR}")
    print(f"{'='*60}")
    # Write catalog markdown
    md_path = os.path.join(SCRIPT_DIR, "image_catalog.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Social Media Image Catalog\n\n")
        f.write(f"**Total images:** {len(results)}\n\n")
        f.write("| # | File | Headline | Subtitle | CTA | Category | Layout |\n")
        f.write("|---|------|----------|----------|-----|----------|--------|\n")
        for r in results:
            f.write(f"| {r['num']} | `{r['file']}` | {r['headline']} | {r['subtitle']} | {r['cta']} | {r['cat']} | {r['style']} |\n")
    print(f"Catalog written to: {md_path}")

if __name__ == "__main__":
    main()
