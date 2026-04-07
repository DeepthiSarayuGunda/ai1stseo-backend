"""
AI-Powered Analysis Tool — Uses dual-path inference (Nova Lite + Ollama fallback)
Provides intelligent SEO insights for scan results, competitor gaps, and chat.
"""

import json
from typing import Optional


class AIAnalyzer:
    """Uses Nova Lite (primary) + Ollama (fallback) for SEO analysis"""

    def _call_llm(self, prompt, max_tokens=1024):
        """Route through the shared dual-path inference module."""
        try:
            from ai_inference import generate
            return generate(prompt, max_tokens=max_tokens, temperature=0.7)
        except Exception as e:
            return "[AI Analysis unavailable: {}]".format(e)

    # =========================================
    # 1. AI-POWERED REPORT ANALYSIS
    # =========================================

    def analyze_scan_results(self, scan_data):
        """Generate a human-friendly analysis of scan results."""
        prompt = (
            "You are an SEO expert analyzing a website scan. Write a brief, "
            "actionable summary for a business owner who isn't technical.\n\n"
            "SCAN DATA:\n"
            "- URL: {url}\n"
            "- SEO Score: {score}/100\n"
            "- Load Time: {lt}s\n"
            "- Critical Issues: {issues}\n"
            "- Warnings: {warnings}\n\n"
            "Write 3-4 sentences explaining:\n"
            "1. Overall health (good/needs work/critical)\n"
            "2. The #1 thing hurting their rankings\n"
            "3. What they should fix first and why it matters\n\n"
            "Keep it conversational, not technical. No bullet points."
        ).format(
            url=scan_data.get("url", "Unknown"),
            score=scan_data.get("score", "N/A"),
            lt=scan_data.get("load_time", "N/A"),
            issues=json.dumps(scan_data.get("critical_issues", [])),
            warnings=json.dumps(scan_data.get("warnings", [])),
        )
        return self._call_llm(prompt, max_tokens=300)

    def explain_score_change(self, current_score, previous_score,
                             current_issues, previous_issues):
        """Explain why a score changed between scans."""
        change = current_score - previous_score
        direction = "improved" if change > 0 else "dropped"
        new_issues = [i for i in current_issues if i not in previous_issues]
        fixed_issues = [i for i in previous_issues if i not in current_issues]

        prompt = (
            "A website's SEO score {dir} by {delta} points "
            "(from {prev} to {cur}).\n\n"
            "New issues found: {new}\n"
            "Issues fixed: {fixed}\n\n"
            "Write 2-3 sentences explaining what likely caused this change "
            "and what the site owner should do about it. Be specific."
        ).format(
            dir=direction, delta=abs(change), prev=previous_score,
            cur=current_score,
            new=json.dumps(new_issues) if new_issues else "None",
            fixed=json.dumps(fixed_issues) if fixed_issues else "None",
        )
        return self._call_llm(prompt, max_tokens=200)

    # =========================================
    # 2. AUTO-GENERATED FIX SUGGESTIONS
    # =========================================

    def generate_fix_code(self, issue, context=None):
        """Generate copy-paste code to fix a specific SEO issue."""
        context_str = json.dumps(context) if context else "{}"
        prompt = (
            "You are an SEO developer. Generate the exact code to fix this issue.\n\n"
            "ISSUE: {issue}\n"
            "SITE CONTEXT: {ctx}\n\n"
            "Provide:\n"
            "1. The exact HTML/code snippet to add (ready to copy-paste)\n"
            "2. Where to add it (e.g., \"in the <head> section\")\n"
            "3. One sentence on why this fixes the issue\n\n"
            "Format your response as JSON:\n"
            '{{"code": "<the exact code>", "location": "where to add it", '
            '"explanation": "why this works"}}\n\n'
            "Only output valid JSON, nothing else."
        ).format(issue=issue, ctx=context_str)

        response = self._call_llm(prompt, max_tokens=500)
        try:
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return {
                "code": response,
                "location": "See code for details",
                "explanation": "AI-generated fix suggestion",
            }

    def generate_all_fixes(self, issues, site_url=""):
        """Generate fixes for all issues in a scan."""
        fixes = []
        for issue in issues[:5]:
            fix = self.generate_fix_code(issue, {"url": site_url})
            fixes.append({"issue": issue, "fix": fix})
        return fixes

    # =========================================
    # 3. COMPETITOR INTELLIGENCE
    # =========================================

    def analyze_competitor_gap(self, your_data, competitor_data):
        """Analyze why competitors might be ranking better."""
        prompt = (
            "You are an SEO strategist. Analyze this competitive data.\n\n"
            "YOUR SITE:\n"
            "- URL: {url}\n- Score: {score}/100\n"
            "- Issues: {issues}\n- Load Time: {lt}s\n\n"
            "COMPETITORS:\n{comps}\n\n"
            "Write a brief competitive analysis (4-5 sentences):\n"
            "1. How you compare overall\n"
            "2. What competitors are doing better\n"
            "3. Your biggest competitive advantage\n"
            "4. The #1 thing to implement to close the gap\n\n"
            "Be specific. Focus on quick wins."
        ).format(
            url=your_data.get("url"), score=your_data.get("score"),
            issues=json.dumps(your_data.get("critical_issues", [])),
            lt=your_data.get("load_time"),
            comps=json.dumps(competitor_data, indent=2),
        )
        return self._call_llm(prompt, max_tokens=400)

    def identify_competitor_strengths(self, competitor_data):
        """Identify what top competitors are doing well."""
        prompt = (
            "Analyze these competitor websites and identify their SEO strengths:\n\n"
            "{comps}\n\n"
            "List the top 3 things the best-performing competitors have in common.\n"
            "Format as JSON array:\n"
            '[{{"strength": "what they do", "impact": "why it helps rankings", '
            '"how_to_copy": "how to implement"}}]\n\n'
            "Only output valid JSON."
        ).format(comps=json.dumps(competitor_data, indent=2))

        response = self._call_llm(prompt, max_tokens=500)
        try:
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return [{"strength": response, "impact": "See details",
                      "how_to_copy": "Consult analysis"}]

    # =========================================
    # 4. CONVERSATIONAL RESPONSES
    # =========================================

    def answer_question(self, question, scan_data):
        """Answer a user's question about their scan results."""
        prompt = (
            "You are an SEO assistant. A user is asking about their website scan.\n\n"
            "THEIR SCAN DATA:\n"
            "- URL: {url}\n- Score: {score}/100\n"
            "- Critical Issues: {issues}\n"
            "- Warnings: {warnings}\n"
            "- AI Citation Rate: {ai}%\n\n"
            "USER QUESTION: {q}\n\n"
            "Answer in 2-3 sentences. Be helpful and specific. "
            "Keep it conversational - this is a chat, not a report."
        ).format(
            url=scan_data.get("url"), score=scan_data.get("score"),
            issues=json.dumps(scan_data.get("critical_issues", [])),
            warnings=json.dumps(scan_data.get("warnings", [])),
            ai=scan_data.get("ai_citation_rate", "N/A"),
            q=question,
        )
        return self._call_llm(prompt, max_tokens=250)

    def suggest_next_action(self, scan_data):
        """Suggest the single most impactful next action."""
        prompt = (
            "Based on this SEO scan, what's the ONE thing this site owner "
            "should do right now to improve their rankings?\n\n"
            "Score: {score}/100\n"
            "Critical Issues: {issues}\n"
            "Warnings: {warnings}\n\n"
            "Give a single, specific action in 1-2 sentences. Start with a verb."
        ).format(
            score=scan_data.get("score"),
            issues=json.dumps(scan_data.get("critical_issues", [])),
            warnings=json.dumps(scan_data.get("warnings", [])[:3]),
        )
        return self._call_llm(prompt, max_tokens=150)


# Singleton instance
_analyzer = None


def get_analyzer():
    """Get or create the AI analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = AIAnalyzer()
    return _analyzer


# OpenClaw tool registration
TOOL_SCHEMA = {
    "name": "ai_analyzer",
    "description": "AI-powered SEO analysis using Nova Lite + Ollama fallback",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["analyze", "explain_change", "generate_fix",
                         "competitor_gap", "answer_question"],
                "description": "Type of AI analysis to perform",
            },
            "data": {
                "type": "object",
                "description": "Scan data or context for analysis",
            },
            "question": {
                "type": "string",
                "description": "User question (for answer_question action)",
            },
        },
        "required": ["action", "data"],
    },
}
