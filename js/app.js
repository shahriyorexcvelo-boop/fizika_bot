/**
 * ASOSIY MINI APP CONTROLLER — js/app.js
 * Tab navigatsiya, API so'rovlari, profil, testlar va umumiy initsializatsiya
 */

var API_BASE  = window.API_BASE || '';
var LS_PIN    = window.LS_PIN || 'app_pin';
var LS_USER   = window.LS_USER || 'app_user';
var LS_LANG   = window.LS_LANG || 'app_lang';
var LS_THEME  = window.LS_THEME || 'app_theme';

var LANG_LABELS = { uz: 'UZ', ru: 'RU', en: 'EN' };
var splashTimer = null;

// ── STATE ────────────────────────────────────────
var state = {
  tgUser: null,
  userInfo: null,
  isAdmin: false,
  pinBuffer: '',
  pinMode: 'enter',
  pinFirst: '',
  activeTab: 'home',
  homeSubtab: 'active',
  adminSubtab: 'users',
};

// ── INIT ────────────────────────────────────────
function initApp() {
  var savedTheme = localStorage.getItem(LS_THEME) || localStorage.getItem('app_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);
  syncTelegramTheme(savedTheme);
  updateLangLabel();
  applyI18n();
  renderOnboardingSlides();

  try {
    var tg = window.Telegram && window.Telegram.WebApp;
    if (tg) {
      try { tg.ready(); tg.expand(); } catch (e) {}
    }
    var urlParams = new URLSearchParams(window.location.search);
    var queryTgId = urlParams.get('tg_id');
    var tgU = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;

    var tgPlatform = tg ? (tg.platform || '').toLowerCase() : '';
    var isTg = !!(tg && (
      (tgPlatform && tgPlatform !== 'unknown') ||
      (tg.initData && tg.initData.length > 0) ||
      (tgU && tgU.id) ||
      queryTgId
    ));

    // ODDIY VEB-BRAUZERDA (TELEGRAMSIZ) OCHILGANDA TO'LIQ BLOKLASH!
    if (!isTg) {
      var wb = document.getElementById('web-block-screen');
      if (wb) wb.style.display = 'flex';
      var sp = document.getElementById('splashScreen');
      if (sp) sp.style.display = 'none';
      var appEl = document.getElementById('app');
      if (appEl) appEl.style.display = 'none';
      return;
    }

    var effectiveId = (tgU && tgU.id) || (queryTgId ? parseInt(queryTgId, 10) : 0);
    state.tgUser = tgU || { id: effectiveId, first_name: 'Foydalanuvchi', last_name: '', username: '' };
    try {
      var savedUser = localStorage.getItem(LS_USER);
      if (savedUser && !isPreview && !state.userInfo) state.userInfo = JSON.parse(savedUser);
    } catch (e) {}
  } catch (err) {
    console.error('initApp error:', err);
  }

  if (window.BM_LOGO_B64) {
    document.querySelectorAll('.header-logo-img, .header-bm-logo, .splash-emblem-img').forEach(function(img) {
      img.src = window.BM_LOGO_B64;
    });
  }

  runSplash();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

// ── SPLASH (Kosmik Fizika Kirish Animatsiyasi) ──────────
function startSplashCanvas() {
  var canvas = document.getElementById('splash-canvas');
  if (!canvas) return null;
  var ctx = canvas.getContext('2d');
  if (!ctx) return null;

  var width = canvas.width = window.innerWidth;
  var height = canvas.height = window.innerHeight;

  var symbols = ['E=mc²', 'F=ma', 'v=s/t', 'λ', 'Ω', 'Hz', 'ρ', 'F', 'a', 'm', 'v', 'p', 'h', 'c', 'g', 'q', 'U', 'I', 'R', 'N', 'J', 'W', 'eV', 'Δt', 'B'];
  var particles = [];
  var count = Math.min(26, Math.max(16, Math.floor(width / 16)));

  for (var i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      char: symbols[Math.floor(Math.random() * symbols.length)],
      size: 13 + Math.random() * 18,
      vx: (Math.random() - 0.5) * 0.45,
      vy: -0.35 - Math.random() * 0.75,
      opacity: 0.12 + Math.random() * 0.45,
      pulseSpeed: 0.02 + Math.random() * 0.03,
      angle: Math.random() * Math.PI * 2,
      spinSpeed: (Math.random() - 0.5) * 0.015
    });
  }

  var animId = null;
  var isDark = document.documentElement.getAttribute('data-theme') !== 'light';

  function draw() {
    ctx.clearRect(0, 0, width, height);
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.angle += p.spinSpeed;
      p.opacity += Math.sin(Date.now() * p.pulseSpeed) * 0.005;
      if (p.opacity < 0.1) p.opacity = 0.1;
      if (p.opacity > 0.6) p.opacity = 0.6;

      if (p.y < -30) { p.y = height + 30; p.x = Math.random() * width; }
      if (p.x < -30) p.x = width + 30;
      if (p.x > width + 30) p.x = -30;

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.angle);
      ctx.font = 'bold ' + p.size + 'px serif';
      if (isDark) {
        ctx.fillStyle = 'rgba(251, 113, 133, ' + p.opacity + ')';
        ctx.shadowColor = 'rgba(244, 63, 94, 0.45)';
        ctx.shadowBlur = 8;
      } else {
        ctx.fillStyle = 'rgba(225, 29, 72, ' + (p.opacity * 0.85) + ')';
        ctx.shadowColor = 'rgba(225, 29, 72, 0.25)';
        ctx.shadowBlur = 6;
      }
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(p.char, 0, 0);
      ctx.restore();
    }
    animId = requestAnimationFrame(draw);
  }

  animId = requestAnimationFrame(draw);

  return function stop() {
    if (animId) cancelAnimationFrame(animId);
  };
}

var _stopSplashCanvas = null;

function dismissSplash() {
  if (splashTimer) clearTimeout(splashTimer);
  if (typeof _stopSplashCanvas === 'function') {
    try { _stopSplashCanvas(); } catch(e) {}
    _stopSplashCanvas = null;
  }
  var splash = document.getElementById('splashScreen') || document.getElementById('splash-screen');
  if (!splash) return;
  if (splash._dismissed) return;
  splash._dismissed = true;

  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    try { window.Telegram.WebApp.HapticFeedback.impactOccurred('medium'); } catch(e) {}
  }

  splash.classList.add('dismissed');
  setTimeout(function() {
    splash.style.display = 'none';
    var isUnreg = checkRegistrationStatus();
    if (!isUnreg && !localStorage.getItem('onboarding_nav_tour_seen')) {
      setTimeout(function() {
        openOnboardingModal();
      }, 300);
    }
  }, 750);
}
window.dismissSplash = dismissSplash;
window.finishSplashImmediately = dismissSplash;

function runSplash() {
  var splash = document.getElementById('splashScreen') || document.getElementById('splash-screen');
  if (!splash) { launchApp(); return; }

  // Kosmik fizika zarrachalari animatsiyasini ishga tushirish
  _stopSplashCanvas = startSplashCanvas();

  // Ma'lumotlarni fonda oldindan yuklash
  launchApp();

  // 3200ms dan so'ng animatsiya to'liq va tabiiy yakunlangach o'tish (boshqa mini app kabi)
  splashTimer = setTimeout(function() {
    dismissSplash();
  }, 3200);
}

// ── PIN SYSTEM (Olib tashlangan / Bypassed) ──────────────────
async function initPinScreen() { launchApp(); }
function updatePinUI() {}
function onPinKey() {}
function onPinDel() {}
function renderPinDots() {}
async function processPin() { launchApp(); }
function showPinError() {}
function changePinPrompt() { showToast("PIN kod talab etilmaydi"); }

// ── LAUNCH APP ──────────────────────────────────
async function launchApp() {
  var pinScreen = document.getElementById('pin-screen');
  if (pinScreen) {
    pinScreen.style.display = 'none';
  }

  var app = document.getElementById('app');
  if (app) {
    app.style.display = 'flex';
    app.style.flexDirection = 'column';
    app.classList.add('visible');
  }

  applyI18n();
  updateHeaderUser();

  // Profil va faol testlarni parallel (bir vaqtda) yuklash
  Promise.all([
    loadUserProfile().catch(function(e) { console.warn('Profile:', e); }),
    loadActiveTests().catch(function(e) { console.warn('ActiveTests:', e); })
  ]).then(function() {
    updateHeaderUser();
    try {
      var urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('tab') === 'admin' && state.isAdmin) {
        switchTab('admin');
      }
    } catch (e) {}
  });

  // Yangi foydalanuvchilar uchun tugmalar va dizayn qo'llanmasi
  var splashScreen = document.getElementById('splash-screen');
  if (!splashScreen && !localStorage.getItem('onboarding_nav_tour_seen')) {
    setTimeout(function() {
      openOnboardingModal();
    }, 600);
  }

  // Real vaqt rejimida Bot & Server faolligini tekshirish
  checkBotServerStatus();
  setInterval(checkBotServerStatus, 25000);
}

// ── SERVER & BOT STATUS MONITOR ─────────────────
async function checkBotServerStatus() {
  var pill = document.getElementById('bot-status-pill');
  var txt = document.getElementById('bot-status-text');
  if (!pill || !txt) return;

  try {
    var controller = new AbortController();
    var timeoutId = setTimeout(function() { controller.abort(); }, 10000);
    var res = await fetch(API_BASE + '/api/app/status', { signal: controller.signal });
    clearTimeout(timeoutId);

    if (res.ok) {
      var data = await res.json();
      if (data.bot_username) window.BOT_USERNAME = data.bot_username;
      if (data.bot_active || data.status === 'online') {
        pill.className = 'server-status-pill online';
        txt.textContent = 'Faol';
        pill.setAttribute('title', 'Bot va Server 24/7 faol ishlamoqda');
        return;
      }
    }
    throw new Error('Offline');
  } catch (e) {
    pill.className = 'server-status-pill offline';
    txt.textContent = 'O\'chiq';
    pill.setAttribute('title', 'Server yoki kompyuter o\'chiq holatda');
  }
}

// ── API & AUTENTIFIKATSIYA ─────────────────────────
function getAuthHeaders(customHeaders) {
  var headers = Object.assign({}, customHeaders || {});
  var initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }
  return headers;
}

async function apiGet(path) {
  var initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
  var fullUrl = API_BASE + path;
  if (initData && fullUrl.indexOf('init_data=') === -1) {
    var sep = fullUrl.indexOf('?') === -1 ? '?' : '&';
    fullUrl += sep + 'init_data=' + encodeURIComponent(initData);
  }
  var res = await fetch(fullUrl, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('API ' + res.status);
  return res.json();
}

async function loadUserProfile() {
  var urlParams = new URLSearchParams(window.location.search);
  var tgId = (state.tgUser && state.tgUser.id) || parseInt(urlParams.get('tg_id')) || 0;
  if (!tgId) {
    var tg = window.Telegram && window.Telegram.WebApp;
    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
      tgId = tg.initDataUnsafe.user.id;
      state.tgUser = tg.initDataUnsafe.user;
    }
  }
  var isPreview = urlParams.get('preview') === 'user' || urlParams.get('mode') === 'user' || urlParams.get('demo') === '1';
  if (isPreview) {
    state.userInfo = {
      tg_id: 7080517395,
      fullname: "O'quvchi (Namuna)",
      phone: "+998901234567",
      status: "approved",
      is_registered: true
    };
    state.isAdmin = false;
    window._unregBypassed = true;
    var adminTab = document.getElementById('nav-admin');
    if (adminTab) adminTab.style.display = 'none';
    var searchNav = document.getElementById('nav-search');
    if (searchNav) searchNav.style.display = 'flex';
    checkRegistrationStatus();
    return;
  }
  if (!tgId || tgId === 0) {
    checkRegistrationStatus();
    return;
  }
  try {
    var data = await apiGet('/api/app/profile?tg_id=' + tgId);
    if (data.success) {
      if (data.bot_username) window.BOT_USERNAME = data.bot_username;
      state.userInfo = data.user;
      if (data.is_admin) {
        state.isActualAdmin = true;
      }
      if (state.isSimulatedUser) {
        state.isAdmin = false;
      } else {
        state.isAdmin = Boolean(data.is_admin);
      }
      localStorage.setItem(LS_USER, JSON.stringify(data.user));
      if (urlParams.get('preview') === 'user' || urlParams.get('mode') === 'user') {
        state.isAdmin = false;
      }
      var adminTab = document.getElementById('nav-admin');
      if (adminTab) adminTab.style.display = state.isAdmin ? 'flex' : 'none';
      var banner = document.getElementById('admin-simulation-banner');
      if (banner) banner.style.display = state.isSimulatedUser ? 'flex' : 'none';
      if (data.user && data.user.is_registered) {
        var unregModal = document.getElementById('unregistered-modal');
        if (unregModal) unregModal.style.display = 'none';
      } else {
        checkRegistrationStatus();
      }
      var searchNav = document.getElementById('nav-search');
      if (searchNav) searchNav.style.display = 'flex';
      if (state.isAdmin && data.pending_users > 0) {
        var badge = document.getElementById('admin-badge');
        if (badge) { badge.textContent = data.pending_users; badge.style.display = 'block'; }
      }
      if (urlParams.get('tab') === 'admin' && state.isAdmin) {
        switchTab('admin');
      }
    } else {
      state.userInfo = { status: 'not_registered', is_registered: false };
      checkRegistrationStatus();
      var searchNav = document.getElementById('nav-search');
      if (searchNav) searchNav.style.display = 'flex';
    }
  } catch (e) {
    console.warn('loadUserProfile err:', e);
    if (!state.userInfo) {
      state.userInfo = { status: 'not_registered', is_registered: false };
    }
    checkRegistrationStatus();
    var searchNav = document.getElementById('nav-search');
    if (searchNav) searchNav.style.display = 'flex';
  }
}

async function loadActiveTests() {
  var tab = document.getElementById('tab-home');
  if (!tab) return;
  tab.innerHTML = '<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>';
  try {
    var tgId = (state.tgUser && state.tgUser.id) || 0;
    var data = await apiGet('/api/app/active-tests?tg_id=' + tgId);
    if (data.success) {
      if (data.server_time) {
        window._serverTimeOffset = (data.server_time * 1000) - Date.now();
      }
      window.availableActiveTests = data.tests || [];
      window._availableTests = window.availableActiveTests;
      renderHomeTab(data.tests);
    }
    else throw new Error('no success');
  } catch (e) {
    tab.innerHTML = '<div class="empty-state"><div class="empty-icon">\u26A0\uFE0F</div><p>' + t('empty_active') + '</p></div>';
  }
}

async function loadMyResults() {
  var tab = document.getElementById('tab-tests');
  tab.innerHTML = '<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>';
  try {
    var tgId = (state.tgUser && state.tgUser.id) || 0;
    var data = await apiGet('/api/app/my-results?tg_id=' + tgId);
    if (data.success) {
      window.cachedMyResults = data.results || [];
      window._myResults = window.cachedMyResults;
      renderTestsTab(data.results);
    }
    else throw new Error('no success');
  } catch (e) {
    tab.innerHTML = '<div class="empty-state"><div class="empty-icon">\u26A0\uFE0F</div><p>' + t('empty_tests') + '</p></div>';
  }
}

async function loadAllUsers() {
  try {
    var urlParams = new URLSearchParams(window.location.search);
    var tgId = (state.tgUser && state.tgUser.id) || parseInt(urlParams.get('tg_id')) || 0;
    
    // Agar testlar ro'yxati yuklanmagan bo'lsa, shablonlar uchun fon rejimida yuklab olamiz
    if (!window.availableActiveTests) {
      apiGet('/api/app/active-tests?tg_id=' + tgId).then(function(d) {
        if (d && d.success) window.availableActiveTests = d.tests || [];
      }).catch(function() {});
    }

    var data = await apiGet('/api/app/users?tg_id=' + tgId);
    if (data.success) {
      renderUsersSection(data.users, data.stats);
    } else {
      var listEl = document.getElementById('users-list');
      if (listEl) {
        listEl.innerHTML = '<div class="empty-state" style="padding:24px 10px;"><div class="empty-icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div><p>' + (data.message || 'Foydalanuvchilarni yuklab bo\'lmadi') + '</p></div>';
      }
    }
  } catch (e) {
    console.warn('users err:', e);
    var listEl = document.getElementById('users-list');
    if (listEl) {
      listEl.innerHTML = '<div class="empty-state" style="padding:24px 10px;"><div class="empty-icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div><p>Server bilan bog\'lanishda xatolik</p></div>';
    }
  }
}

// ── TAB NAVIGATION ──────────────────────────────
function switchTab(tabId) {
  state.activeTab = tabId;

  // Telegram Haptic feedback
  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    try {
      window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
    } catch(e) {}
  }

  // Animate clicked nav button with spring pop
  var activeBtn = document.getElementById('nav-' + tabId);
  if (activeBtn) {
    activeBtn.classList.remove('nav-tap-pop');
    void activeBtn.offsetWidth; // trigger reflow
    activeBtn.classList.add('nav-tap-pop');
    setTimeout(function() {
      activeBtn.classList.remove('nav-tap-pop');
    }, 450);
  }

  document.querySelectorAll('.nav-item').forEach(function(el) {
    el.classList.toggle('active', el.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-content').forEach(function(el) {
    el.classList.toggle('active', el.id === 'tab-' + tabId);
  });
  if (tabId === 'home') loadActiveTests();
  else if (tabId === 'tests') loadMyResults();
  else if (tabId === 'profile') renderProfileTab();
  else if (tabId === 'admin') { renderAdminTab(); loadAllUsers(); }
}

function switchHomeSubtab(subtab) {
  if (state.homeSubtab === subtab) return;
  state.homeSubtab = subtab;

  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    try {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    } catch(e) {}
  }

  if (window.availableActiveTests) {
    renderHomeTab(window.availableActiveTests);
  } else {
    loadActiveTests();
  }
}

function openTestSolving(testId) {
  var tgId = (state.tgUser && state.tgUser.id) || 0;
  window.location.href = '/index.html?test_id=' + testId + '&tg_id=' + tgId;
}

function returnToTelegramChat() {
  if (window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.close === 'function') {
    window.Telegram.WebApp.close();
  } else {
    showToast('Telegram bot chatiga qaytildi');
  }
}

function startTestInBot(testCode, testId) {
  var tgId = (state.tgUser && state.tgUser.id) || 0;
  if (!tgId && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.user) {
    tgId = window.Telegram.WebApp.initDataUnsafe.user.id;
  }

  if (tgId) {
    var url = '/api/app/trigger-solve?tg_id=' + encodeURIComponent(tgId) + 
              '&test_code=' + encodeURIComponent(testCode || '') + 
              '&test_id=' + encodeURIComponent(testId || '');
    try {
      fetch(url, { keepalive: true }).catch(function(e) { console.error(e); });
    } catch(e) {
      console.error("Trigger solve error:", e);
    }
  }

  if (window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.close === 'function' && window.Telegram.WebApp.initData) {
    if (window.Telegram.WebApp.HapticFeedback && window.Telegram.WebApp.HapticFeedback.notificationOccurred) {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
    }
    setTimeout(function() {
      window.Telegram.WebApp.close();
    }, 120);
  } else {
    // Brauzerda test rejimida ochilganda bevosita yechish oynasiga o'tish
    openTestSolving(testId);
  }
}

