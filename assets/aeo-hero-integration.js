/**
 * AEO Rank Tracker — Homepage Hero Integration
 *
 * Hooks into the existing hero URL input to run an AEO scan
 * and display results inline below the hero section.
 * Follows the same MutationObserver injection pattern as
 * growth-email-capture.js and the GEO Scanner card.
 */
(function () {
  'use strict';

  var injected = false;
  var API_BASE =
    location.hostname === 'localhost' || location.hostname === '127.0.0.1'
      ? ''
      : 'https://sgnmqxb2sw.us-east-1.awsapprunner.com';

  // ── Helpers ──────────────────────────────────────────────────────────── //

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function extractBrand(domain) {
    // "ai1stseo.com" → "ai1stseo"
    var d = domain.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
    return d.split('.')[0] || d;
  }

  function cleanDomain(input) {
    var d = input.trim().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
    return d.toLowerCase();
  }

  // ── Inject ───────────────────────────────────────────────────────────── //

  function tryInject() {
    if (injected) return;

    // Find the hero input by placeholder
    var inputs = document.querySelectorAll('input[placeholder*="website URL"]');
    if (!inputs.length) return;
    var heroInput = inputs[0];

    // Walk up to find the form element
    var form = heroInput.closest('form');
    if (!form) return;

    // Find the submit button inside the form
    var btn = form.querySelector('button[type="submit"]');
    if (!btn) return;

    // Walk up to find the hero section container
    var heroSection = form;
    for (var i = 0; i < 12; i++) {
      if (!heroSection.parentElement) break;
      heroSection = heroSection.parentElement;
      // Look for a container that's wide enough to be the hero
      if (heroSection.offsetWidth > 600 && heroSection.offsetHeight > 200) break;
    }

    injected = true;

    // ── Create results container (hidden initially) ──────────────────── //

    var resultsDiv = document.createElement('div');
    resultsDiv.id = 'aeo-hero-results';
    resultsDiv.style.cssText =
      'display:none;width:100%;max-width:900px;margin:0 auto;padding:32px 20px 40px;' +
      'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;';

    // Insert after the hero section
    if (heroSection.nextSibling) {
      heroSection.parentElement.insertBefore(resultsDiv, heroSection.nextSibling);
    } else {
      heroSection.parentElement.appendChild(resultsDiv);
    }

    // ── Intercept form submit ────────────────────────────────────────── //

    var originalText = btn.textContent || btn.innerText;

    form.addEventListener(
      'submit',
      function (e) {
        var rawUrl = heroInput.value.trim();
        if (!rawUrl) return; // let original handler deal with empty

        var domain = cleanDomain(rawUrl);
        if (!domain || domain.length < 3) return; // too short, skip

        // Don't block the original SEO analysis — run AEO in parallel
        runAeoScan(domain, btn);
      },
      true
    );

    // Also add a small AEO badge next to the button
    var aeoBadge = document.createElement('span');
    aeoBadge.style.cssText =
      'display:inline-block;margin-left:8px;padding:2px 8px;border-radius:12px;' +
      'font-size:0.65rem;font-weight:600;background:rgba(0,212,255,0.15);' +
      'color:#00d4ff;border:1px solid rgba(0,212,255,0.25);vertical-align:middle;';
    aeoBadge.textContent = '+ AEO Scan';
    btn.parentElement.appendChild(aeoBadge);

    // ── Run AEO scan ─────────────────────────────────────────────────── //

    function runAeoScan(domain, btn) {
      var brand = extractBrand(domain);
      resultsDiv.style.display = 'block';
      resultsDiv.innerHTML =
        '<div style="text-align:center;padding:30px 0;">' +
        '<div style="width:36px;height:36px;margin:0 auto 12px;border:3px solid rgba(255,255,255,0.15);' +
        'border-top-color:#00d4ff;border-radius:50%;animation:aeo-spin 0.8s linear infinite;"></div>' +
        '<p style="color:rgba(255,255,255,0.5);font-size:0.9rem;">Running AEO scan across AI models\u2026</p>' +
        '</div>' +
        '<style>@keyframes aeo-spin{to{transform:rotate(360deg)}}</style>';

      // Smooth scroll to results
      setTimeout(function () {
        resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 300);

      var queries = [
        'best ' + brand + ' alternatives',
        'top tools like ' + domain,
        'is ' + domain + ' recommended',
      ];

      fetch(API_BASE + '/api/aeo-tracker/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brand_name: brand,
          target_domain: domain,
          queries: queries,
        }),
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data.status !== 'ok') throw new Error(data.error || 'Scan failed');
          renderResults(data, domain, brand);
        })
        .catch(function (err) {
          resultsDiv.innerHTML =
            '<div style="text-align:center;padding:30px 0;">' +
            '<p style="color:#ff8a80;font-size:0.95rem;">\u26a0 ' +
            esc(err.message || 'Analysis failed. Please try again.') +
            '</p></div>';
        });
    }

    // ── Render results ───────────────────────────────────────────────── //

    function renderResults(data, domain, brand) {
      var s = data.summary || {};
      var results = data.results || [];
      var vis = s.visibility_score || 0;
      var isMock = (s.active_llms || []).indexOf('mock') !== -1;

      var visColor = vis >= 50 ? '#00e676' : vis > 0 ? '#ffab00' : '#ff5252';

      var html = '';

      // Section header
      html +=
        '<div style="text-align:center;margin-bottom:24px;opacity:0;animation:aeo-fade 0.5s ease forwards;">' +
        '<style>@keyframes aeo-fade{to{opacity:1}}</style>' +
        '<h2 style="font-size:1.3rem;font-weight:700;color:#e6edf3;margin:0 0 6px;">' +
        'AEO Visibility Report for <span style="color:#00d4ff;">' + esc(domain) + '</span></h2>' +
        '<p style="color:#8b949e;font-size:0.85rem;margin:0;">How AI models cite your brand</p>';

      if (isMock) {
        html +=
          '<span style="display:inline-block;margin-top:8px;padding:3px 12px;border-radius:16px;' +
          'font-size:0.72rem;font-weight:600;background:rgba(255,171,0,0.12);color:#ffab00;' +
          'border:1px solid rgba(255,171,0,0.25);">Demo Mode</span>';
      }
      html += '</div>';

      // Metric cards
      html +=
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px;' +
        'opacity:0;animation:aeo-fade 0.5s ease 0.15s forwards;">';

      html += metricCard(vis + '%', 'Visibility Score', visColor);
      html += metricCard(s.total_scanned || 0, 'Scanned', '#e6edf3');
      html += metricCard(s.total_cited || 0, 'Citations', '#00e676');
      html += metricCard(s.best_llm || '\u2014', 'Best LLM', '#ce93d8');
      html += '</div>';

      // Active LLMs
      var active = s.active_llms || [];
      if (active.length) {
        html +=
          '<div style="text-align:center;margin-bottom:20px;opacity:0;animation:aeo-fade 0.5s ease 0.25s forwards;">';
        for (var i = 0; i < active.length; i++) {
          var isM = active[i] === 'mock';
          html +=
            '<span style="display:inline-block;margin:0 4px;padding:3px 10px;border-radius:14px;' +
            'font-size:0.72rem;font-weight:500;' +
            (isM
              ? 'background:rgba(255,171,0,0.1);color:#ffab00;border:1px solid rgba(255,171,0,0.2);'
              : 'background:rgba(0,230,118,0.1);color:#00e676;border:1px solid rgba(0,230,118,0.2);') +
            '">' +
            esc(active[i]) +
            '</span>';
        }
        html += '</div>';
      }

      // Results table
      html +=
        '<div style="overflow-x:auto;opacity:0;animation:aeo-fade 0.5s ease 0.35s forwards;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">' +
        '<thead><tr>' +
        '<th style="text-align:left;padding:8px 12px;color:rgba(255,255,255,0.45);font-size:0.75rem;' +
        'font-weight:600;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid rgba(255,255,255,0.08);">Query</th>' +
        '<th style="text-align:left;padding:8px 12px;color:rgba(255,255,255,0.45);font-size:0.75rem;' +
        'font-weight:600;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid rgba(255,255,255,0.08);">LLM</th>' +
        '<th style="text-align:center;padding:8px 12px;color:rgba(255,255,255,0.45);font-size:0.75rem;' +
        'font-weight:600;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid rgba(255,255,255,0.08);">Cited</th>' +
        '</tr></thead><tbody>';

      for (var j = 0; j < results.length; j++) {
        var r = results[j];
        var cited = r.citation_found;
        var badge = cited
          ? '<span style="display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.72rem;' +
            'background:rgba(0,230,118,0.12);color:#00e676;border:1px solid rgba(0,230,118,0.25);">Yes</span>'
          : '<span style="display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.72rem;' +
            'background:rgba(255,82,82,0.1);color:#ff5252;border:1px solid rgba(255,82,82,0.2);">No</span>';

        html +=
          '<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">' +
          '<td style="padding:10px 12px;color:rgba(255,255,255,0.8);">' + esc(r.query) + '</td>' +
          '<td style="padding:10px 12px;"><span style="display:inline-block;padding:2px 8px;border-radius:10px;' +
          'font-size:0.72rem;background:rgba(123,44,191,0.12);color:#ce93d8;border:1px solid rgba(123,44,191,0.2);">' +
          esc(r.llm) + '</span></td>' +
          '<td style="padding:10px 12px;text-align:center;">' + badge + '</td>' +
          '</tr>';
      }

      html += '</tbody></table></div>';

      // CTA
      html +=
        '<div style="text-align:center;margin-top:28px;opacity:0;animation:aeo-fade 0.5s ease 0.45s forwards;">' +
        '<a href="/aeo-tracker" style="display:inline-block;padding:12px 32px;border-radius:10px;' +
        'background:linear-gradient(90deg,#00d4ff,#7b2cbf);color:#fff;text-decoration:none;' +
        'font-size:0.95rem;font-weight:600;transition:opacity 0.2s;" ' +
        'onmouseover="this.style.opacity=\'0.85\'" onmouseout="this.style.opacity=\'1\'">' +
        'View Full Report \u2192</a>' +
        '<p style="color:#8b949e;font-size:0.75rem;margin-top:10px;">Run custom queries on the full AEO Rank Tracker</p>' +
        '</div>';

      resultsDiv.innerHTML = html;
    }

    function metricCard(value, label, color) {
      return (
        '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);' +
        'border-radius:12px;padding:18px;text-align:center;">' +
        '<div style="font-size:1.6rem;font-weight:700;color:' + color + ';margin-bottom:2px;">' +
        esc(String(value)) + '</div>' +
        '<div style="font-size:0.75rem;color:rgba(255,255,255,0.5);">' + esc(label) + '</div>' +
        '</div>'
      );
    }
  }

  // ── Observer (same pattern as GEO Scanner card injection) ──────────── //

  var obs = new MutationObserver(tryInject);
  obs.observe(document.body, { childList: true, subtree: true });
  var iv = setInterval(function () {
    tryInject();
    if (injected) {
      clearInterval(iv);
      obs.disconnect();
    }
  }, 400);
  setTimeout(function () {
    obs.disconnect();
    clearInterval(iv);
  }, 30000);
})();
