/**
 * SEO API Service - SEMrush Integration (Primary) + Ahrefs (Secondary)
 *
 * Serverless-compatible, stateless HTTP client.
 * Uses environment variables for all configuration.
 *
 * Required env vars:
 *   SEMRUSH_API_KEY   - SEMrush API key (from Subscription Info > API units)
 *   AHREFS_API_KEY    - Ahrefs API key (optional, for fallback/secondary use)
 *   SEO_API_PROVIDER  - "semrush" (default) or "ahrefs"
 *   SEO_API_TIMEOUT   - Request timeout in ms (default: 10000)
 */

const axios = require("axios");

// --- Config --------------------------------------------------------------- //

const config = {
  provider: process.env.SEO_API_PROVIDER || "semrush",
  semrush: {
    baseUrl: "https://api.semrush.com",
    apiKey: process.env.SEMRUSH_API_KEY,
  },
  ahrefs: {
    baseUrl: "https://api.ahrefs.com/v3",
    apiKey: process.env.AHREFS_API_KEY,
  },
  timeout: parseInt(process.env.SEO_API_TIMEOUT, 10) || 10000,
};

const http = axios.create({ timeout: config.timeout });

// --- SEMrush -------------------------------------------------------------- //

/**
 * Parse SEMrush CSV response into an array of objects.
 * First row is treated as headers.
 */
function parseSemrushCsv(csv) {
  const lines = csv.trim().split("\n");
  if (lines.length < 2) return [];
  const headers = lines[0].split(";").map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const values = line.split(";");
    const row = {};
    headers.forEach((h, i) => {
      row[h] = values[i] !== undefined ? values[i].trim() : null;
    });
    return row;
  });
}

async function semrushKeywordData(keyword, database = "us") {
  const { baseUrl, apiKey } = config.semrush;
  if (!apiKey) throw new Error("SEMRUSH_API_KEY is not set");

  const { data } = await http.get(baseUrl, {
    params: {
      type: "phrase_this",
      key: apiKey,
      phrase: keyword,
      database,
      export_columns: "Ph,Nq,Cp,Co,Nr,Td,Fk",
    },
  });
  const rows = parseSemrushCsv(data);
  if (!rows.length) return null;

  const r = rows[0];
  return {
    provider: "semrush",
    keyword: r.Ph || keyword,
    searchVolume: parseInt(r.Nq, 10) || 0,
    cpc: parseFloat(r.Cp) || 0,
    competition: parseFloat(r.Co) || 0,
    results: parseInt(r.Nr, 10) || 0,
    trend: r.Td || null,
    intent: r.Fk || null,
    database,
  };
}

async function semrushDomainOverview(domain, database = "us") {
  const { baseUrl, apiKey } = config.semrush;
  if (!apiKey) throw new Error("SEMRUSH_API_KEY is not set");

  const { data } = await http.get(baseUrl, {
    params: {
      type: "domain_ranks",
      key: apiKey,
      domain,
      database,
      export_columns: "Db,Dn,Rk,Or,Ot,Oc,Ad,At,Ac",
    },
  });
  const rows = parseSemrushCsv(data);
  if (!rows.length) return null;

  const r = rows[0];
  return {
    provider: "semrush",
    domain: r.Dn || domain,
    authorityRank: parseInt(r.Rk, 10) || 0,
    organicKeywords: parseInt(r.Or, 10) || 0,
    organicTraffic: parseInt(r.Ot, 10) || 0,
    organicCost: parseFloat(r.Oc) || 0,
    paidKeywords: parseInt(r.Ad, 10) || 0,
    paidTraffic: parseInt(r.At, 10) || 0,
    paidCost: parseFloat(r.Ac) || 0,
    database,
  };
}

