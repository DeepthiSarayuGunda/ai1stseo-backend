/**
 * SEO/AEO Perfect Page Optimizer
 *
 * Transforms blog JSON into a fully optimized "perfect page" for
 * both traditional SEO and AI Engine Optimization (AEO).
 *
 * Modules:
 *   1. Structure Validator — checks/fixes H1, H2s, paragraph readability
 *   2. Meta Optimization — generates meta_title (<=60) + meta_description (<=155)
 *   3. FAQ + AEO Block — generates 3-5 FAQs with JSON-LD schema
 *   4. Featured Snippet — extracts 40-60 word direct answer block
 *   5. Internal Linking — adds placeholder related article links
 *   6. SEO Score — via seoScorer.js
 *   7. Final Output — combined perfect page JSON
 *
 * No external paid APIs. Serverless-compatible.
 */

const { calculateSeoScore } = require("./seoScorer");

// ========================================================================== //
// MODULE 1 — Structure Validator                                             //
// ========================================================================== //

/**
 * Validate and auto-fix blog structure.
 * Ensures H1 has keyword, minimum H2 sections, readable paragraphs.
 *
 * @param {object} blog - Blog JSON (mutated in place)
 * @returns {object} { fixed, fixes[] }
 */
function validateStructure(blog) {
  const fixes = [];
  const keyword = blog.seo?.primaryKeyword || "";
  const kwLower = keyword.toLowerCase();

  // Ensure content object exists
  if (!blog.content) {
    blog.content = { h1: "", intro: "", sections: [], conclusion: "" };
    fixes.push("Created missing content object");
  }

  // Fix H1: must contain primary keyword
  if (!blog.content.h1) {
    blog.content.h1 = blog.title || capitalize(keyword);
    fixes.push("Set missing H1 from title");
  } else if (kwLower && !blog.content.h1.toLowerCase().includes(kwLower)) {
    blog.content.h1 = `${capitalize(keyword)}: ${blog.content.h1}`;
    fixes.push("Prepended primary keyword to H1");
  }

  // Sync title with H1
  blog.title = blog.content.h1;

  // Ensure minimum 3 H2 sections
  while (blog.content.sections.length < 3) {
    const idx = blog.content.sections.length + 1;
    blog.content.sections.push({
      h2: `${capitalize(keyword)} — Key Point ${idx}`,
      body: `This section covers an important aspect of ${keyword} that impacts your results.`,
    });
    fixes.push(`Added placeholder H2 section ${idx}`);
  }

  // Ensure intro contains keyword
  if (blog.content.intro && kwLower && !blog.content.intro.toLowerCase().includes(kwLower)) {
    blog.content.intro = `${capitalize(keyword)} is essential. ${blog.content.intro}`;
    fixes.push("Injected keyword into intro paragraph");
  }

  // Check paragraph readability — split any section body > 300 words
  const newSections = [];
  for (const section of blog.content.sections) {
    const words = (section.body || "").split(/\s+/);
    if (words.length > 300) {
      const mid = Math.ceil(words.length / 2);
      newSections.push({
        h2: section.h2,
        body: words.slice(0, mid).join(" "),
      });
      newSections.push({
        h2: `${section.h2} (Continued)`,
        body: words.slice(mid).join(" "),
      });
      fixes.push(`Split long section "${section.h2}" into two`);
    } else {
      newSections.push(section);
    }
  }
  blog.content.sections = newSections;

  return { fixed: fixes.length > 0, fixes };
}

// ========================================================================== //
// MODULE 2 — Meta Optimization                                               //
// ========================================================================== //

/**
 * Generate optimized meta_title and meta_description.
 *
 * @param {object} blog
 * @returns {object} { metaTitle, metaDescription }
 */