function isTestUpcoming(test) {
  if (!test) return false;

  // 1. Agar backend server testni allaqachon boshlangan deb belgilagan bo'lsa (is_upcoming === false):
  // Demak, Toshkent vaqti bilan test allaqachon faol! Foydalanuvchining kompyuter/telefon soati noto'g'ri bo'lsa ham hech qachon bloklanmaydi!
  if (test.is_upcoming === false && !test.code_hidden) {
    return false;
  }

  // 2. Agar server testni kutilmoqda (is_upcoming) deb belgilagan bo'lsa:
  // Sahifada turgan paytda boshlanish vaqti yetib kelganligini server bilan sinxronlangan vaqt orqali tekshiramiz:
  if (!test.scheduled_start) {
    return Boolean(test.code_hidden || test.is_upcoming);
  }

  try {
    // Server vaqti bilan to'liq kalibrlangan Toshkent vaqti (UTC+5)
    var serverNowMs = Date.now() + (window._serverTimeOffset || 0);
    var uzbDate = new Date(serverNowMs + (5 * 3600000));
    var todayYear = uzbDate.getUTCFullYear();
    var todayMonth = uzbDate.getUTCMonth();
    var todayDay = uzbDate.getUTCDate();
    var nowMinutes = uzbDate.getUTCHours() * 60 + uzbDate.getUTCMinutes();

    var sdate = (test.scheduled_date || '').trim();
    if (sdate) {
      var parts = sdate.split(/[-.]/);
      var tYear, tMonth, tDay;
      if (parts[0].length === 4) {
        tYear = parseInt(parts[0], 10);
        tMonth = parseInt(parts[1], 10) - 1;
        tDay = parseInt(parts[2], 10);
      } else {
        tDay = parseInt(parts[0], 10);
        tMonth = parseInt(parts[1], 10) - 1;
        tYear = parseInt(parts[2], 10);
      }

      var tDateOnly = Date.UTC(tYear, tMonth, tDay);
      var curDateOnly = Date.UTC(todayYear, todayMonth, todayDay);
      if (tDateOnly > curDateOnly) return true;
      if (tDateOnly < curDateOnly) return false;
    }

    var startParts = test.scheduled_start.split(':');
    var startMinutes = parseInt(startParts[0], 10) * 60 + parseInt(startParts[1], 10);

    var endMinutes = null;
    if (test.scheduled_end) {
      try {
        var endParts = test.scheduled_end.split(':');
        endMinutes = parseInt(endParts[0], 10) * 60 + parseInt(endParts[1], 10);
      } catch(e) {}
    }

    if (endMinutes !== null && endMinutes < startMinutes) {
      // Yarim tun orqali o'tuvchi test (masalan 23:30 dan 00:30 gacha)
      if (nowMinutes >= startMinutes || nowMinutes < endMinutes) {
        return false;
      } else {
        return true;
      }
    } else {
      if (nowMinutes < startMinutes) {
        return true;
      } else {
        return false;
      }
    }
  } catch(e) {}

  if (test.is_upcoming || test.code_hidden) return true;
  return false;
}

function showTestNotStartedAlert(startStr) {
  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    try {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred('warning');
    } catch(e) {}
  }
  showToast(t('toast_test_not_started') + ' ' + (startStr || '—'));
}

