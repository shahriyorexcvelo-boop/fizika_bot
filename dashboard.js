/**
 * Shohruh Fizika — MacBook Pro Admin Dashboard
 * High-performance, Real-time Desktop Web Application
 */

const State = {
  activeTab: 'overview',
  overview: null,
  submissions: [],
  users: [],
  tests: [],
  logs: [],
  overviewLogs: [],
  submissionsFilter: 'all',
  submissionsTestFilter: '',
  usersFilter: 'all',
  userTestsFilter: null,
  globalSearch: '',
  autoRefresh: true,
  refreshTimer: null,
  currentModalSubmission: null,
  currentModalTest: null,
  activityDayFilter: 'all'
};

// ----------------------------------------------------
// VECTOR SVG ICON HELPERS (Replaces all emojis)
// ----------------------------------------------------
const Icons = {
  check: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:2px;"><polyline points="20 6 9 17 4 12"/></svg>`,
  clock: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:2px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  ban: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:2px;"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>`,
  eye: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:2px;"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`,
  copy: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`,
  trash: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:2px;"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>`,
  calendar: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:4px;"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/></svg>`,
  megaphone: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px;"><path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/></svg>`,
  lock: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px;"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
  play: `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
  pause: `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`,
  activitySubmission: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 21 8 0"/><path d="M12 17v4"/><path d="M7 4h10"/><path d="M17 4v8a5 5 0 0 1-10 0V4"/><path d="M3 9a4 4 0 0 0 4 4"/><path d="M21 9a4 4 0 0 1-4 4"/></svg>`,
  activityLate: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  activityUser: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
};

// ----------------------------------------------------
// SMART UZBEK DATE & DAY HELPERS
// ----------------------------------------------------
const UZB_DAYS = ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba'];
const UZB_DAYS_SHORT = ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'];
const UZB_MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'];

function parseToDateObj(timestampOrStr) {
  if (!timestampOrStr) return null;
  if (typeof timestampOrStr === 'number') {
    return new Date(timestampOrStr * 1000);
  }
  if (/^\d+$/.test(String(timestampOrStr).trim())) {
    return new Date(parseInt(timestampOrStr, 10) * 1000);
  }
  if (typeof timestampOrStr === 'string' && timestampOrStr.includes('.')) {
    const parts = timestampOrStr.trim().split(' ');
    const dParts = parts[0].split('.');
    const tParts = (parts[1] || '00:00:00').split(':');
    return new Date(
      parseInt(dParts[2], 10),
      parseInt(dParts[1], 10) - 1,
      parseInt(dParts[0], 10),
      parseInt(tParts[0], 10),
      parseInt(tParts[1], 10),
      parseInt(tParts[2] || 0, 10)
    );
  }
  const d = new Date(timestampOrStr);
  return isNaN(d.getTime()) ? null : d;
}

function formatUzbSmartDateTime(timestampOrStr) {
  const dateObj = parseToDateObj(timestampOrStr);
  if (!dateObj) {
    return {
      dayBadgeText: '—',
      dayBadgeClass: 'day-chip-past',
      groupKey: 'earlier',
      groupTitle: 'Avvalgi kunlar',
      timeStr: '—',
      fullDate: '—',
      dateOnly: '—'
    };
  }

  // Now in Tashkent time (UTC+5)
  const now = new Date();
  const utcNow = now.getTime() + (now.getTimezoneOffset() * 60000);
  const nowUzb = new Date(utcNow + (3600000 * 5));

  const eventYear = dateObj.getFullYear();
  const eventMonth = dateObj.getMonth();
  const eventDate = dateObj.getDate();
  const eventDay = dateObj.getDay();

  const nowYear = nowUzb.getFullYear();
  const nowMonth = nowUzb.getMonth();
  const nowDate = nowUzb.getDate();

  const todayMidnight = new Date(nowYear, nowMonth, nowDate).getTime();
  const eventMidnight = new Date(eventYear, eventMonth, eventDate).getTime();
  const diffDays = Math.round((todayMidnight - eventMidnight) / (86400 * 1000));

  const dayNameFull = UZB_DAYS[eventDay];
  const dayNameShort = UZB_DAYS_SHORT[eventDay];

  const h = String(dateObj.getHours()).padStart(2, '0');
  const m = String(dateObj.getMinutes()).padStart(2, '0');
  const s = String(dateObj.getSeconds()).padStart(2, '0');
  const timeStr = `${h}:${m}:${s}`;
  const dStr = `${String(eventDate).padStart(2, '0')}.${String(eventMonth + 1).padStart(2, '0')}.${eventYear}`;

  let dayBadgeText = '';
  let dayBadgeClass = '';
  let groupKey = 'earlier';
  let groupTitle = `${dayNameFull}, ${eventDate}-${UZB_MONTHS[eventMonth]}`;

  if (diffDays === 0) {
    dayBadgeText = `Bugun (${dayNameShort})`;
    dayBadgeClass = 'day-chip-today';
    groupKey = 'today';
    groupTitle = `Bugun (${dayNameFull}, ${eventDate}-${UZB_MONTHS[eventMonth]})`;
  } else if (diffDays === 1) {
    dayBadgeText = `Kecha (${dayNameShort})`;
    dayBadgeClass = 'day-chip-yesterday';
    groupKey = 'yesterday';
    groupTitle = `Kecha (${dayNameFull}, ${eventDate}-${UZB_MONTHS[eventMonth]})`;
  } else if (diffDays === 2) {
    dayBadgeText = `Avvalgi kun (${dayNameShort})`;
    dayBadgeClass = 'day-chip-earlier';
    groupKey = 'earlier';
    groupTitle = `Avvalgi kun (${dayNameFull}, ${eventDate}-${UZB_MONTHS[eventMonth]})`;
  } else {
    dayBadgeText = `${dayNameShort}, ${eventDate}-${UZB_MONTHS[eventMonth].slice(0, 3)}`;
    dayBadgeClass = 'day-chip-past';
    groupKey = 'past';
    groupTitle = `${dayNameFull}, ${eventDate}-${UZB_MONTHS[eventMonth]} ${eventYear}`;
  }

  return {
    diffDays,
    dayBadgeText,
    dayBadgeClass,
    groupKey,
    groupTitle,
    timeStr,
    fullDate: `${dStr} ${timeStr}`,
    dateOnly: dStr,
    dayName: dayNameFull
  };
}

// ----------------------------------------------------
// macOS BOOT ANIMATION — MAIN APP STYLE
// ----------------------------------------------------
function startBootCanvas() {
  var canvas = document.getElementById('boot-splash-canvas');
  if (!canvas) return null;
  var ctx = canvas.getContext('2d');
  if (!ctx) return null;

  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  var symbols = ['∞', 'π', '∑', '∫', '√x', 'f(x)', '∆', 'θ', 'λ', '≈', '≠', 'e²', 'α', 'β', '∂y', 'lim', 'dx', '∇'];
  var count = Math.min(28, Math.max(16, Math.floor(canvas.width / 18)));
  var particles = [];
  for (var i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      char: symbols[Math.floor(Math.random() * symbols.length)],
      size: 13 + Math.random() * 20,
      vx: (Math.random() - 0.5) * 0.4,
      vy: -0.3 - Math.random() * 0.7,
      opacity: 0.1 + Math.random() * 0.4,
      pulseSpeed: 0.018 + Math.random() * 0.025,
      angle: Math.random() * Math.PI * 2,
      spinSpeed: (Math.random() - 0.5) * 0.012
    });
  }

  var animId = null;
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.x += p.vx; p.y += p.vy; p.angle += p.spinSpeed;
      p.opacity += Math.sin(Date.now() * p.pulseSpeed) * 0.004;
      if (p.opacity < 0.08) p.opacity = 0.08;
      if (p.opacity > 0.55) p.opacity = 0.55;
      if (p.y < -30) { p.y = canvas.height + 30; p.x = Math.random() * canvas.width; }
      if (p.x < -30) p.x = canvas.width + 30;
      if (p.x > canvas.width + 30) p.x = -30;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.angle);
      ctx.font = 'bold ' + p.size + 'px serif';
      ctx.fillStyle = 'rgba(0, 200, 167, ' + p.opacity + ')';
      ctx.shadowColor = 'rgba(0, 163, 137, 0.4)';
      ctx.shadowBlur = 8;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(p.char, 0, 0);
      ctx.restore();
    }
    animId = requestAnimationFrame(draw);
  }
  animId = requestAnimationFrame(draw);
  return function stop() { if (animId) cancelAnimationFrame(animId); };
}

var _bootCanvasStop = null;

function enterFullscreen() {
  var el = document.documentElement;
  try {
    if (el.requestFullscreen) el.requestFullscreen();
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
    else if (el.mozRequestFullScreen) el.mozRequestFullScreen();
    else if (el.msRequestFullscreen) el.msRequestFullscreen();
  } catch(e) {}
}

function skipBootSplash() {
  var splash = document.getElementById('mac-boot-splash');
  if (!splash) return;
  if (_bootCanvasStop) _bootCanvasStop();
  splash.classList.add('hidden');
  setTimeout(() => {
    if (splash.parentNode) splash.remove();
    // To'liq ekranga o'tish
    enterFullscreen();
  }, 700);
}
window.skipBootSplash = skipBootSplash;

function runBootAnimation() {
  var splash = document.getElementById('mac-boot-splash');
  var bar = document.getElementById('boot-progress-bar');
  if (!splash) return;

  // Start floating math particles
  _bootCanvasStop = startBootCanvas();

  if (!bar) { setTimeout(skipBootSplash, 1500); return; }

  // Progress animation: smoothly reaches 100% in 1250ms, then splash closes at exactly 1500ms (1.5s)
  var startTime = Date.now();
  var duration = 1250;
  var iv = setInterval(function() {
    var elapsed = Date.now() - startTime;
    var pct = Math.min(100, Math.round((elapsed / duration) * 100));
    bar.style.width = pct + '%';
    if (pct >= 100) {
      clearInterval(iv);
      setTimeout(skipBootSplash, 250); // 1250 + 250 = 1500ms (1.5 soniya)
    }
  }, 20);
}

// ----------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  restoreCachedDashboard();
  runBootAnimation();
  initLiveClock();
  setupKeyboardShortcuts();
  fetchDashboardData();
  startAutoRefresh();
});

function restoreCachedDashboard() {
  try {
    const raw = sessionStorage.getItem('bm_cached_overview');
    if (raw) {
      const data = JSON.parse(raw);
      if (data && data.success && data.summary) {
        State.overview = data.summary;
        State.tests = data.tests || [];
        updateHeaderAndBadges(data.summary);
        renderOverviewData(data);
      }
    }
  } catch (e) {}
}

// Live Tashkent Clock (UTC+5)
function initLiveClock() {
  const update = () => {
    const el = document.getElementById('live-clock');
    if (!el) return;
    const now = new Date();
    // UTC+5 calculation
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const uzbDate = new Date(utc + (3600000 * 5));
    const h = String(uzbDate.getHours()).padStart(2, '0');
    const m = String(uzbDate.getMinutes()).padStart(2, '0');
    const s = String(uzbDate.getSeconds()).padStart(2, '0');
    el.textContent = `${h}:${m}:${s}`;
  };
  update();
  setInterval(update, 1000);
}

