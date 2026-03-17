/**
 * ai1stseo.com Authentication Module
 * Connects to Cognito via backend /api/auth/* endpoints
 * Injects login/signup modal and manages session state
 */
(function() {
  'use strict';

  // API base — auto-detect environment
  var API = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:5000' : 'http://api.ai1stseo.com';

  // Session keys
  var SK = {
    ACCESS: 'ai1stseo_access_token',
    ID: 'ai1stseo_id_token',
    REFRESH: 'ai1stseo_refresh_token',
    USER: 'ai1stseo_user'
  };

  // ---- Session helpers ----
  function saveSession(data) {
    localStorage.setItem(SK.ACCESS, data.accessToken);
    localStorage.setItem(SK.ID, data.idToken);
    localStorage.setItem(SK.REFRESH, data.refreshToken);
    localStorage.setItem(SK.USER, JSON.stringify(data.user));
  }

  function getUser() {
    try { return JSON.parse(localStorage.getItem(SK.USER)); } catch(e) { return null; }
  }

  function getAccessToken() { return localStorage.getItem(SK.ACCESS); }

  function clearSession() {
    Object.values(SK).forEach(function(k) { localStorage.removeItem(k); });
  }

  function isLoggedIn() { return !!getAccessToken(); }

  // Expose for other scripts
  window.AI1STSEO_AUTH = {
    getUser: getUser,
    getAccessToken: getAccessToken,
    isLoggedIn: isLoggedIn,
    clearSession: clearSession
  };

  // ---- API calls ----
  function apiCall(endpoint, body, cb) {
    var opts = { method: 'POST', headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    fetch(API + endpoint, opts)
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(res) { cb(null, res.data, res.ok); })
      .catch(function(err) { cb(err.message || 'Network error'); });
  }

  // ---- Styles ----
  function injectStyles() {
    if (document.getElementById('auth-modal-styles')) return;
    var style = document.createElement('style');
    style.id = 'auth-modal-styles';
    style.textContent = [
      '.auth-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.7);z-index:99999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);opacity:0;transition:opacity .2s}',
      '.auth-overlay.visible{opacity:1}',
      '.auth-modal{background:linear-gradient(135deg,#0a0e1a 0%,#111827 100%);border:1px solid rgba(0,255,136,.25);border-radius:16px;padding:32px;width:400px;max-width:92vw;color:#fff;box-shadow:0 20px 60px rgba(0,0,0,.6);transform:translateY(20px);transition:transform .2s}',
      '.auth-overlay.visible .auth-modal{transform:translateY(0)}',
      '.auth-modal h2{margin:0 0 6px;font-size:1.5rem;background:linear-gradient(90deg,#00ff88,#00d4ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}',
      '.auth-modal .subtitle{color:#94a3b8;font-size:.85rem;margin-bottom:20px}',
      '.auth-modal label{display:block;color:#94a3b8;font-size:.8rem;margin-bottom:4px;margin-top:14px}',
      '.auth-modal input{width:100%;padding:10px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:.95rem;outline:none;box-sizing:border-box;transition:border-color .2s}',
      '.auth-modal input:focus{border-color:#00ff88}',
      '.auth-modal .auth-btn{width:100%;padding:12px;margin-top:20px;background:linear-gradient(135deg,#00ff88,#00d4ff);color:#000;font-weight:700;font-size:.95rem;border:none;border-radius:8px;cursor:pointer;transition:opacity .2s}',
      '.auth-modal .auth-btn:hover{opacity:.85}',
      '.auth-modal .auth-btn:disabled{opacity:.5;cursor:not-allowed}',
      '.auth-modal .auth-link{color:#00d4ff;background:none;border:none;cursor:pointer;font-size:.85rem;padding:0;text-decoration:underline}',
      '.auth-modal .auth-link:hover{color:#00ff88}',
      '.auth-modal .auth-footer{text-align:center;margin-top:16px;color:#64748b;font-size:.85rem}',
      '.auth-modal .auth-error{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:#fca5a5;padding:8px 12px;border-radius:6px;font-size:.85rem;margin-top:12px;display:none}',
      '.auth-modal .auth-success{background:rgba(0,255,136,.1);border:1px solid rgba(0,255,136,.3);color:#00ff88;padding:8px 12px;border-radius:6px;font-size:.85rem;margin-top:12px;display:none}',
      '.auth-modal .close-btn{position:absolute;top:12px;right:16px;background:none;border:none;color:#64748b;font-size:1.4rem;cursor:pointer;padding:4px}',
      '.auth-modal .close-btn:hover{color:#fff}',
      '.auth-user-menu{position:relative;display:inline-flex;align-items:center;gap:8px}',
      '.auth-user-btn{background:rgba(0,255,136,.12);border:1px solid rgba(0,255,136,.3);color:#00ff88;padding:6px 14px;border-radius:20px;cursor:pointer;font-size:.85rem;display:flex;align-items:center;gap:6px;transition:background .2s}',
      '.auth-user-btn:hover{background:rgba(0,255,136,.2)}',
      '.auth-user-dd{display:none;position:absolute;top:calc(100% + 6px);right:0;background:rgba(20,25,40,.98);border:1px solid rgba(0,212,255,.3);border-radius:8px;min-width:180px;padding:6px 0;z-index:10001;box-shadow:0 8px 24px rgba(0,0,0,.4)}',
      '.auth-user-dd a,.auth-user-dd button{display:block;width:100%;padding:10px 16px;color:#fff;text-decoration:none;font-size:.85rem;background:none;border:none;text-align:left;cursor:pointer;transition:background .2s;box-sizing:border-box}',
      '.auth-user-dd a:hover,.auth-user-dd button:hover{background:rgba(0,212,255,.1)}',
      '.auth-user-dd .danger{color:#f87171}',
      '.auth-user-dd .danger:hover{background:rgba(239,68,68,.1)}'
    ].join('\n');
    document.head.appendChild(style);
  }

  // ---- Modal HTML ----
  function createOverlay() {
    var el = document.createElement('div');
    el.className = 'auth-overlay';
    el.id = 'auth-overlay';
    el.innerHTML = '<div class="auth-modal" style="position:relative" id="auth-modal-inner"></div>';
    el.addEventListener('click', function(e) { if (e.target === el) closeModal(); });
    document.body.appendChild(el);
    return el;
  }

  function showModal(view) {
    injectStyles();
    var overlay = document.getElementById('auth-overlay') || createOverlay();
    var inner = document.getElementById('auth-modal-inner');
    overlay.style.display = 'flex';
    requestAnimationFrame(function() { overlay.classList.add('visible'); });

    if (view === 'login') renderLogin(inner);
    else if (view === 'signup') renderSignup(inner);
    else if (view === 'verify') renderVerify(inner);
    else if (view === 'forgot') renderForgot(inner);
    else if (view === 'reset') renderReset(inner);
    else if (view === 'profile') renderProfile(inner);
  }

  function closeModal() {
    var overlay = document.getElementById('auth-overlay');
    if (!overlay) return;
    overlay.classList.remove('visible');
    setTimeout(function() { overlay.style.display = 'none'; }, 200);
  }

  function setError(msg) {
    var el = document.getElementById('auth-error');
    if (!el) return;
    el.textContent = msg;
    el.style.display = msg ? 'block' : 'none';
    var s = document.getElementById('auth-success');
    if (s) s.style.display = 'none';
  }

  function setSuccess(msg) {
    var el = document.getElementById('auth-success');
    if (!el) return;
    el.textContent = msg;
    el.style.display = msg ? 'block' : 'none';
    var e = document.getElementById('auth-error');
    if (e) e.style.display = 'none';
  }

  function closeBtn() { return '<button class="close-btn" onclick="document.getElementById(\'auth-overlay\').classList.remove(\'visible\');setTimeout(function(){document.getElementById(\'auth-overlay\').style.display=\'none\'},200)">&times;</button>'; }

  // ---- Login View ----
  function renderLogin(c) {
    c.innerHTML = closeBtn() +
      '<h2>Welcome Back</h2>' +
      '<p class="subtitle">Sign in to your AI1stSEO account</p>' +
      '<label for="auth-email">Email</label>' +
      '<input type="email" id="auth-email" placeholder="you@example.com" autocomplete="email">' +
      '<label for="auth-pass">Password</label>' +
      '<input type="password" id="auth-pass" placeholder="Your password" autocomplete="current-password">' +
      '<button class="auth-btn" id="auth-submit">Sign In</button>' +
      '<div class="auth-error" id="auth-error"></div>' +
      '<div class="auth-success" id="auth-success"></div>' +
      '<div class="auth-footer">' +
        '<button class="auth-link" id="auth-to-forgot">Forgot password?</button>' +
        ' &middot; ' +
        'No account? <button class="auth-link" id="auth-to-signup">Sign up</button>' +
      '</div>';

    document.getElementById('auth-to-signup').onclick = function() { showModal('signup'); };
    document.getElementById('auth-to-forgot').onclick = function() { showModal('forgot'); };
    document.getElementById('auth-submit').onclick = doLogin;
    document.getElementById('auth-pass').addEventListener('keydown', function(e) { if (e.key === 'Enter') doLogin(); });
  }

  function doLogin() {
    var email = document.getElementById('auth-email').value.trim();
    var pass = document.getElementById('auth-pass').value;
    if (!email || !pass) return setError('Please enter email and password.');
    var btn = document.getElementById('auth-submit');
    btn.disabled = true; btn.textContent = 'Signing in...';
    setError('');

    apiCall('/api/auth/login', { email: email, password: pass }, function(err, data, ok) {
      btn.disabled = false; btn.textContent = 'Sign In';
      if (err) return setError(err);
      if (!ok) return setError(data.error || 'Login failed');
      saveSession(data);
      closeModal();
      updateNavForUser();
    });
  }

  // ---- Signup View ----
  function renderSignup(c) {
    c.innerHTML = closeBtn() +
      '<h2>Create Account</h2>' +
      '<p class="subtitle">Join AI1stSEO and start optimizing</p>' +
      '<label for="auth-name">Name (optional)</label>' +
      '<input type="text" id="auth-name" placeholder="Your name" autocomplete="name">' +
      '<label for="auth-email">Email</label>' +
      '<input type="email" id="auth-email" placeholder="you@example.com" autocomplete="email">' +
      '<label for="auth-pass">Password</label>' +
      '<input type="password" id="auth-pass" placeholder="Min 8 chars, uppercase, lowercase, number" autocomplete="new-password">' +
      '<button class="auth-btn" id="auth-submit">Create Account</button>' +
      '<div class="auth-error" id="auth-error"></div>' +
      '<div class="auth-success" id="auth-success"></div>' +
      '<div class="auth-footer">' +
        'Already have an account? <button class="auth-link" id="auth-to-login">Sign in</button>' +
      '</div>';

    document.getElementById('auth-to-login').onclick = function() { showModal('login'); };
    document.getElementById('auth-submit').onclick = doSignup;
    document.getElementById('auth-pass').addEventListener('keydown', function(e) { if (e.key === 'Enter') doSignup(); });
  }

  function doSignup() {
    var name = document.getElementById('auth-name').value.trim();
    var email = document.getElementById('auth-email').value.trim();
    var pass = document.getElementById('auth-pass').value;
    if (!email || !pass) return setError('Email and password are required.');
    var btn = document.getElementById('auth-submit');
    btn.disabled = true; btn.textContent = 'Creating account...';
    setError('');

    apiCall('/api/auth/signup', { email: email, password: pass, name: name }, function(err, data, ok) {
      btn.disabled = false; btn.textContent = 'Create Account';
      if (err) return setError(err);
      if (!ok) return setError(data.error || 'Signup failed');
      // Store email for verify screen
      window._authVerifyEmail = email;
      setSuccess('Account created! Check your email for a verification code.');
      setTimeout(function() { showModal('verify'); }, 1500);
    });
  }

  // ---- Verify Email View ----
  function renderVerify(c) {
    var em = window._authVerifyEmail || '';
    c.innerHTML = closeBtn() +
      '<h2>Verify Email</h2>' +
      '<p class="subtitle">Enter the 6-digit code sent to your email</p>' +
      '<label for="auth-email">Email</label>' +
      '<input type="email" id="auth-email" value="' + em + '" placeholder="you@example.com">' +
      '<label for="auth-code">Verification Code</label>' +
      '<input type="text" id="auth-code" placeholder="123456" maxlength="6" autocomplete="one-time-code">' +
      '<button class="auth-btn" id="auth-submit">Verify</button>' +
      '<div class="auth-error" id="auth-error"></div>' +
      '<div class="auth-success" id="auth-success"></div>' +
      '<div class="auth-footer">' +
        '<button class="auth-link" id="auth-resend">Resend code</button>' +
        ' &middot; ' +
        '<button class="auth-link" id="auth-to-login">Back to sign in</button>' +
      '</div>';

    document.getElementById('auth-to-login').onclick = function() { showModal('login'); };
    document.getElementById('auth-resend').onclick = function() {
      var email = document.getElementById('auth-email').value.trim();
      if (!email) return setError('Enter your email first.');
      apiCall('/api/auth/resend-code', { email: email }, function(err, data, ok) {
        if (!ok) return setError((data && data.error) || 'Failed to resend');
        setSuccess('Code resent! Check your email.');
      });
    };
    document.getElementById('auth-submit').onclick = doVerify;
    document.getElementById('auth-code').addEventListener('keydown', function(e) { if (e.key === 'Enter') doVerify(); });
  }

  function doVerify() {
    var email = document.getElementById('auth-email').value.trim();
    var code = document.getElementById('auth-code').value.trim();
    if (!email || !code) return setError('Email and code are required.');
    var btn = document.getElementById('auth-submit');
    btn.disabled = true; btn.textContent = 'Verifying...';
    setError('');

    apiCall('/api/auth/verify', { email: email, code: code }, function(err, data, ok) {
      btn.disabled = false; btn.textContent = 'Verify';
      if (err) return setError(err);
      if (!ok) return setError(data.error || 'Verification failed');
      setSuccess('Email verified! Redirecting to login...');
      setTimeout(function() { showModal('login'); }, 1500);
    });
  }

  // ---- Forgot Password View ----
  function renderForgot(c) {
    c.innerHTML = closeBtn() +
      '<h2>Reset Password</h2>' +
      '<p class="subtitle">We\'ll send a reset code to your email</p>' +
      '<label for="auth-email">Email</label>' +
      '<input type="email" id="auth-email" placeholder="you@example.com" autocomplete="email">' +
      '<button class="auth-btn" id="auth-submit">Send Reset Code</button>' +
      '<div class="auth-error" id="auth-error"></div>' +
      '<div class="auth-success" id="auth-success"></div>' +
      '<div class="auth-footer">' +
        'Remember your password? <button class="auth-link" id="auth-to-login">Sign in</button>' +
      '</div>';

    document.getElementById('auth-to-login').onclick = function() { showModal('login'); };
    document.getElementById('auth-submit').onclick = function() {
      var email = document.getElementById('auth-email').value.trim();
      if (!email) return setError('Enter your email.');
      var btn = document.getElementById('auth-submit');
      btn.disabled = true; btn.textContent = 'Sending...';
      setError('');

      apiCall('/api/auth/forgot-password', { email: email }, function(err, data, ok) {
        btn.disabled = false; btn.textContent = 'Send Reset Code';
        if (err) return setError(err);
        if (!ok) return setError(data.error || 'Failed');
        window._authVerifyEmail = email;
        setSuccess('Reset code sent! Check your email.');
        setTimeout(function() { showModal('reset'); }, 1500);
      });
    };
  }

  // ---- Reset Password View ----
  function renderReset(c) {
    var em = window._authVerifyEmail || '';
    c.innerHTML = closeBtn() +
      '<h2>Set New Password</h2>' +
      '<p class="subtitle">Enter the code from your email and your new password</p>' +
      '<label for="auth-email">Email</label>' +
      '<input type="email" id="auth-email" value="' + em + '" placeholder="you@example.com">' +
      '<label for="auth-code">Reset Code</label>' +
      '<input type="text" id="auth-code" placeholder="123456" maxlength="6">' +
      '<label for="auth-pass">New Password</label>' +
      '<input type="password" id="auth-pass" placeholder="Min 8 chars, uppercase, lowercase, number" autocomplete="new-password">' +
      '<button class="auth-btn" id="auth-submit">Reset Password</button>' +
      '<div class="auth-error" id="auth-error"></div>' +
      '<div class="auth-success" id="auth-success"></div>' +
      '<div class="auth-footer">' +
        '<button class="auth-link" id="auth-to-login">Back to sign in</button>' +
      '</div>';

    document.getElementById('auth-to-login').onclick = function() { showModal('login'); };
    document.getElementById('auth-submit').onclick = function() {
      var email = document.getElementById('auth-email').value.trim();
      var code = document.getElementById('auth-code').value.trim();
      var pass = document.getElementById('auth-pass').value;
      if (!email || !code || !pass) return setError('All fields are required.');
      var btn = document.getElementById('auth-submit');
      btn.disabled = true; btn.textContent = 'Resetting...';
      setError('');

      apiCall('/api/auth/reset-password', { email: email, code: code, newPassword: pass }, function(err, data, ok) {
        btn.disabled = false; btn.textContent = 'Reset Password';
        if (err) return setError(err);
        if (!ok) return setError(data.error || 'Reset failed');
        setSuccess('Password reset! Redirecting to login...');
        setTimeout(function() { showModal('login'); }, 1500);
      });
    };
  }

  // ---- Profile View (logged in) ----
  function renderProfile(c) {
    var user = getUser();
    if (!user) return showModal('login');
    var displayName = user.name || user.email || 'User';
    c.innerHTML = closeBtn() +
      '<h2>Your Account</h2>' +
      '<p class="subtitle">Manage your AI1stSEO account</p>' +
      '<div style="background:rgba(255,255,255,.04);border-radius:10px;padding:16px;margin-top:12px">' +
        '<div style="color:#94a3b8;font-size:.8rem">Email</div>' +
        '<div style="color:#fff;font-size:.95rem;margin-bottom:12px">' + (user.email || 'N/A') + '</div>' +
        '<div style="color:#94a3b8;font-size:.8rem">Name</div>' +
        '<div style="color:#fff;font-size:.95rem;margin-bottom:12px">' + (user.name || 'Not set') + '</div>' +
        '<div style="color:#94a3b8;font-size:.8rem">Email Verified</div>' +
        '<div style="color:' + (user.emailVerified ? '#00ff88' : '#f87171') + ';font-size:.95rem">' + (user.emailVerified ? 'Yes' : 'No') + '</div>' +
      '</div>' +
      '<button class="auth-btn" id="auth-logout" style="background:rgba(255,255,255,.08);color:#fff;font-weight:500">Sign Out</button>' +
      '<div class="auth-error" id="auth-error"></div>' +
      '<div class="auth-success" id="auth-success"></div>' +
      '<div class="auth-footer">' +
        '<button class="auth-link danger" id="auth-delete" style="color:#f87171">Delete my account</button>' +
      '</div>';

    document.getElementById('auth-logout').onclick = function() {
      clearSession();
      closeModal();
      updateNavForUser();
    };

    document.getElementById('auth-delete').onclick = function() {
      if (!confirm('Are you sure you want to permanently delete your account? This cannot be undone.')) return;
      var token = getAccessToken();
      fetch(API + '/api/auth/delete-account', {
        method: 'DELETE',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' }
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.status === 'success') {
          clearSession();
          closeModal();
          updateNavForUser();
          alert('Account deleted successfully.');
        } else {
          setError(data.error || 'Failed to delete account');
        }
      })
      .catch(function() { setError('Network error'); });
    };
  }

  // ---- Nav Integration ----
  function updateNavForUser() {
    // Remove any existing auth UI we injected
    var existing = document.getElementById('auth-nav-container');
    if (existing) existing.remove();

    var nav = document.querySelector('nav') || document.querySelector('header');
    if (!nav) return;

    // Find the original React Login button and hide it
    var buttons = nav.querySelectorAll('button, a');
    var loginBtn = null;
    buttons.forEach(function(btn) {
      var t = btn.textContent.trim().toUpperCase();
      if (t === 'LOGIN' || t === 'SIGN UP') {
        loginBtn = btn;
      }
    });

    if (isLoggedIn()) {
      var user = getUser();
      var displayName = (user && user.name) ? user.name.split(' ')[0] : (user && user.email) ? user.email.split('@')[0] : 'Account';

      // Hide original login button
      if (loginBtn) loginBtn.style.display = 'none';

      // Create user menu
      var container = document.createElement('div');
      container.id = 'auth-nav-container';
      container.className = 'auth-user-menu';
      container.innerHTML =
        '<button class="auth-user-btn" id="auth-user-toggle">' +
          '<span style="width:24px;height:24px;background:linear-gradient(135deg,#00ff88,#00d4ff);border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:.75rem;color:#000;font-weight:700">' + displayName.charAt(0).toUpperCase() + '</span>' +
          '<span>' + displayName + '</span>' +
          '<span style="font-size:.6rem">&#9662;</span>' +
        '</button>' +
        '<div class="auth-user-dd" id="auth-user-dd">' +
          '<button id="auth-dd-profile">👤 My Account</button>' +
          '<button id="auth-dd-logout">🚪 Sign Out</button>' +
          '<button id="auth-dd-delete" class="danger">🗑️ Delete Account</button>' +
        '</div>';

      // Insert where login button was
      if (loginBtn && loginBtn.parentElement) {
        loginBtn.parentElement.insertBefore(container, loginBtn);
      } else {
        var flexContainers = nav.querySelectorAll('div');
        var target = nav;
        flexContainers.forEach(function(d) {
          var s = window.getComputedStyle(d);
          if (s.display === 'flex' && d.children.length >= 2) target = d;
        });
        target.appendChild(container);
      }

      // Wire up dropdown
      document.getElementById('auth-user-toggle').onclick = function(e) {
        e.stopPropagation();
        var dd = document.getElementById('auth-user-dd');
        dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
      };
      document.addEventListener('click', function() {
        var dd = document.getElementById('auth-user-dd');
        if (dd) dd.style.display = 'none';
      });
      document.getElementById('auth-dd-profile').onclick = function() { showModal('profile'); };
      document.getElementById('auth-dd-logout').onclick = function() {
        clearSession();
        updateNavForUser();
      };
      document.getElementById('auth-dd-delete').onclick = function() {
        if (!confirm('Permanently delete your account?')) return;
        var token = getAccessToken();
        fetch(API + '/api/auth/delete-account', {
          method: 'DELETE',
          headers: { 'Authorization': 'Bearer ' + token }
        }).then(function(r) { return r.json(); }).then(function(d) {
          clearSession();
          updateNavForUser();
          if (d.status === 'success') alert('Account deleted.');
        }).catch(function() { alert('Failed to delete account.'); });
      };

    } else {
      // Show login button — either restore original or create new one
      if (loginBtn) {
        loginBtn.style.display = '';
        // Hijack the click
        loginBtn.onclick = function(e) {
          e.preventDefault();
          e.stopPropagation();
          showModal('login');
        };
      }
    }
  }

  // ---- Init ----
  function init() {
    injectStyles();
    // Wait for React to render the nav, then hijack
    var attempts = 0;
    var interval = setInterval(function() {
      attempts++;
      var nav = document.querySelector('nav') || document.querySelector('header');
      if (nav || attempts > 40) {
        clearInterval(interval);
        updateNavForUser();
      }
    }, 500);
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
