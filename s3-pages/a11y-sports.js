/* ═══════════════════════════════════════════════════════════════════════════
   AI1stSEO Sports — WCAG 2.1 AA Accessibility Toolkit
   Shared across all sports & directory pages
   Features: screen reader, keyboard nav, speech, font size, contrast,
             color blind mode, lite mode, RTL, Google Translate, service worker
   ═══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── 1. Skip-to-Content Link ─────────────────────────────────────────────── */
function injectSkipLink(){
  const main = document.querySelector('.content, main, [role="main"], .container, .page, .listing');
  if(!main) return;
  if(!main.id) main.id = 'main-content';
  main.setAttribute('role','main');
  const skip = document.createElement('a');
  skip.href = '#' + main.id;
  skip.className = 'a11y-skip';
  skip.textContent = 'Skip to main content';
  document.body.prepend(skip);
}

/* ── 2. ARIA Landmarks & Roles ───────────────────────────────────────────── */
function addAriaLandmarks(){
  const nav = document.querySelector('nav');
  if(nav){ nav.setAttribute('role','navigation'); nav.setAttribute('aria-label','Main navigation'); }
  const footer = document.querySelector('footer');
  if(footer){ footer.setAttribute('role','contentinfo'); }
  const tabBar = document.querySelector('.tabs');
  if(tabBar){
    tabBar.setAttribute('role','tablist');
    tabBar.setAttribute('aria-label','Content sections');
    tabBar.querySelectorAll('.tab').forEach((t,i) => {
      t.setAttribute('role','tab');
      t.setAttribute('tabindex','0');
      t.setAttribute('aria-selected', t.classList.contains('active') ? 'true' : 'false');
      t.id = t.id || 'tab-btn-' + (t.dataset.tab || i);
      const panel = document.getElementById('tab-' + (t.dataset.tab || ''));
      if(panel){
        panel.setAttribute('role','tabpanel');
        panel.setAttribute('aria-labelledby', t.id);
        t.setAttribute('aria-controls', panel.id);
      }
    });
  }
  const modal = document.getElementById('matchModal');
  if(modal){
    modal.setAttribute('role','dialog');
    modal.setAttribute('aria-modal','true');
    modal.setAttribute('aria-label','Match details');
  }
  const closeBtn = document.querySelector('.modal-close');
  if(closeBtn){
    closeBtn.setAttribute('aria-label','Close match details');
    closeBtn.setAttribute('role','button');
  }
  const bc = document.querySelector('.breadcrumb');
  if(bc){ bc.setAttribute('role','navigation'); bc.setAttribute('aria-label','Breadcrumb'); }
  const matchContainer = document.getElementById('matches-container');
  if(matchContainer){
    matchContainer.setAttribute('aria-live','polite');
    matchContainer.setAttribute('aria-atomic','false');
    matchContainer.setAttribute('aria-label','Match scores and results');
  }
}