// ----------------------------------------------------
// TAB SWITCHING
// ----------------------------------------------------
function switchDashboardTab(tabId) {
  State.activeTab = tabId;

  if (typeof NavState !== 'undefined') {
    const sIdx = NavState.sidebarTabs.indexOf(tabId);
    if (sIdx !== -1) NavState.sidebarIndex = sIdx;
    clearTableRowSelection();
    clearSidebarFocus();
  }

  // Update navigation classes
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-tab') === tabId);
  });

  // Update Views
  document.querySelectorAll('.page-view').forEach(el => {
    el.classList.remove('active');
  });
  const targetView = document.getElementById(`view-${tabId}`);
  if (targetView) targetView.classList.add('active');

  // Update Title & Subtitle
  const titles = {
    overview: { t: 'Dashboard', sub: 'Umumiy tizim holati, statistika va faolliklar' },
    submissions: { t: 'Natijalar Bazasi', sub: 'O\'quvchilarning ishlagan barcha test javoblari va vaqtlari' },
    users: { t: 'Foydalanuvchilar Bazasi', sub: 'Bot a\'zolari va o\'quvchilar ro\'yxati' },
    tests: { t: 'Testlar Boshqaruvi', sub: 'Yaratilgan barcha milliy sertifikat va blok testlar' },
    activity: { t: 'Jarayonlar & Audit', sub: 'Tizimda sodir bo\'lgan barcha hodisalar jurnali' },
    database: { t: 'Baza & SQL Konsoli', sub: 'PostgreSQL Cloud ma\'lumotlar bazasi va to\'g\'ridan-to\'g\'ri so\'rovlar' }
  };

  const info = titles[tabId] || { t: 'Boshqaruv', sub: '' };
  document.getElementById('page-title').textContent = info.t;
  document.getElementById('page-subtitle').textContent = info.sub;

  // Render view
  renderCurrentView();
}

function renderCurrentView() {
  if (State.activeTab === 'overview') renderOverview();
  else if (State.activeTab === 'submissions') renderSubmissions();
  else if (State.activeTab === 'users') renderUsers();
  else if (State.activeTab === 'tests') renderTests();
  else if (State.activeTab === 'activity') renderLogs();
  else if (State.activeTab === 'database') renderDatabase();
}

// ----------------------------------------------------
// DATA FETCHING (REAL-TIME)
// ----------------------------------------------------
let _isFetchingDashboard = false;
let _lastOverviewFetchTime = 0;

async function fetchDashboardData(manual = false) {
  if (_isFetchingDashboard && !manual) return;
  const now = Date.now();
  if (!manual && (now - _lastOverviewFetchTime < 3000)) return;

  _isFetchingDashboard = true;
  _lastOverviewFetchTime = now;

  try {
    // 1. Overview & Stats
    const url = manual ? '/api/dashboard/overview?refresh=true' : '/api/dashboard/overview';
    const resOverview = await fetch(url);
    if (resOverview.ok) {
      const data = await resOverview.json();
      if (data.success) {
        try { sessionStorage.setItem('bm_cached_overview', JSON.stringify(data)); } catch (e) {}
        State.overview = data.summary;
        State.tests = data.tests || [];
        updateHeaderAndBadges(data.summary);
        if (State.activeTab === 'overview') {
          renderOverviewData(data);
        }
      }
    }

    // 2. Fetch specific tab data if active
    if (State.activeTab === 'submissions') {
      await fetchSubmissionsData();
    } else if (State.activeTab === 'users') {
      await fetchUsersData();
    } else if (State.activeTab === 'tests') {
      await fetchTestsData();
    } else if (State.activeTab === 'activity') {
      await fetchLogsData();
    }

    if (manual) {
      showToast('Ma\'lumotlar muvaffaqiyatli yangilandi!', 'success');
    }
  } catch (err) {
    console.error('Fetch error:', err);
    if (manual) showToast('Bog\'lanishda xatolik yuz berdi', 'danger');
  } finally {
    _isFetchingDashboard = false;
  }
}

async function fetchSubmissionsData() {
  const res = await fetch('/api/dashboard/submissions?limit=1500');
  if (res.ok) {
    const data = await res.json();
    if (data.success) {
      State.submissions = data.submissions || [];
      renderSubmissions();
      // Populate test filter dropdown
      populateTestFilterDropdown();
    }
  }
}

async function fetchUsersData() {
  const res = await fetch('/api/dashboard/users');
  if (res.ok) {
    const data = await res.json();
    if (data.success) {
      State.users = data.users || [];
      renderUsers();
    }
  }
}

async function fetchTestsData() {
  const res = await fetch('/api/dashboard/tests');
  if (res.ok) {
    const data = await res.json();
    if (data.success) {
      State.tests = data.tests || [];
      renderTests();
    }
  }
}

async function fetchLogsData() {
  const res = await fetch('/api/dashboard/logs?limit=150');
  if (res.ok) {
    const data = await res.json();
    if (data.success) {
      State.logs = data.logs || [];
      renderLogs();
    }
  }
}

function updateHeaderAndBadges(summary) {
  if (!summary) return;
  document.getElementById('badge-submissions-count').textContent = summary.total_submissions || 0;
  document.getElementById('badge-users-count').textContent = summary.total_users || 0;
  document.getElementById('badge-tests-count').textContent = summary.total_tests || 0;

  // Stat Cards in Overview
  const elTotalUsers = document.getElementById('stat-total-users');
  if (elTotalUsers) {
    elTotalUsers.textContent = summary.total_users || 0;
    document.getElementById('stat-approved-users').textContent = `${summary.approved_users || 0} faol`;
    document.getElementById('stat-pending-users').textContent = `${summary.pending_users || 0} kutilmoqda`;
    document.getElementById('stat-blocked-users').textContent = `${summary.blocked_users || 0} blok`;
    
    document.getElementById('stat-total-subs').textContent = summary.total_submissions || 0;
    document.getElementById('stat-today-subs').textContent = `+${summary.today_submissions || 0} bugun`;
    document.getElementById('stat-late-subs').textContent = `${summary.late_submissions || 0} kechikkan`;

    document.getElementById('stat-avg-score').textContent = `${summary.avg_score || 0} ball`;
    document.getElementById('stat-avg-corr').textContent = `${summary.avg_correct || 0} ta`;

    document.getElementById('stat-total-tests').textContent = `${summary.total_tests || 0} ta`;
    document.getElementById('stat-active-tests').textContent = `${summary.active_tests || 0} ta faol`;
    
    // DB Explorer counts
    const elTblUsers = document.getElementById('db-tbl-users');
    if (elTblUsers) elTblUsers.textContent = `${summary.total_users || 0} qator`;
    const elTblSubs = document.getElementById('db-tbl-subs');
    if (elTblSubs) elTblSubs.textContent = `${summary.total_submissions || 0} qator`;
    const elTblTests = document.getElementById('db-tbl-tests');
    if (elTblTests) elTblTests.textContent = `${summary.total_tests || 0} qator`;
  }
}

// ----------------------------------------------------
// OVERVIEW RENDERING
// ----------------------------------------------------
function renderOverview() {
  if (State.overview) {
    updateHeaderAndBadges(State.overview);
  } else {
    fetchDashboardData();
  }
}

