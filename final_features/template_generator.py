"""
final_features/template_generator.py
Content template generator — creates structured social post templates.

Supports two styles:
  - "professional" (LinkedIn-style, clean, no emoji)
  - "engaging" (Instagram/Reels-style, emoji-rich)

Usage:
    from final_features.template_generator import generate_template
    result = generate_template("AI-powered SEO", style="engaging")
"""

import random


# ---------------------------------------------------------------------------
# Professional style (LinkedIn)
# ---------------------------------------------------------------------------

_PRO_HOOKS = [
    "{topic} is reshaping how businesses compete online",
    "The data is clear: {topic} delivers measurable ROI",
    "Three lessons from implementing {topic} at scale",
    "Why forward-thinking teams are investing in {topic}",
    "{topic}: what the research actually shows",
]

_PRO_BULLET_SETS = [
    [
        "Automate keyword research to focus on high-intent terms",
        "Use data-driven content scoring to prioritize what works",
        "Implement structured reporting for stakeholder visibility",
        "Build repeatable workflows that scale with your team",
    ],
    [
        "Start with a competitive audit to identify gaps",
        "Align content strategy with business objectives",
        "Measure leading indicators, not just traffic",
        "Iterate monthly based on performance data",
        "Document processes so the team can execute independently",
    ],
    [
        "Map your content to each stage of the buyer journey",
        "Prioritize topics with clear commercial intent",
        "Invest in technical SEO foundations before scaling content",
        "Track attribution from organic search to conversion",
    ],
]

_PRO_CTAS = [
    "What strategies have worked for your team? Share in the comments.",
    "Follow for more insights on {topic} and digital growth.",
    "Agree or disagree? I'd love to hear your perspective.",
    "Connect with me to discuss how {topic} can work for your business.",
]

# ---------------------------------------------------------------------------
# Engaging style (Instagram / Reels)
# ---------------------------------------------------------------------------

_ENG_HOOKS = [
    "🔥 {topic} is changing the game — here's what you need to know",
    "🚀 Want to master {topic}? Start with these tips",
    "⚡ Stop ignoring {topic}. It's costing you growth",
    "💡 Most people get {topic} wrong. Here's the truth",
    "🎯 The secret to {topic} that nobody talks about",
    "📈 {topic} just got easier — here's how",
]

_ENG_BULLET_SETS = [
    [
        "🤖 Automate keyword research — let AI do the heavy lifting",
        "📝 Generate content faster without sacrificing quality",
        "📊 Improve rankings with data, not guesswork",
    ],
    [
        "⏰ Save 10+ hours per week with automation tools",
        "🎯 Focus on what actually moves the needle",
        "📈 Track results weekly and double down on winners",
    ],
    [
        "💪 Build systems that scale without burning out",
        "✨ Quality over quantity — every single time",
        "🤖 Let AI handle the repetitive work for you",
    ],
    [
        "👀 Understand your audience before creating anything",
        "🔧 Solve real problems people actually have",
        "📱 Show up where your audience already hangs out",
        "🔄 Repurpose one piece of content across 5 platforms",
    ],
]

_ENG_CTAS = [
    "👉 Follow for more {topic} tips 🔥",
    "💬 Drop a comment if you want a deep dive!",
    "🔔 Save this and share with someone who needs it ❤️",
    "📩 DM me '{topic}' for a free resource 🎁",
    "❤️ Like + Follow for daily {topic} insights ✨",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_template(topic: str, style: str = "engaging") -> dict:
    """Generate a structured content template for a topic.

    Args:
        topic: The subject matter.
        style: "professional" (LinkedIn) or "engaging" (Instagram/Reels).

    Returns:
        {
            "success": bool,
            "topic": str,
            "style": str,
            "hook": str,
            "bullets": list[str],
            "cta": str,
            "full_text": str,
        }
    """
    if not topic or not topic.strip():
        return {"success": False, "error": "Topic is required"}

    topic = topic.strip()
    style = style.strip().lower() if style else "engaging"

    if style == "professional":
        hooks, bullet_sets, ctas = _PRO_HOOKS, _PRO_BULLET_SETS, _PRO_CTAS
    else:
        hooks, bullet_sets, ctas = _ENG_HOOKS, _ENG_BULLET_SETS, _ENG_CTAS
        style = "engaging"

    hook = random.choice(hooks).format(topic=topic)
    bullets = random.choice(bullet_sets)
    cta = random.choice(ctas).format(topic=topic)

    if style == "engaging":
        bullet_text = "\n".join(bullets)
    else:
        bullet_text = "\n".join("  - " + b for b in bullets)

    full_text = hook + "\n\n" + bullet_text + "\n\n" + cta

    return {
        "success": True,
        "topic": topic,
        "style": style,
        "hook": hook,
        "bullets": bullets,
        "cta": cta,
        "full_text": full_text,
    }
