/**
 * ============================================================================
 * PHYSICS KEYBOARD MODULE (Fizika Klaviaturasi)
 * ============================================================================
 * Maxsus Fizika ochiq savollari (36a — 45b) uchun ishlab chiqilgan virtual klaviatura.
 * 
 * 4 ta mustaqil tab:
 *  1. "123 / ±"     : Raqamlar, amallar, ildiz, qavslar, ·10ⁿ
 *  2. "Birliklar (SI)": m, s, kg, N, J, W, Pa, V, A, Ω, Hz, T, C, m/s, m/s²
 *  3. "α β γ"       : Fizika yunon harflari (λ, μ, ρ, ω, φ, Δ, α, β, γ, θ, π, ε, ν, σ, τ, Φ)
 *  4. "xₙ / g, c"   : Pastki indekslar (x₀, x₁, x₂), doimiylar (g, c, e, k, h) va trigonometriya
 * 
 * Telefonning tabiiy klaviaturasini to'liq bloklaydi va mobil ekranda 100% optimal ishlaydi.
 */

(function(window) {
  'use strict';

  const PhysicsKeyboard = {
    activeFieldKey: null,
    activeInputElement: null,
    activeFieldOrder: [],
    currentTab: 'num', // 'num', 'units', 'greek', 'const'

    init() {
      // 36a dan 45b gacha bo'lgan maydonlar tartibi
      this.activeFieldOrder = [];
      for (let q = 36; q <= 45; q++) {
        this.activeFieldOrder.push(`${q}a`);
        this.activeFieldOrder.push(`${q}b`);
      }

      // DOM panelini tekshirish va yaratish
      this.ensureMounted();

      // Mobil qurilmaning virtual klaviaturasini bloklash
      const blockNative = (e) => {
        const target = e.target;
        if (target && (target.classList.contains('savol-input') || target.classList.contains('kb-live-input') || target.id === 'keyboard-live-input')) {
          this.preventNativeKeyboard(target);
        }
      };

      document.querySelectorAll('.savol-input, .kb-live-input').forEach(el => this.preventNativeKeyboard(el));
      document.addEventListener('focusin', blockNative, true);
      document.addEventListener('touchstart', blockNative, { passive: true });
      document.addEventListener('pointerdown', blockNative, { passive: true });

      const liveInput = document.getElementById('keyboard-live-input');
      if (liveInput) {
        this.preventNativeKeyboard(liveInput);
        const sync = () => this.syncCursorFrom(liveInput);
        liveInput.addEventListener('click', sync);
        liveInput.addEventListener('pointerup', sync);
        liveInput.addEventListener('keyup', sync);
      }
    },

    preventNativeKeyboard(el) {
      if (!el) return;
      el.setAttribute('readonly', 'readonly');
      el.setAttribute('inputmode', 'none');
      el.setAttribute('autocomplete', 'off');
      el.setAttribute('autocorrect', 'off');
      el.setAttribute('autocapitalize', 'off');
      el.setAttribute('spellcheck', 'false');
    },

    ensureMounted() {
      let panel = document.getElementById('physics-keyboard-panel');
      let oldPanel = document.getElementById('math-keyboard-panel');

      if (!panel && oldPanel) {
        panel = oldPanel;
        panel.id = 'physics-keyboard-panel';
        panel.classList.add('physics-keyboard-panel');
      }

      if (!panel) {
        panel = document.createElement('div');
        panel.id = 'physics-keyboard-panel';
        panel.className = 'physics-keyboard-panel math-keyboard-panel';
        document.body.appendChild(panel);
      }

      panel.innerHTML = this.getTemplateHTML();
      this.switchTab(this.currentTab);
    },

    getTemplateHTML() {
      return `
        <!-- 1. YUQORI BOSHQARUV PANELI (Top Bar) -->
        <div class="kb-top-bar">
          <div class="kb-target-wrap">
            <span class="kb-target-badge" id="keyboard-target-name">36a</span>
            <input type="text" class="kb-live-input" id="keyboard-live-input" readonly inputmode="none" placeholder="Javobni kiriting...">
          </div>
          <button type="button" class="kb-done-btn" onclick="PhysicsKeyboard.close()" title="Klaviaturani yopish">
            Tayyor ✓
          </button>
        </div>

        <!-- 2. 4 TA MUSTAQIL TABLAR (Segmented Tabs) -->
        <div class="kb-tabs-bar">
          <button type="button" class="kb-tab-btn" id="pk-tab-num" onclick="PhysicsKeyboard.switchTab('num')">
            123 / ±
          </button>
          <button type="button" class="kb-tab-btn" id="pk-tab-units" onclick="PhysicsKeyboard.switchTab('units')">
            Birliklar (SI)
          </button>
          <button type="button" class="kb-tab-btn" id="pk-tab-greek" onclick="PhysicsKeyboard.switchTab('greek')">
            α β γ
          </button>
          <button type="button" class="kb-tab-btn" id="pk-tab-const" onclick="PhysicsKeyboard.switchTab('const')">
            xₙ / g, c
          </button>
        </div>

        <!-- 3. TUGMALAR TANASI (Tab Panellari) -->

        <!-- TAB 1: Raqamlar, amallar, ildiz, qavslar, ·10ⁿ -->
        <div class="kb-body" id="pk-body-num">
          <div class="kb-row">
            <button type="button" class="kb-key kb-func kb-sci" onclick="PhysicsKeyboard.insertScientific()" title="Ko'paytirilgan o'n darajasi">·10ⁿ</button>
            <button type="button" class="kb-key kb-func" onclick="PhysicsKeyboard.insert('√')">√</button>
            <button type="button" class="kb-key kb-func" onclick="PhysicsKeyboard.insert('(')">(</button>
            <button type="button" class="kb-key kb-func" onclick="PhysicsKeyboard.insert(')')">)</button>
            <button type="button" class="kb-key kb-action" onclick="PhysicsKeyboard.clear()">C</button>
            <button type="button" class="kb-key kb-backspace" onclick="PhysicsKeyboard.backspace()">⌫</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('7')">7</button>
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('8')">8</button>
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('9')">9</button>
            <button type="button" class="kb-key kb-op" onclick="PhysicsKeyboard.insert('/')">/</button>
            <button type="button" class="kb-key kb-op" onclick="PhysicsKeyboard.insert('±')">±</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('4')">4</button>
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('5')">5</button>
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('6')">6</button>
            <button type="button" class="kb-key kb-op" onclick="PhysicsKeyboard.insert('·')">·</button>
            <button type="button" class="kb-key kb-op" onclick="PhysicsKeyboard.insert('-')">−</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('1')">1</button>
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('2')">2</button>
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('3')">3</button>
            <button type="button" class="kb-key kb-op" onclick="PhysicsKeyboard.insert('+')">+</button>
            <button type="button" class="kb-key kb-op" onclick="PhysicsKeyboard.insert('=')">=</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('0')">0</button>
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert(',')">,</button>
            <button type="button" class="kb-key kb-num" onclick="PhysicsKeyboard.insert('.')">.</button>
            <button type="button" class="kb-key kb-space" onclick="PhysicsKeyboard.insert(' ')" style="flex: 1.6;">probel ␣</button>
            <button type="button" class="kb-key kb-nav" onclick="PhysicsKeyboard.prevField()">◀ Oldingi</button>
            <button type="button" class="kb-key kb-nav kb-nav-next" onclick="PhysicsKeyboard.nextField()">Keyingi ▶</button>
          </div>
        </div>

        <!-- TAB 2: Birliklar (SI): m, s, kg, N, J, W, Pa, V, A, Ω, Hz, T, C, m/s, m/s² -->
        <div class="kb-body" id="pk-body-units" style="display: none;">
          <div class="kb-row">
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('m')">m</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('s')">s</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('kg')">kg</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('N')">N</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('J')">J</button>
            <button type="button" class="kb-key kb-backspace" onclick="PhysicsKeyboard.backspace()">⌫</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('W')">W</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('Pa')">Pa</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('V')">V</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('A')">A</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('Ω')">Ω</button>
            <button type="button" class="kb-key kb-action" onclick="PhysicsKeyboard.clear()">C</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('Hz')">Hz</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('T')">T</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('C')">C</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('m/s')">m/s</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('m/s²')" style="font-weight: 800;">m/s²</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('kJ')">kJ</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('nC')">nC</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('μC')">μC</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('kW')">kW</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('cm')">cm</button>
            <button type="button" class="kb-key kb-unit" onclick="PhysicsKeyboard.insertUnit('mm')">mm</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-space" onclick="PhysicsKeyboard.insert(' ')" style="flex: 2;">probel ␣</button>
            <button type="button" class="kb-key kb-nav" onclick="PhysicsKeyboard.prevField()">◀ Oldingi</button>
            <button type="button" class="kb-key kb-nav kb-nav-next" onclick="PhysicsKeyboard.nextField()">Keyingi ▶</button>
          </div>
        </div>

        <!-- TAB 3: Fizika yunon harflari (λ, μ, ρ, ω, φ, Δ, α, β, γ, θ, π, ε, ν, σ, τ, Φ) -->
        <div class="kb-body" id="pk-body-greek" style="display: none;">
          <div class="kb-row">
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('λ')">λ</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('μ')">μ</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('ρ')">ρ</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('ω')">ω</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('φ')">φ</button>
            <button type="button" class="kb-key kb-backspace" onclick="PhysicsKeyboard.backspace()">⌫</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('Δ')">Δ</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('α')">α</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('β')">β</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('γ')">γ</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('θ')">θ</button>
            <button type="button" class="kb-key kb-action" onclick="PhysicsKeyboard.clear()">C</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('π')">π</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('ε')">ε</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('ν')">ν</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('σ')">σ</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('τ')">τ</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('Φ')">Φ</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('η')">η</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('ψ')">ψ</button>
            <button type="button" class="kb-key kb-greek" onclick="PhysicsKeyboard.insert('Ω')">Ω</button>
            <button type="button" class="kb-key kb-func" onclick="PhysicsKeyboard.insert('≈')">≈</button>
            <button type="button" class="kb-key kb-func" onclick="PhysicsKeyboard.insert('°')">°</button>
            <button type="button" class="kb-key kb-func" onclick="PhysicsKeyboard.insert('∞')">∞</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-space" onclick="PhysicsKeyboard.insert(' ')" style="flex: 2;">probel ␣</button>
            <button type="button" class="kb-key kb-nav" onclick="PhysicsKeyboard.prevField()">◀ Oldingi</button>
            <button type="button" class="kb-key kb-nav kb-nav-next" onclick="PhysicsKeyboard.nextField()">Keyingi ▶</button>
          </div>
        </div>

        <!-- TAB 4: Pastki indekslar (x₀, x₁, x₂), doimiylar (g, c, e, k, h) va trigonometriya -->
        <div class="kb-body" id="pk-body-const" style="display: none;">
          <div class="kb-row">
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('g')">g</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('c')">c</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('e')">e</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('k')">k</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('h')">h</button>
            <button type="button" class="kb-key kb-backspace" onclick="PhysicsKeyboard.backspace()">⌫</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('x₀')">x₀</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('x₁')">x₁</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('x₂')">x₂</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('v₀')">v₀</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('t₀')">t₀</button>
            <button type="button" class="kb-key kb-action" onclick="PhysicsKeyboard.clear()">C</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('₀')">₀</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('₁')">₁</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('₂')">₂</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('₃')">₃</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('²')">²</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('³')">³</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('sin(')">sin</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('cos(')">cos</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('tg(')">tg</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('ctg(')">ctg</button>
            <button type="button" class="kb-key kb-const" onclick="PhysicsKeyboard.insert('^')">^</button>
          </div>
          <div class="kb-row">
            <button type="button" class="kb-key kb-space" onclick="PhysicsKeyboard.insert(' ')" style="flex: 2;">probel ␣</button>
            <button type="button" class="kb-key kb-nav" onclick="PhysicsKeyboard.prevField()">◀ Oldingi</button>
            <button type="button" class="kb-key kb-nav kb-nav-next" onclick="PhysicsKeyboard.nextField()">Keyingi ▶</button>
          </div>
        </div>
      `;
    },

    getPanel() {
      return document.getElementById('physics-keyboard-panel') || document.getElementById('math-keyboard-panel');
    },

    openFor(fieldKey) {
      this.activeFieldKey = fieldKey;
      this.ensureMounted();

      // Body klassi: header va pastki dock avtomatik yashiriladi
      document.body.classList.add('keyboard-open');

      const panel = this.getPanel();
      if (panel) {
        panel.classList.add('open');
      }

      const targetName = document.getElementById('keyboard-target-name');
      if (targetName) targetName.textContent = String(fieldKey).toUpperCase();

      const inputEl = document.getElementById(`input-${fieldKey}`) || document.getElementById(`adm-input-${fieldKey}`);
      this.activeInputElement = inputEl;

      const liveInput = document.getElementById('keyboard-live-input');
      if (liveInput) {
        this.preventNativeKeyboard(liveInput);
        liveInput.value = inputEl ? (inputEl.value || '') : '';
      }
      if (inputEl) {
        this.preventNativeKeyboard(inputEl);
      }

      // Savol kartochkasini focused holatiga keltirish va markazga scroll qilish
      document.querySelectorAll('.savol-input-box').forEach(b => b.classList.remove('focused'));
      const boxEl = document.getElementById(`box-${fieldKey}`);
      if (boxEl) {
        boxEl.classList.add('focused');
        setTimeout(() => {
          boxEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 80);
      }

      const curLen = (inputEl && inputEl.value ? inputEl.value.length : 0);
      this.setCursor(curLen);

      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
      }
    },

    close() {
      // Body klassini olib tashlash (header va dock qaytadi)
      document.body.classList.remove('keyboard-open');

      const panel = this.getPanel();
      if (panel) {
        panel.classList.remove('open');
      }

      document.querySelectorAll('.savol-input-box').forEach(b => b.classList.remove('focused'));
      this.activeFieldKey = null;
      this.activeInputElement = null;
    },

    switchTab(tabId) {
      this.currentTab = tabId;
      const tabs = ['num', 'units', 'greek', 'const'];
      tabs.forEach(t => {
        const btn = document.getElementById(`pk-tab-${t}`);
        const body = document.getElementById(`pk-body-${t}`);
        if (btn) btn.classList.toggle('active', t === tabId);
        if (body) body.style.display = (t === tabId) ? 'flex' : 'none';
      });

      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      }
    },

    insert(val) {
      if (!this.activeFieldKey) return;
      const targetInput = this.activeInputElement || document.getElementById('keyboard-live-input');
      if (!targetInput) return;

      const text = targetInput.value || '';
      const start = targetInput.selectionStart ?? text.length;
      const end = targetInput.selectionEnd ?? text.length;

      const newVal = text.substring(0, start) + val + text.substring(end);
      const newPos = start + val.length;
      this.applyValue(newVal, newPos);
    },

    // Birliklarni kiritishda (masalan: "400 J", "4 m/s²") aqlli probel bilan kiritish
    insertUnit(unit) {
      if (!this.activeFieldKey) return;
      const targetInput = this.activeInputElement || document.getElementById('keyboard-live-input');
      if (!targetInput) return;

      const text = targetInput.value || '';
      const start = targetInput.selectionStart ?? text.length;
      const end = targetInput.selectionEnd ?? text.length;

      let insertStr = unit;
      if (start > 0) {
        const prevChar = text[start - 1];
        // Agar oldingi belgi raqam, daraja yoki qavs bo'lsa, probel bilan ajratamiz
        if (/[0-9\)²³⁴ⁿa-zA-Z]/.test(prevChar) && prevChar !== ' ') {
          insertStr = ' ' + unit;
        }
      }

      const newVal = text.substring(0, start) + insertStr + text.substring(end);
      const newPos = start + insertStr.length;
      this.applyValue(newVal, newPos);
    },

    // Ilmiy kiritish (·10ⁿ yoki ·10^)
    insertScientific() {
      if (!this.activeFieldKey) return;
      const targetInput = this.activeInputElement || document.getElementById('keyboard-live-input');
      if (!targetInput) return;

      const text = targetInput.value || '';
      const start = targetInput.selectionStart ?? text.length;
      const end = targetInput.selectionEnd ?? text.length;

      let insertStr = '·10^';
      if (start > 0 && text[start - 1] === ' ') {
        insertStr = '·10^';
      }

      const newVal = text.substring(0, start) + insertStr + text.substring(end);
      const newPos = start + insertStr.length;
      this.applyValue(newVal, newPos);
    },

    insertWithSpace(str) {
      this.insertUnit(str);
    },

    backspace() {
      if (!this.activeFieldKey) return;
      const targetInput = this.activeInputElement || document.getElementById('keyboard-live-input');
      if (!targetInput) return;

      const text = targetInput.value || '';
      const start = targetInput.selectionStart ?? text.length;
      const end = targetInput.selectionEnd ?? text.length;

      let newVal = text;
      let newPos = start;

      if (start === end && start > 0) {
        // Agar kursor oldida ·10^ bo'lsa
        if (start >= 4 && text.substring(start - 4, start) === '·10^') {
          newVal = text.substring(0, start - 4) + text.substring(end);
          newPos = start - 4;
        } else if (start >= 4 && text.substring(start - 4, start) === 'm/s²') {
          newVal = text.substring(0, start - 4) + text.substring(end);
          newPos = start - 4;
        } else if (start >= 3 && text.substring(start - 3, start) === 'm/s') {
          newVal = text.substring(0, start - 3) + text.substring(end);
          newPos = start - 3;
        } else {
          newVal = text.substring(0, start - 1) + text.substring(end);
          newPos = start - 1;
        }
      } else if (start !== end) {
        newVal = text.substring(0, start) + text.substring(end);
        newPos = start;
      }

      this.applyValue(newVal, newPos);
    },

    clear() {
      if (!this.activeFieldKey) return;
      this.applyValue('', 0);
    },

    applyValue(newVal, cursorPos) {
      const liveInput = document.getElementById('keyboard-live-input');
      if (this.activeInputElement) this.activeInputElement.value = newVal;
      if (liveInput) liveInput.value = newVal;

      if (cursorPos !== undefined) {
        this.setCursor(cursorPos);
      }
      this.onInputChange();
    },

    setCursor(pos) {
      this.setSelection(pos, pos);
    },

    setSelection(start, end) {
      const liveInput = document.getElementById('keyboard-live-input');
      if (liveInput && liveInput.setSelectionRange) {
        try { liveInput.setSelectionRange(start, end); } catch (e) {}
      }
      if (this.activeInputElement && this.activeInputElement.setSelectionRange) {
        try { this.activeInputElement.setSelectionRange(start, end); } catch (e) {}
      }
    },

    syncCursorFrom(sourceInput) {
      if (!sourceInput) return;
      const start = sourceInput.selectionStart ?? sourceInput.value.length;
      const end = sourceInput.selectionEnd ?? sourceInput.value.length;
      const targetInput = this.activeInputElement;
      if (targetInput && targetInput !== sourceInput && targetInput.setSelectionRange) {
        try { targetInput.setSelectionRange(start, end); } catch (e) {}
      }
    },

    onInputChange() {
      if (!this.activeFieldKey) return;
      const liveInput = document.getElementById('keyboard-live-input');
      const val = (this.activeInputElement ? this.activeInputElement.value : '') || (liveInput ? liveInput.value : '');

      // TestApp bilan integratsiya
      if (typeof TestApp !== 'undefined' && TestApp.setOpenAnswer) {
        TestApp.setOpenAnswer(this.activeFieldKey, val);
      } else if (window.TestApp && window.TestApp.setOpenAnswer) {
        window.TestApp.setOpenAnswer(this.activeFieldKey, val);
      }

      // AdminApp bilan integratsiya
      if (typeof AdminApp !== 'undefined' && AdminApp.updateOpenAns) {
        AdminApp.updateOpenAns(this.activeFieldKey, val);
      } else if (window.AdminApp && window.AdminApp.updateOpenAns) {
        window.AdminApp.updateOpenAns(this.activeFieldKey, val);
      }

      // Input qutisi to'ldirilgan indikatori
      const boxEl = document.getElementById(`box-${this.activeFieldKey}`);
      if (boxEl) {
        boxEl.classList.toggle('filled', (val || '').trim().length > 0);
      }

      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      }
    },

    prevField() {
      if (!this.activeFieldKey) return;
      const idx = this.activeFieldOrder.indexOf(this.activeFieldKey);
      if (idx > 0) {
        this.openFor(this.activeFieldOrder[idx - 1]);
      }
    },

    nextField() {
      if (!this.activeFieldKey) return;
      const idx = this.activeFieldOrder.indexOf(this.activeFieldKey);
      if (idx < this.activeFieldOrder.length - 1) {
        this.openFor(this.activeFieldOrder[idx + 1]);
      }
    }
  };

  // Global ob'ektlar (Ikkala nom bilan ham to'liq moslik uchun)
  window.PhysicsKeyboard = PhysicsKeyboard;
  window.MathKeyboard = PhysicsKeyboard;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => PhysicsKeyboard.init());
  } else {
    PhysicsKeyboard.init();
  }
})(window);
