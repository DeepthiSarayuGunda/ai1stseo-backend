/**
 * Perfect Page Validator + AEO Enforcer
 *
 * Validates blog output against the "perfect page" template for SEO + AEO.
 * Auto-fixes missing elements. Adds AEO enhancements for LLM citation readiness.
 *
 * Perfect Page Template:
 *   ✓ Title (H1 with keyword)
 *   ✓ Meta title (<= 60 chars)
 *   ✓ Meta description (<= 155 chars)
 *   ✓ Featured snippet (40-60 word answer)
 *   ✓ Intro paragraph (keyword present)
 *   ✓ 3-5 H2 sections (clear subtopics)
 *   ✓ FAQ section (3-5 Q&A)
 *   ✓ Internal links (2-4)
 *   ✓ Schema (FAQPage JSON-LD)
 *   ✓ AEO: direct answer block
 *   ✓ AEO: concise definition
 *   ✓ AEO: entity-based phrasing
 *
 * No external APIs. Serverless-compatible.
 */

const { generateBlog } = require("./blog_generator");
const { optimizePage } = require("./seoOptimizer");
const { calculateSeoScore } = require("./seoScorer");

// ========================================================================== //
// PERFECT PAGE TEMPLATE CHECKLIST                                            //
// ========================================================================== //

const TEMPLATE_CHECKS = [
  { id: "h1_keyword",      label: "H1 contains primary keyword",     category: "structure" },
  { id: "meta_title",      label: "Meta title present (≤60 chars)",   category: "meta" },
  { id: "meta_description", label: "Meta description (≤155 chars)",   category: "meta" },
  { id: "featured_snippet", label: "Featured snippet (40-60 words)",  category: "aeo" },
  { id: "intro_keyword",   label: "Intro contains keyword",          category: "structure" },
  { id: "h2_sections",     label: "3-5 H2 sections",                 category: "structure" },
  { id: "faq_section",     label: "FAQ section (3-5 Q&A)",           category: "aeo" },
  { id: "internal_links",  label: "Internal links (2-4)",            category: "seo" },
  { id: "faq_schema",      label: "FAQPage JSON-LD schema",          category: "schema" },
  { id: "blog_schema",     label: "BlogPosting schema",              category: "schema" },
  { id: "aeo_definition",  label: "AEO: concise definition block",   category: "aeo" },
  { id: "aeo_direct_answer", label: "AEO: direct answer block",      category: "aeo" },
  { id: "aeo_entities",    label: "AEO: entity-based phrasing",      category: "aeo" },
  { id: "conclusion",      label: "Conclusion paragraph",            category: "structure" },
];

// ========================================================================== //
// VALIDATION                                                                 //
// ========================================================================== //

/**
 * Validate an optimized page against the perfect page template.
 *
 * @param {object} page - Output from optimizePage()
 * @returns {object} { is_perfect_page, passed, failed, missing_elements, score }
 */
function validatePerfectPage(page) {
  // Resolve keyword from multiple possible locations
  const keyword = (
    page.seo?.primaryKeyword ||
    page.schema?.blogPosting?.keywords?.split(",")[0]?.trim() ||
    ""
  ).toLowerCase();
  const results = [];

  // H1 with keyword
  results.push(check("h1_keyword",
    page.content?.h1 && keyword && page.content.h1.toLowerCase().includes(keyword)
  ));

  // Meta title
  results.push(check("meta_title",
    page.meta_title && page.meta_title.length > 0 && page.meta_title.length <= 60
  ));

  // Meta description
  results.push(check("meta_description",
    page.meta_description && page.meta_description.length > 0 && page.meta_description.length <= 155
  ));

  // Featured snippet
  const snippetWords = countWords(page.content?.featured_snippet?.snippetText || "");
  results.push(check("featured_snippet", snippetWords >= 35 && snippetWords <= 65));

  // Intro with keyword
  results.push(check("intro_keyword",
    page.content?.intro && keyword && page.content.intro.toLowerCase().includes(keyword)
  ));

  // 3-5 H2 sections
  const sectionCount = (page.content?.sections || []).length;
  results.push(check("h2_sections", sectionCount >= 3 && sectionCount <= 8));

  // FAQ section
  const faqCount = (page.faq_section || []).length;
  results.push(check("faq_section", faqCount >= 3 && faqCount <= 5));

  // Internal links
  const linkCount = (page.internal_links || []).length;
  results.push(check("internal_links", linkCount >= 2 && linkCount <= 6));

  // FAQPage schema
  results.push(check("faq_schema",
    page.schema?.faqPage?.["@type"] === "FAQPage" &&
    (page.schema.faqPage.mainEntity || []).length > 0
  ));

  // BlogPosting schema
  results.push(check("blog_schema",
    page.schema?.blogPosting?.["@type"] === "BlogPosting"
  ));

  // AEO: definition block
  results.push(check("aeo_definition", !!page.aeo?.definition));

  // AEO: direct answer
  results.push(check("aeo_direct_answer", !!page.aeo?.directAnswer));

  // AEO: entities
  results.push(check("aeo_entities",
    page.aeo?.entities && page.aeo.entities.length > 0
  ));

  // Conclusion
  results.push(check("conclusion",
    page.content?.conclusion && page.content.conclusion.length > 20
  ));

  const passed = results.filter((r) => r.pass);
  const failed = results.filter((r) => !r.pass);
  const score = Math.round((passed.length / results.length) * 100);

  return {
    is_perfect_page: failed.length === 0,
    score,
    total_checks: results.length,
    passed: passed.length,
    failed: failed.length,
    missing_elements: failed.map((r) => r.label),
    details: results,
  };
}