function optimizeMeta(blog) {
  const keyword = blog.seo?.primaryKeyword || "";
  const title = blog.title || blog.content?.h1 || "";

  // meta_title: <= 60 chars, keyword first, click intent
  let metaTitle = title;
  if (metaTitle.length > 60) {
    // Shorten: use keyword + truncated title
    metaTitle = keyword
      ? `${capitalize(keyword)} — ${title}`.substring(0, 57) + "..."
      : title.substring(0, 57) + "...";
  }
  // If title is short, add click intent
  if (metaTitle.length < 40 && keyword) {
    metaTitle = `${metaTitle} | Complete Guide`;
    if (metaTitle.length > 60) metaTitle = metaTitle.substring(0, 60);
  }

  // meta_description: <= 155 chars, keyword in first half, action-oriented
  let metaDescription = blog.seo?.metaDescription || "";
  if (!metaDescription || metaDescription.length > 155) {
    metaDescription = keyword
      ? `Discover ${keyword} strategies that work. Actionable tips, data-driven insights, and expert guidance to boost your results today.`
      : `Actionable strategies and data-driven insights to boost your results. Expert guidance you can apply today.`;
    if (metaDescription.length > 155) {
      metaDescription = metaDescription.substring(0, 152) + "...";
    }
  }

  // Store back on blog
  blog.seo = blog.seo || {};
  blog.seo.metaTitle = metaTitle;
  blog.seo.metaDescription = metaDescription;

  return { metaTitle, metaDescription };
}

// ========================================================================== //
// MODULE 3 — FAQ + AEO Block                                                //
// ========================================================================== //

/**
 * Generate 3-5 FAQs from blog content for AEO optimization.
 * Returns FAQ items + JSON-LD FAQPage schema.
 *
 * @param {object} blog
 * @returns {object} { faqs[], schema }
 */
function generateFAQBlock(blog) {
  const keyword = blog.seo?.primaryKeyword || "this topic";
  const sections = blog.content?.sections || [];

  // Generate questions from section headings + keyword
  const faqs = [];

  faqs.push({
    question: `What is ${keyword}?`,
    answer: extractFirstSentences(sections[0]?.body, 2) ||
      `${capitalize(keyword)} refers to the strategies and techniques used to improve performance and results in this area.`,
  });

  faqs.push({
    question: `Why is ${keyword} important?`,
    answer: extractFirstSentences(sections[sections.length - 1]?.body, 2) ||
      `${capitalize(keyword)} is important because it directly impacts visibility, engagement, and long-term growth.`,
  });

  faqs.push({
    question: `How do I get started with ${keyword}?`,
    answer: extractFirstSentences(sections[1]?.body, 2) ||
      `Start by understanding the fundamentals, then implement proven strategies step by step.`,
  });

  if (sections.length >= 4) {
    faqs.push({
      question: `What are the best ${keyword} strategies?`,
      answer: extractFirstSentences(sections[3]?.body, 2) ||
        `The best strategies combine data-driven insights with consistent execution and regular optimization.`,
    });
  }

  if (sections.length >= 5) {
    faqs.push({
      question: `How do I measure ${keyword} success?`,
      answer: extractFirstSentences(sections[4]?.body, 2) ||
        `Track key metrics like engagement, conversion rates, and ROI to measure the impact of your efforts.`,
    });
  }

  // JSON-LD FAQPage schema
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };

  return { faqs, schema };
}

// ========================================================================== //
// MODULE 4 — Featured Snippet Optimization                                   //
// ========================================================================== //

/**
 * Extract a 40-60 word direct answer block for featured snippet targeting.
 * Placed at the top of the article.
 *
 * @param {object} blog
 * @returns {object} { snippetText, wordCount, placement }
 */
function generateFeaturedSnippet(blog) {
  const keyword = blog.seo?.primaryKeyword || "";
  const intro = blog.content?.intro || "";
  const sections = blog.content?.sections || [];

  // Try to extract from intro first
  let candidate = extractWordRange(intro, 40, 60);

  // If intro is too short, combine with first section
  if (!candidate && sections.length > 0) {
    const combined = `${intro} ${sections[0]?.body || ""}`;
    candidate = extractWordRange(combined, 40, 60);
  }

  // Fallback: build a direct answer
  if (!candidate) {
    candidate = `${capitalize(keyword)} is a critical factor for success. ` +
      `It involves implementing proven strategies backed by data to improve visibility and results. ` +
      `This guide covers everything you need to know to get started and see measurable impact.`;
    candidate = extractWordRange(candidate, 40, 60);
  }

  return {
    snippetText: candidate,
    wordCount: countWords(candidate),
    placement: "top_of_article",
    targetQuery: keyword ? `what is ${keyword}` : null,
  };
}

// ========================================================================== //
// MODULE 5 — Internal Linking                                                //
// ========================================================================== //

/**
 * Generate internal link placeholders for related articles.
 * Uses keyword variations as anchor text.
 *
 * @param {object} blog
 * @returns {object[]} Array of { anchorText, href, placement }
 */
