#!/usr/bin/env python3
"""REST API for the generic Directory module (Sports, Tools, Brands, etc.).

Blueprint: /api/dir/*
Completely isolated — does NOT touch existing /api/directory/* routes.

Endpoints:
  GET    /api/dir/categories                  — list all categories
  GET    /api/dir/categories/<slug>           — single category + items
  POST   /api/dir/categories                  — create category (admin)
  PUT    /api/dir/categories/<slug>           — update category (admin)
  DELETE /api/dir/categories/<slug>           — delete category (admin)

  GET    /api/dir/categories/<slug>/items     — items with filters/sort/pagination
  GET    /api/dir/categories/<slug>/items/<item_slug>  — single item detail
  POST   /api/dir/categories/<slug>/items     — create item (admin)
  PUT    /api/dir/categories/<slug>/items/<item_slug>  — update item (admin)
  DELETE /api/dir/categories/<slug>/items/<item_slug>  — delete item (admin)
  POST   /api/dir/categories/<slug>/items/bulk — bulk upsert items (admin)

  GET    /api/dir/trending                    — trending items across all categories
  GET    /api/dir/search?q=...                — search items globally or by category
  GET    /api/dir/tags                        — all available tags
  GET    /api/dir/stats                       — overview stats for dashboard
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

dir_bp = Blueprint('dir_module', __name__, url_prefix='/api/dir')


def _err(msg, code=400):
    return jsonify({'error': msg}), code


def _ok(data, code=200):
    return jsonify(data), code


# ── Categories ────────────────────────────────────────────────────────────────

@dir_bp.route('/categories', methods=['GET'])
def list_categories():
    """List all active directory categories."""
    try:
        from directory.directory_db import get_categories
        active_only = request.args.get('all') != 'true'
        cats = get_categories(active_only=active_only)
        return _ok({'categories': cats, 'count': len(cats)})
    except Exception as e:
        logger.exception("list_categories failed")
        return _err(f'Failed to load categories: {e}', 500)


@dir_bp.route('/categories/<slug>', methods=['GET'])
def get_category(slug):
    """Get a single category by slug, with optional item preview."""
    try:
        from directory.directory_db import get_category_by_slug, get_items
        cat = get_category_by_slug(slug)
        if not cat:
            return _err('Category not found', 404)
        # Include a preview of top items
        preview_limit = int(request.args.get('preview', 10))
        result = get_items(slug, status='active', sort_by='ranking', limit=preview_limit)
        cat['items_preview'] = result['items']
        return _ok(cat)
    except Exception as e:
        logger.exception("get_category failed")
        return _err(f'Failed to load category: {e}', 500)


@dir_bp.route('/categories', methods=['POST'])
def create_category_endpoint():
    """Create a new directory category."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('slug'):
        return _err('name and slug are required')
    try:
        from directory.directory_db import create_category
        cat = create_category(
            name=data['name'], slug=data['slug'],
            description=data.get('description', ''),
            icon=data.get('icon', ''),
            sort_order=data.get('sort_order', 0),
            meta_json=data.get('meta_json'),
        )
        return _ok({'category': cat, 'message': 'Category created'}, 201)
    except Exception as e:
        logger.exception("create_category failed")
        return _err(f'Failed to create category: {e}', 500)


@dir_bp.route('/categories/<slug>', methods=['PUT'])
def update_category_endpoint(slug):
    """Update an existing category."""
    data = request.get_json()
    if not data:
        return _err('Request body required')
    try:
        from directory.directory_db import update_category
        cat = update_category(slug, data)
        if not cat:
            return _err('Category not found', 404)
        return _ok({'category': cat, 'message': 'Category updated'})
    except Exception as e:
        logger.exception("update_category failed")
        return _err(f'Failed to update category: {e}', 500)


@dir_bp.route('/categories/<slug>', methods=['DELETE'])
def delete_category_endpoint(slug):
    """Delete a category and all its items."""
    try:
        from directory.directory_db import delete_category
        deleted = delete_category(slug)
        if not deleted:
            return _err('Category not found', 404)
        return _ok({'message': 'Category deleted'})
    except Exception as e:
        logger.exception("delete_category failed")
        return _err(f'Failed to delete category: {e}', 500)


# ── Items ─────────────────────────────────────────────────────────────────────

@dir_bp.route('/categories/<slug>/items', methods=['GET'])
def list_items(slug):
    """Get items for a category with filtering, sorting, and pagination.

    Query params:
      status   — filter by status (active, inactive, draft)
      tag      — filter by tag
      sort     — ranking | trending | rating | name | newest | updated
      order    — asc | desc
      limit    — items per page (default 50, max 200)
      offset   — pagination offset
    """
    try:
        from directory.directory_db import get_items
        status = request.args.get('status')
        tag = request.args.get('tag')
        sort_by = request.args.get('sort', 'ranking')
        order = request.args.get('order', 'asc')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))

        result = get_items(slug, status=status, tag=tag,
                           sort_by=sort_by, order=order,
                           limit=limit, offset=offset)
        if result['category'] is None:
            return _err('Category not found', 404)
        return _ok({
            'items': result['items'],
            'total': result['total'],
            'category': result['category'],
            'limit': limit,
            'offset': offset,
        })
    except Exception as e:
        logger.exception("list_items failed")
        return _err(f'Failed to load items: {e}', 500)


