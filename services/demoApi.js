/**
 * Demo API Server — Safe, Standalone
 *
 * Exposes GET /api/demo-output with real generated data.
 * Completely separate from the main Flask app — no UI impact.
 *
 * Run:   node services/demoApi.js
 * Test:  curl http://localhost:3099/api/demo-output
 *
 * Env vars:
 *   DEMO_API_PORT - Port (default: 3099)
 */

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = parseInt(process.env.DEMO_API_PORT, 10) || 3099;

// --- Data Loaders --------------------------------------------------------- //

function loadJson(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}

function buildDemoResponse() {
  const dataDir = path.join(__dirname, "..", "data");

  // Load social launch output
  const launchData = loadJson(path.join(dataDir, "social_launch_output.json"));

  // Load engagement data
  const engagementData = loadJson(path.join(dataDir, "engagement.json")) || [];

  // Load analytics events
  const analyticsData = loadJson(path.join(dataDir, "analytics_events.json")) || [];

  // Load schedule
  const scheduleData = loadJson(path.join(dataDir, "social_schedule.json")) || [];

  // --- Blog section ---
  let blog = null;
  if (launchData?.blogs?.length) {
    const firstBlog = launchData.blogs[0];

    // Try to generate a fresh blog for richer data
    try {
      const { generateBlog } = require("./blog_generator");
      const { optimizePage } = require("./seoOptimizer");

      const rawBlog = generateBlog({
        topic: "AI-Powered SEO Strategies for 2026",
        seoData: { keyword: "ai seo", searchVolume: 14800, competition: 0.42, cpc: 6.63 },
      });
      const perfectPage = optimizePage(rawBlog);

      blog = {
        title: perfectPage.title,
        meta_title: perfectPage.meta_title,
        meta_description: perfectPage.meta_description,
        seo_score: perfectPage.seo_score.seo_score,
        seo_grade: perfectPage.seo_score.grade,
        snippet: perfectPage.content.featured_snippet?.snippetText || null,
        content_preview: [
          perfectPage.content.intro,
          perfectPage.content.sections?.[0]?.body || "",
        ],
        faq_count: perfectPage.faq_section?.length || 0,
        internal_links: perfectPage.internal_links?.length || 0,
      };
    } catch {
      // Fallback to stored summary
      blog = {
        title: firstBlog.title,
        seo_score: firstBlog.seoScore,
        seo_grade: firstBlog.grade,
        content_preview: [],
      };
    }
  }

  // --- Social section ---
  let social = { linkedin_post: null, twitter_thread: null };
  if (launchData?.readyToPostContent) {
    const li = launchData.readyToPostContent.linkedin?.[0];
    const tw = launchData.readyToPostContent.twitter?.[0];
    social.linkedin_post = li?.text || null;
    social.twitter_thread = tw?.tweets || null;
  }

  // --- Metrics section ---
  const publishedPosts = scheduleData.filter((p) => p.status === "published").length;
  const queuedPosts = scheduleData.filter((p) => p.status === "queued").length;
  const totalPosts = scheduleData.length;

  let totalEngagement = 0;
  for (const e of engagementData) {
    totalEngagement += (e.likes || 0) + (e.comments || 0) + (e.shares || 0) + (e.clicks || 0);
  }

  const uniquePosts = new Set(engagementData.map((e) => e.postId)).size;
  const avgEngagement = uniquePosts > 0
    ? parseFloat((totalEngagement / uniquePosts).toFixed(1))
    : 0;

  // Event counts from analytics
  const eventCounts = {};
  for (const e of analyticsData) {
    eventCounts[e.type] = (eventCounts[e.type] || 0) + 1;
  }

  const metrics = {
    total_posts: totalPosts,
    published: publishedPosts,
    queued: queuedPosts,
    total_engagement: totalEngagement,
    avg_engagement: avgEngagement,
    engagement_entries: engagementData.length,
    analytics_events: analyticsData.length,
    event_breakdown: eventCounts,
  };

  return {
    status: "ok",
    generated_at: new Date().toISOString(),
    blog,
    social,
    metrics,
  };
}

// --- HTTP Server ---------------------------------------------------------- //

const DASHBOARD_PATH = path.join(__dirname, "demo-dashboard.html");

const server = http.createServer((req, res) => {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // Serve the visual dashboard
  if (req.method === "GET" && (req.url === "/" || req.url === "/demo")) {
    try {
      const html = fs.readFileSync(DASHBOARD_PATH, "utf-8");
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(html);
      console.log(`[${new Date().toISOString()}] GET ${req.url} — 200 (dashboard)`);
    } catch (err) {
      res.writeHead(500, { "Content-Type": "text/plain" });
      res.end("Dashboard file not found");
    }
    return;
  }

  if (req.method === "GET" && req.url === "/api/demo-output") {
    try {
      const response = buildDemoResponse();
      const json = JSON.stringify(response, null, 2);

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(json);

      // CLI output
      console.log(`[${new Date().toISOString()}] GET /api/demo-output — 200`);
    } catch (err) {
      console.error("[demoApi] Error:", err.message);
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "error", message: err.message }));
    }
    return;
  }

  if (req.method === "GET" && req.url === "/api/demo-output/cli") {
    try {
      const response = buildDemoResponse();
      const json = JSON.stringify(response, null, 2);

      // Print to console as well
      console.log("\n--- Demo Output (CLI) ---");
      console.log(json);
      console.log("--- End ---\n");

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(json);
    } catch (err) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "error", message: err.message }));
    }
    return;
  }

  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", service: "demo-api" }));
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not found", routes: ["/", "/demo", "/api/demo-output", "/api/demo-output/cli", "/health"] }));
});

// --- Start ---------------------------------------------------------------- //

if (require.main === module) {
  server.listen(PORT, () => {
    console.log(`Demo API running on http://localhost:${PORT}`);
    console.log(`\n  Dashboard:  http://localhost:${PORT}/`);
    console.log(`  JSON API:   http://localhost:${PORT}/api/demo-output`);
    console.log(`  CLI output: http://localhost:${PORT}/api/demo-output/cli`);
    console.log(`  Health:     http://localhost:${PORT}/health`);
    console.log("\nNo UI files modified. Backend-only.\n");
  });
}

module.exports = { buildDemoResponse, server };
