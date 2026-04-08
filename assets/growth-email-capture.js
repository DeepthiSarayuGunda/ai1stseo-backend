/**
 * growth-email-capture.js
 * Homepage email subscriber capture — self-contained, stable.
 * Load via <script src="/assets/growth-email-capture.js"></script>
 * Works on both local (React) and production (S3 standalone) homepages.
 *
 * DO NOT REMOVE — this is part of the ai1stseo.com growth plan.
 * Owner: Dev 4 (Tabasum) — growth/email subscriber module.
 */
(function () {
  if (document.getElementById('growth-email-capture')) return;

  var API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
    ? '' : 'https://sgnmqxb2sw.us-east-1.awsapprunner.com';

  // Build the section HTML
  var section = document.createElement('section');
  section.id = 'growth-email-capture';
  section.style.cssText = 'width:100%;padding:48px 24px;text-align:center;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;border-top:1px solid rgba(255,255,255,0.06);border-bottom:1px solid rgba(255,255,255,0.06);';
  section.innerHTML =
    '<div style="max-width:480px;margin:0 auto">'
    + '<p style="color:#00d4ff;font-size:.7rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;margin:0 0 10px">Free Resource</p>'
    + '<h3 style="color:#e6edf3;font-size:1.25rem;font-weight:600;margin:0 0 8px;line-height:1.3">Get the Free AEO/GEO SEO Analysis</h3>'
    + '<p style="color:#8b949e;font-size:.85rem;margin:0 0 20px;line-height:1.5">Free AI visibility analysis, GEO strategies, and early access to new tools.</p>'
    + '<form id="growth-email-form" style="display:flex;gap:8px;max-width:400px;margin:0 auto;flex-wrap:wrap">'
    + '<input id="growth-email-input" type="email" placeholder="you@company.com" required style="flex:1;min-width:180px;padding:10px 14px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#e6edf3;font-size:.88rem;font-family:inherit;outline:none;transition:border-color .2s;" onfocus="this.style.borderColor=\'#00d4ff\'" onblur="this.style.borderColor=\'rgba(255,255,255,0.1)\'">'
    + '<button type="submit" id="growth-email-btn" style="padding:10px 20px;border:none;border-radius:8px;background:#00d4ff;color:#0d1117;font-size:.88rem;font-weight:600;cursor:pointer;white-space:nowrap;font-family:inherit;transition:opacity .2s;" onmouseover="this.style.opacity=\'0.85\'" onmouseout="this.style.opacity=\'1\'">Subscribe</button>'
    + '</form>'
    + '<div id="growth-email-msg" style="margin-top:10px;font-size:.8rem;min-height:18px"></div>'
    + '<p style="color:#484f58;font-size:.68rem;margin:12px 0 0">No spam, ever. Unsubscribe anytime.</p>'
    + '</div>';

  // Read UTM params from URL
  var params = new URLSearchParams(location.search);
  var utmData = {};
  ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'].forEach(function (k) {
    var v = params.get(k);
    if (v) utmData[k] = v;
  });

  // Insert: try before footer, fallback to end of body
  function insert() {
    if (document.getElementById('growth-email-capture')) return;
    var footer = document.querySelector('footer');
    if (footer) {
      footer.parentElement.insertBefore(section, footer);
    } else {
      document.body.appendChild(section);
    }
    wireForm();
  }

  function wireForm() {
    var form = document.getElementById('growth-email-form');
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = document.getElementById('growth-email-btn');
      var msg = document.getElementById('growth-email-msg');
      var inp = document.getElementById('growth-email-input');
      var email = inp.value.trim();
      if (!email) return;
      btn.disabled = true; btn.textContent = 'Subscribing...'; btn.style.opacity = '0.6';
      msg.innerHTML = '';
      var payload = { email: email, source: 'website_main', platform: 'landing_page' };
      for (var k in utmData) payload[k] = utmData[k];
      fetch(API_BASE + '/api/growth/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (res.data.success) {
          msg.innerHTML = '<span style="color:#3fb950">\u2713 You\u2019re in! Check your inbox soon.</span>';
          inp.value = '';
        } else if (res.data.duplicate) {
          msg.innerHTML = '<span style="color:#d29922">You\u2019re already subscribed!</span>';
        } else {
          msg.innerHTML = '<span style="color:#f85149">' + (res.data.error || 'Something went wrong.') + '</span>';
        }
      })
      .catch(function () { msg.innerHTML = '<span style="color:#f85149">Network error. Please try again.</span>'; })
      .finally(function () { btn.disabled = false; btn.textContent = 'Subscribe'; btn.style.opacity = '1'; });
    });
  }

  // Wait for DOM ready, then insert
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', insert);
  } else {
    // Small delay to let React/other scripts render first
    setTimeout(insert, 500);
  }
})();
