# Task F: Nova Lite & Ollama — Multi-Modal Content Pipeline Evaluation

## Environment Check

### Amazon Nova Lite (via Bedrock)
- **Available:** Yes — `ai_provider.py` has working Bedrock integration
- **Model:** `us.amazon.nova-lite-v1:0`
- **Access:** Via boto3 `bedrock-runtime` client (requires AWS credentials/IAM role)
- **Current use:** Content generation in `content_generator.py`

### Ollama
- **Available:** Yes — `ai_provider.py` connects to `https://ollama.sageaios.com`
- **Model:** `qwen3:30b-a3b`
- **Access:** Direct HTTPS API calls
- **Current use:** Fallback LLM for content generation

---

## Capability Assessment

### Text Generation

| Capability | Nova Lite | Ollama (qwen3:30b) |
|-----------|-----------|---------------------|
| Text generation | ✅ Yes | ✅ Yes |
| FAQ generation | ✅ Yes | ✅ Yes |
| Social post drafting | ✅ Yes | ✅ Yes |
| Content scoring | ✅ Yes | ✅ Yes |
| Structured output (JSON) | ✅ Yes | ✅ Yes |
| Max tokens | 1024 (configured) | Model-dependent |
| Latency | ~2-5s | ~5-15s (remote) |
| Cost | ~$0.06/1M input tokens | Free (self-hosted) |

### Image Generation

| Capability | Nova Lite | Ollama |
|-----------|-----------|--------|
| Image generation | ❌ NO | ❌ NO |
| Image understanding | ⚠️ Limited | ⚠️ Model-dependent |

**IMPORTANT CLARIFICATION:**
- Nova Lite is a TEXT model. It does NOT generate images.
- Amazon has a separate model called "Nova Canvas" for image generation, but it is NOT the same as Nova Lite and is not currently configured in this project.
- Ollama runs open-source LLMs (text models). It does NOT generate images.
- Neither Nova Lite nor Ollama (qwen3) can generate videos.

### Video Generation

| Capability | Nova Lite | Ollama |
|-----------|-----------|--------|
| Video generation | ❌ NO | ❌ NO |
| Video understanding | ❌ NO | ❌ NO |

**Amazon Nova Reel** is Amazon's video generation model, but it is a completely separate service from Nova Lite and is not available in this project's current Bedrock configuration.

---

## What IS Possible for Social Media Pipeline

Both Nova Lite and Ollama CAN help with the text side of social media content:

1. **Generate post captions** — Already working via `content_generator.py`
2. **Generate hashtag suggestions** — Can be added as a prompt
3. **Generate FAQ content with schema** — Already implemented
4. **Adapt content per platform** — Shorten for Twitter, expand for LinkedIn
5. **Generate alt text for images** — If image understanding is enabled
6. **Content quality scoring** — Via Samarveer's `/api/content-score`

## What Requires External Tools

For actual image/video generation for social media posts:

| Need | Tool | Cost | Integration |
|------|------|------|-------------|
| Image generation | Amazon Nova Canvas (Bedrock) | ~$0.04/image | boto3 bedrock-runtime |
| Image generation | DALL-E 3 (OpenAI) | $0.04-0.12/image | openai library |
| Image generation | Stable Diffusion (self-hosted) | Free (GPU needed) | API call |
| Video generation | Amazon Nova Reel (Bedrock) | ~$0.80/6s video | boto3 bedrock-runtime |
| Video generation | Runway ML | $12-76/month | REST API |
| Stock images | Unsplash API | Free (with attribution) | REST API |

---

## Comparison for Demo Use

| Criterion | Nova Lite | Ollama (qwen3:30b) |
|-----------|-----------|---------------------|
| Speed | ⭐⭐⭐⭐ (~2-5s) | ⭐⭐ (~5-15s) |
| Cost | ⭐⭐⭐ ($0.06/1M tokens) | ⭐⭐⭐⭐⭐ (free) |
| Quality | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Reliability | ⭐⭐⭐⭐⭐ (AWS managed) | ⭐⭐⭐ (depends on homelab) |
| Image gen | ❌ | ❌ |
| Video gen | ❌ | ❌ |
| Setup | Already configured | Already configured |

**Recommended for demo:** Nova Lite — faster, more reliable, already the primary provider. Use Ollama as fallback (already configured in `ai_provider.py`).

---

## Test Script

A test script is available at `dev4-tests/test_ai_providers.py` to verify both providers are accessible and can generate social media content.

---

## Honest Summary

- Both Nova Lite and Ollama are TEXT-ONLY models in this project
- Neither can generate images or videos
- For image generation, Amazon Nova Canvas or DALL-E 3 would need to be added
- For video generation, Amazon Nova Reel or Runway ML would need to be added
- The current pipeline is strong for text content generation (captions, FAQs, comparisons)
- Image/video generation is a separate feature that requires additional services and budget
