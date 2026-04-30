/**
 * Social Content Generator
 *
 * Transforms blog JSON (from blog_generator.js) into platform-specific social posts:
 *   - LinkedIn post (hook + paragraphs + CTA)
 *   - Twitter/X thread (3-5 tweets)
 *   - Short caption (Instagram/general)
 *
 * No external paid APIs required. Serverless-compatible.
 */

const crypto = require("crypto");

/**
 * Extract key content signals from a blog JSON object.
 * @param {object} blog - Output from generateBlog()
 * @returns {object} { title, keyword, intro, insights, conclusion, hashtags }
 */
function extractSignals(blog) {
  if (!blog?.content) throw new Error("Invalid blog JSON: missing content");

  const keyword = blog.seo?.primaryKeyword || "";
  const variations = blog.seo?.keywordVariations || [];
  const sections = blog.content.sections || [];

  // Pull key insights from section bodies (first sentence of each)
  const insights = sections
    .map((s) => s.body?.split(".")[0]?.trim())
    .filter(Boolean)
    .slice(0, 4);

  // Build hashtags from keyword + variations
  const hashtags = [keyword, ...variations.slice(0, 3)]
    .map((w) => "#" + w.replace(/\s+/g, "").replace(/[^a-zA-Z0-9]/g, ""))
    .filter((h) => h.length > 1);

  return {
    title: blog.title || blog.content.h1 || "",
    keyword,
    intro: blog.content.intro || "",
    insights,
    conclusion: blog.content.conclusion || "",
    hashtags,
  };
}

// --- LinkedIn ------------------------------------------------------------- //

/**
 * Generate a LinkedIn post from blog JSON.
 * Structure: strong hook (2 lines) → 3-5 short paragraphs → CTA
 *
 * @param {object} blog - Blog JSON from generateBlog()
 * @returns {object} { platform, postId, text, hashtags, charCount }
 */
function generateLinkedInPost(blog) {
  const { title, keyword, intro, insights, conclusion, hashtags } = extractSignals(blog);

  const hook = `${title}\n\nMost people get ${keyword} wrong. Here's what actually works:`;

  const body = insights
    .map((insight, i) => `${i + 1}. ${insight}.`)
    .join("\n\n");

  const cta = `What's your biggest challenge with ${keyword}? Drop it in the comments 👇`;

  const text = [hook, "", body, "", conclusion, "", cta, "", hashtags.join(" ")].join("\n");

  return {
    platform: "linkedin",
    postId: crypto.randomUUID(),
    text,
    hashtags,
    charCount: text.length,
    createdAt: new Date().toISOString(),
  };
}

// --- Twitter/X Thread ----------------------------------------------------- //

/**
 * Generate a Twitter/X thread (3-5 tweets) from blog JSON.
 * Tweet 1: hook, Tweets 2-4: insights, Final: CTA
 *
 * @param {object} blog - Blog JSON from generateBlog()
 * @returns {object} { platform, threadId, tweets[], tweetCount }
 */
function generateTwitterThread(blog) {
  const { title, keyword, insights, hashtags } = extractSignals(blog);
  const threadId = crypto.randomUUID();
  const tag = hashtags.slice(0, 2).join(" ");
  const tweets = [];

  // Tweet 1: Hook
  tweets.push({
    index: 1,
    text: truncate(`🧵 ${title}\n\nA thread on what actually moves the needle with ${keyword}:\n\n${tag}`, 280),
    type: "hook",
  });

  // Tweets 2-4: Insights
  insights.slice(0, 3).forEach((insight, i) => {
    tweets.push({
      index: i + 2,
      text: truncate(`${i + 2}/ ${insight}.\n\nThis is where most strategies fall short.`, 280),
      type: "insight",
    });
  });

  // Final tweet: CTA
  tweets.push({
    index: tweets.length + 1,
    text: truncate(`${tweets.length + 1}/ If this was useful, repost the first tweet.\n\nFollow for more on ${keyword}.\n\n${tag}`, 280),
    type: "cta",
  });

  return {
    platform: "twitter",
    threadId,
    tweets,
    tweetCount: tweets.length,
    createdAt: new Date().toISOString(),
  };
}

// --- Short Caption -------------------------------------------------------- //

/**
 * Generate a short caption (Instagram, general use).
 *
 * @param {object} blog - Blog JSON from generateBlog()
 * @returns {object} { platform, captionId, text, hashtags }
 */
function generateCaption(blog) {
  const { title, keyword, intro, hashtags } = extractSignals(blog);

  // Take first sentence of intro + keyword mention
  const firstSentence = intro.split(".")[0]?.trim() || title;
  const text = `${firstSentence}.\n\nLearn more about ${keyword} — link in bio.\n\n${hashtags.join(" ")}`;

  return {
    platform: "caption",
    captionId: crypto.randomUUID(),
    text: truncate(text, 2200),
    hashtags,
    charCount: text.length,
    createdAt: new Date().toISOString(),
  };
}

// --- Full Generation ------------------------------------------------------ //

/**
 * Generate all social content from a single blog JSON.
 *
 * @param {object} blog - Blog JSON from generateBlog()
 * @returns {object} { linkedin, twitter, caption, blogSlug }
 */
function generateAllSocial(blog) {
  const linkedin = generateLinkedInPost(blog);
  const twitter = generateTwitterThread(blog);
  const caption = generateCaption(blog);

  // Log to analytics if available
  try {
    const { logEvent } = require("./analytics");
    logEvent("social_post_created", {
      blogSlug: blog.slug,
      platforms: ["linkedin", "twitter", "caption"],
    });
  } catch {
    // analytics not available
  }

  return {
    blogSlug: blog.slug || null,
    linkedin,
    twitter,
    caption,
    generatedAt: new Date().toISOString(),
  };
}

// --- Utilities ------------------------------------------------------------ //

function truncate(str, max) {
  if (str.length <= max) return str;
  return str.substring(0, max - 3) + "...";
}

module.exports = {
  generateLinkedInPost,
  generateTwitterThread,
  generateCaption,
  generateAllSocial,
  extractSignals,
};