function renderOverviewData(data) {
  // 1. Recent Submissions
  const subsBody = document.getElementById('overview-recent-subs-body');
  if (subsBody) {
    const list = data.recent_submissions || [];
    if (list.length === 0) {
      subsBody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted);">Natijalar mavjud emas</td></tr>';
    } else {
      subsBody.innerHTML = list.slice(0, 8).map(s => {
        const usernameTag = s.username ? `<span style="color:var(--primary);font-size:11px;font-weight:700;">@${esc(s.username.replace(/^@/, ''))}</span>` : '';
        const lateBadge = s.is_late == 1 ? `<span class="badge badge-warning" style="margin-left:4px;">${Icons.clock}Kech</span>` : '';
        const dt = formatUzbSmartDateTime(s.submitted_at || s.submitted_at_fmt);
        return `
          <tr class="clickable-row" onclick="openSubmissionModal(${s.id})">
            <td>
              <div style="font-weight:700;font-size:13.5px;color:var(--text-main);">${esc(s.fullname || 'Foydalanuvchi')}</div>
              ${usernameTag}
            </td>
            <td><b style="color:var(--text-main);font-family:var(--font-mono);">#${esc(s.test_code || '')}</b></td>
            <td>
              <div class="time-cell-wrap">
                <span class="day-chip ${dt.dayBadgeClass}">${dt.dayBadgeText}</span>
                <span class="time-str-mono" style="font-size:11px;">${dt.timeStr}</span>
              </div>
            </td>
            <td>
              <span style="font-weight:800;color:var(--success);">${s.correct_count || 0} / ${s.total_count || 55}</span>
              ${lateBadge}
            </td>
            <td><b style="color:var(--primary);font-size:14px;">${s.score || 0} ball</b></td>
            <td onclick="event.stopPropagation();">
              <div style="display:inline-flex;gap:6px;align-items:center;">
                <button class="btn btn-secondary btn-sm" onclick="openSubmissionModal(${s.id})">${Icons.eye}Ko'rish</button>
                <button class="btn btn-danger btn-sm" onclick="openCancelSubModalById(${s.id})" title="Javobni bekor qilish">${Icons.ban}Bekor qilish</button>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // 2. Activity Timeline with Day Groups & Priority
  State.overviewLogs = data.activity_logs || [];
  renderOverviewActivities(State.overviewLogs);
}

function setActivityDayFilter(filter, btn) {
  State.activityDayFilter = filter;
  if (btn && btn.parentElement) {
    btn.parentElement.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }
  renderOverviewActivities(State.overviewLogs);
}
window.setActivityDayFilter = setActivityDayFilter;

function renderOverviewActivities(logs) {
  const container = document.getElementById('overview-activity-list');
  if (!container) return;

  if (!logs || logs.length === 0) {
    container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:24px;">Faolliklar mavjud emas</div>';
    return;
  }

  const groups = {
    today: { title: 'Bugun', items: [] },
    yesterday: { title: 'Kecha', items: [] },
    earlier: { title: 'Undan oldingi kunlar', items: [] }
  };

  logs.forEach(l => {
    const dt = formatUzbSmartDateTime(l.time || l.time_fmt);
    l._dt = dt;
    if (dt.groupKey === 'today') {
      groups.today.items.push(l);
      groups.today.title = dt.groupTitle;
    } else if (dt.groupKey === 'yesterday') {
      groups.yesterday.items.push(l);
      groups.yesterday.title = dt.groupTitle;
    } else {
      groups.earlier.items.push(l);
    }
  });

  const filter = State.activityDayFilter || 'all';

  const renderGroup = (key, grp, headerClass) => {
    if (grp.items.length === 0) {
      if (filter === key) {
        return `
          <div class="activity-day-group">
            <div class="activity-day-header ${headerClass}">
              <span>${Icons.calendar}${esc(grp.title)}</span>
              <span class="badge" style="font-size:10px;">0 ta amal</span>
            </div>
            <div style="font-size:12px;color:var(--text-muted);padding:10px 4px;">Ushbu kunda yangi amallar qayd etilmagan</div>
          </div>
        `;
      }
      return '';
    }

    const itemsHtml = grp.items.map(l => {
      const un = l.username ? ` (@${esc(l.username.replace(/^@/, ''))})` : '';
      return `
        <div class="activity-item">
          <div class="activity-icon-box">
            ${l.type === 'submission' ? Icons.activitySubmission : (l.type === 'late_submission' ? Icons.activityLate : Icons.activityUser)}
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:12.5px;font-weight:700;color:var(--text-main);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(l.title)}</div>
            <div style="font-size:11.5px;color:var(--text-muted);margin-top:1px;font-weight:500;">
              ${esc(l.user_name || '')}${un}
            </div>
            <div style="display:flex;align-items:center;gap:6px;margin-top:3px;">
              <span class="day-chip ${l._dt.dayBadgeClass}">${l._dt.dayBadgeText}</span>
              <span style="font-size:11px;font-family:var(--font-mono);color:var(--text-dim);font-weight:700;">${l._dt.timeStr}</span>
            </div>
          </div>
          <span class="badge badge-${l.badge_color || 'info'}" style="font-size:10px;flex-shrink:0;">${esc(l.badge || '')}</span>
        </div>
      `;
    }).join('');

    return `
      <div class="activity-day-group">
        <div class="activity-day-header ${headerClass}">
          <span>${Icons.calendar}${esc(grp.title)}</span>
          <span class="badge" style="font-size:10px;font-weight:800;">${grp.items.length} ta amal</span>
        </div>
        <div>${itemsHtml}</div>
      </div>
    `;
  };

  let renderedHtml = '';
  if (filter === 'today') {
    renderedHtml = renderGroup('today', groups.today, 'today');
  } else if (filter === 'yesterday') {
    renderedHtml = renderGroup('yesterday', groups.yesterday, 'yesterday');
  } else {
    // ALL: Prioritize Today's actions at top!
    if (groups.today.items.length === 0) {
      renderedHtml += `
        <div class="activity-day-group">
          <div class="activity-day-header today">
            <span>${Icons.calendar}Bugungi amallar</span>
            <span class="badge badge-warning" style="font-size:10px;">Bugun hozircha yangi amal yo'q</span>
          </div>
        </div>
      `;
    } else {
      renderedHtml += renderGroup('today', groups.today, 'today');
    }
    renderedHtml += renderGroup('yesterday', groups.yesterday, 'yesterday');
    renderedHtml += renderGroup('earlier', groups.earlier, 'earlier');
  }

  container.innerHTML = renderedHtml;
}

// ----------------------------------------------------
// SUBMISSIONS RENDERING & FILTERING
// ----------------------------------------------------
function setSubmissionsFilter(filter, btn) {
  State.submissionsFilter = filter;
  if (btn && btn.parentElement) {
    btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }
  renderSubmissions();
}

function filterSubmissionsByTest(testCode) {
  State.submissionsTestFilter = testCode;
  renderSubmissions();
}

function populateTestFilterDropdown() {
  const sel = document.getElementById('filter-test-select');
  if (!sel) return;
  const codes = [...new Set(State.submissions.map(s => String(s.test_code)).filter(Boolean))];
  const cur = sel.value;
  sel.innerHTML = '<option value="">Barcha testlar</option>' + 
    codes.map(c => `<option value="${esc(c)}" ${cur === c ? 'selected' : ''}>#${esc(c)} testi</option>`).join('');
}

function renderSubmissions() {
  const body = document.getElementById('submissions-table-body');
  if (!body) return;

  const q = State.globalSearch.toLowerCase().trim();
  const cleanQ = q.replace(/^@+/, '').trim();

  let filtered = State.submissions.filter(s => {
    // 1. Status filter
    if (State.submissionsFilter === 'ontime' && s.is_late == 1) return false;
    if (State.submissionsFilter === 'late' && s.is_late != 1) return false;

    // 2. Test filter
    if (State.submissionsTestFilter && String(s.test_code) !== String(State.submissionsTestFilter)) return false;

    // 3. Search query
    if (q) {
      const uName = (s.username || '').toLowerCase().replace(/^@+/, '').trim();
      const fn = (s.fullname || '').toLowerCase();
      const code = String(s.test_code || '').toLowerCase();
      const idStr = String(s.user_tg_id || '');
      const match = fn.includes(q) || fn.includes(cleanQ) || (uName && (uName.includes(cleanQ) || ('@' + uName).includes(q))) || code.includes(cleanQ) || idStr.includes(cleanQ);
      if (!match) return false;
    }
    return true;
  });

  const countBadge = document.getElementById('submissions-count-badge');
  if (countBadge) countBadge.textContent = `${filtered.length} ta`;

  if (filtered.length === 0) {
    body.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:32px;color:var(--text-muted);">Qidiruv bo\'yicha hech narsa topilmadi</td></tr>';
    return;
  }

  body.innerHTML = filtered.map((s, idx) => {
    const usernameTag = s.username ? `<span style="color:var(--primary);font-size:11.5px;font-weight:700;">@${esc(s.username.replace(/^@/, ''))}</span>` : '<span style="color:var(--text-dim);font-size:11px;">—</span>';
    
    // Status Badge
    let stBadge = '';
    if (s.status === 'rejected') {
      stBadge = `<span class="badge badge-danger" style="background:#EF4444;color:#fff;">${Icons.ban}Bekor qilingan</span>`;
    } else if (s.is_late == 1) {
      stBadge = `<span class="badge badge-warning">${Icons.clock}Kechikkan</span>`;
    } else {
      stBadge = `<span class="badge badge-success">${Icons.check}O'z vaqtida</span>`;
    }

    // Grade Badge
    const gr = s.grade || '—';
    let grColor = 'purple';
    if (gr === 'A+' || gr === 'A') grColor = 'success';
    else if (gr === 'B+' || gr === 'B') grColor = 'info';
    else if (gr === 'C+' || gr === 'C') grColor = 'warning';

    // Smart Date & Day Badge
    const dt = formatUzbSmartDateTime(s.submitted_at || s.submitted_at_fmt);

    return `
      <tr class="clickable-row" onclick="openSubmissionModal(${s.id})">
        <td style="color:var(--text-dim);font-weight:700;font-family:var(--font-mono);">${idx + 1}</td>
        <td>
          <div style="font-weight:700;font-size:13.5px;color:var(--text-main);">${esc(s.fullname || 'Foydalanuvchi')}</div>
          <div style="font-size:11px;color:var(--text-dim);font-family:var(--font-mono);font-weight:700;">ID: ${s.user_tg_id}</div>
        </td>
        <td>${usernameTag}</td>
        <td><span class="badge badge-info" style="font-family:var(--font-mono);font-size:11.5px;">#${esc(s.test_code || '')}</span></td>
        <td>
          <div class="time-cell-wrap">
            <span class="day-chip ${dt.dayBadgeClass}">${dt.dayBadgeText}</span>
            <span class="time-str-mono">${dt.fullDate}</span>
          </div>
        </td>
        <td>
          <b style="color:var(--success);font-size:13px;">${s.correct_count || 0}</b>
          <span style="color:var(--text-muted);font-size:11px;">/ ${s.total_count || 55}</span>
        </td>
        <td><b style="color:var(--primary);font-size:14.5px;">${s.score || 0} ball</b></td>
        <td><span class="badge badge-${grColor}">${esc(gr)}</span></td>
        <td>${stBadge}</td>
        <td style="text-align:right;" onclick="event.stopPropagation();">
          <div style="display:inline-flex;gap:6px;align-items:center;">
            <button class="btn btn-secondary btn-sm" onclick="openSubmissionModal(${s.id})">
              ${Icons.eye}Ko'rish
            </button>
            <button class="btn btn-danger btn-sm" onclick="openCancelSubModalById(${s.id})" title="Javobni bekor qilish">
              ${Icons.ban}Bekor qilish
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// ----------------------------------------------------
// USERS RENDERING & FILTERING
// ----------------------------------------------------
function setUsersFilter(filter, btn) {
  State.usersFilter = filter;
  if (btn && btn.parentElement) {
    btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }
  renderUsers();
}

function renderUsers() {
  const body = document.getElementById('users-table-body');
  if (!body) return;

  const q = State.globalSearch.toLowerCase().trim();
  const cleanQ = q.replace(/^@+/, '').trim();
  const isTestFilterActive = (State.userTestsFilter !== null && State.userTestsFilter !== undefined && State.userTestsFilter !== '');
  const targetTc = isTestFilterActive ? parseInt(State.userTestsFilter, 10) : null;

  let filtered = State.users.filter(u => {
    // 1. Status Filter
    const st = (u.status || 'pending').toLowerCase();
    if (State.usersFilter === 'approved' && st !== 'approved') return false;
    if (State.usersFilter === 'pending' && st !== 'pending') return false;
    if (State.usersFilter === 'blocked' && st !== 'blocked') return false;

    // 2. User Tests Count Filter (faqat raqam kiritilganda yoki preset tanlanganda)
    if (isTestFilterActive) {
      const tc = parseInt(u.tests_count || 0, 10);
      if (tc !== targetTc) return false;
    }

    // 3. Search query
    if (q) {
      const uName = (u.username || '').toLowerCase().replace(/^@+/, '').trim();
      const fn = (u.fullname || '').toLowerCase();
      const ph = (u.phone || '').toLowerCase();
      const idStr = String(u.tg_id || '');
      const match = fn.includes(q) || fn.includes(cleanQ) || (uName && (uName.includes(cleanQ) || ('@' + uName).includes(q))) || ph.includes(cleanQ) || idStr.includes(cleanQ);
      if (!match) return false;
    }
    return true;
  });

  const countBadge = document.getElementById('users-count-badge');
  if (countBadge) countBadge.textContent = `${filtered.length} nafar`;

  // Update header filter controls (preset buttons, clear button, bulk warn button)
  const clearBtn = document.getElementById('preset-tests-clear');
  if (clearBtn) clearBtn.style.display = isTestFilterActive ? 'inline-flex' : 'none';

  const p0 = document.getElementById('preset-tests-0');
  const p1 = document.getElementById('preset-tests-1');
  if (p0) p0.classList.toggle('active', isTestFilterActive && targetTc === 0);
  if (p1) p1.classList.toggle('active', isTestFilterActive && targetTc === 1);

  const warnAllBtn = document.getElementById('btn-warn-all-users');
  const warnAllCountLabel = document.getElementById('warn-all-count-label');
  if (warnAllBtn) {
    if (isTestFilterActive && filtered.length > 0) {
      warnAllBtn.style.display = 'inline-flex';
      if (warnAllCountLabel) warnAllCountLabel.textContent = `Barchasiga ogohlantirish (${filtered.length} ta)`;
    } else {
      warnAllBtn.style.display = 'none';
    }
  }

  if (filtered.length === 0) {
    body.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:32px;color:var(--text-muted);">${isTestFilterActive ? `${targetTc} ta test ishlagan foydalanuvchilar topilmadi` : "Foydalanuvchilar topilmadi"}</td></tr>`;
    return;
  }

  body.innerHTML = filtered.map(u => {
    const rawUsername = u.username ? u.username.replace(/^@/, '') : '';
    const usernameTag = rawUsername ? `<span style="color:var(--primary);font-size:12px;font-weight:700;">@${esc(rawUsername)}</span>` : '<span style="color:var(--text-dim);">—</span>';
    
    // Status Badge
    let stBadge = '';
    const st = (u.status || 'pending').toLowerCase();
    if (st === 'approved') stBadge = `<span class="badge badge-success">${Icons.check}Faol</span>`;
    else if (st === 'pending') stBadge = `<span class="badge badge-warning">${Icons.clock}Kutilmoqda</span>`;
    else if (st === 'blocked') stBadge = `<span class="badge badge-danger">${Icons.ban}Bloklangan</span>`;

    const regDt = formatUzbSmartDateTime(u.registered_at || u.registered_at_fmt);

    return `
      <tr class="clickable-row" onclick="openUserTestsModal(${u.tg_id}, '${esc(u.fullname || 'Foydalanuvchi')}', '${rawUsername ? '@' + rawUsername : ''}')">
        <td class="copyable-cell" onclick="event.stopPropagation(); copyToClipboard('${u.tg_id}', 'ID')" title="Nusxalash uchun bosing">
          <span class="copy-val" style="font-family:var(--font-mono);font-size:12px;color:var(--text-dim);font-weight:700;">${u.tg_id}</span>
          <span class="copy-icon">${Icons.copy}</span>
        </td>
        <td class="copyable-cell" onclick="event.stopPropagation(); copyToClipboard('${esc(u.fullname || '')}', 'Ism')" title="Nusxalash uchun bosing">
          <div class="copy-val" style="font-weight:700;font-size:13.5px;color:var(--text-main);display:inline-block;">${esc(u.fullname || 'Foydalanuvchi')}</div>
          <span class="copy-icon">${Icons.copy}</span>
        </td>
        <td class="copyable-cell" onclick="event.stopPropagation(); ${rawUsername ? `copyToClipboard('@${rawUsername}', 'Username')` : ''}" title="${rawUsername ? 'Nusxalash uchun bosing' : ''}">
          <span class="copy-val">${usernameTag}</span>
          ${rawUsername ? `<span class="copy-icon">${Icons.copy}</span>` : ''}
        </td>
        <td style="font-size:12px;color:var(--text-muted);font-weight:600;">${esc(u.phone || '—')}</td>
        <td>${stBadge}</td>
        <td>
          <div class="time-cell-wrap">
            <span class="day-chip ${regDt.dayBadgeClass}">${regDt.dayBadgeText}</span>
            <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim);font-weight:600;">${regDt.fullDate}</span>
          </div>
        </td>
        <td>
          <button type="button" class="user-tests-badge-btn" onclick="event.stopPropagation(); openUserTestsModal(${u.tg_id}, '${esc(u.fullname || 'Foydalanuvchi')}', '${rawUsername ? '@' + rawUsername : ''}')" title="Topshirgan barcha testlarini ko'rish">
            ${u.tests_count || 0} ta <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-left:2px;"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
        </td>
        <td style="text-align:right;" onclick="event.stopPropagation();">
          <div style="display:inline-flex;gap:6px;align-items:center;">
            ${isTestFilterActive ? `
              <button type="button" class="btn btn-warning btn-sm btn-warn-user" onclick="warnUserDirect(${u.tg_id}, ${u.tests_count || 0}, '${esc(u.fullname || 'Foydalanuvchi')}')" title="Telegram orqali rasmiy ogohlantirish yuborish">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                Ogohlantirish
              </button>
            ` : ''}
            ${st !== 'approved' ? `<button class="btn btn-secondary btn-sm" onclick="changeUserStatus(${u.tg_id}, 'approve')">${Icons.check}Faol</button>` : ''}
            ${st !== 'blocked' ? `<button class="btn btn-secondary btn-sm" onclick="changeUserStatus(${u.tg_id}, 'block')">${Icons.ban}Blok</button>` : ''}
            <button class="btn btn-danger btn-sm" onclick="changeUserStatus(${u.tg_id}, 'delete')">${Icons.trash}O'chirish</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// ----------------------------------------------------
// USER TESTS COUNT FILTER & DIRECT TELEGRAM WARNING
// ----------------------------------------------------
function setUserTestsCountFilter(val) {
  if (val === '' || val === null || val === undefined) {
    State.userTestsFilter = null;
  } else {
    const parsed = parseInt(val, 10);
    State.userTestsFilter = isNaN(parsed) || parsed < 0 ? null : parsed;
  }
  const input = document.getElementById('filter-user-tests-count');
  if (input && input.value !== (State.userTestsFilter !== null ? String(State.userTestsFilter) : '')) {
    input.value = State.userTestsFilter !== null ? State.userTestsFilter : '';
  }
  renderUsers();
}
window.setUserTestsCountFilter = setUserTestsCountFilter;

function applyUserTestsCountPreset(num) {
  const input = document.getElementById('filter-user-tests-count');
  if (input) input.value = num;
  setUserTestsCountFilter(num);
}
window.applyUserTestsCountPreset = applyUserTestsCountPreset;

function clearUserTestsCountFilter() {
  const input = document.getElementById('filter-user-tests-count');
  if (input) input.value = '';
  setUserTestsCountFilter(null);
}
window.clearUserTestsCountFilter = clearUserTestsCountFilter;

async function warnUserDirect(tgId, testsCount, fullname) {
  const countNum = parseInt(testsCount || 0, 10);
  const msgIntro = countNum === 0 
    ? `Hurmatli ${fullname}!\nSiz birorta ham test ishlamagansiz (0 ta). Bugungi testda qatnashmasangiz botdan chiqarib yuborilishingiz haqida rasmiy ogohlantirish yuborilsinmi?`
    : `Hurmatli ${fullname}!\nSiz hozirgacha faqat ${countNum} ta test ishlagansiz. Bugungi testda qatnashmasangiz botdan chiqarib yuborilishingiz haqida rasmiy ogohlantirish yuborilsinmi?`;

  if (!confirm(`⚠️ TELEGRAM RASMIY OGOHLANTIRISH:\n\n${msgIntro}`)) {
    return;
  }

  showToast(`Ogohlantirish yuborilmoqda: ${fullname}...`, 'info');
  try {
    const res = await fetch('/api/dashboard/warn-user', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tg_id: tgId,
        tests_count: countNum
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || `Ogohlantirish ${fullname} ga yetkazildi!`, 'success');
    } else if (data.blocked) {
      showToast(data.message, 'warning');
      loadData(false);
    } else {
      showToast(data.error || 'Xatolik yuz berdi', 'error');
    }
  } catch (err) {
    console.error('Warn user direct error:', err);
    showToast('Tarmoq xatosi: xabar yuborilmadi', 'error');
  }
}
window.warnUserDirect = warnUserDirect;

async function sendWarningToAllFilteredUsers() {
  if (State.userTestsFilter === null || State.userTestsFilter === undefined) return;
  const targetTc = parseInt(State.userTestsFilter, 10);
  
  // Find all users matching current active filter
  const targetUsers = State.users.filter(u => {
    const tc = parseInt(u.tests_count || 0, 10);
    if (tc !== targetTc) return false;
    const st = (u.status || 'pending').toLowerCase();
    if (State.usersFilter === 'approved' && st !== 'approved') return false;
    if (State.usersFilter === 'pending' && st !== 'pending') return false;
    if (State.usersFilter === 'blocked' && st !== 'blocked') return false;
    return true;
  });

  if (targetUsers.length === 0) {
    showToast('Ogohlantirish yuborish uchun foydalanuvchilar yo\'q', 'warning');
    return;
  }

  const promptMsg = `⚠️ DIQQAT!\n\nFiltrlangan barcha ${targetUsers.length} nafar foydalanuvchiga Telegram orqali rasmiy ogohlantirish xabari yuborilsinmi?\n\n(Bu foydalanuvchilar hozirgacha ${targetTc} ta test ishlagan)`;
  if (!confirm(promptMsg)) {
    return;
  }

  showToast(`${targetUsers.length} nafar foydalanuvchiga yuborilmoqda...`, 'info');

  const warnBtn = document.getElementById('btn-warn-all-users');
  if (warnBtn) {
    warnBtn.disabled = true;
    warnBtn.innerHTML = `<span class="spinner-border spinner-border-sm" style="display:inline-block;width:12px;height:12px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:spin 0.6s linear infinite;margin-right:4px;"></span> Yuborilmoqda...`;
  }

  try {
    const payload = targetUsers.map(u => ({
      tg_id: u.tg_id,
      tests_count: u.tests_count || 0,
      fullname: u.fullname || 'Foydalanuvchi'
    }));

    const res = await fetch('/api/dashboard/warn-users-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ users: payload })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || `Xabarlar yuborildi!`, 'success');
      loadData(false);
    } else {
      showToast(data.error || 'Xatolik yuz berdi', 'error');
    }
  } catch (err) {
    console.error('Batch warn error:', err);
    showToast('Tarmoq xatosi: xabarlar to\'liq yuborilmadi', 'error');
  } finally {
    if (warnBtn) {
      warnBtn.disabled = false;
      renderUsers();
    }
  }
}
window.sendWarningToAllFilteredUsers = sendWarningToAllFilteredUsers;

// ----------------------------------------------------
// COPY TO CLIPBOARD HELPER
// ----------------------------------------------------
function copyToClipboard(text, label = '') {
  if (!text || text === '—') return;
  const str = String(text).trim();
  if (!str) return;

  const onSuccess = () => {
    showToast(`Nusxalandi: ${label ? label + ' ' : ''}"${str}"`, 'success');
  };

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(str).then(onSuccess).catch(() => fallbackCopy(str, onSuccess));
  } else {
    fallbackCopy(str, onSuccess);
  }
}

function fallbackCopy(text, cb) {
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    if (cb) cb();
  } catch(e) {
    showToast('Nusxa olish imkoni bo\'lmadi', 'error');
  }
}
window.copyToClipboard = copyToClipboard;

// ----------------------------------------------------
// USER TESTS MODAL (Topshirgan testlar ro'yxati)
// ----------------------------------------------------
function openUserTestsModal(userId, userName, userHandle) {
  const modal = document.getElementById('user-tests-modal');
  if (!modal) return;

  const nameEl = document.getElementById('user-tests-modal-name');
  const idEl = document.getElementById('user-tests-modal-id');
  const uNameEl = document.getElementById('user-tests-modal-username');
  const countEl = document.getElementById('user-tests-modal-count');
  const tbody = document.getElementById('user-tests-modal-tbody');

  if (nameEl) nameEl.textContent = userName || 'Foydalanuvchi';
  if (idEl) idEl.textContent = `ID: ${userId}`;
  if (uNameEl) uNameEl.textContent = userHandle || '—';
  
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:28px;color:var(--text-muted);">Yuklanmoqda...</td></tr>';
  }

  modal.classList.add('open');

  function renderUserSubsList(list) {
    if (countEl) countEl.textContent = `${list.length} ta topshirilgan test`;
    tbody.innerHTML = list.map((s, idx) => {
      let stBadge = '';
      if (s.status === 'rejected') {
        stBadge = `<span class="badge badge-danger">${Icons.ban}Bekor</span>`;
      } else if (s.is_late == 1) {
        stBadge = `<span class="badge badge-warning">${Icons.clock}Kechikkan</span>`;
      } else {
        stBadge = `<span class="badge badge-success">${Icons.check}O'z vaqtida</span>`;
      }

      const gr = s.grade || '—';
      let grBadge = `<span class="badge badge-purple">${gr}</span>`;
      if (gr === 'A+' || gr === 'A') grBadge = `<span class="badge badge-success">${gr}</span>`;
      else if (gr === 'B+' || gr === 'B') grBadge = `<span class="badge badge-info">${gr}</span>`;
      else if (gr === 'C+' || gr === 'C') grBadge = `<span class="badge badge-warning">${gr}</span>`;

      const dt = formatUzbSmartDateTime(s.submitted_at || s.submitted_at_fmt);

      return `
        <tr class="clickable-row" onclick="closeUserTestsModal(); openSubmissionModal(${s.id})">
          <td style="color:var(--text-dim);font-weight:700;font-family:var(--font-mono);">${idx + 1}</td>
          <td>
            <div style="font-weight:700;font-size:13.5px;color:var(--text-main);">#${esc(s.test_code || '')} — ${esc(s.test_title || 'Test')}</div>
          </td>
          <td>
            <div class="time-cell-wrap">
              <span class="day-chip ${dt.dayBadgeClass}">${dt.dayBadgeText}</span>
              <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim);font-weight:600;">${dt.fullDate}</span>
            </div>
          </td>
          <td><b style="color:var(--text-main);">${s.correct_count != null ? s.correct_count : 0}</b> <span style="color:var(--text-muted);font-size:11px;">/ ${s.total_count || 55} ta</span></td>
          <td><b style="color:var(--primary);font-size:14px;">${s.score != null ? s.score : '0.0'}</b> <span style="font-size:11px;color:var(--text-muted);">ball</span></td>
          <td>${grBadge}</td>
          <td>${stBadge}</td>
          <td style="text-align:right;">
            <button class="btn btn-secondary btn-sm" onclick="closeUserTestsModal(); openSubmissionModal(${s.id})" title="Javoblarni ko'rish">
              Batafsil <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-left:2px;"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  function showEmptyUserSubs() {
    if (countEl) countEl.textContent = '0 ta test';
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align:center;padding:40px 16px;color:var(--text-muted);">
          <div style="display:flex;justify-content:center;margin-bottom:10px;">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--text-dim)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 12h-6l-2 3h-4l-2-3H2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-7Z"/>
              <path d="M5.45 5.11 2 12v0"/>
              <path d="M18.55 5.11 22 12v0"/>
              <path d="M6 3h12l3.55 7.11a1 1 0 0 1 .45.89V12"/>
            </svg>
          </div>
          <div style="font-weight:700;font-size:14px;color:var(--text-main);margin-bottom:4px;">Testlar topilmadi</div>
          <div style="font-size:12px;">Ushbu foydalanuvchi hozircha birorta ham test topshirmagan.</div>
        </td>
      </tr>
    `;
  }

  // Filter from State.submissions
  const userSubs = (State.submissions || []).filter(s => Number(s.user_tg_id) === Number(userId));
  
  if (userSubs.length > 0) {
    renderUserSubsList(userSubs);
  } else {
    // Fallback to API
    fetch(`/api/dashboard/user-submissions/${userId}`)
      .then(res => res.json())
      .then(data => {
        if (data.success && data.submissions && data.submissions.length > 0) {
          renderUserSubsList(data.submissions);
        } else {
          showEmptyUserSubs();
        }
      })
      .catch(() => showEmptyUserSubs());
  }
}

function closeUserTestsModal() {
  const modal = document.getElementById('user-tests-modal');
  if (modal) modal.classList.remove('open');
}
window.openUserTestsModal = openUserTestsModal;
window.closeUserTestsModal = closeUserTestsModal;

// ----------------------------------------------------
// TESTS RENDERING & ACTIONS
// ----------------------------------------------------
function renderTests() {
  const body = document.getElementById('tests-table-body');
  if (!body) return;

  const list = State.tests || [];
  if (list.length === 0) {
    body.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:32px;color:var(--text-muted);">Mavjud testlar topilmadi</td></tr>';
    return;
  }

  body.innerHTML = list.map(t => {
    const isAct = t.is_active == 1;
    const isPub = t.results_published == 1;

    return `
      <tr class="clickable-row" onclick="openTestModal(${t.id})">
        <td><b style="color:var(--primary);font-size:14px;font-family:var(--font-mono);">#${esc(t.test_code || '')}</b></td>
        <td>
          <div style="font-weight:700;font-size:14px;color:var(--text-main);">${esc(t.title || 'Test')}</div>
          <div style="font-size:11px;color:var(--text-muted);font-weight:600;">Batafsil ma'lumot va kalitlar uchun bosing</div>
        </td>
        <td><span class="badge badge-purple">${esc(t.subject || 'Fizika')}</span></td>
        <td style="font-family:var(--font-mono);font-size:12px;color:var(--text-main);font-weight:600;">${esc(t.scheduled_date || '—')} ${esc(t.scheduled_start || '')}</td>
        <td style="font-family:var(--font-mono);font-size:12px;color:var(--text-main);font-weight:600;">${esc(t.scheduled_end || '—')}</td>
        <td><b>${t.total_questions || 55} ta</b></td>
        <td><b style="color:var(--success);font-size:13.5px;">${t.submissions_count || 0} kishi</b></td>
        <td>
          <span class="badge badge-${isAct ? 'success' : 'danger'}">
            ${isAct ? '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#10b981;margin-right:4px;"></span>Faol' : '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#ef4444;margin-right:4px;"></span>To\'xtatilgan'}
          </span>
        </td>
        <td>
          <span class="badge badge-${isPub ? 'success' : 'warning'}">
            ${isPub ? `${Icons.megaphone}E'lon qilingan` : `${Icons.lock}Yashirin`}
          </span>
        </td>
        <td style="text-align:right;" onclick="event.stopPropagation();">
          <div style="display:inline-flex;gap:6px;">
            <button class="btn btn-secondary btn-sm" onclick="openTestModal(${t.id})" title="Barcha kalitlar va statistikani ko'rish">
              ${Icons.eye}Tafsilot
            </button>
            <button class="btn btn-secondary btn-sm" onclick="toggleTestStatus(${t.id})" title="Testni to'xtatish / yoqish">
              ${isAct ? Icons.pause : Icons.play}
            </button>
            <button class="btn btn-secondary btn-sm" onclick="toggleTestPublish(${t.id})" title="Natijalarni e'lon qilish / yashirish">
              ${isPub ? Icons.lock : Icons.megaphone}
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// ----------------------------------------------------
// TEST DETAILS MODAL (Ustiga bosganda ma'lumot berish)
// ----------------------------------------------------
function extractKeyValue(val) {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'string' || typeof val === 'number') return String(val).trim();
  if (typeof val === 'object') {
    if (val.ans !== undefined) return String(val.ans).trim();
    if (val.answer !== undefined) return String(val.answer).trim();
    if (val.key !== undefined) return String(val.key).trim();
    if (val.val !== undefined) return String(val.val).trim();
    if (val.correct !== undefined) return String(val.correct).trim();
    const values = Object.values(val);
    if (values.length > 0 && typeof values[0] !== 'object') return String(values[0]).trim();
    return JSON.stringify(val);
  }
  return String(val).trim();
}

function openTestModal(testId) {
  const modal = document.getElementById('test-detail-modal');
  if (!modal) return;

  const t = (State.tests || []).find(item => item.id == testId);
  if (!t) {
    showToast('Test ma\'lumotlari topilmadi', 'warning');
    return;
  }
  State.currentModalTest = t;
  modal.classList.add('open');

  document.getElementById('modal-test-title').textContent = `#${t.test_code} — ${t.title || 'Test'}`;
  document.getElementById('modal-test-sub').textContent = `Fan: ${t.subject || 'Fizika'} • Yaratilgan sana: ${t.created_at_fmt || t.created_date || '—'}`;

  // 1. Schedule & Times (Qachon boshlangan, qachon tugagan)
  const startTimeStr = t.scheduled_date ? `${t.scheduled_date} ${t.scheduled_start || ''}`.trim() : (t.created_at_fmt || 'E\'lon qilingan vaqtdan');
  const endTimeStr = t.scheduled_end ? `${t.scheduled_date || ''} ${t.scheduled_end}`.trim() : (t.is_active == 1 ? 'Hozirda davom etmoqda' : 'Yakunlangan');
  const durationStr = t.time_limit_min ? `${t.time_limit_min} daqiqa (${(t.time_limit_min/60).toFixed(1)} soat)` : 'Vaqt chegarasisiz';
  
  document.getElementById('modal-test-start-time').textContent = startTimeStr;
  document.getElementById('modal-test-end-time').textContent = endTimeStr;
  document.getElementById('modal-test-duration').textContent = durationStr;
  document.getElementById('modal-test-q-count').textContent = `${t.total_questions || 55} ta savol`;

  // 2. Statistics
  document.getElementById('modal-test-subs-count').textContent = `${t.submissions_count || 0} kishi`;
  document.getElementById('modal-test-subs-sub').textContent = t.submissions_count > 0 ? "O'quvchilar topshirdi" : "Hozircha topshirilmadi";
  document.getElementById('modal-test-avg-score').textContent = `${Number(t.avg_score || 0).toFixed(1)} ball`;
  document.getElementById('modal-test-avg-corr').textContent = `O'rtacha ko'rsatkich`;
  document.getElementById('modal-test-max-score').textContent = `${Number(t.max_score_achieved || 0).toFixed(1)} ball`;

  const isAct = t.is_active == 1;
  const isPub = t.results_published == 1;

  document.getElementById('modal-test-status-badge').innerHTML = `
    <span class="badge badge-${isAct ? 'success' : 'danger'}" style="font-size:11.5px;">
      ${isAct ? '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#10b981;margin-right:4px;"></span>Qabul ochiq (Faol)' : '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#ef4444;margin-right:4px;"></span>To\'xtatilgan'}
    </span>
  `;
  document.getElementById('modal-test-pub-badge').innerHTML = `
    <span class="badge badge-${isPub ? 'success' : 'warning'}" style="font-size:11.5px;">
      ${isPub ? `${Icons.megaphone}Natijalar e'lon qilingan` : `${Icons.lock}Natijalar yashirin`}
    </span>
  `;

  // 3. Action buttons inside modal
  const actContainer = document.getElementById('modal-test-actions');
  if (actContainer) {
    actContainer.innerHTML = `
      <button class="btn btn-secondary btn-sm" onclick="toggleTestStatusFromModal(${t.id})">
        ${isAct ? Icons.pause + ' Qabulni to\'xtatish' : Icons.play + ' Testni yoqish'}
      </button>
      <button class="btn btn-secondary btn-sm" onclick="toggleTestPublishFromModal(${t.id})">
        ${isPub ? Icons.lock + ' Natijalarni yashirish' : Icons.megaphone + ' Natijalarni e\'lon qilish'}
      </button>
    `;
  }

  // 4. Reset keys drawer (boshida yopiq turadi!)
  const drawer = document.getElementById('modal-test-keys-drawer');
  if (drawer) drawer.style.display = 'none';
  const btnKeys = document.getElementById('btn-toggle-test-keys');
  if (btnKeys) {
    btnKeys.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:4px;"><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg><span>Kalitlarni ko'rish ▼</span>`;
  }
}

function toggleTestKeysView() {
  const drawer = document.getElementById('modal-test-keys-drawer');
  const btn = document.getElementById('btn-toggle-test-keys');
  if (!drawer) return;
  const isHidden = drawer.style.display === 'none' || !drawer.style.display;
  if (isHidden) {
    drawer.style.display = 'block';
    if (btn) {
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:4px;"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg><span>Kalitlarni yashirish ▲</span>`;
    }
    if (State.currentModalTest) {
      renderTestKeysGrid(State.currentModalTest);
    }
  } else {
    drawer.style.display = 'none';
    if (btn) {
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:4px;"><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg><span>Kalitlarni ko'rish ▼</span>`;
    }
  }
}
window.toggleTestKeysView = toggleTestKeysView;

function renderTestKeysGrid(t) {
  const grid = document.getElementById('modal-test-keys-grid');
  if (!grid) return;

  let keysObj = {};
  try {
    if (typeof t.answers_json === 'string') {
      keysObj = JSON.parse(t.answers_json || '{}');
    } else if (typeof t.answers_json === 'object') {
      keysObj = t.answers_json || {};
    }
  } catch (e) {
    keysObj = {};
  }

  const keysList = [];
  const totalQ = t.total_questions || 55;
  if (totalQ === 55 || totalQ >= 45) {
    for (let i = 1; i <= 35; i++) keysList.push(String(i));
    for (let i = 36; i <= 45; i++) {
      keysList.push(`${i}a`);
      keysList.push(`${i}b`);
    }
  } else {
    for (let i = 1; i <= totalQ; i++) keysList.push(String(i));
  }

  if (Object.keys(keysObj).length === 0) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:24px;color:var(--text-muted);">Ushbu test uchun to\'g\'ri kalitlar bazada kiritilmagan.</div>';
    return;
  }

  let html = '';
  keysList.forEach(k => {
    const rawVal = keysObj[k] !== undefined ? keysObj[k] : keysObj[k.toUpperCase()];
    const val = extractKeyValue(rawVal);
    const isSpecial = k.includes('a') || k.includes('b');
    html += `
      <div class="answer-card" style="border-left: 3px solid var(--primary);">
        <div style="display:flex;justify-content:space-between;font-weight:700;">
          <span>${k}-savol</span>
          <span style="font-size:10px;color:var(--text-muted);">${isSpecial ? 'Yozma' : 'Variant'}</span>
        </div>
        <div style="font-size:13.5px;color:var(--primary);font-weight:800;font-family:var(--font-mono);margin-top:2px;">
          ${esc(val)}
        </div>
      </div>
    `;
  });

  grid.innerHTML = html;
}

function closeTestModal() {
  const modal = document.getElementById('test-detail-modal');
  if (modal) modal.classList.remove('open');
  State.currentModalTest = null;
}

function viewTestSubmissionsFromModal() {
  if (!State.currentModalTest) return;
  const code = State.currentModalTest.test_code;
  closeTestModal();
  switchDashboardTab('submissions');
  setTimeout(() => {
    filterSubmissionsByTest(code);
    const sel = document.getElementById('filter-test-select');
    if (sel) sel.value = String(code);
  }, 100);
}

async function toggleTestStatusFromModal(testId) {
  await toggleTestStatus(testId);
  const t = (State.tests || []).find(item => item.id == testId);
  if (t) openTestModal(testId);
}

async function toggleTestPublishFromModal(testId) {
  await toggleTestPublish(testId);
  const t = (State.tests || []).find(item => item.id == testId);
  if (t) openTestModal(testId);
}

window.openTestModal = openTestModal;
window.closeTestModal = closeTestModal;
window.viewTestSubmissionsFromModal = viewTestSubmissionsFromModal;
window.toggleTestStatusFromModal = toggleTestStatusFromModal;
window.toggleTestPublishFromModal = toggleTestPublishFromModal;

// ----------------------------------------------------
// ACTIVITY LOGS RENDERING
// ----------------------------------------------------
function renderLogs() {
  const body = document.getElementById('activity-table-body');
  if (!body) return;

  const list = State.logs || [];
  if (list.length === 0) {
    body.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--text-muted);">Faolliklar jurnali bo\'sh</td></tr>';
    return;
  }

  body.innerHTML = list.map(l => {
    const un = l.username ? ` (@${esc(l.username.replace(/^@/, ''))})` : '';
    const dt = formatUzbSmartDateTime(l.time || l.time_fmt);
    return `
      <tr>
        <td>
          <div class="time-cell-wrap">
            <span class="day-chip ${dt.dayBadgeClass}">${dt.dayBadgeText}</span>
            <span class="time-str-mono">${dt.fullDate}</span>
          </div>
        </td>
        <td>
          <span class="badge badge-${l.badge_color || 'info'}">${esc(l.type || 'hodisa')}</span>
        </td>
        <td>
          <div style="font-weight:700;color:var(--text-main);">${esc(l.user_name || 'Foydalanuvchi')}</div>
          <div style="font-size:11px;color:var(--text-dim);font-weight:700;">${un} (ID: ${l.user_id})</div>
        </td>
        <td><div style="font-size:13px;color:var(--text-main);font-weight:600;">${esc(l.title || '')}</div></td>
        <td><b style="color:var(--primary);font-size:12px;">${esc(l.badge || '')}</b></td>
      </tr>
    `;
  }).join('');
}

// ----------------------------------------------------
// DATABASE & SQL CONSOLE
// ----------------------------------------------------
function renderDatabase() {
  fetchDashboardData();
}

async function runSqlConsoleQuery() {
  const input = document.getElementById('sql-query-input');
  const resContainer = document.getElementById('sql-result-container');
  if (!input || !resContainer) return;

  const q = input.value.trim();
  if (!q) return;

  resContainer.innerHTML = '<div style="color:var(--text-muted);padding:10px;">So\'rov bajarilmoqda...</div>';

  try {
    const res = await fetch('/api/dashboard/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q })
    });
    const data = await res.json();
    if (!data.success) {
      resContainer.innerHTML = `<div style="color:var(--danger);padding:10px;font-family:var(--font-mono);background:rgba(239,68,68,0.1);border-radius:6px;">Xatolik: ${esc(data.error || 'Noma\'lum xatolik')}</div>`;
      return;
    }

    const rows = data.rows || [];
    if (rows.length === 0) {
      resContainer.innerHTML = '<div style="color:var(--text-muted);padding:10px;">Natija topilmadi (0 qator).</div>';
      return;
    }

    const cols = Object.keys(rows[0]);
    let tableHtml = `
      <div style="margin-bottom:8px;font-size:12px;color:var(--text-muted);">Qaytarildi: <b>${rows.length} ta qator</b></div>
      <table class="mac-table" style="font-size:12px;">
        <thead>
          <tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${rows.map(r => `<tr>${cols.map(c => `<td style="font-family:var(--font-mono);">${esc(String(r[c] !== null ? r[c] : 'NULL'))}</td>`).join('')}</tr>`).join('')}
        </tbody>
      </table>
    `;
    resContainer.innerHTML = tableHtml;
  } catch (e) {
    resContainer.innerHTML = `<div style="color:var(--danger);padding:10px;">Server xatosi: ${esc(String(e))}</div>`;
  }
}

// ----------------------------------------------------
// SUBMISSION DETAILS MODAL
// ----------------------------------------------------
async function openSubmissionModal(subId) {
  const modal = document.getElementById('submission-modal');
  if (!modal) return;
  modal.classList.add('open');

  document.getElementById('modal-sub-title').textContent = 'Yuklanmoqda...';
  document.getElementById('modal-sub-answers-grid').innerHTML = '<div style="color:var(--text-muted);padding:20px;">Yuklanmoqda...</div>';

  try {
    const res = await fetch(`/api/dashboard/submission/${subId}`);
    if (!res.ok) throw new Error('Not found');
    const data = await res.json();
    if (!data.success) throw new Error(data.error);

    const s = data.submission;
    State.currentModalSubmission = s;

    const un = s.username ? ` (@${esc(s.username.replace(/^@/, ''))})` : '';
    const dt = formatUzbSmartDateTime(s.submitted_at || s.submitted_at_fmt);
    document.getElementById('modal-sub-time').innerHTML = `Topshirilgan vaqt: <b style="color:var(--text-main);">${dt.fullDate}</b> <span class="day-chip ${dt.dayBadgeClass}" style="margin-left:6px;">${dt.dayBadgeText}</span>`;
    document.getElementById('modal-sub-score').textContent = `${s.score || 0} ball`;
    document.getElementById('modal-sub-correct').textContent = `${s.correct_count || 0} / ${s.total_count || 55}`;
    document.getElementById('modal-sub-grade').textContent = s.grade || '—';

    // Late badge & Late decision box
    const lateBadgeEl = document.getElementById('modal-sub-late-badge');
    const lateBox = document.getElementById('modal-sub-late-box');
    if (s.is_late == 1) {
      lateBadgeEl.innerHTML = `<span class="badge badge-warning">${Icons.clock}Kechikkan</span>`;
      if (lateBox) lateBox.style.display = 'block';
    } else {
      lateBadgeEl.innerHTML = `<span class="badge badge-success">${Icons.check}O'z vaqtida</span>`;
      if (lateBox) lateBox.style.display = 'none';
    }

    // Question-by-question breakdown
    renderSubmissionAnswersGrid(s);
  } catch (err) {
    document.getElementById('modal-sub-answers-grid').innerHTML = `<div style="color:var(--danger);padding:20px;">Xatolik: ${esc(String(err))}</div>`;
  }
}

function renderSubmissionAnswersGrid(s) {
  const grid = document.getElementById('modal-sub-answers-grid');
  if (!grid) return;

  const details = s.details || {};
  const userAnswers = s.answers || {};

  // Build list of keys: 1..35, 36a..45b
  const keys = [];
  for (let i = 1; i <= 35; i++) keys.push(String(i));
  for (let i = 36; i <= 45; i++) {
    keys.push(`${i}a`);
    keys.push(`${i}b`);
  }

  let html = '';
  keys.forEach(k => {
    const qInfo = details[k] || {};
    const uVal = qInfo.user !== undefined ? qInfo.user : (userAnswers[k] || '');
    const cVal = qInfo.correct !== undefined ? qInfo.correct : '';
    const status = qInfo.status || (uVal ? 'incorrect' : 'unanswered');

    let statusClass = 'unanswered';
    let statusLabel = '—';
    if (status === 'correct') {
      statusClass = 'correct';
      statusLabel = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1.5px;margin-right:3px;"><polyline points="20 6 9 17 4 12"/></svg>To\'g\'ri';
    } else if (status === 'partial') {
      statusClass = 'partial';
      statusLabel = 'Qisman (30%)';
    } else if (status === 'incorrect') {
      statusClass = 'incorrect';
      statusLabel = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1.5px;margin-right:3px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>Noto\'g\'ri';
    }

    const scoreBadge = (status === 'partial') ? `
      <div style="font-size:10px;color:#f59e0b;font-weight:700;margin-top:2px;">
        Ball: ${qInfo.score !== undefined ? qInfo.score : '0.45'} / ${qInfo.max_score || '1.5'} (Oxirgacha hisoblanmagan)
      </div>` : '';

    html += `
      <div class="answer-card ${statusClass}">
        <div style="display:flex;justify-content:space-between;font-weight:700;">
          <span>${k}-savol</span>
          <span style="font-size:10px;">${statusLabel}</span>
        </div>
        <div style="font-size:11.5px;color:var(--text-main);">
          Javob: <b>${esc(uVal || 'Belgilanmagan')}</b>
        </div>
        <div style="font-size:10.5px;color:var(--text-muted);">
          Kalit: <span style="color:var(--primary);font-weight:700;">${esc(cVal || '—')}</span>
        </div>
        ${scoreBadge}
      </div>
    `;
  });

  grid.innerHTML = html;
}

function closeSubmissionModal() {
  const modal = document.getElementById('submission-modal');
  if (modal) modal.classList.remove('open');
  State.currentModalSubmission = null;
}

async function handleModalLateAction(action) {
  if (!State.currentModalSubmission) return;
  const subId = State.currentModalSubmission.id;

  try {
    const res = await fetch('/api/dashboard/late-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ submission_id: subId, action: action })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || 'Muvaffaqiyatli bajarildi', 'success');
      closeSubmissionModal();
      fetchDashboardData();
    } else {
      showToast(data.error || 'Xatolik', 'danger');
    }
  } catch (e) {
    showToast('Server bilan bog\'lanishda xatolik', 'danger');
  }
}

// ----------------------------------------------------
// ACTIONS (USER, TEST)
// ----------------------------------------------------
async function changeUserStatus(userId, action) {
  const confirmMsg = action === 'delete' 
    ? 'Haqiqatan ham bu foydalanuvchini bazadan butunlay o\'chirmoqchimisiz?' 
    : (action === 'block' ? 'Foydalanuvchini bloklamoqchimisiz?' : 'Foydalanuvchini tasdiqlaysizmi?');

  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch('/api/dashboard/user-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, action: action })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      fetchUsersData();
      fetchDashboardData();
    } else {
      showToast(data.error || 'Xatolik', 'danger');
    }
  } catch (e) {
    showToast('Xatolik yuz berdi', 'danger');
  }
}

