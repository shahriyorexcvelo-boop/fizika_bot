/**
 * Test Tekshirish Tizimi — Asosiy Mini App Mantiqi
 */

const TestApp = {
  testId: 1,
  testCode: 'TEST-01',
  testTitle: 'Fizika Blok Test',
  subject: 'Fizika',
  userTgId: 0,
  userFullname: 'Foydalanuvchi',
  isDarkMode: false,
  minSubmitInfo: null,
  minSubmitTimerInterval: null,
  isAdmin: false,

  // Foydalanuvchi belgilagan javoblar
  answers: {},

  init() {
    if (window.BM_LOGO_B64) {
      document.querySelectorAll('.intro-logo-img, .header-bm-logo').forEach(img => {
        img.src = window.BM_LOGO_B64;
      });
    }

    // 1. Telegram WebApp ni sozlash va tekshirish
    const isTelegramWebApp = Boolean(
      window.Telegram &&
      window.Telegram.WebApp &&
      (
        (window.Telegram.WebApp.initData && window.Telegram.WebApp.initData.length > 5) ||
        (window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.user)
      )
    );

    if (window.Telegram && window.Telegram.WebApp) {
      const tg = window.Telegram.WebApp;
      try { tg.ready(); tg.expand(); } catch(e) {}

      // Foydalanuvchi ma'lumotlari
      if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        const u = tg.initDataUnsafe.user;
        this.userTgId = u.id;
        this.userFullname = `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.username || 'Foydalanuvchi';
      }
    }

    // Mavzu (birinchi kirishda oq/light, agar foydalanuvchi qoraga o'tkazsa saqlanadi)
    const savedTheme = localStorage.getItem('app_theme') || 'light';
    this.setTheme(savedTheme === 'dark');

    // 2. URL parametrlardan test ma'lumotlarini olish
    const params = new URLSearchParams(window.location.search);
    if (params.has('test_code')) this.testCode = params.get('test_code');
    if (params.has('test_id')) this.testId = parseInt(params.get('test_id')) || 1;
    if (params.has('title')) this.testTitle = params.get('title');
    if (params.has('subject')) this.subject = params.get('subject');

    // Faqat agar Telegram WebApp ichida bo'lsa yoki URL parametrda tg_id bo'lsa fallback olish
    if (!this.userTgId && params.has('tg_id')) {
      const parsedId = parseInt(params.get('tg_id'), 10);
      if (parsedId && !isNaN(parsedId)) {
        this.userTgId = parsedId;
      }
    }
    if (!this.userTgId) {
      try {
        const savedUser = JSON.parse(localStorage.getItem('app_user') || '{}');
        if (savedUser && savedUser.tg_id) {
          this.userTgId = parseInt(savedUser.tg_id, 10);
        }
      } catch (e) {}
    }

    // ⚠️ AGAR WEB ORQALI KIRILGAN BO'LSA (TELEGRAMSIZ) — TO'LIQ BLOKLASH!
    if (!this.userTgId || this.userTgId <= 0) {
      const webBlock = document.getElementById('web-block-screen');
      if (webBlock) {
        webBlock.style.display = 'flex';
      }
      const introSplash = document.getElementById('intro-splash') || document.getElementById('splashScreen');
      if (introSplash) {
        introSplash.style.display = 'none';
      }
      const testContent = document.querySelector('.test-body') || document.querySelector('.main-container');
      if (testContent) {
        testContent.style.filter = 'blur(10px)';
        testContent.style.pointerEvents = 'none';
      }
      return; // To'xtatish! Savollarni yuklamaslik va ishlashga ruxsat bermaslik!
    }

    // UI ga o'rnatish
    const titleEl = document.getElementById('test-title-display');
    const codeEl = document.getElementById('test-code-display');
    const subjectEl = document.getElementById('test-subject-badge');
    const userEl = document.getElementById('user-welcome-text');

    if (titleEl) {
      titleEl.textContent = this.testCode ? `#${this.testCode} test` : this.testTitle;
    }
    if (codeEl) codeEl.textContent = `KOD: #${this.testCode}`;
    if (subjectEl) subjectEl.textContent = `📐 ${this.subject}`;
    if (userEl) userEl.textContent = `Ishtirokchi: ${this.userFullname}`;

    // 3. Savollarni render qilish
    this.renderQuestions();
    this.renderMapGrid();
    this.updateProgress();

    // 3.1. Agar telefon o'chib yongan yoki sahifa yangilangan bo'lsa, javoblarni xotiradan tiklash
    this.restoreAnswersFromStorage();

    // 4. Mavzuga mos kirish animatsiyasini ishga tushirish
    this.runIntroAnimation();

    // 5. Allaqachon topshirganlikni va 45 daqiqalik cheklovni tekshirish
    if (this.userTgId) {
      fetch('/api/app/active-tests?tg_id=' + this.userTgId)
        .then(function(res) { return res.json(); })
        .then(function(d) {
          if (d && d.tests) {
            TestApp.isAdmin = Boolean(d.is_admin);
            var cur = d.tests.find(function(t) { return Number(t.id) === Number(TestApp.testId); });
            if (cur) {
              if (cur.min_submit_info) {
                TestApp.minSubmitInfo = cur.min_submit_info;
                TestApp.startMinSubmitTimer();
              }
              if (cur.already_submitted) {
                var submitBtn = document.getElementById('btn-submit-test');
                if (submitBtn) {
                  submitBtn.disabled = true;
                  submitBtn.textContent = 'Topshirilgan ✅';
                  submitBtn.style.background = '#10b981';
                  submitBtn.style.cursor = 'not-allowed';
                }
                setTimeout(function() {
                  alert("⛔️ Siz ushbu testni allaqachon topshirgansiz!\n\nJavoblaringiz qabul qilingan. Natijalar Rasch modeli tahlili e'lon qilingandan so'ng botingizga yuboriladi.");
                }, 400);
              }
            }
          }
        }).catch(function(e) {});
    } else {
      var submitBtn = document.getElementById('btn-submit-test');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.5';
        submitBtn.style.cursor = 'not-allowed';
        submitBtn.textContent = 'Bot orqali kiring 🔒';
      }
    }
  },

  finishSplashImmediately() {
    const splash = document.getElementById('intro-splash') || document.getElementById('splashScreen');
    if (!splash) return;
    if (this._splashDismissed) return;
    this._splashDismissed = true;

    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      try { window.Telegram.WebApp.HapticFeedback.impactOccurred('medium'); } catch(e) {}
    }

    splash.classList.add('dismissed');
    setTimeout(() => {
      splash.style.display = 'none';
    }, 600);
  },

  runIntroAnimation() {
    const splash = document.getElementById('intro-splash') || document.getElementById('splashScreen');
    if (!splash) return;

    window.dismissSplash = () => this.finishSplashImmediately();
    window.finishSplashImmediately = () => this.finishSplashImmediately();

    // 3200ms dan so'ng avtomatik o'tish
    setTimeout(() => {
      this.finishSplashImmediately();
    }, 3200);
  },

  toggleTheme() {
    this.setTheme(!this.isDarkMode);
  },

  setTheme(isDark) {
    this.isDarkMode = isDark;
    document.body.classList.toggle('dark-mode', isDark);
    localStorage.setItem('app_theme', isDark ? 'dark' : 'light');
  },

  // ----------------------------------------------------
  // SAVOLLARNI GENERATSIYA QILISH
  // ----------------------------------------------------
  renderQuestions() {
    const part1 = document.getElementById('questions-part-1');
    const part2 = document.getElementById('questions-part-2');
    const part3 = document.getElementById('questions-part-3');

    // 1. 1-32 Variantli Savollar (A, B, C, D)
    if (part1) {
      let html1 = '';
      for (let q = 1; q <= 32; q++) {
        html1 += `
          <div class="question-card" id="qcard-${q}">
            <span class="question-num-tag">${q}-savol</span>
            <div class="options-group">
              ${['A', 'B', 'C', 'D'].map(opt => `
                <button class="option-btn" id="opt-${q}-${opt}" onclick="TestApp.selectOption(${q}, '${opt}')">
                  ${opt}
                </button>
              `).join('')}
            </div>
          </div>
        `;
      }
      part1.innerHTML = html1;
    }

    // 2. 33, 34, 35 savollar: 6 ta variantli (A, B, C, D, E, F)
    if (part2) {
      let html2 = '';
      for (let q = 33; q <= 35; q++) {
        html2 += `
          <div class="question-card" id="qcard-${q}" style="flex-direction: column; align-items: flex-start; gap: 8px; margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; width: 100%;">
              <span class="question-num-tag" style="font-size: 13.5px; font-weight: 800;">${q}-savol (6 ta variant)</span>
              <span style="font-size: 11px; color: var(--text-muted);">Maxsus savol</span>
            </div>
            <div class="options-group-6" style="width: 100%;">
              ${['A', 'B', 'C', 'D', 'E', 'F'].map(opt => `
                <button class="option-btn" id="opt-${q}-${opt}" onclick="TestApp.selectOption(${q}, '${opt}')">
                  ${opt}
                </button>
              `).join('')}
            </div>
          </div>
        `;
      }
      part2.innerHTML = html2;
    }

    // 3. 36-45 Yopiq Savollar (a va b qismlar alohida qator shaklida)
    if (part3) {
      let html3 = '';
      for (let q = 36; q <= 45; q++) {
        for (let sub of ['a', 'b']) {
          const key = `${q}${sub}`;
          html3 += `
            <div class="open-question-row" id="qrow-${key}">
              <div class="savol-badge">${key}-savol</div>
              <div class="savol-input-box" id="box-${key}" onclick="MathKeyboard.openFor('${key}')">
                <input type="text" class="savol-input" id="input-${key}" readonly inputmode="none" placeholder="" onclick="MathKeyboard.openFor('${key}')">
              </div>
              <button type="button" class="btn-kb-icon" onclick="MathKeyboard.openFor('${key}')" title="Klaviaturani ochish">⌨️</button>
            </div>
          `;
        }
      }
      part3.innerHTML = html3;
    }
  },

  // ----------------------------------------------------
  // LOCALSTORAGE AUTOSAVE & RESTORE (Javoblar o'chib ketmasligi uchun)
  // ----------------------------------------------------
  getStorageKey() {
    const tid = this.testId || '1';
    const uid = this.userTgId || '0';
    return `bm_answers_test_${tid}_user_${uid}`;
  },

  saveAnswersToStorage() {
    try {
      if (!this.testId) return;
      // 36a-45b ochiq savollar qiymatini DOM dan olish
      for (let q = 36; q <= 45; q++) {
        for (let sub of ['a', 'b']) {
          const key = `${q}${sub}`;
          const input = document.getElementById(`input-${key}`);
          if (input && input.value !== undefined) {
            this.answers[key] = input.value.trim();
          }
        }
      }
      const key = this.getStorageKey();
      localStorage.setItem(key, JSON.stringify(this.answers));
    } catch (e) {
      console.warn('Storage save error:', e);
    }
  },

  restoreAnswersFromStorage() {
    try {
      const key = this.getStorageKey();
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (!saved || typeof saved !== 'object') return;

      this.answers = Object.assign({}, saved);

      // 1-35 variantli savollarni tiklash
      for (let q = 1; q <= 35; q++) {
        const opt = this.answers[String(q)];
        if (opt) {
          const btn = document.getElementById(`opt-${q}-${opt}`);
          if (btn) btn.classList.add('selected');
          const card = document.getElementById(`qcard-${q}`);
          if (card) card.classList.add('answered');
          this.updateMapItem(String(q), true);
        }
      }

      // 36a-45b ochiq savollarni tiklash
      for (let q = 36; q <= 45; q++) {
        for (let sub of ['a', 'b']) {
          const fieldKey = `${q}${sub}`;
          const val = this.answers[fieldKey];
          if (val !== undefined && val !== null && String(val).trim().length > 0) {
            const input = document.getElementById(`input-${fieldKey}`);
            if (input) input.value = val;
            const box = document.getElementById(`box-${fieldKey}`);
            if (box) box.classList.add('filled');
            this.updateMapItem(fieldKey, true);
          }
        }
      }

      this.updateProgress();
    } catch (e) {
      console.warn('Storage restore error:', e);
    }
  },

  clearAnswersFromStorage() {
    try {
      const key = this.getStorageKey();
      localStorage.removeItem(key);
    } catch (e) {}
  },

  // ----------------------------------------------------
  // JAVOBNI TANLASH VA O'RNATISH
  // ----------------------------------------------------
  selectOption(qNum, option) {
    if (typeof MathKeyboard !== 'undefined' && MathKeyboard.close) {
      MathKeyboard.close();
    }
    const key = String(qNum);
    const prev = this.answers[key];

    // Variant tugmalarini yangilash (33, 34, 35 savollar 6 ta variant: A, B, C, D, E, F)
    const opts = [33, 34, 35].includes(qNum) ? ['A', 'B', 'C', 'D', 'E', 'F'] : ['A', 'B', 'C', 'D'];
    opts.forEach(opt => {
      const btn = document.getElementById(`opt-${qNum}-${opt}`);
      if (btn) btn.classList.toggle('selected', opt === option);
    });

    this.answers[key] = option;

    const card = document.getElementById(`qcard-${qNum}`);
    if (card) card.classList.add('answered');

    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
    }

    this.updateProgress();
    this.updateMapItem(String(qNum), true);
    this.saveAnswersToStorage();
  },

  setOpenAnswer(fieldKey, val) {
    this.answers[fieldKey] = val;

    const box = document.getElementById(`box-${fieldKey}`);
    if (box) {
      box.classList.toggle('filled', (val || '').trim().length > 0);
    }

    const isFilled = (val || '').trim().length > 0;
    this.updateMapItem(fieldKey, isFilled);
    this.updateProgress();
    this.saveAnswersToStorage();
  },

  // ----------------------------------------------------
  // PROGRESS VA XARITA (JAMI 55 TA SAVOL: 1-35 VA 36a-45b)
  // ----------------------------------------------------
  renderMapGrid() {
    const grid = document.getElementById('map-grid');
    if (!grid) return;

    let html = '';
    // 1-35 savollar
    for (let q = 1; q <= 35; q++) {
      html += `
        <button class="map-num-btn" id="map-btn-${q}" onclick="TestApp.scrollToQuestion('${q}')">
          ${q}
        </button>
      `;
    }
    // 36a dan 45b gacha (20 ta alohida savol)
    for (let q = 36; q <= 45; q++) {
      for (let sub of ['a', 'b']) {
        const key = `${q}${sub}`;
        html += `
          <button class="map-num-btn open-map-btn" id="map-btn-${key}" onclick="TestApp.scrollToQuestion('${key}')" style="font-size: 11.5px; font-weight: 800; min-width: 36px; padding: 4px 2px;">
            ${key}
          </button>
        `;
      }
    }
    grid.innerHTML = html;
  },

  toggleNavMap() {
    const map = document.getElementById('questions-nav-map');
    const arrow = document.getElementById('map-arrow-icon');
    if (!map) return;

    const isOpen = map.style.display !== 'none';
    map.style.display = isOpen ? 'none' : 'block';
    if (arrow) arrow.textContent = isOpen ? '▼' : '▲';
  },

  scrollToQuestion(key) {
    const el = document.getElementById(`qcard-${key}`) || document.getElementById(`qrow-${key}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('pulse-highlight');
      setTimeout(() => el.classList.remove('pulse-highlight'), 1200);
    }
    this.toggleNavMap();
  },

  updateMapItem(key, isFilled) {
    const btn = document.getElementById(`map-btn-${key}`);
    if (btn) btn.classList.toggle('answered', isFilled);
  },

  updateProgress() {
    let answeredQuestions = 0;

    // 1-35 savollar (35 ta)
    for (let q = 1; q <= 35; q++) {
      if (this.answers[String(q)]) answeredQuestions++;
    }

    // 36a-45b savollar (20 ta alohida savol)
    for (let q = 36; q <= 45; q++) {
      for (let sub of ['a', 'b']) {
        const key = `${q}${sub}`;
        const input = document.getElementById(`input-${key}`);
        const val = this.answers[key] !== undefined ? this.answers[key] : (input ? input.value : '');
        if ((val || '').trim().length > 0) {
          answeredQuestions++;
        }
      }
    }

    const total = 55;
    const remaining = total - answeredQuestions;
    const percent = Math.round((answeredQuestions / total) * 100);

    const countEl = document.getElementById('answered-counter');
    const fillEl = document.getElementById('progress-bar-fill');
    const dockText = document.getElementById('dock-answered-text');
    const dockSub = document.getElementById('dock-unanswered-text');

    if (countEl) countEl.textContent = `${answeredQuestions} / ${total}`;
    if (fillEl) fillEl.style.width = `${percent}%`;
    if (dockText) dockText.textContent = `${answeredQuestions} / ${total} ta belgilandi (${percent}%)`;
    if (dockSub) dockSub.textContent = remaining === 0 ? '🎉 Barcha 55 ta savol to\'ldirildi!' : `${remaining} ta savol qoldi`;
  },

  // ----------------------------------------------------
  // TESTNI TOPSHIRISH (SUBMIT) — 2 BOSQICHLI XAVFSIZ TIZIM
  // ----------------------------------------------------
  openConfirmSubmitModal() {
    if (typeof MathKeyboard !== 'undefined' && MathKeyboard.close) {
      MathKeyboard.close();
    }

    // 45 daqiqalik topshirish cheklovini tekshirish
    if (this.minSubmitInfo && !this.minSubmitInfo.can_submit && !this.isAdmin) {
      this.openMinSubmitModal();
      return;
    }

    // 1-bosqichga o'tkazish ("Testni yakunlaysizmi? Ha / Yo'q")
    const step1 = document.getElementById('confirm-step-1');
    const step2 = document.getElementById('confirm-step-2');
    if (step1) step1.style.display = 'block';
    if (step2) step2.style.display = 'none';

    const modal = document.getElementById('confirm-modal');
    if (modal) modal.classList.add('open');
  },

  closeConfirmSubmitModal() {
    const modal = document.getElementById('confirm-modal');
    if (modal) modal.classList.remove('open');
  },

  proceedToSubmitStep2() {
    // 2-bosqichga o'tish: avval ochiq savollar inputlarini sinxronlashtirish va saqlash
    for (let q = 36; q <= 45; q++) {
      for (let sub of ['a', 'b']) {
        const key = `${q}${sub}`;
        const input = document.getElementById(`input-${key}`);
        if (input && input.value !== undefined) {
          this.answers[key] = input.value.trim();
        }
      }
    }
    this.saveAnswersToStorage();

    let answered = 0;
    for (let q = 1; q <= 35; q++) {
      if (this.answers[String(q)]) answered++;
    }
    for (let q = 36; q <= 45; q++) {
      for (let sub of ['a', 'b']) {
        const key = `${q}${sub}`;
        if ((this.answers[key] || '').trim().length > 0) {
          answered++;
        }
      }
    }

    const total = 55;
    const empty = total - answered;

    const mAnswered = document.getElementById('m-stat-answered');
    const mEmpty = document.getElementById('m-stat-empty');
    if (mAnswered) mAnswered.textContent = answered;
    if (mEmpty) mEmpty.textContent = empty;

    const step1 = document.getElementById('confirm-step-1');
    const step2 = document.getElementById('confirm-step-2');
    const zeroWarn = document.getElementById('zero-answers-warning');
    const partialWarn = document.getElementById('partial-answers-warning');
    const finalBtn = document.getElementById('btn-final-submit');
    const iconEl = document.getElementById('confirm-step-2-icon');
    const titleEl = document.getElementById('confirm-step-2-title');
    const descEl = document.getElementById('confirm-step-2-desc');

    if (answered === 0) {
      // 0 ta belgilangan bo'lsa: QAT'IY TO'SIQ!
      if (zeroWarn) zeroWarn.style.display = 'block';
      if (partialWarn) partialWarn.style.display = 'none';
      if (iconEl) iconEl.textContent = '⚠️';
      if (titleEl) titleEl.textContent = 'Javoblar belgilanmagan!';
      if (descEl) descEl.textContent = 'Testda birorta ham savolga javob belgilanmagan.';
      if (finalBtn) {
        finalBtn.disabled = true;
        finalBtn.style.opacity = '0.35';
        finalBtn.style.cursor = 'not-allowed';
        finalBtn.style.pointerEvents = 'none';
        finalBtn.textContent = 'Topshirish bloklangan ⛔️';
      }
    } else {
      // Kamida 1 ta belgilangan bo'lsa: Yakunlash imkoni
      if (zeroWarn) zeroWarn.style.display = 'none';
      if (partialWarn) partialWarn.style.display = empty > 0 ? 'block' : 'none';
      if (iconEl) iconEl.textContent = '📊';
      if (titleEl) titleEl.textContent = 'Javoblaringiz holati';
      if (descEl) descEl.textContent = `Siz 55 ta savoldan ${answered} tasini belgiladingiz, ${empty} tasini belgilanmagan qoldirdingiz.`;
      if (finalBtn) {
        finalBtn.disabled = false;
        finalBtn.style.opacity = '1';
        finalBtn.style.cursor = 'pointer';
        finalBtn.style.pointerEvents = 'auto';
        finalBtn.textContent = 'Oxirgi yakunlash 🚀';
      }
    }

    if (step1) step1.style.display = 'none';
    if (step2) step2.style.display = 'block';
  },

  backToSubmitStep1() {
    const step1 = document.getElementById('confirm-step-1');
    const step2 = document.getElementById('confirm-step-2');
    if (step1) step1.style.display = 'block';
    if (step2) step2.style.display = 'none';
  },

  openMinSubmitModal() {
    const modal = document.getElementById('min-submit-modal');
    if (!modal) return;
    this.updateMinSubmitModalUI();
    modal.classList.add('open');
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      try { window.Telegram.WebApp.HapticFeedback.notificationOccurred('warning'); } catch(e) {}
    }
  },

  closeMinSubmitModal() {
    const modal = document.getElementById('min-submit-modal');
    if (modal) modal.classList.remove('open');
  },

  startMinSubmitTimer() {
    if (this.minSubmitTimerInterval) {
      clearInterval(this.minSubmitTimerInterval);
      this.minSubmitTimerInterval = null;
    }
    if (!this.minSubmitInfo || this.minSubmitInfo.can_submit) return;

    this.minSubmitTimerInterval = setInterval(() => {
      if (!this.minSubmitInfo) return;
      if (this.minSubmitInfo.remaining_seconds > 0) {
        this.minSubmitInfo.remaining_seconds--;
        this.updateMinSubmitModalUI();
      } else {
        this.minSubmitInfo.can_submit = true;
        this.minSubmitInfo.remaining_seconds = 0;
        clearInterval(this.minSubmitTimerInterval);
        this.minSubmitTimerInterval = null;
        this.updateMinSubmitModalUI();
      }
    }, 1000);
  },

  updateMinSubmitModalUI() {
    const countEl = document.getElementById('min-submit-countdown');
    const unlockEl = document.getElementById('min-submit-unlock-info');
    const titleEl = document.getElementById('min-submit-title');
    const descEl = document.getElementById('min-submit-desc');
    const iconWrap = document.getElementById('min-submit-icon-wrap');
    const actionBtn = document.getElementById('min-submit-action-btn');

    if (!this.minSubmitInfo) return;

    const rem = Math.max(0, this.minSubmitInfo.remaining_seconds || 0);
    const mins = Math.floor(rem / 60);
    const secs = rem % 60;
    const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

    if (rem > 0 && !this.minSubmitInfo.can_submit) {
      if (countEl) {
        countEl.textContent = timeStr;
        countEl.style.color = 'var(--primary, #2563EB)';
      }
      if (unlockEl && this.minSubmitInfo.unlock_time_str) {
        unlockEl.innerHTML = `Topshirish ochiladigan vaqt: <b style="color:var(--text-main);">${this.minSubmitInfo.unlock_time_str}</b>`;
      }
      if (titleEl) titleEl.textContent = 'Hali javob yubora olmaysiz!';
      if (descEl) descEl.innerHTML = 'Test boshlanganidan so\'ng dastlabki <b>45 daqiqa</b> davomida javoblarni topshirish cheklangan.';
      if (iconWrap) {
        iconWrap.textContent = '⏳';
        iconWrap.style.borderColor = '#F59E0B';
        iconWrap.style.background = 'linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(239, 68, 68, 0.15))';
      }
      if (actionBtn) {
        actionBtn.textContent = 'Savollarni qayta tekshirish 🔍';
        actionBtn.className = 'btn-modal-cancel';
        actionBtn.onclick = () => this.closeMinSubmitModal();
      }
    } else {
      if (countEl) {
        countEl.textContent = '00:00';
        countEl.style.color = '#10B981';
      }
      if (unlockEl) {
        unlockEl.innerHTML = '✅ <b style="color:#10B981;">45 daqiqalik cheklov yakunlandi!</b>';
      }
      if (titleEl) titleEl.textContent = 'Topshirish vaqti yetib keldi!';
      if (descEl) descEl.textContent = 'Endi javoblaringizni bemalol topshirishingiz mumkin.';
      if (iconWrap) {
        iconWrap.textContent = '✅';
        iconWrap.style.borderColor = '#10B981';
        iconWrap.style.background = 'rgba(16, 185, 129, 0.15)';
      }
      if (actionBtn) {
        actionBtn.textContent = 'Testni yakunlashga o\'tish 🚀';
        actionBtn.className = 'btn-modal-confirm';
        actionBtn.onclick = () => {
          this.closeMinSubmitModal();
          this.openConfirmSubmitModal();
        };
      }
    }
  },

  async submitTestNow() {
    if (!this.userTgId || this.userTgId <= 0) {
      this.closeConfirmSubmitModal();
      alert("⚠️ Web orqali ishlash mumkin emas! Testni faqat rasmiy Telegram botimiz (@fizika_rash_testbot) va Mini ilova orqali topshirish mumkin.");
      const webBlock = document.getElementById('web-block-screen');
      if (webBlock) webBlock.style.display = 'flex';
      return;
    }

    // 45 daqiqa tekshiruvi
    if (this.minSubmitInfo && !this.minSubmitInfo.can_submit && !this.isAdmin) {
      this.closeConfirmSubmitModal();
      this.openMinSubmitModal();
      return;
    }

    // 36a-45b savollar qiymatlarini to'g'ridan-to'g'ri DOM dan olib yakuniy tekshirish
    for (let q = 36; q <= 45; q++) {
      for (let sub of ['a', 'b']) {
        const key = `${q}${sub}`;
        const input = document.getElementById(`input-${key}`);
        if (input && input.value !== undefined) {
          this.answers[key] = input.value.trim();
        }
      }
    }

    // Xavfsizlik: 0 ta belgilangan bo'lsa topshirishga mutlaqo ruxsat bermaslik
    let answered = 0;
    for (let q = 1; q <= 35; q++) {
      if (this.answers[String(q)]) answered++;
    }
    for (let q = 36; q <= 45; q++) {
      for (let sub of ['a', 'b']) {
        const key = `${q}${sub}`;
        if ((this.answers[key] || '').trim().length > 0) answered++;
      }
    }

    if (answered === 0 && !this.isAdmin) {
      alert("⚠️ Siz birorta ham savolga javob belgilamadingiz (0/55)!\n\nBo'sh testni topshirib bo'lmaydi. Iltimos, savollarni ishlab, javoblarni belgilang!");
      this.closeConfirmSubmitModal();
      return;
    }

    if (this._isSubmitting) return;
    this._isSubmitting = true;

    const submitBtn = document.getElementById('btn-final-submit');
    const backBtn = document.getElementById('btn-confirm-back');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Amalga oshirilmoqda... ⏳';
    }
    if (backBtn) {
      backBtn.disabled = true;
    }

    const payload = {
      test_id: this.testId,
      test_code: this.testCode,
      user_tg_id: this.userTgId,
      fullname: this.userFullname,
      answers: this.answers
    };

    try {
      const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || '';
      const response = await fetch('/api/submit-test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData
        },
        body: JSON.stringify(Object.assign({}, payload, { init_data: initData }))
      });

      const result = await response.json();

      if (response.status === 429) {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Oxirgi yakunlash 🚀';
        }
        if (backBtn) backBtn.disabled = false;
        alert(result.message || "Iltimos, biroz kuting! So'rovingiz navbatda qayta ishlanmoqda...");
        return;
      }

      this.closeConfirmSubmitModal();

      if (result.success && result.data) {
        this.clearAnswersFromStorage();
        this.showResultModal(result.data);
      } else {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Oxirgi yakunlash 🚀';
        }
        if (backBtn) backBtn.disabled = false;

        if (result.error_code === 'EARLY_SUBMISSION_BLOCKED') {
          if (!this.minSubmitInfo) this.minSubmitInfo = {};
          this.minSubmitInfo.can_submit = false;
          if (result.remaining_seconds !== undefined) {
            this.minSubmitInfo.remaining_seconds = result.remaining_seconds;
          }
          if (result.unlock_time) {
            this.minSubmitInfo.unlock_time_str = result.unlock_time;
          }
          this.startMinSubmitTimer();
          this.openMinSubmitModal();
          return;
        }
        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.showAlert) {
          window.Telegram.WebApp.showAlert(result.message || 'Javoblarni yuborishda xatolik!');
        } else {
          alert(result.message || 'Javoblarni yuborishda xatolik yuz berdi!');
        }
      }
    } catch (e) {
      console.error('Submit error:', e);
      this.closeConfirmSubmitModal();
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Oxirgi yakunlash 🚀';
      }
      if (backBtn) backBtn.disabled = false;
      alert('Tarmoq xatoligi yoki serverga ulanishda muammo yuz berdi. Iltimos, qayta urinib ko\'ring.');
    } finally {
      setTimeout(() => {
        this._isSubmitting = false;
        if (backBtn) backBtn.disabled = false;
      }, 1500);
    }
  },

  showResultModal(data) {
    this.clearAnswersFromStorage();
    const mainSubmitBtn = document.getElementById('btn-submit-test');
    if (mainSubmitBtn) {
      mainSubmitBtn.disabled = true;
      mainSubmitBtn.textContent = 'Topshirilgan ✅';
      mainSubmitBtn.style.background = '#10b981';
      mainSubmitBtn.style.cursor = 'not-allowed';
    }

    const modal = document.getElementById('result-modal');
    if (!modal) return;

    const nameEl = document.getElementById('result-user-name');
    const titleEl = modal.querySelector('.result-title');
    const gradeContainer = document.getElementById('result-grade-container');
    const detailsGrid = modal.querySelector('.result-details-grid');
    const noteEl = modal.querySelector('.result-actions div');
    const analysisBtn = document.getElementById('btn-open-analysis');

    if (nameEl) nameEl.textContent = data.fullname || this.userFullname;

    const isPublished = Boolean(data.is_published);

    if (data.is_late) {
      if (titleEl) titleEl.textContent = "Test kech topshirildi! ⚠️";
      if (gradeContainer) {
        gradeContainer.style.borderColor = "rgba(239, 68, 68, 0.4)";
        gradeContainer.style.background = "rgba(239, 68, 68, 0.12)";
        gradeContainer.innerHTML = `
          <span style="font-size: 26px;">⏰</span>
          <div style="text-align: left;">
            <div style="font-size: 11px; text-transform: uppercase; font-weight: 800; color: #EF4444; letter-spacing: 0.5px;">Holat</div>
            <div style="font-size: 15px; font-weight: 800; color: #DC2626;">Kech topshirildi (Hisobga olinmaydi)</div>
          </div>
        `;
      }
      if (detailsGrid) detailsGrid.style.display = 'none';
      if (analysisBtn) analysisBtn.style.display = 'none';
      if (noteEl) {
        noteEl.innerHTML = `⚠️ <b>Siz testni belgilangan vaqtdan kech topshirdingiz!</b> Natijangiz umumiy hisobga olinmaydi. Javoblaringiz ko'rib chiqish uchun adminga yuborildi. Agar admin ruxsat bersa, natijangiz umumiy reytingga qo'shiladi.`;
      }
    } else if (!isPublished) {
      if (titleEl) titleEl.textContent = "Javoblaringiz qabul qilindi! ⏳";
      if (gradeContainer) {
        gradeContainer.style.borderColor = "rgba(245, 158, 11, 0.4)";
        gradeContainer.style.background = "rgba(245, 158, 11, 0.12)";
        gradeContainer.innerHTML = `
          <span style="font-size: 26px;">⏳</span>
          <div style="text-align: left;">
            <div style="font-size: 11px; text-transform: uppercase; font-weight: 800; color: #D97706; letter-spacing: 0.5px;">Holat</div>
            <div style="font-size: 16px; font-weight: 800; color: #B45309;">Jarayonda (Kutilmoqda)...</div>
          </div>
        `;
      }
      if (detailsGrid) detailsGrid.style.display = 'none';
      if (analysisBtn) analysisBtn.style.display = 'none';
      if (noteEl) {
        noteEl.innerHTML = `⏳ <b>Eslatma:</b> Javoblaringiz muvaffaqiyatli saqlandi. Test hozirda davom etmoqda. Admin testni to'xtatib, <b>Rasch modeli (JMLE)</b> asosida tahlil o'tkazgach, to'g'ri ishlangan savollar soni, ball va Milliy sertifikat darajangiz botingizga shaxsiy xabar qilib yuboriladi!`;
      }
    } else {
      if (titleEl) titleEl.textContent = "Test Yakunlandi! 🎉";
      if (detailsGrid) detailsGrid.style.display = 'grid';
      if (analysisBtn) analysisBtn.style.display = 'block';

      const correctEl = document.getElementById('r-correct-count');
      const incorrectEl = document.getElementById('r-incorrect-count');
      const emptyEl = document.getElementById('r-unanswered-count');
      if (correctEl) correctEl.textContent = `${data.correct_count ?? 0} ta`;
      if (incorrectEl) incorrectEl.textContent = `${data.incorrect_count ?? 0} ta`;
      if (emptyEl) emptyEl.textContent = `${data.unanswered_count ?? 0} ta`;

      const gradeVal = document.getElementById('result-grade-val');
      if (gradeVal) {
        const grade = data.grade || '—';
        const score = (data.score !== undefined && data.score !== null) ? `${data.score} ball` : '';
        gradeVal.textContent = `${grade} ${score ? `(${score})` : ''}`;
      }
    }

    this.lastResultData = data;
    modal.classList.add('open');

    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
    }
  },

  openAnswersAnalysis() {
    const data = this.lastResultData;
    if (!data || !data.details || !data.is_published) {
      alert("Natijalar va to'liq tahlil test admin tomonidan to'xtatilib, rasmiy e'lon qilingach ochiladi.");
      return;
    }

    const container = document.getElementById('analysis-items-container');
    if (!container) return;

    let html = '';
    const details = data.details;

    Object.keys(details).forEach(key => {
      const item = details[key];
      const isCorrect = item.status === 'correct';
      const isUnanswered = item.status === 'unanswered';
      
      let statusBg = isCorrect ? 'rgba(16, 185, 129, 0.12)' : (isUnanswered ? 'rgba(100, 116, 139, 0.12)' : 'rgba(239, 68, 68, 0.12)');
      let statusBorder = isCorrect ? '#10B981' : (isUnanswered ? '#94A3B8' : '#EF4444');
      let statusIcon = isCorrect ? '✅' : (isUnanswered ? '⚪️' : '❌');
      let statusLabel = isCorrect ? 'To\'g\'ri' : (isUnanswered ? 'Belgilanmagan' : 'Noto\'g\'ri');

      let userAnsDisplay = (item.user || '').trim() || '<span style="color: #94A3B8; font-style: italic;">(Belgilanmadi)</span>';
      let correctAnsDisplay = item.correct || '—';
      let scoreBadge = '';
      if (item.score !== undefined && item.max_score !== undefined) {
        scoreBadge = isCorrect
          ? `<span style="font-size: 11.5px; color: #10B981; font-weight: 700; margin-left: 6px;">(+${item.score} ball)</span>`
          : `<span style="font-size: 11px; color: #94A3B8; margin-left: 6px;">(${item.max_score} ball)</span>`;
      }

      html += `
        <div style="background: ${statusBg}; border: 1px solid ${statusBorder}; border-radius: 10px; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: 800; font-size: 13.5px; color: var(--text-main);">${item.num || key + '-savol'} ${scoreBadge}</span>
            <span style="font-size: 12px; font-weight: 800; display: inline-flex; align-items: center; gap: 4px;">${statusIcon} ${statusLabel}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 13px; margin-top: 2px;">
            <span>Sizning javobingiz: <strong>${userAnsDisplay}</strong></span>
            <span style="color: #10B981;">To'g'ri kalit: <strong>${correctAnsDisplay}</strong></span>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
    const modal = document.getElementById('analysis-modal');
    if (modal) modal.classList.add('open');
  },

  closeAnswersAnalysis() {
    const modal = document.getElementById('analysis-modal');
    if (modal) modal.classList.remove('open');
  },

  closeWebApp() {
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.close();
    } else {
      window.location.reload();
    }
  }
};

window.TestApp = TestApp;
window.dismissSplash = () => TestApp.finishSplashImmediately();
window.finishSplashImmediately = () => TestApp.finishSplashImmediately();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    TestApp.init();
  });
} else {
  TestApp.init();
}
