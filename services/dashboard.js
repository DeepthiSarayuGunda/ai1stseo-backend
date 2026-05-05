/**
 * Dashboard — Growth Summary Report Generator
 *
 * Aggregates data from kpiEngine, subscriber, and analytics
 * into a single JSON report. Serverless-compatible.
 *
 * Env vars:
 *   DASHBOARD_REPORT_PATH - Output path for JSON report (default: ./data/dashboard_report.json)
 */

const fs = require("fs");
const path = require("path");
const { calculateKPIs, getSignupTrend } = require("./kpiEngine");
const { listSubscribers } = require("./subscriber");
const { countByType } = require("./analytics");

const REPORT_PATH = process.env.DASHBOARD_REPORT_PATH || path.join(__dirname, "..", "data", "dashboard_report.json");

/**
 * Generate the full growth dashboard report.
 *
 * @param {object} [opts]
 * @param {number} [opts.days=30] - Reporting window
 * @param {boolean} [opts.save=false] - Write report to disk
 * @returns {object} Dashboard JSON
 */
function generateReport({ days = 30, save = false } = {}) {
  const kpis = calculateKPIs({ days });
  const { total: totalUsers } = listSubscribers();
  const signupTrend = getSignupTrend(days);
  const eventBreakdown = countByType(days);

  const report = {
    summary: {
      total_users: totalUsers,
      total_signups: kpis.totalSignups,
      conversion_rate: `${kpis.conversionRate}%`,
      engagement_score: kpis.engagementScore,
    },
    kpis,
    signupTrend,
    eventBreakdown,
    generatedAt: new Date().toISOString(),
  };

  if (save) {
    const dir = path.dirname(REPORT_PATH);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), "utf-8");
    report._savedTo = REPORT_PATH;
  }

  return report;
}

module.exports = { generateReport };
