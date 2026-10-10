/**
 * GLOBAL SEARCH & KNOWLEDGE BASE ENGINE — js/search-engine.js
 * Lupa qidiruv tizimi, savol-javoblar bazasi va tezkor amallar
 */

(function(window) {
  'use strict';

// ── HELPER FALLBACKS & ENVIRONMENT GUARDS ─────────────────
var t = function(key) {
  if (typeof window.t === 'function') return window.t(key);
  return key;
};

var escHtml = function(s) {
  if (typeof window.escHtml === 'function') return window.escHtml(s);
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
};

var formatDateOnly = function(ts) {
  if (typeof window.formatDateOnly === 'function') return window.formatDateOnly(ts);
  if (!ts) return '—';
  var d = new Date(ts * 1000);
  return d.getDate() + '.' + (d.getMonth() + 1) + '.' + d.getFullYear();
};

var getGradeFromScore = function(sc, max) {
  if (typeof window.getGradeFromScore === 'function') return window.getGradeFromScore(sc, max);
  return '—';
};

var apiGet = function(url) {
  if (typeof window.apiGet === 'function') return window.apiGet(url);
  var headers = (typeof window.getAuthHeaders === 'function') ? window.getAuthHeaders() : {};
  return fetch(url, { headers: headers }).then(function(r) { return r.json(); });
};

var searchState = {
  searchQuery: '',
  searchFilter: 'all'
};

// ──────────────────────────────────────────────────────────
// GLOBAL SEARCH & KNOWLEDGE BASE (LUPA TIZIMI)
// ──────────────────────────────────────────────────────────

var BOT_KNOWLEDGE_BASE = [
  {
    id: 'about_bot',
    title: "Fizika — Milliy Sertifikat haqida",
    category: 'about',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    keywords: 'bot haqida nima fizika milliy sertifikat tizim platforma',
    summary: "Fizika fanidan milliy sertifikat test tekshirish va bilimni baholash tizimi.",
    fullHtml: "<h4>Fizika — Milliy Sertifikat Test Tizimi</h4>" +
              "<p>Ushbu tizim o'quvchilarning fizika fanidan bilim darajasini zamonaviy psixometrik standartlar (Rasch modeli) asosida xolis va adolatli baholash uchun ishlab chiqilgan.</p>" +
              "<ul>" +
              "<li><b>Rasmiy Telegram Bot:</b> @fizika_rash_testbot</li>" +
              "<li><b>Rahbar va Bosh Admin:</b> Shohruh Eshimbetov</li>" +
              "<li><b>Asosiy yo'nalish:</b> Milliy sertifikat, DTM va olimpiada testlari tahlili</li>" +
              "<li><b>Format:</b> Har bir test bo'yicha batafsil savolma-savol tahlil va Rasmiy PDF reyting jadvali taqdim etiladi.</li>" +
              "</ul>"
  },
  {
    id: 'rasch_model',
    title: "Rasch modeli va Ball qanday hisoblanadi?",
    category: 'about',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
    keywords: 'rasch model ball hisoblash baholash qiyinlik daraja theta adolatli',
    summary: "Nega oddiy foiz emas, balki Rasch modeli? Savol qiyinligi va qobiliyat o'lchovi.",
    fullHtml: "<h4>Rasch Modeli Qanday Ishlaydi?</h4>" +
              "<p>Rasch modeli — bu Kembrij, SAT va O'zbekiston Milliy sertifikat imtihonlarida qo'llaniladigan xalqaro standartdir.</p>" +
              "<p><b>Oddiy testlardan farqi:</b></p>" +
              "<ul>" +
              "<li>Oddiy testda oson savol ham, eng qiyin savol ham bir xil 1 ball beradi.</li>" +
              "<li><b>Rasch modelida esa:</b> Har bir savolning o'z qiyinlik darajasi (Item Difficulty, Beta) mavjud. Qiyin savolni to'g'ri topgan o'quvchining qobiliyati (Theta) yuqoriroq baholanadi.</li>" +
              "<li>Tasodifiy taxmin qilib topish (guessing) ta'siri kamaytiriladi va yakunda 0 dan 100 gacha shkalalangan eng aniq ball chiqariladi.</li>" +
              "</ul>"
  },
  {
    id: 'national_cert',
    title: "Milliy Sertifikat darajalari (A+, A, B+, B, C)",
    category: 'about',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>',
    keywords: 'milliy sertifikat daraja a+ a b+ b c foiz ball talab darajalari',
    summary: "Sertifikat olish uchun qancha ball to'plash kerak va qaysi darajalar beriladi.",
    fullHtml: "<h4>Milliy Sertifikat Baholash Mezonlari</h4>" +
              "<p>Tizimda Rasch modeli bo'yicha to'plangan umumiy ballga ko'ra quyidagi darajalar belgilanadi:</p>" +
              "<ul>" +
              "<li><b>A+ Daraja:</b> 90% va undan yuqori — Eng a'lo natija, maksimal imtiyoz.</li>" +
              "<li><b>A Daraja:</b> 80% dan 89.9% gacha — Yuqori darajali sertifikat.</li>" +
              "<li><b>B+ Daraja:</b> 70% dan 79.9% gacha — Yaxshi natija.</li>" +
              "<li><b>B Daraja:</b> 60% dan 69.9% gacha — O'rtacha ijobiy daraja.</li>" +
              "<li><b>C Daraja:</b> 50% dan 59.9% gacha — Qoniqarli minimal sertifikat darajasi.</li>" +
              "<li><b>Qoniqarsiz:</b> 50% dan past — Sertifikat berilmaydi, bilimni oshirish tavsiya etiladi.</li>" +
              "</ul>"
  },
  {
    id: 'test_rules',
    title: "Test topshirish qoidalari va Vaqt chegarasi",
    category: 'about',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    keywords: 'qoida qoidalar vaqt topshirish tartibi javob format 1a2b3c',
    summary: "Test kodi, javoblarni yuborish tartibi va vaqt nazorati haqida muhim qoidalar.",
    fullHtml: "<h4>Test Topshirish Qoidalari</h4>" +
              "<ul>" +
              "<li><b>1. Testni boshlash:</b> Botda yoki Mini ilovada faol test kodini (masalan, #49) tanlang.</li>" +
              "<li><b>2. Vaqt chegarasi:</b> Har bir test uchun aniq vaqt belgilanadi (masalan, 120 daqiqa). Vaqt tugagach test avtomatik yakunlanadi.</li>" +
              "<li><b>3. Javoblarni yuborish formati:</b> Bot orqali topshirishda javoblarni ketma-ketlikda yuboring (Masalan: <code>1a2b3c4d5e...</code>).</li>" +
              "<li><b>4. Bir martalik topshirish:</b> Har bir test faqat bir marta topshiriladi. Qayta topshirish taqiqlanadi.</li>" +
              "</ul>"
  },
  {
    id: 'pin_security',
    title: "PIN kod va Shaxsiy xavfsizlik",
    category: 'about',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    keywords: 'pin kod xavfsizlik parol profil himoya ozgartirish',
    summary: "Natijalaringiz va shaxsiy ma'lumotlaringizni himoyalovchi 4 xonali PIN kod.",
    fullHtml: "<h4>PIN Kod Tizimi</h4>" +
              "<p>Natijalaringiz va profilingiz begona shaxslar qo'liga tushmasligi uchun 4 xonali shaxsiy PIN kod o'rnatiladi.</p>" +
              "<ul>" +
              "<li>PIN kodni o'zgartirish uchun: <b>Profil</b> bo'limidagi <b>«Profilni tahrirlash»</b> yoki sozlamalardan foydalaning.</li>" +
              "<li>Agar PIN kodingizni esdan chiqarsangiz, bot ma'muriga (@eshmbetov) murojaat qiling.</li>" +
              "</ul>"
  },
  {
    id: 'contact_admin',
    title: "Ma'muriyat bilan bog'lanish va Yordam",
    category: 'about',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
    keywords: 'admin murojaat yordam boglanish eshmbetov kontakt aloqa savol muammo',
    summary: "Savol, taklif va texnik muammolar bo'yicha administrator bilan aloqa.",
    fullHtml: "<h4>Bog'lanish va Qo'llab-quvvatlash</h4>" +
              "<p>Har qanday savol, taklif yoki texnik muammolar yuzasidan quyidagi kontaktlarga murojaat qilishingiz mumkin:</p>" +
              "<ul>" +
              "<li><b>Bosh Admin:</b> @eshmbetov</li>" +
              "<li><b>Rasmiy Bot:</b> @fizika_rash_testbot</li>" +
              "<li><b>Rasmiy Kanal:</b> Fizika Milliy Sertifikat o'quv kanali</li>" +
              "</ul>" +
              "<div style='margin-top:14px;'><a href='https://t.me/eshmbetov' target='_blank' style='display:inline-flex;align-items:center;gap:6px;padding:10px 16px;border-radius:12px;background:linear-gradient(135deg,#3B82F6,#6366F1);color:white;text-decoration:none;font-weight:700;'><span>Adminga yozish (@eshmbetov)</span><svg width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5'><polyline points='9 18 15 12 9 6'/></svg></a></div>"
  }
];

var QUICK_ACTIONS = [
  {
    id: 'act_tests',
    title: "Testlar bo'limiga o'tish",
    sub: "Barcha faol va rejalashtirilgan testlarni ko'rish",
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    keywords: 'test testlar kutilayotgan faol topshirish',
    action: function() { closeGlobalSearch(); switchTab('home'); }
  },
  {
    id: 'act_results',
    title: "Mening natijalarim",
    sub: "Topshirilgan testlar, ballar va sertifikat darajasi",
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    keywords: 'natija natijalarim ball sertifikat reyting tarix',
    action: function() { closeGlobalSearch(); switchTab('tests'); }
  },
  {
    id: 'act_profile',
    title: "Profilim va Shaxsiy ma'lumotlar",
    sub: "Ism, telefon raqami va statusni ko'rish",
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    keywords: 'profil ism telefon hisob status shaxsiy',
    action: function() { closeGlobalSearch(); switchTab('profile'); }
  },
  {
    id: 'act_edit_profile',
    title: "Profilni tahrirlash",
    sub: "Ism va telefon raqamini o'zgartirish",
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    keywords: 'profil tahrirlash ism telefon yangilash',
    action: function() { closeGlobalSearch(); switchTab('profile'); if (typeof openEditProfileModal === 'function') openEditProfileModal(); }
  },
  {
    id: 'act_theme',
    title: "Mavzuni almashtirish (Dark / Light)",
    sub: "Tungi yoki kunduzgi ko'rinish rejimiga o'tish",
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
    keywords: 'tema mavzu qorongu oq dark light tun',
    action: function() { toggleTheme(); renderSearchResults(); }
  },
  {
    id: 'act_lang',
    title: "Tilni o'zgartirish (Language)",
    sub: "O'zbekcha / Русский / English",
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    keywords: 'til tilni almashtirish uz ru en language',
    action: function() { cycleLang(); renderSearchResults(); }
  }
];

async function openGlobalSearch() {
  var modal = document.getElementById('global-search-modal');
  if (!modal) return;
  modal.style.display = 'flex';

  var inp = document.getElementById('global-search-input');
  if (inp) {
    inp.value = '';
    setTimeout(function() { inp.focus(); }, 150);
  }
  var clearBtn = document.getElementById('search-clear-btn');
  if (clearBtn) clearBtn.style.display = 'none';

  searchState.searchFilter = 'all';
  searchState.searchQuery = '';
  updateSearchChipUI('all');

  // Active tests va past results ni fonda yuklab turish (agar hali yuklanmagan bo'lsa)
  var tgId = (window.state && window.state.tgUser && window.state.tgUser.id) || 0;
  
  if (!window.availableActiveTests || window.availableActiveTests.length === 0) {
    if (window._availableTests && window._availableTests.length > 0) {
      window.availableActiveTests = window._availableTests;
    } else {
      apiGet('/api/app/active-tests?tg_id=' + tgId).then(function(d) {
        if (d && d.success) {
          window.availableActiveTests = d.tests || [];
          window._availableTests = window.availableActiveTests;
          renderSearchResults();
        }
      }).catch(function() {});
    }
  }

  if (!window.cachedMyResults || window.cachedMyResults.length === 0) {
    if (window._myResults && window._myResults.length > 0) {
      window.cachedMyResults = window._myResults;
    } else {
      apiGet('/api/app/my-results?tg_id=' + tgId).then(function(d) {
        if (d && d.success) {
          window.cachedMyResults = d.results || [];
          window._myResults = window.cachedMyResults;
          renderSearchResults();
        }
      }).catch(function() {});
    }
  }

  renderSearchResults();
}

function closeGlobalSearch(e) {
  if (e && e.target && e.target.id !== 'global-search-modal' && !e.target.classList.contains('search-close-btn')) return;
  var modal = document.getElementById('global-search-modal');
  if (modal) modal.style.display = 'none';
}

function clearGlobalSearch() {
  var inp = document.getElementById('global-search-input');
  if (inp) {
    inp.value = '';
    inp.focus();
  }
  handleGlobalSearch('');
}

function selectSearchFilter(filterType) {
  searchState.searchFilter = filterType;
  updateSearchChipUI(filterType);
  renderSearchResults();
}

function updateSearchChipUI(activeFilter) {
  var chips = document.querySelectorAll('.search-chip');
  chips.forEach(function(btn) {
    btn.classList.remove('active');
  });
  var activeBtn = document.getElementById('chip-' + activeFilter);
  if (activeBtn) activeBtn.classList.add('active');
}

var searchDebounceTimer = null;
function handleGlobalSearch(query) {
  searchState.searchQuery = (query || '').trim();
  var clearBtn = document.getElementById('search-clear-btn');
  if (clearBtn) {
    clearBtn.style.display = searchState.searchQuery ? 'flex' : 'none';
  }
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(function() {
    renderSearchResults();
  }, 250);
}

function renderSearchResults() {
  var container = document.getElementById('global-search-results');
  if (!container) return;

  var q = (searchState.searchQuery || '').toLowerCase().trim();
  var filter = searchState.searchFilter || 'all';

  var activeTests = window.availableActiveTests || window._availableTests || [];
  var myResults = window.cachedMyResults || window._myResults || [];
  var knowledgeBase = BOT_KNOWLEDGE_BASE || [];
  var quickActions = QUICK_ACTIONS || [];

  // Filter Active Tests
  var matchedTests = [];
  if (filter === 'all' || filter === 'tests') {
    matchedTests = activeTests.filter(function(testItem) {
      if (!q) return true;
      var title = (testItem.title || '').toLowerCase();
      var code = (testItem.test_code || '').toLowerCase();
      var subj = (testItem.subject || '').toLowerCase();
      return title.indexOf(q) !== -1 || code.indexOf(q) !== -1 || subj.indexOf(q) !== -1;
    });
  }

  // Filter My Results
  var matchedResults = [];
  if (filter === 'all' || filter === 'results') {
    matchedResults = myResults.filter(function(r) {
      if (!q) return true;
      var title = (r.test_title || r.title || '').toLowerCase();
      var code = (r.test_code || '').toLowerCase();
      var grade = (r.grade || '').toLowerCase();
      var score = String(r.score || '');
      return title.indexOf(q) !== -1 || code.indexOf(q) !== -1 || grade.indexOf(q) !== -1 || score.indexOf(q) !== -1;
    });
  }

  // Filter Bot Knowledge Base
  var matchedKnowledge = [];
  if (filter === 'all' || filter === 'about') {
    matchedKnowledge = knowledgeBase.filter(function(knowItem) {
      if (!q) return true;
      var title = (knowItem.title || '').toLowerCase();
      var kw = (knowItem.keywords || '').toLowerCase();
      var sum = (knowItem.summary || '').toLowerCase();
      return title.indexOf(q) !== -1 || kw.indexOf(q) !== -1 || sum.indexOf(q) !== -1;
    });
  }

  // Filter Quick Actions
  var matchedActions = [];
  if (filter === 'all') {
    matchedActions = quickActions.filter(function(a) {
      if (!q) return true;
      var title = (a.title || '').toLowerCase();
      var sub = (a.sub || '').toLowerCase();
      var kw = (a.keywords || '').toLowerCase();
      return title.indexOf(q) !== -1 || sub.indexOf(q) !== -1 || kw.indexOf(q) !== -1;
    });
  }

  var totalFound = matchedTests.length + matchedResults.length + matchedKnowledge.length + matchedActions.length;

  if (totalFound === 0) {
    container.innerHTML =
      '<div class="search-empty-state">' +
        '<div class="search-empty-icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>' +
        '<div class="search-empty-title">' + t('search_empty_title') + '</div>' +
        '<div class="search-empty-desc">' + t('search_empty_desc') + '</div>' +
      '</div>';
    return;
  }

  var html = '';

  // 1. TESTS GROUP
  if (matchedTests.length > 0) {
    html += '<div class="search-group-container">' +
      '<div class="search-group-header">' +
        '<div class="search-group-title"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg> ' + t('search_group_tests') + '</div>' +
        '<span class="search-group-badge">' + matchedTests.length + ' ta</span>' +
      '</div>' +
      '<div class="search-card-list">';
    matchedTests.forEach(function(test) {
      var isDone = test.is_participated || (test.user_status && test.user_status.has_submitted);
      var statusPill = isDone
        ? '<span class="search-card-pill pill-green"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="display:inline-block;vertical-align:-1px;margin-right:3px"><polyline points="20 6 9 17 4 12"/></svg>Topshirilgan</span>'
        : (test.is_active ? '<span class="search-card-pill pill-blue"><span class="status-dot dot-active"></span>Faol</span>' : '<span class="search-card-pill">Yakunlangan</span>');
      var codeStr = test.test_code ? ('Kod: #' + test.test_code) : '';
      var qCount = test.total_questions ? (test.total_questions + ' ta savol') : '45 ta savol';

      html += '<div class="search-card-item" onclick="handleSearchSelectTest(' + test.id + ', \'' + (test.test_code || '') + '\', ' + (isDone ? 'true' : 'false') + ')">' +
        '<div class="search-card-icon icon-blue"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></div>' +
        '<div class="search-card-info">' +
          '<div class="search-card-title">' + escHtml(test.title || 'Fizika Testi') + '</div>' +
          '<div class="search-card-sub">' +
            statusPill +
            (codeStr ? '<span>' + escHtml(codeStr) + '</span>' : '') +
            '<span>' + qCount + '</span>' +
          '</div>' +
        '</div>' +
        '<span class="search-card-arrow"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
      '</div>';
    });
    html += '</div></div>';
  }

  // 2. RESULTS GROUP
  if (matchedResults.length > 0) {
    html += '<div class="search-group-container">' +
      '<div class="search-group-header">' +
        '<div class="search-group-title"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg> ' + t('search_group_results') + '</div>' +
        '<span class="search-group-badge">' + matchedResults.length + ' ta</span>' +
      '</div>' +
      '<div class="search-card-list">';
    matchedResults.forEach(function(res, idx) {
      var scoreVal = (res.score != null) ? res.score : 0;
      var gradeVal = res.grade || getGradeFromScore(scoreVal, res.max_score || 100);
      var dateStr = formatDateOnly(res.submitted_at);

      html += '<div class="search-card-item" onclick="handleSearchSelectResult(' + idx + ')">' +
        '<div class="search-card-icon icon-green"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.45 1-1 1H7"/><path d="M14 14.66V17c0 .55.45 1 1 1h2"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2z"/></svg></div>' +
        '<div class="search-card-info">' +
          '<div class="search-card-title">' + escHtml(res.test_title || res.title || 'Test Natijasi') + '</div>' +
          '<div class="search-card-sub">' +
            '<span class="search-card-pill pill-green">' + scoreVal + ' ball (' + gradeVal + ')</span>' +
            '<span><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-right:3px"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' + dateStr + '</span>' +
          '</div>' +
        '</div>' +
        '<span class="search-card-arrow"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
      '</div>';
    });
    html += '</div></div>';
  }

  // 3. BOT HAQIDA (KNOWLEDGE BASE)
  if (matchedKnowledge.length > 0) {
    html += '<div class="search-group-container">' +
      '<div class="search-group-header">' +
        '<div class="search-group-title"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg> ' + t('search_group_about') + '</div>' +
        '<span class="search-group-badge">' + matchedKnowledge.length + ' ta</span>' +
      '</div>' +
      '<div class="search-card-list">';
    matchedKnowledge.forEach(function(item) {
      html += '<div class="search-card-item" onclick="showAboutInfoModal(\'' + item.id + '\')">' +
        '<div class="search-card-icon icon-purple">' + item.icon + '</div>' +
        '<div class="search-card-info">' +
          '<div class="search-card-title">' + escHtml(item.title) + '</div>' +
          '<div class="search-card-sub">' + escHtml(item.summary) + '</div>' +
        '</div>' +
        '<span class="search-card-arrow"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
      '</div>';
    });
    html += '</div></div>';
  }

  // 4. QUICK ACTIONS
  if (matchedActions.length > 0 && filter === 'all') {
    html += '<div class="search-group-container">' +
      '<div class="search-group-header">' +
        '<div class="search-group-title"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-2px;margin-right:4px"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> ' + t('search_group_actions') + '</div>' +
      '</div>' +
      '<div class="search-card-list">';
    matchedActions.forEach(function(act, idx) {
      html += '<div class="search-card-item" onclick="handleSearchAction(' + idx + ')">' +
        '<div class="search-card-icon icon-amber">' + act.icon + '</div>' +
        '<div class="search-card-info">' +
          '<div class="search-card-title">' + escHtml(act.title) + '</div>' +
          '<div class="search-card-sub">' + escHtml(act.sub) + '</div>' +
        '</div>' +
        '<span class="search-card-arrow"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
      '</div>';
    });
    html += '</div></div>';
  }

  container.innerHTML = html;
}

function handleSearchSelectTest(testId, testCode, isDone) {
  closeGlobalSearch();
  if (isDone) {
    if (typeof window.openPastTestResult === 'function') {
      window.openPastTestResult(testId);
    } else if (typeof window.showResultModal === 'function') {
      window.showResultModal({ test_id: testId, id: testId });
    }
  } else {
    if (typeof window.switchTab === 'function') window.switchTab('home');
    setTimeout(function() {
      var el = document.getElementById('test-card-' + testId);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 150);
  }
}

function handleSearchSelectResult(resIndex) {
  closeGlobalSearch();
  var myResults = window.cachedMyResults || window._myResults || [];
  if (myResults[resIndex]) {
    if (typeof window.showResultModal === 'function') {
      window.showResultModal(myResults[resIndex]);
    }
  } else {
    if (typeof window.switchTab === 'function') {
      window.switchTab('tests');
    }
  }
}

function handleSearchAction(actIndex) {
  if (QUICK_ACTIONS[actIndex] && typeof QUICK_ACTIONS[actIndex].action === 'function') {
    QUICK_ACTIONS[actIndex].action();
  }
}

function showAboutInfoModal(infoId) {
  var item = BOT_KNOWLEDGE_BASE.find(function(k) { return k.id === infoId; });
  if (!item) return;

  var modal = document.getElementById('about-info-modal');
  var title = document.getElementById('about-info-title');
  var body = document.getElementById('about-info-body');
  if (!modal || !title || !body) return;

  title.innerHTML = '<span style="margin-right:6px;">' + item.icon + '</span> ' + escHtml(item.title);
  body.innerHTML = item.fullHtml;
  modal.style.display = 'flex';
}

function closeAboutInfoModal(e) {
  if (e && e.target && e.target.id !== 'about-info-modal' && !e.target.classList.contains('modal-close')) return;
  var modal = document.getElementById('about-info-modal');
  if (modal) modal.style.display = 'none';
}

// ESC tugmasi bosilganda qidiruv modalini yopish
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    var sm = document.getElementById('global-search-modal');
    if (sm && sm.style.display !== 'none') closeGlobalSearch();
    var am = document.getElementById('about-info-modal');
    if (am && am.style.display !== 'none') closeAboutInfoModal();
  }
});


  // Global Scope eksport
  window.BOT_KNOWLEDGE_BASE = BOT_KNOWLEDGE_BASE;
  window.QUICK_ACTIONS = QUICK_ACTIONS;
  window.openGlobalSearch = openGlobalSearch;
  window.closeGlobalSearch = closeGlobalSearch;
  window.clearGlobalSearch = clearGlobalSearch;
  window.selectSearchFilter = selectSearchFilter;
  window.updateSearchChipUI = updateSearchChipUI;
  window.handleGlobalSearch = handleGlobalSearch;
  window.renderSearchResults = renderSearchResults;
  window.handleSearchSelectTest = handleSearchSelectTest;
  window.handleSearchSelectResult = handleSearchSelectResult;
  window.handleSearchAction = handleSearchAction;
  window.showAboutInfoModal = showAboutInfoModal;
  window.closeAboutInfoModal = closeAboutInfoModal;

})(window);