function renderTestDetailCard(test, type) {
  var tgId = (state.tgUser && state.tgUser.id) || 0;
  var isUpcoming = (type === 'upcoming' || isTestUpcoming(test));
  var isActive = (type === 'active' && !isUpcoming);
  var isInactive = (type === 'inactive' && !isUpcoming);
  var done = Boolean(test.already_submitted);

  // Check matching submission in window._myResults if available
  var matchingResult = null;
  if (window._myResults && window._myResults.length > 0) {
    matchingResult = window._myResults.find(function(r) {
      return (r.test_id && test.id && Number(r.test_id) === Number(test.id)) ||
             (r.test_code && test.test_code && String(r.test_code).trim().toLowerCase() === String(test.test_code).trim().toLowerCase());
    });
    if (matchingResult) {
      done = true;
      if (matchingResult.is_rejected || matchingResult.status === 'rejected') {
        test.is_rejected = true;
      }
      var isPub = Boolean(matchingResult.results_published);
      if (test.is_rejected) {
        test.user_score = 0;
        test.user_correct = 0;
        test.user_grade = "Bekor qilingan";
      } else if (isPub) {
        if (test.user_score == null) test.user_score = matchingResult.score;
        if (test.user_correct == null) test.user_correct = matchingResult.correct_count;
        if (test.user_total == null) test.user_total = matchingResult.total_count;
        if (test.user_grade == null) test.user_grade = matchingResult.grade;
      } else {
        test.user_score = null;
        test.user_correct = null;
        test.user_total = null;
        test.user_grade = "Kutilmoqda";
      }
      if (test.submitted_at == null) test.submitted_at = matchingResult.submitted_at;
      test.results_published = matchingResult.results_published;
    }
  }

  var isRejected = Boolean(test.is_rejected || (matchingResult && (matchingResult.is_rejected || matchingResult.status === 'rejected')));

  var cardClass = isUpcoming ? 'test-card-upcoming' : (isActive ? 'test-card-active' : 'test-card-closed');
  var badgeHtml = '';
  if (isRejected) {
    badgeHtml = '<span class="badge" style="background:rgba(239,68,68,0.15);color:#EF4444;border:1px solid rgba(239,68,68,0.3);font-weight:800;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="display:inline-block;vertical-align:-1px;margin-right:3px"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>' + (t('badge_cancelled') || 'Bekor qilingan') + '</span>';
  } else if (isUpcoming) {
    badgeHtml = '<span class="badge" style="background:rgba(245,158,11,0.15);color:#D97706;border:1px solid rgba(245,158,11,0.3);font-weight:800;">' + t('badge_upcoming') + '</span>';
  } else if (isActive) {
    if (done) {
      badgeHtml = '<span class="badge" style="background:rgba(16,185,129,0.15);color:#059669;border:1px solid rgba(16,185,129,0.3);font-weight:800;">' + (Boolean(test.results_published) ? t('badge_submitted') : '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' + t('badge_submitted')) + '</span>';
    } else {
      badgeHtml = '<span class="badge" style="background:rgba(16,185,129,0.15);color:#10B981;border:1px solid rgba(16,185,129,0.3);font-weight:800;">' + t('badge_active_now') + '</span>';
    }
  } else {
    // Inactive / Past test: tepadagi badge shart emas, chunki pastdagi alohida banner aniq ko'rsatib turadi
    badgeHtml = '';
  }

  var displayTitle = (test.title || t('default_test_title'));
  if (isUpcoming) {
    displayTitle = displayTitle.replace(/\s*#[\w\d]+\b/g, '').trim();
  }

  var codeDisplay = '—';
  if (isUpcoming) {
    codeDisplay = '<span style="background:rgba(245,158,11,0.14);color:#D97706;padding:3px 9px;border-radius:6px;font-size:12px;font-weight:700;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>' + t('code_hidden_until_start') + '</span>';
  } else if (test.test_code) {
    codeDisplay = String(test.test_code).startsWith('#') ? test.test_code : ('#' + test.test_code);
  }

  var dateStr = test.scheduled_date ? escHtml(test.scheduled_date) : (test.created_at ? formatDateOnly(test.created_at) : (isUpcoming ? t('val_scheduled_soon') : t('val_today')));
  
  // Haqiqiy boshlangan vaqt (Har bir testning o'z ma'lumotlari)
  var startStr = '—';
  if (test.scheduled_start) {
    startStr = escHtml(test.scheduled_start) + ' (UZB)';
  } else if (test.first_submission_at) {
    startStr = formatTimeOnly(test.first_submission_at) + ' (UZB)';
  } else if (test.created_at) {
    startStr = formatTimeOnly(test.created_at) + ' (UZB)';
  } else if (isActive) {
    startStr = t('val_started');
  }

  // Haqiqiy to'xtatilgan / yakunlangan vaqt (22:00 qotirilmagan, haqiqiy to'xtatilgan vaqti)
  var endStr = '—';
  if (test.stopped_at) {
    endStr = formatTimeOnly(test.stopped_at) + ' (UZB)';
  } else if (test.scheduled_end) {
    endStr = escHtml(test.scheduled_end) + ' (UZB)';
  } else if (test.last_submission_at) {
    endStr = formatTimeOnly(test.last_submission_at) + ' (UZB)';
  } else if (isInactive) {
    if (test.created_at && test.time_limit_min) {
      endStr = formatTimeOnly(test.created_at + test.time_limit_min * 60) + ' (UZB)';
    } else if (test.created_at) {
      endStr = formatTimeOnly(test.created_at + 7200) + ' (UZB)';
    } else {
      endStr = t('val_ended');
    }
  } else {
    endStr = t('val_unlimited');
  }
  var totalQuestions = (test.total_questions || 45) + ' ' + t('val_questions_format');
  var timeLimit = test.time_limit_min ? (test.time_limit_min + ' ' + t('val_minutes')) : t('val_infinite');
  var ytUrl = (test.youtube_url || '').trim();
  var ytStatus = ytUrl ? ('<span style="color:#DC2626;font-weight:700;">' + t('val_yt_available') + '</span>') : ('<span style="color:var(--text-muted);">' + t('val_yt_planning') + '</span>');

  var cardOnClick = isInactive ? (' onclick="handlePastTestCardClick(' + test.id + ')" style="cursor:pointer;"') : '';

  var userStatusBannerHtml = '';
  if (isRejected) {
    userStatusBannerHtml =
      '<div class="test-user-status-banner" style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);border-radius:12px;padding:12px 14px;display:flex;gap:10px;align-items:flex-start;margin:12px 0;">' +
        '<span class="status-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg></span>' +
        '<div class="status-content">' +
          '<div class="status-title" style="color:#EF4444;font-weight:800;font-size:13.5px;">Test javoblaringiz bekor qilingan</div>' +
          '<div class="status-desc" style="color:var(--text-muted);font-size:12px;margin-top:2px;">Ushbu test bo\'yicha topshirgan javoblaringiz ma\'muriyat tomonidan bekor qilindi va qabul qilinmadi.</div>' +
        '</div>' +
      '</div>';
  } else if (isInactive) {
    if (done) {
      var isPub = Boolean(test.results_published);
      var scoreText = (isPub && test.user_score != null) ? (test.user_score + ' ' + t('test_score_unit')) : '';
      var correctPart = (isPub && test.user_correct != null) ? (' (' + test.user_correct + ' ' + t('tests_stat_correct') + ')') : '';
      var iconDone = isPub
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
      userStatusBannerHtml =
        '<div class="test-user-status-banner status-participated">' +
          '<span class="status-icon">' + iconDone + '</span>' +
          '<div class="status-content">' +
            '<div class="status-title">' + (isPub ? t('user_status_participated') : 'Javoblaringiz qabul qilindi (Jarayonda)') + '</div>' +
            '<div class="status-desc">' + (scoreText ? (t('stat_score') + ': <b>' + scoreText + '</b>' + correctPart) : (isPub ? t('test_ended_user_took') : 'Test davom etmoqda. Admin Rasch tahlili o\'tkazgach, ballaringiz e\'lon qilinadi.')) + '</div>' +
          '</div>' +
        '</div>';
    } else {
      userStatusBannerHtml =
        '<div class="test-user-status-banner status-not-participated">' +
          '<span class="status-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span>' +
          '<div class="status-content">' +
            '<div class="status-title">' + t('user_status_not_participated') + '</div>' +
            '<div class="status-desc">' + t('test_ended_on_desc') + '</div>' +
          '</div>' +
        '</div>';
    }
  }

  var iconHeader = isUpcoming
    ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
    : (isActive
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>');

  var html = '<div class="test-rich-card ' + cardClass + ' animate-in"' + cardOnClick + '>' +
    '<div class="test-rich-header">' +
      '<div class="test-rich-icon ' + (isUpcoming ? 'amber' : (isActive ? 'green' : 'gray')) + '">' +
        iconHeader +
      '</div>' +
      '<div class="test-rich-title-box">' +
        '<div class="test-rich-title">' + escHtml(displayTitle) + '</div>' +
        '<div class="test-rich-subject">' + escHtml(test.subject || t('default_subject')) + '</div>' +
      '</div>' +
      '<div>' + badgeHtml + '</div>' +
    '</div>' +
    userStatusBannerHtml +

    // Qatorma-qator to'liq ma'lumotlar ro'yxati (Boshlangan va To'xtatilgan vaqtlari bilan)
    '<div class="test-rich-info-grid">' +
      '<div class="test-rich-info-row">' +
        '<span class="test-rich-label">' + t('lbl_test_code') + '</span>' +
        '<span class="test-rich-val test-rich-code">' + (isUpcoming ? codeDisplay : escHtml(codeDisplay)) + '</span>' +
      '</div>' +
      '<div class="test-rich-info-row">' +
        '<span class="test-rich-label">' + (isInactive ? t('lbl_ended_date') : t('lbl_scheduled_date')) + '</span>' +
        '<span class="test-rich-val">' + dateStr + '</span>' +
      '</div>' +
      '<div class="test-rich-info-row">' +
        '<span class="test-rich-label">' + t('lbl_start_time') + '</span>' +
        '<span class="test-rich-val">' + startStr + '</span>' +
      '</div>' +
      '<div class="test-rich-info-row">' +
        '<span class="test-rich-label">' + (isInactive ? t('lbl_ended_time') : t('lbl_end_time')) + '</span>' +
        '<span class="test-rich-val">' + endStr + '</span>' +
      '</div>' +
      '<div class="test-rich-info-row">' +
        '<span class="test-rich-label">' + t('lbl_questions_count') + '</span>' +
        '<span class="test-rich-val">' + totalQuestions + '</span>' +
      '</div>' +
      (test.time_limit_min ? (
        '<div class="test-rich-info-row">' +
          '<span class="test-rich-label">' + t('lbl_time_limit') + '</span>' +
          '<span class="test-rich-val">' + timeLimit + '</span>' +
        '</div>'
      ) : '') +
      '<div class="test-rich-info-row">' +
        '<span class="test-rich-label">' + t('lbl_video_analysis') + '</span>' +
        '<span class="test-rich-val">' + ytStatus + '</span>' +
      '</div>' +
    '</div>';

  // Tugmalar
  html += '<div class="test-rich-actions">';
  if (isRejected) {
    html += '<button type="button" class="btn-rich-action" style="width:100%;background:rgba(239,68,68,0.15);color:#EF4444;border:1px solid rgba(239,68,68,0.3);font-weight:800;cursor:pointer;" onclick="event.stopPropagation(); showToast(\'Ushbu test javoblaringiz ma\\\'muriyat tomonidan bekor qilingan\');">' +
      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>Test bekor qilingan' +
    '</button>';
  } else if (isUpcoming) {
    html += '<button type="button" class="btn-rich-action btn-rich-secondary" style="width:100%;cursor:pointer;" onclick="event.stopPropagation(); showTestNotStartedAlert(\'' + escHtml(startStr) + '\')">' +
      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' + t('btn_waiting_start') + (test.scheduled_start ? (' (' + escHtml(test.scheduled_start) + ')') : '') +
    '</button>';
  } else if (isActive) {
    if (done) {
      var isPub = Boolean(test.results_published);
      var btnDoneIcon = isPub
        ? '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="display:inline-block;vertical-align:-2px;margin-right:4px"><polyline points="20 6 9 17 4 12"/></svg>'
        : '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
      html += '<button type="button" class="btn-rich-action btn-rich-success" style="width:100%" onclick="event.stopPropagation(); openPastTestResult(' + test.id + ')">' +
        btnDoneIcon + (isPub ? t('btn_view_result') : 'Javoblar qabul qilindi (Jarayonda)') +
      '</button>';
    } else {
      html += '<button type="button" class="btn-rich-action btn-rich-primary" style="width:100%" onclick="event.stopPropagation(); startTestInBot(\'' + (test.test_code || '') + '\', ' + test.id + ')">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>' + t('btn_solve_test') +
      '</button>';
    }
  } else {
    // Inactive / Past test buttons
    if (done) {
      html += '<button type="button" class="btn-rich-action btn-rich-success" style="width:100%" onclick="event.stopPropagation(); openPastTestResult(' + test.id + ')">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>' + t('btn_view_my_result') +
      '</button>';
    } else {
      html += '<button type="button" class="btn-rich-action btn-rich-secondary" style="width:100%" onclick="event.stopPropagation(); showPastTestEndedModal(' + test.id + ')">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>' + t('btn_test_ended_info') +
      '</button>';
    }
  }
  html += '</div>';

  html += '</div>';
  return html;
}

function handlePastTestCardClick(testId) {
  var test = (window.availableActiveTests || []).find(function(t) { return t.id === testId; });
  if (!test) return;
  var done = Boolean(test.already_submitted);
  if (!done && window._myResults && window._myResults.length > 0) {
    done = window._myResults.some(function(r) {
      return (r.test_id && Number(r.test_id) === Number(test.id)) ||
             (r.test_code && test.test_code && String(r.test_code).trim().toLowerCase() === String(test.test_code).trim().toLowerCase());
    });
  }
  if (done) {
    openPastTestResult(testId);
  } else {
    showPastTestEndedModal(testId);
  }
}

function openPastTestResult(testId) {
  var matching = null;
  if (window._myResults && window._myResults.length > 0) {
    matching = window._myResults.find(function(r) {
      return (r.test_id && Number(r.test_id) === Number(testId));
    });
  }
  if (!matching) {
    var tObj = (window.availableActiveTests || []).find(function(t) { return t.id === testId; });
    if (tObj && tObj.already_submitted) {
      matching = {
        test_id: tObj.id,
        test_title: tObj.title,
        score: tObj.user_score,
        correct_count: tObj.user_correct,
        total_count: tObj.user_total || 45,
        grade: tObj.user_grade || "Kutilmoqda",
        submitted_at: tObj.submitted_at,
        results_published: Boolean(tObj.results_published)
      };
    }
  }

  if (matching) {
    showResultModal(matching);
  } else {
    switchTab('tests');
  }
}

function showPastTestEndedModal(testId) {
  var test = (window.availableActiveTests || []).find(function(t) { return t.id === testId; });
  if (!test) return;

  var dateStr = test.scheduled_date ? escHtml(test.scheduled_date) : (test.created_at ? formatDateOnly(test.created_at) : t('val_today'));
  var startStr = '—';
  if (test.scheduled_start) {
    startStr = escHtml(test.scheduled_start) + ' (UZB)';
  } else if (test.first_submission_at) {
    startStr = formatTimeOnly(test.first_submission_at) + ' (UZB)';
  } else if (test.created_at) {
    startStr = formatTimeOnly(test.created_at) + ' (UZB)';
  }

  var endStr = '—';
  if (test.stopped_at) {
    endStr = formatTimeOnly(test.stopped_at) + ' (UZB)';
  } else if (test.scheduled_end) {
    endStr = escHtml(test.scheduled_end) + ' (UZB)';
  } else if (test.last_submission_at) {
    endStr = formatTimeOnly(test.last_submission_at) + ' (UZB)';
  } else if (test.created_at && test.time_limit_min) {
    endStr = formatTimeOnly(test.created_at + test.time_limit_min * 60) + ' (UZB)';
  } else if (test.created_at) {
    endStr = formatTimeOnly(test.created_at + 7200) + ' (UZB)';
  } else {
    endStr = t('val_ended');
  }
  var title = test.title || t('default_test_title');
  var code = test.test_code ? (String(test.test_code).startsWith('#') ? test.test_code : ('#' + test.test_code)) : '—';
  var done = Boolean(test.already_submitted);

  if (!done && window._myResults && window._myResults.length > 0) {
    done = window._myResults.some(function(r) {
      return (r.test_id && Number(r.test_id) === Number(test.id)) ||
             (r.test_code && test.test_code && String(r.test_code).trim().toLowerCase() === String(test.test_code).trim().toLowerCase());
    });
  }

  var modal = document.getElementById('past-test-modal');
  var titleEl = document.getElementById('past-test-modal-title');
  var body = document.getElementById('past-test-modal-body');
  if (!modal || !body) return;

  if (titleEl) titleEl.textContent = t('test_ended_modal_title');

  var userStatusHtml = '';
  if (done) {
    var sc = test.user_score != null ? test.user_score : '—';
    var correctCount = test.user_correct != null ? test.user_correct : '—';
    userStatusHtml =
      '<div class="past-modal-status-box status-participated">' +
        '<div style="width:36px;height:36px;border-radius:50%;background:rgba(16,185,129,0.15);color:#059669;display:flex;align-items:center;justify-content:center;flex-shrink:0;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg></div>' +
        '<div>' +
          '<div style="font-weight:900;font-size:15px;color:#059669;">' + t('user_status_participated') + '</div>' +
          '<div style="font-size:13px;color:var(--text-muted);margin-top:3px;">' +
            t('stat_score') + ': <b>' + sc + ' ' + t('test_score_unit') + '</b> (' + correctCount + ' ' + t('tests_stat_correct') + ')' +
          '</div>' +
        '</div>' +
      '</div>';
  } else {
    userStatusHtml =
      '<div class="past-modal-status-box status-not-participated">' +
        '<div style="width:36px;height:36px;border-radius:50%;background:rgba(239,68,68,0.15);color:#DC2626;display:flex;align-items:center;justify-content:center;flex-shrink:0;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></div>' +
        '<div>' +
          '<div style="font-weight:900;font-size:15px;color:#DC2626;">' + t('user_status_not_participated') + '</div>' +
          '<div style="font-size:13px;color:var(--text-muted);margin-top:3px;line-height:1.4;">' +
            t('test_ended_user_not_took') +
          '</div>' +
        '</div>' +
      '</div>';
  }

  var ytHtml = '';
  if (test.youtube_url && test.youtube_url.trim()) {
    ytHtml =
      '<a href="' + escHtml(test.youtube_url.trim()) + '" target="_blank" class="past-modal-yt-btn">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px;"><polygon points="5 3 19 12 5 21 5 3"/></svg>' + t('val_yt_available') +
      '</a>';
  }

  var actionBtnHtml = '';
  if (done) {
    actionBtnHtml =
      '<button type="button" class="btn-primary" style="width:100%;margin-bottom:10px;padding:12px;border-radius:12px;font-weight:800;font-size:14px;" onclick="closePastTestModal(); openPastTestResult(' + test.id + ');">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px;"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>' + t('btn_view_my_result') +
      '</button>';
  }

  var summaryNotice = t('test_ended_on_datetime')
    .replace('{date}', '<b>' + escHtml(dateStr) + '</b>')
    .replace('{time}', '<b>' + escHtml(endStr) + '</b>');

  body.innerHTML =
    '<div class="past-modal-hero">' +
      '<div class="past-modal-lock-icon"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>' +
      '<h3 class="past-modal-heading">' + t('test_ended_modal_title') + '</h3>' +
      '<div class="past-modal-title-tag">' + escHtml(title) + ' (' + escHtml(code) + ')</div>' +
    '</div>' +

    '<div class="past-modal-info-card">' +
      '<div class="past-modal-info-row">' +
        '<span><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' + t('lbl_ended_date') + '</span>' +
        '<b>' + escHtml(dateStr) + '</b>' +
      '</div>' +
      '<div class="past-modal-info-row">' +
        '<span>' + t('lbl_start_time') + '</span>' +
        '<b>' + escHtml(startStr) + '</b>' +
      '</div>' +
      '<div class="past-modal-info-row">' +
        '<span>' + t('lbl_ended_time') + '</span>' +
        '<b>' + escHtml(endStr) + '</b>' +
      '</div>' +
      '<div class="past-modal-info-row">' +
        '<span><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' + t('lbl_questions_count') + '</span>' +
        '<b>' + (test.total_questions || 45) + ' ta savol</b>' +
      '</div>' +
      '<div class="past-modal-summary-text">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>' + summaryNotice +
      '</div>' +
    '</div>' +

    userStatusHtml +
    ytHtml +
    actionBtnHtml +

    '<button type="button" class="past-modal-close-btn" onclick="closePastTestModal()">' +
      t('btn_modal_understand') +
    '</button>';

  modal.style.display = 'flex';
}

function closePastTestModal(e) {
  if (e && e.target && e.target.id !== 'past-test-modal') return;
  var modal = document.getElementById('past-test-modal');
  if (modal) modal.style.display = 'none';
}

// ── HOME TAB (Faol va Oldingi testlar - 2 ta bo'lim) ─
function renderHomeTab(tests) {
  var tab = document.getElementById('tab-home');
  if (!tab) return;
  window.availableActiveTests = tests || [];
  var currentSubtab = state.homeSubtab || 'active';

  var upcoming = tests.filter(function(t) { return isTestUpcoming(t); });
  var active = tests.filter(function(t) { return t.is_active && !isTestUpcoming(t); });
  var inactive = tests.filter(function(t) { return !t.is_active && !isTestUpcoming(t); });

  var activeTotalCount = active.length + upcoming.length;
  var pastTotalCount = inactive.length;

  var html = '<div class="section-header animate-in">' +
    '<div class="section-title">' + t('home_title') + '</div>' +
    '<div class="section-sub">' + t('home_sub') + '</div></div>';

  // ── SUBTABS (2 ta bo'lim: Faol va Oldingi) ──
  var boltIcon = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" fill="currentColor"/></svg>';
  var archiveIcon = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';

  html += '<div class="home-subtabs animate-in">' +
    '<button type="button" class="home-subtab ' + (currentSubtab === 'active' ? 'active' : '') + '" onclick="switchHomeSubtab(\'active\')">' +
      '<span class="home-subtab-icon">' + boltIcon + '</span>' +
      '<span class="home-subtab-text">' + t('subtab_active') + '</span>' +
      '<span class="home-subtab-badge">' + activeTotalCount + '</span>' +
    '</button>' +
    '<button type="button" class="home-subtab ' + (currentSubtab === 'past' ? 'active' : '') + '" onclick="switchHomeSubtab(\'past\')">' +
      '<span class="home-subtab-icon">' + archiveIcon + '</span>' +
      '<span class="home-subtab-text">' + t('subtab_past') + '</span>' +
      '<span class="home-subtab-badge">' + pastTotalCount + '</span>' +
    '</button>' +
  '</div>';

  // ── SUBTAB MAZMUNI ──
  html += '<div class="home-subtab-content animate-in">';

  if (currentSubtab === 'active') {
    // 1. Kutilayotgan testlar (Upcoming)
    if (upcoming.length > 0) {
      html += '<div class="section-sub" style="margin-bottom:12px;font-weight:800;color:#D97706;font-size:13px;display:flex;align-items:center;gap:6px;">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> ' + t('upcoming_tests') + ' (' + upcoming.length + ' ' + t('unit_count') + '):' +
      '</div>';
      upcoming.forEach(function(test) {
        html += renderTestDetailCard(test, 'upcoming');
      });
    }

    // 2. Faol testlar (Active)
    if (active.length > 0) {
      if (upcoming.length > 0) {
        html += '<div class="section-sub" style="margin:16px 0 12px;font-weight:800;color:var(--success);font-size:13px;display:flex;align-items:center;gap:6px;">' +
          '<span class="status-dot dot-active" style="display:inline-block;margin-right:2px;"></span> ' + t('active_tests_now') + ' (' + active.length + ' ' + t('unit_count') + '):' +
        '</div>';
      }
      active.forEach(function(test) {
        html += renderTestDetailCard(test, 'active');
      });
    }

    // Bo'sh holat
    if (activeTotalCount === 0) {
      html += '<div class="empty-state animate-in" style="padding:44px 16px;">' +
        '<div class="empty-icon" style="margin-bottom:12px;"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg></div>' +
        '<div style="font-weight:800;font-size:16px;margin-bottom:6px;color:var(--text)">' + t('empty_active') + '</div>' +
        '<p style="font-size:13px;color:var(--text-muted);margin:0;max-width:280px;line-height:1.5;">' + t('empty_active_sub') + '</p>' +
      '</div>';
    }
  } else {
    // 3. Oldingi / Muddati tugagan testlar (Closed)
    if (inactive.length > 0) {
      inactive.forEach(function(test) {
        html += renderTestDetailCard(test, 'inactive');
      });
    } else {
      html += '<div class="empty-state animate-in" style="padding:44px 16px;">' +
        '<div class="empty-icon" style="margin-bottom:12px;"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></div>' +
        '<div style="font-weight:800;font-size:16px;margin-bottom:6px;color:var(--text)">' + t('empty_past') + '</div>' +
        '<p style="font-size:13px;color:var(--text-muted);margin:0;max-width:280px;line-height:1.5;">' + t('empty_past_sub') + '</p>' +
      '</div>';
    }
  }

  html += '</div>';

  tab.innerHTML = html;
}

// Har 15 soniyada rejalashtirilgan testlar vaqtini tekshirib, boshlanish vaqti kelganda avtomatik ochish
setInterval(function() {
  if (state.activeTab === 'home') {
    var hasUpcoming = window.availableActiveTests && window.availableActiveTests.some(function(t) { return isTestUpcoming(t); });
    if (hasUpcoming) {
      loadActiveTests();
    } else if (window.availableActiveTests && window.availableActiveTests.length > 0) {
      renderHomeTab(window.availableActiveTests);
    }
  }
}, 15000);

// ── TESTS TAB (Boyitilgan Natijalar & Sertifikat Markazi) ──
var _myTestsFilter = 'all';

function filterMyTests(filterType) {
  _myTestsFilter = filterType;
  if (window._myResults) {
    renderTestsTab(window._myResults);
  } else {
    loadMyResults();
  }
}

function renderTestsTab(results) {
  var tab = document.getElementById('tab-tests');
  if (!tab) return;
  window._myResults = results || [];

  if (!results || results.length === 0) {
    tab.innerHTML =
      '<div class="section-header animate-in">' +
        '<div class="section-title">' + t('my_tests_title') + '</div>' +
        '<div class="section-sub">0 ' + t('tests_count') + '</div>' +
      '</div>' +
      '<div class="empty-tests-hero animate-in">' +
        '<div class="empty-tests-icon"><svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg></div>' +
        '<h3 class="empty-tests-title">' + t('tests_empty_title') + '</h3>' +
        '<p class="empty-tests-desc">' + t('tests_empty_desc') + '</p>' +
        '<button type="button" class="empty-tests-btn" onclick="switchTab(\'home\')">' +
          '<span>' + t('tests_empty_btn') + '</span>' +
        '</button>' +
      '</div>';
    return;
  }

  // Calculate statistics across published results
  var publishedList = results.filter(function(r) { return Boolean(r.results_published); });
  var totalCompleted = publishedList.length;
  var sumScore = 0;
  var maxScoreVal = 0;
  var totalCorrect = 0;
  var totalQ = 0;

  publishedList.forEach(function(r) {
    var sc = Number(r.score != null ? r.score : 0);
    sumScore += sc;
    if (sc > maxScoreVal) maxScoreVal = sc;
    totalCorrect += Number(r.correct_count || 0);
    totalQ += Number(r.total_count || 45);
  });

  var avgScore = totalCompleted > 0 ? (sumScore / totalCompleted).toFixed(1) : '0.0';
  var accuracyPct = totalQ > 0 ? Math.min(100, Math.round((totalCorrect / totalQ) * 100)) : 0;

  // National certificate level based on average score
  var numAvg = parseFloat(avgScore);
  var certLevel = 'A+ Daraja';
  var certClass = 'cert-a';
  if (numAvg >= 75) {
    certLevel = 'A+ Daraja';
    certClass = 'cert-a';
  } else if (numAvg >= 70) {
    certLevel = 'A Daraja';
    certClass = 'cert-a';
  } else if (numAvg >= 65) {
    certLevel = 'B+ Daraja';
    certClass = 'cert-b';
  } else if (numAvg >= 60) {
    certLevel = 'B Daraja';
    certClass = 'cert-b';
  } else if (numAvg >= 50) {
    certLevel = 'C Daraja';
    certClass = 'cert-c';
  } else if (totalCompleted === 0) {
    certLevel = t('test_waiting_result');
    certClass = 'cert-c';
  } else {
    certLevel = 'Boshlang\'ich';
    certClass = 'cert-c';
  }

  var html =
    '<div class="section-header animate-in">' +
      '<div class="section-title">' + t('my_tests_title') + '</div>' +
      '<div class="section-sub">' + results.length + ' ' + t('tests_count') + '</div>' +
    '</div>' +

    // Top Summary Hero Card
    '<div class="tests-hero-card animate-in">' +
      '<div class="tests-hero-top">' +
        '<div class="tests-hero-badge">' +
          '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px;"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg><span>' + t('tests_hero_title') + '</span>' +
        '</div>' +
        '<div class="tests-cert-chip ' + certClass + '">' +
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none" style="display:inline-block;vertical-align:-1px;margin-right:3px;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>' + certLevel +
        '</div>' +
      '</div>' +
      '<div class="tests-hero-stats">' +
        '<div class="tests-stat-box">' +
          '<div class="tests-stat-val">' + results.length + '</div>' +
          '<div class="tests-stat-lbl">' + t('stat_tests') + '</div>' +
        '</div>' +
        '<div class="tests-stat-box">' +
          '<div class="tests-stat-val" style="color:var(--primary,#3b82f6);">' + avgScore + '</div>' +
          '<div class="tests-stat-lbl">' + t('stat_avg') + ' (' + t('test_score_unit') + ')</div>' +
        '</div>' +
        '<div class="tests-stat-box">' +
          '<div class="tests-stat-val" style="color:#10b981;">' + maxScoreVal + '</div>' +
          '<div class="tests-stat-lbl">' + t('stat_max') + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="tests-progress-wrap">' +
        '<div class="tests-progress-header">' +
          '<span>' + t('tests_accuracy') + '</span>' +
          '<span style="font-weight:800;color:var(--text);">' + accuracyPct + '%</span>' +
        '</div>' +
        '<div class="tests-progress-bar">' +
          '<div class="tests-progress-fill" style="width:' + accuracyPct + '%;"></div>' +
        '</div>' +
      '</div>' +
    '</div>' +

    // Filter Chips
    '<div class="tests-filter-bar animate-in">' +
      '<button type="button" class="tests-filter-chip ' + (_myTestsFilter === 'all' ? 'active' : '') + '" onclick="filterMyTests(\'all\')">' + t('tests_filter_all') + ' (' + results.length + ')</button>' +
      '<button type="button" class="tests-filter-chip ' + (_myTestsFilter === 'top' ? 'active' : '') + '" onclick="filterMyTests(\'top\')">' + t('tests_filter_top') + '</button>' +
      '<button type="button" class="tests-filter-chip ' + (_myTestsFilter === 'good' ? 'active' : '') + '" onclick="filterMyTests(\'good\')">' + t('tests_filter_good') + '</button>' +
      '<button type="button" class="tests-filter-chip ' + (_myTestsFilter === 'checking' ? 'active' : '') + '" onclick="filterMyTests(\'checking\')">' + t('tests_filter_checking') + '</button>' +
    '</div>';

  // Apply Filter
  var filtered = results.filter(function(r) {
    var isPub = Boolean(r.results_published);
    var maxScore = r.max_score || 100;
    var score = Number(r.score != null ? r.score : 0);
    var grade = r.grade || getGradeFromScore(score, maxScore);

    if (_myTestsFilter === 'top') return isPub && (grade === 'A+' || grade === 'A' || grade === '5');
    if (_myTestsFilter === 'good') return isPub && (grade === 'B+' || grade === 'B' || grade === '4');
    if (_myTestsFilter === 'checking') return !isPub;
    return true;
  });

  if (filtered.length === 0) {
    html += '<div class="empty-state animate-in"><div class="empty-icon"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div><p>' + t('admin_no_match') + '</p></div>';
  } else {
    filtered.forEach(function(r, idx) {
      var origIndex = results.indexOf(r);
      var isPub = Boolean(r.results_published);
      var maxScore = r.max_score || 100;
      var date = formatDate(r.submitted_at);
      var totalQues = r.total_count || 45;
      var correct = r.correct_count || 0;
      var incorrect = r.incorrect_count != null ? r.incorrect_count : Math.max(0, totalQues - correct);

      var isRejected = Boolean(r.is_rejected || r.status === 'rejected');
      if (isRejected) {
        html +=
          '<div class="test-card-modern animate-in" style="animation-delay:' + (idx * 0.04) + 's;border:1.5px solid rgba(239,68,68,0.45);background:rgba(239,68,68,0.04);" onclick="showResultModal(window._myResults[' + origIndex + '])">' +
            '<div class="test-card-top-row">' +
              '<div class="test-card-title">' + escHtml(r.test_title || r.title || t('default_test_title')) + '</div>' +
              '<div class="test-card-date"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' + date + '</div>' +
            '</div>' +
            '<div class="test-card-middle-row">' +
              '<div class="test-score-box" style="background:rgba(239,68,68,0.15);border:1.5px solid #EF4444;color:#EF4444;display:flex;align-items:center;justify-content:center;flex-direction:column;">' +
                '<span class="test-score-num" style="display:flex;align-items:center;justify-content:center;color:#EF4444;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span>' +
                '<span class="test-score-rank" style="font-size:9.5px;color:#EF4444;">' + (t('badge_cancelled') || 'Bekor') + '</span>' +
              '</div>' +
              '<div class="test-metrics-grid">' +
                '<span class="test-metric-tag" style="color:#EF4444;font-weight:800;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>Test bekor qilingan</span>' +
                '<span class="test-metric-tag" style="color:var(--text-muted);">Natija qabul qilinmagan</span>' +
              '</div>' +
            '</div>' +
            '<div class="test-card-bottom-row">' +
              '<button type="button" class="btn-test-action-quick" style="color:#EF4444;">' +
                '<span><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:3px"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>' + t('tests_card_btn_analysis') + '</span>' +
              '</button>' +
              '<span style="color:var(--text-muted);display:flex;align-items:center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
            '</div>' +
          '</div>';
      } else if (isPub) {
        var score = Number(r.score != null ? r.score : 0);
        var grade = r.grade || getGradeFromScore(score, maxScore);
        var gradeClass = 'good';
        var borderClass = 'grade-good';
        if (grade === 'A+' || grade === 'A' || grade === '5') {
          gradeClass = 'top';
          borderClass = 'grade-top';
        } else if (grade === 'C' || grade === '3' || grade === '2') {
          gradeClass = 'pass';
          borderClass = 'grade-pass';
        }

        var pct = totalQues > 0 ? Math.min(100, Math.round((correct / totalQues) * 100)) : 0;

        html +=
          '<div class="test-card-modern ' + borderClass + ' animate-in" style="animation-delay:' + (idx * 0.04) + 's;" onclick="showResultModal(window._myResults[' + origIndex + '])">' +
            '<div class="test-card-top-row">' +
              '<div class="test-card-title">' + escHtml(r.test_title || r.title || t('default_test_title')) + '</div>' +
              '<div class="test-card-date"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' + date + '</div>' +
            '</div>' +
            '<div class="test-card-middle-row">' +
              '<div class="test-score-box ' + gradeClass + '">' +
                '<span class="test-score-num">' + score + '</span>' +
                '<span class="test-score-rank">' + grade + '</span>' +
              '</div>' +
              '<div class="test-metrics-grid">' +
                '<span class="test-metric-tag" style="color:#10b981;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="display:inline-block;vertical-align:-1px;margin-right:2px"><polyline points="20 6 9 17 4 12"/></svg>' + correct + ' ' + t('tests_stat_correct') + '</span>' +
                '<span class="test-metric-tag" style="color:#ef4444;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="display:inline-block;vertical-align:-1px;margin-right:2px"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' + incorrect + ' ' + t('tests_stat_incorrect') + '</span>' +
                '<span class="test-metric-tag" style="color:var(--primary,#3b82f6);"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" style="display:inline-block;vertical-align:-1px;margin-right:2px"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>' + pct + '% ' + t('tests_stat_efficiency') + '</span>' +
              '</div>' +
            '</div>' +
            '<div class="test-card-bottom-row">' +
              '<button type="button" class="btn-test-action-quick">' +
                '<span><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:3px"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' + t('tests_card_btn_analysis') + '</span>' +
              '</button>' +
              '<span style="color:var(--text-muted);display:flex;align-items:center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
            '</div>' +
          '</div>';
      } else {
        html +=
          '<div class="test-card-modern grade-pending animate-in" style="animation-delay:' + (idx * 0.04) + 's;" onclick="showResultModal(window._myResults[' + origIndex + '])">' +
            '<div class="test-card-top-row">' +
              '<div class="test-card-title">' + escHtml(r.test_title || r.title || t('default_test_title')) + '</div>' +
              '<div class="test-card-date"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' + date + '</div>' +
            '</div>' +
            '<div class="test-card-middle-row">' +
              '<div class="test-score-box pending">' +
                '<span style="display:flex;align-items:center;justify-content:center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></span>' +
                '<span class="test-score-rank" style="font-size:10px;">' + t('test_waiting_result') + '</span>' +
              '</div>' +
              '<div class="test-metrics-grid">' +
                '<span class="test-metric-tag" style="color:#f59e0b;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' + t('test_in_progress') + '</span>' +
              '</div>' +
            '</div>' +
            '<div class="test-card-bottom-row">' +
              '<button type="button" class="btn-test-action-quick" style="color:#f59e0b;">' +
                '<span>' + t('btn_view_result') + '</span>' +
              '</button>' +
              '<span style="color:var(--text-muted);display:flex;align-items:center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
            '</div>' +
          '</div>';
      }
    });
  }

  tab.innerHTML = html;
}

// ── PROFILE TAB ─────────────────────────────────
// ── PROFILE TAB (Real Mobile App Design) ────────
function renderProfileTab() {
  var tab = document.getElementById('tab-profile');
  if (!tab) return;
  var u = state.userInfo;
  var tgU = state.tgUser;

  // Ismni to'g'ri proporsiya va bosh harflar bilan formatlash
  var rawFullname = (u && u.fullname) || ((tgU && ((tgU.first_name || '') + ' ' + (tgU.last_name || '')).trim())) || t('default_user');
  var fullname = rawFullname.split(' ').map(function(w) {
    if (!w) return '';
    return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
  }).join(' ');

  // Telefon raqamini chiroyli ajratib ko'rsatish (+998 97 027 87 70)
  var rawPhone = (u && u.phone) || '';
  var formattedPhone = rawPhone;
  var digits = rawPhone.replace(/\D/g, '');
  if (digits.length === 12 && digits.startsWith('998')) {
    formattedPhone = '+' + digits.slice(0, 3) + ' ' + digits.slice(3, 5) + ' ' + digits.slice(5, 8) + ' ' + digits.slice(8, 10) + ' ' + digits.slice(10, 12);
  } else if (!rawPhone) {
    formattedPhone = t('val_not_linked');
  }

  var username = (tgU && tgU.username) ? ('@' + tgU.username) : ((u && u.username) ? ('@' + u.username) : t('val_none'));
  var tgId = (tgU && tgU.id) || (u && u.tg_id) || 0;
  var testsCount = (u && u.tests_count) || 0;
  var avgScore = (u && u.avg_score) ? (Number(u.avg_score).toFixed(1)) : '0.0';
  var maxScore = (u && u.max_score) ? (Number(u.max_score).toFixed(1)) : '0.0';
  var avatarLetter = fullname.charAt(0).toUpperCase() || 'U';

  var regDateStr = (u && u.registered_at) ? formatDate(u.registered_at) : t('val_recent');

  var st = (u && u.status || 'pending').toLowerCase();
  var isAdmin = Boolean(state.isAdmin);

  var statusChipHtml = '';
  var avatarBadgeClass = 'approved';

  if (st === 'approved') {
    statusChipHtml = '<span class="profile-chip chip-approved"><span class="chip-dot dot-approved"></span> ' + t('profile_status_approved') + '</span>';
    avatarBadgeClass = 'approved';
  } else if (st === 'pending') {
    statusChipHtml = '<span class="profile-chip chip-pending"><span class="chip-dot dot-pending"></span> ' + t('profile_status_pending') + '</span>';
    avatarBadgeClass = 'pending';
  } else {
    statusChipHtml = '<span class="profile-chip chip-rejected"><span class="chip-dot dot-rejected"></span> ' + t('profile_status_blocked') + '</span>';
    avatarBadgeClass = 'blocked';
  }

  var adminChipHtml = isAdmin ? ('<span class="profile-chip chip-admin">' + t('profile_status_admin') + '</span>') : '';

  var avatarInnerHtml = '';
  if (tgU && tgU.photo_url) {
    avatarInnerHtml = '<img src="' + escHtml(tgU.photo_url) + '" class="profile-avatar-img" alt="Avatar" onerror="this.onerror=null;this.parentElement.innerHTML=\'' + avatarLetter + '\';">';
  } else {
    avatarInnerHtml = avatarLetter;
  }

  var curTheme = document.documentElement.getAttribute('data-theme') || 'light';
  var themeLabel = curTheme === 'dark' ? t('theme_dark_lbl') : t('theme_light_lbl');

  var isActualAdmin = Boolean(state.isActualAdmin || state.isAdmin || state.isSimulatedUser);
  var simSwitchHtml = '';
  if (isActualAdmin) {
    if (!state.isSimulatedUser) {
      simSwitchHtml =
        '<div class="admin-simulation-switch-card animate-in">' +
          '<div class="sim-switch-body">' +
            '<div class="sim-switch-badge"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>ADMIN BOSHQARUVI</div>' +
            '<div class="sim-switch-title">O\'quvchi sifatida kirish (User Mode)</div>' +
            '<div class="sim-switch-desc">Mini ilova oddiy o\'quvchida qanday ko\'rinishi va ishlashini o\'z ko\'zingiz bilan ko\'rib sinash uchun o\'quvchi rejimiga o\'ting.</div>' +
          '</div>' +
          '<button type="button" class="btn-switch-to-user" onclick="toggleUserSimulationMode(true)">' +
            '<span><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>User sifatida kirish</span>' +
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>' +
          '</button>' +
        '</div>';
    } else {
      simSwitchHtml =
        '<div class="admin-simulation-switch-card simulated animate-in">' +
          '<div class="sim-switch-body">' +
            '<div class="sim-switch-badge simulated"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>O\'QUVCHI REJIMI FAOL</div>' +
            '<div class="sim-switch-title">Siz hozir o\'quvchi rejimidasiz</div>' +
            '<div class="sim-switch-desc">Barcha ekranlar, qidiruv va testlar oddiy o\'quvchi sifatida ishlamoqda. Admin boshqaruviga qaytish uchun tugmani bosing.</div>' +
          '</div>' +
          '<button type="button" class="btn-switch-to-admin" onclick="toggleUserSimulationMode(false)">' +
            '<span><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>Admin boshqaruviga qaytish</span>' +
          '</button>' +
        '</div>';
    }
  }

  tab.innerHTML =
    // ── 1. HERO PROFILE CARD (Ixcham, toza va to'g'ri o'lchamdagi ism) ──
    '<div class="profile-hero-card animate-in">' +
      '<div class="profile-avatar-box">' +
        '<div class="profile-avatar-circle">' + avatarInnerHtml + '</div>' +
        '<span class="profile-avatar-badge ' + avatarBadgeClass + '"></span>' +
      '</div>' +
      '<div class="profile-name-title">' + escHtml(fullname) + '</div>' +
      '<div class="profile-phone-subtitle">' + escHtml(formattedPhone) + '</div>' +
      '<div class="profile-tag-row">' +
        adminChipHtml +
        statusChipHtml +
      '</div>' +
      '<div style="display:flex;justify-content:center;margin-top:10px;">' +
        '<button type="button" class="btn-hero-profile-action btn-edit-profile-hero" onclick="openEditProfileModal()" style="max-width:170px;">' +
          '<span class="hero-btn-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></span><span>' + t('profile_edit_btn') + '</span>' +
        '</button>' +
      '</div>' +
    '</div>' +

    // ── 1.5. ADMIN USER SIMULATION SWITCH (Agar Admin bo'lsa) ──
    simSwitchHtml +

    // ── 2. METRIKALAR PANELCHASI (3 ta ustunli qulay va ixcham lenta) ──
    '<div class="profile-stats-ribbon animate-in">' +
      '<div class="stat-ribbon-item">' +
        '<div class="stat-ribbon-val">' + testsCount + ' <span style="font-size:11px;font-weight:600;opacity:0.8;">' + t('unit_count') + '</span></div>' +
        '<div class="stat-ribbon-lbl">' + t('stat_tests') + '</div>' +
      '</div>' +
      '<div class="stat-ribbon-divider"></div>' +
      '<div class="stat-ribbon-item">' +
        '<div class="stat-ribbon-val">' + avgScore + '</div>' +
        '<div class="stat-ribbon-lbl">' + t('stat_avg') + '</div>' +
      '</div>' +
      '<div class="stat-ribbon-divider"></div>' +
      '<div class="stat-ribbon-item">' +
        '<div class="stat-ribbon-val">' + maxScore + '</div>' +
        '<div class="stat-ribbon-lbl">' + t('stat_max') + '</div>' +
      '</div>' +
    '</div>' +

    // ── 3. SHAXSIY MA'LUMOTLAR BO'LIMI (Ko'rsatish / Yashirish) ──
    '<div class="profile-section-card animate-in" id="profile-info-section" style="margin-top:12px;">' +
      '<div class="profile-info-toggle-header" onclick="toggleProfileDetails()">' +
        '<div style="display:flex;align-items:center;gap:12px;min-width:0;">' +
          '<div class="profile-item-icon" style="background:rgba(59,130,246,0.12);color:var(--accent,#3b82f6);width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">' +
            '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
              '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>' +
              '<circle cx="12" cy="7" r="4"></circle>' +
            '</svg>' +
          '</div>' +
          '<div style="flex:1;min-width:0;">' +
            '<div style="margin:0;font-size:14px;font-weight:700;color:var(--text);letter-spacing:0.2px;">' + t('profile_personal_info') + '</div>' +
          '</div>' +
        '</div>' +
        '<span class="profile-info-toggle-badge" id="profile-info-toggle-badge" style="padding:6px 13px;border-radius:16px;font-size:12px;font-weight:700;background:rgba(59,130,246,0.12);color:var(--accent,#3b82f6);transition:all 0.2s ease;flex-shrink:0;margin-left:8px;">' + (window._profileDetailsOpen ? t('toggle_hide') : t('toggle_show')) + '</span>' +
      '</div>' +
      '<div id="profile-details-content" style="display:' + (window._profileDetailsOpen ? 'block' : 'none') + ';border-top:1px solid var(--border);">' +
        '<div class="profile-item-row clickable" onclick="copyTextToClipboard(\'' + tgId + '\', \'' + t('toast_copied') + '\')">' +
          '<div class="profile-item-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><line x1="15" y1="8" x2="17" y2="8"/><line x1="15" y1="12" x2="17" y2="12"/><line x1="7" y1="16" x2="17" y2="16"/></svg></div>' +
          '<div class="profile-item-body">' +
            '<div class="profile-item-label">' + t('lbl_tg_id') + '</div>' +
            '<div class="profile-item-value"><code>' + tgId + '</code></div>' +
          '</div>' +
          '<span class="profile-item-action-chip"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>' + t('btn_copy') + '</span>' +
        '</div>' +
        '<div class="profile-item-row clickable" onclick="copyTextToClipboard(\'' + escHtml(username) + '\', \'' + t('toast_copied') + '\')">' +
          '<div class="profile-item-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg></div>' +
          '<div class="profile-item-body">' +
            '<div class="profile-item-label">' + t('lbl_username') + '</div>' +
            '<div class="profile-item-value">' + escHtml(username) + '</div>' +
          '</div>' +
          '<span class="profile-item-action-chip"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>' + t('btn_copy') + '</span>' +
        '</div>' +
        '<div class="profile-item-row clickable" onclick="openEditProfileModal()">' +
          '<div class="profile-item-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg></div>' +
          '<div class="profile-item-body">' +
            '<div class="profile-item-label">' + t('lbl_phone_edit') + '</div>' +
            '<div class="profile-item-value">' + escHtml(formattedPhone) + '</div>' +
          '</div>' +
          '<span class="profile-item-action-chip"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>' + t('profile_edit_btn') + '</span>' +
        '</div>' +
        '<div class="profile-item-row" style="border-bottom:none;">' +
          '<div class="profile-item-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>' +
          '<div class="profile-item-body">' +
            '<div class="profile-item-label">' + t('lbl_reg_date') + '</div>' +
            '<div class="profile-item-value">' + regDateStr + '</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>' +

    // ── 4. SOZLAMALAR VA QO'LLANMA ──
    '<div class="profile-section-card animate-in" style="margin-top:10px;">' +
      '<div class="profile-section-title">' + t('sec_settings_guide') + '</div>' +
      '<div class="profile-item-row clickable" onclick="toggleTheme(event)">' +
        '<div class="profile-item-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 0 0 20z" fill="currentColor"/></svg></div>' +
        '<div class="profile-item-body">' +
          '<div class="profile-item-label">' + t('lbl_app_theme') + '</div>' +
          '<div class="profile-item-value" id="profile-theme-label">' + themeLabel + '</div>' +
        '</div>' +
        '<span class="profile-item-arrow"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
      '</div>' +
      '<div class="profile-item-row clickable" onclick="openOnboardingModal()" style="border-bottom:none;">' +
        '<div class="profile-item-icon" style="background:rgba(59,130,246,0.12);color:#2563eb;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg></div>' +
        '<div class="profile-item-body">' +
          '<div class="profile-item-label">' + t('lbl_how_it_works') + '</div>' +
          '<div class="profile-item-value" style="font-size:12px;color:var(--text-muted);font-weight:600;">' + t('sub_how_it_works') + '</div>' +
        '</div>' +
        '<span class="profile-item-arrow"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
      '</div>' +
    '</div>' +

    // ── 5. XAVFLI HUDUD (Akkauntni butunlay o'chirish) ──
    '<div class="profile-danger-card animate-in">' +
      '<div class="danger-card-title">' + t('sec_danger_zone') + '</div>' +
      '<div class="danger-card-desc">' + t('desc_danger_zone') + '</div>' +
      '<button type="button" class="btn-delete-account" onclick="deleteMyAccount()">' +
        '<span>' + t('btn_delete_account') + '</span>' +
      '</button>' +
    '</div>';
}

function toggleProfileDetails() {
  window._profileDetailsOpen = !window._profileDetailsOpen;
  var content = document.getElementById('profile-details-content');
  var badge = document.getElementById('profile-info-toggle-badge');
  if (content) {
    content.style.display = window._profileDetailsOpen ? 'block' : 'none';
    if (window._profileDetailsOpen) {
      setTimeout(function() {
        var sec = document.getElementById('profile-info-section');
        if (sec) sec.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    }
  }
  if (badge) {
    badge.textContent = window._profileDetailsOpen ? t('toggle_hide') : t('toggle_show');
  }
  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    try { window.Telegram.WebApp.HapticFeedback.selectionChanged(); } catch(e) {}
  }
}

function openEditProfileModal() {
  var u = state.userInfo;
  var tgU = state.tgUser;
  var fullname = (u && u.fullname) || ((tgU && ((tgU.first_name || '') + ' ' + (tgU.last_name || '')).trim())) || '';
  var phone = (u && u.phone) || '';

  var modal = document.getElementById('edit-profile-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'edit-profile-modal';
    modal.className = 'modal-overlay';
    modal.style.cssText = 'display:none;position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.7);align-items:center;justify-content:center;backdrop-filter:blur(6px);padding:16px;';
    modal.onclick = function(e) { if (e.target === modal || e.target.classList.contains('modal-close')) closeEditProfileModal(); };
    modal.innerHTML =
      '<div class="modal-box" style="max-width:380px;width:100%;padding:22px 18px;border-radius:24px;background:var(--bg-card,#1e293b);border:1px solid var(--border);box-shadow:0 24px 60px rgba(0,0,0,0.5);">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">' +
          '<div style="font-size:16px;font-weight:800;color:var(--text);">' + t('modal_edit_title') + '</div>' +
          '<button class="modal-close" onclick="closeEditProfileModal()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;padding:4px;display:flex;align-items:center;justify-content:center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>' +
        '</div>' +
        '<div style="margin-bottom:12px;">' +
          '<label style="display:block;font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;">' + t('lbl_fullname') + '</label>' +
          '<input type="text" id="edit-profile-name" class="modal-input" placeholder="' + t('placeholder_fullname') + '" style="width:100%;padding:11px 14px;border-radius:12px;background:var(--bg-glass-2);border:1px solid var(--border);color:var(--text);font-family:var(--font);font-size:14px;outline:none;">' +
        '</div>' +
        '<div style="margin-bottom:18px;">' +
          '<label style="display:block;font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;">' + t('lbl_phone') + '</label>' +
          '<input type="tel" id="edit-profile-phone" class="modal-input" placeholder="' + t('placeholder_phone') + '" style="width:100%;padding:11px 14px;border-radius:12px;background:var(--bg-glass-2);border:1px solid var(--border);color:var(--text);font-family:var(--font);font-size:14px;outline:none;">' +
        '</div>' +
        '<div style="display:flex;gap:8px;">' +
          '<button type="button" onclick="closeEditProfileModal()" style="flex:1;padding:12px;border-radius:12px;background:transparent;border:1px solid var(--border);color:var(--text-muted);font-weight:700;cursor:pointer;">' + t('btn_cancel') + '</button>' +
          '<button type="button" id="btn-save-profile" onclick="saveEditedProfile()" style="flex:1.5;padding:12px;border-radius:12px;background:linear-gradient(135deg,#2563EB,#1D4ED8);border:none;color:#fff;font-weight:800;cursor:pointer;box-shadow:0 4px 14px rgba(37,99,235,0.35);">' + t('btn_save') + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(modal);
  }

  var nameInput = document.getElementById('edit-profile-name');
  var phoneInput = document.getElementById('edit-profile-phone');
  if (nameInput) nameInput.value = fullname;
  if (phoneInput) phoneInput.value = phone;

  modal.style.display = 'flex';
}

function closeEditProfileModal() {
  var modal = document.getElementById('edit-profile-modal');
  if (modal) modal.style.display = 'none';
}

async function saveEditedProfile() {
  var nameInput = document.getElementById('edit-profile-name');
  var phoneInput = document.getElementById('edit-profile-phone');
  if (!nameInput || !phoneInput) return;

  var newName = (nameInput.value || '').trim();
  var newPhone = (phoneInput.value || '').trim();

  if (!newName) {
    alert(t('alert_enter_name'));
    nameInput.focus();
    return;
  }
  if (!newPhone) {
    alert(t('alert_enter_phone'));
    phoneInput.focus();
    return;
  }

  var btn = document.getElementById('btn-save-profile');
  if (btn) {
    btn.disabled = true;
    btn.textContent = t('btn_saving');
  }

  var tgId = (state.tgUser && state.tgUser.id) || (state.userInfo && state.userInfo.tg_id) || 0;

  try {
    var res = await fetch('/api/app/update-profile', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        tg_id: tgId,
        fullname: newName,
        phone: newPhone,
        init_data: (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''
      })
    });
    var data = await res.json();
    if (data.success) {
      if (!state.userInfo) state.userInfo = {};
      state.userInfo.fullname = newName;
      state.userInfo.phone = newPhone;
      localStorage.setItem(LS_USER, JSON.stringify(state.userInfo));
      closeEditProfileModal();
      renderProfileTab();
      showToast(t('toast_profile_saved'));
      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
        try { window.Telegram.WebApp.HapticFeedback.notificationOccurred('success'); } catch(e) {}
      }
    } else {
      alert((t('error_occurred') + ': ') + (data.message || ''));
    }
  } catch(e) {
    alert(t('err_network') + ' ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = t('btn_save');
    }
  }
}

