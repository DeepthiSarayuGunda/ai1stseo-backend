/**
 * Content Pipeline - SEO-Driven Blog Generation Orchestrator
 *
 * Connects seoService → blog_generator to produce keyword-driven blog content.
 * Flow:
 *   1. Accept a topic
 *   2. Call getKeywordData(topic) to fetch SEO metrics
 *   3. Extract primary_keyword, search_volume, competition
 *   4. Pass enriched input to blog generator
 *   5. Return structured blog JSON with SEO data embedded
 *
 * Serverless-compatible. No persistent state.
 */

const { getKeywordData } = require("./seoService");
const { generateBlog } = require("./blog_generator");

/**
 * Run the full SEO-driven blog generation pipeline.
 *
 * @param {object} params
 * @param {string} params.topic - Blog topic / seed keyword
 * @param {string} [params.locale="us"] - Country/database for SEO data
 * @param {string} [params.author] - Author name
 * @returns {Promise<object>} { blog, seoData, pipeline }
 */
async function runBlogPipeline({ topic, locale = "us", author }) {
  if (!topic) throw new Error("topic is required");

  const startTime = Date.now();
  const pipeline = { topic, locale, steps: [] };

  // Step 1: Fetch SEO keyword data
  let seoData;
  try {
    seoData = await getKeywordData(topic, locale);
    pipeline.steps.push({ step: "getKeywordData", status: "ok", keyword: seoData?.keyword });
  } catch (err) {
    // Graceful degradation: generate blog with topic as keyword if API fails
    seoData = {
      provider: "fallback",
      keyword: topic,
      searchVolume: 0,
      competition: 0,
      cpc: 0,
    };
    pipeline.steps.push({ step: "getKeywordData", status: "fallback", error: err.message });
  }

  // Step 2: Extract SEO signals
  const seoInput = {
    keyword: seoData.keyword || topic,
    searchVolume: seoData.searchVolume || 0,
    competition: seoData.competition || 0,
    cpc: seoData.cpc || 0,
  };
  pipeline.steps.push({ step: "extractSeoSignals", status: "ok", data: seoInput });

  // Step 3: Generate SEO-optimized blog
  const blog = generateBlog({ topic, seoData: seoInput, author });
  pipeline.steps.push({ step: "generateBlog", status: "ok", slug: blog.slug });

  pipeline.durationMs = Date.now() - startTime;

  return { blog, seoData, pipeline };
}

/**
 * Batch-generate blogs for multiple topics.
 *
 * @param {string[]} topics - Array of topics
 * @param {object} [opts] - Options passed to each pipeline run
 * @returns {Promise<object[]>} Array of pipeline results
 */
async function runBatchPipeline(topics, opts = {}) {
  if (!Array.isArray(topics) || !topics.length) {
    throw new Error("topics must be a non-empty array");
  }

  const results = [];
  for (const topic of topics) {
    const result = await runBlogPipeline({ topic, ...opts });
    results.push(result);
  }
  return results;
}

module.exports = { runBlogPipeline, runBatchPipeline };
