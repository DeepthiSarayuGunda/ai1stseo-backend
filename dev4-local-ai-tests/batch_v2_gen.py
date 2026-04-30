"""batch_v2_gen.py - Generate 15 social images from copy_library. No AI regen."""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(SCRIPT_DIR, "outputs")
FONTS_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
BG_A = os.path.join(OUTPUTS_DIR, "bg_seo_banner.png")
BG_B = os.path.join(OUTPUTS_DIR, "bg_social_post.png")

sys.path.insert(0, SCRIPT_DIR)
from copy_library import COPY
from PIL import Image, ImageDraw, ImageFont


def load_font(name, size):
    p = os.path.join(FONTS_DIR, name)
    if os.path.exists(p):
        return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def center_text_x(draw, text, fnt, canvas_width):
    bb = draw.textbbox((0, 0), text, font=fnt)
    tw = bb[2] - bb[0]
    return (canvas_width - tw) // 2


ACCENT_COLORS = [
    (59, 130, 246), (16, 185, 129), (139, 92, 246), (236, 72, 153),
    (14, 165, 233), (245, 158, 11), (34, 197, 94), (99, 102, 241),
    (234, 88, 12), (22, 163, 74), (79, 70, 229), (6, 182, 212),
    (217, 70, 239), (37, 99, 235), (225, 29, 72),
]

PICK_IDS = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29]


def draw_center_box(img, hl, sub, cta, acc):
    w, h = img.size
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    top = int(h * 0.25)
    bot = int(h * 0.75)
    left = int(w * 0.07)
    right = int(w * 0.93)
    d.rectangle([left, top, right, bot], fill=(0, 0, 0, 145))
    d.rectangle([left, top, right, top + 5], fill=(acc[0], acc[1], acc[2], 220))
    f_hl = load_font("arialbd.ttf", 68)
    f_sub = load_font("calibrib.ttf", 34)
    f_cta = load_font("segoeuib.ttf", 28)
    hx = center_text_x(d, hl, f_hl, w)
    hy = top + 50
    d.text((hx + 2, hy + 2), hl, font=f_hl, fill=(0, 0, 0, 140))
    d.text((hx, hy), hl, font=f_hl, fill=(255, 255, 255, 255))
    sx = center_text_x(d, sub, f_sub, w)
    sy = hy + 100
    d.text((sx, sy), sub, font=f_sub, fill=(200, 220, 255, 230))
    cx = center_text_x(d, cta, f_cta, w)
    cy = bot - 80
    cb = d.textbbox((cx, cy), cta, font=f_cta)
    d.rounded_rectangle(
        [cb[0] - 36, cb[1] - 18, cb[2] + 36, cb[3] + 18],
        radius=22, fill=(acc[0], acc[1], acc[2], 220)
    )
    d.text((cx, cy), cta, font=f_cta, fill=(255, 255, 255, 255))
    return Image.alpha_composite(img, ov)


def draw_top_heavy(img, hl, sub, cta, acc):
    w, h = img.size
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(int(h * 0.55)):
        alpha = int(150 * (1 - y / (h * 0.55)))
        d.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    f_hl = load_font("impact.ttf", 80)
    f_sub = load_font("arialbd.ttf", 38)
    f_cta = load_font("segoeuib.ttf", 26)
    hx = center_text_x(d, hl, f_hl, w)
    hy = int(h * 0.12)
    d.text((hx + 3, hy + 3), hl, font=f_hl, fill=(0, 0, 0, 180))
    d.text((hx, hy), hl, font=f_hl, fill=(255, 255, 255, 255))
    hbb = d.textbbox((hx, hy), hl, font=f_hl)
    line_y = hbb[3] + 12
    line_x = (w - (hbb[2] - hbb[0])) // 2
    line_w = hbb[2] - hbb[0]
    d.rectangle([line_x, line_y, line_x + line_w, line_y + 4],
                fill=(acc[0], acc[1], acc[2], 200))
    sx = center_text_x(d, sub, f_sub, w)
    sy = line_y + 30
    d.text((sx + 2, sy + 2), sub, font=f_sub, fill=(0, 0, 0, 120))
    d.text((sx, sy), sub, font=f_sub, fill=(220, 235, 255, 245))
    cx = center_text_x(d, cta, f_cta, w)
    cy = int(h * 0.85)
    cb = d.textbbox((cx, cy), cta, font=f_cta)
    d.rounded_rectangle(
        [cb[0] - 32, cb[1] - 16, cb[2] + 32, cb[3] + 16],
        radius=20, fill=(acc[0], acc[1], acc[2], 210)
    )
    d.text((cx, cy), cta, font=f_cta, fill=(255, 255, 255, 255))
    return Image.alpha_composite(img, ov)


