/**
 * Social Post Scheduler (MVP)
 *
 * Queue system for scheduling social posts with timestamps.
 * Stores to JSON file. Serverless-compatible.
 *
 * Env vars:
 *   SCHEDULE_STORE_PATH - Path to schedule JSON file (default: ./data/social_schedule.json)
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const STORE_PATH = process.env.SCHEDULE_STORE_PATH || path.join(__dirname, "..", "data", "social_schedule.json");

const VALID_PLATFORMS = new Set(["linkedin", "twitter", "instagram", "facebook", "caption"]);
const VALID_STATUSES = new Set(["queued", "published", "failed", "cancelled"]);

// --- Storage -------------------------------------------------------------- //

function readQueue() {
  try {
    if (!fs.existsSync(STORE_PATH)) return [];
    return JSON.parse(fs.readFileSync(STORE_PATH, "utf-8"));
  } catch {
    return [];
  }
}

function writeQueue(queue) {
  const dir = path.dirname(STORE_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(STORE_PATH, JSON.stringify(queue, null, 2), "utf-8");
}

// --- Public API ----------------------------------------------------------- //

/**
 * Schedule a post for future publishing.
 *
 * @param {object} post - The social post content object
 * @param {string} post.platform - Target platform (linkedin, twitter, instagram, facebook, caption)
 * @param {string} post.text - Post content text
 * @param {string|object} [post.meta] - Additional metadata (threadId, hashtags, etc.)
 * @param {string|Date} scheduledTime - ISO timestamp or Date for when to publish
 * @returns {object} { success, scheduleId, scheduledFor }
 */
function schedulePost(post, scheduledTime) {
  if (!post?.text) return { success: false, error: "post.text is required" };
  if (!post?.platform) return { success: false, error: "post.platform is required" };

  const platform = post.platform.toLowerCase();
  if (!VALID_PLATFORMS.has(platform)) {
    return { success: false, error: `Invalid platform: ${platform}. Allowed: ${[...VALID_PLATFORMS].join(", ")}` };
  }

  const scheduledFor = scheduledTime
    ? new Date(scheduledTime).toISOString()
    : new Date(Date.now() + 3600000).toISOString(); // default: 1 hour from now

  const entry = {
    scheduleId: crypto.randomUUID(),
    platform,
    text: post.text,
    meta: post.meta || null,
    hashtags: post.hashtags || [],
    status: "queued",
    scheduledFor,
    createdAt: new Date().toISOString(),
    publishedAt: null,
  };

  const queue = readQueue();
  queue.push(entry);
  writeQueue(queue);

  // Log to analytics
  try {
    const { logEvent } = require("./analytics");
    logEvent("social_post_scheduled", { scheduleId: entry.scheduleId, platform });
  } catch {
    // analytics not available
  }

  return { success: true, scheduleId: entry.scheduleId, scheduledFor };
}

/**
 * Schedule all social content from generateAllSocial() output.
 *
 * @param {object} socialContent - Output from socialGenerator.generateAllSocial()
 * @param {string|Date} [baseTime] - Base time for scheduling (staggers posts 2h apart)
 * @returns {object} { success, scheduled[] }
 */
function scheduleAllSocial(socialContent, baseTime) {
  const base = baseTime ? new Date(baseTime).getTime() : Date.now() + 3600000;
  const results = [];
  const gap = 2 * 3600000; // 2 hours between posts

  // LinkedIn
  if (socialContent.linkedin) {
    results.push(schedulePost(socialContent.linkedin, new Date(base)));
  }

  // Twitter (schedule first tweet, include thread as meta)
  if (socialContent.twitter?.tweets?.length) {
    const firstTweet = socialContent.twitter.tweets[0];
    results.push(schedulePost(
      {
        platform: "twitter",
        text: firstTweet.text,
        meta: { threadId: socialContent.twitter.threadId, tweets: socialContent.twitter.tweets },
        hashtags: [],
      },
      new Date(base + gap)
    ));
  }

  // Caption
  if (socialContent.caption) {
    results.push(schedulePost(socialContent.caption, new Date(base + gap * 2)));
  }

  return { success: true, scheduled: results };
}

/**
 * Get next posts due for publishing.
 *
 * @param {object} [opts]
 * @param {number} [opts.limit=10] - Max posts to return
 * @param {string} [opts.platform] - Filter by platform
 * @returns {object[]} Array of queued posts sorted by scheduledFor
 */
function getNextPosts({ limit = 10, platform } = {}) {
  const now = new Date().toISOString();
  let queue = readQueue().filter((p) => p.status === "queued");

  if (platform) {
    queue = queue.filter((p) => p.platform === platform.toLowerCase());
  }

  return queue
    .filter((p) => p.scheduledFor <= now)
    .sort((a, b) => a.scheduledFor.localeCompare(b.scheduledFor))
    .slice(0, limit);
}

/**
 * Get all upcoming (future) scheduled posts.
 *
 * @param {object} [opts]
 * @param {string} [opts.platform] - Filter by platform
 * @returns {object[]}
 */
function getUpcoming({ platform } = {}) {
  let queue = readQueue().filter((p) => p.status === "queued");

  if (platform) {
    queue = queue.filter((p) => p.platform === platform.toLowerCase());
  }

  return queue.sort((a, b) => a.scheduledFor.localeCompare(b.scheduledFor));
}

/**
 * Mark a scheduled post as published.
 *
 * @param {string} scheduleId
 * @returns {object} { success, post }
 */
function markPublished(scheduleId) {
  const queue = readQueue();
  const post = queue.find((p) => p.scheduleId === scheduleId);
  if (!post) return { success: false, error: "Post not found" };

  post.status = "published";
  post.publishedAt = new Date().toISOString();
  writeQueue(queue);

  // Log to analytics
  try {
    const { logEvent } = require("./analytics");
    logEvent("social_post_published", { scheduleId, platform: post.platform });
  } catch {
    // analytics not available
  }

  return { success: true, post };
}

/**
 * Get queue stats.
 * @returns {object} { total, queued, published, failed, byPlatform }
 */
function getQueueStats() {
  const queue = readQueue();
  const stats = { total: queue.length, queued: 0, published: 0, failed: 0, cancelled: 0, byPlatform: {} };

  for (const p of queue) {
    stats[p.status] = (stats[p.status] || 0) + 1;
    if (!stats.byPlatform[p.platform]) {
      stats.byPlatform[p.platform] = { queued: 0, published: 0, failed: 0 };
    }
    stats.byPlatform[p.platform][p.status] = (stats.byPlatform[p.platform][p.status] || 0) + 1;
  }

  return stats;
}

module.exports = {
  schedulePost,
  scheduleAllSocial,
  getNextPosts,
  getUpcoming,
  markPublished,
  getQueueStats,
};