@dir_bp.route('/categories/<slug>/items/<item_slug>', methods=['GET'])
def get_item(slug, item_slug):
    """Get a single item by category slug + item slug."""
    try:
        from directory.directory_db import get_item_by_slug
        item = get_item_by_slug(slug, item_slug)
        if not item:
            return _err('Item not found', 404)
        return _ok(item)
    except Exception as e:
        logger.exception("get_item failed")
        return _err(f'Failed to load item: {e}', 500)


@dir_bp.route('/categories/<slug>/items', methods=['POST'])
def create_item_endpoint(slug):
    """Create a new item in a category."""
    data = request.get_json()
    if not data or not data.get('name'):
        return _err('name is required')
    try:
        from directory.directory_db import create_item
        item = create_item(slug, data)
        if not item:
            return _err('Category not found', 404)
        return _ok({'item': item, 'message': 'Item created'}, 201)
    except Exception as e:
        logger.exception("create_item failed")
        return _err(f'Failed to create item: {e}', 500)


@dir_bp.route('/categories/<slug>/items/<item_slug>', methods=['PUT'])
def update_item_endpoint(slug, item_slug):
    """Update an existing item."""
    data = request.get_json()
    if not data:
        return _err('Request body required')
    try:
        from directory.directory_db import update_item
        item = update_item(slug, item_slug, data)
        if not item:
            return _err('Item not found', 404)
        return _ok({'item': item, 'message': 'Item updated'})
    except Exception as e:
        logger.exception("update_item failed")
        return _err(f'Failed to update item: {e}', 500)


@dir_bp.route('/categories/<slug>/items/<item_slug>', methods=['DELETE'])
def delete_item_endpoint(slug, item_slug):
    """Delete an item."""
    try:
        from directory.directory_db import delete_item
        deleted = delete_item(slug, item_slug)
        if not deleted:
            return _err('Item not found', 404)
        return _ok({'message': 'Item deleted'})
    except Exception as e:
        logger.exception("delete_item failed")
        return _err(f'Failed to delete item: {e}', 500)


@dir_bp.route('/categories/<slug>/items/bulk', methods=['POST'])
def bulk_upsert_endpoint(slug):
    """Bulk insert/update items for a category.

    Body: { "items": [ { "name": "...", ... }, ... ] }
    """
    data = request.get_json()
    if not data or not data.get('items'):
        return _err('items array is required')
    try:
        from directory.directory_db import bulk_upsert_items
        result = bulk_upsert_items(slug, data['items'])
        if result.get('error'):
            return _err(result['error'], 404)
        return _ok(result, 201)
    except Exception as e:
        logger.exception("bulk_upsert failed")
        return _err(f'Bulk upsert failed: {e}', 500)


# ── Trending / Search / Tags / Stats ─────────────────────────────────────────

@dir_bp.route('/trending', methods=['GET'])
def trending():
    """Get trending items across all categories (or scoped to one)."""
    try:
        from directory.directory_db import get_trending_items
        category = request.args.get('category')
        limit = min(int(request.args.get('limit', 20)), 100)
        items = get_trending_items(limit=limit, category_slug=category)
        return _ok({'items': items, 'count': len(items)})
    except Exception as e:
        logger.exception("trending failed")
        return _err(f'Failed to load trending: {e}', 500)


@dir_bp.route('/search', methods=['GET'])
def search():
    """Search items by name, description, or tag.

    Query params: q (required), category (optional), limit
    """
    query = request.args.get('q', '').strip()
    if not query:
        return _err('q parameter is required')
    try:
        from directory.directory_db import search_items
        category = request.args.get('category')
        limit = min(int(request.args.get('limit', 30)), 100)
        items = search_items(query, category_slug=category, limit=limit)
        return _ok({'items': items, 'count': len(items), 'query': query})
    except Exception as e:
        logger.exception("search failed")
        return _err(f'Search failed: {e}', 500)


@dir_bp.route('/tags', methods=['GET'])
def tags():
    """Get all distinct tags, optionally scoped to a category."""
    try:
        from directory.directory_db import get_all_tags
        category = request.args.get('category')
        tag_list = get_all_tags(category_slug=category)
        return _ok({'tags': tag_list, 'count': len(tag_list)})
    except Exception as e:
        logger.exception("tags failed")
        return _err(f'Failed to load tags: {e}', 500)


@dir_bp.route('/stats', methods=['GET'])
def stats():
    """Overview stats: total categories, total items, trending count."""
    try:
        from directory.directory_db import get_categories, get_conn
        import psycopg2.extras
        cats = get_categories(active_only=False)
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT COUNT(*) as total FROM directory_items")
            total_items = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as total FROM directory_items WHERE status = 'active'")
            active_items = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as total FROM directory_items WHERE trending_score > 0")
            trending_count = cur.fetchone()['total']
        return _ok({
            'total_categories': len(cats),
            'total_items': total_items,
            'active_items': active_items,
            'trending_items': trending_count,
        })
    except Exception as e:
        logger.exception("stats failed")
        return _err(f'Failed to load stats: {e}', 500)


# ── Blueprint registration ───────────────────────────────────────────────────

def register_directory_module(app):
    """Register the directory module blueprint with the Flask app."""
    from directory.directory_db import init_directory_tables
    try:
        init_directory_tables()
        logger.info("Directory module tables initialized")
    except Exception as e:
        logger.warning("Directory module table init failed (non-fatal): %s", e)
    app.register_blueprint(dir_bp)
    logger.info("Directory module blueprint registered at /api/dir")
