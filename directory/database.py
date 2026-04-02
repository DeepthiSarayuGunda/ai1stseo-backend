#!/usr/bin/env python3
"""Database management for AI Business Directory listings.
Uses SQLite locally, designed to migrate to Postgres on homelab."""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
DB_DIR = '/tmp' if IS_LAMBDA else os.path.dirname(os.path.abspath(__file__))


class DirectoryDatabase:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(DB_DIR, 'directory.db')
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                subcategories TEXT,
                address TEXT,
                city TEXT DEFAULT 'Ottawa',
                province TEXT DEFAULT 'ON',
                postal_code TEXT,
                phone TEXT,
                website TEXT,
                latitude REAL,
                longitude REAL,
                rating REAL,
                review_count INTEGER DEFAULT 0,
                price_range TEXT,
                hours_json TEXT,
                ai_summary TEXT,
                faq_json TEXT,
                schema_markup TEXT,
                comparison_tags TEXT,
                freshness_score INTEGER DEFAULT 50,
                ai_score INTEGER DEFAULT 0,
                citation_chatgpt INTEGER DEFAULT 0,
                citation_gemini INTEGER DEFAULT 0,
                citation_perplexity INTEGER DEFAULT 0,
                citation_claude INTEGER DEFAULT 0,
                source TEXT,
                scraped_at TIMESTAMP,
                ai_generated_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                listing_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS scrape_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                category TEXT,
                listings_found INTEGER DEFAULT 0,
                listings_added INTEGER DEFAULT 0,
                errors TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    # --- Listing CRUD ---

    def add_listing(self, data: Dict) -> int:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO listings
            (name, slug, category, subcategories, address, city, province,
             postal_code, phone, website, latitude, longitude, rating,
             review_count, price_range, hours_json, source, scraped_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['name'], data.get('slug', self._slugify(data['name'])),
            data['category'], json.dumps(data.get('subcategories', [])),
            data.get('address'), data.get('city', 'Ottawa'),
            data.get('province', 'ON'), data.get('postal_code'),
            data.get('phone'), data.get('website'),
            data.get('latitude'), data.get('longitude'),
            data.get('rating'), data.get('review_count', 0),
            data.get('price_range'), json.dumps(data.get('hours', {})),
            data.get('source', 'manual'), datetime.utcnow().isoformat()
        ))
        conn.commit()
        lid = c.lastrowid
        conn.close()
        return lid

    def get_listing(self, slug: str) -> Optional[Dict]:
        conn = self.get_connection()
        row = conn.execute('SELECT * FROM listings WHERE slug=?', (slug,)).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_dict(row)

    def get_listings_by_category(self, category: str, limit=10) -> List[Dict]:
        conn = self.get_connection()
        rows = conn.execute(
            'SELECT * FROM listings WHERE category=? ORDER BY ai_score DESC, rating DESC LIMIT ?',
            (category, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def search_listings(self, query: str, limit=20) -> List[Dict]:
        conn = self.get_connection()
        rows = conn.execute(
            'SELECT * FROM listings WHERE name LIKE ? OR category LIKE ? ORDER BY ai_score DESC LIMIT ?',
            (f'%{query}%', f'%{query}%', limit)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def update_ai_content(self, listing_id: int, ai_summary: str, faq_json: str, schema_markup: str):
        conn = self.get_connection()
        conn.execute('''
            UPDATE listings SET ai_summary=?, faq_json=?, schema_markup=?,
            ai_generated_at=?, updated_at=? WHERE id=?
        ''', (ai_summary, faq_json, schema_markup,
              datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), listing_id))
        conn.commit()
        conn.close()

    def update_freshness(self, listing_id: int, score: int):
        conn = self.get_connection()
        conn.execute(
            'UPDATE listings SET freshness_score=?, updated_at=? WHERE id=?',
            (score, datetime.utcnow().isoformat(), listing_id)
        )
        conn.commit()
        conn.close()

    def update_citations(self, listing_id: int, citations: Dict):
        conn = self.get_connection()
        ai_score = sum(1 for v in citations.values() if v) * 25  # 0-100
        conn.execute('''
            UPDATE listings SET citation_chatgpt=?, citation_gemini=?,
            citation_perplexity=?, citation_claude=?, ai_score=?, updated_at=?
            WHERE id=?
        ''', (
            citations.get('chatgpt', 0), citations.get('gemini', 0),
            citations.get('perplexity', 0), citations.get('claude', 0),
            ai_score, datetime.utcnow().isoformat(), listing_id
        ))
        conn.commit()
        conn.close()

    def get_all_listings(self, limit=100) -> List[Dict]:
        conn = self.get_connection()
        rows = conn.execute(
            'SELECT * FROM listings ORDER BY ai_score DESC, rating DESC LIMIT ?', (limit,)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    # --- Categories ---

    def add_category(self, name: str, slug: str, description: str = ''):
        conn = self.get_connection()
        conn.execute(
            'INSERT OR IGNORE INTO categories (name, slug, description) VALUES (?,?,?)',
            (name, slug, description)
        )
        conn.commit()
        conn.close()

    def get_categories(self) -> List[Dict]:
        conn = self.get_connection()
        rows = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Scrape Logs ---

    def log_scrape(self, source: str, category: str, found: int, added: int, errors: str = ''):
        conn = self.get_connection()
        conn.execute(
            'INSERT INTO scrape_logs (source, category, listings_found, listings_added, errors) VALUES (?,?,?,?,?)',
            (source, category, found, added, errors)
        )
        conn.commit()
        conn.close()

    # --- Helpers ---

    def _slugify(self, text: str) -> str:
        import re
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

    def _row_to_dict(self, row) -> Dict:
        d = dict(row)
        for key in ('subcategories', 'hours_json', 'faq_json'):
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
