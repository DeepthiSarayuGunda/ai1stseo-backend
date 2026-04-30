/**
 * SEO Score Engine
 *
 * Calculates a 0-100 SEO score for blog JSON based on:
 *   - Keyword usage score (density, placement, natural usage)
 *   - Structure score (H1, H2 count, paragraph length)
 *   - Readability score (sentence length, word count, scannability)
 *
 * No external APIs. Serverless-compatible.
 */

// --- Keyword Score (0-40) ------------------------------------------------- //

/**
 * Score keyword usage across the blog content.
 * Checks: H1 presence, intro presence, density, stuffing detection.
 *
 * @param {object} blog - Blog JSON
 * @returns {object} { score, max, issues, suggestions }
 */
function scoreKeywordUsage(blog) {
  const keyword = (blog.seo?.primaryKeyword || "").toLowerCase();
  if (!keyword) return { score: 0, max: 40, issues: ["No primary keyword defined"], suggestions: ["Set a primary keyword in seo.primaryKeyword"] };

  let score = 0;
  const issues = [];
  const suggestions = [];

  const h1 = (blog.content?.h1 || "").toLowerCase();
  const intro = (blog.content?.intro || "").toLowerCase();
  const conclusion = (blog.content?.conclusion || "").toLowerCase();
  const metaDesc = (blog.seo?.metaDescription || "").toLowerCase();
  const sections = blog.content?.sections || [];

  // H1 contains keyword (10 pts)
  if (h1.includes(keyword)) {
    score += 10;
  } else {
    issues.push("Primary keyword missing from H1");
    suggestions.push("Include the primary keyword in your H1 title");
  }

  // Intro contains keyword (8 pts)
  if (intro.includes(keyword)) {
    score += 8;
  } else {
    issues.push("Primary keyword missing from first paragraph");
    suggestions.push("Add the primary keyword to the opening paragraph");
  }

  // Meta description contains keyword (6 pts)
  if (metaDesc.includes(keyword)) {
    score += 6;
  } else {
    issues.push("Primary keyword missing from meta description");
    suggestions.push("Include the keyword in the meta description");
  }

  // Keyword in at least 2 H2 headings (6 pts)
  const h2WithKeyword = sections.filter((s) => (s.h2 || "").toLowerCase().includes(keyword)).length;
  if (h2WithKeyword >= 2) {
    score += 6;
  } else if (h2WithKeyword === 1) {
    score += 3;
    suggestions.push("Use the keyword in at least 2 subheadings");
  } else {
    issues.push("Primary keyword not found in any H2 headings");
    suggestions.push("Include the keyword naturally in subheadings");
  }

  // Conclusion contains keyword (4 pts)
  if (conclusion.includes(keyword)) {
    score += 4;
  } else {
    suggestions.push("Mention the keyword in the conclusion");
  }

  // Keyword density check (6 pts) — ideal: 1-3%
  const allText = gatherAllText(blog);
  const wordCount = countWords(allText);
  const kwCount = countOccurrences(allText.toLowerCase(), keyword);
  const density = wordCount > 0 ? (kwCount / wordCount) * 100 : 0;

  if (density >= 1 && density <= 3) {
    score += 6;
  } else if (density > 3) {
    score += 2;
    issues.push(`Keyword density too high (${density.toFixed(1)}%) — risk of stuffing`);
    suggestions.push("Reduce keyword repetition; use variations instead");
  } else if (density > 0) {
    score += 3;
    suggestions.push(`Keyword density is low (${density.toFixed(1)}%); aim for 1-3%`);
  } else {
    issues.push("Keyword not found in body content");
  }

  return { score, max: 40, density: parseFloat(density.toFixed(2)), issues, suggestions };
}

// --- Structure Score (0-30) ----------------------------------------------- //

/**
 * Score content structure.
 * Checks: H1 exists, H2 count, paragraph lengths, section balance.
 *
 * @param {object} blog
 * @returns {object} { score, max, issues, suggestions }
 */
function scoreStructure(blog) {
  let score = 0;
  const issues = [];
  const suggestions = [];
  const sections = blog.content?.sections || [];

  // H1 exists (5 pts)
  if (blog.content?.h1) {
    score += 5;
  } else {
    issues.push("Missing H1 heading");
  }

  // Minimum 2-3 H2 sections (8 pts)
  if (sections.length >= 3) {
    score += 8;
  } else if (sections.length === 2) {
    score += 5;
    suggestions.push("Add at least one more H2 section for better structure");
  } else {
    issues.push(`Only ${sections.length} H2 section(s) — need at least 2-3`);
    suggestions.push("Add more H2 sections to improve content depth");
  }

  // Intro exists (4 pts)
  if (blog.content?.intro && blog.content.intro.length > 50) {
    score += 4;
  } else {
    issues.push("Intro is missing or too short");
    suggestions.push("Write an intro paragraph of at least 50 characters");
  }

  // Conclusion exists (4 pts)
  if (blog.content?.conclusion && blog.content.conclusion.length > 30) {
    score += 4;
  } else {
    suggestions.push("Add a conclusion paragraph");
  }

  // Paragraphs are scannable — no section body > 300 words (5 pts)
  let allScannable = true;
  for (const s of sections) {
    const wc = countWords(s.body || "");
    if (wc > 300) {
      allScannable = false;
      suggestions.push(`Section "${s.h2}" is ${wc} words — consider splitting`);
    }
  }
  if (allScannable && sections.length > 0) {
    score += 5;
  } else if (sections.length > 0) {
    score += 2;
  }

  // Meta title length (4 pts)
  const metaTitle = blog.seo?.metaTitle || blog.title || "";
  if (metaTitle.length > 0 && metaTitle.length <= 60) {
    score += 4;
  } else if (metaTitle.length > 60) {
    score += 2;
    issues.push(`Meta title is ${metaTitle.length} chars — should be <= 60`);
  } else {
    issues.push("Missing meta title");
  }

  return { score, max: 30, sectionCount: sections.length, issues, suggestions };
}