async function semrushBacklinksOverview(target) {
  const { baseUrl, apiKey } = config.semrush;
  if (!apiKey) throw new Error("SEMRUSH_API_KEY is not set");

  const { data } = await http.get(baseUrl, {
    params: {
      type: "backlinks_overview",
      key: apiKey,
      target,
      export_columns: "total,domains_num,urls_num,ips_num,follows_num,nofollows_num",
      target_type: "root_domain",
    },
  });
  const rows = parseSemrushCsv(data);
  if (!rows.length) return null;

  const r = rows[0];
  return {
    provider: "semrush",
    target,
    totalBacklinks: parseInt(r.total, 10) || 0,
    referringDomains: parseInt(r.domains_num, 10) || 0,
    referringUrls: parseInt(r.urls_num, 10) || 0,
    referringIps: parseInt(r.ips_num, 10) || 0,
    followLinks: parseInt(r.follows_num, 10) || 0,
    nofollowLinks: parseInt(r.nofollows_num, 10) || 0,
  };
}

// --- Ahrefs --------------------------------------------------------------- //

async function ahrefsKeywordData(keyword, country = "us") {
  const { baseUrl, apiKey } = config.ahrefs;
  if (!apiKey) throw new Error("AHREFS_API_KEY is not set");

  const { data } = await http.get(`${baseUrl}/keywords-explorer/overview`, {
    headers: { Authorization: `Bearer ${apiKey}` },
    params: {
      keywords: keyword,
      country,
      select: "keyword,volume,difficulty,cpc,global_volume,traffic_potential",
    },
  });

  const kw = data?.keywords?.[0];
  if (!kw) return null;

  return {
    provider: "ahrefs",
    keyword: kw.keyword || keyword,
    searchVolume: kw.volume || 0,
    difficulty: kw.difficulty || 0,
    cpc: kw.cpc ? kw.cpc / 100 : 0, // Ahrefs returns CPC in cents
    globalVolume: kw.global_volume || 0,
    trafficPotential: kw.traffic_potential || 0,
    country,
  };
}

async function ahrefsDomainOverview(target) {
  const { baseUrl, apiKey } = config.ahrefs;
  if (!apiKey) throw new Error("AHREFS_API_KEY is not set");

  const { data } = await http.get(`${baseUrl}/site-explorer/overview`, {
    headers: { Authorization: `Bearer ${apiKey}` },
    params: {
      target,
      select: "domain_rating,organic_keywords,organic_traffic,backlinks,referring_domains",
    },
  });

  return {
    provider: "ahrefs",
    target,
    domainRating: data?.domain_rating || 0,
    organicKeywords: data?.organic_keywords || 0,
    organicTraffic: data?.organic_traffic || 0,
    backlinks: data?.backlinks || 0,
    referringDomains: data?.referring_domains || 0,
  };
}

// --- Unified Interface ---------------------------------------------------- //

/**
 * Get keyword data from the configured provider.
 * @param {string} keyword - The keyword to look up
 * @param {string} [locale="us"] - Country/database code
 * @returns {Promise<object>} Keyword metrics
 */
async function getKeywordData(keyword, locale = "us") {
  if (!keyword) throw new Error("keyword is required");

  if (config.provider === "ahrefs") {
    return ahrefsKeywordData(keyword, locale);
  }
  return semrushKeywordData(keyword, locale);
}

/**
 * Get domain overview from the configured provider.
 * @param {string} domain - The domain to analyze
 * @param {string} [locale="us"] - Country/database code
 * @returns {Promise<object>} Domain metrics
 */
async function getDomainOverview(domain, locale = "us") {
  if (!domain) throw new Error("domain is required");

  if (config.provider === "ahrefs") {
    return ahrefsDomainOverview(domain);
  }
  return semrushDomainOverview(domain, locale);
}

/**
 * Get backlinks overview (SEMrush only for now).
 * @param {string} target - Domain or URL
 * @returns {Promise<object>} Backlink metrics
 */
async function getBacklinksOverview(target) {
  if (!target) throw new Error("target is required");

  if (config.provider === "ahrefs") {
    // Ahrefs backlinks available via site-explorer/backlinks endpoint
    return ahrefsDomainOverview(target); // includes backlink count
  }
  return semrushBacklinksOverview(target);
}

// --- Exports -------------------------------------------------------------- //

module.exports = {
  getKeywordData,
  getDomainOverview,
  getBacklinksOverview,
  // Expose provider-specific functions for advanced use
  semrush: { semrushKeywordData, semrushDomainOverview, semrushBacklinksOverview },
  ahrefs: { ahrefsKeywordData, ahrefsDomainOverview },
  config,
};
