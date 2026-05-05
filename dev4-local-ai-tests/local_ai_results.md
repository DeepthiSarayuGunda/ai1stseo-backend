# Local AI Image/Video Generation — Test Results

**Date:** April 2, 2026 (updated)
**Tester:** Dev 4 (Tabasum)
**Status:** ✅ SUCCESS — images, video, and final banners with text generated

---

## Server Info

| Property | Value |
|----------|-------|
| Server | `https://comfy.aisomad.ai` |
| ComfyUI version | 0.3.57 |
| GPU | Tesla P40 (24 GB VRAM) |
| PyTorch | 2.6.0+cu124 |
| RAM | 96 GB total |

---

## Final Outputs (Demo-Ready)

### Final Banners (AI background + clean text overlay)

| File | Description | Size |
|------|-------------|------|
| `final_banner_1.png` | SEO headline banner — "Boost Your SEO" + subtitle + CTA pill | 888 KB |
| `final_banner_2.png` | Social stats post — "3X More Traffic" + features + brand bar | 840 KB |

**Method:** SDXL generates text-free backgrounds → Pillow adds crisp, readable text with proper fonts, shadows, and layout. This two-step approach produces sharp, professional results that SDXL alone cannot achieve.

### Background Images (text-free, for reuse)

| File | Description | Size | Gen Time |
|------|-------------|------|----------|
| `bg_seo_banner.png` | Blue/white gradient, geometric shapes, empty center | 969 KB | 83.3s |
| `bg_social_post.png` | Blue-to-teal gradient, data viz elements, clean upper area | 852 KB | 80.3s |

### Raw SDXL Images (previous round)

| File | Description | Size | Gen Time |
|------|-------------|------|----------|
| `seo_banner_sdxl.png` | SEO banner (text attempted in prompt — garbled) | 1,191 KB | 175.6s |
| `social_post_sdxl.png` | Social media graphic | 1,289 KB | 67.9s |
| `dashboard_ui_sdxl.png` | Dashboard UI graphic | 1,175 KB | 67.9s |

### Video

| File | Description | Size | Gen Time |
|------|-------------|------|----------|
| `svd_video_test.webp` | Animated banner (14 frames, 1024×576, 6fps) | 504 KB | 493s |

---

## Quality Comparison: Before vs After

| Aspect | Before (SDXL with text in prompt) | After (SDXL bg + Pillow text) |
|--------|-----------------------------------|-------------------------------|
| Text readability | ❌ Garbled, unreadable | ✅ Sharp, crisp, perfect |
| Font control | ❌ None | ✅ Full (Arial Bold, Calibri, Segoe UI, Impact) |
| Layout control | ❌ Random | ✅ Precise positioning, centered, aligned |
| Background quality | ✅ Good | ✅ Better (optimized prompts, no text artifacts) |
| Professional look | ⚠️ Mediocre | ✅ Demo-ready |
| Reusability | ❌ One-off | ✅ Backgrounds reusable with different text |

---

## Improvement Details

### What changed:
1. **Prompts optimized** — explicitly request "no text, no letters, no words" + "empty space for text"
2. **Negative prompts** — actively suppress text/typography/watermark generation
3. **Better sampler** — switched from euler/normal to dpmpp_2m/karras (better detail)
4. **Higher CFG** — 7.5 instead of 7.0 (stronger prompt adherence)
5. **More steps** — 30 instead of 25 (finer detail)
6. **Text overlay** — Pillow renders text with system fonts, drop shadows, semi-transparent backgrounds, and proper layout

### Text overlay features:
- Drop shadows for readability on any background
- Semi-transparent dark overlay boxes behind text
- Centered alignment with proper spacing
- Multiple font sizes for hierarchy (headline / subtitle / CTA)
- Brand bar at bottom
- CTA pill button with rounded corners

---

## Models Available on Server

### Image Generation
| Model | File | Tested |
|-------|------|--------|
| SDXL Base 1.0 | `SDXL/sd_xl_base_1.0.safetensors` | ✅ Yes |
| SDXL Base 1.0 (0.9 VAE) | `SDXL/sd_xl_base_1.0_0.9vae.safetensors` | No |
| SD 2.1 | `SD2.1/v2-1_768-ema-pruned.safetensors` | No |
| 4x Upscaler | `upscale/x4-upscaler-ema.safetensors` | No |

### Video Generation
| Model | File | Tested |
|-------|------|--------|
| SVD XT | `SVD/svd_xt.safetensors` | ✅ Yes |
| LTX Video 2B | `LTXV/ltx-video-2b-v0.9.safetensors` | No |
| Wan 2.2 I2V 14B | `wan2.2_i2v_*_14B_fp8_scaled.safetensors` | No |
| Wan 2.2 T2V 5B | `wan2.2_ti2v_5B_fp16.safetensors` | No |

### Not Available
- FLUX Schnell — not installed

---

## Recommendation

**This method is suitable for demo.** The two-step approach (SDXL background + Pillow text overlay) produces professional, sharp social media graphics with fully readable text.

**For production workflow:**
1. Generate backgrounds in batch (can pre-generate a library)
2. Apply text overlays dynamically per post
3. Backgrounds are reusable — same background, different text for each post
4. Text overlay script runs instantly (< 1 second)

**To further improve:**
- Ask server admin to install FLUX Schnell for faster/higher quality backgrounds
- Add more text templates (Instagram story, LinkedIn post, Twitter card)
- Use the 4x upscaler model for higher resolution output

---

## Files in dev4-local-ai-tests/

| File | Purpose |
|------|---------|
| `comfy_test.py` | Main ComfyUI test script |
| `gen_backgrounds.py` | Generate text-free backgrounds via SDXL |
| `add_text_overlay.py` | Add clean text to backgrounds using Pillow |
| `upload_for_svd.py` | Upload image for SVD video generation |
| `svd_test.py` | SVD video generation test |
| `local_ai_results.md` | This report |
| `outputs/` | All generated images and video |

No existing project files were modified.
