"""
test_ai_providers.py
Quick test to verify Nova Lite and Ollama availability for social media content generation.
Run: python dev4-tests/test_ai_providers.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_provider_availability():
    """Check which AI providers are reachable."""
    print("=" * 60)
    print("AI Provider Availability Check")
    print("=" * 60)
    try:
        from ai_provider import get_available_providers
        providers = get_available_providers()
        for p in providers:
            status = "AVAILABLE" if p["available"] else "UNAVAILABLE"
            print(f"  {p['name']:10s} [{status}] {p['reason']}")
        return providers
    except Exception as e:
        print(f"  ERROR: Could not check providers: {e}")
        return []


def test_social_content_generation():
    """Test generating a social media caption with available provider."""
    print("\n" + "=" * 60)
    print("Social Media Caption Generation Test")
    print("=" * 60)

    prompt = (
        "Write a short Twitter/X post (max 280 chars) promoting an AI-powered "
        "SEO tool called AI1stSEO that helps brands get cited by ChatGPT and "
        "other AI engines. Include 2 relevant hashtags. Be concise and punchy."
    )

    try:
        from ai_provider import generate
        print("  Calling Nova Lite...")
        result = generate(prompt, provider="nova")
        print(f"  Nova response ({len(result)} chars):")
        print(f"    {result[:300]}")
        return True
    except Exception as e:
        print(f"  Nova failed: {e}")
        try:
            print("  Trying Ollama fallback...")
            from ai_provider import generate
            result = generate(prompt, provider="ollama")
            print(f"  Ollama response ({len(result)} chars):")
            print(f"    {result[:300]}")
            return True
        except Exception as e2:
            print(f"  Ollama also failed: {e2}")
            return False


def test_multimodal_capability():
    """Document what IS and IS NOT possible with current models."""
    print("\n" + "=" * 60)
    print("Multi-Modal Capability Matrix")
    print("=" * 60)
    capabilities = {
        "Nova Lite (Bedrock)": {
            "text_generation": True,
            "image_generation": False,
            "video_generation": False,
            "image_understanding": False,
            "note": "Text-only model. Use Nova Canvas for images, Nova Reel for video.",
        },
        "Ollama (qwen3:30b)": {
            "text_generation": True,
            "image_generation": False,
            "video_generation": False,
            "image_understanding": False,
            "note": "Text-only LLM. No multi-modal support in current config.",
        },
    }
    for model, caps in capabilities.items():
        print(f"\n  {model}:")
        for k, v in caps.items():
            if k == "note":
                print(f"    Note: {v}")
            else:
                icon = "YES" if v else "NO"
                print(f"    {k:25s} {icon}")


if __name__ == "__main__":
    providers = test_provider_availability()
    gen_ok = test_social_content_generation()
    test_multimodal_capability()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    available = [p["name"] for p in providers if p.get("available")]
    print(f"  Available providers: {', '.join(available) if available else 'NONE'}")
    print(f"  Text generation: {'PASS' if gen_ok else 'FAIL (no provider reachable)'}")
    print(f"  Image generation: NOT SUPPORTED (need Nova Canvas or DALL-E)")
    print(f"  Video generation: NOT SUPPORTED (need Nova Reel or Runway)")
