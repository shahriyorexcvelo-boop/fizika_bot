/**
 * Interaktiv Matematik Klaviatura (Virtual Math Keyboard)
 * Har qanday son, amal, belgi, ildiz, formula va erkin matnlarni kiritish imkoniyati
 * Telefonning tabiiy klaviaturasini to'liq bloklaydi va n-darajali ildizni qulay boshqaradi.
 */

const SUPERSCRIPTS = {
  '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
  '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
  'n': 'ⁿ', 'm': 'ᵐ', 'k': 'ᵏ', 'x': 'ˣ', 'y': 'ʸ',
  '⁰': '⁰', '¹': '¹', '²': '²', '³': '³', '⁴': '⁴',
  '⁵': '⁵', '⁶': '⁶', '⁷': '⁷', '⁸': '⁸', '⁹': '⁹',
  'ⁿ': 'ⁿ'
};

const MathKeyboard = {
  activeFieldKey: null,
  activeInputElement: null,
  activeFieldOrder: [],
  waitingRootDegree: false,

  init() {
    // 36a dan 45b gacha bo'lgan maydonlar ketma-ketligini tuzish
    this.activeFieldOrder = [];
    for (let q = 36; q <= 45; q++) {
      this.activeFieldOrder.push(`${q}a`);
      this.activeFieldOrder.push(`${q}b`);
    }

    // Telefon klaviaturasini mutlaqo ochilmasligini ta'minlash
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

  openFor(fieldKey) {
    this.activeFieldKey = fieldKey;
    this.waitingRootDegree = false;
    const inputEl = document.getElementById(`input-${fieldKey}`) || document.getElementById(`adm-input-${fieldKey}`);
    this.activeInputElement = inputEl;

    // Tepadagi bo'limlarni yashirish va joy ochish uchun
    document.body.classList.add('keyboard-open');

    const panel = document.getElementById('math-keyboard-panel');
    const targetName = document.getElementById('keyboard-target-name');
    const liveInput = document.getElementById('keyboard-live-input');

    if (targetName) targetName.textContent = fieldKey.toUpperCase();
    if (liveInput) {
      this.preventNativeKeyboard(liveInput);
      if (inputEl) {
        liveInput.value = inputEl.value || '';
      }
    }
    if (inputEl) {
      this.preventNativeKeyboard(inputEl);
    }

    if (panel) {
      panel.classList.add('open');
    }

    // Input qutisini aktiv deb belgilash
    document.querySelectorAll('.savol-input-box').forEach(b => b.classList.remove('focused'));
    const boxEl = document.getElementById(`box-${fieldKey}`);
    if (boxEl) {
      boxEl.classList.add('focused');
      setTimeout(() => {
        boxEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 60);
    }

    const curLen = (inputEl && inputEl.value ? inputEl.value.length : 0);
    this.setCursor(curLen);

    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
    }
  },

  close() {
    // Tepadagi bo'limlarni qayta ko'rsatish
    document.body.classList.remove('keyboard-open');

    const panel = document.getElementById('math-keyboard-panel');
    if (panel) panel.classList.remove('open');
    document.querySelectorAll('.savol-input-box').forEach(b => b.classList.remove('focused'));
    this.activeFieldKey = null;
    this.activeInputElement = null;
    this.waitingRootDegree = false;
  },

  onLiveInput(val) {
    if (!this.activeFieldKey) return;
    if (this.activeInputElement) {
      this.activeInputElement.value = val;
    }
    
    if (typeof TestApp !== 'undefined' && TestApp.setOpenAnswer) {
      TestApp.setOpenAnswer(this.activeFieldKey, val);
    } else if (window.TestApp && window.TestApp.setOpenAnswer) {
      window.TestApp.setOpenAnswer(this.activeFieldKey, val);
    }

    if (typeof AdminApp !== 'undefined' && AdminApp.updateOpenAns) {
      AdminApp.updateOpenAns(this.activeFieldKey, val);
    } else if (window.AdminApp && window.AdminApp.updateOpenAns) {
      window.AdminApp.updateOpenAns(this.activeFieldKey, val);
    }

    const boxEl = document.getElementById(`box-${this.activeFieldKey}`);
    if (boxEl) {
      boxEl.classList.toggle('filled', (val || '').trim().length > 0);
    }
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

  moveCursor(dir) {
    const liveInput = document.getElementById('keyboard-live-input');
    const targetInput = this.activeInputElement || liveInput;
    if (!targetInput) return;
    const len = (targetInput.value || '').length;
    let pos = targetInput.selectionStart ?? len;
    pos = Math.max(0, Math.min(len, pos + dir));
    this.setCursor(pos);
  },

  insertNthRoot() {
    if (!this.activeFieldKey) return;
    const liveInput = document.getElementById('keyboard-live-input');
    const targetInput = this.activeInputElement || liveInput;
    if (!targetInput) return;

    let text = targetInput.value || '';
    let start = targetInput.selectionStart ?? text.length;
    let end = targetInput.selectionEnd ?? text.length;

    // 1-holat: Kursordan oldingi belgi allaqachon daraja yoki son bo'lsa (masalan: 5 yozib, keyin ⁿ√ bosilsa):
    if (start > 0) {
      const prevChar = text[start - 1];
      const sup = SUPERSCRIPTS[prevChar];
      if (sup) {
        // Oldingi raqamni ustki darajaga o'girib, yoniga √ qo'yamiz (masalan, 5 -> ⁵√):
        const newVal = text.substring(0, start - 1) + sup + '√' + text.substring(end);
        const newPos = start - 1 + sup.length + 1; // √ dan keyinga o'tish
        this.applyValue(newVal, newPos);
        this.waitingRootDegree = false;
        return;
      }
    }

    // 2-holat: ⁿ√ ni qo'yish va n ustiga daraja kiritish rejimini faollashtirish:
    const newVal = text.substring(0, start) + 'ⁿ√' + text.substring(end);
    this.waitingRootDegree = true;
    this.applyValue(newVal, start); // kursorni 'ⁿ' ustiga qo'yish
    this.setSelection(start, start + 1); // 'ⁿ' ni tanlangan (selected) holatda ko'rsatish
  },

  insert(val) {
    if (!this.activeFieldKey) return;
    if (val === 'ⁿ√') {
      this.insertNthRoot();
      return;
    }

    const liveInput = document.getElementById('keyboard-live-input');
    const targetInput = this.activeInputElement || liveInput;
    if (!targetInput) return;

    let text = targetInput.value || '';
    let start = targetInput.selectionStart ?? text.length;
    let end = targetInput.selectionEnd ?? text.length;

    // n-DARAJALI ILDIZ BOSILGANDAN SO'NG DARAJA KIRITILSA:
    // "n darajalli ildiz bosilganda har qanday daraja bosilsa u n ni orniga bolib qolishi kere"
    const hasNthRoot = text.indexOf('ⁿ√') !== -1;
    if (this.waitingRootDegree || hasNthRoot) {
      const sup = SUPERSCRIPTS[val] || (val.length === 1 && /[0-9a-zA-Z]/.test(val) ? val : null);
      if (sup) {
        // 'ⁿ√' joylashuvini aniqlaymiz:
        let idx = -1;
        if (text.slice(start, start + 2) === 'ⁿ√') idx = start;
        else if (start > 0 && text.slice(start - 1, start + 1) === 'ⁿ√') idx = start - 1;
        else idx = text.indexOf('ⁿ√');

        if (idx !== -1) {
          const newVal = text.substring(0, idx) + sup + '√' + text.substring(idx + 2);
          const newPos = idx + sup.length + 1; // Kursorni to'g'ridan-to'g'ri √ dan keyinga o'tkazish!
          this.applyValue(newVal, newPos);
          this.waitingRootDegree = false;
          return;
        }
      }
    }

    this.waitingRootDegree = false;

    // Oddiy belgi kiritish:
    const newVal = text.substring(0, start) + val + text.substring(end);
    const newPos = start + val.length;
    this.applyValue(newVal, newPos);
  },

  insertPower(powerChar) {
    if (!this.activeFieldKey) return;
    const liveInput = document.getElementById('keyboard-live-input');
    const targetInput = this.activeInputElement || liveInput;
    if (!targetInput) return;

    let text = targetInput.value || '';
    // Agar ⁿ√ kutilayotgan bo'lsa, to'g'ridan-to'g'ri n o'rniga daraja bo'lib tushsin:
    if (this.waitingRootDegree || text.indexOf('ⁿ√') !== -1) {
      this.insert(powerChar);
      return;
    }

    const start = targetInput.selectionStart ?? targetInput.value.length;
    const charBefore = start > 0 ? text[start - 1] : '';

    // Agar kursordan oldingi belgi son, harf, qavs yoki π (pi) bo'lsa:
    // Faqat daraja ko'rsatkichining o'zini biriktir (masalan: π², π³, x², 5³, (a+b)²)
    if (/[a-zA-Z0-9\)\_π]/.test(charBefore)) {
      this.insert(powerChar);
    } else {
      // Agar oldinda hech narsa bo'lmasa, x ning darajasini qo'yadi:
      this.insert('x' + powerChar);
    }
  },

  insertPiPower(p) {
    if (!this.activeFieldKey) return;
    if (p === 1) this.insert('π');
    else if (p === 2) this.insert('π²');
    else if (p === 3) this.insert('π³');
    else this.insert('π^');
  },

  insertCustomPower() {
    if (!this.activeFieldKey) return;
    const liveInput = document.getElementById('keyboard-live-input');
    const targetInput = this.activeInputElement || liveInput;
    if (!targetInput) return;

    let text = targetInput.value || '';
    if (this.waitingRootDegree || text.indexOf('ⁿ√') !== -1) {
      this.insert('^');
      return;
    }

    const start = targetInput.selectionStart ?? targetInput.value.length;
    const charBefore = start > 0 ? text[start - 1] : '';

    if (/[a-zA-Z0-9\)\_π]/.test(charBefore)) {
      this.insert('^');
    } else {
      this.insert('x^');
    }
  },

  backspace() {
    if (!this.activeFieldKey) return;
    const liveInput = document.getElementById('keyboard-live-input');
    const targetInput = this.activeInputElement || liveInput;
    if (!targetInput) return;

    const start = targetInput.selectionStart ?? targetInput.value.length;
    const end = targetInput.selectionEnd ?? targetInput.value.length;
    const text = targetInput.value || '';

    let newVal = text;
    let newPos = start;

    if (start === end && start > 0) {
      // Agar kursor oldida yoki orqasida 'ⁿ√' tursa, butunligicha o'chirish:
      if (start >= 2 && text.substring(start - 2, start) === 'ⁿ√') {
        newVal = text.substring(0, start - 2) + text.substring(end);
        newPos = start - 2;
      } else if (start >= 1 && text.substring(start - 1, start + 1) === 'ⁿ√') {
        newVal = text.substring(0, start - 1) + text.substring(start + 1);
        newPos = start - 1;
      } else {
        newVal = text.substring(0, start - 1) + text.substring(end);
        newPos = start - 1;
      }
    } else if (start !== end) {
      // Agar 'ⁿ' tanlangan bo'lsa va undan keyin '√' tursa, ikkalasini birga o'chirish:
      if (text.substring(start, end) === 'ⁿ' && text[end] === '√') {
        newVal = text.substring(0, start) + text.substring(end + 1);
        newPos = start;
      } else {
        newVal = text.substring(0, start) + text.substring(end);
        newPos = start;
      }
    }

    this.waitingRootDegree = false;
    this.applyValue(newVal, newPos);
  },

  clear() {
    if (!this.activeFieldKey) return;
    this.waitingRootDegree = false;
    this.applyValue('', 0);
  },

  onInputChange() {
    if (!this.activeFieldKey) return;
    const liveInput = document.getElementById('keyboard-live-input');
    const val = (this.activeInputElement ? this.activeInputElement.value : '') || (liveInput ? liveInput.value : '');
    
    // Asosiy TestApp holatiga saqlash
    if (typeof TestApp !== 'undefined' && TestApp.setOpenAnswer) {
      TestApp.setOpenAnswer(this.activeFieldKey, val);
    } else if (window.TestApp && window.TestApp.setOpenAnswer) {
      window.TestApp.setOpenAnswer(this.activeFieldKey, val);
    }

    if (typeof AdminApp !== 'undefined' && AdminApp.updateOpenAns) {
      AdminApp.updateOpenAns(this.activeFieldKey, val);
    } else if (window.AdminApp && window.AdminApp.updateOpenAns) {
      window.AdminApp.updateOpenAns(this.activeFieldKey, val);
    }

    // Box indicator
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
    this.waitingRootDegree = false;
    const idx = this.activeFieldOrder.indexOf(this.activeFieldKey);
    if (idx > 0) {
      this.openFor(this.activeFieldOrder[idx - 1]);
    }
  },

  nextField() {
    if (!this.activeFieldKey) return;
    this.waitingRootDegree = false;
    const idx = this.activeFieldOrder.indexOf(this.activeFieldKey);
    if (idx < this.activeFieldOrder.length - 1) {
      this.openFor(this.activeFieldOrder[idx + 1]);
    }
  },

  switchTab(tab) {
    const tabs = ['math', 'power', 'func', 'vars'];
    tabs.forEach(t => {
      const btn = document.getElementById(`kb-tab-${t}`);
      const body = document.getElementById(`keyboard-body-${t}`);
      if (btn) btn.classList.toggle('active', t === tab);
      if (body) body.style.display = t === tab ? 'flex' : 'none';
    });
  }
};

window.MathKeyboard = MathKeyboard;

document.addEventListener('DOMContentLoaded', () => {
  MathKeyboard.init();
});
