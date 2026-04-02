#!/usr/bin/env python3
"""API endpoints for AI Business Directory.
Serves listing data so frontend templates populate dynamically."""

import os
import json
from flask import Blueprint, request, jsonify
from directory.database import DirectoryDatabase

directory_bp = Blueprint('directory', __name__, url_prefix='/api/directory')

IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
DB_DIR = '/tmp' if IS_LAMBDA else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dir_db = DirectoryDatabase(db_path=os.path.join(DB_DIR, 'directory.db'))


@directory_bp.route('/listings', methods=['GET'])
def get_listings():
    """Get all listings, optionally filtered by category or search query."""
    category = request.args.get('category')
    query = request.args.get('q')
    limit = int(request.args.get('limit', 20))

    if query:
        listings = dir_db.search_listings(query, limit=limit)
    elif category:
        listings = dir_db.get_listings_by_category(category, limit=limit)
    else:
        listings = dir_db.get_all_listings(limit=limit)

    return jsonify({'listings': listings, 'count': len(listings)})


@directory_bp.route('/listings/<slug>', methods=['GET'])
def get_listing(slug):
    """Get a single listing by slug."""
    listing = dir_db.get_listing(slug)
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404
    return jsonify(listing)


@directory_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get all directory categories."""
    categories = dir_db.get_categories()
    return jsonify({'categories': categories})


@directory_bp.route('/listings', methods=['POST'])
def add_listing():
    """Add a new business listing."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('category'):
        return jsonify({'error': 'name and category are required'}), 400

    listing_id = dir_db.add_listing(data)
    return jsonify({'id': listing_id, 'message': 'Listing added'}), 201


@directory_bp.route('/listings/<int:listing_id>/ai-content', methods=['POST'])
def generate_ai_content(listing_id):
    """Trigger AI content generation for a specific listing."""
    conn = dir_db.get_connection()
    row = conn.execute('SELECT * FROM listings WHERE id=?', (listing_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Listing not found'}), 404

    listing = dir_db._row_to_dict(row)

    try:
        from directory.ai_generator import AIContentGenerator
        gen = AIContentGenerator()
        result = gen.process_listing(listing, db=dir_db)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@directory_bp.route('/listings/<int:listing_id>/citations', methods=['PUT'])
def update_citations(listing_id):
    """Update AI citation status for a listing."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Citation data required'}), 400

    dir_db.update_citations(listing_id, data)
    return jsonify({'message': 'Citations updated'})


@directory_bp.route('/scrape', methods=['POST'])
def trigger_scrape():
    """Trigger a scraping job (for manual/testing use)."""
    data = request.get_json() or {}
    categories = data.get('categories')
    city = data.get('city', 'Ottawa')

    try:
        from directory.scraper import BusinessScraper
        scraper = BusinessScraper(db=dir_db)
        result = scraper.scrape_all(categories=categories, city=city)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@directory_bp.route('/batch-generate', methods=['POST'])
def batch_generate():
    """Trigger batch AI content generation (nightly job endpoint)."""
    data = request.get_json() or {}
    limit = data.get('limit', 50)

    try:
        from directory.ai_generator import AIContentGenerator
        gen = AIContentGenerator()
        results = gen.batch_generate(dir_db, limit=limit)
        return jsonify({'processed': len(results), 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@directory_bp.route('/compare', methods=['GET'])
def compare_listings():
    """Compare two listings side by side."""
    slug_a = request.args.get('a')
    slug_b = request.args.get('b')

    if not slug_a or not slug_b:
        return jsonify({'error': 'Provide ?a=slug1&b=slug2'}), 400

    listing_a = dir_db.get_listing(slug_a)
    listing_b = dir_db.get_listing(slug_b)

    if not listing_a or not listing_b:
        return jsonify({'error': 'One or both listings not found'}), 404

    # Determine winner
    score_a = (listing_a.get('ai_score', 0) or 0) + (listing_a.get('rating', 0) or 0) * 10
    score_b = (listing_b.get('ai_score', 0) or 0) + (listing_b.get('rating', 0) or 0) * 10
    winner = listing_a['name'] if score_a >= score_b else listing_b['name']

    return jsonify({
        'listing_a': listing_a,
        'listing_b': listing_b,
        'winner': winner,
        'score_a': score_a,
        'score_b': score_b
    })


def register_directory_routes(app):
    """Register directory blueprint with the main Flask app."""
    app.register_blueprint(directory_bp)