/* ── 3. Keyboard Navigation ──────────────────────────────────────────────── */
function enableKeyboardNav(){
  document.addEventListener('keydown', function(e){
    if(e.target.getAttribute('role') === 'tab'){
      const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
      const idx = tabs.indexOf(e.target);
      let next = -1;
      if(e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (idx + 1) % tabs.length;
      if(e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (idx - 1 + tabs.length) % tabs.length;
      if(next >= 0){ e.preventDefault(); tabs[next].focus(); tabs[next].click(); }
      if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); e.target.click(); }
    }
    if(e.target.classList.contains('match-card') && (e.key === 'Enter' || e.key === ' ')){
      e.preventDefault(); e.target.click();
    }
    if(e.target.classList.contains('league-pill') && (e.key === 'Enter' || e.key === ' ')){
      e.preventDefault(); e.target.click();
    }
    if(e.key === 'Escape'){
      const modal = document.getElementById('matchModal');
      if(modal && modal.classList.contains('open')){
        if(typeof closeModal === 'function') closeModal();
      }
      const panel = document.getElementById('a11yPanel');
      if(panel && panel.classList.contains('open')) togglePanel();
    }
  });
  const observer = new MutationObserver(function(){
    document.querySelectorAll('.match-card:not([tabindex])').forEach(c => {
      c.setAttribute('tabindex','0');
      c.setAttribute('role','button');
    });
    document.querySelectorAll('.league-pill:not([tabindex])').forEach(p => {
      p.setAttribute('tabindex','0');
      p.setAttribute('role','button');
    });
    document.querySelectorAll('.explore-card:not([tabindex])').forEach(c => { c.setAttribute('tabindex','0'); });
    document.querySelectorAll('.news-card:not([tabindex])').forEach(c => { c.setAttribute('tabindex','0'); });
    document.querySelectorAll('.match-card:not([aria-label])').forEach(c => {
      const teams = c.querySelector('.match-teams');
      const status = c.querySelector('.match-status');
      const score = c.querySelector('.match-score');
      const league = c.querySelector('.match-league');
      if(teams){
        let label = teams.textContent.replace(/\s+/g,' ').trim();
        if(score) label += ', Score: ' + score.textContent.trim();
        if(status) label += ', Status: ' + status.textContent.trim();
        if(league) label += ', ' + league.textContent.trim();
        label += '. Press Enter to view details.';
        c.setAttribute('aria-label', label);
      }
    });
  });
  observer.observe(document.body, {childList:true, subtree:true});
}

/* ── 4. Listen Button (Web Speech API) ───────────────────────────────────── */
function injectListenButtons(){
  if(!('speechSynthesis' in window)) return;
  const observer = new MutationObserver(function(){
    document.querySelectorAll('.match-card:not([data-a11y-listen])').forEach(c => {
      c.setAttribute('data-a11y-listen','1');
      const btn = document.createElement('button');
      btn.className = 'a11y-listen';
      btn.setAttribute('aria-label','Listen to match details');
      btn.setAttribute('aria-pressed','false');
      btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg> Listen';
      btn.onclick = function(e){
        e.stopPropagation();
        const teams = c.querySelector('.match-teams');
        const score = c.querySelector('.match-score');
        const status = c.querySelector('.match-status');
        const league = c.querySelector('.match-league');
        let text = '';
        if(teams) text += teams.textContent.replace(/\s+/g,' ').trim() + '. ';
        if(score) text += 'Score: ' + score.textContent.trim() + '. ';
        if(status) text += 'Status: ' + status.textContent.trim() + '. ';
        if(league) text += league.textContent.trim() + '.';
        toggleSpeech(text, btn);
      };
      c.appendChild(btn);
    });
    document.querySelectorAll('.news-card:not([data-a11y-listen])').forEach(c => {
      c.setAttribute('data-a11y-listen','1');
      const btn = document.createElement('button');
      btn.className = 'a11y-listen';
      btn.setAttribute('aria-label','Listen to this news item');
      btn.setAttribute('aria-pressed','false');
      btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg> Listen';
      btn.onclick = function(e){
        e.stopPropagation();
        const title = c.querySelector('.news-title');
        const summary = c.querySelector('.news-summary');
        let text = '';
        if(title) text += title.textContent.trim() + '. ';
        if(summary) text += summary.textContent.trim();
        toggleSpeech(text, btn);
      };
      c.appendChild(btn);
    });
    document.querySelectorAll('.tip-card:not([data-a11y-listen]), .prediction-card:not([data-a11y-listen])').forEach(c => {
      c.setAttribute('data-a11y-listen','1');
      // Add plain-English summary for cognitive accessibility
      const pick = c.querySelector('.tip-pick-team');
      const conf = c.querySelector('.confidence-text');
      if(pick && !c.querySelector('.a11y-plain-summary')){
        const summary = document.createElement('div');
        summary.className = 'a11y-plain-summary';
        summary.textContent = 'Simple summary: We think ' + pick.textContent.trim() + ' will win this match' + (conf ? ' (' + conf.textContent.trim() + ')' : '') + '.';
        const pred = c.querySelector('.tip-prediction');
        if(pred) pred.after(summary);
      }
      const btn = document.createElement('button');
      btn.className = 'a11y-listen';
      btn.setAttribute('aria-label','Listen to this prediction');
      btn.setAttribute('aria-pressed','false');
      btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg> Listen';
      btn.onclick = function(e){
        e.stopPropagation();
        toggleSpeech(c.textContent.replace(/\s+/g,' ').trim().substring(0,500), btn);
      };
      c.appendChild(btn);
    });
  });
  observer.observe(document.body, {childList:true, subtree:true});
}

