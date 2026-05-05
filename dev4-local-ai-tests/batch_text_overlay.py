"""
batch_text_overlay.py — Generate 10 social media post variations
using existing AI backgrounds + Pillow text overlay.

Reuses: bg_seo_banner.png, bg_social_post.png (no regeneration needed)
Output: final_post_01.png through final_post_10.png

Usage: python dev4-local-ai-tests/batch_text_overlay.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(SCRIPT_DIR, "outputs")
FONTS_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

BG_BANNER = os.path.join(OUTPUTS_DIR, "bg_seo_banner.png")
BG_SOCIAL = os.path.join(OUTPUTS_DIR, "bg_social_post.png")


def font(name, size):
    path = os.path.join(FONTS_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def center_x(draw, text, fnt, canvas_w):
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return (canvas_w - (bbox[2] - bbox[0])) // 2


# --- 10 post variations ---
# Each defines: background, headline, subtitle, cta, accent color, layout style

POSTS = [
    {
        "bg": BG_BANNER,
        "headline": "Boost Your SEO",
        "subtitle": "AI-Powered Insights for Smarter Rankings",
        "cta": "Get Started Free",
        "accent": (59, 130, 246),
        "style": "center_box",
    },
    {
        "bg": BG_SOCIAL,
        "headline": "Rank Higher on Google",
        "subtitle": "Data-Driven Strategies That Actually Work",
        "cta": "ai1stseo.com",
        "accent": (16, 185, 129),
        "style": "center_box",
    },
    {
        "bg": BG_BANNER,
        "headline": "3X More Traffic",
        "subtitle": "Proven AI Optimization for Every Page",
        "cta": "See How It Works",
        "accent": (139, 92, 246),
        "style": "top_heavy",
    },
    {
        "bg": BG_SOCIAL,
        "headline": "AI-Powered Marketing",
        "subtitle": "Automate Your Content Strategy Today",
        "cta": "Start Your Free Trial",
        "accent": (236, 72, 153),
        "style": "top_heavy",
    },
    {
        "bg": BG_BANNER,
        "headline": "Smarter SEO Starts Here",
        "subtitle": "Real-Time Analytics \u2022 Keyword Tracking \u2022 AI Content",
        "cta": "ai1stseo.com",
        "accent": (14, 165, 233),
        "style": "bottom_bar",
    },
    {
        "bg": BG_SOCIAL,
        "headline": "Outrank Your Competition",
        "subtitle": "Intelligent Keyword Analysis & Rank Tracking",
        "cta": "Learn More",
        "accent": (245, 158, 11),
        "style": "bottom_bar",
    },
    {
        "bg": BG_BANNER,
        "headline": "Content That Converts",
        "subtitle": "AI-Generated SEO Content for Maximum Impact",
        "cta": "Try It Now",
        "accent": (34, 197, 94),
        "style": "center_box",
    },
    {
        "bg": BG_SOCIAL,
        "headline": "Your SEO Copilot",
        "subtitle": "From Keywords to Rankings \u2014 Fully Automated",
        "cta": "ai1stseo.com",
        "accent": (99, 102, 241),
        "style": "top_heavy",
    },
    {
        "bg": BG_BANNER,
        "headline": "Stop Guessing. Start Ranking.",
        "subtitle": "AI Tells You Exactly What to Optimize",
        "cta": "Get Your Free Audit",
        "accent": (239, 68, 68),
        "style": "bottom_bar",
    },
    {
        "bg": BG_SOCIAL,
        "headline": "SEO Made Simple",
        "subtitle": "One Platform \u2022 All Your SEO Needs \u2022 Zero Complexity",
        "cta": "Start Free Today",
        "accent": (6, 182, 212),
        "style": "center_box",
    },
]


# --- Layout renderers ---

def render_center_box(img, post):
    """Centered dark box with headline, subtitle, and CTA pill."""
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    accent = post["accent"]

    # Dark box
    box_t, box_b = int(h * 0.25), int(h * 0.75)
    draw.rectangle([int(w * 0.07), box_t, int(w * 0.93), box_b], fill=(0, 0, 0, 145))

    # Accent top stripe
    draw.rectangle([int(w * 0.07), box_t, int(w * 0.93), box_t + 5], fill=(*accent, 220))

    # Headline
    fh = font("arialbd.ttf", 68)
    hx = center_x(draw, post["headline"], fh, w)
    hy = box_t + 50
    draw.text((hx + 2, hy + 2), post["headline"], font=fh, fill=(0, 0, 0, 140))
    draw.text((hx, hy), post["headline"], font=fh, fill=(255, 255, 255, 255))

    # Subtitle
    fs = font("calibrib.ttf", 34)
    sx = center_x(draw, post["subtitle"], fs, w)
    sy = hy + 100
    draw.text((sx, sy), post["subtitle"], font=fs, fill=(200, 220, 255, 230))

    # CTA pill
    fc = font("segoeuib.ttf", 28)
    cta = post["cta"]
    cbbox = draw.textbbox((0, 0), cta, font=fc)
    cw = cbbox[2] - cbbox[0]
    cx = (w - cw) // 2
    cy = box_b - 80
    pad = 18
    draw.rounded_rectangle(
        [cx - pad * 2, cy - pad, cx + cw + pad * 2, cy + 34 + pad],
        radius=22,
        fill=(*accent, 220),
    )
    draw.text((cx, cy), cta, font=fc, fill=(255, 255, 255, 255))

    return Image.alpha_composite(img, overlay)


def render_top_heavy(img, post):
    """Large headline at top, subtitle mid, CTA at bottom with accent bar."""
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    accent = post["accent"]

    # Top gradient overlay
    for y in range(int(h * 0.6)):
        alpha = int(160 * (1 - y / (h * 0.6)))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    # Headline — big and bold
    fh = font("impact.ttf", 80)
    hx = center_x(draw, post["headline"], fh, w)
    hy = int(h * 0.12)
    draw.text((hx + 3, hy + 3), post["headline"], font=fh, fill=(0, 0, 0, 180))
    draw.text((hx, hy), post["headline"], font=fh, fill=(255, 255, 255, 255))

    # Accent underline
    bbox = draw.textbbox((hx, hy), post["headline"], font=fh)
    line_y = bbox[3] + 12
    line_w = bbox[2] - bbox[0]
    line_x = (w - line_w) // 2
    draw.rectangle([line_x, line_y, line_x + line_w, line_y + 4], fill=(*accent, 200))

    # Subtitle
    fs = font("arialbd.ttf", 38)
    sx = center_x(draw, post["subtitle"], fs, w)
    sy = line_y + 30
    draw.text((sx + 2, sy + 2), post["subtitle"], font=fs, fill=(0, 0, 0, 120))
    draw.text((sx, sy), post["subtitle"], font=fs, fill=(220, 235, 255, 245))

    # CTA at bottom
    fc = font("segoeuib.ttf", 26)
    cta = post["cta"]
    cx = center_x(draw, cta, fc, w)
    cy = int(h * 0.85)
    # Pill
    cbbox = draw.textbbox((cx, cy), cta, font=fc)
    pad = 16
    draw.rounded_rectangle(
        [cbbox[0] - pad * 2, cbbox[1] - pad, cbbox[2] + pad * 2, cbbox[3] + pad],
        radius=20,
        fill=(*accent, 210),
    )
    draw.text((cx, cy), cta, font=fc, fill=(255, 255, 255, 255))

    return Image.alpha_composite(img, overlay)


def render_bottom_bar(img, post):
    """Clean top headline with bold bottom bar containing CTA."""
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    accent = post["accent"]

    # Subtle top overlay
    for y in range(int(h * 0.45)):
        alpha = int(130 * (1 - y / (h * 0.45)))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    # Headline
    fh = font("arialbd.ttf", 64)
    hx = center_x(draw, post["headline"], fh, w)
    hy = int(h * 0.15)
    draw.text((hx + 2, hy + 2), post["headline"], font=fh, fill=(0, 0, 0, 150))
    draw.text((hx, hy), post["headline"], font=fh, fill=(255, 255, 255, 255))

    # Subtitle
    fs = font("calibrib.ttf", 32)
    sx = center_x(draw, post["subtitle"], fs, w)
    sy = hy + 90
    draw.text((sx, sy), post["subtitle"], font=fs, fill=(210, 225, 255, 230))

    # Bottom bar
    bar_h = 120
    bar_y = h - bar_h
    draw.rectangle([0, bar_y, w, h], fill=(*accent, 220))

    # CTA in bar
    fc = font("arialbd.ttf", 36)
    cta = post["cta"]
    cx = center_x(draw, cta, fc, w)
    cy = bar_y + (bar_h - 40) // 2
    draw.text((cx, cy), cta, font=fc, fill=(255, 255, 255, 255))

    # Brand small text
    fb = font("calibrib.ttf", 20)
    brand = "ai1stseo.com"
    bx = center_x(draw, brand, fb, w)
    by = cy + 46
    draw.text((bx, by), brand, font=fb, fill=(255, 255, 255, 180))

    return Image.alpha_composite(img, overlay)


RENDERERS = {
    "center_box": render_center_box,
    "top_heavy": render_top_heavy,
    "bottom_bar": render_bottom_bar,
}


def main():
    print("=" * 60)
    print("BATCH TEXT OVERLAY — 10 Social Media Post Variations")
    print("=" * 60)

    # Verify backgrounds exist
    for bg in [BG_BANNER, BG_SOCIAL]:
        if not os.path.exists(bg):
            print(f"ERROR: Background not found: {bg}")
            return

    results = []
    for i, post in enumerate(POSTS, 1):
        num = f"{i:02d}"
        out_name = f"final_post_{num}.png"
        out_path = os.path.join(OUTPUTS_DIR, out_name)

        bg_img = Image.open(post["bg"]).convert("RGBA")
        renderer = RENDERERS[post["style"]]
        result = renderer(bg_img, post).convert("RGB")
        result.save(out_path, quality=95)

        size_kb = os.path.getsize(out_path) / 1024
        bg_name = os.path.basename(post["bg"])
        print(f"  [{num}] {out_name} — {post['headline']}")
        print(f"       bg={bg_name}  style={post['style']}  {size_kb:.0f} KB")
        results.append({
            "file": out_name,
            "headline": post["headline"],
            "subtitle": post["subtitle"],
            "style": post["style"],
            "bg": bg_name,
            "size_kb": round(size_kb),
        })

    print(f"\n{'=' * 60}")
    print(f"DONE — {len(results)} images generated")
    print(f"Output: {OUTPUTS_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