async function toggleTestStatus(testId) {
  try {
    const res = await fetch('/api/dashboard/test-toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test_id: testId })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      fetchTestsData();
      fetchDashboardData();
    }
  } catch (e) {
    showToast('Xatolik', 'danger');
  }
}

async function toggleTestPublish(testId) {
  try {
    const res = await fetch('/api/dashboard/test-publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test_id: testId })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      fetchTestsData();
      fetchDashboardData();
    }
  } catch (e) {
    showToast('Xatolik', 'danger');
  }
}

// ----------------------------------------------------
// CSV EXPORT
// ----------------------------------------------------
function exportCurrentTable() {
  if (State.activeTab === 'submissions') {
    exportSubmissionsToCSV();
  } else if (State.activeTab === 'users') {
    exportUsersToCSV();
  } else {
    showToast('Hozirgi bo\'lim eksportini tanlash uchun Natijalar yoki Foydalanuvchilar bo\'limiga o\'ting.', 'info');
  }
}

function exportSubmissionsToCSV() {
  if (!State.submissions || State.submissions.length === 0) {
    showToast('Eksport qilish uchun natijalar yo\'q', 'warning');
    return;
  }
  let csv = 'ID,Foydalanuvchi,Username,Telefon,Test Kodi,Topshirilgan Vaqt,Togri Javoblar,Jami Savollar,Ball,Daraja,Kechikkan\n';
  State.submissions.forEach(s => {
    const fn = (s.fullname || '').replace(/,/g, ' ');
    const un = (s.username || '').replace(/,/g, ' ');
    const ph = (s.phone || '').replace(/,/g, ' ');
    csv += `${s.id},"${fn}","${un}","${ph}",#${s.test_code},"${s.submitted_at_fmt || ''}",${s.correct_count || 0},${s.total_count || 55},${s.score || 0},"${s.grade || ''}",${s.is_late == 1 ? 'HA' : 'YOQ'}\n`;
  });
  downloadFile(csv, `natijalar_baza_${Date.now()}.csv`, 'text/csv;charset=utf-8;');
  showToast('Natijalar CSV fayli yuklab olindi!', 'success');
}

