/**
 * MATEMATIK YORDAMCHILAR VA XAVFSIZ PARSER — js/math-utils.js
 * Matematik javoblarni tozalash (normalizeAnswer), xavfsiz tokenizer va parser (evalNumericVal),
 * hamda taqqoslash yordamchilari (checkAnswerMatch, countBinaryPlusMinus)
 */

(function(window) {
  'use strict';

  /**
   * Foydalanuvchi va to'g'ri kalit javoblarini standart formatga keltirish.
   */
  function normalizeAnswer(ans) {
    if (ans === undefined || ans === null) return '';
    var s = String(ans).trim();

    // 1. Bo'shliqlar, ko'rinmas belgilar va dollar belgilarini olib tashlash
    s = s.replace(/[\s\u200b\u200c\u200d\u00a0\uFEFF\$]/g, '');

    // 2. Barcha klaviaturalardagi minus/chiziqchalarni bitta standart '-' belgisiga keltirish
    s = s.replace(/[–—−‐⁃֊־]/g, '-');

    // 3. Barcha ko'paytirish belgilarini '*' ga keltirish
    s = s.replace(/[·•✕✖×*]/g, '*');
    s = s.replace(/\\+(?:cdot|times)\b/g, '*');

    // 4. Bo'lish belgilarini '/' ga keltirish
    s = s.replace(/[\u00f7]/g, '/');

    // 5. Funksiyalardagi vergulni ajratuvchi sifatida himoya qilish (masalan: pow(2, 3) -> pow(2;3))
    s = s.replace(/pow\(([^,]+),([^)]+)\)/gi, 'pow($1;$2)');

    // 6. O'nlik kasrlardagi vergul: 2,5 -> 2.5
    s = s.replace(/(\d+),(\d+)/g, '$1.$2');

    // 7. Plus-minus belgisi
    s = s.replace(/(\+\/\-|\+\s*\-|\+\-)/g, '±');

    // 8. Pi soni: \pi, pi, PI -> π
    s = s.replace(/(^|[^a-zA-Z])\\*pi(?![a-zA-Z])/gi, '$1π');

    // 9. Cheksizlik (Infinity): \infty, infty, infinity, inf, cheksiz, cheksizlik -> ∞
    s = s.replace(/\\+infty\b|\\infty\b|\\inf\b/g, '∞');
    s = s.replace(/(?:infinity|infty|inf|cheksiz(?:lik)?)\b/gi, '∞');
    s = s.replace(/(?<![0-9a-zA-Z])\+∞/g, '∞');

    // Oraliqlardagi vergul: [0, ∞) -> [0;∞), (-∞, 5) -> (-∞;5)
    s = s.replace(/([0-9a-zA-Z∞\.\-\+]+),([0-9a-zA-Z∞\.\-\+]+)/g, '$1;$2');

    // 10. Darajalarni standart ^ shakliga keltirish
    var sups = [
      ['⁰', '^0'], ['¹', '^1'], ['²', '^2'], ['³', '^3'], ['⁴', '^4'],
      ['⁵', '^5'], ['⁶', '^6'], ['⁷', '^7'], ['⁸', '^8'], ['⁹', '^9'], ['ⁿ', '^n']
    ];
    sups.forEach(function(pair) {
      s = s.split(pair[0]).join(pair[1]);
    });

    // 11. LaTeX residuallari: \frac, \sqrt, \sqrt[n]
    while (/\\+sqrt\[([^\]]+)\]\{([^{}]+)\}/.test(s)) {
      s = s.replace(/\\+sqrt\[([^\]]+)\]\{([^{}]+)\}/g, 'pow($2, 1/($1))');
    }
    while (/\\+d?frac\{([^{}]+)\}\{([^{}]+)\}/.test(s)) {
      s = s.replace(/\\+d?frac\{([^{}]+)\}\{([^{}]+)\}/g, '($1)/($2)');
    }
    while (/sqrt\{([^{}]+)\}/.test(s)) {
      s = s.replace(/\\+sqrt\{([^{}]+)\}/g, 'sqrt($1)');
    }
    s = s.replace(/\\+sqrt([0-9a-zA-Z]+)/g, 'sqrt($1)');
    s = s.replace(/sqrt\(/g, 'sqrt(');
    s = s.replace(/cbrt/g, '∛');

    // Ildiz qavslari: "√(29)" -> "√29", "5√(32)" -> "5√32"
    while (/([0-9a-zA-Z]*√)\(([0-9a-zA-Z]+)\)/.test(s)) {
      s = s.replace(/([0-9a-zA-Z]*√)\(([0-9a-zA-Z]+)\)/g, '$1$2');
    }
    while (/^\(([0-9a-zA-Z]*√[0-9a-zA-Z]+)\)$/.test(s)) {
      s = s.replace(/^\(([0-9a-zA-Z]*√[0-9a-zA-Z]+)\)$/g, '$1');
    }

    // Raqam va qavsli ildiz: "8(√58)" -> "8√58"
    s = s.replace(/(\d)\((√[0-9a-zA-Z]+)\)/g, '$1$2');

    // Tashqi ortiqcha qavslar: (-3π/2) -> -3π/2
    while (s.charAt(0) === '(' && s.charAt(s.length - 1) === ')' && (s.match(/\(/g) || []).length === 1) {
      s = s.slice(1, -1);
    }

    // "x = ", "x1 = ", "javob:" kabi prefikslarni tozalash
    s = s.replace(/^(?:[a-zA-Z]|x\d*|y\d*|k\d*)\s*=\s*/, '');
    s = s.replace(/^(?:javob|ans)\s*:\s*/i, '');

    // Ortiqcha figurali qavslar va sleshlar
    s = s.replace(/\{([^{}]+)\}/g, '$1');
    s = s.replace(/\\/g, '');

    return s.trim().toLowerCase();
  }

  /**
   * XAVFSIZ RECURSIVE DESCENT MATEMATIK PARSER
   * eval() yoki Function() ishlatmaydi.
   * Amallar: +, -, *, /, ^, **, unar minus, qavslar.
   * Funksiyalar va konstantalar: π, sqrt, cbrt, ∛, ∜, pow, abs.
   * Xato yoki notanish belgilarda null qaytaradi.
   */
  function evalNumericVal(expr) {
    var s = normalizeAnswer(expr);
    if (!s || s.indexOf('±') !== -1 || s.indexOf('∞') !== -1) return null;

    // 1. Ildiz belgilarini standart funktsiyalarga o'tkazamiz
    s = s.replace(/∛\(([^()]+)\)/g, 'cbrt($1)');
    s = s.replace(/∛(\d+(?:\.\d+)?)/g, 'cbrt($1)');
    s = s.replace(/∜\(([^()]+)\)/g, 'pow($1,0.25)');
    s = s.replace(/∜(\d+(?:\.\d+)?)/g, 'pow($1,0.25)');
    s = s.replace(/√\(([^()]+)\)/g, 'sqrt($1)');
    s = s.replace(/√(\d+(?:\.\d+)?)/g, 'sqrt($1)');
    s = s.replace(/√/g, 'sqrt');

    // Math. prefiksini olib tashlaymiz
    s = s.replace(/math\./gi, '');

    // 2. Yashirin ko'paytirish (Implicit multiplication): 3sqrt(...) -> 3*sqrt(...)
    s = s.replace(/(\d)(sqrt|cbrt|pow|abs|π|pi)/g, '$1*$2');
    s = s.replace(/(\))(sqrt|cbrt|pow|abs|π|pi)/g, '$1*$2');
    s = s.replace(/(π|pi)(\d)/g, '$1*$2');
    s = s.replace(/(π|pi)\s*\(/g, '$1*(');
    s = s.replace(/(\))\s*\(/g, '$1*(');
    s = s.replace(/(\d)\s*\(/g, '$1*(');
    s = s.replace(/(\))\s*(\d)/g, '$1*$2');

    // 3. Tokenizer
    var tokens = [];
    var i = 0;
    var len = s.length;

    while (i < len) {
      var c = s.charAt(i);
      if (c === ' ' || c === '\t' || c === '\r' || c === '\n') {
        i++;
        continue;
      }

      // Son (butun yoki o'nlik kasr)
      if ((c >= '0' && c <= '9') || c === '.') {
        var numStr = '';
        var hasDot = false;
        while (i < len && ((s.charAt(i) >= '0' && s.charAt(i) <= '9') || s.charAt(i) === '.')) {
          if (s.charAt(i) === '.') {
            if (hasDot) return null; // Ketma-ket ikkita nuqta xato
            hasDot = true;
          }
          numStr += s.charAt(i);
          i++;
        }
        var parsedNum = parseFloat(numStr);
        if (isNaN(parsedNum)) return null;
        tokens.push({ type: 'NUM', val: parsedNum });
        continue;
      }

      // Daraja belgisi: ** yoki ^
      if (c === '*' && s.charAt(i + 1) === '*') {
        tokens.push({ type: 'OP', val: '^' });
        i += 2;
        continue;
      }

      // Arifmetik amallar
      if ('+-*/^'.indexOf(c) !== -1) {
        tokens.push({ type: 'OP', val: c });
        i++;
        continue;
      }

      // Qavslar
      if (c === '(' || c === ')') {
        tokens.push({ type: c });
        i++;
        continue;
      }

      // Funksiya argumentlari ajratuvchisi (, yoki ;)
      if (c === ',' || c === ';') {
        tokens.push({ type: ',' });
        i++;
        continue;
      }

      // Pi belgisi
      if (c === 'π') {
        tokens.push({ type: 'CONST', val: Math.PI });
        i++;
        continue;
      }

      // Identifikatorlar (harflar bilan boshlanuvchi)
      if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) {
        var idStr = '';
        while (i < len && ((s.charAt(i) >= 'a' && s.charAt(i) <= 'z') || (s.charAt(i) >= 'A' && s.charAt(i) <= 'Z') || (s.charAt(i) >= '0' && s.charAt(i) <= '9'))) {
          idStr += s.charAt(i);
          i++;
        }
        idStr = idStr.toLowerCase();
        if (idStr === 'pi') {
          tokens.push({ type: 'CONST', val: Math.PI });
        } else if (['sqrt', 'cbrt', 'pow', 'abs'].indexOf(idStr) !== -1) {
          tokens.push({ type: 'FUNC', val: idStr });
        } else {
          // Ruxsat berilmagan harf yoki o'zgaruvchi (x, y, alert, Function, etc.)
          return null;
        }
        continue;
      }

      // Har qanday notanish belgi darhol xavfsiz reject qilinadi
      return null;
    }

    // 4. Recursive Descent Parser
    var pos = 0;

    function peek() {
      return tokens[pos];
    }

    function consume(expectedType) {
      var t = tokens[pos];
      if (!t || t.type !== expectedType) return null;
      pos++;
      return t;
    }

    function parseExpression() {
      var left = parseTerm();
      if (left === null) return null;
      while (pos < tokens.length) {
        var op = peek();
        if (op && op.type === 'OP' && (op.val === '+' || op.val === '-')) {
          pos++;
          var right = parseTerm();
          if (right === null) return null;
          if (op.val === '+') left = left + right;
          else left = left - right;
        } else {
          break;
        }
      }
      return left;
    }

    function parseTerm() {
      var left = parsePower();
      if (left === null) return null;
      while (pos < tokens.length) {
        var op = peek();
        if (op && op.type === 'OP' && (op.val === '*' || op.val === '/')) {
          pos++;
          var right = parsePower();
          if (right === null) return null;
          if (op.val === '*') {
            left = left * right;
          } else {
            if (Math.abs(right) < 1e-15) return null; // Nolga bo'lish
            left = left / right;
          }
        } else {
          break;
        }
      }
      return left;
    }

    function parsePower() {
      var base = parseFactor();
      if (base === null) return null;
      var op = peek();
      if (op && op.type === 'OP' && op.val === '^') {
        pos++;
        var exp = parsePower(); // O'ngdan chapga assotsiativlik
        if (exp === null) return null;
        base = Math.pow(base, exp);
      }
      return base;
    }

    function parseFactor() {
      var t = peek();
      if (!t) return null;

      // Unar minus yoki unar plyus
      if (t.type === 'OP' && (t.val === '+' || t.val === '-')) {
        pos++;
        var f = parseFactor();
        if (f === null) return null;
        return t.val === '-' ? -f : f;
      }

      // Oddiy son
      if (t.type === 'NUM') {
        pos++;
        return t.val;
      }

      // O'zgarmas (π)
      if (t.type === 'CONST') {
        pos++;
        return t.val;
      }

      // Matematik funksiyalar: sqrt, cbrt, pow, abs
      if (t.type === 'FUNC') {
        pos++;
        var funcName = t.val;
        if (!consume('(')) return null;
        var arg1 = parseExpression();
        if (arg1 === null) return null;
        var arg2 = null;
        if (funcName === 'pow') {
          if (!consume(',')) return null;
          arg2 = parseExpression();
          if (arg2 === null) return null;
        }
        if (!consume(')')) return null;

        if (funcName === 'sqrt') {
          if (arg1 < 0) return null;
          return Math.sqrt(arg1);
        } else if (funcName === 'cbrt') {
          return Math.cbrt ? Math.cbrt(arg1) : Math.pow(arg1, 1/3);
        } else if (funcName === 'pow') {
          return Math.pow(arg1, arg2);
        } else if (funcName === 'abs') {
          return Math.abs(arg1);
        }
        return null;
      }

      // Qavs ichidagi ifoda
      if (t.type === '(') {
        pos++;
        var val = parseExpression();
        if (val === null) return null;
        if (!consume(')')) return null;
        return val;
      }

      return null;
    }

    var result = parseExpression();
    if (pos !== tokens.length) return null; // Ifodadan keyin ortiqcha belgilar qolsa, xato
    return (typeof result === 'number' && !isNaN(result) && isFinite(result)) ? result : null;
  }

  /**
   * Binar qo'shish va ayirish amallari sonini sanash
   * (Hisoblanmay qolib ketgan amallarni aniqlash uchun).
   */
  function countBinaryPlusMinus(s) {
    if (!s) return 0;
    var cnt = 0;
    for (var i = 0; i < s.length; i++) {
      var ch = s.charAt(i);
      if (ch === '+') {
        cnt++;
      } else if (ch === '-') {
        if (i > 0 && ['(', '*', '/', '^', '±', '[', '{'].indexOf(s.charAt(i - 1)) === -1) {
          cnt++;
        }
      }
    }
    return cnt;
  }

  /**
   * Foydalanuvchi javobini to'g'ri kalitga solishtirish
   */
  function checkAnswerMatch(cVal, uVal) {
    if (cVal === undefined || cVal === null || uVal === undefined || uVal === null) {
      return { isOk: false, ratio: 0, status: 'incorrect' };
    }
    var cStr = String(cVal).trim();
    var uStr = String(uVal).trim();
    if (!cStr || !uStr) {
      return { isOk: false, ratio: 0, status: 'incorrect' };
    }

    // Agar kalitda bir nechta to'g'ri variant berilgan bo'lsa
    if (/[;\|]|\byoki\b|\bor\b/.test(cStr)) {
      var parts = cStr.split(/[;\|]|\byoki\b|\bor\b/);
      var best = { isOk: false, ratio: 0, status: 'incorrect' };
      for (var pi = 0; pi < parts.length; pi++) {
        var part = parts[pi].trim();
        if (part) {
          var res = checkAnswerMatch(part, uVal);
          if (res.ratio > best.ratio) best = res;
          if (best.ratio >= 1.0) return best;
        }
      }
      return best;
    }

    var nC = normalizeAnswer(cStr);
    var nU = normalizeAnswer(uStr);
    if (!nC || !nU) return { isOk: false, ratio: 0, status: 'incorrect' };

    // 1. To'g'ridan-to'g'ri matnli tenglik -> 100% to'g'ri
    if (nC === nU) return { isOk: true, ratio: 1.0, status: 'correct' };

    // 2. Yulduzcha ko'paytirish belgisisiz
    if (nC.replace(/\*/g, '') === nU.replace(/\*/g, '')) return { isOk: true, ratio: 1.0, status: 'correct' };

    // 3. Yig'indi hadlarining o'rin almashuvi (masalan: 120 + 36π == 36π + 120)
    if (nC.indexOf('+') !== -1 && nU.indexOf('+') !== -1) {
      var cTerms = nC.split('+').map(function(t) { return t.trim().replace(/\*/g, ''); }).sort().join('+');
      var uTerms = nU.split('+').map(function(t) { return t.trim().replace(/\*/g, ''); }).sort().join('+');
      if (cTerms === uTerms) return { isOk: true, ratio: 1.0, status: 'correct' };
    }

    // 4. Matematik ifodaning sonli qiymati tengligi (xavfsiz parser yordamida)
    var numC = evalNumericVal(nC);
    var numU = evalNumericVal(nU);
    if (numC !== null && numU !== null) {
      if ((numU > 1e-6 && numC < -1e-6) || (numU < -1e-6 && numC > 1e-6)) {
        return { isOk: false, ratio: 0, status: 'incorrect' };
      }
      if (Math.abs(numC - numU) < 1e-4) {
        if (countBinaryPlusMinus(nU) > countBinaryPlusMinus(nC)) {
          return { isOk: true, ratio: 0.3, status: 'partial' };
        }
        return { isOk: true, ratio: 1.0, status: 'correct' };
      }
    }

    return { isOk: false, ratio: 0, status: 'incorrect' };
  }

  function isAnswerMatching(cVal, uVal) {
    return checkAnswerMatch(cVal, uVal).isOk;
  }

  // Global Scope eksport
  window.normalizeAnswer = normalizeAnswer;
  window.evalNumericVal = evalNumericVal;
  window.countBinaryPlusMinus = countBinaryPlusMinus;
  window.checkAnswerMatch = checkAnswerMatch;
  window.isAnswerMatching = isAnswerMatching;

})(window);