function generateInternalLinks(blog) {
  const keyword = blog.seo?.primaryKeyword || "";
  const variations = blog.seo?.keywordVariations || [];
  const slug = blog.slug || "article";

  const links = [];

  // Related article links based on keyword variations
  if (variations.length > 0) {
    links.push({
      anchorText: `Learn more about ${variations[0] || keyword}`,
      href: `/blog/${slugify(variations[0] || keyword)}`,
      placement: "intro",
      rel: "internal",
    });
  }

  if (variations.length > 1) {
    links.push({
      anchorText: `Read our ${variations[1] || keyword} guide`,
      href: `/blog/${slugify(variations[1] || keyword)}`,
      placement: "mid_content",
      rel: "internal",
    });
  }

  if (variations.length > 2) {
    links.push({
      anchorText: `Explore ${variations[2] || keyword}`,
      href: `/blog/${slugify(variations[2] || keyword)}`,
      placement: "conclusion",
      rel: "internal",
    });
  }

  // Pillar page link
  links.push({
    anchorText: `Complete ${capitalize(keyword)} resource hub`,
    href: `/resources/${slugify(keyword)}`,
    placement: "sidebar",
    rel: "pillar",
  });

  return links;
}

// ========================================================================== //
// MODULE 7 — Final Output (Perfect Page)                                     //
// ========================================================================== //

/**
 * Run the full optimization pipeline on a blog JSON.
 * Returns a "perfect page" ready for publishing.
 *
 * @param {object} blog - Blog JSON from generateBlog()
 * @returns {object} Perfect page JSON with all optimizations applied
 */
function optimizePage(blog) {
  if (!blog) throw new Error("blog is required");

  // Deep clone to avoid mutating original
  const page = JSON.parse(JSON.stringify(blog));

  // Module 1: Structure validation + auto-fix
  const structureResult = validateStructure(page);

  // Module 2: Meta optimization
  const meta = optimizeMeta(page);

  // Module 3: FAQ + AEO
  const faqBlock = generateFAQBlock(page);

  // Module 4: Featured snippet
  const snippet = generateFeaturedSnippet(page);

  // Module 5: Internal linking
  const internalLinks = generateInternalLinks(page);

  // Module 6: SEO score (via seoScorer)
  const seoScore = calculateSeoScore(page);

  // Module 7: Assemble final output
  return {
    // Core content
    title: page.title,
    slug: page.slug,
    author: page.author,

    // Meta
    meta_title: meta.metaTitle,
    meta_description: meta.metaDescription,

    // Content with featured snippet at top
    content: {
      featured_snippet: snippet,
      h1: page.content.h1,
      intro: page.content.intro,
      sections: page.content.sections,
      conclusion: page.content.conclusion,
    },

    // AEO
    faq_section: faqBlock.faqs,
    internal_links: internalLinks,

    // Schema markup
    schema: {
      blogPosting: page.schema,
      faqPage: faqBlock.schema,
    },

    // SEO analysis
    seo_score: seoScore,

    // Optimization metadata
    optimization: {
      structureFixes: structureResult.fixes,
      wasAutoFixed: structureResult.fixed,
      optimizedAt: new Date().toISOString(),
    },
  };
}

// --- Utilities ------------------------------------------------------------ //

function capitalize(str) {
  return str.replace(/\b\w/g, (c) => c.toUpperCase());
}

function slugify(str) {
  return (str || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function countWords(text) {
  return (text || "").split(/\s+/).filter((w) => w.length > 0).length;
}

function extractFirstSentences(text, count = 2) {
  if (!text) return "";
  const sentences = text.split(/(?<=[.!?])\s+/).slice(0, count);
  return sentences.join(" ").trim();
}

function extractWordRange(text, min, max) {
  if (!text) return null;
  const words = text.split(/\s+/).filter((w) => w.length > 0);
  if (words.length < min) return null;
  const slice = words.slice(0, max);
  let result = slice.join(" ");
  // Ensure it ends with a period
  if (!result.endsWith(".")) {
    result = result.replace(/[,;:!?]?$/, ".");
  }
  return result;
}

module.exports = {
  optimizePage,
  validateStructure,
  optimizeMeta,
  generateFAQBlock,
  generateFeaturedSnippet,
  generateInternalLinks,
};
