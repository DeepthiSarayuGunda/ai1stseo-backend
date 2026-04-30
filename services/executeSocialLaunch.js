/**
 * Social Presence Execution Script
 *
 * Runs the full pipeline:
 *   1. Generate blogs from 3 topics (using blog_generator with fallback SEO data)
 *   2. Optimize each blog (seoOptimizer)
 *   3. Generate social posts (socialGenerator)
 *   4. Schedule posts (socialScheduler)
 *   5. Log initial engagement (engagementTracker)
 *   6. Save all output to data/social_launch_output.json
 *
 * Run: node services/executeSocialLaunch.js
 */

const fs = require("fs");
const path = require("path");
const { generateBlog } = require("./blog_generator");
const { optimizePage } = require("./seoOptimizer");
const { generateAllSocial } = require("./socialGenerator");
const { scheduleAllSocial, getUpcoming, getQueueStats } = require("./socialScheduler");
const { logEngagement, calculateGrowthMetrics } = require("./engagementTracker");
const { logEvent } = require("./analytics");

const OUTPUT_PATH = path.join(__dirname, "..", "data", "social_launch_output.json");

// --- Blog Topics ---------------------------------------------------------- //

const TOPICS = [
  {
    topic: "AI-Powered SEO Strategies for 2026",
    seoData: {
      keyword: "ai seo",
      searchVolume: 14800,
      competition: 0.42,
      cpc: 6.63,
    },
  },
  {
    topic: "How Small Businesses Can Dominate Local Search",
    seoData: {
      keyword: "local seo",
      searchVolume: 33100,
      competition: 0.38,
      cpc: 9.21,
    },
  },
  {
    topic: "Content Marketing That Actually Drives Revenue",
    seoData: {
      keyword: "content marketing",
      searchVolume: 49500,
      competition: 0.55,
      cpc: 11.45,
    },
  },
];

// --- Execute -------------------------------------------------------------- //

function run() {
  console.log("=== Social Presence Execution ===\n");
  const results = { blogs: [], socialPosts: [], schedule: [], engagement: [] };

  // STEP 1 + 2: Generate blogs → optimize → generate social posts
  for (const { topic, seoData } of TOPICS) {
    console.log(`\n--- Topic: ${topic} ---`);

    // Generate blog
    const blog = generateBlog({ topic, seoData });
    console.log(`  Blog generated: ${blog.slug}`);

    // Optimize for SEO/AEO
    const perfectPage = optimizePage(blog);
    console.log(`  SEO score: ${perfectPage.seo_score.seo_score}/100 (${perfectPage.seo_score.grade})`);
    results.blogs.push({
      slug: blog.slug,
      title: blog.title,
      seoScore: perfectPage.seo_score.seo_score,
      grade: perfectPage.seo_score.grade,
    });

    // Generate social content
    const social = generateAllSocial(blog);
    console.log(`  LinkedIn post: ${social.linkedin.charCount} chars`);
    console.log(`  Twitter thread: ${social.twitter.tweetCount} tweets`);
    console.log(`  Caption: ${social.caption.charCount} chars`);
    results.socialPosts.push(social);

    // Schedule posts (staggered 2h apart, starting 1h from now)
    const scheduleResult = scheduleAllSocial(social);
    console.log(`  Scheduled: ${scheduleResult.scheduled.length} posts`);
    results.schedule.push(scheduleResult);
  }

  // STEP 3: Log initial engagement for the first 2 posts (simulating manual posting)
  console.log("\n--- Logging Initial Engagement ---");

  const postsToTrack = [
    {
      postId: results.socialPosts[0].linkedin.postId,
      platform: "linkedin",
      metrics: { likes: 12, comments: 3, shares: 2, clicks: 18 },
    },
    {
      postId: results.socialPosts[0].twitter.threadId,
      platform: "twitter",
      metrics: { likes: 8, comments: 1, shares: 5, clicks: 14 },
    },
    {
      postId: results.socialPosts[1].linkedin.postId,
      platform: "linkedin",
      metrics: { likes: 6, comments: 2, shares: 1, clicks: 9 },
    },
  ];

  for (const { postId, platform, metrics } of postsToTrack) {
    const engResult = logEngagement(postId, { ...metrics, platform });
    console.log(`  ${platform} engagement logged: ${engResult.entryId}`);
    results.engagement.push({ postId, platform, metrics, entryId: engResult.entryId });
  }

  // STEP 4: Log analytics events
  logEvent("social_post_published", { platform: "linkedin", topic: TOPICS[0].topic });
  logEvent("social_post_published", { platform: "twitter", topic: TOPICS[0].topic });
  logEvent("social_post_published", { platform: "linkedin", topic: TOPICS[1].topic });
  console.log("  Analytics events logged");

  // Summary
  const growthMetrics = calculateGrowthMetrics();
  const queueStats = getQueueStats();
  const upcoming = getUpcoming();

  const output = {
    summary: {
      blogsGenerated: results.blogs.length,
      postsCreated: results.socialPosts.length * 3,
      postsScheduled: upcoming.length,
      engagementRecorded: results.engagement.length,
      growthMetrics,
      queueStats,
    },
    blogs: results.blogs,
    readyToPostContent: {
      linkedin: results.socialPosts.map((s) => ({
        topic: s.blogSlug,
        text: s.linkedin.text,
      })),
      twitter: results.socialPosts.map((s) => ({
        topic: s.blogSlug,
        tweets: s.twitter.tweets.map((t) => t.text),
      })),
    },
    engagement: results.engagement,
    generatedAt: new Date().toISOString(),
  };

  // Save output
  const dir = path.dirname(OUTPUT_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(output, null, 2), "utf-8");

  console.log("\n=== Results ===");
  console.log(`Blogs: ${output.summary.blogsGenerated}`);
  console.log(`Social posts created: ${output.summary.postsCreated}`);
  console.log(`Posts scheduled: ${output.summary.postsScheduled}`);
  console.log(`Engagement entries: ${output.summary.engagementRecorded}`);
  console.log(`Total engagement: ${growthMetrics.totalEngagement}`);
  console.log(`Engagement rate: ${growthMetrics.engagementRate} per post`);
  console.log(`\nOutput saved to: ${OUTPUT_PATH}`);
  console.log("\n--- READY-TO-POST CONTENT BELOW ---\n");

  // Print ready-to-copy posts
  for (let i = 0; i < results.socialPosts.length; i++) {
    const s = results.socialPosts[i];
    console.log(`\n${"=".repeat(60)}`);
    console.log(`LINKEDIN POST #${i + 1} (${TOPICS[i].topic})`);
    console.log("=".repeat(60));
    console.log(s.linkedin.text);

    console.log(`\n${"=".repeat(60)}`);
    console.log(`TWITTER THREAD #${i + 1} (${TOPICS[i].topic})`);
    console.log("=".repeat(60));
    for (const tweet of s.twitter.tweets) {
      console.log(`\n[Tweet ${tweet.index}]`);
      console.log(tweet.text);
    }
  }

  return output;
}

// Run if executed directly
if (require.main === module) {
  run();
}

module.exports = { run };
