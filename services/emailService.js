/**
 * Email Service — Welcome Email Automation
 *
 * Sends welcome email after successful subscription.
 * Uses Resend API (primary) with nodemailer SMTP fallback.
 *
 * Serverless-compatible. Async sending with error logging.
 *
 * Env vars:
 *   EMAIL_PROVIDER       - "resend" (default) or "smtp"
 *   RESEND_API_KEY       - Resend API key
 *   EMAIL_FROM           - Sender address (default: onboarding@ai1stseo.com)
 *   SMTP_HOST            - SMTP host (for smtp provider)
 *   SMTP_PORT            - SMTP port (default: 587)
 *   SMTP_USER            - SMTP username
 *   SMTP_PASS            - SMTP password
 */

const axios = require("axios");

const config = {
  provider: process.env.EMAIL_PROVIDER || "resend",
  from: process.env.EMAIL_FROM || "onboarding@ai1stseo.com",
  resend: {
    apiKey: process.env.RESEND_API_KEY,
    baseUrl: "https://api.resend.com",
  },
  smtp: {
    host: process.env.SMTP_HOST,
    port: parseInt(process.env.SMTP_PORT, 10) || 587,
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS,
  },
};

// --- Email Templates ------------------------------------------------------ //

function buildWelcomeEmail(email) {
  return {
    to: email,
    from: config.from,
    subject: "Welcome to AI1STSEO — Here's What's Next",
    html: `
      <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #1a1a2e;">Welcome aboard!</h1>
        <p>Thanks for subscribing to AI1STSEO. You're now part of a community focused on data-driven SEO growth.</p>
        <h2 style="color: #16213e;">Here's what you get:</h2>
        <ul>
          <li>Weekly SEO insights and keyword opportunities</li>
          <li>Access to our content optimization tools</li>
          <li>Priority updates on new features</li>
        </ul>
        <h2 style="color: #16213e;">Your next step:</h2>
        <p>
          <a href="https://ai1stseo.com/dashboard" 
             style="display: inline-block; background: #0f3460; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
            Explore Your Dashboard
          </a>
        </p>
        <p style="color: #666; font-size: 14px; margin-top: 30px;">
          Questions? Just reply to this email. We read every message.
        </p>
      </div>
    `,
    text: [
      "Welcome aboard!",
      "",
      "Thanks for subscribing to AI1STSEO. You're now part of a community focused on data-driven SEO growth.",
      "",
      "Here's what you get:",
      "- Weekly SEO insights and keyword opportunities",
      "- Access to our content optimization tools",
      "- Priority updates on new features",
      "",
      "Your next step: Visit https://ai1stseo.com/dashboard",
      "",
      "Questions? Just reply to this email.",
    ].join("\n"),
  };
}

// --- Senders -------------------------------------------------------------- //

async function sendViaResend(emailData) {
  const { apiKey, baseUrl } = config.resend;
  if (!apiKey) throw new Error("RESEND_API_KEY is not set");

  const { data } = await axios.post(
    `${baseUrl}/emails`,
    {
      from: emailData.from,
      to: [emailData.to],
      subject: emailData.subject,
      html: emailData.html,
      text: emailData.text,
    },
    {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      timeout: 10000,
    }
  );

  return { success: true, provider: "resend", id: data.id };
}

async function sendViaSmtp(emailData) {
  // Lazy-load nodemailer only when SMTP is selected
  let nodemailer;
  try {
    nodemailer = require("nodemailer");
  } catch {
    throw new Error("nodemailer is not installed. Run: npm install nodemailer");
  }

  const { host, port, user, pass } = config.smtp;
  if (!host || !user) throw new Error("SMTP_HOST and SMTP_USER are required");

  const transporter = nodemailer.createTransport({
    host,
    port,
    secure: port === 465,
    auth: { user, pass },
  });

  const info = await transporter.sendMail({
    from: emailData.from,
    to: emailData.to,
    subject: emailData.subject,
    html: emailData.html,
    text: emailData.text,
  });

  return { success: true, provider: "smtp", messageId: info.messageId };
}

// --- Public API ----------------------------------------------------------- //

/**
 * Send the welcome email to a new subscriber.
 * @param {string} email - Recipient email
 * @returns {Promise<object>} Send result
 */
async function sendWelcomeEmail(email) {
  if (!email) throw new Error("email is required");

  const emailData = buildWelcomeEmail(email);

  try {
    const result =
      config.provider === "smtp"
        ? await sendViaSmtp(emailData)
        : await sendViaResend(emailData);

    // Log success
    try {
      const { logEvent } = require("./analytics");
      logEvent("email_sent", { email, type: "welcome", provider: result.provider });
    } catch {
      // analytics not available
    }

    return result;
  } catch (err) {
    console.error("[emailService] send failed:", err.message);

    // Log failure
    try {
      const { logEvent } = require("./analytics");
      logEvent("email_failed", { email, type: "welcome", error: err.message });
    } catch {
      // analytics not available
    }

    return { success: false, error: err.message };
  }
}

/**
 * Send a custom email.
 * @param {object} opts - { to, subject, html, text }
 * @returns {Promise<object>}
 */
async function sendEmail({ to, subject, html, text }) {
  const emailData = { to, from: config.from, subject, html, text };
  return config.provider === "smtp"
    ? sendViaSmtp(emailData)
    : sendViaResend(emailData);
}

module.exports = { sendWelcomeEmail, sendEmail, config };