async function deleteMyAccount() {
  if (!confirm(t('confirm_delete_account'))) {
    return;
  }
  var tgId = (state.tgUser && state.tgUser.id) || (state.userInfo && state.userInfo.tg_id) || 0;
  if (!tgId) return;

  try {
    var res = await fetch('/api/app/delete-my-account', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        tg_id: tgId,
        init_data: (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''
      })
    });
    var data = await res.json();
    if (data.success) {
      alert(t('alert_account_deleted'));
      localStorage.removeItem(LS_USER);
      localStorage.removeItem('pin_code');
      window.location.reload();
    } else {
      alert((t('error_occurred') + ': ') + (data.message || ''));
    }
  } catch(e) {
    alert(t('err_network') + ' ' + e.message);
  }
}

// ── ADMIN TAB ───────────────────────────────────
var ADMIN_QUICK_TEMPLATES_I18N = {
  uz: {
    '30m': "Diqqat! Test boshlanishiga 30 daqiqa qoldi! Internet aloqangizni tekshirib, qoralama qog'ozlarni tayyorlab oling.",
    '10m': "Test boshlanishiga 10 daqiqa qoldi! Mini ilovaga kirib, tayyor bo'lib turing.",
    'started': "Test boshlandi! Barchaga omad tilaymiz. Belgilangan vaqt ichida javoblarni topshirishni unutmang.",
    '15m': "Diqqat, test yakunlanishiga 15 daqiqa qoldi! Qolgan javoblarni tekshirib, topshirishga shoshiling.",
    'ended': "Test yakunlandi! Javoblarni qabul qilish to'xtatildi. Ishtirok etgan barcha o'quvchilarga minnatdorchilik bildiramiz. Tez orada to'liq tahlil va rasmiy natijalar e'lon qilinadi."
  },
  ru: {
    '30m': "Внимание! До начала теста осталось 30 минут! Проверьте подключение к интернету и приготовьте черновики.",
    '10m': "До начала теста осталось 10 минут! Войдите в приложение и будьте готовы.",
    'started': "Тест начался! Желаем всем удачи. Не забудьте отправить ответы в установленное время.",
    '15m': "Внимание, до окончания теста осталось 15 минут! Проверьте оставшиеся ответы и поторопитесь со сдачей.",
    'ended': "Тест завершен! Прием ответов остановлен. Благодарим всех участников. Скоро будут опубликованы полный разбор и официальные результаты."
  },
  en: {
    '30m': "Attention! 30 minutes left before the test starts! Check your internet connection and prepare draft papers.",
    '10m': "10 minutes left before the test starts! Open the mini app and be ready.",
    'started': "The test has started! Good luck to everyone. Remember to submit your answers within the allotted time.",
    '15m': "Attention, 15 minutes left before the test ends! Double-check your answers and hurry to submit.",
    'ended': "The test has ended! Answer submission is closed. Thank you to all participants. Full analysis and official results will be announced shortly."
  }
};

