#!/usr/bin/env python3
"""Claude API integration for AI Business Directory.
Generates BLUF summaries (40-60 words) and FAQ blocks (5-8 Q&A) per listing.
Designed to run as a nightly batch job."""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Try Bedrock (AWS) first, fall back to Anthropic direct API
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bedrock_helper import bedrock
    HAS_BEDROCK = True
except Exception:
    HAS_BEDROCK = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class AIContentGenerator:
    """Generates AI summaries and FAQ blocks for business listings using Claude."""

    def __init__(self):
        self.model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
        self.client = None
        if HAS_BOTO3:
            try:
                self.client = boto3.client(
                    'bedrock-runtime',
                    region_name=os.environ.get('AWS_REGION', 'us-east-1')
                )
            except Exception as e:
                logger.warning(f"Bedrock client init failed: {e}")

    def generate_bluf(self, listing: Dict) -> str:
        """Generate a BLUF (Bottom Line Up Front) summary — 40-60 words."""
        prompt = f"""Write a BLUF (Bottom Line Up Front) summary for this business listing in exactly 40-60 words.
Be factual, specific, and include key differentiators. Do not use marketing fluff.

Business: {listing['name']}
Category: {listing.get('category', 'business')}
City: {listing.get('city', 'Ottawa')}, {listing.get('province', 'ON')}
Address: {listing.get('address', 'N/A')}
Rating: {listing.get('rating', 'N/A')} ({listing.get('review_count', 0)} reviews)
Price Range: {listing.get('price_range', 'N/A')}

Return ONLY the summary text, no quotes or labels."""

        return self._call_claude(prompt) or self._fallback_bluf(listing)

    def generate_faqs(self, listing: Dict, count: int = 5) -> List[Dict]:
        """Generate FAQ Q&A pairs (5-8) for a business listing."""
        prompt = f"""Generate exactly {count} FAQ questions and answers for this business.
Each Q&A should be something a real customer would ask before visiting.
Include questions about: services, pricing, insurance/payment, hours/location, what makes them different.

Business: {listing['name']}
Category: {listing.get('category', 'business')}
City: {listing.get('city', 'Ottawa')}, {listing.get('province', 'ON')}
Address: {listing.get('address', 'N/A')}
Rating: {listing.get('rating', 'N/A')} ({listing.get('review_count', 0)} reviews)

Return as JSON array: [{{"question": "...", "answer": "..."}}]
Return ONLY the JSON array, no other text."""

        response = self._call_claude(prompt)
        if response:
            try:
                faqs = json.loads(response)
                if isinstance(faqs, list) and len(faqs) > 0:
                    return faqs[:count]
            except json.JSONDecodeError:
                pass
        return self._fallback_faqs(listing, count)

    def generate_schema_markup(self, listing: Dict, faqs: List[Dict]) -> str:
        """Generate JSON-LD schema markup for LocalBusiness + FAQPage."""
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "LocalBusiness",
                    "name": listing['name'],
                    "description": listing.get('ai_summary', ''),
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": listing.get('address', ''),
                        "addressLocality": listing.get('city', 'Ottawa'),
                        "addressRegion": listing.get('province', 'ON'),
                        "postalCode": listing.get('postal_code', ''),
                        "addressCountry": "CA"
                    },
                    "telephone": listing.get('phone', ''),
                    "priceRange": listing.get('price_range', ''),
                },
                {
                    "@type": "FAQPage",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": faq['question'],
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": faq['answer']
                            }
                        } for faq in faqs
                    ]
                }
            ]
        }
        if listing.get('rating'):
            schema["@graph"][0]["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": str(listing['rating']),
                "reviewCount": str(listing.get('review_count', 0))
            }
        return json.dumps(schema, indent=2)

    def process_listing(self, listing: Dict, db=None) -> Dict:
        """Full pipeline: generate BLUF + FAQs + schema for one listing."""
        logger.info(f"Generating AI content for: {listing['name']}")

        bluf = self.generate_bluf(listing)
        faqs = self.generate_faqs(listing)
        listing['ai_summary'] = bluf
        schema = self.generate_schema_markup(listing, faqs)

        if db:
            db.update_ai_content(
                listing_id=listing['id'],
                ai_summary=bluf,
                faq_json=json.dumps(faqs),
                schema_markup=schema
            )
            logger.info(f"  Saved AI content for listing #{listing['id']}")

        return {
            'listing_id': listing.get('id'),
            'name': listing['name'],
            'bluf': bluf,
            'faqs': faqs,
            'schema': schema
        }

    def batch_generate(self, db, limit: int = 50):
        """Nightly batch job: generate AI content for listings missing it."""
        conn = db.get_connection()
        rows = conn.execute(
            'SELECT * FROM listings WHERE ai_summary IS NULL OR ai_summary = "" LIMIT ?',
            (limit,)
        ).fetchall()
        conn.close()

        results = []
        for row in rows:
            listing = db._row_to_dict(row)
            try:
                result = self.process_listing(listing, db=db)
                results.append(result)
            except Exception as e:
                logger.error(f"  Failed for {listing['name']}: {e}")

        logger.info(f"Batch complete: {len(results)}/{len(rows)} listings processed")
        return results

    def _call_claude(self, prompt: str) -> Optional[str]:
        """Call Claude via Bedrock."""
        if not self.client:
            return None
        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            })
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType='application/json'
            )
            result = json.loads(response['body'].read())
            return result.get('content', [{}])[0].get('text', '').strip()
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    def _fallback_bluf(self, listing: Dict) -> str:
        """Fallback BLUF when Claude is unavailable."""
        name = listing['name']
        cat = listing.get('category', 'business')
        city = listing.get('city', 'Ottawa')
        rating = listing.get('rating', 'N/A')
        reviews = listing.get('review_count', 0)
        return (
            f"{name} is a {cat} located in {city}, Ontario. "
            f"Rated {rating} stars based on {reviews} reviews. "
            f"Serving the Ottawa-Gatineau region with professional {cat} services."
        )

    def _fallback_faqs(self, listing: Dict, count: int) -> List[Dict]:
        """Fallback FAQs when Claude is unavailable."""
        name = listing['name']
        cat = listing.get('category', 'business')
        templates = [
            {"question": f"What services does {name} offer?",
             "answer": f"{name} offers a full range of {cat} services in Ottawa. Contact them directly for a complete list of services and pricing."},
            {"question": f"What are {name}'s hours of operation?",
             "answer": f"{name} is open during regular business hours. Call ahead to confirm current hours and availability."},
            {"question": f"Does {name} accept insurance?",
             "answer": f"Contact {name} directly to confirm which insurance plans they accept and whether direct billing is available."},
            {"question": f"How do I book an appointment at {name}?",
             "answer": f"You can book an appointment by calling {name} directly or visiting their website for online booking options."},
            {"question": f"Where is {name} located?",
             "answer": f"{name} is located in Ottawa, Ontario. Check their listing for the exact address and directions."},
            {"question": f"What do customers say about {name}?",
             "answer": f"{name} has a rating of {listing.get('rating', 'N/A')} based on {listing.get('review_count', 0)} reviews."},
            {"question": f"Does {name} offer emergency services?",
             "answer": f"Contact {name} directly to ask about emergency or same-day service availability."},
            {"question": f"Is parking available at {name}?",
             "answer": f"Check with {name} about parking options. Many Ottawa businesses offer street or lot parking nearby."},
        ]
        return templates[:count]


# --- CLI entry point for nightly batch ---
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from directory.database import DirectoryDatabase

    db = DirectoryDatabase()
    gen = AIContentGenerator()

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    results = gen.batch_generate(db, limit=limit)
    print(f"\nGenerated AI content for {len(results)} listings")