def draw_bottom_bar(img, hl, sub, cta, acc):
    w, h = img.size
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(int(h * 0.45)):
        alpha = int(130 * (1 - y / (h * 0.45)))
        d.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    f_hl = load_font("arialbd.ttf", 64)
    f_sub = load_font("calibrib.ttf", 32)
    f_cta = load_font("arialbd.ttf", 36)
    f_brand = load_font("calibrib.ttf", 20)
    hx = center_text_x(d, hl, f_hl, w)
    hy = int(h * 0.15)
    d.text((hx + 2, hy + 2), hl, font=f_hl, fill=(0, 0, 0, 150))
    d.text((hx, hy), hl, font=f_hl, fill=(255, 255, 255, 255))
    sx = center_text_x(d, sub, f_sub, w)
    sy = hy + 90
    d.text((sx, sy), sub, font=f_sub, fill=(210, 225, 255, 230))
    bar_y = h - 120
    d.rectangle([0, bar_y, w, h], fill=(acc[0], acc[1], acc[2], 220))
    cx = center_text_x(d, cta, f_cta, w)
    cy = bar_y + 20
    d.text((cx, cy), cta, font=f_cta, fill=(255, 255, 255, 255))
    bx = center_text_x(d, "ai1stseo.com", f_brand, w)
    d.text((bx, cy + 46), "ai1stseo.com", font=f_brand, fill=(255, 255, 255, 180))
    return Image.alpha_composite(img, ov)


LAYOUT_FNS = [draw_center_box, draw_top_heavy, draw_bottom_bar]


def main():
    print("=" * 60)
    print("BATCH V2 - Generating 15 social media images")
    print("=" * 60)

    backgrounds = [BG_A, BG_B]
    for bg in backgrounds:
        if not os.path.exists(bg):
            print("ERROR: Background not found: " + bg)
            return

    results = []
    for idx, pick_id in enumerate(PICK_IDS):
        entry = None
        for c in COPY:
            if c["id"] == pick_id:
                entry = c
                break
        if entry is None:
            continue

        num = idx + 1
        bg_path = backgrounds[idx % 2]
        layout_fn = LAYOUT_FNS[idx % 3]
        accent = ACCENT_COLORS[idx % len(ACCENT_COLORS)]

        bg_img = Image.open(bg_path).convert("RGBA")
        composed = layout_fn(bg_img, entry["headline"], entry["subtitle"], entry["cta"], accent)
        final = composed.convert("RGB")

        fname = "final_v2_%02d.png" % num
        out_path = os.path.join(OUTPUTS_DIR, fname)
        final.save(out_path, quality=95)
        kb = os.path.getsize(out_path) / 1024

        bg_short = os.path.basename(bg_path)
        style_name = layout_fn.__name__
        print("  [%02d] %s | %s" % (num, fname, entry["headline"]))
        print("        %s | %s | %s | %d KB" % (entry["cat"], style_name, bg_short, kb))

        results.append({
            "num": num, "file": fname,
            "headline": entry["headline"], "subtitle": entry["subtitle"],
            "cta": entry["cta"], "cat": entry["cat"],
            "style": style_name, "bg": bg_short, "kb": int(kb),
        })

    print("")
    print("=" * 60)
    print("DONE - %d images generated" % len(results))
    print("Output: " + OUTPUTS_DIR)
    print("=" * 60)

    # Write catalog
    md_path = os.path.join(SCRIPT_DIR, "image_catalog.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Social Media Image Catalog\n\n")
        f.write("**Generated:** 15 images from 30-entry copy library\n\n")
        f.write("| # | File | Headline | Subtitle | CTA | Category | Layout |\n")
        f.write("|---|------|----------|----------|-----|----------|--------|\n")
        for r in results:
            f.write("| %d | `%s` | %s | %s | %s | %s | %s |\n" % (
                r["num"], r["file"], r["headline"], r["subtitle"],
                r["cta"], r["cat"], r["style"]))
    print("Catalog: " + md_path)


if __name__ == "__main__":
    main()
