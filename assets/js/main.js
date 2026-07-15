/* ==========================================================================
   SUZAKU main.js — ナビゲーション / 演出 / Cookie同意 / 共通ユーティリティ
   ========================================================================== */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  /* ---------- ストレージ(プライベートモード等でも落ちないように) ---------- */
  function lsGet(key, fallback) {
    try {
      var v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch (e) { return fallback; }
  }
  function lsSet(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* noop */ }
  }
  window.szStore = { get: lsGet, set: lsSet };

  /* ---------- トースト ---------- */
  var toastTimer = null;
  window.szToast = function (msg) {
    var el = $("#toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove("is-visible"); }, 2800);
  };

  /* ---------- カートバッジ ---------- */
  window.szUpdateCartBadge = function () {
    var badge = $("#cartBadge");
    if (!badge) return;
    var cart = lsGet("sz_cart", []);
    var n = cart.reduce(function (a, x) { return a + x.qty; }, 0);
    badge.textContent = n > 99 ? "99+" : String(n);
    badge.classList.toggle("is-on", n > 0);
  };

  /* ---------- カラーテーマ(ライト/ダーク/G/朱雀) ---------- */
  var THEMES = ["auto", "light", "dark", "g", "suzaku"];
  function applyTheme(name) {
    var html = document.documentElement;
    if (name === "auto") {
      html.setAttribute("data-theme", html.getAttribute("data-page-theme") || "dark");
    } else {
      html.setAttribute("data-theme", name);
    }
    $$("[data-theme-opt]").forEach(function (b) {
      var on = b.getAttribute("data-theme-opt") === name;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-checked", String(on));
    });
  }
  (function initTheme() {
    var html = document.documentElement;
    if (!html.getAttribute("data-page-theme")) {
      html.setAttribute("data-page-theme", html.getAttribute("data-theme") || "dark");
    }
    var saved = lsGet("sz_theme", "auto");
    if (THEMES.indexOf(saved) === -1) saved = "auto";
    applyTheme(saved);
    var btn = $("#themeBtn");
    var menu = $("#themeMenu");
    function closeMenu() {
      if (!menu) return;
      menu.classList.remove("is-open");
      if (btn) btn.setAttribute("aria-expanded", "false");
    }
    if (btn && menu) {
      btn.addEventListener("click", function () {
        var open = menu.classList.toggle("is-open");
        btn.setAttribute("aria-expanded", String(open));
      });
      /* iOS Safariは非インタラクティブ要素のタップでclickが発火しないため、pointerdownで外側クローズする */
      document.addEventListener("pointerdown", function (e) {
        if (menu.classList.contains("is-open") && !menu.contains(e.target)) closeMenu();
      });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeMenu();
      });
    }
    /* ドロップダウン・ドロワー内セグメント共通のテーマ選択 */
    $$("[data-theme-opt]").forEach(function (opt) {
      opt.addEventListener("click", function () {
        var name = opt.getAttribute("data-theme-opt");
        if (THEMES.indexOf(name) === -1) return;
        lsSet("sz_theme", name);
        applyTheme(name);
        closeMenu();
        window.szToast("テーマ: " + (opt.getAttribute("data-theme-label") || opt.textContent.trim()));
      });
    });
  })();

  /* ---------- サイト設定(この端末の表示設定 / アカウント設定とは無関係) ----------
     新しい設定項目は PREF_SCHEMA に1行足すだけで追加できる。
       key      … localStorage(sz_prefs)上のキー
       default  … 初期値
       apply    … 値を受け取り、<html>属性やクラスへ反映する関数(任意)
     applyPrefs() が全項目を走査して反映するため、項目追加時に個別配線は不要。 */
  var htmlEl = document.documentElement;
  var PREF_SCHEMA = {
    footerMode: {
      "default": "accordion",
      apply: function (v) { htmlEl.setAttribute("data-footer-mode", v); }
    },
    motion: {
      "default": "auto",
      apply: function (v) { htmlEl.setAttribute("data-motion", v); }
    },
    density: {
      "default": "comfortable",
      apply: function (v) { htmlEl.setAttribute("data-density", v); }
    }
  };
  function getPrefs() {
    var saved = lsGet("sz_prefs", {});
    var out = {};
    for (var k in PREF_SCHEMA) {
      out[k] = Object.prototype.hasOwnProperty.call(saved, k) ? saved[k] : PREF_SCHEMA[k]["default"];
    }
    return out;
  }
  function applyPrefs() {
    var p = getPrefs();
    for (var k in PREF_SCHEMA) {
      if (typeof PREF_SCHEMA[k].apply === "function") PREF_SCHEMA[k].apply(p[k]);
    }
    return p;
  }
  function setPref(key, value) {
    if (!PREF_SCHEMA[key]) return;
    var saved = lsGet("sz_prefs", {});
    saved[key] = value;
    lsSet("sz_prefs", saved);
    applyPrefs();
  }
  function resetPrefs() {
    try { localStorage.removeItem("sz_prefs"); } catch (e) { /* noop */ }
    applyPrefs();
  }
  window.szPrefs = { get: getPrefs, set: setPref, apply: applyPrefs, reset: resetPrefs, schema: PREF_SCHEMA };
  applyPrefs();

  /* ---------- ヘッダー ---------- */
  var header = $("#siteHeader");
  function onScroll() {
    if (header) header.classList.toggle("is-scrolled", window.scrollY > 8);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  var navToggle = $("#navToggle");
  function setDrawerOpen(open) {
    document.body.classList.toggle("drawer-open", open);
    if (navToggle) navToggle.setAttribute("aria-expanded", String(open));
  }
  if (navToggle) {
    navToggle.addEventListener("click", function () {
      setDrawerOpen(!document.body.classList.contains("drawer-open"));
    });
  }
  $$(".drawer__summary").forEach(function (btn) {
    var group = btn.closest(".drawer__group");
    function setGroupOpen(open) {
      group.classList.toggle("is-open", open);
      btn.setAttribute("aria-expanded", String(open));
    }
    setGroupOpen(group.classList.contains("is-open"));
    btn.addEventListener("click", function () {
      setGroupOpen(!group.classList.contains("is-open"));
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && document.body.classList.contains("drawer-open")) setDrawerOpen(false);
  });
  $$(".drawer a").forEach(function (a) {
    a.addEventListener("click", function () { setDrawerOpen(false); });
  });

  /* フッターのアコーディオン(スマートフォンのみ挙動、PCではCSSで常時展開)。
     設定で「常時展開(expanded)」を選んだ場合はトグルを無効化する。 */
  $$(".footer-map__title").forEach(function (title) {
    title.addEventListener("click", function () {
      if (htmlEl.getAttribute("data-footer-mode") === "expanded") return;
      if (window.matchMedia("(max-width: 640px)").matches) {
        title.parentElement.classList.toggle("is-open");
      }
    });
  });

  /* ---------- スクロールリビール ---------- */
  var revealTargets = $$(".reveal, .reveal-l, .reveal-r, .reveal-scale, .reveal-stagger");
  if ("IntersectionObserver" in window && revealTargets.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("is-inview");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    revealTargets.forEach(function (el) { io.observe(el); });
  } else {
    revealTargets.forEach(function (el) { el.classList.add("is-inview"); });
  }

  /* ---------- 数値カウントアップ ---------- */
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function animateCount(el) {
    var text = el.childNodes[0] && el.childNodes[0].nodeValue;
    if (!text) return;
    var m = text.trim().match(/^([+-]?)([\d,]+(?:\.\d+)?)$/);
    if (!m) return;
    var sign = m[1];
    var target = parseFloat(m[2].replace(/,/g, ""));
    var decimals = (m[2].split(".")[1] || "").length;
    var hasComma = m[2].indexOf(",") !== -1;
    var start = null;
    var dur = 1400;
    function fmt(v) {
      var s = v.toFixed(decimals);
      if (hasComma) s = Number(s).toLocaleString("ja-JP", { minimumFractionDigits: decimals });
      return sign + s;
    }
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.childNodes[0].nodeValue = fmt(target * eased);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  var counters = $$(".stat__value[data-count]");
  if (counters.length && !reduced && "IntersectionObserver" in window) {
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          animateCount(en.target);
          cio.unobserve(en.target);
        }
      });
    }, { threshold: 0.4 });
    counters.forEach(function (el) { cio.observe(el); });
  }

  /* ---------- アコーディオン(汎用) ---------- */
  document.addEventListener("click", function (e) {
    var q = e.target.closest(".accordion__q");
    if (!q) return;
    var item = q.closest(".accordion__item");
    item.classList.toggle("is-open");
    q.setAttribute("aria-expanded", String(item.classList.contains("is-open")));
  });

  /* ---------- タブ(汎用: data-tabs / data-tab / data-tab-panel) ---------- */
  $$("[data-tabs]").forEach(function (group) {
    var tabs = $$("[data-tab]", group);
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) { t.classList.toggle("is-active", t === tab); });
        $$("[data-tab-panel]", group).forEach(function (panel) {
          panel.hidden = panel.getAttribute("data-tab-panel") !== tab.getAttribute("data-tab");
        });
      });
    });
  });

  /* ---------- コードコピー ---------- */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".copy-btn");
    if (!btn) return;
    var block = btn.closest(".codeblock");
    var code = block ? block.querySelector("pre") : null;
    if (!code) return;
    var done = function () {
      btn.classList.add("is-copied");
      btn.textContent = "コピー済み";
      setTimeout(function () {
        btn.classList.remove("is-copied");
        btn.textContent = "コピー";
      }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code.textContent).then(done, done);
    } else { done(); }
  });

  /* ---------- 火の粉パーティクル(ヒーロー) ---------- */
  var canvas = $("#emberCanvas");
  if (canvas && !reduced) {
    var ctx = canvas.getContext("2d");
    var embers = [];
    var W, H;
    function resize() {
      W = canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
      H = canvas.height = canvas.offsetHeight * (window.devicePixelRatio || 1);
    }
    resize();
    window.addEventListener("resize", resize);
    var COUNT = Math.min(46, Math.floor(window.innerWidth / 26));
    for (var i = 0; i < COUNT; i++) {
      embers.push({
        x: Math.random(), y: Math.random(),
        r: 0.8 + Math.random() * 2.4,
        vy: 0.0004 + Math.random() * 0.0012,
        vx: (Math.random() - 0.5) * 0.0004,
        a: 0.15 + Math.random() * 0.55,
        hue: 8 + Math.random() * 26,
        tw: Math.random() * Math.PI * 2
      });
    }
    var visible = true;
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }).observe(canvas);
    }
    (function tick() {
      requestAnimationFrame(tick);
      if (!visible) return;
      ctx.clearRect(0, 0, W, H);
      var dpr = window.devicePixelRatio || 1;
      embers.forEach(function (p) {
        p.y -= p.vy;
        p.x += p.vx + Math.sin(p.tw += 0.01) * 0.00012;
        if (p.y < -0.05) { p.y = 1.05; p.x = Math.random(); }
        var flicker = 0.75 + Math.sin(p.tw * 3) * 0.25;
        ctx.beginPath();
        ctx.arc(p.x * W, p.y * H, p.r * dpr, 0, Math.PI * 2);
        ctx.fillStyle = "hsla(" + p.hue + ", 92%, 58%, " + (p.a * flicker) + ")";
        ctx.shadowColor = "hsla(" + p.hue + ", 92%, 55%, 0.8)";
        ctx.shadowBlur = 8 * dpr;
        ctx.fill();
        ctx.shadowBlur = 0;
      });
    })();
  }

  /* ---------- Cookie同意 ---------- */
  var CONSENT_KEY = "sz_consent";
  var banner = $("#cookieBanner");
  var modal = $("#consentModal");

  /* Cookieバナーの実高を測ってCSS変数に反映する。表示中の管理者プレビュー
     チップ(.admin-preview)がモバイルでバナーと重ならないよう、バナー側の
     高さをチップのbottomオフセット計算に使う(--maint-h/--announce-hと同じ手法)。 */
  function syncCookieH() {
    var h = (banner && banner.classList.contains("is-visible")) ? banner.offsetHeight : 0;
    document.documentElement.style.setProperty("--cookie-h", h + "px");
  }
  window.addEventListener("resize", syncCookieH);

  function saveConsent(analytics, marketing) {
    lsSet(CONSENT_KEY, {
      necessary: true,
      analytics: !!analytics,
      marketing: !!marketing,
      date: new Date().toISOString(),
      version: 2
    });
    if (banner) banner.classList.remove("is-visible");
    syncCookieH();
    closeModal();
    window.szToast("Cookie設定を保存しました");
    renderConsentState();
  }
  function openModal() {
    if (!modal) return;
    var c = lsGet(CONSENT_KEY, null) || {};
    var an = $("#consentAnalytics"), mk = $("#consentMarketing");
    if (an) an.checked = !!c.analytics;
    if (mk) mk.checked = !!c.marketing;
    modal.classList.add("is-visible");
    modal.setAttribute("aria-hidden", "false");
  }
  function closeModal() {
    if (!modal) return;
    modal.classList.remove("is-visible");
    modal.setAttribute("aria-hidden", "true");
  }
  window.szOpenCookieSettings = openModal;

  function renderConsentState() {
    // /legal/cookie/ の現在設定表示
    var box = $("#consentStateBox");
    if (!box) return;
    var c = lsGet(CONSENT_KEY, null);
    if (!c) {
      box.innerHTML = "<p>現在、Cookie設定は保存されていません(バナー表示中)。</p>";
      return;
    }
    box.innerHTML =
      "<p><strong>保存日時:</strong> " + new Date(c.date).toLocaleString("ja-JP") + "</p>" +
      "<p><strong>必須Cookie:</strong> 有効(常時) / <strong>分析:</strong> " + (c.analytics ? "同意" : "拒否") +
      " / <strong>マーケティング:</strong> " + (c.marketing ? "同意" : "拒否") + "</p>";
  }

  if (!lsGet(CONSENT_KEY, null) && banner) {
    setTimeout(function () { banner.classList.add("is-visible"); syncCookieH(); }, 900);
  }
  var btnA = $("#consentAcceptAll");
  var btnR = $("#consentRejectAll");
  var btnO = $("#consentOpenSettings");
  var btnS = $("#consentSave");
  var btnC = $("#consentModalClose");
  var btnF = $("#cookieSettingsBtn");
  if (btnA) btnA.addEventListener("click", function () { saveConsent(true, true); });
  if (btnR) btnR.addEventListener("click", function () { saveConsent(false, false); });
  if (btnO) btnO.addEventListener("click", openModal);
  if (btnF) btnF.addEventListener("click", openModal);
  if (btnS) btnS.addEventListener("click", function () {
    saveConsent($("#consentAnalytics").checked, $("#consentMarketing").checked);
  });
  if (btnC) btnC.addEventListener("click", closeModal);
  if (modal) modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeModal(); });
  renderConsentState();
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-open-cookie-settings]");
    if (t) { e.preventDefault(); openModal(); }
  });

  /* ---------- キャッシュの手動削除(Cookie設定ページ・Cookie設定モーダルの両方に配置) ---------- */
  $$(".clear-cache-trigger").forEach(function (clearCacheBtn) {
    clearCacheBtn.addEventListener("click", function () {
      clearCacheBtn.disabled = true;
      clearCacheBtn.textContent = "削除しています…";
      Promise.resolve()
        .then(function () {
          if ("caches" in window) {
            return caches.keys().then(function (keys) {
              return Promise.all(keys.map(function (k) { return caches.delete(k); }));
            });
          }
        })
        .catch(function () { /* noop */ })
        .then(function () {
          if ("serviceWorker" in navigator) {
            return navigator.serviceWorker.getRegistrations().then(function (regs) {
              return Promise.all(regs.map(function (r) { return r.unregister(); }));
            });
          }
        })
        .catch(function () { /* noop */ })
        .then(function () {
          window.szToast("キャッシュを削除しました。最新の状態に更新します…");
          setTimeout(function () {
            /* URLを一意にして、このページのHTML自体をブラウザキャッシュを介さず再取得する。
               HTMLに書き出されたCSS/JSのURLは常にビルド時点の最新バージョン(?v=ハッシュ)を
               指しているため、この再取得だけで古いCSS/JSとの混在を解消できる。 */
            var base = window.location.origin + window.location.pathname;
            window.location.href = base + "?_cachebust=" + Date.now();
          }, 500);
        });
    });
  });

  /* ---------- 検索ボックス(ヘッダー以外の共通) ---------- */
  $$("form[data-search-form]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = form.querySelector("input[name=q]").value.trim();
      window.location.href = "/search/?q=" + encodeURIComponent(q);
    });
  });

  szUpdateCartBadge();
})();
