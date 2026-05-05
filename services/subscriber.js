/**
 * Subscriber Capture Module
 *
 * POST /subscribe handler logic.
 * Validates email, prevents duplicates, stores to JSON file.
 * Emits events to analytics and triggers welcome email.
 *
 * Serverless-compatible — uses flat-file storage (swap for DynamoDB/Redis in prod).
 *
 * Env vars:
 *   SUBSCRIBER_STORE_PATH - Path to subscribers JSON file (default: ./data/subscribers.json)
 */

const fs = require("fs");
const path = require("path");

const STORE_PATH = process.env.SUBSCRIBER_STORE_PATH || path.join(__dirname, "..", "data", "subscribers.json");

// --- Validation ----------------------------------------------------------- //

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function validateEmail(email) {
  if (!email || typeof email !== "string") return false;
  const trimmed = email.trim().toLowerCase();
  return EMAIL_RE.test(trimmed) && trimmed.length <= 254;
}

// --- Storage -------------------------------------------------------------- //

function readStore() {
  try {
    if (!fs.existsSync(STORE_PATH)) return [];
    const raw = fs.readFileSync(STORE_PATH, "utf-8");
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function writeStore(subscribers) {
  const dir = path.dirname(STORE_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(STORE_PATH, JSON.stringify(subscribers, null, 2), "utf-8");
}

function isDuplicate(email, subscribers) {
  const normalized = email.trim().toLowerCase();
  return subscribers.some((s) => s.email === normalized);
}

// --- Core ----------------------------------------------------------------- //

/**
 * Subscribe a new user.
 *
 * @param {object} payload
 * @param {string} payload.email - User email
 * @param {string} [payload.source] - Acquisition source (e.g. "homepage", "blog")
 * @param {string} [payload.timestamp] - Client timestamp (server timestamp used if omitted)
 * @returns {object} { success, message, subscriber? }
 */
async function subscribe(payload) {
  const { email, source, timestamp } = payload || {};

  // Validate
  if (!validateEmail(email)) {
    return { success: false, message: "Invalid email format" };
  }

  const normalized = email.trim().toLowerCase();
  const subscribers = readStore();

  // Duplicate check
  if (isDuplicate(normalized, subscribers)) {
    return { success: false, message: "Email already subscribed" };
  }

  const subscriber = {
    email: normalized,
    source: (source || "direct").toLowerCase().substring(0, 100),
    subscribedAt: new Date().toISOString(),
    clientTimestamp: timestamp || null,
  };

  subscribers.push(subscriber);
  writeStore(subscribers);

  // Trigger welcome email (async, non-blocking)
  try {
    const { sendWelcomeEmail } = require("./emailService");
    sendWelcomeEmail(normalized).catch((err) =>
      console.error("[subscriber] welcome email failed:", err.message)
    );
  } catch {
    // emailService not available — skip
  }

  // Log signup event (async, non-blocking)
  try {
    const { logEvent } = require("./analytics");
    logEvent("signup", { email: normalized, source: subscriber.source });
  } catch {
    // analytics not available — skip
  }

  return { success: true, message: "Subscribed successfully", subscriber };
}

/**
 * List all subscribers.
 * @param {object} [opts]
 * @param {number} [opts.limit] - Max results
 * @param {number} [opts.offset] - Skip count
 * @returns {object} { subscribers, total }
 */
function listSubscribers({ limit, offset = 0 } = {}) {
  const all = readStore();
  const sliced = limit ? all.slice(offset, offset + limit) : all.slice(offset);
  return { subscribers: sliced, total: all.length };
}

/**
 * Get subscriber count.
 * @returns {number}
 */
function getSubscriberCount() {
  return readStore().length;
}

module.exports = { subscribe, listSubscribers, getSubscriberCount, validateEmail };
