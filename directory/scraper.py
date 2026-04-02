#!/usr/bin/env python3
"""Business scraping pipeline for AI Business Directory.
Scrapes Ottawa businesses from Google Maps, Yelp, Yellow Pages, BBB, Canada411.
Designed to run on homelab with Scrapy/Playwright."""

import os
import re
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Optional imports — graceful fallback if not installed
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class BusinessScraper:
    """Scrapes business data from multiple sources for Ottawa region."""

    SOURCES = ['google_maps', 'yelp', 'yellow_pages', 'bbb', 'canada411']

    # Default categories to scrape
    CATEGORIES = [
        'dentist', 'lawyer', 'restaurant', 'plumber', 'electrician',
        'accountant', 'chiropractor', 'veterinarian', 'mechanic', 'realtor'
    ]

    def __init__(self, db=None):
        self.db = db
        self.results = []
        self.errors = []

    def scrape_all(self, categories: List[str] = None, city: str = 'Ottawa'):
        """Run full scrape pipeline across all sources and categories."""
        cats = categories or self.CATEGORIES
        total_found = 0
        total_added = 0

        for category in cats:
            logger.info(f"Scraping category: {category} in {city}")
            for source in self.SOURCES:
                try:
                    listings = self._scrape_source(source, category, city)
                    found = len(listings)
                    added = 0
                    for listing in listings:
                        listing['category'] = category
                        listing['source'] = source
                        if self.db:
                            self.db.add_listing(listing)
                            added += 1
                        self.results.append(listing)
                    total_found += found
                    total_added += added
                    if self.db:
                        self.db.log_scrape(source, category, found, added)
                    logger.info(f"  {source}: found {found}, added {added}")
                except Exception as e:
                    err = f"{source}/{category}: {str(e)}"
                    self.errors.append(err)
                    logger.error(f"  Error: {err}")
                    if self.db:
                        self.db.log_scrape(source, category, 0, 0, str(e))
                # Rate limiting
                time.sleep(2)

        logger.info(f"Scrape complete: {total_found} found, {total_added} added, {len(self.errors)} errors")
        return {'found': total_found, 'added': total_added, 'errors': self.errors}

    def _scrape_source(self, source: str, category: str, city: str) -> List[Dict]:
        """Route to the appropriate scraper."""
        scrapers = {
            'google_maps': self._scrape_google_maps,
            'yelp': self._scrape_yelp,
            'yellow_pages': self._scrape_yellow_pages,
            'bbb': self._scrape_bbb,
            'canada411': self._scrape_canada411,
        }
        fn = scrapers.get(source)
        if fn:
            return fn(category, city)
        return []

    def _scrape_google_maps(self, category: str, city: str) -> List[Dict]:
        """Scrape Google Maps results using Playwright (JS-rendered)."""
        if not HAS_PLAYWRIGHT:
            logger.warning("Playwright not installed — skipping Google Maps. pip install playwright && playwright install")
            return []

        results = []
        query = f"{category} in {city} Ontario"
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000)
                page.wait_for_timeout(3000)

                # Scroll to load more results
                for _ in range(3):
                    page.mouse.wheel(0, 1000)
                    page.wait_for_timeout(1500)

                # Extract business cards
                cards = page.query_selector_all('[data-result-index]')
                for card in cards[:10]:
                    try:
                        name_el = card.query_selector('.fontHeadlineSmall, .qBF1Pd')
                        rating_el = card.query_selector('.MW4etd')
                        reviews_el = card.query_selector('.UY7F9')
                        addr_el = card.query_selector('.W4Efsd:last-child')

                        name = name_el.inner_text() if name_el else None
                        if not name:
                            continue

                        rating_text = rating_el.inner_text() if rating_el else '0'
                        reviews_text = reviews_el.inner_text() if reviews_el else '(0)'
                        review_count = int(re.sub(r'[^\d]', '', reviews_text) or 0)

                        results.append({
                            'name': name.strip(),
                            'rating': float(rating_text),
                            'review_count': review_count,
                            'address': addr_el.inner_text().strip() if addr_el else '',
                            'city': city,
                        })
                    except Exception:
                        continue
                browser.close()
        except Exception as e:
            logger.error(f"Google Maps scrape error: {e}")

        return results

    def _scrape_yelp(self, category: str, city: str) -> List[Dict]:
        """Scrape Yelp search results."""
        if not HAS_REQUESTS or not HAS_BS4:
            logger.warning("requests/bs4 not installed — skipping Yelp")
            return []

        results = []
        url = f"https://www.yelp.ca/search?find_desc={category}&find_loc={city}+ON"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO-DirectoryBot/1.0)'}

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')

            for card in soup.select('[data-testid="serp-ia-card"]')[:10]:
                name_el = card.select_one('a[href*="/biz/"] span')
                rating_el = card.select_one('[aria-label*="star rating"]')
                reviews_el = card.select_one('span[class*="reviewCount"]')

                name = name_el.get_text(strip=True) if name_el else None
                if not name:
                    continue

                rating_match = re.search(r'([\d.]+)', rating_el.get('aria-label', '')) if rating_el else None
                review_match = re.search(r'(\d+)', reviews_el.get_text() if reviews_el else '')

                results.append({
                    'name': name,
                    'rating': float(rating_match.group(1)) if rating_match else 0,
                    'review_count': int(review_match.group(1)) if review_match else 0,
                    'city': city,
                })
        except Exception as e:
            logger.error(f"Yelp scrape error: {e}")

        return results

    def _scrape_yellow_pages(self, category: str, city: str) -> List[Dict]:
        """Scrape YellowPages.ca results."""
        if not HAS_REQUESTS or not HAS_BS4:
            return []

        results = []
        url = f"https://www.yellowpages.ca/search/si/1/{category}/{city}+ON"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO-DirectoryBot/1.0)'}

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')

            for card in soup.select('.listing__content')[:10]:
                name_el = card.select_one('.listing__name a')
                addr_el = card.select_one('.listing__address')
                phone_el = card.select_one('.mlr__item__cta-phone')

                name = name_el.get_text(strip=True) if name_el else None
                if not name:
                    continue

                results.append({
                    'name': name,
                    'address': addr_el.get_text(strip=True) if addr_el else '',
                    'phone': phone_el.get_text(strip=True) if phone_el else '',
                    'city': city,
                    'rating': 0,
                    'review_count': 0,
                })
        except Exception as e:
            logger.error(f"YellowPages scrape error: {e}")

        return results

    def _scrape_bbb(self, category: str, city: str) -> List[Dict]:
        """Scrape BBB (Better Business Bureau) results."""
        if not HAS_REQUESTS or not HAS_BS4:
            return []

        results = []
        url = f"https://www.bbb.org/search?find_country=CAN&find_loc={city}%2C%20ON&find_text={category}"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO-DirectoryBot/1.0)'}

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')

            for card in soup.select('.result-item, .search-result')[:10]:
                name_el = card.select_one('.result-name a, h3 a')
                name = name_el.get_text(strip=True) if name_el else None
                if not name:
                    continue
                results.append({
                    'name': name,
                    'city': city,
                    'rating': 0,
                    'review_count': 0,
                })
        except Exception as e:
            logger.error(f"BBB scrape error: {e}")

        return results

    def _scrape_canada411(self, category: str, city: str) -> List[Dict]:
        """Scrape Canada411 business results."""
        if not HAS_REQUESTS or not HAS_BS4:
            return []

        results = []
        url = f"https://www.canada411.ca/search/si/1/{category}/{city}+ON"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO-DirectoryBot/1.0)'}

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')

            for card in soup.select('.listing__content, .vcard')[:10]:
                name_el = card.select_one('.listing__name a, .fn')
                phone_el = card.select_one('.listing__phone, .tel')
                addr_el = card.select_one('.listing__address, .adr')

                name = name_el.get_text(strip=True) if name_el else None
                if not name:
                    continue
                results.append({
                    'name': name,
                    'phone': phone_el.get_text(strip=True) if phone_el else '',
                    'address': addr_el.get_text(strip=True) if addr_el else '',
                    'city': city,
                    'rating': 0,
                    'review_count': 0,
                })
        except Exception as e:
            logger.error(f"Canada411 scrape error: {e}")

        return results

    def deduplicate(self, listings: List[Dict]) -> List[Dict]:
        """Remove duplicate businesses by normalized name."""
        seen = set()
        unique = []
        for l in listings:
            key = re.sub(r'[^a-z0-9]', '', l['name'].lower())
            if key not in seen:
                seen.add(key)
                unique.append(l)
        return unique


# --- CLI entry point ---
if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from directory.database import DirectoryDatabase

    db = DirectoryDatabase()
    scraper = BusinessScraper(db=db)

    cats = sys.argv[1:] if len(sys.argv) > 1 else None
    result = scraper.scrape_all(categories=cats)
    print(f"\nDone: {result['found']} found, {result['added']} added")
    if result['errors']:
        print(f"Errors: {len(result['errors'])}")
        for e in result['errors']:
            print(f"  - {e}")
