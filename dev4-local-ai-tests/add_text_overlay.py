"""
add_text_overlay.py — Add clean, readable text to AI-generated background images.
Uses Pillow (PIL) for text rendering with proper fonts.
No credentials needed — works on local files only.

Usage: python dev4-local-ai-tests/add_text_overlay.py
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(SCRIPT_DIR, "outputs")
FONTS_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def get_font(name, size):
    """Load a system font by filename."""
    path = os.path.join(FONTS_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    # Fallback
    return ImageFont.load_default()


def draw_text_with_shadow(draw, position, text, font, fill, shadow_color, shadow_offset=3):
    """Draw text with a drop shadow for readability."""
    x, y = position
    # Shadow
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    # Main text
    draw.text((x, y), text, font=font, fill=fill)


def draw_text_with_background(draw, position, text, font, text_color, bg_color, padding=20):
    """Draw text with a semi-transparent background box."""
    x, y = position
    bbox = draw.textbbox((x, y), text, font=font)
    # Draw background rectangle with padding
    draw.rectangle(
        [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
        fill=bg_color,
    )
    # Draw text
    draw.text((x, y), text, font=font, fill=text_color)


def create_banner_1():
    """
    Banner 1: SEO marketing banner with headline + subtitle.
    Uses bg_seo_banner.png as background.
    """
    bg_path = os.path.join(OUTPUTS_DIR, "bg_seo_banner.png")
    if not os.path.exists(bg_path):
        print(f"  SKIP: {bg_path} not found")
        return None

    img = Image.open(bg_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Semi-transparent dark overlay in center for text readability
    w, h = img.size
    box_top = int(h * 0.28)
    box_bottom = int(h * 0.72)
    draw.rectangle(
        [int(w * 0.08), box_top, int(w * 0.92), box_bottom],
        fill=(0, 0, 0, 140),
    )

    # Headline
    font_headline = get_font("arialbd.ttf", 72)
    font_subtitle = get_font("calibrib.ttf", 36)
    font_cta = get_font("segoeuib.ttf", 28)

    headline = "Boost Your SEO"
    subtitle = "AI-Powered Insights for Smarter Rankings"
    cta = "ai1stseo.com"

    # Center headline
    hbox = draw.textbbox((0, 0), headline, font=font_headline)
    hw = hbox[2] - hbox[0]
    hx = (w - hw) // 2
    hy = box_top + 40
    draw.text((hx, hy), headline, font=font_headline, fill=(255, 255, 255, 255))

    # Center subtitle
    sbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
    sw = sbox[2] - sbox[0]
    sx = (w - sw) // 2
    sy = hy + 100
    draw.text((sx, sy), subtitle, font=font_subtitle, fill=(200, 220, 255, 240))

    # CTA / brand at bottom of box
    cbox = draw.textbbox((0, 0), cta, font=font_cta)
    cw = cbox[2] - cbox[0]
    cx = (w - cw) // 2
    cy = box_bottom - 60
    # CTA pill background
    pill_pad = 16
    draw.rounded_rectangle(
        [cx - pill_pad * 2, cy - pill_pad, cx + cw + pill_pad * 2, cy + 34 + pill_pad],
        radius=20,
        fill=(59, 130, 246, 220),
    )
    draw.text((cx, cy), cta, font=font_cta, fill=(255, 255, 255, 255))

    # Composite
    result = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = os.path.join(OUTPUTS_DIR, "final_banner_1.png")
    result.save(out_path, quality=95)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Saved: final_banner_1.png ({size_kb:.0f} KB)")
    return out_path


def create_banner_2():
    """
    Banner 2: Social media post with bold stats + tagline.
    Uses bg_social_post.png as background.
    """
    bg_path = os.path.join(OUTPUTS_DIR, "bg_social_post.png")
    if not os.path.exists(bg_path):
        print(f"  SKIP: {bg_path} not found")
        return None

    img = Image.open(bg_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    w, h = img.size

    # Fonts
    font_big = get_font("impact.ttf", 84)
    font_mid = get_font("arialbd.ttf", 44)
    font_small = get_font("calibrib.ttf", 30)
    font_brand = get_font("segoeuib.ttf", 26)

    # Top section — big stat
    stat_text = "3X More Traffic"
    stat_box = draw.textbbox((0, 0), stat_text, font=font_big)
    stat_w = stat_box[2] - stat_box[0]
    stat_x = (w - stat_w) // 2
    stat_y = int(h * 0.18)

    # Glow/shadow behind stat
    draw.text((stat_x + 3, stat_y + 3), stat_text, font=font_big, fill=(0, 0, 0, 160))
    draw.text((stat_x, stat_y), stat_text, font=font_big, fill=(255, 255, 255, 255))

    # Subtitle
    sub_text = "with AI-Powered SEO Optimization"
    sub_box = draw.textbbox((0, 0), sub_text, font=font_mid)
    sub_w = sub_box[2] - sub_box[0]
    sub_x = (w - sub_w) // 2
    sub_y = stat_y + 110
    draw.text((sub_x + 2, sub_y + 2), sub_text, font=font_mid, fill=(0, 0, 0, 120))
    draw.text((sub_x, sub_y), sub_text, font=font_mid, fill=(220, 240, 255, 255))

    # Divider line
    line_y = sub_y + 80
    draw.line(
        [(w * 0.25, line_y), (w * 0.75, line_y)],
        fill=(255, 255, 255, 100),
        width=2,
    )

    # Feature bullets
    features = [
        "Smart Keyword Analysis",
        "Real-Time Rank Tracking",
        "AI Content Recommendations",
    ]
    feat_y = line_y + 30
    for feat in features:
        feat_text = f"  {feat}"
        fbox = draw.textbbox((0, 0), feat_text, font=font_small)
        fw = fbox[2] - fbox[0]
        fx = (w - fw) // 2
        draw.text((fx + 2, feat_y + 2), feat_text, font=font_small, fill=(0, 0, 0, 100))
        draw.text((fx, feat_y), feat_text, font=font_small, fill=(200, 230, 255, 230))
        feat_y += 50

    # Brand bar at bottom
    bar_y = int(h * 0.88)
    draw.rectangle([0, bar_y, w, h], fill=(0, 0, 0, 150))
    brand = "ai1stseo.com  |  AI-Powered SEO Platform"
    bbox = draw.textbbox((0, 0), brand, font=font_brand)
    bw = bbox[2] - bbox[0]
    bx = (w - bw) // 2
    by = bar_y + 20
    draw.text((bx, by), brand, font=font_brand, fill=(180, 200, 255, 220))

    # Composite
    result = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = os.path.join(OUTPUTS_DIR, "final_banner_2.png")
    result.save(out_path, quality=95)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Saved: final_banner_2.png ({size_kb:.0f} KB)")
    return out_path


def main():
    print("=" * 60)
    print("TEXT OVERLAY — Creating final social media banners")
    print("=" * 60)

    print("\nBanner 1: SEO headline banner")
    b1 = create_banner_1()

    print("\nBanner 2: Social media stats post")
    b2 = create_banner_2()

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    if b1:
        print(f"  final_banner_1.png — headline + subtitle + CTA")
    if b2:
        print(f"  final_banner_2.png — stats + features + brand bar")
    print(f"  Output dir: {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
