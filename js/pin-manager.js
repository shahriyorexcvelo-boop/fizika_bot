/**
 * PIN-KOD BOSHQARUVCHISI — js/pin-manager.js
 * 4 xonali PIN o'rnatish, tekshirish va Telegram CloudStorage logikasi
 */

(function(window) {
  'use strict';

  const LS_PIN = 'app_pin';

  var pinState = {
    buffer: '',
    firstPin: '',
    mode: 'enter' // 'setup' | 'confirm' | 'enter'
  };

  /**
   * PIN ekrani initsializatsiyasi
   */
  async function initPinScreen() {
    var hasPin = !!localStorage.getItem(LS_PIN);
    var userInfo = (window.state && window.state.userInfo) || null;

    if (!hasPin && userInfo && userInfo.has_pin) {
      hasPin = true;
    }

    // Telegram CloudStorage tekshirish
    if (!hasPin && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.CloudStorage) {
      try {
        window.Telegram.WebApp.CloudStorage.getItem(LS_PIN, function(err, val) {
          if (!err && val) {
            // CloudStorage'dan kelgan qiymat base64 yoki ochiq matn bo'lishi mumkin
            var safeVal = val;
            try {
              atob(val); // base64 ekanligini sinab ko'ramiz — xato bo'lsa catch ga o'tamiz
            } catch (e) {
              safeVal = btoa(val); // ochiq matn — base64 ga o'giramiz
            }
            localStorage.setItem(LS_PIN, safeVal);
            pinState.mode = 'enter';
            if (window.state) window.state.pinMode = 'enter';
            updatePinUI(true);
          }
        });
      } catch (e) {}
    }


    updatePinUI(hasPin);
    renderPinDots(0);

    // Agar PIN mavjud bo'lmasa yoki pin-screen HTML da bo'lmasa, ilovani to'g'ridan-to'g'ri ishga tushirish
    var pinScreen = document.getElementById('pin-screen');
    if (!pinScreen) {
      // pin-screen element yo'q — splash orqali to'g'ri ishga tushiramiz
      if (typeof window.runSplash === 'function') window.runSplash();
      else if (typeof window.launchApp === 'function') window.launchApp();
      return;
    }

    if (!hasPin) {
      // PIN yo'q — to'g'ridan app'ga o'tamiz (setup keyinroq)
      pinScreen.style.display = 'none';
      if (typeof window.runSplash === 'function') window.runSplash();
      else if (typeof window.launchApp === 'function') window.launchApp();
    } else {
      // PIN bor — ekranni ko'rsatamiz
      pinScreen.style.display = 'flex';
    }
  }

  function updatePinUI(hasPin) {

    var pinTitle = document.getElementById('pin-title');
    var pinSub = document.getElementById('pin-subtitle');
    if (!pinTitle || !pinSub) return;

    var t = window.t || function(k) { return k; };
    var userInfo = (window.state && window.state.userInfo) || null;
    var tgUser = (window.state && window.state.tgUser) || null;

    if (!hasPin) {
      pinState.mode = 'setup';
      if (window.state) window.state.pinMode = 'setup';
      pinTitle.textContent = t('pin_create');
      pinSub.textContent = t('pin_create_sub');
    } else {
      pinState.mode = 'enter';
      if (window.state) window.state.pinMode = 'enter';
      var name = (userInfo && userInfo.fullname) || (tgUser && tgUser.first_name) || 'Foydalanuvchi';
      pinTitle.textContent = t('welcome') + ', ' + name.split(' ')[0] + '!';
      pinSub.textContent = t('pin_enter_sub');
    }
  }

  function onPinKey(val) {
    if (pinState.buffer.length >= 4) return;
    pinState.buffer += val;
    if (window.state) window.state.pinBuffer = pinState.buffer;

    renderPinDots(pinState.buffer.length);
    if (pinState.buffer.length === 4) {
      setTimeout(processPin, 120);
    }
  }

  function onPinDel() {
    if (pinState.buffer.length === 0) return;
    pinState.buffer = pinState.buffer.slice(0, -1);
    if (window.state) window.state.pinBuffer = pinState.buffer;

    renderPinDots(pinState.buffer.length);
  }

  function renderPinDots(count, mode) {
    var dots = document.querySelectorAll('.pin-dot');
    dots.forEach(function(d, i) {
      d.classList.remove('filled', 'error');
      if (mode === 'error') {
        d.classList.add('error');
      } else if (i < count) {
        d.classList.add('filled');
      }
    });
  }

  async function processPin() {
    var pin = pinState.buffer;
    pinState.buffer = '';
    if (window.state) window.state.pinBuffer = '';

    var t = window.t || function(k) { return k; };
    var tgId = (window.state && window.state.tgUser && window.state.tgUser.id) || 0;
    var mode = (window.state && window.state.pinMode) || pinState.mode;

    if (mode === 'setup') {
      pinState.firstPin = pin;
      pinState.mode = 'confirm';
      if (window.state) {
        window.state.pinFirst = pin;
        window.state.pinMode = 'confirm';
      }

      var pinTitle = document.getElementById('pin-title');
      var pinSub = document.getElementById('pin-subtitle');
      if (pinTitle) pinTitle.textContent = t('pin_confirm');
      if (pinSub) pinSub.textContent = t('pin_confirm_sub');

      renderPinDots(0);
      showPinError('');
    } else if (mode === 'confirm') {
      var expectedFirst = (window.state && window.state.pinFirst) || pinState.firstPin;
      if (pin === expectedFirst) {
        // 1. LocalStorage ga saqlash
        localStorage.setItem(LS_PIN, btoa(pin));

        // 2. Telegram CloudStorage ga saqlash
        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.CloudStorage) {
          try {
            window.Telegram.WebApp.CloudStorage.setItem(LS_PIN, btoa(pin));
          } catch (e) {}
        }

        // 3. Serverga saqlash
        if (tgId) {
          try {
            var authHeaders = (typeof window.getAuthHeaders === 'function')
              ? window.getAuthHeaders({ 'Content-Type': 'application/json' })
              : { 'Content-Type': 'application/json' };

            fetch('/api/app/set-pin', {
              method: 'POST',
              headers: authHeaders,
              body: JSON.stringify({
                tg_id: tgId,
                pin: pin,
                init_data: (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''
              })
            });
          } catch (e) {}
        }

        showPinError('');
        if (typeof window.launchApp === 'function') {
          window.launchApp();
        }
      } else {
        showPinError(t('pin_mismatch'));
        renderPinDots(4, 'error');
        pinState.mode = 'setup';
        pinState.firstPin = '';
        if (window.state) {
          window.state.pinMode = 'setup';
          window.state.pinFirst = '';
        }

        setTimeout(function() {
          renderPinDots(0);
          var pt = document.getElementById('pin-title');
          var ps = document.getElementById('pin-subtitle');
          if (pt) pt.textContent = t('pin_create');
          if (ps) ps.textContent = t('pin_create_sub');
          showPinError('');
        }, 1000);
      }
    } else {
      // mode === 'enter'
      var stored = '';
      try {
        stored = atob(localStorage.getItem(LS_PIN) || '');
      } catch (e) {}

      var isValid = (stored && pin === stored);

      if (!isValid && tgId) {
        try {
          var authH = (typeof window.getAuthHeaders === 'function')
            ? window.getAuthHeaders({ 'Content-Type': 'application/json' })
            : { 'Content-Type': 'application/json' };

          var res = await fetch('/api/app/verify-pin', {
            method: 'POST',
            headers: authH,
            body: JSON.stringify({
              tg_id: tgId,
              pin: pin,
              init_data: (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''
            })
          });
          var data = await res.json();
          if (data.valid) {
            isValid = true;
            localStorage.setItem(LS_PIN, btoa(pin));
          }
        } catch (e) {}
      }

      if (isValid) {
        showPinError('');
        if (typeof window.launchApp === 'function') {
          window.launchApp();
        }
      } else {
        showPinError(t('pin_wrong'));
        renderPinDots(4, 'error');
        setTimeout(function() {
          renderPinDots(0);
          showPinError('');
        }, 900);
      }
    }
  }

  function showPinError(msg) {
    var el = document.getElementById('pin-error');
    if (el) el.textContent = msg;
  }

  function changePinPrompt() {
    localStorage.removeItem(LS_PIN);
    pinState.buffer = '';
    pinState.firstPin = '';
    pinState.mode = 'setup';

    if (window.state) {
      window.state.pinBuffer = '';
      window.state.pinFirst = '';
      window.state.pinMode = 'setup';
    }

    var pinScreen = document.getElementById('pin-screen');
    var app = document.getElementById('app');
    var t = window.t || function(k) { return k; };

    var pt = document.getElementById('pin-title');
    var ps = document.getElementById('pin-subtitle');
    if (pt) pt.textContent = t('pin_create');
    if (ps) ps.textContent = t('pin_create_sub');

    renderPinDots(0);
    showPinError('');

    if (app) {
      app.style.display = 'none';
      app.classList.remove('visible');
    }
    if (pinScreen) {
      pinScreen.style.transition = '';
      pinScreen.style.opacity = '1';
      pinScreen.style.transform = 'scale(1)';
      pinScreen.style.display = 'flex';
    }
  }

  // Global Scope eksport
  window.LS_PIN = LS_PIN;
  window.initPinScreen = initPinScreen;
  window.updatePinUI = updatePinUI;
  window.onPinKey = onPinKey;
  window.onPinDel = onPinDel;
  window.renderPinDots = renderPinDots;
  window.processPin = processPin;
  window.showPinError = showPinError;
  window.changePinPrompt = changePinPrompt;

})(window);
