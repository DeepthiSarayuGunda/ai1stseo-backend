/**
 * KPI Engine — Growth Metrics Calculator
 *
 * Computes:
 *   - total_signups
 *   - conversion_rate (signups / page_views)
 *   - engagement_score (weighted composite)
 *
 * Pulls data from analytics.js and subscriber.js.
 * Serverless-compatible, stateless.
 */

const { countByType, getEvents } = require("./analytics");
const { getSubscriberCount } = require("./subscriber");

/**
 * Calculate all KPIs for a given time window.
 *
 * @param {object} [opts]
 * @param {number} [opts.days=30] - Time window in days
 * @returns {object} KPI summary
 */
function calculateKPIs({ days = 30 } = {}) {
  const counts = countByType(days);

  const totalSignups = counts.signup || 0;
  const totalPageViews = counts.page_view || 0;
  const totalClicks = counts.click || 0;
  const totalEmailsSent = counts.email_sent || 0;
  const totalEmailsFailed = counts.email_failed || 0;
  const totalConversions = counts.conversion || 0;

  // Conversion rate: signups / page views
  const conversionRate = totalPageViews > 0
    ? parseFloat(((totalSignups / totalPageViews) * 100).toFixed(2))
    : 0;

  // Email delivery rate
  const totalEmailAttempts = totalEmailsSent + totalEmailsFailed;
  const emailDeliveryRate = totalEmailAttempts > 0
    ? parseFloat(((totalEmailsSent / totalEmailAttempts) * 100).toFixed(2))
    : 100;

  // Engagement score: weighted composite (0-100)
  // Weights: clicks (0.3), signups (0.4), conversions (0.3)
  const engagementScore = computeEngagementScore({
    pageViews: totalPageViews,
    clicks: totalClicks,
    signups: totalSignups,
    conversions: totalConversions,
  });

  return {
    period: `last_${days}_days`,
    totalSignups,
    totalPageViews,
    totalClicks,
    totalEmailsSent,
    totalEmailsFailed,
    totalConversions,
    conversionRate,
    emailDeliveryRate,
    engagementScore,
    totalSubscribers: getSubscriberCount(),
    social: getSocialKPIs(days),
    calculatedAt: new Date().toISOString(),
  };
}

/**
 * Calculate social-specific KPIs.
 * @param {number} days
 * @returns {object}
 */
function getSocialKPIs(days) {
  const counts = countByType(days);
  const totalPosts = (counts.social_post_created || 0);
  const totalScheduled = (counts.social_post_scheduled || 0);
  const totalPublished = (counts.social_post_published || 0);

  // Pull engagement totals from engagement events
  const engagementEvents = getEvents({ type: "social_engagement", days });
  let totalLikes = 0, totalComments = 0, totalShares = 0, totalSocialClicks = 0;
  for (const e of engagementEvents) {
    const d = e.data || {};
    totalLikes += d.likes || 0;
    totalComments += d.comments || 0;
    totalShares += d.shares || 0;
    totalSocialClicks += d.clicks || 0;
  }

  const totalEngagement = totalLikes + totalComments + totalShares + totalSocialClicks;
  const engagementRate = totalPublished > 0
    ? parseFloat((totalEngagement / totalPublished).toFixed(2))
    : 0;

  return {
    totalPosts,
    totalScheduled,
    totalPublished,
    totalEngagement,
    engagementRate,
    breakdown: { likes: totalLikes, comments: totalComments, shares: totalShares, clicks: totalSocialClicks },
  };
}

/**
 * Compute a 0-100 engagement score from event counts.
 *
 * Formula:
 *   clickRate = clicks / pageViews (capped at 1)
 *   signupRate = signups / pageViews (capped at 1)
 *   conversionRate = conversions / signups (capped at 1)
 *   score = (clickRate * 30) + (signupRate * 40) + (conversionRate * 30)
 */
function computeEngagementScore({ pageViews, clicks, signups, conversions }) {
  if (pageViews === 0) return 0;

  const clickRate = Math.min(clicks / pageViews, 1);
  const signupRate = Math.min(signups / pageViews, 1);
  const conversionRate = signups > 0 ? Math.min(conversions / signups, 1) : 0;

  const score = (clickRate * 30) + (signupRate * 40) + (conversionRate * 30);
  return parseFloat(score.toFixed(1));
}

/**
 * Get signup trend — daily signup counts for the period.
 *
 * @param {number} [days=30]
 * @returns {object[]} Array of { date, count }
 */
function getSignupTrend(days = 30) {
  const events = getEvents({ type: "signup", days });
  const byDate = {};

  for (const e of events) {
    const date = e.timestamp.substring(0, 10); // YYYY-MM-DD
    byDate[date] = (byDate[date] || 0) + 1;
  }

  return Object.entries(byDate)
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

module.exports = { calculateKPIs, computeEngagementScore, getSignupTrend };
