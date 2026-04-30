/**
 * Analytics Module — Lightweight Event Tracking
 *
 * Tracks: page_view, click, signup, email_sent, email_failed, conversion
 * Stores events to JSON file. Serverless-compatible.
 *
 * Env vars:
 *   ANALYTICS_STORE_PATH - Path to events JSON file (default: ./data/analytics_events.json)
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const STORE_PATH = process.env.ANALYTICS_STORE_PATH || path.join(__dirname, "..", "data", "analytics_events.json");

const ALLOWED_TYPES = new Set([
  "page_view",
  "click",
  "signup",
  "email_sent",
  "email_failed",
  "conversion",
  "social_post_created",
  "social_post_scheduled",
  "social_post_published",
  "social_engagement",
]);

// --- Storage -------------------------------------------------------------- //

function readEvents() {
  try {
    if (!fs.existsSync(STORE_PATH)) return [];
    return JSON.parse(fs.readFileSync(STORE_PATH, "utf-8"));
  } catch {
    return [];
  }
}

function appendEvent(event) {
  const dir = path.dirname(STORE_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const events = readEvents();
  events.push(event);
  fs.writeFileSync(STORE_PATH, JSON.stringify(events, null, 2), "utf-8");
}

// --- Public API ----------------------------------------------------------- //

/**
 * Log an analytics event.
 *
 * @param {string} type - Event type (page_view, click, signup, email_sent, email_failed, conversion)
 * @param {object} [data] - Arbitrary event payload
 * @returns {object} { success, eventId }
 */
function logEvent(type, data = {}) {
  if (!type || !ALLOWED_TYPES.has(type)) {
    return {
      success: false,
      error: `Invalid event type: ${type}. Allowed: ${[...ALLOWED_TYPES].join(", ")}`,
    };
  }

  const event = {
    eventId: crypto.randomUUID(),
    type,
    data,
    timestamp: new Date().toISOString(),
  };

  try {
    appendEvent(event);
    return { success: true, eventId: event.eventId };
  } catch (err) {
    console.error("[analytics] logEvent failed:", err.message);
    return { success: false, error: err.message };
  }
}

/**
 * Get events, optionally filtered by type and date range.
 *
 * @param {object} [opts]
 * @param {string} [opts.type] - Filter by event type
 * @param {number} [opts.days] - Only events from last N days
 * @param {number} [opts.limit] - Max results
 * @returns {object[]}
 */
function getEvents({ type, days, limit } = {}) {
  let events = readEvents();

  if (type) {
    events = events.filter((e) => e.type === type);
  }

  if (days) {
    const cutoff = new Date(Date.now() - days * 86400000).toISOString();
    events = events.filter((e) => e.timestamp >= cutoff);
  }

  if (limit) {
    events = events.slice(-limit);
  }

  return events;
}

/**
 * Count events by type.
 * @param {number} [days] - Only count events from last N days
 * @returns {object} Map of type → count
 */
function countByType(days) {
  const events = days ? getEvents({ days }) : readEvents();
  const counts = {};
  for (const e of events) {
    counts[e.type] = (counts[e.type] || 0) + 1;
  }
  return counts;
}

module.exports = { logEvent, getEvents, countByType, ALLOWED_TYPES };
