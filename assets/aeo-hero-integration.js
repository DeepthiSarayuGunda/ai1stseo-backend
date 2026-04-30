/**
 * AEO Rank Tracker — Homepage Hero Integration
 *
 * Hooks into the existing hero URL input to run an AEO scan
 * and display results inline below the hero section.
 *
 * Strategy: MutationObserver watches for React to render the hero
 * input, then attaches the AEO scan behavior. If the hero input
 * can't be found after 15s, injects a standalone AEO section.
 */
(function () {
  'use strict';

  var DEBUG = true; // flip to false in production
  var injected = false;
  var API_BASE =
    location.hostname === 'localhost' || location.hostname === '127.0.0.1'
      ? ''
      : 'https://sgnmqxb2sw.us-east-1.awsapprunner.com';

  function log() {
    if (DEBUG) console.log.apply(console, ['[AEO]'].concat(Array.prototype.slice.call(arguments)));
  }

  log('Script loaded');

  // ── Helpers ──────────────────────────────────────────────────────────── //

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function extractBrand(domain) {
    var d = domain.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
    return d.split('.')[0] || d;
  }

  function cleanDomain(input) {
    var d = input.trim().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
    return d.toLowerCase();
  }

  // ── Find the hero input using multiple strategies ────────────────────── //

  function findHeroInput() {
    // Strategy 1: placeholder attribute (MUI renders this on the inner input)
    var el = document.querySelector('input[placeholder*="website URL"]');
    if (el) { log('Found via placeholder*="website URL"'); return el; }

    el = document.querySelector('input[placeholder*="website"]');
    if (el) { log('Found via placeholder*="website"'); return el; }

    // Strategy 2: Look for input inside #root that's in a form
    var forms = document.querySelectorAll('#root form');
    for (var i = 0; i < forms.length; i++) {
      var inp = forms[i].querySelector('input[type="text"], input[type="url"], input:not([type])');
      if (inp) { log('Found via #root form input'); return inp; }
    }

    // Strategy 3: MUI TextField — look for input inside a div with MUI classes
    var muiInputs = document.querySelectorAll('.MuiInputBase-input, .MuiOutlinedInput-input, .MuiInput-input');
    for (var j = 0; j < muiInputs.length; j++) {
      var parent = muiInputs[j].closest('form');
      if (parent) {
        var btn = parent.querySelector('button[type="submit"]');
        if (btn) { log('Found via MUI class + form + submit button'); return muiInputs[j]; }
      }
    }

    // Strategy 4: Any text input near a button containing "Analyze" or "Analysis"
    var buttons = document.querySelectorAll('button');
    for (var k = 0; k < buttons.length; k++) {
      var txt = (buttons[k].textContent || '').toLowerCase();
      if (txt.indexOf('analy') !== -1 || txt.indexOf('free') !== -1) {
        var container = buttons[k].closest('form') || buttons[k].parentElement;
        if (container) {
          var nearInput = container.querySelector('input');
          if (nearInput) { log('Found via button text "' + txt.trim() + '" + nearby input'); return nearInput; }
        }
      }
    }

    return null;
  }

  // ── Create the results container ─────────────────────────────────────── //

  function createResultsContainer() {
    var div = document.createElement('div');
    div.id = 'aeo-hero-results';
    div.style.cssText =
      'display:none;width:100%;max-width:900px;margin:0 auto;padding:32px 20px 40px;' +
      'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;';
    return div;
  }

  // ── Create standalone AEO section (fallback) ─────────────────────────── //

  function injectStandalone() {
    if (document.getElementById('aeo-standalone-section')) return;
    log('Injecting standalone AEO section (hero input not found)');

    var root = document.getElementById('root');
    if (!root) return;

    var section = document.createElement('div');
    section.id = 'aeo-standalone-section';
    section.style.cssText =
      'width:100%;padding:40px 20px;text-align:center;' +
      'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;' +
      'border-top:1px solid rgba(255,255,255,0.06);';

    section.innerHTML =
      '<div style="max-width:600px;margin:0 auto;">' +
      '<p style="color:#00d4ff;font-size:.7rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;margin:0 0 10px">AI Visibility Check</p>' +
      '<h3 style="color:#e6edf3;font-size:1.25rem;font-weight:600;margin:0 0 8px;line-height:1.3">See How AI Models Cite Your Brand</h3>' +
      '<p style="color:#8b949e;font-size:.85rem;margin:0 0 20px;line-height:1.5">Enter your domain to scan across ChatGPT, Gemini, Claude, and Perplexity.</p>' +
      '<form id="aeo-standalone-form" style="display:flex;gap:8px;max-width:500px;margin:0 auto;flex-wrap:wrap;">' +
      '<input id="aeo-standalone-input" type="text" placeholder="yourdomain.com" ' +
      'style="flex:1;min-width:200px;padding:12px 16px;background:rgba(255,255,255,0.05);' +
      'border:1px solid rgba(255,255,255,0.12);border-radius:10px;color:#e6edf3;font-size:.92rem;' +
      'font-family:inherit;outline:none;transition:border-color .2s;" ' +
      'onfocus="this.style.borderColor=\'#00d4ff\'" onblur="this.style.borderColor=\'rgba(255,255,255,0.12)\'">' +
      '<button type="submit" id="aeo-standalone-btn" ' +
      'style="padding:12px 28px;border:none;border-radius:10px;cursor:pointer;font-size:.92rem;font-weight:600;' +
      'font-family:inherit;background:linear-gradient(90deg,#00d4ff,#7b2cbf);color:#fff;' +
      'transition:opacity .2s;white-space:nowrap;" ' +
      'onmouseover="this.style.opacity=\'0.85\'" onmouseout="this.style.opacity=\'1\'">AEO Scan</button>' +
      '</form>' +
      '</div>';

    var resultsDiv = createResultsContainer();

    // Insert after the first major child of root, or append
    if (root.children.length > 0) {
      // Try to find a good insertion point — after stats row or first section
      var inserted = false;
      var allDivs = root.querySelectorAll('div');
      for (var i = 0; i < allDivs.length; i++) {
        var el = allDivs[i];
        if (el.children.length >= 4 && el.offsetHeight > 30 && el.offsetHeight < 200) {
          // Likely a stats/feature row
          el.parentElement.insertBefore(section, el.nextSibling);
          el.parentElement.insertBefore(resultsDiv, section.nextSibling);
          inserted = true;
          break;
        }
      }
      if (!inserted) {
        root.appendChild(section);
        root.appendChild(resultsDiv);
      }
    } else {
      root.appendChild(section);
      root.appendChild(resultsDiv);
    }

    // Wire up form
    document.getElementById('aeo-standalone-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var input = document.getElementById('aeo-standalone-input');
      var domain = cleanDomain(input.value);
      if (!domain || domain.length < 3) return;
      var btn = document.getElementById('aeo-standalone-btn');
      btn.disabled = true;
      btn.textContent = 'Scanning\u2026';
      btn.style.opacity = '0.5';
      runAeoScan(domain, resultsDiv, function () {
        btn.disabled = false;
        btn.textContent = 'AEO Scan';
        btn.style.opacity = '1';
      });
    });
  }

  // ── Main injection (hooks into hero input) ───────────────────────────── //

  function tryInject() {
    if (injected) return;

    var heroInput = findHeroInput();
    if (!heroInput) return;

    var form = heroInput.closest('form');
    if (!form) {
      log('Input found but no parent form — skipping');
      return;
    }

    var btn = form.querySelector('button[type="submit"], button');
    if (!btn) {
      log('Input found but no submit button — skipping');
      return;
    }

    injected = true;
    log('Hero input found, attaching AEO scan');

    // Create results container
    var resultsDiv = createResultsContainer();

    // Insert after the hero section
    var heroSection = form;
    for (var i = 0; i < 15; i++) {
      if (!heroSection.parentElement || heroSection.parentElement.id === 'root') break;
      heroSection = heroSection.parentElement;
    }
    if (heroSection.nextSibling) {
      heroSection.parentElement.insertBefore(resultsDiv, heroSection.nextSibling);
    } else {
      heroSection.parentElement.appendChild(resultsDiv);
    }

    // Add AEO badge next to button
    try {
      var badge = document.createElement('span');
      badge.style.cssText =
        'display:inline-block;margin-left:8px;padding:2px 8px;border-radius:12px;' +
        'font-size:0.65rem;font-weight:600;background:rgba(0,212,255,0.15);' +
        'color:#00d4ff;border:1px solid rgba(0,212,255,0.25);vertical-align:middle;';
      badge.textContent = '+ AEO';
      btn.parentElement.appendChild(badge);
    } catch (e) { log('Badge injection skipped:', e); }

    // Intercept form submit — run AEO in parallel with existing SEO analysis
    form.addEventListener('submit', function () {
      var rawUrl = heroInput.value.trim();
      if (!rawUrl) return;
      var domain = cleanDomain(rawUrl);
      if (!domain || domain.length < 3) return;
      log('Form submitted, running AEO scan for:', domain);
      runAeoScan(domain, resultsDiv);
    }, true);
  }

  // ── AEO scan logic (shared by hero hook and standalone) ──────────────── //

  function runAeoScan(domain, resultsDiv, onComplete) {
    var brand = extractBrand(domain);

    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML =
      '<div style="text-align:center;padding:30px 0;">' +
      '<div class="aeo-spinner"></div>' +
      '<p style="color:rgba(255,255,255,0.5);font-size:0.9rem;">Scanning AI models for <strong style="color:#00d4ff;">' + esc(domain) + '</strong>\u2026</p>' +
      '</div>' +
      '<style>.aeo-spinner{width:36px;height:36px;margin:0 auto 12px;border:3px solid rgba(255,255,255,0.15);' +
      'border-top-color:#00d4ff;border-radius:50%;animation:aeo-spin 0.8s linear infinite}' +
      '@keyframes aeo-spin{to{transform:rotate(360deg)}}</style>';

    setTimeout(function () {
      resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 200);

    var queries = [
      'best ' + brand + ' alternatives',
      'top tools like ' + domain,
      'is ' + domain + ' recommended'
    ];

    fetch(API_BASE + '/api/aeo-tracker/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand_name: brand, target_domain: domain, queries: queries })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.status !== 'ok') throw new Error(data.error || 'Scan failed');
        renderResults(data, domain, resultsDiv);
      })
      .catch(function (err) {
        log('Scan error:', err);
        resultsDiv.innerHTML =
          '<div style="text-align:center;padding:30px 0;">' +
          '<p style="color:#ff8a80;font-size:0.95rem;">\u26a0 ' + esc(err.message || 'Analysis failed. Please try again.') + '</p>' +
          '</div>';
      })
      .finally(function () {
        if (onComplete) onComplete();
      });
  }

  // ── Render results ───────────────────────────────────────────────────── //

  function renderResults(data, domain, container) {
    var s = data.summary || {};
    var results = data.results || [];
    var vis = s.visibility_score || 0;
    var isMock = (s.active_llms || []).indexOf('mock') !== -1;
    var visColor = vis >= 50 ? '#00e676' : vis > 0 ? '#ffab00' : '#ff5252';

    var html = '';

    // Header
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

    // Metrics
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
      html += '<div style="text-align:center;margin-bottom:20px;opacity:0;animation:aeo-fade 0.5s ease 0.25s forwards;">';
      for (var i = 0; i < active.length; i++) {
        var isM = active[i] === 'mock';
        html +=
          '<span style="display:inline-block;margin:0 4px;padding:3px 10px;border-radius:14px;font-size:0.72rem;font-weight:500;' +
          (isM ? 'background:rgba(255,171,0,0.1);color:#ffab00;border:1px solid rgba(255,171,0,0.2);'
               : 'background:rgba(0,230,118,0.1);color:#00e676;border:1px solid rgba(0,230,118,0.2);') +
          '">' + esc(active[i]) + '</span>';
      }
      html += '</div>';
    }

    // Results table
    html +=
      '<div style="overflow-x:auto;opacity:0;animation:aeo-fade 0.5s ease 0.35s forwards;">' +
      '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">' +
      '<thead><tr>' +
      thCell('Query') + thCell('LLM') + thCell('Cited') +
      '</tr></thead><tbody>';
    for (var j = 0; j < results.length; j++) {
      var r = results[j];
      var badge = r.citation_found
        ? '<span style="display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.72rem;background:rgba(0,230,118,0.12);color:#00e676;border:1px solid rgba(0,230,118,0.25);">Yes</span>'
        : '<span style="display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.72rem;background:rgba(255,82,82,0.1);color:#ff5252;border:1px solid rgba(255,82,82,0.2);">No</span>';
      html +=
        '<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">' +
        '<td style="padding:10px 12px;color:rgba(255,255,255,0.8);">' + esc(r.query) + '</td>' +
        '<td style="padding:10px 12px;"><span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:0.72rem;background:rgba(123,44,191,0.12);color:#ce93d8;border:1px solid rgba(123,44,191,0.2);">' + esc(r.llm) + '</span></td>' +
        '<td style="padding:10px 12px;text-align:center;">' + badge + '</td></tr>';
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
      '<p style="color:#8b949e;font-size:0.75rem;margin-top:10px;">Run custom queries on the full AEO Rank Tracker</p></div>';

    container.innerHTML = html;
  }

  function metricCard(value, label, color) {
    return '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:18px;text-align:center;">' +
      '<div style="font-size:1.6rem;font-weight:700;color:' + color + ';margin-bottom:2px;">' + esc(String(value)) + '</div>' +
      '<div style="font-size:0.75rem;color:rgba(255,255,255,0.5);">' + esc(label) + '</div></div>';
  }

  function thCell(text) {
    return '<th style="text-align:left;padding:8px 12px;color:rgba(255,255,255,0.45);font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid rgba(255,255,255,0.08);">' + text + '</th>';
  }

  // ── Observer + fallback ──────────────────────────────────────────────── //

  var attempts = 0;
  var maxAttempts = 40; // 40 * 400ms = 16 seconds

  var obs = new MutationObserver(function () {
    tryInject();
    if (injected) { obs.disconnect(); clearInterval(iv); }
  });
  obs.observe(document.body, { childList: true, subtree: true });

  var iv = setInterval(function () {
    attempts++;
    tryInject();
    if (injected) {
      clearInterval(iv);
      obs.disconnect();
      log('Injection complete after', attempts, 'attempts');
    } else if (attempts >= maxAttempts) {
      clearInterval(iv);
      obs.disconnect();
      log('Hero input not found after', attempts, 'attempts — using standalone fallback');
      injectStandalone();
    }
  }, 400);
})();