// --- Readability Score (0-30) --------------------------------------------- //

/**
 * Score readability.
 * Checks: avg sentence length, total word count, paragraph variety.
 *
 * @param {object} blog
 * @returns {object} { score, max, wordCount, avgSentenceLength, issues, suggestions }
 */
function scoreReadability(blog) {
  let score = 0;
  const issues = [];
  const suggestions = [];

  const allText = gatherAllText(blog);
  const wordCount = countWords(allText);
  const sentences = allText.split(/[.!?]+/).filter((s) => s.trim().length > 0);
  const avgSentenceLength = sentences.length > 0 ? Math.round(wordCount / sentences.length) : 0;

  // Word count: 300+ is minimum, 800+ is good, 1500+ is great (10 pts)
  if (wordCount >= 1500) {
    score += 10;
  } else if (wordCount >= 800) {
    score += 7;
  } else if (wordCount >= 300) {
    score += 4;
    suggestions.push(`Content is ${wordCount} words — aim for 800+ for better ranking`);
  } else {
    issues.push(`Content is only ${wordCount} words — too thin for SEO`);
    suggestions.push("Expand content to at least 800 words");
  }

  // Average sentence length: 15-20 words is ideal (10 pts)
  if (avgSentenceLength >= 10 && avgSentenceLength <= 25) {
    score += 10;
  } else if (avgSentenceLength < 10) {
    score += 6;
    suggestions.push("Sentences are very short — add some variety");
  } else {
    score += 4;
    issues.push(`Average sentence length is ${avgSentenceLength} words — too long`);
    suggestions.push("Break long sentences into shorter, scannable ones");
  }

  // Content variety: has intro + sections + conclusion (10 pts)
  const hasIntro = (blog.content?.intro || "").length > 0;
  const hasSections = (blog.content?.sections || []).length > 0;
  const hasConclusion = (blog.content?.conclusion || "").length > 0;

  if (hasIntro && hasSections && hasConclusion) {
    score += 10;
  } else {
    score += 4;
    if (!hasIntro) suggestions.push("Add an introduction");
    if (!hasConclusion) suggestions.push("Add a conclusion");
  }

  return { score, max: 30, wordCount, avgSentenceLength, issues, suggestions };
}

// --- Combined Score ------------------------------------------------------- //

/**
 * Calculate the full SEO score for a blog.
 *
 * @param {object} blog - Blog JSON from generateBlog()
 * @returns {object} { seo_score, keyword, structure, readability, issues, suggestions }
 */
function calculateSeoScore(blog) {
  if (!blog?.content) throw new Error("Invalid blog JSON");

  const keyword = scoreKeywordUsage(blog);
  const structure = scoreStructure(blog);
  const readability = scoreReadability(blog);

  const totalScore = keyword.score + structure.score + readability.score;
  const maxScore = keyword.max + structure.max + readability.max;
  const seoScore = Math.round((totalScore / maxScore) * 100);

  const allIssues = [...keyword.issues, ...structure.issues, ...readability.issues];
  const allSuggestions = [...keyword.suggestions, ...structure.suggestions, ...readability.suggestions];

  return {
    seo_score: seoScore,
    breakdown: {
      keyword: { score: keyword.score, max: keyword.max, density: keyword.density },
      structure: { score: structure.score, max: structure.max, sections: structure.sectionCount },
      readability: { score: readability.score, max: readability.max, wordCount: readability.wordCount, avgSentenceLength: readability.avgSentenceLength },
    },
    issues: allIssues,
    suggestions: allSuggestions,
    grade: getGrade(seoScore),
  };
}

// --- Utilities ------------------------------------------------------------ //

function gatherAllText(blog) {
  const parts = [
    blog.content?.intro || "",
    ...(blog.content?.sections || []).map((s) => `${s.h2 || ""} ${s.body || ""}`),
    blog.content?.conclusion || "",
  ];
  return parts.join(" ");
}

function countWords(text) {
  return text.split(/\s+/).filter((w) => w.length > 0).length;
}

function countOccurrences(text, phrase) {
  if (!phrase) return 0;
  const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const matches = text.match(new RegExp(escaped, "gi"));
  return matches ? matches.length : 0;
}

function getGrade(score) {
  if (score >= 90) return "A+";
  if (score >= 80) return "A";
  if (score >= 70) return "B";
  if (score >= 60) return "C";
  if (score >= 50) return "D";
  return "F";
}

module.exports = {
  calculateSeoScore,
  scoreKeywordUsage,
  scoreStructure,
  scoreReadability,
};
