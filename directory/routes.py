#!/usr/bin/env python3
"""API endpoints for AI Business Directory.

Supports both SQLite (local/default) and DynamoDB (production) backends
via the USE_DYNAMO_DIRECTORY feature flag — same pattern as AEO/GEO modules.

All routes are under /api/directory/* — completely isolated from
GEO Scanner, AEO, OpenClaw, and other existing features.
"""

import os
import json
from flask import Blueprint, request, jsonify

directory_bp = Blueprint('directory', __name__, url_prefix='/api/directory')

# --- Backend selection (same pattern as USE_DYNAMO_AEO) ---
USE_DYNAMO = os.environ.get('USE_DYNAMO_DIRECTORY', 'false').lower() == 'true'

_dir_db = None
_dir_repo = None


def _get_backend():
    """Lazy-init the appropriate backend."""
    global _dir_db, _dir_repo
    if USE_DYNAMO:
        if _dir_repo is None:
            from dynamo.directory_repository import DirectoryRepository
            _dir_repo = DirectoryRepository()
        return _dir_repo
    else:
        if _dir_db is None:
            from directory.database import DirectoryDatabase
            IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
            DB_DIR = '/tmp' if IS_LAMBDA else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _dir_db = DirectoryDatabase(db_path=os.path.join(DB_DIR, 'directory.db'))
        return _dir_db


# ===================== LISTING ENDPOINTS =====================

@directory_bp.route('/listings', methods=['GET'])
def get_listings():
    """Get all listings, optionally filtered by category or search query."""
    backend = _get_backend()
    category = request.args.get('category')
    query = request.args.get('q')
    limit = int(request.args.get('limit', 20))

    if query:
        listings = backend.search_listings(query, limit=limit)
    elif category:
        listings = backend.get_listings_by_category(category, limit=limit)
    else:
        listings = backend.get_all_listings(limit=limit)

    return jsonify({'listings': listings, 'count': len(listings)})


@directory_bp.route('/listings/<slug>', methods=['GET'])
def get_listing(slug):
    """Get a single listing by slug."""
    backend = _get_backend()
    listing = backend.get_listing(slug)
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404
    return jsonify(listing)


@directory_bp.route('/listings', methods=['POST'])
def add_listing():
    """Add a new business listing."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('category'):
        return jsonify({'error': 'name and category are required'}), 400

    backend = _get_backend()
    result = backend.add_listing(data)
    return jsonify({'slug': result, 'message': 'Listing added'}), 201


# ===================== AI CONTENT ENDPOINTS =====================

@directory_bp.route('/listings/<slug>/ai-content', methods=['POST'])
def generate_ai_content(slug):
    """Trigger AI content generation (BLUF + FAQ + schema) for a listing."""
    backend = _get_backend()
    listing = backend.get_listing(slug)
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404

    try:
        from directory.ai_generator import AIContentGenerator
        gen = AIContentGenerator()
        bluf = gen.generate_bluf(listing)
        faqs = gen.generate_faqs(listing)
        listing['ai_summary'] = bluf
        schema = gen.generate_schema_markup(listing, faqs)

        if USE_DYNAMO:
            backend.update_ai_content(
                slug=slug, category=listing['category'],
                ai_summary=bluf, faq_json=json.dumps(faqs),
                schema_markup=schema
            )
        else:
            backend.update_ai_content(
                listing_id=listing['id'],
                ai_summary=bluf, faq_json=json.dumps(faqs),
                schema_markup=schema
            )

        return jsonify({'slug': slug, 'bluf': bluf, 'faqs': faqs, 'schema': schema})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@directory_bp.route('/listings/<slug>/citations', methods=['PUT'])
def update_citations(slug):
    """Update AI citation status for a listing."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Citation data required'}), 400

    backend = _get_backend()
    listing = backend.get_listing(slug)
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404

    if USE_DYNAMO:
        backend.update_citations(slug=slug, category=listing['category'], citations=data)
    else:
        backend.update_citations(listing_id=listing['id'], citations=data)

    return jsonify({'message': 'Citations updated'})


# ===================== CATEGORY ENDPOINTS =====================

@directory_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get all directory categories."""
    backend = _get_backend()
    categories = backend.get_categories()
    return jsonify({'categories': categories})


# ===================== COMPARE ENDPOINT =====================

@directory_bp.route('/compare', methods=['GET'])
def compare_listings():
    """Compare two listings side by side."""
    slug_a = request.args.get('a')
    slug_b = request.args.get('b')
    if not slug_a or not slug_b:
        return jsonify({'error': 'Provide ?a=slug1&b=slug2'}), 400

    backend = _get_backend()

    if USE_DYNAMO and hasattr(backend, 'compare_listings'):
        result = backend.compare_listings(slug_a, slug_b)
        if not result:
            return jsonify({'error': 'One or both listings not found'}), 404
        return jsonify(result)

    listing_a = backend.get_listing(slug_a)
    listing_b = backend.get_listing(slug_b)
    if not listing_a or not listing_b:
        return jsonify({'error': 'One or both listings not found'}), 404

    score_a = (listing_a.get('ai_score', 0) or 0) + (listing_a.get('rating', 0) or 0) * 10
    score_b = (listing_b.get('ai_score', 0) or 0) + (listing_b.get('rating', 0) or 0) * 10

    return jsonify({
        'listing_a': listing_a, 'listing_b': listing_b,
        'winner': listing_a['name'] if score_a >= score_b else listing_b['name'],
        'score_a': score_a, 'score_b': score_b,
    })


# ===================== BATCH OPERATIONS =====================

@directory_bp.route('/scrape', methods=['POST'])
def trigger_scrape():
    """Trigger a scraping job."""
    data = request.get_json() or {}
    categories = data.get('categories')
    city = data.get('city', 'Ottawa')

    try:
        backend = _get_backend()
        from directory.scraper import BusinessScraper
        scraper = BusinessScraper(db=backend if not USE_DYNAMO else None)
        result = scraper.scrape_all(categories=categories, city=city)

        # If using DynamoDB, save scraped results
        if USE_DYNAMO:
            for listing in scraper.results:
                backend.add_listing(listing)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@directory_bp.route('/batch-generate', methods=['POST'])
def batch_generate():
    """Trigger batch AI content generation."""
    data = request.get_json() or {}
    limit = data.get('limit', 50)

    try:
        backend = _get_backend()
        from directory.ai_generator import AIContentGenerator
        gen = AIContentGenerator()

        if USE_DYNAMO:
            listings = backend.get_listings_needing_ai(limit=limit)
            results = []
            for listing in listings:
                try:
                    result = gen.process_listing(listing)
                    backend.update_ai_content(
                        slug=listing['slug'], category=listing['category'],
                        ai_summary=result['bluf'],
                        faq_json=json.dumps(result['faqs']),
                        schema_markup=result['schema']
                    )
                    results.append(result)
                except Exception:
                    pass
        else:
            results = gen.batch_generate(backend, limit=limit)

        return jsonify({'processed': len(results), 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def register_directory_routes(app):
    """Register directory blueprint with the main Flask app."""
    app.register_blueprint(directory_bp)
