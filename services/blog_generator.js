/**
 * Blog Generator - SEO-Driven Blog Content Builder
 *
 * Produces structured blog JSON with keyword placement enforced:
 *   - Primary keyword in H1 title
 *   - Primary keyword in first paragraph
 *   - Keyword variations in subheadings
 *   - Meta description with primary keyword
 *
 * Designed to receive SEO data from seoService and produce
 * publish-ready blog JSON. Serverless-compatible.
 */

/**
 * Build keyword variations from a primary keyword.
 * Generates long-tail and related phrasing for subheadings.
 * @param {string} keyword
 * @returns {string[]}
 */
function buildKeywordVariations(keyword) {
  const base = keyword.toLowerCase().trim();
  return [
    `best ${base}`,
    `how to use ${base}`,
    `${base} guide`,
    `${base} tips and strategies`,
    `why ${base} matters`,
  ];
}

/**
 * Generate an SEO-optimized blog post from a topic and keyword data.
 *
 * @param {object} params
 * @param {string} params.topic - The blog topic / working title
 * @param {object} params.seoData - Output from seoService.getKeywordData()
 * @param {string} params.seoData.keyword - Primary keyword
 * @param {number} params.seoData.searchVolume - Monthly search volume
 * @param {number} params.seoData.competition - Competition score (0-1)
 * @param {number} [params.seoData.cpc] - Cost per click
 * @param {string} [params.author] - Author name
 * @returns {object} Structured blog JSON
 */
function generateBlog({ topic, seoData, author = "AI1STSEO Team" }) {
  if (!topic) throw new Error("topic is required");
  if (!seoData?.keyword) throw new Error("seoData.keyword is required");

  const primaryKeyword = seoData.keyword;
  const variations = buildKeywordVariations(primaryKeyword);
  const now = new Date().toISOString();

  // Title: include primary keyword naturally
  const title = buildTitle(topic, primaryKeyword);

  // Meta description: 150-160 chars, keyword in first half
  const metaDescription = buildMetaDescription(primaryKeyword, topic);

  // Sections with keyword variations in headings
  const sections = buildSections(primaryKeyword, variations, topic);

  return {
    title,
    slug: slugify(title),
    author,
    publishedAt: null,
    createdAt: now,
    seo: {
      primaryKeyword,
      searchVolume: seoData.searchVolume || 0,
      competition: seoData.competition || 0,
      cpc: seoData.cpc || 0,
      metaDescription,
      keywordVariations: variations,
    },
    content: {
      h1: title,
      intro: buildIntro(primaryKeyword, topic),
      sections,
      conclusion: buildConclusion(primaryKeyword),
    },
    schema: {
      "@type": "BlogPosting",
      headline: title,
      description: metaDescription,
      author: { "@type": "Person", name: author },
      keywords: [primaryKeyword, ...variations.slice(0, 3)].join(", "),
    },
  };
}

// --- Internal builders ---------------------------------------------------- //

function buildTitle(topic, keyword) {
  const kw = capitalize(keyword);
  // If topic already contains the keyword, use it directly
  if (topic.toLowerCase().includes(keyword.toLowerCase())) {
    return topic;
  }
  return `${kw}: ${topic}`;
}

function buildMetaDescription(keyword, topic) {
  const desc = `Learn about ${keyword} and discover actionable strategies for ${topic.toLowerCase()}. Data-driven insights to boost your results.`;
  // Trim to 160 chars max
  return desc.length > 160 ? desc.substring(0, 157) + "..." : desc;
}

function buildIntro(keyword, topic) {
  // Primary keyword appears in the first paragraph
  return (
    `${capitalize(keyword)} is one of the most important factors in ${topic.toLowerCase()} today. ` +
    `In this guide, we break down everything you need to know about ${keyword}, ` +
    `backed by real search data and proven strategies.`
  );
}

function buildSections(keyword, variations, topic) {
  return [
    {
      h2: `What Is ${capitalize(keyword)}?`,
      body: `Understanding ${keyword} is the first step toward building a strong strategy for ${topic.toLowerCase()}. Here we cover the fundamentals.`,
    },
    {
      h2: capitalize(variations[0]),
      body: `We compare the top options for ${keyword} so you can make an informed decision based on performance and value.`,
    },
    {
      h2: capitalize(variations[1]),
      body: `A step-by-step walkthrough on implementing ${keyword} effectively in your workflow.`,
    },
    {
      h2: capitalize(variations[2]),
      body: `This comprehensive ${keyword} guide covers beginner to advanced techniques you can apply immediately.`,
    },
    {
      h2: capitalize(variations[3]),
      body: `Proven ${keyword} tips and strategies from industry experts to accelerate your results.`,
    },
    {
      h2: capitalize(variations[4]),
      body: `Why investing in ${keyword} delivers long-term ROI and how to measure its impact on your business.`,
    },
  ];
}

function buildConclusion(keyword) {
  return (
    `${capitalize(keyword)} continues to evolve, and staying ahead means acting on data, not guesswork. ` +
    `Use the strategies in this guide to build a sustainable, results-driven approach to ${keyword}.`
  );
}

// --- Utilities ------------------------------------------------------------ //

function capitalize(str) {
  return str.replace(/\b\w/g, (c) => c.toUpperCase());
}

function slugify(str) {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

module.exports = { generateBlog, buildKeywordVariations };