function exportUsersToCSV() {
  if (!State.users || State.users.length === 0) {
    showToast('Eksport qilish uchun foydalanuvchilar yo\'q', 'warning');
    return;
  }
  let csv = 'Telegram ID,Foydalanuvchi Ismi,Username,Telefon,Holati,Qoshilgan Vaqt,Testlar Soni\n';
  State.users.forEach(u => {
    const fn = (u.fullname || '').replace(/,/g, ' ');
    const un = (u.username || '').replace(/,/g, ' ');
    const ph = (u.phone || '').replace(/,/g, ' ');
    csv += `${u.tg_id},"${fn}","${un}","${ph}","${u.status || ''}","${u.registered_at_fmt || ''}",${u.tests_count || 0}\n`;
  });
  downloadFile(csv, `foydalanuvchilar_baza_${Date.now()}.csv`, 'text/csv;charset=utf-8;');
  showToast('Foydalanuvchilar CSV fayli yuklab olindi!', 'success');
}

function downloadFile(content, fileName, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ----------------------------------------------------
// AUTO-REFRESH & THEME & SHORTCUTS
// ----------------------------------------------------
function toggleAutoRefresh() {
  State.autoRefresh = !State.autoRefresh;
  const label = document.getElementById('refresh-label');
  const icon = document.getElementById('refresh-icon');
  if (State.autoRefresh) {
    startAutoRefresh();
    if (label) label.textContent = 'Jonli (25s)';
    if (icon) {
      icon.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`;
    }
    showToast('Avtomatik yangilanish yoqildi (har 25s)', 'success');
  } else {
    stopAutoRefresh();
    if (label) label.textContent = 'To\'xtatilgan';
    if (icon) {
      icon.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;
    }
    showToast('Avtomatik yangilanish to\'xtatildi', 'info');
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  State.refreshTimer = setInterval(() => {
    if (State.autoRefresh) {
      fetchDashboardData();
    }
  }, 25000);
}

function stopAutoRefresh() {
  if (State.refreshTimer) {
    clearInterval(State.refreshTimer);
    State.refreshTimer = null;
  }
}

function toggleTheme() {
  const html = document.documentElement;
  const cur = html.getAttribute('data-theme') || 'dark';
  const nxt = cur === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', nxt);
  const btn = document.getElementById('btn-theme-toggle');
  if (btn) {
    if (nxt === 'dark') {
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`;
    } else {
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>`;
    }
  }
  showToast(`Rejim o'zgartirildi: ${nxt === 'dark' ? 'Qorong\'u' : 'Yorug\''}`, 'info');
}

function handleGlobalSearch(val) {
  State.globalSearch = val || '';
  if (State.activeTab === 'submissions') renderSubmissions();
  else if (State.activeTab === 'users') renderUsers();
}

/* ============================================================
   STEP-BY-STEP NAVIGATION SYSTEM (1 ta user pastga/tepaga, Enter, Bo'limlar)
   ============================================================ */
const NavState = {
  context: 'table', // 'sidebar' | 'table'
  sidebarIndex: 0,
  sidebarTabs: ['overview', 'submissions', 'users', 'tests', 'activity', 'database'],
  selectedRowIndex: -1,
};

function getActiveVisibleRows() {
  // 1. Check if an active modal with a table is visible
  const visibleModals = Array.from(document.querySelectorAll('.modal-overlay')).filter(m => {
    return window.getComputedStyle(m).display !== 'none';
  });
  if (visibleModals.length > 0) {
    const modal = visibleModals[visibleModals.length - 1];
    const rows = modal.querySelectorAll('.mac-table tbody tr');
    return Array.from(rows).filter(r => !r.querySelector('td[colspan]'));
  }

  // 2. Otherwise active tab view table
  const activeView = document.querySelector('.page-view.active');
  if (activeView) {
    const rows = activeView.querySelectorAll('.mac-table tbody tr');
    return Array.from(rows).filter(r => !r.querySelector('td[colspan]'));
  }
  return [];
}

function getActiveScrollableContainer() {
  const visibleModals = Array.from(document.querySelectorAll('.modal-overlay')).filter(m => {
    return window.getComputedStyle(m).display !== 'none';
  });
  if (visibleModals.length > 0) {
    const modalBody = visibleModals[visibleModals.length - 1].querySelector('.modal-body');
    if (modalBody) return modalBody;
  }
  return document.querySelector('.views-container') || document.documentElement;
}

function getActiveTableResponsive() {
  const visibleModals = Array.from(document.querySelectorAll('.modal-overlay')).filter(m => {
    return window.getComputedStyle(m).display !== 'none';
  });
  if (visibleModals.length > 0) {
    const tbl = visibleModals[visibleModals.length - 1].querySelector('.table-responsive');
    if (tbl) return tbl;
  }
  const activeView = document.querySelector('.page-view.active');
  if (activeView) {
    const tbl = activeView.querySelector('.table-responsive');
    if (tbl) return tbl;
  }
  return document.querySelector('.table-responsive');
}

function flashDpadButton(btnId) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.classList.add('active');
  setTimeout(() => btn.classList.remove('active'), 180);
}

function clearTableRowSelection() {
  document.querySelectorAll('.table-row-selected').forEach(r => r.classList.remove('table-row-selected'));
  NavState.selectedRowIndex = -1;
}

function clearSidebarFocus() {
  document.querySelectorAll('.app-sidebar .nav-item').forEach(i => i.classList.remove('nav-item-focused'));
}

function highlightTableRow(index) {
  const rows = getActiveVisibleRows();
  if (!rows || rows.length === 0) return;

  if (index < 0) index = 0;
  if (index >= rows.length) index = rows.length - 1;

  NavState.selectedRowIndex = index;
  NavState.context = 'table';
  clearSidebarFocus();

  rows.forEach((r, i) => {
    if (i === index) {
      r.classList.add('table-row-selected');
      r.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else {
      r.classList.remove('table-row-selected');
    }
  });
}
window.highlightTableRow = highlightTableRow;

function highlightSidebarItem(index) {
  const navItems = Array.from(document.querySelectorAll('.app-sidebar .nav-item'));
  if (!navItems || navItems.length === 0) return;

  if (index < 0) index = 0;
  if (index >= navItems.length) index = navItems.length - 1;

  NavState.sidebarIndex = index;
  NavState.context = 'sidebar';
  clearTableRowSelection();

  navItems.forEach((item, i) => {
    if (i === index) {
      item.classList.add('nav-item-focused');
      item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else {
      item.classList.remove('nav-item-focused');
    }
  });
}
window.highlightSidebarItem = highlightSidebarItem;

function navStep(direction) {
  // Context 1: SIDEBAR (2-rasm: bo'limlar navigatsiyasi)
  if (NavState.context === 'sidebar') {
    const navItems = Array.from(document.querySelectorAll('.app-sidebar .nav-item'));
    if (!navItems || navItems.length === 0) return;

    if (direction === 'down') {
      flashDpadButton('btn-dpad-down');
      NavState.sidebarIndex = (NavState.sidebarIndex + 1) % navItems.length;
      highlightSidebarItem(NavState.sidebarIndex);
    } else if (direction === 'up') {
      flashDpadButton('btn-dpad-up');
      NavState.sidebarIndex = (NavState.sidebarIndex - 1 + navItems.length) % navItems.length;
      highlightSidebarItem(NavState.sidebarIndex);
    } else if (direction === 'right') {
      // Step from sidebar into the table rows
      flashDpadButton('btn-dpad-right');
      NavState.context = 'table';
      clearSidebarFocus();
      const rows = getActiveVisibleRows();
      if (rows && rows.length > 0) {
        highlightTableRow(0);
      }
    } else if (direction === 'left') {
      flashDpadButton('btn-dpad-left');
      highlightSidebarItem(NavState.sidebarIndex);
    }
    return;
  }

  // Context 2: TABLE (Userlar qatorida 1 ta pastga, 1 ta tepaga)
  const rows = getActiveVisibleRows();
  if (!rows || rows.length === 0) {
    // If no table rows, scroll view container smoothly
    navScroll(direction, 180);
    return;
  }

  if (direction === 'down') {
    flashDpadButton('btn-dpad-down');
    if (NavState.selectedRowIndex < 0) {
      highlightTableRow(0);
    } else if (NavState.selectedRowIndex < rows.length - 1) {
      highlightTableRow(NavState.selectedRowIndex + 1);
    } else {
      // At last row, smooth scroll container down
      const container = getActiveScrollableContainer();
      container.scrollBy({ top: 120, behavior: 'smooth' });
    }
  } else if (direction === 'up') {
    flashDpadButton('btn-dpad-up');
    if (NavState.selectedRowIndex > 0) {
      highlightTableRow(NavState.selectedRowIndex - 1);
    } else if (NavState.selectedRowIndex === 0) {
      // At top row, smooth scroll container top
      const container = getActiveScrollableContainer();
      container.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      highlightTableRow(0);
    }
  } else if (direction === 'left') {
    flashDpadButton('btn-dpad-left');
    // Move focus from table back to sidebar (2-rasm)
    const curTabIdx = NavState.sidebarTabs.indexOf(State.activeTab);
    highlightSidebarItem(curTabIdx !== -1 ? curTabIdx : 0);
  } else if (direction === 'right') {
    flashDpadButton('btn-dpad-right');
    // Scroll wide table to the right
    scrollActiveTable('right');
  }
}
window.navStep = navStep;

function executeCurrentSelection() {
  flashDpadButton('btn-dpad-center');

  if (NavState.context === 'sidebar') {
    // Activate sidebar section
    const targetTab = NavState.sidebarTabs[NavState.sidebarIndex];
    if (targetTab) {
      switchDashboardTab(targetTab);
      clearSidebarFocus();
      setTimeout(() => {
        const rows = getActiveVisibleRows();
        if (rows && rows.length > 0) {
          highlightTableRow(0);
        }
      }, 80);
    }
    return;
  }

  // Context: TABLE - click on selected row ("enter bosam ustiga bosiladigan")
  const rows = getActiveVisibleRows();
  if (NavState.selectedRowIndex >= 0 && NavState.selectedRowIndex < rows.length) {
    const row = rows[NavState.selectedRowIndex];
    if (row) {
      // Tactile click visual feedback
      row.style.transform = 'scale(0.985)';
      setTimeout(() => { row.style.transform = ''; }, 120);

      // Trigger click on row
      if (typeof row.onclick === 'function') {
        row.onclick(new MouseEvent('click', { bubbles: true, cancelable: true }));
      } else {
        const primaryBtn = row.querySelector('.user-tests-badge-btn, button.btn-secondary, button.btn-primary');
        if (primaryBtn) {
          primaryBtn.click();
        } else {
          row.click();
        }
      }
    }
  } else {
    // If no row was selected yet, select the 1st row
    if (rows && rows.length > 0) {
      highlightTableRow(0);
    }
  }
}
window.executeCurrentSelection = executeCurrentSelection;

function navScroll(direction, amount) {
  const container = getActiveScrollableContainer();
  const table = getActiveTableResponsive();
  const vStep = amount || 240;
  const hStep = amount || 280;

  if (direction === 'up') {
    flashDpadButton('btn-dpad-up');
    container.scrollBy({ top: -vStep, behavior: 'smooth' });
  } else if (direction === 'down') {
    flashDpadButton('btn-dpad-down');
    container.scrollBy({ top: vStep, behavior: 'smooth' });
  } else if (direction === 'left') {
    flashDpadButton('btn-dpad-left');
    if (table) table.scrollBy({ left: -hStep, behavior: 'smooth' });
    else container.scrollBy({ left: -hStep, behavior: 'smooth' });
  } else if (direction === 'right') {
    flashDpadButton('btn-dpad-right');
    if (table) table.scrollBy({ left: hStep, behavior: 'smooth' });
    else container.scrollBy({ left: hStep, behavior: 'smooth' });
  } else if (direction === 'top') {
    flashDpadButton('btn-dpad-center');
    container.scrollTo({ top: 0, behavior: 'smooth' });
    if (table) table.scrollTo({ left: 0, behavior: 'smooth' });
  } else if (direction === 'bottom') {
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
  }
}
window.navScroll = navScroll;

function scrollActiveTable(direction) {
  const table = getActiveTableResponsive();
  if (table) {
    const step = direction === 'left' ? -280 : 280;
    table.scrollBy({ left: step, behavior: 'smooth' });
    flashDpadButton(direction === 'left' ? 'btn-dpad-left' : 'btn-dpad-right');
  }
}
window.scrollActiveTable = scrollActiveTable;

function navigateTabs(delta) {
  const tabs = ['overview', 'submissions', 'users', 'tests', 'activity', 'database'];
  const curIdx = tabs.indexOf(State.activeTab);
  if (curIdx !== -1) {
    let nextIdx = curIdx + delta;
    if (nextIdx < 0) nextIdx = tabs.length - 1;
    if (nextIdx >= tabs.length) nextIdx = 0;
    switchDashboardTab(tabs[nextIdx]);
  }
}
window.navigateTabs = navigateTabs;

function toggleNavDock() {
  const dock = document.getElementById('mac-nav-dock');
  if (!dock) return;
  dock.classList.toggle('minimized');
  const isMin = dock.classList.contains('minimized');
  try {
    localStorage.setItem('bm_nav_dock_minimized', isMin ? '1' : '0');
  } catch (e) {}
}
window.toggleNavDock = toggleNavDock;

function initNavDockState() {
  try {
    if (localStorage.getItem('bm_nav_dock_minimized') === '1') {
      const dock = document.getElementById('mac-nav-dock');
      if (dock) dock.classList.add('minimized');
    }
  } catch (e) {}
}

function setupKeyboardShortcuts() {
  initNavDockState();

  // Mouse click row delegation: clicking any row sets it as selected
  document.addEventListener('click', (e) => {
    const tr = e.target.closest('.mac-table tbody tr');
    if (tr && !tr.querySelector('td[colspan]')) {
      const rows = getActiveVisibleRows();
      const idx = rows.indexOf(tr);
      if (idx !== -1) {
        NavState.selectedRowIndex = idx;
        NavState.context = 'table';
        clearSidebarFocus();
        rows.forEach((r, i) => r.classList.toggle('table-row-selected', i === idx));
      }
    }
    const navItem = e.target.closest('.app-sidebar .nav-item');
    if (navItem) {
      const navItems = Array.from(document.querySelectorAll('.app-sidebar .nav-item'));
      const idx = navItems.indexOf(navItem);
      if (idx !== -1) {
        NavState.sidebarIndex = idx;
        NavState.context = 'sidebar';
        clearTableRowSelection();
      }
    }
  });

  window.addEventListener('keydown', (e) => {
    // If typing in an input, textarea, or contentEditable, do not hijack typing
    const isInputFocused = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable;

    // Cmd+K or Ctrl+K to focus search
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      const inp = document.getElementById('global-search-input');
      if (inp) {
        inp.focus();
        inp.select();
      }
      return;
    }
    // Cmd+R to refresh data
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'r') {
      e.preventDefault();
      fetchDashboardData(true);
      return;
    }
    // Escape: closes modals if open, or moves focus to sidebar
    if (e.key === 'Escape') {
      const visibleModals = Array.from(document.querySelectorAll('.modal-overlay')).filter(m => window.getComputedStyle(m).display !== 'none');
      if (visibleModals.length > 0) {
        closeSubmissionModal();
        closeUserTestsModal();
        closeCancelSubModal();
        closeTestModal();
      } else {
        const curTabIdx = NavState.sidebarTabs.indexOf(State.activeTab);
        highlightSidebarItem(curTabIdx !== -1 ? curTabIdx : 0);
      }
      return;
    }
    // Cmd+1..6 tab switching
    if ((e.metaKey || e.ctrlKey) && ['1', '2', '3', '4', '5', '6'].includes(e.key)) {
      e.preventDefault();
      const tabs = ['overview', 'submissions', 'users', 'tests', 'activity', 'database'];
      const idx = parseInt(e.key) - 1;
      if (tabs[idx]) switchDashboardTab(tabs[idx]);
      return;
    }

    if (isInputFocused) return;

    // Directional Step Keys: Pastga (↓), Tepaga (↑), Enter (Tanlash), Chapga (←), O'ngga (→)
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      navStep('down');
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      navStep('up');
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeCurrentSelection();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      if (e.altKey || e.metaKey || e.ctrlKey) {
        navigateTabs(-1);
      } else {
        navStep('left');
      }
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      if (e.altKey || e.metaKey || e.ctrlKey) {
        navigateTabs(1);
      } else {
        navStep('right');
      }
    } else if (e.key === 'Tab') {
      e.preventDefault();
      // Toggle between sidebar (2-rasm) and table rows
      if (NavState.context === 'sidebar') {
        NavState.context = 'table';
        clearSidebarFocus();
        highlightTableRow(0);
      } else {
        const curTabIdx = NavState.sidebarTabs.indexOf(State.activeTab);
        highlightSidebarItem(curTabIdx !== -1 ? curTabIdx : 0);
      }
    } else if (e.key === 'PageDown' || (e.key === ' ' && !e.shiftKey)) {
      e.preventDefault();
      navScroll('down', 480);
    } else if (e.key === 'PageUp' || (e.key === ' ' && e.shiftKey)) {
      e.preventDefault();
      navScroll('up', 480);
    } else if (e.key === 'Home') {
      e.preventDefault();
      if (NavState.context === 'table') highlightTableRow(0);
      else navScroll('top');
    } else if (e.key === 'End') {
      e.preventDefault();
      const rows = getActiveVisibleRows();
      if (NavState.context === 'table' && rows.length > 0) highlightTableRow(rows.length - 1);
      else navScroll('bottom');
    }
  });
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

function closeDashboardWindow() {
  if (confirm('Boshqaruv panelini yopmoqchimisiz?')) {
    window.close();
  }
}

function minimizeDashboardWindow() {
  showToast('MacBook oynasi kichraytirildi (Dock rejimi)', 'info');
}

// ----------------------------------------------------
// TOAST NOTIFICATIONS
// ----------------------------------------------------
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const t = document.createElement('div');
  t.className = 'mac-toast';
  
  let iconSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
  let color = 'var(--info)';
  if (type === 'success') {
    iconSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="16 9 10 15 8 13"/></svg>';
    color = 'var(--success)';
  } else if (type === 'danger') {
    iconSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>';
    color = 'var(--danger)';
  } else if (type === 'warning') {
    iconSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    color = 'var(--warning)';
  }

  t.style.borderLeft = `4px solid ${color}`;
  t.innerHTML = `<span style="display:inline-flex;align-items:center;color:${color};flex-shrink:0;">${iconSvg}</span><span style="flex:1;">${esc(msg)}</span>`;
  container.appendChild(t);

  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transform = 'translateY(10px)';
    t.style.transition = 'all 0.3s ease';
    setTimeout(() => t.remove(), 300);
  }, 3200);
}

// Helper: Escape HTML
function esc(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ====================================================
// SUBMISSION CANCELLATION (JAVOBNI BEKOR QILISH)
// 1. Javobni qabul qilmaslik (reject)
// 2. Qayta topshirish (allow_retake)
// ====================================================
let cancelModalSub = null;
let selectedCancelActionType = null;

function openCancelSubModalById(subId) {
  const s = (State.submissions || []).find(x => Number(x.id) === Number(subId)) ||
            (State.overviewSubmissions || []).find(x => Number(x.id) === Number(subId)) ||
            (State.currentModalSubmission && Number(State.currentModalSubmission.id) === Number(subId) ? State.currentModalSubmission : null);

  if (!s) {
    fetch(`/api/dashboard/submission/${subId}`)
      .then(r => r.json())
      .then(d => {
        if (d && d.submission) {
          openCancelSubModalWithData(d.submission);
        } else {
          showToast('Natija topilmadi', 'danger');
        }
      })
      .catch(e => showToast('Xatolik: ' + e, 'danger'));
    return;
  }
  openCancelSubModalWithData(s);
}
window.openCancelSubModalById = openCancelSubModalById;

function promptCancelCurrentModalSubmission() {
  if (State.currentModalSubmission) {
    openCancelSubModalWithData(State.currentModalSubmission);
  } else {
    showToast('Natija ma\'lumotlari yuklanmagan', 'warning');
  }
}
window.promptCancelCurrentModalSubmission = promptCancelCurrentModalSubmission;

function openCancelSubModalWithData(sub) {
  cancelModalSub = sub;
  selectedCancelActionType = null;

  const infoEl = document.getElementById('cancel-sub-user-info');
  if (infoEl) {
    const un = sub.username ? ` (@${sub.username.replace(/^@/, '')})` : '';
    infoEl.innerHTML = `<b style="color:var(--text-main);">${esc(sub.fullname || 'Foydalanuvchi')}</b> (ID: ${sub.user_tg_id})${un} • Test #${esc(sub.test_code || '')}`;
  }

  // Show Step 1, hide Step 2
  backToCancelStep1();

  const modal = document.getElementById('cancel-sub-modal');
  if (modal) modal.classList.add('open');
}

function closeCancelSubModal() {
  const modal = document.getElementById('cancel-sub-modal');
  if (modal) modal.classList.remove('open');
  cancelModalSub = null;
  selectedCancelActionType = null;
}
window.closeCancelSubModal = closeCancelSubModal;

function selectCancelAction(actionType) {
  if (!cancelModalSub) return;
  selectedCancelActionType = actionType;

  const step1 = document.getElementById('cancel-sub-step-1');
  const step2 = document.getElementById('cancel-sub-step-2');
  const confirmActions = document.getElementById('cancel-sub-confirm-actions');
  const titleEl = document.getElementById('cancel-sub-confirm-title');
  const descEl = document.getElementById('cancel-sub-confirm-desc');
  const btnExec = document.getElementById('btn-confirm-cancel-exec');

  if (step1) step1.style.display = 'none';
  if (step2) step2.style.display = 'block';
  if (confirmActions) confirmActions.style.display = 'flex';

  const fn = esc(cancelModalSub.fullname || 'Foydalanuvchi');
  const tc = esc(cancelModalSub.test_code || '');

  if (actionType === 'reject') {
    if (titleEl) {
      titleEl.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;margin-right:6px;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Javobni qabul qilmaslikni tasdiqlaysizmi?';
      titleEl.style.color = '#EF4444';
    }
    if (descEl) {
      descEl.innerHTML = `Haqiqatan ham <b>${fn}</b> ning #${tc} test bo'yicha topshirgan javoblarini <b>qabul qilmaslikni (rad etishni)</b> tasdiqlaysizmi?<br><br>• Natija bekor qilinadi va hisobga olinmaydi.<br>• O'quvchi testni qayta topshira olmaydi.<br>• O'quvchining shaxsiy Telegramiga xabar yuboriladi.`;
    }
    if (btnExec) {
      btnExec.textContent = 'Ha, qabul qilinmasin (Rad etish)';
      btnExec.className = 'btn btn-danger';
    }
  } else if (actionType === 'allow_retake') {
    if (titleEl) {
      titleEl.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;margin-right:6px;"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg> Qayta topshirishga ruxsat berishni tasdiqlaysizmi?';
      titleEl.style.color = '#2563EB';
    }
    if (descEl) {
      descEl.innerHTML = `Haqiqatan ham <b>${fn}</b> ga #${tc} testni <b>qaytadan topshirishga</b> ruxsat berishni tasdiqlaysizmi?<br><br>• Avvalgi topshirgan natijasi bazadan butunlay o'chiriladi.<br>• O'quvchi bot orqali testni qaytadan boshidan ishlashi mumkin bo'ladi.<br>• O'quvchining shaxsiy Telegramiga testni qayta topshirishi mumkinligi haqida xabar boradi.`;
    }
    if (btnExec) {
      btnExec.textContent = 'Ha, qayta topshirishga ruxsat';
      btnExec.className = 'btn btn-primary';
    }
  }
}
window.selectCancelAction = selectCancelAction;

function backToCancelStep1() {
  selectedCancelActionType = null;
  const step1 = document.getElementById('cancel-sub-step-1');
  const step2 = document.getElementById('cancel-sub-step-2');
  const confirmActions = document.getElementById('cancel-sub-confirm-actions');

  if (step1) step1.style.display = 'block';
  if (step2) step2.style.display = 'none';
  if (confirmActions) confirmActions.style.display = 'none';
}
window.backToCancelStep1 = backToCancelStep1;

async function executeCancelSubmission() {
  if (!cancelModalSub || !selectedCancelActionType) return;

  const btnExec = document.getElementById('btn-confirm-cancel-exec');
  if (btnExec) {
    btnExec.disabled = true;
    btnExec.textContent = 'Bajarilmoqda...';
  }

  try {
    const res = await fetch('/api/dashboard/submissions/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        submission_id: cancelModalSub.id,
        action: selectedCancelActionType
      })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Xatolik yuz berdi');
    }

    showToast(data.message || 'Muvaffaqiyatli bajarildi!', 'success');
    closeCancelSubModal();
    closeSubmissionModal();

    // Reload submissions and overview
    if (typeof loadSubmissions === 'function') loadSubmissions();
    if (typeof loadOverview === 'function') loadOverview();
  } catch (err) {
    showToast(String(err.message || err), 'danger');
  } finally {
    if (btnExec) {
      btnExec.disabled = false;
      btnExec.textContent = 'Ha, tasdiqlayman';
    }
  }
}
window.executeCancelSubmission = executeCancelSubmission;

