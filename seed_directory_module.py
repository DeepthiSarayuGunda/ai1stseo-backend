#!/usr/bin/env python3
"""Seed the generic Directory module with real categories and items.

Run: python seed_directory_module.py

Categories seeded: Sports, AI Tools, Brands, SEO Tools, Analytics Platforms
Each category gets real, verifiable items with accurate data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from directory.directory_db import (
    init_directory_tables, create_category, create_item
)

print("Initializing directory tables...")
init_directory_tables()

# ── Categories ────────────────────────────────────────────────────────────────

CATEGORIES = [
    ("Sports", "sports", "Live sports leagues, teams, events, and athlete rankings", "sports", 1),
    ("AI Tools", "ai-tools", "AI-powered tools for content, code, design, and productivity", "robot", 2),
    ("Brands", "brands", "Top brands tracked for AI visibility and citation performance", "tag", 3),
    ("SEO Tools", "seo-tools", "Search engine optimization platforms and utilities", "search", 4),
    ("Analytics", "analytics", "Web and business analytics platforms", "chart", 5),
]

print("\nSeeding categories...")
for name, slug, desc, icon, order in CATEGORIES:
    create_category(name, slug, desc, icon, order)
    print(f"  + {name}")

# ── Sports items ──────────────────────────────────────────────────────────────

SPORTS = [
    {
        "name": "NHL - National Hockey League",
        "slug": "nhl",
        "description": "Professional ice hockey league with 32 teams across North America. The 2025-26 season features expanded analytics and AI-driven player tracking.",
        "source_url": "https://www.nhl.com",
        "image_url": "https://www-league.nhlstatic.com/images/logos/league-dark/133-flat.svg",
        "tags": ["hockey", "ice-hockey", "north-america", "professional"],
        "trending_score": 92, "ranking": 1, "rating": 4.8, "review_count": 15000,
        "meta_json": {"league_type": "professional", "sport": "hockey", "teams": 32, "country": "NA"}
    },
    {
        "name": "NBA - National Basketball Association",
        "slug": "nba",
        "description": "Premier professional basketball league with 30 teams. Known for advanced stats, player tracking, and global reach.",
        "source_url": "https://www.nba.com",
        "tags": ["basketball", "north-america", "professional"],
        "trending_score": 95, "ranking": 2, "rating": 4.7, "review_count": 18000,
        "meta_json": {"league_type": "professional", "sport": "basketball", "teams": 30, "country": "NA"}
    },
    {
        "name": "Premier League",
        "slug": "premier-league",
        "description": "Top tier of English football with 20 clubs. Most-watched sports league globally with extensive AI-powered match analysis.",
        "source_url": "https://www.premierleague.com",
        "tags": ["football", "soccer", "england", "professional"],
        "trending_score": 97, "ranking": 3, "rating": 4.9, "review_count": 25000,
        "meta_json": {"league_type": "professional", "sport": "football", "teams": 20, "country": "UK"}
    },
    {
        "name": "NFL - National Football League",
        "slug": "nfl",
        "description": "American football league with 32 teams. Highest revenue sports league globally with advanced game analytics.",
        "source_url": "https://www.nfl.com",
        "tags": ["football", "american-football", "north-america", "professional"],
        "trending_score": 94, "ranking": 4, "rating": 4.7, "review_count": 20000,
        "meta_json": {"league_type": "professional", "sport": "american-football", "teams": 32, "country": "US"}
    },
    {
        "name": "MLB - Major League Baseball",
        "slug": "mlb",
        "description": "Professional baseball with 30 teams. Pioneer in sports analytics with Statcast tracking system.",
        "source_url": "https://www.mlb.com",
        "tags": ["baseball", "north-america", "professional"],
        "trending_score": 80, "ranking": 5, "rating": 4.5, "review_count": 12000,
        "meta_json": {"league_type": "professional", "sport": "baseball", "teams": 30, "country": "NA"}
    },
    {
        "name": "UFC - Ultimate Fighting Championship",
        "slug": "ufc",
        "description": "Premier mixed martial arts organization with events worldwide. Growing rapidly in AI-driven fight analytics.",
        "source_url": "https://www.ufc.com",
        "tags": ["mma", "fighting", "combat-sports", "professional"],
        "trending_score": 88, "ranking": 6, "rating": 4.6, "review_count": 9000,
        "meta_json": {"league_type": "professional", "sport": "mma", "country": "global"}
    },
    {
        "name": "La Liga",
        "slug": "la-liga",
        "description": "Top professional football division in Spain featuring FC Barcelona and Real Madrid.",
        "source_url": "https://www.laliga.com",
        "tags": ["football", "soccer", "spain", "professional"],
        "trending_score": 85, "ranking": 7, "rating": 4.7, "review_count": 14000,
        "meta_json": {"league_type": "professional", "sport": "football", "teams": 20, "country": "Spain"}
    },
    {
        "name": "Formula 1",
        "slug": "formula-1",
        "description": "Pinnacle of motorsport racing with 10 teams and 20 drivers. Heavy use of AI for race strategy and car development.",
        "source_url": "https://www.formula1.com",
        "tags": ["motorsport", "racing", "f1", "professional"],
        "trending_score": 91, "ranking": 8, "rating": 4.8, "review_count": 16000,
        "meta_json": {"league_type": "professional", "sport": "motorsport", "teams": 10, "country": "global"}
    },
    {
        "name": "ATP Tour - Tennis",
        "slug": "atp-tour",
        "description": "Men's professional tennis circuit organizing Grand Slams, Masters, and ATP events worldwide.",
        "source_url": "https://www.atptour.com",
        "tags": ["tennis", "individual-sport", "professional"],
        "trending_score": 75, "ranking": 9, "rating": 4.5, "review_count": 8000,
        "meta_json": {"league_type": "professional", "sport": "tennis", "country": "global"}
    },
    {
        "name": "IPL - Indian Premier League",
        "slug": "ipl",
        "description": "Premier T20 cricket league in India with 10 franchise teams. Most valuable cricket league globally.",
        "source_url": "https://www.iplt20.com",
        "tags": ["cricket", "t20", "india", "professional"],
        "trending_score": 93, "ranking": 10, "rating": 4.6, "review_count": 22000,
        "meta_json": {"league_type": "professional", "sport": "cricket", "teams": 10, "country": "India"}
    },
]

print("\nSeeding Sports items...")
for item in SPORTS:
    create_item("sports", item)
    print(f"  + {item['name']}")


# ── AI Tools items ────────────────────────────────────────────────────────────

AI_TOOLS = [
    {
        "name": "ChatGPT",
        "slug": "chatgpt",
        "description": "OpenAI's conversational AI assistant for writing, coding, analysis, and creative tasks. GPT-4o powers the latest version.",
        "source_url": "https://chat.openai.com",
        "tags": ["chatbot", "writing", "coding", "openai", "llm"],
        "trending_score": 99, "ranking": 1, "rating": 4.7, "review_count": 50000,
        "meta_json": {"provider": "OpenAI", "pricing": "freemium", "model": "GPT-4o"}
    },
    {
        "name": "Claude",
        "slug": "claude",
        "description": "Anthropic's AI assistant known for long-context understanding, safety, and nuanced reasoning.",
        "source_url": "https://claude.ai",
        "tags": ["chatbot", "writing", "coding", "anthropic", "llm"],
        "trending_score": 95, "ranking": 2, "rating": 4.8, "review_count": 25000,
        "meta_json": {"provider": "Anthropic", "pricing": "freemium", "model": "Claude 3.5 Sonnet"}
    },
    {
        "name": "Midjourney",
        "slug": "midjourney",
        "description": "AI image generation tool creating high-quality artwork from text prompts via Discord.",
        "source_url": "https://www.midjourney.com",
        "tags": ["image-generation", "art", "design", "creative"],
        "trending_score": 88, "ranking": 3, "rating": 4.6, "review_count": 30000,
        "meta_json": {"provider": "Midjourney", "pricing": "paid", "type": "image-generation"}
    },
    {
        "name": "Perplexity AI",
        "slug": "perplexity-ai",
        "description": "AI-powered search engine that provides cited, real-time answers from the web.",
        "source_url": "https://www.perplexity.ai",
        "tags": ["search", "research", "citations", "llm"],
        "trending_score": 90, "ranking": 4, "rating": 4.5, "review_count": 15000,
        "meta_json": {"provider": "Perplexity", "pricing": "freemium", "type": "search"}
    },
    {
        "name": "GitHub Copilot",
        "slug": "github-copilot",
        "description": "AI pair programmer by GitHub and OpenAI that suggests code completions in your IDE.",
        "source_url": "https://github.com/features/copilot",
        "tags": ["coding", "developer-tools", "ide", "github"],
        "trending_score": 92, "ranking": 5, "rating": 4.5, "review_count": 20000,
        "meta_json": {"provider": "GitHub/OpenAI", "pricing": "paid", "type": "code-assistant"}
    },
    {
        "name": "Gemini",
        "slug": "gemini",
        "description": "Google's multimodal AI model integrated across Google products for text, image, and code tasks.",
        "source_url": "https://gemini.google.com",
        "tags": ["chatbot", "multimodal", "google", "llm"],
        "trending_score": 91, "ranking": 6, "rating": 4.4, "review_count": 18000,
        "meta_json": {"provider": "Google", "pricing": "freemium", "model": "Gemini 1.5 Pro"}
    },
    {
        "name": "Cursor",
        "slug": "cursor",
        "description": "AI-first code editor built on VS Code with deep AI integration for code generation and editing.",
        "source_url": "https://cursor.sh",
        "tags": ["coding", "ide", "developer-tools", "editor"],
        "trending_score": 87, "ranking": 7, "rating": 4.6, "review_count": 8000,
        "meta_json": {"provider": "Cursor", "pricing": "freemium", "type": "code-editor"}
    },
    {
        "name": "Runway ML",
        "slug": "runway-ml",
        "description": "AI creative suite for video generation, editing, and visual effects using Gen-2 models.",
        "source_url": "https://runwayml.com",
        "tags": ["video", "creative", "generation", "editing"],
        "trending_score": 82, "ranking": 8, "rating": 4.4, "review_count": 10000,
        "meta_json": {"provider": "Runway", "pricing": "freemium", "type": "video-generation"}
    },
]

print("\nSeeding AI Tools items...")
for item in AI_TOOLS:
    create_item("ai-tools", item)
    print(f"  + {item['name']}")

# ── Brands items ──────────────────────────────────────────────────────────────

BRANDS = [
    {
        "name": "Apple",
        "slug": "apple",
        "description": "Technology company known for iPhone, Mac, iPad, and services ecosystem. Strong AI visibility across all platforms.",
        "source_url": "https://www.apple.com",
        "tags": ["technology", "consumer-electronics", "software", "services"],
        "trending_score": 96, "ranking": 1, "rating": 4.8, "review_count": 100000,
        "meta_json": {"industry": "technology", "market_cap_tier": "mega", "hq": "Cupertino, CA"}
    },
    {
        "name": "Nike",
        "slug": "nike",
        "description": "Global athletic footwear and apparel brand. Leader in sports marketing and AI-driven personalization.",
        "source_url": "https://www.nike.com",
        "tags": ["sportswear", "footwear", "apparel", "athletics"],
        "trending_score": 90, "ranking": 2, "rating": 4.6, "review_count": 80000,
        "meta_json": {"industry": "sportswear", "market_cap_tier": "large", "hq": "Beaverton, OR"}
    },
    {
        "name": "Tesla",
        "slug": "tesla",
        "description": "Electric vehicle and clean energy company. Pioneering autonomous driving with AI and neural networks.",
        "source_url": "https://www.tesla.com",
        "tags": ["automotive", "electric-vehicles", "energy", "ai"],
        "trending_score": 94, "ranking": 3, "rating": 4.5, "review_count": 60000,
        "meta_json": {"industry": "automotive", "market_cap_tier": "mega", "hq": "Austin, TX"}
    },
    {
        "name": "Google",
        "slug": "google",
        "description": "Search and technology giant. Dominates search, advertising, cloud, and AI research with DeepMind and Gemini.",
        "source_url": "https://www.google.com",
        "tags": ["technology", "search", "advertising", "cloud", "ai"],
        "trending_score": 97, "ranking": 4, "rating": 4.7, "review_count": 120000,
        "meta_json": {"industry": "technology", "market_cap_tier": "mega", "hq": "Mountain View, CA"}
    },
    {
        "name": "Amazon",
        "slug": "amazon",
        "description": "E-commerce and cloud computing leader. AWS powers a significant portion of the internet.",
        "source_url": "https://www.amazon.com",
        "tags": ["e-commerce", "cloud", "technology", "retail"],
        "trending_score": 93, "ranking": 5, "rating": 4.5, "review_count": 150000,
        "meta_json": {"industry": "e-commerce", "market_cap_tier": "mega", "hq": "Seattle, WA"}
    },
    {
        "name": "Samsung",
        "slug": "samsung",
        "description": "South Korean conglomerate leading in smartphones, semiconductors, and display technology.",
        "source_url": "https://www.samsung.com",
        "tags": ["technology", "consumer-electronics", "semiconductors"],
        "trending_score": 85, "ranking": 6, "rating": 4.4, "review_count": 70000,
        "meta_json": {"industry": "technology", "market_cap_tier": "mega", "hq": "Seoul, South Korea"}
    },
]

print("\nSeeding Brands items...")
for item in BRANDS:
    create_item("brands", item)
    print(f"  + {item['name']}")

# ── SEO Tools items ───────────────────────────────────────────────────────────

SEO_TOOLS = [
    {
        "name": "Ahrefs",
        "slug": "ahrefs",
        "description": "Comprehensive SEO toolset for backlink analysis, keyword research, site audits, and rank tracking.",
        "source_url": "https://ahrefs.com",
        "tags": ["backlinks", "keyword-research", "site-audit", "rank-tracking"],
        "trending_score": 90, "ranking": 1, "rating": 4.7, "review_count": 12000,
        "meta_json": {"pricing": "paid", "starting_price": "$99/mo", "type": "all-in-one"}
    },
    {
        "name": "SEMrush",
        "slug": "semrush",
        "description": "All-in-one digital marketing suite with SEO, PPC, content, and competitive analysis tools.",
        "source_url": "https://www.semrush.com",
        "tags": ["keyword-research", "competitive-analysis", "ppc", "content"],
        "trending_score": 89, "ranking": 2, "rating": 4.6, "review_count": 15000,
        "meta_json": {"pricing": "paid", "starting_price": "$129/mo", "type": "all-in-one"}
    },
    {
        "name": "Moz Pro",
        "slug": "moz-pro",
        "description": "SEO software with domain authority metrics, keyword explorer, and site crawl capabilities.",
        "source_url": "https://moz.com",
        "tags": ["domain-authority", "keyword-research", "site-crawl"],
        "trending_score": 72, "ranking": 3, "rating": 4.3, "review_count": 8000,
        "meta_json": {"pricing": "paid", "starting_price": "$99/mo", "type": "all-in-one"}
    },
    {
        "name": "Screaming Frog",
        "slug": "screaming-frog",
        "description": "Desktop website crawler for technical SEO audits — broken links, redirects, meta data analysis.",
        "source_url": "https://www.screamingfrog.co.uk",
        "tags": ["technical-seo", "site-crawl", "audit", "desktop"],
        "trending_score": 68, "ranking": 4, "rating": 4.5, "review_count": 5000,
        "meta_json": {"pricing": "freemium", "starting_price": "$259/yr", "type": "crawler"}
    },
    {
        "name": "Surfer SEO",
        "slug": "surfer-seo",
        "description": "AI-powered content optimization tool that analyzes top-ranking pages and provides real-time writing guidelines.",
        "source_url": "https://surferseo.com",
        "tags": ["content-optimization", "ai", "on-page", "writing"],
        "trending_score": 83, "ranking": 5, "rating": 4.5, "review_count": 6000,
        "meta_json": {"pricing": "paid", "starting_price": "$89/mo", "type": "content"}
    },
]

print("\nSeeding SEO Tools items...")
for item in SEO_TOOLS:
    create_item("seo-tools", item)
    print(f"  + {item['name']}")

# ── Analytics items ───────────────────────────────────────────────────────────

ANALYTICS = [
    {
        "name": "Google Analytics 4",
        "slug": "google-analytics-4",
        "description": "Google's event-based analytics platform for web and app measurement with AI-powered insights.",
        "source_url": "https://analytics.google.com",
        "tags": ["web-analytics", "google", "free", "event-based"],
        "trending_score": 95, "ranking": 1, "rating": 4.3, "review_count": 30000,
        "meta_json": {"pricing": "free", "type": "web-analytics", "provider": "Google"}
    },
    {
        "name": "Mixpanel",
        "slug": "mixpanel",
        "description": "Product analytics platform for tracking user behavior, funnels, and retention with self-serve insights.",
        "source_url": "https://mixpanel.com",
        "tags": ["product-analytics", "funnels", "retention", "user-behavior"],
        "trending_score": 78, "ranking": 2, "rating": 4.4, "review_count": 8000,
        "meta_json": {"pricing": "freemium", "starting_price": "$25/mo", "type": "product-analytics"}
    },
    {
        "name": "Amplitude",
        "slug": "amplitude",
        "description": "Digital analytics platform focused on product intelligence, behavioral cohorts, and experimentation.",
        "source_url": "https://amplitude.com",
        "tags": ["product-analytics", "behavioral", "experimentation"],
        "trending_score": 76, "ranking": 3, "rating": 4.4, "review_count": 6000,
        "meta_json": {"pricing": "freemium", "type": "product-analytics"}
    },
    {
        "name": "Hotjar",
        "slug": "hotjar",
        "description": "Behavior analytics with heatmaps, session recordings, and user feedback tools for UX optimization.",
        "source_url": "https://www.hotjar.com",
        "tags": ["heatmaps", "session-recording", "ux", "feedback"],
        "trending_score": 74, "ranking": 4, "rating": 4.3, "review_count": 10000,
        "meta_json": {"pricing": "freemium", "starting_price": "$39/mo", "type": "behavior-analytics"}
    },
    {
        "name": "Plausible Analytics",
        "slug": "plausible",
        "description": "Lightweight, privacy-focused web analytics. Open source alternative to Google Analytics without cookies.",
        "source_url": "https://plausible.io",
        "tags": ["web-analytics", "privacy", "open-source", "lightweight"],
        "trending_score": 70, "ranking": 5, "rating": 4.6, "review_count": 3000,
        "meta_json": {"pricing": "paid", "starting_price": "$9/mo", "type": "web-analytics"}
    },
]

print("\nSeeding Analytics items...")
for item in ANALYTICS:
    create_item("analytics", item)
    print(f"  + {item['name']}")

print(f"\n[OK] Done — seeded {len(CATEGORIES)} categories and "
      f"{len(SPORTS) + len(AI_TOOLS) + len(BRANDS) + len(SEO_TOOLS) + len(ANALYTICS)} items total")