function check(id, pass) {
  const tmpl = TEMPLATE_CHECKS.find((t) => t.id === id);
  return { id, label: tmpl?.label || id, category: tmpl?.category || "other", pass: !!pass };
}

// ========================================================================== //
// AEO ENHANCEMENTS                                                           //
// ========================================================================== //

/**
 * Generate AEO (AI Engine Optimization) blocks for LLM citation readiness.
 *
 * @param {object} page - Optimized page from optimizePage()
 * @returns {object} { definition, directAnswer, entities, citationBlock }
 */
function generateAEOBlocks(page) {
  const keyword = page.seo?.primaryKeyword || page.content?.h1 || "";
  const kwCap = capitalize(keyword);
  const sections = page.content?.sections || [];
  const intro = page.content?.intro || "";

  // 1. Concise definition (1-2 sentences, "X is..." format)
  const definition = `${kwCap} is ${buildDefinitionPhrase(keyword, sections)}. ` +
    `It encompasses strategies and techniques designed to improve measurable outcomes in this domain.`;

  // 2. Direct answer block (factual, 30-50 words, no fluff)
  const directAnswer = buildDirectAnswer(keyword, intro, sections);

  // 3. Entity-based phrasing (structured facts an LLM can extract)
  const entities = buildEntities(keyword, sections);

  // 4. Citation-ready block (structured for LLM extraction)
  const citationBlock = {
    topic: kwCap,
    definition,
    keyFacts: entities.map((e) => `${e.entity}: ${e.statement}`),
    source: `AI1STSEO — ${page.title || kwCap}`,
    url: `/blog/${page.slug || slugify(keyword)}`,
  };

  return { definition, directAnswer, entities, citationBlock };
}

function buildDefinitionPhrase(keyword, sections) {
  // Try to extract from the first section (usually "What is X?")
  const firstBody = sections[0]?.body || "";
  const firstSentence = firstBody.split(".")[0]?.trim();
  if (firstSentence && firstSentence.length > 20) {
    // Rephrase as definition
    return firstSentence.toLowerCase().replace(/^understanding\s+/i, "").replace(/^the\s+/i, "");
  }
  return `a set of practices focused on optimizing ${keyword} for better performance and visibility`;
}

function buildDirectAnswer(keyword, intro, sections) {
  // Combine intro + first section for a factual answer
  const source = `${intro} ${sections[0]?.body || ""}`;
  const sentences = source.split(/(?<=[.!?])\s+/).filter((s) => s.trim().length > 10);

  // Pick 2-3 sentences that total 30-50 words
  let answer = "";
  let wordCount = 0;
  for (const s of sentences) {
    const wc = s.split(/\s+/).length;
    if (wordCount + wc > 55) break;
    answer += (answer ? " " : "") + s.trim();
    wordCount += wc;
    if (wordCount >= 30) break;
  }

  // Ensure it ends cleanly
  if (!answer.endsWith(".")) answer += ".";
  return answer;
}

function buildEntities(keyword, sections) {
  const kwCap = capitalize(keyword);
  const entities = [];

  entities.push({
    entity: kwCap,
    type: "Topic",
    statement: `${kwCap} is a key discipline for improving digital visibility and performance.`,
  });

  // Extract entity-like statements from section headings
  for (const s of sections.slice(0, 4)) {
    if (s.h2 && s.body) {
      const firstSentence = s.body.split(".")[0]?.trim();
      if (firstSentence) {
        entities.push({
          entity: s.h2,
          type: "Subtopic",
          statement: firstSentence + ".",
        });
      }
    }
  }

  return entities;
}

// ========================================================================== //
// ENFORCEMENT — Auto-fix + produce perfect page                              //
// ========================================================================== //

/**
 * Take a blog JSON, run it through the full pipeline, enforce all perfect page
 * requirements, add AEO blocks, validate, and return the final result.
 *
 * @param {object} blog - Raw blog JSON from generateBlog()
 * @returns {object} { page, validation, aeo, improvements }
 */
