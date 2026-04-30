/* ═══════════════════════════════════════════════════════════════════════════
   AI1stSEO Sports — WCAG 2.1 AA Accessibility Toolkit
   Shared across: directory-sport.html, directory-sports.html, cricket-tips.html
   Features: screen reader, keyboard nav, speech, font size, contrast,
             color blind mode, lite mode, RTL, Google Translate, service worker
   ═══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

// ── 1. Skip-to-Content Link ─────────────────────────────────────────────────
function injectSkipLink(){
  const main = document.querySelector('.content, main, [role="main"]');
  if(!main) return;
  if(!main.id) main.id = 'main-content';
  main.setAttribute('role','main');
  const skip = document.createElement('a');
  skip.href = '#' + main.id;
  skip.className = 'a11y-skip';
  skip.textContent = 'Skip to main content';
  document.body.prepend(skip);
}

// ── 2. ARIA Landmarks & Roles ────────────────────────────────────────────────
function addAriaLandmarks(){
  const nav = document.querySelector('nav');
  if(nav){ nav.setAttribute('role','navigation'); nav.setAttribute('aria-label','Main navigation'); }
  const footer = document.querySelector('footer');
  if(footer){ footer.setAttribute('role','contentinfo'); }
  // Tabs
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
  // Modal
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
  // Breadcrumb
  const bc = document.querySelector('.breadcrumb');
  if(bc){ bc.setAttribute('role','navigation'); bc.setAttribute('aria-label','Breadcrumb'); }
  // Live region for score updates
  const matchContainer = document.getElementById('matches-container');
  if(matchContainer){
    matchContainer.setAttribute('aria-live','polite');
    matchContainer.setAttribute('aria-atomic','false');
    matchContainer.setAttribute('aria-label','Match scores and results');
  }
}

// ── 3. Keyboard Navigation ───────────────────────────────────────────────────
function enableKeyboardNav(){
  // Make tabs keyboard navigable
  document.addEventListener('keydown', function(e){
    // Tab switching with arrow keys
    if(e.target.getAttribute('role') === 'tab'){
      const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
      const idx = tabs.indexOf(e.target);
      let next = -1;
      if(e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (idx + 1) % tabs.length;
      if(e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (idx - 1 + tabs.length) % tabs.length;
      if(next >= 0){ e.preventDefault(); tabs[next].focus(); tabs[next].click(); }
      if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); e.target.click(); }
    }
    // Match cards — Enter to open
    if(e.target.classList.contains('match-card') && (e.key === 'Enter' || e.key === ' ')){
      e.preventDefault(); e.target.click();
    }
    // League pills
    if(e.target.classList.contains('league-pill') && (e.key === 'Enter' || e.key === ' ')){
      e.preventDefault(); e.target.click();
    }
    // Escape closes modal
    if(e.key === 'Escape'){
      const modal = document.getElementById('matchModal');
      if(modal && modal.classList.contains('open')){
        if(typeof closeModal === 'function') closeModal();
      }
    }
  });
  // Make match cards focusable
  const observer = new MutationObserver(function(){
    document.querySelectorAll('.match-card:not([tabindex])').forEach(c => {
      c.setAttribute('tabindex','0');
      c.setAttribute('role','button');
    });
    document.querySelectorAll('.league-pill:not([tabindex])').forEach(p => {
      p.setAttribute('tabindex','0');
      p.setAttribute('role','button');
    });
    document.querySelectorAll('.explore-card:not([tabindex])').forEach(c => {
      c.setAttribute('tabindex','0');
    });
    document.querySelectorAll('.news-card:not([tabindex])').forEach(c => {
      c.setAttribute('tabindex','0');
    });
    // Add aria-labels to match cards
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

// ── 4. Listen Button (Web Speech API) ────────────────────────────────────────

function injectListenButtons(){
  if(!('speechSynthesis' in window)) return;
  const observer = new MutationObserver(function(){
    // Match cards
    document.querySelectorAll('.match-card:not([data-a11y-listen])').forEach(c => {
      c.setAttribute('data-a11y-listen','1');
      const btn = document.createElement('button');
      btn.className = 'a11y-listen';
      btn.setAttribute('aria-label','Listen to match details');
      btn.setAttribute('aria-pressed','false');
      btn.innerHTML = '🔊 Listen';
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
    // News cards
    document.querySelectorAll('.news-card:not([data-a11y-listen])').forEach(c => {
      c.setAttribute('data-a11y-listen','1');
      const btn = document.createElement('button');
      btn.className = 'a11y-listen';
      btn.setAttribute('aria-label','Listen to this news item');
      btn.setAttribute('aria-pressed','false');
      btn.innerHTML = '🔊 Listen';
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
    // Tips cards (cricket-tips page)
    document.querySelectorAll('.tip-card:not([data-a11y-listen]), .prediction-card:not([data-a11y-listen])').forEach(c => {
      c.setAttribute('data-a11y-listen','1');
      const btn = document.createElement('button');
      btn.className = 'a11y-listen';
      btn.setAttribute('aria-label','Listen to this prediction');
      btn.setAttribute('aria-pressed','false');
      btn.innerHTML = '🔊 Listen';
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
    if(btn){ btn.innerHTML = '🔊 Listen'; btn.setAttribute('aria-pressed','false'); }
    currentUtterance = null;
    return;
  }
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 0.9;
  utter.onend = function(){ if(btn){ btn.innerHTML = '🔊 Listen'; btn.setAttribute('aria-pressed','false'); } currentUtterance = null; };
  utter.onerror = utter.onend;
  if(btn){ btn.innerHTML = '🔇 Stop'; btn.setAttribute('aria-pressed','true'); }
  currentUtterance = utter;
  speechSynthesis.speak(utter);
}

// ── 5. Accessibility Toolbar (font size, contrast, color blind, lite, translate) ─
function injectToolbar(){
  const nav = document.querySelector('nav');
  if(!nav) return;
  const toolbar = document.createElement('div');
  toolbar.className = 'a11y-toolbar';
  toolbar.setAttribute('role','toolbar');
  toolbar.setAttribute('aria-label','Accessibility settings');

  // Font size toggle
  const fontBtn = mkBtn('A+','Font size','a11y-font-btn');
  fontBtn.onclick = function(){ cycleFontSize(); };
  toolbar.appendChild(fontBtn);

  // High contrast
  const contrastBtn = mkBtn('◐','High contrast','a11y-contrast-btn');
  contrastBtn.onclick = function(){ toggleContrast(contrastBtn); };
  toolbar.appendChild(contrastBtn);

  // Color blind mode
  const cbBtn = mkBtn('👁','Color blind','a11y-cb-btn');
  cbBtn.onclick = function(){ toggleColorBlind(cbBtn); };
  toolbar.appendChild(cbBtn);

  // Lite mode
  const liteBtn = mkBtn('⚡','Lite mode','a11y-lite-btn');
  liteBtn.onclick = function(){ toggleLite(liteBtn); };
  toolbar.appendChild(liteBtn);

  // Google Translate
  const translateDiv = document.createElement('div');
  translateDiv.id = 'google_translate_element';
  toolbar.appendChild(translateDiv);

  nav.appendChild(toolbar);

  // Restore saved preferences
  restorePrefs();
  // Load Google Translate
  loadGoogleTranslate();
}

function mkBtn(icon, label, id){
  const b = document.createElement('button');
  b.className = 'a11y-btn';
  b.id = id;
  b.setAttribute('aria-label', label);
  b.setAttribute('title', label);
  b.textContent = icon;
  return b;
}

// ── 6. Font Size ─────────────────────────────────────────────────────────────
const FONT_SIZES = ['normal','large','xlarge'];
function cycleFontSize(){
  const html = document.documentElement;
  const current = html.getAttribute('data-fontsize') || 'normal';
  const idx = FONT_SIZES.indexOf(current);
  const next = FONT_SIZES[(idx + 1) % FONT_SIZES.length];
  html.setAttribute('data-fontsize', next);
  localStorage.setItem('a11y_fontsize', next);
  const btn = document.getElementById('a11y-font-btn');
  if(btn) btn.textContent = next === 'normal' ? 'A' : next === 'large' ? 'A+' : 'A++';
}

// ── 7. High Contrast ─────────────────────────────────────────────────────────
function toggleContrast(btn){
  const html = document.documentElement;
  const on = html.getAttribute('data-contrast') === 'high';
  html.setAttribute('data-contrast', on ? '' : 'high');
  localStorage.setItem('a11y_contrast', on ? '' : 'high');
  if(btn) btn.classList.toggle('active', !on);
}

// ── 8. Color Blind Mode ──────────────────────────────────────────────────────
function toggleColorBlind(btn){
  const html = document.documentElement;
  const on = html.getAttribute('data-colorblind') === 'on';
  html.setAttribute('data-colorblind', on ? '' : 'on');
  localStorage.setItem('a11y_colorblind', on ? '' : 'on');
  if(btn) btn.classList.toggle('active', !on);
}

// ── 9. Lite Mode ─────────────────────────────────────────────────────────────
function toggleLite(btn){
  const html = document.documentElement;
  const on = html.getAttribute('data-lite') === 'on';
  html.setAttribute('data-lite', on ? '' : 'on');
  localStorage.setItem('a11y_lite', on ? '' : 'on');
  if(btn) btn.classList.toggle('active', !on);
}

// ── 10. Restore Preferences ──────────────────────────────────────────────────
function restorePrefs(){
  const html = document.documentElement;
  const fs = localStorage.getItem('a11y_fontsize');
  if(fs && fs !== 'normal'){ html.setAttribute('data-fontsize', fs); const b = document.getElementById('a11y-font-btn'); if(b) b.textContent = fs === 'large' ? 'A+' : 'A++'; }
  const ct = localStorage.getItem('a11y_contrast');
  if(ct === 'high'){ html.setAttribute('data-contrast','high'); const b = document.getElementById('a11y-contrast-btn'); if(b) b.classList.add('active'); }
  const cb = localStorage.getItem('a11y_colorblind');
  if(cb === 'on'){ html.setAttribute('data-colorblind','on'); const b = document.getElementById('a11y-cb-btn'); if(b) b.classList.add('active'); }
  const lt = localStorage.getItem('a11y_lite');
  if(lt === 'on'){ html.setAttribute('data-lite','on'); const b = document.getElementById('a11y-lite-btn'); if(b) b.classList.add('active'); }
}

// ── 11. Google Translate ─────────────────────────────────────────────────────
function loadGoogleTranslate(){
  window.googleTranslateElementInit = function(){
    new google.translate.TranslateElement({pageLanguage:'en',layout:google.translate.TranslateElement.InlineLayout.SIMPLE,autoDisplay:false},'google_translate_element');
  };
  const s = document.createElement('script');
  s.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
  s.async = true;
  document.head.appendChild(s);
}

// ── 12. Lazy Load Images ─────────────────────────────────────────────────────
function enableLazyLoad(){
  const observer = new MutationObserver(function(){
    document.querySelectorAll('img:not([loading])').forEach(img => {
      img.setAttribute('loading','lazy');
      if(!img.alt) img.alt = 'Sports image';
    });
  });
  observer.observe(document.body, {childList:true, subtree:true});
  // Initial pass
  document.querySelectorAll('img:not([loading])').forEach(img => {
    img.setAttribute('loading','lazy');
    if(!img.alt) img.alt = 'Sports image';
  });
}

// ── 13. Visual Alert Banner (deaf users) ─────────────────────────────────────
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

// ── 14. Service Worker Registration (offline mode) ───────────────────────────
function registerServiceWorker(){
  if('serviceWorker' in navigator){
    navigator.serviceWorker.register('/sw-sports.js').catch(function(){});
  }
}

// ── 15. Add status text labels alongside colors ──────────────────────────────
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

// ── 16. RTL Detection ────────────────────────────────────────────────────────
function detectRTL(){
  const lang = document.documentElement.lang || navigator.language || '';
  const rtlLangs = ['ar','he','fa','ur','ps','sd','yi'];
  const langCode = lang.split('-')[0].toLowerCase();
  if(rtlLangs.includes(langCode)){
    document.documentElement.setAttribute('dir','rtl');
  }
  // Also check Google Translate changes
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

// ── INIT ─────────────────────────────────────────────────────────────────────
function initA11y(){
  injectSkipLink();
  addAriaLandmarks();
  enableKeyboardNav();
  injectListenButtons();
  injectToolbar();
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