function getActiveOrPlannedTestCode() {
  var tests = window.availableActiveTests || [];
  var active = tests.find(function(t) { return t.is_active; });
  if (active && active.test_code) return String(active.test_code).trim();
  if (tests.length > 0 && tests[0].test_code) return String(tests[0].test_code).trim();
  return '';
}

function applyQuickTemplate(type) {
  var textarea = document.getElementById('admin-broadcast-text');
  if (!textarea) return;

  var lang = localStorage.getItem(LS_LANG) || 'uz';
  var tmpls = ADMIN_QUICK_TEMPLATES_I18N[lang] || ADMIN_QUICK_TEMPLATES_I18N.uz;
  var text = tmpls[type] || '';
  if (type === 'started' || type === 'ended') {
    var code = getActiveOrPlannedTestCode();
    var codeDisplay = code ? (code.startsWith('#') ? code : ('#' + code)) : '#TEST_KODI';
    text = text + "\n\n" + t('lbl_test_code') + " " + codeDisplay;
  }

  textarea.value = text;
  updateBroadcastCharCount();

  textarea.focus();
  try {
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  } catch (e) {}

  try {
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
    }
  } catch (e) {}

  var btn = document.getElementById('tmpl-btn-' + type);
  if (btn) {
    btn.classList.add('tmpl-active');
    setTimeout(function() { btn.classList.remove('tmpl-active'); }, 300);
  }
}

function updateBroadcastCharCount() {
  var textarea = document.getElementById('admin-broadcast-text');
  var countEl = document.getElementById('broadcast-char-count');
  if (!textarea) return;
  window._cachedBroadcastText = textarea.value || '';
  if (countEl) {
    var len = (textarea.value || '').length;
    countEl.textContent = len + ' ' + t('bcast_chars');
  }
}

function clearBroadcastText() {
  var textarea = document.getElementById('admin-broadcast-text');
  if (textarea) {
    textarea.value = '';
    window._cachedBroadcastText = '';
    updateBroadcastCharCount();
    textarea.focus();
  }
}