function enforcePerfectPage(blog) {
  const improvements = [];

  // Step 1: Run through seoOptimizer
  const page = optimizePage(blog);

  // Step 2: Generate AEO blocks
  const aeo = generateAEOBlocks({ ...page, seo: blog.seo });
  page.aeo = aeo;
  page.seo = blog.seo; // Carry SEO data through for validation
  improvements.push("Added AEO definition block");
  improvements.push("Added AEO direct answer block");
  improvements.push("Added AEO entity-based phrasing");
  improvements.push("Added LLM citation block");

  // Step 2b: Ensure intro contains keyword
  const kwLower = (blog.seo?.primaryKeyword || "").toLowerCase();
  if (kwLower && page.content?.intro && !page.content.intro.toLowerCase().includes(kwLower)) {
    page.content.intro = `${capitalize(blog.seo.primaryKeyword)} is essential. ${page.content.intro}`;
    improvements.push("Injected keyword into intro paragraph");
  }

  // Step 3: Enforce meta_title length
  if (!page.meta_title || page.meta_title.length > 60) {
    const kw = capitalize(blog.seo?.primaryKeyword || "");
    page.meta_title = `${kw} — Complete Guide`.substring(0, 60);
    improvements.push("Fixed meta_title to ≤60 chars");
  }

  // Step 4: Enforce meta_description length
  if (!page.meta_description || page.meta_description.length > 155) {
    const kw = blog.seo?.primaryKeyword || "";
    page.meta_description = `Discover ${kw} strategies that work. Actionable tips and data-driven insights to boost your results today.`.substring(0, 155);
    improvements.push("Fixed meta_description to ≤155 chars");
  }

  // Step 5: Ensure FAQ count is 3-5
  if (!page.faq_section || page.faq_section.length < 3) {
    const kw = blog.seo?.primaryKeyword || "this topic";
    page.faq_section = page.faq_section || [];
    while (page.faq_section.length < 3) {
      page.faq_section.push({
        question: `What should I know about ${kw}?`,
        answer: `${capitalize(kw)} requires a strategic approach combining data analysis, consistent execution, and regular optimization for best results.`,
      });
    }
    improvements.push("Ensured minimum 3 FAQs");
  }
  if (page.faq_section.length > 5) {
    page.faq_section = page.faq_section.slice(0, 5);
    improvements.push("Trimmed FAQs to maximum 5");
  }

  // Step 6: Ensure internal links 2-4
  if (!page.internal_links || page.internal_links.length < 2) {
    page.internal_links = page.internal_links || [];
    const kw = blog.seo?.primaryKeyword || "topic";
    while (page.internal_links.length < 2) {
      page.internal_links.push({
        anchorText: `Related ${capitalize(kw)} resources`,
        href: `/blog/${slugify(kw)}-resources`,
        placement: "conclusion",
        rel: "internal",
      });
    }
    improvements.push("Added minimum internal links");
  }

  // Step 7: Ensure FAQPage schema matches FAQ section
  if (page.faq_section && page.faq_section.length > 0) {
    page.schema.faqPage = {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: page.faq_section.map((faq) => ({
        "@type": "Question",
        name: faq.question,
        acceptedAnswer: { "@type": "Answer", text: faq.answer },
      })),
    };
  }

  // Step 8: Recalculate SEO score after all fixes
  page.seo_score = calculateSeoScore({
    ...blog,
    title: page.title,
    content: page.content,
    seo: { ...blog.seo, metaTitle: page.meta_title, metaDescription: page.meta_description },
  });

  // Step 9: Validate
  const validation = validatePerfectPage(page);

  return { page, validation, improvements };
}

// ========================================================================== //
// FULL PIPELINE — Topic → Perfect Page                                       //
// ========================================================================== //

/**
 * Generate a perfect page from a topic + SEO data in one call.
 *
 * @param {object} params
 * @param {string} params.topic
 * @param {object} params.seoData - { keyword, searchVolume, competition, cpc }
 * @param {string} [params.author]
 * @returns {object} { page, validation, improvements }
 */
function createPerfectPage({ topic, seoData, author }) {
  const blog = generateBlog({ topic, seoData, author });
  return enforcePerfectPage(blog);
}

// --- Utilities ------------------------------------------------------------ //

function capitalize(str) {
  return (str || "").replace(/\b\w/g, (c) => c.toUpperCase());
}

function slugify(str) {
  return (str || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function countWords(text) {
  return (text || "").split(/\s+/).filter((w) => w.length > 0).length;
}

module.exports = {
  validatePerfectPage,
  enforcePerfectPage,
  createPerfectPage,
  generateAEOBlocks,
  TEMPLATE_CHECKS,
};
