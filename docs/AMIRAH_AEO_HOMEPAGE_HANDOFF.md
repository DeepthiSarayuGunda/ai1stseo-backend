# AEO Rank Tracker — Homepage Integration (For Amirah)

## What's needed

Add an "AI Visibility Check" section to the live homepage. It has its own input, button, and results area. No detection or hooking into existing elements — it's a self-contained block.

## Where to place it

In the live homepage HTML, paste the snippet below **after the hero section** (after the "236 Checks / 4 AI Models / Instant PDF / AEO + GEO + SEO" stats row, before the "Everything You Need" features grid).

## Backend (already live)

The API is deployed and working at:
```
https://sgnmqxb2sw.us-east-1.awsapprunner.com/api/aeo-tracker/run
```

The full tracker page is also live at:
```
https://sgnmqxb2sw.us-east-1.awsapprunner.com/aeo-tracker
```

## HTML snippet to paste

Copy everything between the `<!-- AEO START -->` and `<!-- AEO END -->` comments:

```html
<!-- AEO START -->
<section id="aeo-section" style="width:100%;padding:48px 20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;border-top:1px solid rgba(255,255,255,0.06);background:linear-gradient(180deg,rgba(15,52,96,0.3) 0%,transparent 100%);">
  <div style="max-width:700px;margin:0 auto;text-align:center;">
    <p style="color:#00d4ff;font-size:.7rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;margin:0 0 10px;">AI Visibility Check</p>
    <h2 style="color:#e6edf3;font-size:1.4rem;font-weight:700;margin:0 0 8px;line-height:1.3;">See How AI Models Cite Your Brand</h2>
    <p style="color:#8b949e;font-size:.88rem;margin:0 0 24px;line-height:1.5;">Enter your domain to scan across ChatGPT, Gemini, Claude, and Perplexity.</p>
    <form id="aeo-scan-form" style="display:flex;gap:10px;max-width:520px;margin:0 auto;flex-wrap:wrap;">
      <input id="aeo-scan-input" type="text" placeholder="yourdomain.com" required
        style="flex:1;min-width:200px;padding:12px 16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.12);border-radius:10px;color:#e6edf3;font-size:.95rem;font-family:inherit;outline:none;transition:border-color .2s;"
        onfocus="this.style.borderColor='#00d4ff'" onblur="this.style.borderColor='rgba(255,255,255,0.12)'">
      <button type="submit" id="aeo-scan-btn"
        style="padding:12px 28px;border:none;border-radius:10px;cursor:pointer;font-size:.95rem;font-weight:600;font-family:inherit;background:linear-gradient(90deg,#00d4ff,#7b2cbf);color:#fff;transition:opacity .2s;white-space:nowrap;"
        onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">Run AEO Scan</button>
    </form>
    <p style="color:#484f58;font-size:.7rem;margin:12px 0 0;">Free scan. No signup required.</p>
  </div>
  <div id="aeo-scan-results" style="max-width:900px;margin:28px auto 0;display:none;"></div>
</section>

<script>
(function() {
  var API = 'https://sgnmqxb2sw.us-east-1.awsapprunner.com';
  function esc(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

  document.getElementById('aeo-scan-form').addEventListener('submit', function(e) {
    e.preventDefault();
    var raw = document.getElementById('aeo-scan-input').value.trim();
    if (!raw) return;
    var domain = raw.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0].toLowerCase();
    if (domain.length < 3) return;
    var brand = domain.split('.')[0];
    var btn = document.getElementById('aeo-scan-btn');
    var box = document.getElementById('aeo-scan-results');

    btn.disabled = true; btn.textContent = 'Scanning\u2026'; btn.style.opacity = '0.5';
    box.style.display = 'block';
    box.innerHTML =
      '<div style="text-align:center;padding:24px 0;">' +
      '<div style="width:36px;height:36px;margin:0 auto 12px;border:3px solid rgba(255,255,255,0.15);border-top-color:#00d4ff;border-radius:50%;animation:aeospin .8s linear infinite"></div>' +
      '<p style="color:rgba(255,255,255,0.5);font-size:.9rem;">Scanning AI models for <strong style="color:#00d4ff;">' + esc(domain) + '</strong>\u2026</p>' +
      '</div><style>@keyframes aeospin{to{transform:rotate(360deg)}}</style>';
    box.scrollIntoView({ behavior: 'smooth', block: 'start' });

    fetch(API + '/api/aeo-tracker/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand_name: brand, target_domain: domain, queries: [
        'best ' + brand + ' alternatives',
        'top tools like ' + domain,
        'is ' + domain + ' recommended'
      ]})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.status !== 'ok') throw new Error(data.error || 'Scan failed');
      var s = data.summary || {}, res = data.results || [];
      var vis = s.visibility_score || 0;
      var isMock = (s.active_llms || []).indexOf('mock') !== -1;
      var vc = vis >= 50 ? '#00e676' : vis > 0 ? '#ffab00' : '#ff5252';
      var h = '';

      h += '<div style="text-align:center;margin-bottom:20px;">';
      h += '<h3 style="font-size:1.15rem;font-weight:700;color:#e6edf3;margin:0 0 4px;">AEO Report: <span style="color:#00d4ff;">' + esc(domain) + '</span></h3>';
      if (isMock) h += '<span style="display:inline-block;margin-top:6px;padding:3px 12px;border-radius:14px;font-size:.72rem;font-weight:600;background:rgba(255,171,0,0.12);color:#ffab00;border:1px solid rgba(255,171,0,0.25);">Demo Mode</span>';
      h += '</div>';

      h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:20px;">';
      h += mc(vis + '%', 'Visibility', vc);
      h += mc(s.total_scanned || 0, 'Scanned', '#e6edf3');
      h += mc(s.total_cited || 0, 'Citations', '#00e676');
      h += mc(s.best_llm || '\u2014', 'Best LLM', '#ce93d8');
      h += '</div>';

      var al = s.active_llms || [];
      if (al.length) {
        h += '<div style="text-align:center;margin-bottom:16px;">';
        for (var i = 0; i < al.length; i++) {
          var m = al[i] === 'mock';
          h += '<span style="display:inline-block;margin:0 3px;padding:2px 9px;border-radius:12px;font-size:.72rem;' +
            (m ? 'background:rgba(255,171,0,0.1);color:#ffab00;border:1px solid rgba(255,171,0,0.2);'
               : 'background:rgba(0,230,118,0.1);color:#00e676;border:1px solid rgba(0,230,118,0.2);') +
            '">' + esc(al[i]) + '</span>';
        }
        h += '</div>';
      }

      h += '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:.85rem;">';
      h += '<thead><tr>' + th('Query') + th('LLM') + th('Cited') + '</tr></thead><tbody>';
      for (var j = 0; j < res.length; j++) {
        var r = res[j], cited = r.citation_found;
        var bg = cited
          ? '<span style="padding:2px 8px;border-radius:12px;font-size:.72rem;background:rgba(0,230,118,0.12);color:#00e676;border:1px solid rgba(0,230,118,0.25);">Yes</span>'
          : '<span style="padding:2px 8px;border-radius:12px;font-size:.72rem;background:rgba(255,82,82,0.1);color:#ff5252;border:1px solid rgba(255,82,82,0.2);">No</span>';
        h += '<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">';
        h += '<td style="padding:9px 12px;color:rgba(255,255,255,0.8);">' + esc(r.query) + '</td>';
        h += '<td style="padding:9px 12px;"><span style="padding:2px 8px;border-radius:10px;font-size:.72rem;background:rgba(123,44,191,0.12);color:#ce93d8;border:1px solid rgba(123,44,191,0.2);">' + esc(r.llm) + '</span></td>';
        h += '<td style="padding:9px 12px;text-align:center;">' + bg + '</td></tr>';
      }
      h += '</tbody></table></div>';

      h += '<div style="text-align:center;margin-top:24px;">';
      h += '<a href="/aeo-tracker" style="display:inline-block;padding:11px 30px;border-radius:10px;background:linear-gradient(90deg,#00d4ff,#7b2cbf);color:#fff;text-decoration:none;font-size:.92rem;font-weight:600;transition:opacity .2s;" onmouseover="this.style.opacity=\'0.85\'" onmouseout="this.style.opacity=\'1\'">View Full Report \u2192</a>';
      h += '<p style="color:#8b949e;font-size:.73rem;margin-top:8px;">Run custom queries on the full AEO Rank Tracker</p></div>';

      box.innerHTML = h;
    })
    .catch(function(err) {
      box.innerHTML = '<div style="text-align:center;padding:24px 0;"><p style="color:#ff8a80;font-size:.95rem;">\u26a0 ' + esc(err.message || 'Analysis failed. Please try again.') + '</p></div>';
    })
    .finally(function() {
      btn.disabled = false; btn.textContent = 'Run AEO Scan'; btn.style.opacity = '1';
    });
  });

  function mc(val, label, color) {
    return '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px;text-align:center;">' +
      '<div style="font-size:1.5rem;font-weight:700;color:' + color + ';margin-bottom:2px;">' + esc(String(val)) + '</div>' +
      '<div style="font-size:.73rem;color:rgba(255,255,255,0.5);">' + esc(label) + '</div></div>';
  }
  function th(t) {
    return '<th style="text-align:left;padding:8px 12px;color:rgba(255,255,255,0.4);font-size:.73rem;font-weight:600;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid rgba(255,255,255,0.08);">' + t + '</th>';
  }
})();
</script>
<!-- AEO END -->
```