let currentUtterance = null;
function toggleSpeech(text, btn){
  if(speechSynthesis.speaking){
    speechSynthesis.cancel();
    if(btn){ btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg> Listen'; btn.setAttribute('aria-pressed','false'); }
    currentUtterance = null;
    return;
  }
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 0.9;
  utter.onend = function(){ if(btn){ btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg> Listen'; btn.setAttribute('aria-pressed','false'); } currentUtterance = null; };
  utter.onerror = utter.onend;
  if(btn){ btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> Stop'; btn.setAttribute('aria-pressed','true'); }
  currentUtterance = utter;
  speechSynthesis.speak(utter);
}

/* ── 5. Accessibility Panel (floating, organized, impressive) ────────────── */
let panelOpen = false;

function togglePanel(){
  const panel = document.getElementById('a11yPanel');
  if(!panel) return;
  panelOpen = !panelOpen;
  panel.classList.toggle('open', panelOpen);
  const trigger = document.getElementById('a11yTrigger');
  if(trigger) trigger.setAttribute('aria-expanded', panelOpen ? 'true' : 'false');
  if(panelOpen){
    // Focus first option for keyboard users
    setTimeout(function(){ const first = panel.querySelector('.a11y-option'); if(first) first.focus(); }, 100);
  }
}

function injectAccessibilityUI(){
  const nav = document.querySelector('nav');
  if(!nav) return;

  // Trigger button — append to nav-links if it exists, otherwise to nav
  const trigger = document.createElement('button');
  trigger.id = 'a11yTrigger';
  trigger.className = 'a11y-trigger';
  trigger.setAttribute('aria-label','Open accessibility settings');
  trigger.setAttribute('aria-expanded','false');
  trigger.setAttribute('aria-controls','a11yPanel');
  trigger.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="4.5" r="2.5"/><path d="M12 7v5m0 0l-3 7m3-7l3 7"/><path d="M5 10.5h14"/></svg><span>Accessibility</span><div class="a11y-badge"></div>';
  trigger.onclick = togglePanel;
  const navLinks = nav.querySelector('.nav-links');
  if(navLinks) navLinks.appendChild(trigger);
  else nav.appendChild(trigger);

  // Floating panel
  const panel = document.createElement('div');
  panel.id = 'a11yPanel';
  panel.className = 'a11y-panel';
  panel.setAttribute('role','dialog');
  panel.setAttribute('aria-label','Accessibility Settings');
  panel.innerHTML = buildPanelHTML();
  document.body.appendChild(panel);

  // Close on outside click
  document.addEventListener('click', function(e){
    if(panelOpen && !panel.contains(e.target) && !trigger.contains(e.target)){
      togglePanel();
    }
  });

  restorePrefs();
  loadGoogleTranslate();
}

function buildPanelHTML(){
  return '<div class="a11y-panel-header">'
    + '<div class="a11y-panel-title"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="4.5" r="2.5"/><path d="M12 7v5m0 0l-3 7m3-7l3 7" stroke="currentColor" stroke-width="2" fill="none"/><path d="M5 10.5h14" stroke="currentColor" stroke-width="2" fill="none"/></svg> Accessibility</div>'
    + '<button class="a11y-panel-close" onclick="togglePanel()" aria-label="Close accessibility panel">&times;</button>'
    + '</div>'

    // Vision section
    + '<div class="a11y-section">'
    + '<div class="a11y-section-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> Vision</div>'

    + '<div class="a11y-option" id="opt-theme" tabindex="0" onclick="toggleTheme()">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">☀️</div><div class="a11y-option-text"><div class="a11y-option-name">Light Mode</div><div class="a11y-option-desc">Switch to light background for daytime use</div></div></div>'
    + '<button class="a11y-toggle" id="tog-theme" aria-label="Toggle light mode"></button>'
    + '</div>'

    + '<div class="a11y-option" id="opt-fontsize" tabindex="0">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">Aa</div><div class="a11y-option-text"><div class="a11y-option-name">Text Size</div><div class="a11y-option-desc">Increase font size for readability</div></div></div>'
    + '<div class="a11y-font-group"><button class="a11y-font-opt active" data-size="normal" onclick="setFontSize(\'normal\')" aria-label="Normal text size">A</button><button class="a11y-font-opt" data-size="large" onclick="setFontSize(\'large\')" aria-label="Large text size">A+</button><button class="a11y-font-opt" data-size="xlarge" onclick="setFontSize(\'xlarge\')" aria-label="Extra large text size">A++</button></div>'
    + '</div>'

    + '<div class="a11y-option" id="opt-contrast" tabindex="0" onclick="toggleContrast()">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">◐</div><div class="a11y-option-text"><div class="a11y-option-name">High Contrast</div><div class="a11y-option-desc">White text on pure black background</div></div></div>'
    + '<button class="a11y-toggle" id="tog-contrast" aria-label="Toggle high contrast"></button>'
    + '</div>'

    + '<div class="a11y-option" id="opt-colorblind" tabindex="0" onclick="toggleColorBlind()">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">👁</div><div class="a11y-option-text"><div class="a11y-option-name">Color Blind Safe</div><div class="a11y-option-desc">Deuteranopia & protanopia friendly palette</div></div></div>'
    + '<button class="a11y-toggle" id="tog-colorblind" aria-label="Toggle color blind mode"></button>'
    + '</div>'
    + '</div>'

    // Hearing & Speech section
    + '<div class="a11y-section">'
    + '<div class="a11y-section-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg> Hearing & Speech</div>'
    + '<div class="a11y-option" style="cursor:default">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">🔊</div><div class="a11y-option-text"><div class="a11y-option-name">Screen Reader</div><div class="a11y-option-desc">Listen buttons on every card read content aloud</div></div></div>'
    + '<span style="font-size:.72rem;color:rgba(0,255,136,.7);font-weight:600">Active</span>'
    + '</div>'
    + '<div class="a11y-option" style="cursor:default">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">📢</div><div class="a11y-option-text"><div class="a11y-option-name">Visual Alerts</div><div class="a11y-option-desc">Sound alerts replaced with visual banners</div></div></div>'
    + '<span style="font-size:.72rem;color:rgba(0,255,136,.7);font-weight:600">Active</span>'
    + '</div>'
    + '</div>'

    // Navigation section
    + '<div class="a11y-section">'
    + '<div class="a11y-section-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg> Navigation</div>'
    + '<div class="a11y-option" style="cursor:default">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">⌨️</div><div class="a11y-option-text"><div class="a11y-option-name">Keyboard Navigation</div><div class="a11y-option-desc">Tab, arrows, Enter, Escape — full keyboard support</div></div></div>'
    + '<span style="font-size:.72rem;color:rgba(0,255,136,.7);font-weight:600">Active</span>'
    + '</div>'
    + '<div class="a11y-option" style="cursor:default">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">⏭️</div><div class="a11y-option-text"><div class="a11y-option-name">Skip to Content</div><div class="a11y-option-desc">Press Tab on page load to skip navigation</div></div></div>'
    + '<span style="font-size:.72rem;color:rgba(0,255,136,.7);font-weight:600">Active</span>'
    + '</div>'
    + '</div>'

    // Performance section
    + '<div class="a11y-section">'
    + '<div class="a11y-section-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Performance</div>'
    + '<div class="a11y-option" id="opt-lite" tabindex="0" onclick="toggleLite()">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">⚡</div><div class="a11y-option-text"><div class="a11y-option-name">Lite Mode</div><div class="a11y-option-desc">Text only — strips images & animations for 2G/3G</div></div></div>'
    + '<button class="a11y-toggle" id="tog-lite" aria-label="Toggle lite mode"></button>'
    + '</div>'
    + '<div class="a11y-option" style="cursor:default">'
    + '<div class="a11y-option-left"><div class="a11y-option-icon">📶</div><div class="a11y-option-text"><div class="a11y-option-name">Offline Mode</div><div class="a11y-option-desc">Last viewed scores cached for no-connection access</div></div></div>'
    + '<span style="font-size:.72rem;color:rgba(0,255,136,.7);font-weight:600">Active</span>'
    + '</div>'
    + '</div>'

    // Language section
    + '<div class="a11y-section">'
    + '<div class="a11y-section-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg> Language — 130+ Languages</div>'
    + '<div class="a11y-translate-wrap" id="google_translate_element"></div>'
    + '</div>'

    // Footer
    + '<div class="a11y-panel-footer">'
    + '<p>AI1stSEO is committed to making sports accessible for everyone worldwide. Built to WCAG 2.1 AA standards.<br><a href="https://www.w3.org/WAI/WCAG21/quickref/" target="_blank" rel="noopener">Learn about WCAG 2.1</a></p>'
    + '</div>';
}

// Expose togglePanel globally for the close button
window.togglePanel = togglePanel;

/* ── 6. Theme (Light/Dark) ────────────────────────────────────────────────── */
window.toggleTheme = function(){
  const html = document.documentElement;
  const on = html.getAttribute('data-theme') === 'light';
  html.setAttribute('data-theme', on ? '' : 'light');
  localStorage.setItem('a11y_theme', on ? '' : 'light');
  const tog = document.getElementById('tog-theme');
  if(tog) tog.classList.toggle('on', !on);
  const opt = document.getElementById('opt-theme');
  if(opt) opt.classList.toggle('active', !on);
  // Update icon
  const icon = opt ? opt.querySelector('.a11y-option-icon') : null;
  if(icon) icon.textContent = on ? '☀️' : '🌙';
  const name = opt ? opt.querySelector('.a11y-option-name') : null;
  if(name) name.textContent = on ? 'Light Mode' : 'Dark Mode';
  updateTriggerBadge();
};

/* ── 7. Font Size ────────────────────────────────────────────────────────── */
const FONT_SIZES = ['normal','large','xlarge'];
window.setFontSize = function(size){
  document.documentElement.setAttribute('data-fontsize', size);
  localStorage.setItem('a11y_fontsize', size);
  document.querySelectorAll('.a11y-font-opt').forEach(b => b.classList.toggle('active', b.dataset.size === size));
  updateTriggerBadge();
};

/* ── 8. High Contrast ────────────────────────────────────────────────────── */
window.toggleContrast = function(){
  const html = document.documentElement;
  const on = html.getAttribute('data-contrast') === 'high';
  html.setAttribute('data-contrast', on ? '' : 'high');
  localStorage.setItem('a11y_contrast', on ? '' : 'high');
  const tog = document.getElementById('tog-contrast');
  if(tog) tog.classList.toggle('on', !on);
  const opt = document.getElementById('opt-contrast');
  if(opt) opt.classList.toggle('active', !on);
  updateTriggerBadge();
};

/* ── 8. Color Blind Mode ─────────────────────────────────────────────────── */
window.toggleColorBlind = function(){
  const html = document.documentElement;
  const on = html.getAttribute('data-colorblind') === 'on';
  html.setAttribute('data-colorblind', on ? '' : 'on');
  localStorage.setItem('a11y_colorblind', on ? '' : 'on');
  const tog = document.getElementById('tog-colorblind');
  if(tog) tog.classList.toggle('on', !on);
  const opt = document.getElementById('opt-colorblind');
  if(opt) opt.classList.toggle('active', !on);
  updateTriggerBadge();
};

/* ── 9. Lite Mode ────────────────────────────────────────────────────────── */
window.toggleLite = function(){
  const html = document.documentElement;
  const on = html.getAttribute('data-lite') === 'on';
  html.setAttribute('data-lite', on ? '' : 'on');
  localStorage.setItem('a11y_lite', on ? '' : 'on');
  const tog = document.getElementById('tog-lite');
  if(tog) tog.classList.toggle('on', !on);
  const opt = document.getElementById('opt-lite');
  if(opt) opt.classList.toggle('active', !on);
  updateTriggerBadge();
};

/* ── 10. Update trigger badge (green dot when settings active) ───────────── */
function updateTriggerBadge(){
  const trigger = document.getElementById('a11yTrigger');
  if(!trigger) return;
  const hasActive = (localStorage.getItem('a11y_fontsize') && localStorage.getItem('a11y_fontsize') !== 'normal')
    || localStorage.getItem('a11y_contrast') === 'high'
    || localStorage.getItem('a11y_colorblind') === 'on'
    || localStorage.getItem('a11y_lite') === 'on'
    || localStorage.getItem('a11y_theme') === 'light';
  trigger.classList.toggle('has-active', hasActive);
}

/* ── 11. Restore Preferences ─────────────────────────────────────────────── */
function restorePrefs(){
  const html = document.documentElement;
  // Theme
  const th = localStorage.getItem('a11y_theme');
  if(th === 'light'){
    html.setAttribute('data-theme','light');
    const tog = document.getElementById('tog-theme'); if(tog) tog.classList.add('on');
    const opt = document.getElementById('opt-theme'); if(opt){ opt.classList.add('active'); const icon = opt.querySelector('.a11y-option-icon'); if(icon) icon.textContent = '🌙'; const name = opt.querySelector('.a11y-option-name'); if(name) name.textContent = 'Dark Mode'; }
  }
  const fs = localStorage.getItem('a11y_fontsize');
  if(fs && fs !== 'normal'){
    html.setAttribute('data-fontsize', fs);
    document.querySelectorAll('.a11y-font-opt').forEach(b => b.classList.toggle('active', b.dataset.size === fs));
  }
  const ct = localStorage.getItem('a11y_contrast');
  if(ct === 'high'){
    html.setAttribute('data-contrast','high');
    const tog = document.getElementById('tog-contrast'); if(tog) tog.classList.add('on');
    const opt = document.getElementById('opt-contrast'); if(opt) opt.classList.add('active');
  }
  const cb = localStorage.getItem('a11y_colorblind');
  if(cb === 'on'){
    html.setAttribute('data-colorblind','on');
    const tog = document.getElementById('tog-colorblind'); if(tog) tog.classList.add('on');
    const opt = document.getElementById('opt-colorblind'); if(opt) opt.classList.add('active');
  }
  const lt = localStorage.getItem('a11y_lite');
  if(lt === 'on'){
    html.setAttribute('data-lite','on');
    const tog = document.getElementById('tog-lite'); if(tog) tog.classList.add('on');
    const opt = document.getElementById('opt-lite'); if(opt) opt.classList.add('active');
  }
  updateTriggerBadge();
}

/* ── 12. Google Translate ────────────────────────────────────────────────── */
function loadGoogleTranslate(){
  window.googleTranslateElementInit = function(){
    new google.translate.TranslateElement({pageLanguage:'en',layout:google.translate.TranslateElement.InlineLayout.SIMPLE,autoDisplay:false},'google_translate_element');
  };
  const s = document.createElement('script');
  s.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
  s.async = true;
  document.head.appendChild(s);
}

/* ── 13. Lazy Load Images ────────────────────────────────────────────────── */
function enableLazyLoad(){
  const observer = new MutationObserver(function(){
    document.querySelectorAll('img:not([loading])').forEach(img => {
      img.setAttribute('loading','lazy');
      if(!img.alt) img.alt = 'Sports image';
    });
  });
  observer.observe(document.body, {childList:true, subtree:true});
  document.querySelectorAll('img:not([loading])').forEach(img => {
    img.setAttribute('loading','lazy');
    if(!img.alt) img.alt = 'Sports image';
  });
}

/* ── 14. Visual Alert Banner (deaf users) ────────────────────────────────── */
function showVisualAlert(message){
  let banner = document.getElementById('a11y-alert-banner');
  if(!banner){
    banner = document.createElement('div');
    banner.id = 'a11y-alert-banner';
    banner.className = 'a11y-alert-banner';
    banner.setAttribute('role','alert');
    banner.setAttribute('aria-live','assertive');
    document.body.prepend(banner);
  }
  banner.textContent = message;
  banner.classList.add('show');
  setTimeout(function(){ banner.classList.remove('show'); }, 5000);
}
window.showVisualAlert = showVisualAlert;

/* ── 15. Service Worker Registration (offline mode) ──────────────────────── */
function registerServiceWorker(){
  if('serviceWorker' in navigator){
    navigator.serviceWorker.register('/sw-sports.js').catch(function(){});
  }
}

/* ── 16. Add status text labels alongside colors ─────────────────────────── */
function addStatusTextLabels(){
  const observer = new MutationObserver(function(){
    document.querySelectorAll('.match-status:not([data-a11y-labeled])').forEach(s => {
      s.setAttribute('data-a11y-labeled','1');
      const text = s.textContent.trim();
      if(text === '● LIVE' && !s.querySelector('.sr-only')){
        s.innerHTML = '<span aria-hidden="true">●</span> LIVE <span class="sr-only">(match in progress)</span>';
      }
      if(text === 'Final' && !s.querySelector('.sr-only')){
        s.innerHTML = 'Final <span class="sr-only">(match completed)</span>';
      }
    });
  });
  observer.observe(document.body, {childList:true, subtree:true});
}

/* ── 17. RTL Detection ───────────────────────────────────────────────────── */
function detectRTL(){
  const lang = document.documentElement.lang || navigator.language || '';
  const rtlLangs = ['ar','he','fa','ur','ps','sd','yi'];
  const langCode = lang.split('-')[0].toLowerCase();
  if(rtlLangs.includes(langCode)){
    document.documentElement.setAttribute('dir','rtl');
  }
  const observer = new MutationObserver(function(){
    const htmlLang = document.documentElement.lang || '';
    const code = htmlLang.split('-')[0].toLowerCase();
    if(rtlLangs.includes(code)){
      document.documentElement.setAttribute('dir','rtl');
    } else {
      document.documentElement.removeAttribute('dir');
    }
  });
  observer.observe(document.documentElement, {attributes:true, attributeFilter:['lang','class']});
}

/* ── INIT ────────────────────────────────────────────────────────────────── */
function initA11y(){
  injectSkipLink();
  addAriaLandmarks();
  enableKeyboardNav();
  injectListenButtons();
  injectAccessibilityUI();
  enableLazyLoad();
  addStatusTextLabels();
  detectRTL();
  registerServiceWorker();
}

if(document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', initA11y);
} else {
  initA11y();
}

})();