async function sendAdminBroadcast() {
  var textarea = document.getElementById('admin-broadcast-text');
  if (!textarea) return;
  var msg = (textarea.value || '').trim();
  if (!msg) {
    alert(t('admin_broadcast_empty_prompt'));
    textarea.focus();
    return;
  }

  if (!confirm(t('admin_broadcast_confirm_prompt') + "\n\n\"" + (msg.length > 80 ? msg.substring(0, 80) + '...' : msg) + "\"")) {
    return;
  }

  var btn = document.getElementById('btn-send-broadcast');
  var originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>' + t('admin_broadcast_sending') + '</span>';
  }

  var urlParams = new URLSearchParams(window.location.search);
  var adminId = (state.tgUser && state.tgUser.id) || parseInt(urlParams.get('tg_id')) || 0;

  try {
    var res = await fetch('/api/app/broadcast', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        admin_id: adminId,
        message: msg,
        init_data: (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''
      })
    });
    var data = await res.json();
    if (data.success) {
      alert(t('admin_broadcast_sent_title') + "\n\n" + t('admin_broadcast_delivered_lbl') + ": " + (data.sent || 0) + " " + t('unit_count') + (data.fail ? ("\n" + t('admin_broadcast_failed_lbl') + ": " + data.fail + " " + t('unit_count')) : ""));
      textarea.value = '';
      window._cachedBroadcastText = '';
      updateBroadcastCharCount();
    } else {
      alert((t('error_occurred') + ': ') + (data.message || ''));
    }
  } catch (e) {
    console.error("Broadcast error:", e);
    alert(t('err_network') + ' ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

function switchAdminSubtab(subtab) {
  if (state.adminSubtab === subtab) return;

  var currentText = document.getElementById('admin-broadcast-text');
  if (currentText) {
    window._cachedBroadcastText = currentText.value;
  }

  state.adminSubtab = subtab;

  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    try {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    } catch(e) {}
  }

  renderAdminTab();

  if (subtab === 'users') {
    if (window.currentAdminUsers) {
      renderUsersSection(window.currentAdminUsers, window.currentAdminStats);
    } else {
      loadAllUsers();
    }
  } else if (subtab === 'broadcast') {
    var ta = document.getElementById('admin-broadcast-text');
    if (ta && window._cachedBroadcastText) {
      ta.value = window._cachedBroadcastText;
      updateBroadcastCharCount();
    }
  }
}

function renderAdminTab() {
  var tab = document.getElementById('tab-admin');
  if (!tab) return;
  var currentSubtab = state.adminSubtab || 'users';
  var usersCount = window.currentAdminUsers ? window.currentAdminUsers.length : 0;

  var usersIcon = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';
  var broadcastIcon = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>';

  var html =
    '<div class="admin-header-card animate-in">' +
      '<div class="admin-header-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></div>' +
      '<div>' +
        '<div style="font-size:16px;font-weight:800;color:var(--text)">' + t('admin_panel') + '</div>' +
        '<div style="font-size:12px;color:var(--text-muted);margin-top:2px">' + t('admin_panel_sub') + '</div>' +
      '</div>' +
    '</div>' +

    // ── ADMIN SUBTABS SWITCHER (Bo'limlarga ajratish) ──
    '<div class="admin-subtabs animate-in" style="margin-top:12px;margin-bottom:14px;">' +
      '<button type="button" class="admin-subtab ' + (currentSubtab === 'users' ? 'active' : '') + '" onclick="switchAdminSubtab(\'users\')">' +
        '<span class="admin-subtab-icon">' + usersIcon + '</span>' +
        '<span class="admin-subtab-text">' + t('admin_tab_users') + '</span>' +
        '<span class="admin-subtab-badge" id="admin-subtab-users-count">' + usersCount + '</span>' +
      '</button>' +
      '<button type="button" class="admin-subtab ' + (currentSubtab === 'broadcast' ? 'active' : '') + '" onclick="switchAdminSubtab(\'broadcast\')">' +
        '<span class="admin-subtab-icon">' + broadcastIcon + '</span>' +
        '<span class="admin-subtab-text">' + t('admin_tab_broadcast') + '</span>' +
        '<span class="admin-subtab-badge"><svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></span>' +
      '</button>' +
    '</div>';

  if (currentSubtab === 'users') {
    html +=
      // Statistika konteyneri (JS to'ldiradi)
      '<div id="admin-stats-container" class="animate-in"></div>' +

      // Foydalanuvchilar kartasi
      '<div class="card animate-in" style="margin-top:0">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">' +
          '<div style="font-size:13.5px;font-weight:800;color:var(--text)">' + t('admin_users_list') + '</div>' +
          '<div id="admin-users-badge-count" style="font-size:11.5px;font-weight:700;color:var(--text-muted)">0 ' + t('unit_count') + '</div>' +
        '</div>' +

        // Qidiruv paneli
        '<div class="admin-search-box">' +
          '<span class="admin-search-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>' +
          '<input type="text" id="admin-user-search-input" class="admin-search-input" placeholder="' + t('admin_search_ph') + '" oninput="handleAdminUserSearch(this.value)">' +
        '</div>' +

        // Filtr tugmalari
        '<div class="admin-filter-tabs">' +
          '<button class="admin-filter-btn active" id="btn-flt-all" onclick="setAdminUserFilter(\'all\')">' + t('flt_all') + '</button>' +
          '<button class="admin-filter-btn" id="btn-flt-approved" onclick="setAdminUserFilter(\'approved\')">' + t('flt_approved') + '</button>' +
          '<button class="admin-filter-btn" id="btn-flt-pending" onclick="setAdminUserFilter(\'pending\')">' + t('flt_pending') + '</button>' +
          '<button class="admin-filter-btn" id="btn-flt-blocked" onclick="setAdminUserFilter(\'blocked\')">' + t('flt_blocked') + '</button>' +
        '</div>' +

        // Ro'yxat
        '<div id="users-list">' +
          '<div class="skeleton skeleton-card" style="height:50px"></div>' +
          '<div class="skeleton skeleton-card" style="height:50px;margin-top:8px"></div>' +
        '</div>' +
      '</div>' +

      // Barchani cheklash tugmasi
      '<button class="admin-btn-restrict-all animate-in" style="margin-top:14px;" onclick="restrictAllUsersFromApp()">' +
        t('btn_restrict_all') +
      '</button>';
  } else {
    // O'quvchilarga xabar yuborish (Tezkor shablonlar + Textarea)
    html +=
      '<div class="admin-broadcast-card animate-in">' +
        '<div class="admin-broadcast-header">' +
          '<div class="admin-broadcast-title-wrap">' +
            '<div class="admin-broadcast-icon-box"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg></div>' +
            '<div>' +
              '<div class="admin-broadcast-title">' + t('bcast_title') + '</div>' +
              '<div class="admin-broadcast-subtitle">' + t('bcast_subtitle') + '</div>' +
            '</div>' +
          '</div>' +
          '<span class="admin-broadcast-badge">' + t('bcast_badge_fast') + '</span>' +
        '</div>' +

        // Tezkor tayyor shablonlar
        '<div class="quick-templates-section">' +
          '<div class="quick-templates-label"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="display:inline-block;vertical-align:-1px;margin-right:3px"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> ' + t('bcast_quick_label') + '</div>' +
          '<div class="quick-templates-grid">' +
            '<button type="button" class="quick-tmpl-btn" id="tmpl-btn-30m" onclick="applyQuickTemplate(\'30m\')">' +
              '<span class="tmpl-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></span>' +
              '<span class="tmpl-text">' + t('tmpl_30m') + '</span>' +
            '</button>' +
            '<button type="button" class="quick-tmpl-btn" id="tmpl-btn-10m" onclick="applyQuickTemplate(\'10m\')">' +
              '<span class="tmpl-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span>' +
              '<span class="tmpl-text">' + t('tmpl_10m') + '</span>' +
            '</button>' +
            '<button type="button" class="quick-tmpl-btn" id="tmpl-btn-started" onclick="applyQuickTemplate(\'started\')">' +
              '<span class="tmpl-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg></span>' +
              '<span class="tmpl-text">' + t('tmpl_started') + '</span>' +
            '</button>' +
            '<button type="button" class="quick-tmpl-btn" id="tmpl-btn-15m" onclick="applyQuickTemplate(\'15m\')">' +
              '<span class="tmpl-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></span>' +
              '<span class="tmpl-text">' + t('tmpl_15m') + '</span>' +
            '</button>' +
            '<button type="button" class="quick-tmpl-btn" id="tmpl-btn-ended" onclick="applyQuickTemplate(\'ended\')">' +
              '<span class="tmpl-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg></span>' +
              '<span class="tmpl-text">' + t('tmpl_ended') + '</span>' +
            '</button>' +
          '</div>' +
        '</div>' +

        // Xabar matni maydoni (textarea)
        '<div class="broadcast-textarea-wrap">' +
          '<textarea id="admin-broadcast-text" class="admin-broadcast-textarea" rows="3" placeholder="' + t('bcast_textarea_ph') + '" oninput="updateBroadcastCharCount()">' + escHtml(window._cachedBroadcastText || '') + '</textarea>' +
          '<div class="broadcast-meta-row">' +
            '<span id="broadcast-char-count" class="broadcast-char-count">' + (window._cachedBroadcastText ? window._cachedBroadcastText.length : 0) + ' ' + t('bcast_chars') + '</span>' +
            '<button type="button" class="btn-clear-broadcast" onclick="clearBroadcastText()">' + t('bcast_clear') + '</button>' +
          '</div>' +
        '</div>' +

        // Yuborish tugmasi
        '<button type="button" class="btn-send-broadcast" id="btn-send-broadcast" onclick="sendAdminBroadcast()">' +
          '<span>' + t('bcast_send_btn') + '</span>' +
        '</button>' +
      '</div>';
  }

  tab.innerHTML = html;
}

function handleAdminUserSearch(query) {
  window.adminSearchQuery = (query || '').trim().toLowerCase();
  renderFilteredAdminUsers();
}

function setAdminUserFilter(filter) {
  window.adminCurrentFilter = filter;
  ['all', 'approved', 'pending', 'blocked'].forEach(function(f) {
    var btn = document.getElementById('btn-flt-' + f);
    if (btn) btn.classList.toggle('active', f === filter);
  });
  renderFilteredAdminUsers();
}

function renderUsersSection(users, stats) {
  window.currentAdminUsers = users || [];
  window.currentAdminStats = stats || null;
  window.adminCurrentFilter = window.adminCurrentFilter || 'all';
  window.adminSearchQuery = window.adminSearchQuery || '';

  // Admin subtabdagi foydalanuvchilar soni
  var subtabBadge = document.getElementById('admin-subtab-users-count');
  if (subtabBadge) {
    subtabBadge.textContent = window.currentAdminUsers.length;
  }

  // 1. Statistikani yangilash
  var statsContainer = document.getElementById('admin-stats-container');
  if (statsContainer && stats) {
    statsContainer.innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px">' +
        '<div class="stat-card" style="padding:8px 4px;text-align:center"><div class="stat-value" style="font-size:16px;font-weight:800">' + (stats.total||0) + '</div><div class="stat-label" style="font-size:10px">' + t('admin_stat_total') + '</div></div>' +
        '<div class="stat-card" style="padding:8px 4px;text-align:center"><div class="stat-value" style="font-size:16px;font-weight:800;color:#10b981">' + (stats.approved||0) + '</div><div class="stat-label" style="font-size:10px">' + t('admin_stat_active') + '</div></div>' +
        '<div class="stat-card" style="padding:8px 4px;text-align:center"><div class="stat-value" style="font-size:16px;font-weight:800;color:#f59e0b">' + (stats.pending||0) + '</div><div class="stat-label" style="font-size:10px">' + t('admin_stat_pending') + '</div></div>' +
        '<div class="stat-card" style="padding:8px 4px;text-align:center"><div class="stat-value" style="font-size:16px;font-weight:800;color:#ef4444">' + (stats.blocked||0) + '</div><div class="stat-label" style="font-size:10px">' + t('admin_stat_blocked') + '</div></div>' +
      '</div>';
  }

  // 2. Foydalanuvchilar ro'yxatini render qilish
  renderFilteredAdminUsers();
}

function renderFilteredAdminUsers() {
  var listEl = document.getElementById('users-list');
  if (!listEl) return;

  var users = window.currentAdminUsers || [];
  var filter = window.adminCurrentFilter || 'all';
  var q = window.adminSearchQuery || '';

  var filtered = users.filter(function(u) {
    // Holat bo'yicha filter
    var st = (u.status || 'pending').toLowerCase();
    if (filter === 'approved' && st !== 'approved') return false;
    if (filter === 'pending' && st !== 'pending') return false;
    if (filter === 'blocked' && st !== 'blocked') return false;

    // Qidiruv bo'yicha filter
    if (q) {
      var rawQ = q.toLowerCase().trim();
      var cleanQ = rawQ.replace(/^@+/, '').trim();
      var uName = (u.username || '').toLowerCase().replace(/^@+/, '').trim();
      var nameMatch = (u.fullname || '').toLowerCase().indexOf(rawQ) !== -1 || (cleanQ && (u.fullname || '').toLowerCase().indexOf(cleanQ) !== -1);
      var phoneMatch = cleanQ ? (u.phone || '').toLowerCase().indexOf(cleanQ) !== -1 : false;
      var idMatch = cleanQ ? String(u.tg_id || '').indexOf(cleanQ) !== -1 : false;
      var userMatch = Boolean(uName && (uName.indexOf(cleanQ) !== -1 || ('@' + uName).indexOf(rawQ) !== -1 || uName.indexOf(rawQ) !== -1));
      if (!nameMatch && !phoneMatch && !idMatch && !userMatch) return false;
    }
    return true;
  });

  var countBadge = document.getElementById('admin-users-badge-count');
  if (countBadge) {
    countBadge.textContent = filtered.length + ' ' + t('unit_count') + (filtered.length !== users.length ? (' (' + t('filtered_suffix') + ')') : '');
  }

  if (filtered.length === 0) {
    listEl.innerHTML =
      '<div class="empty-state" style="padding:24px 10px;">' +
        '<div class="empty-icon"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>' +
        '<p style="font-size:13px;color:var(--text-muted);">' + (q ? t('admin_no_match') : t('admin_no_users')) + '</p>' +
      '</div>';
    return;
  }

  var usersHtml = filtered.map(function(u) {
    var letter = (u.fullname || 'F').charAt(0).toUpperCase();
    var tc = u.tests_count || 0;
    var st = (u.status || 'pending').toLowerCase();
    var sb = '';
    if (st === 'approved') {
      sb = '<span class="badge" style="padding:3px 8px;font-size:10.5px;display:inline-flex;align-items:center;gap:4px;background:rgba(16,185,129,0.15);color:#10b981;border:1px solid rgba(16,185,129,0.3);border-radius:12px;"><span class="status-dot approved" style="width:6px;height:6px"></span> ' + t('status_approved') + '</span>';
    } else if (st === 'pending') {
      sb = '<span class="badge" style="padding:3px 8px;font-size:10.5px;display:inline-flex;align-items:center;gap:4px;background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);border-radius:12px;"><span class="status-dot pending" style="width:6px;height:6px"></span> ' + t('status_pending') + '</span>';
    } else if (st === 'blocked') {
      sb = '<span class="badge" style="padding:3px 8px;font-size:10.5px;display:inline-flex;align-items:center;gap:4px;background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);border-radius:12px;"><span class="status-dot rejected" style="width:6px;height:6px"></span> ' + t('status_blocked') + '</span>';
    } else {
      sb = '<span class="badge" style="padding:3px 8px;font-size:10.5px;display:inline-flex;align-items:center;gap:4px;background:rgba(100,116,139,0.15);color:#94a3b8;border:1px solid rgba(100,116,139,0.3);border-radius:12px;">' + st + '</span>';
    }

    return '<div class="user-row clickable" onclick="openAdminUserModal(' + u.tg_id + ')">' +
      '<div class="user-row-avatar">' + letter + '</div>' +
      '<div class="user-row-info">' +
        '<div class="user-row-name" style="font-size:14.5px;font-weight:700;">' + escHtml(u.fullname || t('user_unknown')) + '</div>' +
      '</div>' +
      sb +
      '<span style="color:var(--text-muted);display:flex;align-items:center;margin-left:4px"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
    '</div>';
  }).join('');

  listEl.innerHTML = usersHtml;
}

function openAdminUserModal(targetUid) {
  var users = window.currentAdminUsers || [];
  var u = users.find(function(item) { return item.tg_id === Number(targetUid); });
  if (!u && typeof targetUid === 'object') u = targetUid;

  if (!u) {
    alert(t('user_not_found'));
    return;
  }

  var modal = document.getElementById('admin-user-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'admin-user-modal';
    modal.className = 'modal-overlay';
    modal.style.cssText = 'display:none;position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.7);align-items:center;justify-content:center;backdrop-filter:blur(6px);padding:16px;';
    modal.onclick = function(e) { closeAdminUserModal(e); };
    modal.innerHTML =
      '<div class="modal-box" id="admin-user-modal-box" style="max-width:400px;width:100%;max-height:92vh;overflow-y:auto;padding:22px 18px;border-radius:24px;background:var(--bg-card,#1e293b);border:1px solid var(--border,rgba(255,255,255,0.12));box-shadow:0 24px 60px rgba(0,0,0,0.5);position:relative;">' +
        '<div class="modal-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">' +
          '<div class="modal-title" style="font-size:16px;font-weight:800;color:var(--text,#fff);">' + t('modal_user_mgmt_title') + '</div>' +
          '<button class="modal-close" onclick="closeAdminUserModal()" style="background:none;border:none;color:var(--text-muted,#94a3b8);cursor:pointer;padding:4px 8px;display:flex;align-items:center;justify-content:center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>' +
        '</div>' +
        '<div class="modal-body" id="admin-user-modal-body"></div>' +
      '</div>';
    document.body.appendChild(modal);
  }

  var body = document.getElementById('admin-user-modal-body');
  if (!body) return;

  var letter = (u.fullname || 'F').charAt(0).toUpperCase();
  var st = (u.status || 'pending').toLowerCase();

  var statusBadge = '';
  if (st === 'approved') {
    statusBadge = '<span class="stat-status-badge status-approved" style="font-size:12px;padding:4px 12px;"><span class="status-dot approved"></span> ' + t('admin_modal_approved_badge') + '</span>';
  } else if (st === 'pending') {
    statusBadge = '<span class="stat-status-badge status-pending" style="font-size:12px;padding:4px 12px;"><span class="status-dot pending"></span> ' + t('admin_modal_pending_badge') + '</span>';
  } else if (st === 'blocked') {
    statusBadge = '<span class="stat-status-badge status-rejected" style="font-size:12px;padding:4px 12px;"><span class="status-dot rejected"></span> ' + t('admin_modal_blocked_badge') + '</span>';
  } else {
    statusBadge = '<span class="stat-status-badge" style="font-size:12px;padding:4px 12px;">' + st + '</span>';
  }

  var regDateStr = u.registered_at ? formatDate(u.registered_at) : t('user_unknown');
  var lastTestStr = u.last_test_at ? formatDate(u.last_test_at) : t('admin_no_tests_yet');
  var usernameStr = u.username ? ('@' + u.username) : t('val_none');

  // Harakat tugmalari (Action buttons) - Birinchi o'rinda ko'rinadi
  var actionButtonsHtml = '<div style="margin-top:12px;display:flex;flex-direction:column;gap:8px;">';

  if (st !== 'approved') {
    actionButtonsHtml += '<button class="admin-btn-action admin-btn-approve" onclick="updateUserStatusFromModal(' + u.tg_id + ', \'approved\')">' + t('btn_admin_approve') + '</button>';
  } else {
    actionButtonsHtml += '<button class="admin-btn-action admin-btn-pending" onclick="updateUserStatusFromModal(' + u.tg_id + ', \'pending\')">' + t('btn_admin_suspend') + '</button>';
  }

  if (st !== 'blocked') {
    actionButtonsHtml += '<button class="admin-btn-action admin-btn-block" onclick="updateUserStatusFromModal(' + u.tg_id + ', \'blocked\')">' + t('btn_admin_block') + '</button>';
  } else {
    actionButtonsHtml += '<button class="admin-btn-action admin-btn-approve" onclick="updateUserStatusFromModal(' + u.tg_id + ', \'approved\')">' + t('btn_admin_unblock') + '</button>';
  }

  actionButtonsHtml += '<button class="admin-btn-action admin-btn-delete" onclick="updateUserStatusFromModal(' + u.tg_id + ', \'delete\')">' + t('btn_admin_delete_db') + '</button>';
  actionButtonsHtml += '</div>';

  // Foydalanuvchi ma'lumotlari (Akkordeon / Ko'rsatish-Yashirish)
  var infoToggleHtml =
    '<button type="button" class="admin-user-info-toggle-btn" id="btn-toggle-user-info" onclick="toggleAdminUserInfo()">' +
      '<span class="info-toggle-left">' +
        '<span style="display:flex;align-items:center;"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></span>' +
        '<span>' + t('admin_user_info_label') + '</span>' +
      '</span>' +
      '<span class="info-toggle-arrow" id="info-toggle-arrow">' + t('toggle_show') + '</span>' +
    '</button>' +
    '<div id="admin-user-info-content" class="admin-user-info-content" style="display:none;">' +
      '<div class="card" style="margin:0;padding:10px 14px;border-radius:14px;background:var(--bg-glass-2);border:1px solid var(--border);">' +
        '<div class="info-row" style="padding:9px 0;"><div class="info-icon" style="width:32px;height:32px;display:flex;align-items:center;justify-content:center;"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg></div><div><div class="info-label" style="font-size:11px;">' + t('lbl_phone_short') + '</div><div class="info-value" style="font-size:14px;font-weight:700;"><a href="tel:' + escHtml(u.phone || '') + '" style="color:var(--primary);text-decoration:none;">' + escHtml(u.phone || '—') + '</a></div></div></div>' +
        '<div class="info-row" style="padding:9px 0;"><div class="info-icon" style="width:32px;height:32px;display:flex;align-items:center;justify-content:center;"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><line x1="15" y1="8" x2="17" y2="8"/><line x1="15" y1="12" x2="17" y2="12"/><line x1="7" y1="16" x2="17" y2="16"/></svg></div><div><div class="info-label" style="font-size:11px;">' + t('lbl_tg_id_short') + '</div><div class="info-value" style="font-size:14px;font-weight:700;"><code>' + u.tg_id + '</code></div></div></div>' +
        '<div class="info-row" style="padding:9px 0;"><div class="info-icon" style="width:32px;height:32px;display:flex;align-items:center;justify-content:center;"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg></div><div><div class="info-label" style="font-size:11px;">' + t('lbl_username_short') + '</div><div class="info-value" style="font-size:14px;font-weight:700;">' + escHtml(usernameStr) + '</div></div></div>' +
        '<div class="info-row" style="padding:9px 0;"><div class="info-icon" style="width:32px;height:32px;display:flex;align-items:center;justify-content:center;"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div><div><div class="info-label" style="font-size:11px;">' + t('lbl_reg_date') + '</div><div class="info-value" style="font-size:13.5px;font-weight:700;color:var(--primary);">' + regDateStr + '</div></div></div>' +
        '<div class="info-row" style="padding:9px 0;"><div class="info-icon" style="width:32px;height:32px;display:flex;align-items:center;justify-content:center;"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></div><div><div class="info-label" style="font-size:11px;">' + t('admin_lbl_tests_count') + '</div><div class="info-value" style="font-size:14px;font-weight:700;">' + (u.tests_count || 0) + ' ' + t('unit_count') + '</div></div></div>' +
        '<div class="info-row" style="padding:9px 0;border-bottom:none;"><div class="info-icon" style="width:32px;height:32px;display:flex;align-items:center;justify-content:center;"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 14 10"/></svg></div><div><div class="info-label" style="font-size:11px;">' + t('admin_lbl_last_test') + '</div><div class="info-value" style="font-size:13px;font-weight:600;">' + lastTestStr + '</div></div></div>' +
      '</div>' +
    '</div>';

  body.innerHTML =
    '<div style="text-align:center;padding:2px 0 10px;">' +
      '<div class="profile-avatar" style="margin:0 auto 8px;width:52px;height:52px;font-size:22px;display:flex;align-items:center;justify-content:center;">' + letter + '</div>' +
      '<div style="font-size:16.5px;font-weight:800;color:var(--text);">' + escHtml(u.fullname || t('default_user')) + '</div>' +
      '<div style="margin-top:6px;">' + statusBadge + '</div>' +
    '</div>' +
    actionButtonsHtml +
    infoToggleHtml;

  modal.style.display = 'flex';
}

function toggleAdminUserInfo() {
  var content = document.getElementById('admin-user-info-content');
  var arrow = document.getElementById('info-toggle-arrow');
  if (!content) return;
  var isHidden = content.style.display === 'none' || content.style.display === '';
  if (isHidden) {
    content.style.display = 'block';
    if (arrow) arrow.innerHTML = t('toggle_hide');
  } else {
    content.style.display = 'none';
    if (arrow) arrow.innerHTML = t('toggle_show');
  }
  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    try { window.Telegram.WebApp.HapticFeedback.selectionChanged(); } catch(e) {}
  }
}

function closeAdminUserModal(e) {
  if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('modal-close')) return;
  var modal = document.getElementById('admin-user-modal');
  if (modal) modal.style.display = 'none';
}

async function updateUserStatusFromModal(targetUid, newStatus) {
  if (newStatus === 'delete') {
    if (!confirm(t('admin_confirm_delete_user'))) {
      return;
    }
  } else if (newStatus === 'blocked') {
    if (!confirm(t('admin_confirm_block_user'))) {
      return;
    }
  } else if (newStatus === 'pending') {
    if (!confirm(t('admin_confirm_pending_user'))) {
      return;
    }
  }

  var adminId = (state.tgUser && state.tgUser.id) || 0;
  var btn = (typeof event !== 'undefined' && event && event.target) ? event.target : null;
  var originalText = btn ? btn.textContent : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = t('action_in_progress');
  }

  try {
    var res = await fetch('/api/app/update-user-status', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        admin_id: adminId,
        target_uid: targetUid,
        status: newStatus,
        init_data: (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''
      })
    });
    var data = await res.json();
    if (data.success) {
      closeAdminUserModal();
      if (newStatus === 'delete') {
        alert(t('admin_alert_deleted'));
      } else if (newStatus === 'approved') {
        alert(t('admin_alert_approved'));
      } else if (newStatus === 'blocked') {
        alert(t('admin_alert_blocked'));
      } else if (newStatus === 'pending') {
        alert(t('admin_alert_pending'));
      }
      loadAllUsers();
    } else {
      alert((t('error_occurred') + ': ') + (data.message || ''));
      if (btn) { btn.disabled = false; btn.textContent = originalText; }
    }
  } catch (err) {
    alert(t('err_network') + ' ' + err.message);
    if (btn) { btn.disabled = false; btn.textContent = originalText; }
  }
}

async function restrictAllUsersFromApp() {
  if (!confirm(t('admin_confirm_restrict_all'))) {
    return;
  }

  var adminId = (state.tgUser && state.tgUser.id) || 0;
  try {
    var res = await fetch('/api/app/restrict-all-users', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        admin_id: adminId,
        init_data: (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''
      })
    });
    var data = await res.json();
    if (data.success) {
      alert('Jami ' + (data.count || 0) + ' ta foydalanuvchi muvaffaqiyatli cheklandi!');
      loadAllUsers();
    } else {
      alert(data.message || 'Xatolik yuz berdi');
    }
  } catch (err) {
    alert('Server bilan bogʻlanishda xatolik: ' + err.message);
  }
}

// Webapp redirection functions removed (users will use bot inline buttons directly)

// ── PIN CHANGE ───────────────────────────────────
function changePinPrompt() {
  localStorage.removeItem(LS_PIN);
  state.pinBuffer = '';
  state.pinFirst = '';
  state.pinMode = 'setup';
  var pinScreen = document.getElementById('pin-screen');
  var app = document.getElementById('app');
  document.getElementById('pin-title').textContent = t('pin_create');
  document.getElementById('pin-subtitle').textContent = t('pin_create_sub');
  renderPinDots(0);
  showPinError('');
  app.style.display = 'none';
  app.classList.remove('visible');
  pinScreen.style.transition = '';
  pinScreen.style.opacity = '1';
  pinScreen.style.transform = 'scale(1)';
  pinScreen.style.display = 'flex';
}

// ── THEME ────────────────────────────────────────
function syncTelegramTheme(theme) {
  var t = theme || document.documentElement.getAttribute('data-theme') || 'light';
  var bg = t === 'dark' ? '#0a0b14' : '#f0f4ff';
  var metaTheme = document.querySelector('meta[name="theme-color"]');
  if (metaTheme) metaTheme.setAttribute('content', bg);
  if (window.Telegram && window.Telegram.WebApp) {
    var tg = window.Telegram.WebApp;
    try {
      if (tg.setHeaderColor) tg.setHeaderColor(bg);
      if (tg.setBackgroundColor) tg.setBackgroundColor(bg);
      if (tg.setBottomBarColor) tg.setBottomBarColor(bg);
      if (typeof tg.expand === 'function') tg.expand();
    } catch(e) {}
  }
}

var _themeSwitching = false;

function toggleTheme(event) {
  if (_themeSwitching) return;
  _themeSwitching = true;
  setTimeout(function() { _themeSwitching = false; }, 850);

  var btn = document.getElementById('theme-btn');
  if (btn) {
    btn.classList.add('theme-spinning');
    setTimeout(function() { btn.classList.remove('theme-spinning'); }, 600);
  }

  var cur = document.documentElement.getAttribute('data-theme') || 'dark';
  var next = cur === 'dark' ? 'light' : 'dark';

  // Origin coordinates: from click position or top-right theme button
  var x, y;
  if (event && typeof event.clientX === 'number' && event.clientX > 0 && typeof event.clientY === 'number' && event.clientY > 0) {
    x = event.clientX;
    y = event.clientY;
  } else if (btn) {
    var rect = btn.getBoundingClientRect();
    x = rect.left + rect.width / 2;
    y = rect.top + rect.height / 2;
  } else {
    x = window.innerWidth - 36;
    y = 36;
  }

  // Calculate radius to furthest screen corner
  var maxRadius = Math.hypot(
    Math.max(x, window.innerWidth - x),
    Math.max(y, window.innerHeight - y)
  ) + 40;

  function applyThemeChange() {
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem(LS_THEME, next);
    updateThemeIcon(next);
    syncTelegramTheme(next);
    var pTheme = document.getElementById('profile-theme-label');
    if (pTheme) {
      pTheme.textContent = next === 'dark' ? t('theme_dark_lbl') : t('theme_light_lbl');
    }
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      try { window.Telegram.WebApp.HapticFeedback.impactOccurred('medium'); } catch(e) {}
    }
  }

  // Check if native startViewTransition is safely usable without WebView restrictions
  var canViewTransition = false;
  try {
    if (typeof document.startViewTransition === 'function' && !(window.Telegram && window.Telegram.WebApp)) {
      canViewTransition = true;
    }
  } catch(e) {}

  if (canViewTransition) {
    try {
      var transition = document.startViewTransition(function() {
        applyThemeChange();
      });
      transition.ready.then(function() {
        document.documentElement.animate(
          {
            clipPath: [
              'circle(0px at ' + Math.round(x) + 'px ' + Math.round(y) + 'px)',
              'circle(' + Math.round(maxRadius) + 'px at ' + Math.round(x) + 'px ' + Math.round(y) + 'px)'
            ]
          },
          {
            duration: 620,
            easing: 'cubic-bezier(0.2, 0.85, 0.32, 1)',
            pseudoElement: '::view-transition-new(root)'
          }
        );
      }).catch(function() {
        applyThemeChange();
      });
      return;
    } catch(err) {}
  }

  // Universal GPU-accelerated Corner Wave (works 100% on iOS, Android, Telegram WebApp)
  runCornerThemeWave(x, y, maxRadius, next, applyThemeChange);
}