## Placement in the live homepage

Looking at the current live homepage structure, paste it here:

```
... 📊 236 Checks / 🤖 4 AI Models / 📄 Instant PDF / 🌐 AEO + GEO + SEO ...

<!-- PASTE AEO SNIPPET HERE -->

... Everything You Need for AI Visibility ...
```

## What it does

- Shows a heading, input field (placeholder: "yourdomain.com"), and "Run AEO Scan" button
- On submit: calls the backend API, shows a spinner, then renders results
- Results include: visibility score, citations found, best LLM, per-query table
- "View Full Report" button links to `/aeo-tracker` for the full dashboard
- If backend is in mock mode (no API keys), shows a "Demo Mode" badge
- If API fails, shows an error message and re-enables the button
- Matches the existing dark theme (same colors, fonts, border-radius)

## No dependencies

- No external JS files needed
- No MutationObserver or detection logic
- Self-contained HTML + inline JS
- Works immediately on page load

## API reference

Full API docs are in `docs/AEO_RANK_TRACKER_API.md` in the repo.

Quick summary:
- `POST /api/aeo-tracker/run` — run a scan
- `GET /api/aeo-tracker/providers` — check which LLMs are active
- `GET /api/aeo-tracker/history` — past results
- `GET /api/aeo-tracker/summary` — aggregated stats
