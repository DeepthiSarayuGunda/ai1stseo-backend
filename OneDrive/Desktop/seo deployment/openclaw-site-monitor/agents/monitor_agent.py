"""
Comprehensive Site Monitor Agent for OpenClaw
Orchestrates all monitoring tools: SEO, Uptime, Content, AI Citation, Competitors, Transactions
"""

import json
from datetime import datetime
from pathlib import Path

from tools.seo_scanner import scan_site, deep_scan_site
from tools.notifier import send_alert
from tools.uptime_monitor import check_uptime
from tools.content_monitor import check_content_changes
from tools.ai_citation_tracker import check_ai_visibility
from tools.competitor_monitor import monitor_competitors
from tools.transaction_monitor import test_critical_paths
from tools.mention_scanner import scan_mentions
from tools.decay_detector import detect_decay
from tools.brand_sentiment import check_brand_sentiment


class SiteMonitorAgent:
    """OpenClaw agent that performs comprehensive site monitoring"""
    
    def __init__(self, config_path: str = "config/sites.json", history_path: str = "data/history.json"):
        self.config_path = Path(config_path)
        self.history_path = Path(history_path)
        self.config = self._load_config()
        self.history = self._load_history()
        
    def _load_config(self) -> dict:
        with open(self.config_path) as f:
            return json.load(f)
    
    def _load_history(self) -> dict:
        if self.history_path.exists():
            with open(self.history_path) as f:
                return json.load(f)
        return {"scans": []}
    
    def _save_history(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def _get_last_score(self, url: str) -> int | None:
        for scan in reversed(self.history.get("scans", [])):
            if scan.get("url") == url:
                return scan.get("score")
        return None
    
    def run_comprehensive_scan(self, site: dict) -> dict:
        """Run all monitoring checks for a single site"""
        url = site["url"]
        name = site["name"]
        brand = site.get("brand", name)
        threshold = site.get("alert_threshold", 5)
        settings = self.config.get("settings", {})
        
        alerts = []
        results = {}
        
        # 1. SEO Scan (always run) - Full 231-check deep analysis
        print(f"  [SEO] Running comprehensive 231-check scan...")
        seo_result = deep_scan_site(url)
        results["seo"] = seo_result
        
        last_score = self._get_last_score(url)
        if last_score is not None:
            drop = last_score - seo_result["score"]
            if drop >= threshold:
                alerts.append({
                    "type": "score_drop",
                    "severity": "warning",
                    "message": f"[WARNING] {name} score dropped {drop} points ({last_score} -> {seo_result['score']})"
                })
        
        if seo_result["critical_issues"]:
            issues_text = "\n".join(f"  - {i}" for i in seo_result["critical_issues"][:3])
            alerts.append({
                "type": "critical_issues",
                "severity": "warning",
                "message": f"[WARNING] {name} has critical issues:\n{issues_text}"
            })
        
        # 2. Uptime Check
        if settings.get("check_uptime", True):
            print(f"  [UPTIME] Checking status...")
            uptime_result = check_uptime(url)
            results["uptime"] = uptime_result
            
            if not uptime_result["is_up"]:
                alerts.append({
                    "type": "downtime",
                    "severity": "critical",
                    "message": f"[CRITICAL] {name} is DOWN - Multiple locations report unavailability."
                })
            
            # SSL warning
            ssl_days = uptime_result.get("ssl_days_remaining")
            ssl_warning = settings.get("ssl_warning_days", 30)
            if ssl_days is not None and ssl_days < ssl_warning:
                alerts.append({
                    "type": "ssl_expiring",
                    "severity": "critical" if ssl_days < 7 else "warning",
                    "message": f"[SSL] {name} certificate expires in {ssl_days} days"
                })
        
        # 3. Content Change Detection
        if settings.get("check_content_changes", True):
            print(f"  [CONTENT] Checking changes...")
            content_result = check_content_changes(url)
            results["content"] = content_result
            
            if content_result["alerts"]:
                for alert in content_result["alerts"]:
                    alerts.append({
                        "type": "content_change",
                        "severity": "critical" if "CRITICAL" in alert else "warning",
                        "message": f"{name}: {alert}"
                    })
        
        # 4. AI Citation Tracking
        if settings.get("check_ai_visibility", True):
            print(f"  [AI] Checking visibility...")
            ai_result = check_ai_visibility(url, brand)
            results["ai_visibility"] = ai_result
            
            if ai_result["citation_rate"] < 30:
                alerts.append({
                    "type": "low_ai_visibility",
                    "severity": "warning",
                    "message": f"[WARNING] {name} has low AI citation rate ({ai_result['citation_rate']}%). Recommendations:\n  - " + "\n  - ".join(ai_result["recommendations"][:2])
                })
        
        # 5. Transaction/API Health
        if settings.get("check_transactions", True):
            print(f"  [TRANSACTIONS] Testing paths...")
            transaction_result = test_critical_paths(url)
            results["transactions"] = transaction_result
            
            if transaction_result["failed"] > 0:
                failed_items = [r["name"] for r in transaction_result["results"] if r["status"] == "fail"]
                alerts.append({
                    "type": "transaction_failure",
                    "severity": "warning",
                    "message": f"[WARNING] {name} has {transaction_result['failed']} failed transactions: {', '.join(failed_items[:3])}"
                })
        
        # 6. Competitor Comparison
        competitors = site.get("competitors", [])
        if competitors:
            print(f"  [COMPETITORS] Comparing rankings...")
            competitor_urls = [c["url"] for c in competitors]
            comp_result = monitor_competitors(url, competitor_urls)
            results["competitors"] = comp_result
            
            if comp_result["your_rank"] > 1:
                alerts.append({
                    "type": "competitor_ranking",
                    "severity": "info",
                    "message": f"[INFO] {name} ranks #{comp_result['your_rank']} vs competitors. {comp_result['insights'][0]}"
                })

        # 7. Content Decay Detection
        if settings.get("check_decay", True):
            print(f"  [DECAY] Checking score trends...")
            try:
                decay_result = detect_decay(url, str(self.history_path), threshold=threshold)
                results["decay"] = decay_result
                if decay_result["decaying"]:
                    for d in decay_result["decaying"][:3]:
                        sev = "critical" if d.get("severity") == "critical" else "warning"
                        alerts.append({
                            "type": "content_decay",
                            "severity": sev,
                            "message": f"[DECAY] {d['url']} dropped {abs(d['change'])} points ({d['previous_score']} → {d['latest_score']})"
                        })
            except Exception as e:
                print(f"  [DECAY] Error: {e}")

        # 8. Brand Mention Scanning
        if settings.get("check_mentions", True):
            print(f"  [MENTIONS] Scanning web for brand mentions...")
            try:
                domain = site.get("domain", url.replace("https://", "").replace("http://", "").split("/")[0])
                mention_result = scan_mentions(brand, domain)
                results["mentions"] = mention_result
                if mention_result["unlinked_count"] > 0:
                    alerts.append({
                        "type": "unlinked_mentions",
                        "severity": "info",
                        "message": f"[MENTIONS] Found {mention_result['unlinked_count']} unlinked mention(s) of {brand} — backlink opportunities"
                    })
            except Exception as e:
                print(f"  [MENTIONS] Error: {e}")

        # 9. Brand Sentiment Monitoring (AI-powered)
        if settings.get("check_brand_sentiment", True):
            print(f"  [SENTIMENT] Probing AI models for brand perception...")
            try:
                sentiment_result = check_brand_sentiment(brand)
                results["brand_sentiment"] = sentiment_result
                if sentiment_result["dominant_sentiment"] == "negative":
                    alerts.append({
                        "type": "negative_sentiment",
                        "severity": "warning",
                        "message": f"[SENTIMENT] AI models have negative sentiment toward {brand}. Recommendation score: {sentiment_result['avg_recommendation_score']}/100"
                    })
                if sentiment_result["hallucination_flags"]:
                    alerts.append({
                        "type": "hallucination_detected",
                        "severity": "warning",
                        "message": f"[HALLUCINATION] AI models making {len(sentiment_result['hallucination_flags'])} unverified claim(s) about {brand} (pricing, dates)"
                    })
            except Exception as e:
                print(f"  [SENTIMENT] Error: {e}")
        
        # Store scan result
        self.history["scans"].append({
            "url": url,
            "name": name,
            "score": seo_result["score"],
            "uptime": results.get("uptime", {}).get("is_up", True),
            "ai_citation_rate": results.get("ai_visibility", {}).get("citation_rate", 0),
            "brand_sentiment": results.get("brand_sentiment", {}).get("dominant_sentiment", "unknown"),
            "unlinked_mentions": results.get("mentions", {}).get("unlinked_count", 0),
            "decaying_pages": len(results.get("decay", {}).get("decaying", [])),
            "timestamp": datetime.now().isoformat()
        })
        
        return {"results": results, "alerts": alerts}
    
    def run_daily_scan(self) -> dict:
        """Run comprehensive scans for all configured sites"""
        all_results = []
        all_alerts = []
        
        print("\n" + "=" * 60)
        print("  COMPREHENSIVE SITE MONITOR - Daily Scan")
        print("=" * 60 + "\n")
        
        for site in self.config.get("sites", []):
            if not site.get("enabled", True):
                continue
            
            print(f"\n[SCANNING] {site['name']} ({site['url']})")
            print("-" * 40)
            
            scan_data = self.run_comprehensive_scan(site)
            all_results.append({
                "site": site["name"],
                "url": site["url"],
                "results": scan_data["results"]
            })
            all_alerts.extend(scan_data["alerts"])
        
        self._save_history()
        
        # Send alerts via WhatsApp (default)
        for alert in all_alerts:
            send_alert(
                message=alert["message"],
                channel="whatsapp",
                severity=alert["severity"]
            )
        
        # Summary
        print("\n" + "=" * 60)
        print("  SCAN SUMMARY")
        print("=" * 60)
        
        for result in all_results:
            seo = result["results"].get("seo", {})
            uptime = result["results"].get("uptime", {})
            ai = result["results"].get("ai_visibility", {})
            mentions = result["results"].get("mentions", {})
            sentiment = result["results"].get("brand_sentiment", {})
            decay = result["results"].get("decay", {})
            
            status = "[PASS]" if seo.get("score", 0) >= 70 else "[WARN]" if seo.get("score", 0) >= 50 else "[FAIL]"
            print(f"\n{status} {result['site']}")
            print(f"   SEO Score: {seo.get('score', 'N/A')}/100 ({seo.get('totalChecks', 'N/A')} checks)")
            print(f"   Uptime: {'UP' if uptime.get('is_up', True) else 'DOWN'}")
            print(f"   AI Citation Rate: {ai.get('citation_rate', 'N/A')}%")
            print(f"   SSL Days Left: {uptime.get('ssl_days_remaining', 'N/A')}")
            print(f"   Brand Sentiment: {sentiment.get('dominant_sentiment', 'N/A')} (rec: {sentiment.get('avg_recommendation_score', 'N/A')}/100)")
            print(f"   Unlinked Mentions: {mentions.get('unlinked_count', 0)} opportunities")
            print(f"   Decaying Pages: {len(decay.get('decaying', []))}")
        
        print(f"\nAlerts sent: {len(all_alerts)}")
        print("=" * 60 + "\n")
        
        return {
            "sites_scanned": len(all_results),
            "alerts_sent": len(all_alerts),
            "results": all_results,
            "timestamp": datetime.now().isoformat()
        }


# OpenClaw agent registration
AGENT_CONFIG = {
    "name": "comprehensive_site_monitor",
    "description": "Monitors websites for SEO, uptime, content changes, AI visibility, and competitor performance",
    "tools": [
        "seo_scanner",
        "uptime_monitor", 
        "content_monitor",
        "ai_citation_tracker",
        "competitor_monitor",
        "transaction_monitor",
        "mention_scanner",
        "decay_detector",
        "brand_sentiment",
        "notifier"
    ],
    "schedule": {
        "type": "cron",
        "expression": "0 8 * * *"
    },
    "policies": {
        "max_retries": 2,
        "timeout_seconds": 600,
        "rate_limit": "10/minute"
    }
}
