"""
Brand Sentiment Monitor Tool
Probes AI models for brand sentiment, recommendation strength,
and hallucination detection during daily monitoring.
"""

import re
from datetime import datetime, timezone
from typing import TypedDict, Optional


class SentimentResult(TypedDict):
    brand: str
    dominant_sentiment: str
    sentiment_breakdown: dict
    avg_recommendation_score: float
    hallucination_flags: list
    competitor_mentions: list
    timestamp: str


def check_brand_sentiment(
    brand: str,
    domain: str = '',
    queries: list = None,
) -> SentimentResult:
    """
    Probe AI models for brand sentiment and factual accuracy.

    Args:
        brand: Brand name to check
        domain: Brand's domain (for mention detection)
        queries: Custom queries (defaults to standard brand queries)

    Returns:
        SentimentResult with sentiment, recommendation score, and hallucination flags
    """
    if not queries:
        queries = [
            'What is {} and is it any good?'.format(brand),
            'Would you recommend {} for SEO?'.format(brand),
            'What are the pros and cons of {}?'.format(brand),
        ]

    try:
        from ai_inference import generate
    except ImportError:
        return SentimentResult(
            brand=brand, dominant_sentiment='unknown',
            sentiment_breakdown={'error': 'AI inference not available'},
            avg_recommendation_score=0, hallucination_flags=[],
            competitor_mentions=[], timestamp=datetime.now(timezone.utc).isoformat(),
        )

    sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
    total_rec = 0
    all_hallucinations = []
    all_competitors = set()

    positive_words = ['recommend', 'excellent', 'great', 'powerful', 'effective',
                      'impressive', 'reliable', 'trusted', 'innovative', 'leading',
                      'best', 'top', 'strong', 'valuable']
    negative_words = ['avoid', 'poor', 'weak', 'unreliable', 'expensive', 'limited',
                      'lacking', 'disappointing', 'outdated', 'concern', 'problem']
    seo_brands = ['semrush', 'ahrefs', 'moz', 'surfer', 'clearscope',
                  'brightedge', 'conductor', 'se ranking', 'seoclarity']

    for query in queries[:5]:
        response = generate(query, max_tokens=512, temperature=0.3,
                            triggered_by='brand_sentiment_monitor')
        resp_lower = response.lower()
        brand_lower = brand.lower()

        # Sentiment
        pos = sum(1 for w in positive_words if w in resp_lower)
        neg = sum(1 for w in negative_words if w in resp_lower)
        if pos > neg + 1:
            sentiment_counts['positive'] += 1
        elif neg > pos + 1:
            sentiment_counts['negative'] += 1
        else:
            sentiment_counts['neutral'] += 1

        # Recommendation score
        rec = 50
        if 'recommend' in resp_lower and brand_lower in resp_lower:
            rec = 80
        if 'highly recommend' in resp_lower:
            rec = 95
        if 'not recommend' in resp_lower or 'avoid' in resp_lower:
            rec = 15
        total_rec += rec

        # Competitor mentions
        for comp in seo_brands:
            if comp in resp_lower and comp != brand_lower:
                all_competitors.add(comp)

        # Hallucination flags
        prices = re.findall(r'\$[\d,]+(?:\.\d{2})?(?:/mo| per month)?', response)
        if prices:
            all_hallucinations.append({
                'type': 'pricing_claim', 'claims': prices,
                'query': query[:50],
            })
        years = re.findall(r'(?:founded|launched|since)\s+(?:in\s+)?(\d{4})', resp_lower)
        if years:
            all_hallucinations.append({
                'type': 'date_claim', 'claims': years,
                'query': query[:50],
            })

    dominant = max(sentiment_counts, key=sentiment_counts.get)
    avg_rec = round(total_rec / len(queries), 1) if queries else 0

    return SentimentResult(
        brand=brand,
        dominant_sentiment=dominant,
        sentiment_breakdown=sentiment_counts,
        avg_recommendation_score=avg_rec,
        hallucination_flags=all_hallucinations,
        competitor_mentions=sorted(all_competitors),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


TOOL_SCHEMA = {
    "name": "brand_sentiment",
    "description": "Probe AI models for brand sentiment, recommendation strength, and hallucination detection",
    "input_schema": {
        "type": "object",
        "properties": {
            "brand": {"type": "string", "description": "Brand name to check"},
            "domain": {"type": "string", "description": "Brand's domain"},
        },
        "required": ["brand"],
    },
}