function runCornerThemeWave(x, y, maxRadius, nextTheme, callback) {
  var overlay = document.getElementById('theme-ripple-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'theme-ripple-overlay';
    document.body.appendChild(overlay);
  }

  // Clear any existing waves
  overlay.innerHTML = '';

  var wave = document.createElement('div');
  wave.className = 'theme-corner-wave ' + (nextTheme === 'dark' ? 'wave-to-dark' : 'wave-to-light');
  var size = Math.round(maxRadius * 2.3);
  wave.style.width = size + 'px';
  wave.style.height = size + 'px';
  wave.style.left = Math.round(x) + 'px';
  wave.style.top = Math.round(y) + 'px';

  overlay.appendChild(wave);

  // Force synchronous reflow to register scale(0)
  void wave.offsetWidth;

  // Animate expansion
  requestAnimationFrame(function() {
    wave.classList.add('wave-expanded');
  });

  // Switch underlying theme when wave covers the screen
  setTimeout(function() {
    callback();
  }, 280);

  // Fade out cleanly once expansion finishes
  setTimeout(function() {
    wave.classList.add('wave-fade');
    setTimeout(function() {
      if (wave.parentNode) wave.parentNode.removeChild(wave);
    }, 280);
  }, 580);
}

function closeUnregisteredModal() {
  // Ro'yxatdan o'tish qat'iy majburiy - oynani yopish cheklangan
}

function checkRegistrationStatus() {
  var modal = document.getElementById('unregistered-modal');
  var tg = window.Telegram && window.Telegram.WebApp;
  var tgU = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
  var tgId = (state.tgUser && state.tgUser.id) || (tgU && tgU.id) || 0;

  // 1. Agar admin simulyatsiya rejimida bo'lsa (User mode), modal chiqmaydi
  if (state.isSimulatedUser || window._unregBypassed) {
    if (modal) modal.style.display = 'none';
    return false;
  }

  // 2. Agar profil hali serverdan yuklanayotgan bo'lsa (state.userInfo null bo'lsa), modalni ko'rsatmay kutamiz
  if (!state.userInfo) {
    if (modal) modal.style.display = 'none';
    return false;
  }

  // 3. Botda ro'yxatdan o'tganligini tekshirish
  var u = state.userInfo;
  var isUnreg = (!tgId || tgId === 0 || u.status === 'not_registered' || u.is_registered === false);
  if (modal) {
    modal.style.display = isUnreg ? 'flex' : 'none';
  }
  return !!isUnreg;
}

function toggleUserSimulationMode(enable) {
  if (enable) {
    state.isActualAdmin = true;
    state.isSimulatedUser = true;
    state.isAdmin = false;
    showToast("O'quvchi rejimiga o'tildi. O'zgarishlarni bemalol tekshirishingiz mumkin!");
  } else {
    state.isSimulatedUser = false;
    state.isAdmin = true;
    showToast("Admin rejimiga qaytildi.");
  }

  // Yuqori floating banner
  var banner = document.getElementById('admin-simulation-banner');
  if (banner) {
    banner.style.display = state.isSimulatedUser ? 'flex' : 'none';
  }

  // Pastki navigatsiyadagi Admin tugmasi
  var navAdmin = document.getElementById('nav-admin');
  if (navAdmin) {
    navAdmin.style.display = state.isAdmin ? 'flex' : 'none';
  }

  // Agar admin tabida turgan bo'lsa va user rejimiga o'tsa -> Asosiy tabga o'tkazish
  if (state.isSimulatedUser && state.activeTab === 'admin') {
    switchTab('home');
  } else {
    refreshActiveTab();
  }
}

function goToBotRegister() {
  var botUser = window.BOT_USERNAME || 'bm_testbot';
  if (window.Telegram && window.Telegram.WebApp) {
    var tg = window.Telegram.WebApp;
    if (botUser) {
      try {
        tg.openTelegramLink('https://t.me/' + botUser + '?start=start');
      } catch(e) {}
    }
    try {
      tg.close();
    } catch(e) {}
  } else if (botUser) {
    window.location.href = 'https://t.me/' + botUser + '?start=start';
  } else {
    window.location.href = 'https://t.me/share/url?url=start';
  }
}

function updateThemeIcon(theme) {
  var el = document.getElementById('theme-icon');
  if (el) el.innerHTML = theme === 'dark' ? '&#9790;' : '&#9728;';
}

// ── LANGUAGE ─────────────────────────────────────
var LANGS = ['uz', 'ru', 'en'];
var LANG_LABELS = { uz: 'UZ', ru: 'RU', en: 'EN' };

function refreshActiveTab() {
  var tabId = state.activeTab || 'home';
  if (tabId === 'home') {
    if (window.availableActiveTests) renderHomeTab(window.availableActiveTests);
    else loadActiveTests();
  } else if (tabId === 'tests') {
    if (window._myResults) renderTestsTab(window._myResults);
    else loadMyResults();
  } else if (tabId === 'profile') {
    renderProfileTab();
  } else if (tabId === 'admin') {
    renderAdminTab();
    if (window.currentAdminUsers) renderUsersSection(window.currentAdminUsers, window.currentAdminStats);
    else loadAllUsers();
  }
}

function cycleLang() {
  var cur = localStorage.getItem(LS_LANG) || 'uz';
  var idx = LANGS.indexOf(cur);
  var next = LANGS[(idx + 1) % LANGS.length];
  localStorage.setItem(LS_LANG, next);
  updateLangLabel();
  applyI18n();
  renderOnboardingSlides();
  refreshActiveTab();
}

function updateLangLabel() {
  var cur = localStorage.getItem(LS_LANG) || 'uz';
  var el = document.getElementById('lang-label');
  if (el) el.textContent = LANG_LABELS[cur] || 'UZ';
}

function applyI18n() {
  // data-i18n atributli barcha elementlar
  document.querySelectorAll('[data-i18n]').forEach(function(el) {
    el.textContent = t(el.getAttribute('data-i18n'));
  });
  // Header title atributlari
  var langBtn = document.getElementById('lang-btn');
  if (langBtn) langBtn.setAttribute('title', t('header_lang_title'));
  var themeBtn = document.getElementById('theme-btn');
  if (themeBtn) themeBtn.setAttribute('title', t('header_theme_title'));

  // PIN ekrani matnlari
  var pinTitle = document.getElementById('pin-title');
  var pinSub = document.getElementById('pin-subtitle');
  if (pinTitle && pinSub) {
    var hasPin = !!localStorage.getItem(LS_PIN);
    if (!hasPin || state.pinMode === 'setup') {
      pinTitle.textContent = t('pin_create');
      pinSub.textContent = t('pin_create_sub');
    } else {
      pinTitle.textContent = t('pin_enter_title');
      pinSub.textContent = t('pin_enter_sub');
    }
  }
}

// ── RESULT MODAL ─────────────────────────────────
function showResultModal(result) {
  if (typeof result === 'string') { try { result = JSON.parse(result); } catch(e) { return; } }
  var modal = document.getElementById('result-modal');
  var title = document.getElementById('result-modal-title');
  var body = document.getElementById('result-modal-body');
  if (!modal || !body) return;

  var testId = result.test_id || result.id || 0;
  var score = (result.score != null) ? result.score : 0;
  var maxScore = result.max_score || 100;
  var grade = result.grade || getGradeFromScore(score, maxScore);
  var gradeClass = gradeToClass(grade);
  var date = formatDate(result.submitted_at);
  var correct = (result.correct_count != null) ? Number(result.correct_count) : 0;
  var total = result.total_count || result.total_questions || 55;
  var wrong = (result.incorrect_count != null) ? result.incorrect_count : Math.max(0, total - correct);
  var blank = result.unanswered_count || 0;

  var gradeBg = { 'grade-5':'rgba(16,185,129,0.15)', 'grade-4':'rgba(59,130,246,0.15)', 'grade-3':'rgba(245,158,11,0.15)', 'grade-2':'rgba(239,68,68,0.15)' };
  var gradeColor = { 'grade-5':'#10B981', 'grade-4':'#3B82F6', 'grade-3':'#F59E0B', 'grade-2':'#EF4444' };
  var gradeBorder = { 'grade-5':'#10B981', 'grade-4':'#3B82F6', 'grade-3':'#F59E0B', 'grade-2':'#EF4444' };

  var isRejected = Boolean(result.is_rejected || result.status === 'rejected');
  if (isRejected) {
    grade = t('badge_cancelled') || 'Bekor qilingan';
    score = 0;
    gradeClass = 'grade-2';
  }

  var isPub = Boolean(result.results_published);
  if (title) title.textContent = (result.test_title || result.title || t('result_title'));

  var html =
    '<div style="text-align:center;margin:6px 0 14px;">' +
      '<div style="display:inline-flex;flex-direction:column;align-items:center;justify-content:center;padding:12px 28px;border-radius:18px;background:' + (isRejected ? 'rgba(239,68,68,0.15)' : (gradeBg[gradeClass]||'rgba(99,102,241,0.15)')) + ';border:2px solid ' + (isRejected ? '#EF4444' : (gradeBorder[gradeClass]||'#6366F1')) + ';min-width:140px;">' +
        '<span style="font-size:24px;font-weight:900;line-height:1.1;color:' + (isRejected ? '#EF4444' : (gradeColor[gradeClass]||'#6366F1')) + ';display:inline-flex;align-items:center;justify-content:center;gap:6px;">' + (isRejected ? '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg> ' + grade : grade) + '</span>' +
        '<span style="font-size:14px;font-weight:800;color:var(--text);margin-top:4px;">' + (isRejected ? 'Natija bekor qilingan' : (score + ' ' + t('score_pts'))) + '</span>' +
      '</div>' +
    '</div>';

  if (isRejected) {
    html += '<div style="margin:8px 0 14px;padding:12px 14px;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);border-radius:12px;font-size:12.5px;color:#EF4444;font-weight:700;line-height:1.45;text-align:left;display:flex;align-items:center;gap:8px;">' +
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>' +
      '<span>Ushbu test javoblaringiz ma\'muriyat tomonidan bekor qilindi va qabul qilinmadi.</span>' +
    '</div>';
  } else {
    html +=
      '<div id="compare-keys-section" style="text-align:center; margin: 10px 0 14px;">' +
        '<button id="btn-compare-keys" type="button" onclick="promptCompareKeys(' + testId + ')" style="background:linear-gradient(135deg, #3B82F6, #6366F1);color:white;border:none;padding:12px;border-radius:12px;font-weight:800;font-size:14.5px;cursor:pointer;width:100%;box-shadow:0 4px 14px rgba(59, 130, 246, 0.4);display:flex;align-items:center;justify-content:center;gap:8px;">' + t('btn_see_keys') + '</button>' +
        '<div id="compare-keys-auth" style="display:none;margin-top:10px;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:12px;text-align:left;">' +
          '<p style="font-size:12px;color:var(--text-muted);margin:0 0 8px;font-weight:600;">' + t('desc_key_code') + '</p>' +
          '<div style="display:flex;gap:8px;margin-bottom:6px;">' +
            '<input type="text" id="input-key-code" placeholder="' + t('placeholder_key_code') + '" style="flex:1;padding:10px;border-radius:8px;border:1px solid var(--border);background:var(--bg-body, #111827);color:var(--text);font-size:14px;outline:none;">' +
            '<button type="button" id="btn-submit-key-code" onclick="submitCompareKeys(' + testId + ')" style="background:#10B981;color:white;border:none;padding:10px 16px;border-radius:8px;font-weight:700;cursor:pointer;white-space:nowrap;">' + t('btn_confirm') + '</button>' +
          '</div>' +
          '<div id="compare-keys-error" style="color:var(--error);font-size:12px;margin-top:4px;display:none;line-height:1.4;"></div>' +
        '</div>' +
      '</div>' +
      '<div id="compare-keys-result" style="display:none;margin-bottom:14px;max-height:320px;overflow-y:auto;border:1px solid var(--border);border-radius:12px;padding:10px;"></div>';

    if (!isPub) {
      html += '<div style="margin:8px 0 12px;padding:10px 14px;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.25);border-radius:12px;font-size:12.5px;color:#D97706;font-weight:600;line-height:1.45;text-align:left;display:flex;align-items:center;gap:8px;">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> ' +
        '<span>' + t('test_waiting_result') + '</span>' +
      '</div>';
    }
  }

  html +=
    '<div class="result-row"><span class="result-row-label">' + t('lbl_total_score') + '</span><span class="result-row-val" style="color:var(--primary);font-weight:800;font-size:16px;">' + score + ' ' + t('score_pts') + '</span></div>' +
    '<div class="result-row"><span class="result-row-label">' + t('result_grade') + '</span><span class="result-row-val" style="color:' + (gradeColor[gradeClass]||'var(--accent)') + ';font-weight:800;">' + grade + '</span></div>' +
    '<div class="result-row"><span class="result-row-label">' + t('result_correct') + '</span><span class="result-row-val green">' + correct + ' / ' + total + ' ' + t('unit_count') + '</span></div>' +
    '<div class="result-row"><span class="result-row-label">' + t('result_wrong') + '</span><span class="result-row-val red">' + wrong + ' ' + t('unit_count') + '</span></div>' +
    (blank > 0 ? ('<div class="result-row"><span class="result-row-label">' + t('result_blank') + '</span><span class="result-row-val orange">' + blank + ' ' + t('unit_count') + '</span></div>') : '') +
    '<div class="result-row"><span class="result-row-label">' + t('result_date') + '</span><span class="result-row-val">' + date + '</span></div>';

  body.innerHTML = html;
  modal.style.display = 'flex';
}

function promptCompareKeys(testId) {
  var btn = document.getElementById('btn-compare-keys');
  var auth = document.getElementById('compare-keys-auth');
  var inp = document.getElementById('input-key-code');
  if (btn) btn.style.display = 'none';
  if (auth) auth.style.display = 'block';
  if (inp) {
    inp.focus();
    inp.onkeydown = function(e) {
      if (e.key === 'Enter') submitCompareKeys(testId);
    };
  }
}

async function submitCompareKeys(testId) {
  var tgId = (state.tgUser && state.tgUser.id) || (state.userInfo && state.userInfo.tg_id) || 0;
  var inp = document.getElementById('input-key-code');
  var code = inp ? inp.value.trim() : '';
  var errEl = document.getElementById('compare-keys-error');
  var resEl = document.getElementById('compare-keys-result');
  var btn = document.getElementById('btn-submit-key-code') || (typeof event !== 'undefined' && event && event.target);

  if (state._isComparing) return;
  state._isComparing = true;

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="display:inline-block;width:12px;height:12px;border:2px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:spin 0.8s linear infinite;margin-right:6px;vertical-align:middle;"></span>Tekshirilmoqda...';
  }
  if (errEl) errEl.style.display = 'none';

  try {
    const res = await fetch('/api/app/compare-keys', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        tg_id: tgId,
        test_id: Number(testId),
        code: code,
        init_data: (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''
      })
    });
    const data = await res.json();

    if (res.status === 429) {
      if (errEl) {
        errEl.textContent = data.message || "Iltimos, biroz kuting! So'rovingiz navbatda qayta ishlanmoqda...";
        errEl.style.display = 'block';
      }
      return;
    }

    if (data.success) {
      var auth = document.getElementById('compare-keys-auth');
      if (auth) auth.style.display = 'none';
      renderKeyComparison(data, resEl);
    } else {
      if (errEl) {
        errEl.textContent = data.message || t('error_occurred');
        errEl.style.display = 'block';
      }
    }
  } catch(e) {
    if (errEl) {
      errEl.textContent = t('err_network') || "Serverga ulanib bo'lmadi";
      errEl.style.display = 'block';
    }
  } finally {
    state._isComparing = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = t('btn_confirm');
    }
  }
}

