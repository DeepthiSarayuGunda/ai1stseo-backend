"""
final_features/outreach_email.py
Partnership outreach email generator.

Usage:
    from final_features.outreach_email import generate_outreach_email
    result = generate_outreach_email("Jane Smith", "Acme Marketing")
"""

import random
from datetime import datetime, timezone

_SUBJECT_LINES = [
    "Partnership Opportunity — AI-Powered SEO for {organization}",
    "Collaboration Idea: SEO Growth for {organization}",
    "Quick Question for {name} at {organization}",
    "Let's Talk SEO — {organization} x AI1stSEO",
]

_TEMPLATES = [
    {
        "body": (
            "Hi {name},\n\n"
            "I came across {organization} and was impressed by what your team is building. "
            "I'm reaching out because I think there's a strong opportunity for us to collaborate.\n\n"
            "At AI1stSEO, we help businesses improve their search visibility using AI-powered "
            "optimization. Our platform automates keyword research, content scoring, and "
            "competitive analysis — saving teams 10+ hours per week.\n\n"
            "Here's what a partnership could look like:\n"
            "  • Co-branded SEO audit for {organization}'s audience\n"
            "  • Joint webinar on AI-driven content strategy\n"
            "  • Mutual referral program with revenue share\n\n"
            "Would you be open to a 15-minute call this week to explore this?\n\n"
            "Best,\n"
            "The AI1stSEO Team\n"
            "https://ai1stseo.com"
        ),
    },
    {
        "body": (
            "Hi {name},\n\n"
            "I've been following {organization}'s work and I think we could create "
            "something valuable together.\n\n"
            "We specialize in AI-powered SEO — helping businesses rank higher, faster, "
            "with less manual effort. Our clients typically see 40-60% improvement in "
            "organic traffic within 90 days.\n\n"
            "I'd love to explore how we could support {organization}:\n"
            "  • Free SEO health check for your website\n"
            "  • Custom content strategy powered by AI analysis\n"
            "  • Ongoing optimization with monthly performance reports\n\n"
            "No pressure — just a quick conversation to see if there's a fit.\n\n"
            "Looking forward to hearing from you,\n"
            "The AI1stSEO Team\n"
            "https://ai1stseo.com"
        ),
    },
]


def generate_outreach_email(name: str, organization: str) -> dict:
    """Generate a professional partnership outreach email.

    Args:
        name: Contact person's name.
        organization: Their company/organization name.

    Returns:
        {
            "success": bool,
            "subject": str,
            "body": str,
            "to_name": str,
            "to_organization": str,
            "generated_at": str,
        }
    """
    if not name or not name.strip():
        return {"success": False, "error": "Name is required"}
    if not organization or not organization.strip():
        return {"success": False, "error": "Organization is required"}

    name = name.strip()
    organization = organization.strip()

    subject = random.choice(_SUBJECT_LINES).format(name=name, organization=organization)
    template = random.choice(_TEMPLATES)
    body = template["body"].format(name=name, organization=organization)

    return {
        "success": True,
        "subject": subject,
        "body": body,
        "to_name": name,
        "to_organization": organization,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
