/**
 * Engagement Tracker
 *
 * Tracks social post engagement metrics (likes, comments, shares, clicks).
 * Stores to JSON file. Connects to KPI engine via analytics events.
 *
 * Serverless-compatible.
 *
 * Env vars:
 *   ENGAGEMENT_STORE_PATH - Path to engagement JSON file (default: ./data/engagement.json)
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const STORE_PATH = process.env.ENGAGEMENT_STORE_PATH || path.join(__dirname, "..", "data", "engagement.json");

// --- Storage -------------------------------------------------------------- //

function readStore() {
  try {
    if (!fs.existsSync(STORE_PATH)) return [];
    return JSON.parse(fs.readFileSync(STORE_PATH, "utf-8"));
  } catch {
    return [];
  }
}

function writeStore(data) {
  const dir = path.dirname(STORE_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(STORE_PATH, JSON.stringify(data, null, 2), "utf-8");
}

// --- Public API ----------------------------------------------------------- //

/**
 * Log engagement metrics for a social post.
 *
 * @param {string} postId - The post or schedule ID
 * @param {object} metrics
 * @param {number} [metrics.likes=0]
 * @param {number} [metrics.comments=0]
 * @param {number} [metrics.shares=0]
 * @param {number} [metrics.clicks=0]
 * @param {string} [metrics.platform] - Platform name
 * @returns {object} { success, entryId }
 */
function logEngagement(postId, metrics = {}) {
  if (!postId) return { success: false, error: "postId is required" };

  const entry = {
    entryId: crypto.randomUUID(),
    postId,
    platform: metrics.platform || "unknown",
    likes: Math.max(0, parseInt(metrics.likes, 10) || 0),
    comments: Math.max(0, parseInt(metrics.comments, 10) || 0),
    shares: Math.max(0, parseInt(metrics.shares, 10) || 0),
    clicks: Math.max(0, parseInt(metrics.clicks, 10) || 0),
    timestamp: new Date().toISOString(),
  };

  entry.totalEngagement = entry.likes + entry.comments + entry.shares + entry.clicks;

  const store = readStore();
  store.push(entry);
  writeStore(store);

  // Push to analytics for KPI engine
  try {
    const { logEvent } = require("./analytics");
    logEvent("social_engagement", {
      postId,
      platform: entry.platform,
      likes: entry.likes,
      comments: entry.comments,
      shares: entry.shares,
      clicks: entry.clicks,
      total: entry.totalEngagement,
    });
  } catch {
    // analytics not available
  }

  return { success: true, entryId: entry.entryId };
}

/**
 * Get engagement history for a specific post.
 *
 * @param {string} postId
 * @returns {object[]} Array of engagement entries
 */
function getPostEngagement(postId) {
  return readStore().filter((e) => e.postId === postId);
}

/**
 * Get aggregated engagement for a post (latest cumulative snapshot).
 *
 * @param {string} postId
 * @returns {object|null} { likes, comments, shares, clicks, total } or null
 */
function getPostTotals(postId) {
  const entries = getPostEngagement(postId);
  if (!entries.length) return null;

  // Return the most recent entry (assumes cumulative logging)
  const latest = entries[entries.length - 1];
  return {
    postId,
    platform: latest.platform,
    likes: latest.likes,
    comments: latest.comments,
    shares: latest.shares,
    clicks: latest.clicks,
    totalEngagement: latest.totalEngagement,
    lastUpdated: latest.timestamp,
  };
}

/**
 * Calculate growth metrics across all tracked posts.
 *
 * @param {object} [opts]
 * @param {number} [opts.days] - Only include entries from last N days
 * @returns {object} { totalPosts, totalEngagement, engagementRate, breakdown, topPosts }
 */
function calculateGrowthMetrics({ days } = {}) {
  let entries = readStore();

  if (days) {
    const cutoff = new Date(Date.now() - days * 86400000).toISOString();
    entries = entries.filter((e) => e.timestamp >= cutoff);
  }

  // Group by postId, take latest entry per post
  const byPost = {};
  for (const e of entries) {
    byPost[e.postId] = e;
  }

  const posts = Object.values(byPost);
  const totalPosts = posts.length;

  let totalLikes = 0, totalComments = 0, totalShares = 0, totalClicks = 0;
  for (const p of posts) {
    totalLikes += p.likes;
    totalComments += p.comments;
    totalShares += p.shares;
    totalClicks += p.clicks;
  }

  const totalEngagement = totalLikes + totalComments + totalShares + totalClicks;
  const engagementRate = totalPosts > 0
    ? parseFloat((totalEngagement / totalPosts).toFixed(2))
    : 0;

  // Top 5 posts by total engagement
  const topPosts = posts
    .sort((a, b) => b.totalEngagement - a.totalEngagement)
    .slice(0, 5)
    .map((p) => ({ postId: p.postId, platform: p.platform, total: p.totalEngagement }));

  return {
    totalPosts,
    totalEngagement,
    engagementRate,
    breakdown: { likes: totalLikes, comments: totalComments, shares: totalShares, clicks: totalClicks },
    topPosts,
    calculatedAt: new Date().toISOString(),
  };
}

module.exports = {
  logEngagement,
  getPostEngagement,
  getPostTotals,
  calculateGrowthMetrics,
};