function renderKeyComparison(data, container) {
  if (!container) return;
  container.style.display = 'block';

  var results = {};
  var totalCorrect = 0;
  var totalClosed = 0;
  var totalOpen = 0;

  if (data && data.results) {
    results = data.results;
    totalCorrect = (data.total_correct !== undefined) ? data.total_correct : 0;
    totalClosed = (data.total_correct_closed !== undefined) ? data.total_correct_closed : 0;
    totalOpen = (data.total_correct_open !== undefined) ? data.total_correct_open : 0;
  } else if (arguments.length >= 3) {
    var correct = arguments[0] || {};
    var user = arguments[1] || {};
    container = arguments[2];

    for (var i = 1; i <= 35; i++) {
      var k = String(i);
      var cVal = correct[k];
      var uVal = user[k];
      var m = (window.checkAnswerMatch ? window.checkAnswerMatch(cVal, uVal) : { isOk: (cVal === uVal), status: (cVal === uVal ? 'correct' : 'incorrect') });
      if (m.isOk) totalClosed++;
      results[k] = { status: m.status, user: uVal || '—' };
    }
    for (var q = 36; q <= 45; q++) {
      ['a', 'b'].forEach(function(sub) {
        var k = q + sub;
        var cVal = correct[k];
        var uVal = user[k];
        var m = (window.checkAnswerMatch ? window.checkAnswerMatch(cVal, uVal) : { isOk: (cVal === uVal), status: (cVal === uVal ? 'correct' : 'incorrect'), ratio: 1.0 });
        if (m.isOk) totalOpen++;
        results[k] = { status: m.status, user: uVal || '—', ratio: m.ratio };
      });
    }
    totalCorrect = totalClosed + totalOpen;
  }

  // 1-bosqich: Yopiq testlar (1–35)
  var closedHtml = '';
  for (var i = 1; i <= 35; i++) {
    var item = results[String(i)] || { status: 'incorrect', user: '—' };
    var isOk = item.status === 'correct';
    var bg = isOk ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)';
    var col = isOk ? '#10B981' : '#EF4444';
    var iconSvg = isOk 
      ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="display:inline-block;vertical-align:middle;"><polyline points="20 6 9 17 4 12"/></svg>' 
      : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="display:inline-block;vertical-align:middle;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    var uVal = item.user || '—';

    closedHtml += '<div style="background:' + bg + ';color:' + col + ';border:1px solid ' + col + ';border-radius:8px;padding:6px 2px;text-align:center;font-size:11px;line-height:1.2;">';
    closedHtml += '<div style="font-weight:700;font-size:11px;margin-bottom:2px;display:flex;align-items:center;justify-content:center;gap:3px;">#' + i + ' ' + iconSvg + '</div>';
    closedHtml += '<div style="font-size:10px;opacity:0.9;">' + t('compare_keys_you') + ' <b>' + escHtml(uVal) + '</b></div>';
    closedHtml += '<div style="font-size:10px;font-weight:600;">' + (isOk ? t('result_correct') : t('result_wrong')) + '</div>';
    closedHtml += '</div>';
  }

  // 2-bosqich: Ochiq yozma savollar (36a–45b)
  var openHtml = '';
  for (var q = 36; q <= 45; q++) {
    ['a', 'b'].forEach(function(sub) {
      var key = q + sub;
      var item = results[key] || { status: 'incorrect', user: '—', ratio: 0 };
      var isOk = item.status === 'correct';
      var isPartial = item.status === 'partial';
      var bg = isOk ? 'rgba(16, 185, 129, 0.15)' : (isPartial ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)');
      var col = isOk ? '#10B981' : (isPartial ? '#F59E0B' : '#EF4444');
      var iconSvg = isOk 
        ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="display:inline-block;vertical-align:middle;"><polyline points="20 6 9 17 4 12"/></svg>' 
        : (isPartial 
          ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="display:inline-block;vertical-align:middle;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' 
          : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="display:inline-block;vertical-align:middle;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>');
      var uVal = item.user || '—';
      var statusLabel = isOk ? t('result_correct') : (isPartial ? '30% (qisman)' : t('result_wrong'));

      openHtml += '<div style="background:' + bg + ';color:' + col + ';border:1px solid ' + col + ';border-radius:8px;padding:6px 2px;text-align:center;font-size:11px;line-height:1.2;overflow:hidden;">';
      openHtml += '<div style="font-weight:700;font-size:11px;margin-bottom:2px;display:flex;align-items:center;justify-content:center;gap:3px;">#' + key + ' ' + iconSvg + '</div>';
      openHtml += '<div style="font-size:10px;text-overflow:ellipsis;overflow:hidden;white-space:nowrap;" title="' + escHtml(uVal) + '">' + t('compare_keys_you') + ' <b>' + escHtml(uVal) + '</b></div>';
      openHtml += '<div style="font-size:10px;font-weight:600;">' + statusLabel + '</div>';
      openHtml += '</div>';
    });
  }

  var html = '<div class="key-comparison-box" style="margin-top:14px;background:var(--bg-card, #1A1D2D);border:1px solid var(--border, rgba(255,255,255,0.08));border-radius:14px;padding:16px;">';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid var(--border, rgba(255,255,255,0.08));flex-wrap:wrap;gap:8px;">';
  html += '<div><h4 style="margin:0;font-size:15px;font-weight:700;color:var(--text, #FFF);">' + t('compare_keys_title') + '</h4><span style="font-size:12px;color:var(--text-muted, #94A3B8);">' + t('compare_keys_sub') + '</span></div>';
  html += '<div style="font-size:13px;font-weight:700;padding:4px 12px;border-radius:999px;background:' + (totalCorrect >= 28 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)') + ';color:' + (totalCorrect >= 28 ? '#10B981' : '#EF4444') + ';border:1px solid ' + (totalCorrect >= 28 ? '#10B981' : '#EF4444') + ';">' + totalCorrect + ' / 55 ' + t('compare_keys_correct_suffix') + '</div>';
  html += '</div>';

  // 1-bosqich bloki
  html += '<div style="margin-bottom:16px;">';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">';
  html += '<span style="font-size:13px;font-weight:600;color:var(--primary, #6366F1);">' + t('compare_keys_stage1') + '</span>';
  html += '<span style="font-size:11px;font-weight:600;color:var(--text-muted, #94A3B8);">' + totalClosed + ' / 35 ' + t('compare_keys_correct_suffix') + '</span>';
  html += '</div>';
  html += '<div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(64px, 1fr));gap:6px;">' + closedHtml + '</div>';
  html += '</div>';

  // 2-bosqich bloki
  html += '<div>';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">';
  html += '<span style="font-size:13px;font-weight:600;color:var(--primary, #6366F1);">' + t('compare_keys_stage2') + '</span>';
  html += '<span style="font-size:11px;font-weight:600;color:var(--text-muted, #94A3B8);">' + totalOpen + ' / 20 ' + t('compare_keys_correct_suffix') + '</span>';
  html += '</div>';
  html += '<div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(78px, 1fr));gap:6px;">' + openHtml + '</div>';
  html += '</div>';

  html += '</div>';
  container.innerHTML = html;
}


function closeResultModal(e) {
  if (e && e.target && e.target.id !== 'result-modal') return;
  var modal = document.getElementById('result-modal');
  if (modal) modal.style.display = 'none';
}

// ── HEADER UPDATE ────────────────────────────────
function updateHeaderUser() {
  var u = state.userInfo;
  var tgU = state.tgUser;
  var name = (u && u.fullname) || (tgU && tgU.first_name) || 'F';
  var el = document.getElementById('header-avatar');
  if (el) el.textContent = name.charAt(0).toUpperCase();
}

// ── HELPERS ─────────────────────────────────────
function computeStatus(testsCount, avgScore) {
  var starSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
  if (testsCount === 0) return { label: t('status_new'), icon: starSvg, cls: 'status-beginner' };
  if (avgScore >= 40) return { label: t('status_gold'), icon: starSvg, cls: 'status-gold' };
  if (avgScore >= 30) return { label: t('status_silver'), icon: starSvg, cls: 'status-silver' };
  if (avgScore >= 20) return { label: t('status_bronze'), icon: starSvg, cls: 'status-bronze' };
  return { label: t('status_learner'), icon: starSvg, cls: 'status-beginner' };
}

function getGradeFromScore(score, maxScore) {
  var s = parseFloat(score) || 0;
  var max = parseFloat(maxScore) || 100;

  // Agar ball 0 yoki undan kam bo'lsa, darhol daraja berilmasin
  if (s <= 0) return 'Yetarli emas';

  var pct = (max > 0) ? (s / max * 100) : s;
  
  if (pct >= 86 && s >= 70) return 'A+';
  if (pct >= 75 && s >= 65) return 'A';
  if (pct >= 65 && s >= 60) return 'B+';
  if (pct >= 60 && s >= 55) return 'B';
  if (pct >= 55 && s >= 50) return 'C+';
  if (pct >= 46 && s >= 46) return 'C';
  
  return 'Yetarli emas';
}

function gradeToClass(grade) {
  if (!grade) return 'grade-2';
  var g = String(grade).toUpperCase();
  if (g.startsWith('A')) return 'grade-5';
  if (g.startsWith('B')) return 'grade-4';
  if (g.startsWith('C')) return 'grade-3';
  return 'grade-2';
}

function formatDate(ts) {
  if (!ts) return '\u2014';
  var lang = localStorage.getItem(LS_LANG) || 'uz';
  var locale = lang === 'ru' ? 'ru-RU' : (lang === 'en' ? 'en-US' : 'uz-UZ');
  var d = new Date(ts * 1000);
  return d.toLocaleDateString(locale, { timeZone: 'Asia/Tashkent', day:'2-digit', month:'2-digit', year:'numeric' }) +
    ' ' + d.toLocaleTimeString(locale, { timeZone: 'Asia/Tashkent', hour:'2-digit', minute:'2-digit', hour12: false });
}

function formatDateOnly(ts) {
  if (!ts) return '\u2014';
  var lang = localStorage.getItem(LS_LANG) || 'uz';
  var locale = lang === 'ru' ? 'ru-RU' : (lang === 'en' ? 'en-US' : 'uz-UZ');
  var d = new Date(ts * 1000);
  return d.toLocaleDateString(locale, { timeZone: 'Asia/Tashkent', day:'2-digit', month:'2-digit', year:'numeric' });
}

function formatTimeOnly(ts) {
  if (!ts) return '';
  var lang = localStorage.getItem(LS_LANG) || 'uz';
  var locale = lang === 'ru' ? 'ru-RU' : (lang === 'en' ? 'en-US' : 'uz-UZ');
  var d = new Date(ts * 1000);
  return d.toLocaleTimeString(locale, { timeZone: 'Asia/Tashkent', hour:'2-digit', minute:'2-digit', hour12: false });
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showToast(msg) {
  var toast = document.getElementById('toast');
  if (!toast) return;
  var displayMsg = msg || '';
  toast.textContent = displayMsg;
  toast.classList.add('show');
  clearTimeout(window._toastTimeout);
  window._toastTimeout = setTimeout(function() { toast.classList.remove('show'); }, 2200);
}

function copyTextToClipboard(text, successMsg) {
  if (!text) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(String(text)).then(function() {
      showToast(successMsg || 'Nusxa olindi!');
    }).catch(function() {
      fallbackCopy(text, successMsg);
    });
  } else {
    fallbackCopy(text, successMsg);
  }
  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    try {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
    } catch(e) {}
  }
}

function fallbackCopy(text, successMsg) {
  var ta = document.createElement('textarea');
  ta.value = String(text);
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    showToast(successMsg || 'Nusxa olindi!');
  } catch(e) {}
  document.body.removeChild(ta);
}

// ── ONBOARDING / BOT QO'LLANMA OYNASI ───────────
var currentOnboardingSlide = 0;
var totalOnboardingSlides = 4;

function renderOnboardingSlides() {
  var container = document.getElementById('onboarding-slides-container');
  if (!container) return;
  container.innerHTML =
    '<!-- Slide 0: Asosiy -->' +
    '<div class="onboarding-slide" id="onboarding-slide-0">' +
      '<div style="width:72px;height:72px;border-radius:24px;background:rgba(59,130,246,0.12);color:#3B82F6;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;box-shadow:0 8px 22px rgba(59,130,246,0.2);"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg></div>' +
      '<div style="display:inline-block;padding:3px 12px;border-radius:20px;background:rgba(59,130,246,0.12);color:#3B82F6;font-size:11.5px;font-weight:800;letter-spacing:0.5px;margin-bottom:8px;">' + t('ob_slide0_badge') + '</div>' +
      '<h3 style="font-size:19px;font-weight:900;color:var(--text);margin-bottom:8px;">' + t('ob_slide0_title') + '</h3>' +
      '<p style="font-size:13.5px;color:var(--text-muted);line-height:1.55;margin:0 auto 12px;max-width:310px;">' + t('ob_slide0_desc') + '</p>' +
      '<div style="background:var(--bg-body);border:1px solid var(--border);border-radius:14px;padding:10px 14px;display:flex;align-items:center;justify-content:center;gap:10px;font-size:12.5px;color:var(--text);font-weight:600;">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--primary);flex-shrink:0;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> <span>' + t('ob_slide0_feat') + '</span>' +
      '</div>' +
    '</div>' +

    '<!-- Slide 1: Testlar -->' +
    '<div class="onboarding-slide" id="onboarding-slide-1" style="display:none;">' +
      '<div style="width:72px;height:72px;border-radius:24px;background:rgba(16,185,129,0.12);color:#10B981;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;box-shadow:0 8px 22px rgba(16,185,129,0.2);"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg></div>' +
      '<div style="display:inline-block;padding:3px 12px;border-radius:20px;background:rgba(16,185,129,0.12);color:#10B981;font-size:11.5px;font-weight:800;letter-spacing:0.5px;margin-bottom:8px;">' + t('ob_slide1_badge') + '</div>' +
      '<h3 style="font-size:19px;font-weight:900;color:var(--text);margin-bottom:8px;">' + t('ob_slide1_title') + '</h3>' +
      '<p style="font-size:13.5px;color:var(--text-muted);line-height:1.55;margin:0 auto 12px;max-width:310px;">' + t('ob_slide1_desc') + '</p>' +
      '<div style="background:var(--bg-body);border:1px solid var(--border);border-radius:14px;padding:10px 14px;display:flex;align-items:center;justify-content:center;gap:10px;font-size:12.5px;color:var(--text);font-weight:600;">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:#10B981;flex-shrink:0;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> <span>' + t('ob_slide1_feat') + '</span>' +
      '</div>' +
    '</div>' +

    '<!-- Slide 2: Profil -->' +
    '<div class="onboarding-slide" id="onboarding-slide-2" style="display:none;">' +
      '<div style="width:72px;height:72px;border-radius:24px;background:rgba(245,158,11,0.12);color:#F59E0B;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;box-shadow:0 8px 22px rgba(245,158,11,0.2);"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>' +
      '<div style="display:inline-block;padding:3px 12px;border-radius:20px;background:rgba(245,158,11,0.12);color:#F59E0B;font-size:11.5px;font-weight:800;letter-spacing:0.5px;margin-bottom:8px;">' + t('ob_slide2_badge') + '</div>' +
      '<h3 style="font-size:19px;font-weight:900;color:var(--text);margin-bottom:8px;">' + t('ob_slide2_title') + '</h3>' +
      '<p style="font-size:13.5px;color:var(--text-muted);line-height:1.55;margin:0 auto 12px;max-width:310px;">' + t('ob_slide2_desc') + '</p>' +
      '<div style="background:var(--bg-body);border:1px solid var(--border);border-radius:14px;padding:10px 14px;display:flex;align-items:center;justify-content:center;gap:10px;font-size:12.5px;color:var(--text);font-weight:600;">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:#F59E0B;flex-shrink:0;"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg> <span>' + t('ob_slide2_feat') + '</span>' +
      '</div>' +
    '</div>' +

    '<!-- Slide 3: Mavzu -->' +
    '<div class="onboarding-slide" id="onboarding-slide-3" style="display:none;">' +
      '<div style="width:72px;height:72px;border-radius:24px;background:rgba(139,92,246,0.12);color:#8B5CF6;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;box-shadow:0 8px 22px rgba(139,92,246,0.2);gap:6px;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></div>' +
      '<div style="display:inline-block;padding:3px 12px;border-radius:20px;background:rgba(139,92,246,0.12);color:#8B5CF6;font-size:11.5px;font-weight:800;letter-spacing:0.5px;margin-bottom:8px;">' + t('ob_slide3_badge') + '</div>' +
      '<h3 style="font-size:19px;font-weight:900;color:var(--text);margin-bottom:8px;">' + t('ob_slide3_title') + '</h3>' +
      '<p style="font-size:13.5px;color:var(--text-muted);line-height:1.55;margin:0 auto 12px;max-width:310px;">' + t('ob_slide3_desc') + '</p>' +
      '<div style="background:var(--bg-body);border:1px solid var(--border);border-radius:14px;padding:10px 14px;display:flex;align-items:center;justify-content:center;gap:12px;font-size:12.5px;color:var(--text);font-weight:700;">' +
        '<span>' + t('ob_slide3_light') + '</span> <span style="color:var(--text-muted);display:inline-flex;align-items:center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg></span> <span>' + t('ob_slide3_dark') + '</span>' +
      '</div>' +
    '</div>';

  goOnboardingSlide(currentOnboardingSlide || 0);
}

function openOnboardingModal() {
  currentOnboardingSlide = 0;
  renderOnboardingSlides();
  var modal = document.getElementById('onboarding-modal');
  if (modal) {
    modal.style.display = 'flex';
    setTimeout(function() {
      modal.classList.add('open');
    }, 20);
  }
}

function closeOnboardingModal() {
  var modal = document.getElementById('onboarding-modal');
  if (modal) {
    modal.classList.remove('open');
    setTimeout(function() {
      modal.style.display = 'none';
    }, 280);
  }
}

function goOnboardingSlide(idx) {
  currentOnboardingSlide = idx;
  for (var i = 0; i < totalOnboardingSlides; i++) {
    var slide = document.getElementById('onboarding-slide-' + i);
    var dot = document.getElementById('ob-dot-' + i);
    if (slide) {
      if (i === idx) {
        slide.style.display = 'block';
        slide.classList.add('active');
      } else {
        slide.style.display = 'none';
        slide.classList.remove('active');
      }
    }
    if (dot) {
      if (i === idx) {
        dot.classList.add('active');
      } else {
        dot.classList.remove('active');
      }
    }
  }

  var btnNext = document.getElementById('btn-onboarding-next') || document.getElementById('onboarding-next-btn');
  if (btnNext) {
    if (idx === totalOnboardingSlides - 1) {
      btnNext.innerHTML = t('btn_finish');
    } else {
      btnNext.innerHTML = t('btn_next');
    }
  }
}

function nextOnboardingSlide() {
  if (currentOnboardingSlide < totalOnboardingSlides - 1) {
    goOnboardingSlide(currentOnboardingSlide + 1);
  } else {
    finishOnboarding();
  }
}

function finishOnboarding() {
  localStorage.setItem('onboarding_nav_tour_seen', 'true');
  closeOnboardingModal();
  showToast(t('toast_tour_done'));
}

// ──────────────────────────────────────────────────────────


// Global Scope eksport (HTML onclick va barcha tashqi modullar uchun)
window.state = state;
window.switchTab = switchTab;
window.switchHomeSubtab = switchHomeSubtab;
window.switchAdminSubtab = switchAdminSubtab;
window.filterMyTests = filterMyTests;
window.dismissSplash = dismissSplash;
window.finishSplashImmediately = dismissSplash;
window.launchApp = launchApp;
window.initApp = initApp;
window.getAuthHeaders = getAuthHeaders;
window.apiGet = apiGet;
window.showToast = showToast;
window.escHtml = escHtml;
window.formatDate = formatDate;
window.formatDateOnly = formatDateOnly;
window.formatTimeOnly = formatTimeOnly;
window.getGradeFromScore = getGradeFromScore;
window.gradeToClass = gradeToClass;
window.toggleTheme = toggleTheme;
window.syncTelegramTheme = syncTelegramTheme;
window.showResultModal = showResultModal;
window.closeResultModal = closeResultModal;
window.promptCompareKeys = promptCompareKeys;
window.submitCompareKeys = submitCompareKeys;
window.renderKeyComparison = renderKeyComparison;
window.openPastTestResult = openPastTestResult;
window.showPastTestEndedModal = showPastTestEndedModal;
window.closePastTestModal = closePastTestModal;
window.handlePastTestCardClick = handlePastTestCardClick;
window.openEditProfileModal = openEditProfileModal;
window.closeEditProfileModal = closeEditProfileModal;
window.saveEditedProfile = saveEditedProfile;
window.deleteMyAccount = deleteMyAccount;
window.toggleProfileDetails = toggleProfileDetails;
window.toggleUserSimulationMode = toggleUserSimulationMode;
window.openAdminUserModal = openAdminUserModal;
window.toggleAdminUserInfo = toggleAdminUserInfo;
window.closeAdminUserModal = closeAdminUserModal;
window.updateUserStatusFromModal = updateUserStatusFromModal;
window.handleAdminUserSearch = handleAdminUserSearch;
window.setAdminUserFilter = setAdminUserFilter;
window.applyQuickTemplate = applyQuickTemplate;
window.updateBroadcastCharCount = updateBroadcastCharCount;
window.clearBroadcastText = clearBroadcastText;
window.sendAdminBroadcast = sendAdminBroadcast;
window.openOnboardingModal = openOnboardingModal;
window.closeOnboardingModal = closeOnboardingModal;
window.finishOnboarding = finishOnboarding;
window.loadActiveTests = loadActiveTests;
window.loadMyResults = loadMyResults;
window.loadAllUsers = loadAllUsers;
window.openTestSolving = openTestSolving;
window.startTestInBot = startTestInBot;
window.returnToTelegramChat = returnToTelegramChat;
window.showTestNotStartedAlert = showTestNotStartedAlert;
window.goToBotRegister = goToBotRegister;
window.checkRegistrationStatus = checkRegistrationStatus;
window.closeUnregisteredModal = closeUnregisteredModal;
window.cycleLang = cycleLang;
