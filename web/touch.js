/* Thalheimer is Among Us - Touch-Steuerung fuer Handy und Tablet.
 * Wird von der Spielseite (/play/, das Spiel laeuft im Browser) UND vom Server-Modus (app.js) benutzt.
 *
 *  - erkennt Handy/Tablet (Touchscreen + grober Zeiger bzw. mobiler Browser); wer auf einem Laptop
 *    den Bildschirm beruehrt, bekommt die Touch-Steuerung ebenfalls
 *  - Joystick links unten: stufenlos (Richtung UND Tempo), erscheint dort, wo der Daumen aufsetzt,
 *    und wandert mit, wenn der Daumen ueber den Rand hinaus zieht
 *  - Zusatzknoepfe je nach Spielsituation (meldet das Spiel mit "touchctx"):
 *      X = Aufgabe/Karte schliessen (Q), Pfeile = Vent wechseln (A/D), Chat-Feld im Meeting
 *  - Hinweis "Geraet quer halten", Vollbild beim ersten Antippen, Menueknopf fuer die Werkzeugleiste
 * Die Aktions-Buttons (Toeten, Melden, Benutzen, Vent, Faehigkeit, Karte, Rolle) zeichnet das Spiel
 * selbst unten rechts - die werden einfach angetippt.
 */
(function () {
  "use strict";

  const DEAD_ZONE = 0.14;      // so weit darf der Daumen zittern, ohne dass die Figur laeuft
  const FULL_SPEED = 0.8;      // ab hier volle Geschwindigkeit (Anteil des Joystick-Radius)

  const CSS = `
html.tt-on, html.tt-on body { touch-action: none; overscroll-behavior: none; -webkit-user-select: none; user-select: none;
  -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent; }
.tt-root { position: fixed; inset: 0; pointer-events: none; z-index: 30; font-family: "Segoe UI", system-ui, Arial, sans-serif; }
.tt-root .tt-hide { display: none !important; }
.tt-zone { position: fixed; left: 0; bottom: 0; pointer-events: auto; touch-action: none; }
.tt-base { position: fixed; border-radius: 50%; transform: translate(-50%, -50%); pointer-events: none;
  background: radial-gradient(circle, rgba(255,255,255,.05) 0%, rgba(255,255,255,.10) 62%, rgba(255,255,255,.2) 100%);
  border: 2px solid rgba(255,255,255,.38); box-shadow: 0 0 22px rgba(0,0,0,.45), inset 0 0 18px rgba(0,0,0,.35);
  opacity: .5; transition: opacity .2s, left .18s ease-out, top .18s ease-out; }
.tt-base.active { opacity: .95; }
.tt-knob { position: absolute; left: 50%; top: 50%; width: 46%; height: 46%; margin: -23% 0 0 -23%; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #ffffff, #c4cdf0 55%, #7d8bc4); box-shadow: 0 4px 12px rgba(0,0,0,.5);
  will-change: transform; }
.tt-base:not(.active) .tt-knob { transition: transform .12s ease-out; }
.tt-btn { position: fixed; pointer-events: auto; touch-action: none; display: flex; align-items: center; justify-content: center;
  border: 2px solid rgba(255,255,255,.45); background: rgba(16,18,32,.78); color: #fff; font-weight: 900; border-radius: 50%;
  box-shadow: 0 4px 14px rgba(0,0,0,.5); padding: 0; line-height: 1; transition: transform .06s, background .06s; }
.tt-btn.pressed { transform: scale(.9); background: rgba(70,82,140,.9); }
.tt-close { background: rgba(150,30,42,.85); }
.tt-chatzone { position: fixed; pointer-events: auto; border-radius: 8px; }
.tt-chat { position: fixed; left: 8px; right: 8px; top: 8px; z-index: 72; display: flex; gap: 8px; pointer-events: auto;
  padding: 8px; border-radius: 14px; background: rgba(12,14,28,.96); border: 1px solid #3b4585; box-shadow: 0 8px 30px rgba(0,0,0,.6); }
.tt-chat input { flex: 1; min-width: 0; font-size: 17px; padding: 10px 12px; border-radius: 10px; border: 1px solid #4a5596;
  background: #f4f5fb; color: #111; -webkit-user-select: text; user-select: text; touch-action: manipulation; }
.tt-chat button { border: 0; border-radius: 10px; padding: 0 16px; font-size: 16px; font-weight: 800; color: #fff; background: #1f6fd6; }
.tt-chat .tt-chatx { background: #3a4170; padding: 0 14px; }
.tt-menu { top: 8px; right: 8px; width: 44px; height: 44px; font-size: 22px; border-radius: 12px; z-index: 41; opacity: .8; }
.tt-rotate { position: fixed; inset: 0; z-index: 80; display: none; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px; background: #070913; color: #eef0fa; text-align: center; padding: 24px; pointer-events: auto; font-size: 18px; }
.tt-rotate b { font-size: 54px; display: inline-block; animation: ttturn 1.8s ease-in-out infinite; }
@keyframes ttturn { 0%, 30% { transform: rotate(0); } 60%, 100% { transform: rotate(-90deg); } }
@media (orientation: portrait) { html.tt-on .tt-rotate { display: flex; } }
html.tt-on .tt-toolbar { display: none !important; }
html.tt-on .tt-toolbar.tt-open { display: flex !important; opacity: 1 !important; top: 60px !important; right: 8px !important;
  left: auto !important; flex-wrap: wrap; justify-content: flex-end; max-width: calc(100vw - 16px); z-index: 42; }
html.tt-on .tt-toolbar.tt-open button { min-height: 40px; font-size: 14px; }
`;

  function detect() {
    const params = new URLSearchParams(location.search);
    const ua = navigator.userAgent || "";
    const points = navigator.maxTouchPoints || 0;
    const coarse = !!(window.matchMedia && matchMedia("(pointer: coarse)").matches);
    const mobileUA = /Android|iPhone|iPad|iPod|Mobile|Tablet|Silk|Kindle|PlayBook|BlackBerry/i.test(ua);
    const iPadOS = /Macintosh/.test(ua) && points > 1;      // iPads melden sich als Mac
    let touch = points > 0 && (coarse || mobileUA || iPadOS);
    if (params.get("touch") === "1") touch = true;          // zum Testen erzwingen
    if (params.get("touch") === "0") touch = false;
    const shortSide = Math.min(screen.width || innerWidth, screen.height || innerHeight);
    const phone = /iPhone|iPod/i.test(ua) || (/Android/i.test(ua) && /Mobile/i.test(ua)) || shortSide < 600;
    return { touch, kind: phone ? "handy" : "tablet", capable: points > 0 || touch };
  }

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  class TiauTouch {
    /* opts: canvas (Element mit dem Spielbild), gameW/gameH (1440x810), toolbar (Element, optional),
     *       onMode(m 0/1/2), onAxis(x, y), onKey("q"|"a"|"d"), onText(text) */
    constructor(opts) {
      this.canvas = opts.canvas;
      this.gameW = opts.gameW || 1440;
      this.gameH = opts.gameH || 810;
      this.toolbar = opts.toolbar || null;
      this.onMode = opts.onMode || (() => {});
      this.onAxis = opts.onAxis || (() => {});
      this.onKey = opts.onKey || (() => {});
      this.onText = opts.onText || (() => {});
      const d = detect();
      this.kind = d.kind;
      this.capable = d.capable;
      this.enabled = false;
      this.userOff = false;
      this.ctx = { joy: 0, close: 0, vent: 0, chat: null };
      this.axis = { x: 0, y: 0 };
      this.stick = null;
      this.rect = null;
      this.radius = 60;
      this.home = { x: 100, y: 300 };
      this.triedFullscreen = false;
      this._listeners = [];
      this._build();
      this._bindGlobal();
      this.setEnabled(d.touch);
    }

    mode() { return this.enabled ? (this.kind === "handy" ? 2 : 1) : 0; }

    // ------------------------------------------------------------------ Aufbau
    _build() {
      if (!document.getElementById("tt-style")) {
        const st = document.createElement("style");
        st.id = "tt-style";
        st.textContent = CSS;
        document.head.appendChild(st);
      }
      const root = this.root = document.createElement("div");
      root.className = "tt-root";
      root.addEventListener("contextmenu", (e) => e.preventDefault());

      this.zone = document.createElement("div");
      this.zone.className = "tt-zone";
      this.base = document.createElement("div");
      this.base.className = "tt-base";
      this.knob = document.createElement("div");
      this.knob.className = "tt-knob";
      this.base.appendChild(this.knob);
      this.zone.addEventListener("pointerdown", (e) => this._down(e));
      this.zone.addEventListener("pointermove", (e) => this._move(e));
      this.zone.addEventListener("pointerup", (e) => this._up(e));
      this.zone.addEventListener("pointercancel", (e) => this._up(e));
      this.zone.addEventListener("lostpointercapture", (e) => this._up(e));

      this.btnClose = this._button("tt-close", "✕", "q", "Schließen");
      this.btnVentL = this._button("tt-vent", "◀", "a", "Vorheriger Vent");
      this.btnVentR = this._button("tt-vent", "▶", "d", "Nächster Vent");

      this.chatZone = document.createElement("div");
      this.chatZone.className = "tt-chatzone";
      // "click" statt "pointerdown": nur so darf das Eingabefeld (auch auf dem iPhone) die Tastatur oeffnen
      this.chatZone.addEventListener("click", () => this.openChat());

      this.chat = document.createElement("form");
      this.chat.className = "tt-chat tt-hide";
      this.chat.innerHTML = '<input type="text" maxlength="120" enterkeyhint="send" autocomplete="off" autocorrect="off"' +
        ' autocapitalize="sentences" spellcheck="false" placeholder="Nachricht an alle ..." aria-label="Chat-Nachricht">' +
        '<button type="submit">Senden</button><button type="button" class="tt-chatx" aria-label="Chat schließen">✕</button>';
      this.chatInput = this.chat.querySelector("input");
      this.chat.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = this.chatInput.value.trim();
        if (text) this.onText(text);
        this.chatInput.value = "";
        this.chatInput.focus();            // Tastatur bleibt offen fuer die naechste Nachricht
      });
      this.chat.querySelector(".tt-chatx").addEventListener("click", () => this.closeChat());
      // Tasten im Eingabefeld gehoeren NUR dem Feld (sonst tippt das Spiel doppelt mit)
      ["keydown", "keyup", "keypress"].forEach((t) => this.chatInput.addEventListener(t, (e) => e.stopPropagation()));

      this.menu = this._button("tt-menu", "☰", null, "Menü");
      this.menu.addEventListener("click", () => {
        if (this.toolbar && !this.toolbar.classList.contains("hidden")) this.toolbar.classList.toggle("tt-open");
      });

      this.rotate = document.createElement("div");
      this.rotate.className = "tt-rotate";
      this.rotate.innerHTML = "<b>📱</b><div>Bitte das Gerät <strong>quer</strong> halten.</div>";

      [this.zone, this.base, this.btnClose, this.btnVentL, this.btnVentR, this.chatZone, this.chat, this.menu]
        .forEach((el) => root.appendChild(el));
      document.body.appendChild(root);
      document.body.appendChild(this.rotate);     // liegt ueber allem (auch Ladebildschirm/Leiste)

      if (this.toolbar) {
        this.toolbar.classList.add("tt-toolbar");
        if (this.capable) {
          this.toggleBtn = document.createElement("button");
          this.toggleBtn.className = this.toolbar.querySelector("button") ? this.toolbar.querySelector("button").className : "";
          this.toggleBtn.type = "button";
          this.toggleBtn.addEventListener("click", () => {
            this.userOff = this.enabled;
            this.setEnabled(!this.enabled);
            this.toolbar.classList.remove("tt-open");
          });
          const last = this.toolbar.lastElementChild;
          this.toolbar.insertBefore(this.toggleBtn, last);
        }
      }
    }

    _button(cls, label, key, title) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "tt-btn " + cls;
      b.textContent = label;
      b.title = title;
      b.setAttribute("aria-label", title);
      if (key) {
        // sofort beim Beruehren reagieren (nicht erst beim Loslassen)
        b.addEventListener("pointerdown", (e) => {
          e.preventDefault();
          b.classList.add("pressed");
          this._buzz();
          this.onKey(key);
        });
        const up = () => b.classList.remove("pressed");
        ["pointerup", "pointercancel", "pointerleave"].forEach((t) => b.addEventListener(t, up));
      }
      return b;
    }

    _on(target, type, fn, opts) {
      target.addEventListener(type, fn, opts);
      this._listeners.push([target, type, fn, opts]);
    }

    _bindGlobal() {
      const relayout = () => { this._layout(); this._apply(); };
      this._on(window, "resize", relayout);
      this._on(window, "orientationchange", () => setTimeout(relayout, 250));
      if (window.visualViewport) this._on(window.visualViewport, "resize", relayout);
      if (window.ResizeObserver && this.canvas) {
        this._ro = new ResizeObserver(relayout);
        this._ro.observe(this.canvas);
      }
      // Wer den Bildschirm beruehrt, bekommt die Touch-Steuerung (z.B. Laptop mit Touchscreen)
      this._on(window, "touchstart", () => {
        if (!this.enabled && !this.userOff) this.setEnabled(true);
      }, { capture: true, passive: true });
      // Vollbild + Querformat beim ersten Antippen (Browser erlauben das nur nach einer Beruehrung)
      this._on(window, "pointerup", (e) => {
        if (e.pointerType !== "mouse" && this.enabled && !this.triedFullscreen) {
          this.triedFullscreen = true;
          this.fullscreen();
        }
      }, true);
      const release = () => this._release();
      this._on(window, "blur", release);
      this._on(document, "visibilitychange", () => { if (document.hidden) release(); });
    }

    fullscreen() {
      const el = document.documentElement;
      const req = el.requestFullscreen || el.webkitRequestFullscreen;
      if (!req || document.fullscreenElement || document.webkitFullscreenElement) return;
      try {
        const p = req.call(el, { navigationUI: "hide" });
        const lock = () => { try { screen.orientation.lock("landscape").catch(() => {}); } catch (e) { /* egal */ } };
        if (p && p.then) p.then(lock).catch(() => {}); else lock();
      } catch (e) { /* iPhone: kein Vollbild fuer Webseiten */ }
    }

    destroy() {
      this._release();
      this.closeChat();
      this._listeners.forEach(([t, type, fn, opts]) => t.removeEventListener(type, fn, opts));
      this._listeners = [];
      if (this._ro) this._ro.disconnect();
      this.root.remove();
      this.rotate.remove();
      if (this.toggleBtn) this.toggleBtn.remove();
      if (this.toolbar) this.toolbar.classList.remove("tt-toolbar", "tt-open");
      document.documentElement.classList.remove("tt-on");
    }

    // ------------------------------------------------------------------ Zustand
    setEnabled(on) {
      this.enabled = !!on;
      document.documentElement.classList.toggle("tt-on", this.enabled);
      if (!this.enabled) {
        this._release();
        this.closeChat();
        if (this.toolbar) this.toolbar.classList.remove("tt-open");
      }
      if (this.toggleBtn) this.toggleBtn.textContent = this.enabled ? "Touch: an" : "Touch: aus";
      this._layout();
      this._apply();
      this.onMode(this.mode());
    }

    setContext(ctx) {
      this.ctx = {
        joy: ctx.joy ? 1 : 0,
        close: ctx.close ? 1 : 0,
        vent: ctx.vent ? 1 : 0,
        chat: Array.isArray(ctx.chat) && ctx.chat.length === 4 ? ctx.chat : null,
      };
      if (!this.ctx.joy) this._release();
      if (!this.ctx.chat) this.closeChat();
      this._apply();
    }

    _apply() {
      const on = this.enabled;
      const show = (el, v) => el.classList.toggle("tt-hide", !v);
      show(this.zone, on && this.ctx.joy);
      show(this.base, on && this.ctx.joy);
      show(this.btnClose, on && this.ctx.close);
      show(this.btnVentL, on && this.ctx.vent);
      show(this.btnVentR, on && this.ctx.vent);
      show(this.chatZone, on && this.ctx.chat);
      show(this.menu, on && this.toolbar);
      if (on && this.ctx.chat && this.rect) {
        const [x, y, w, h] = this.ctx.chat;
        const sx = this.rect.width / this.gameW, sy = this.rect.height / this.gameH;
        Object.assign(this.chatZone.style, {
          left: this.rect.left + x * sx + "px", top: this.rect.top + y * sy + "px",
          width: w * sx + "px", height: Math.max(h * sy, 36) + "px",
        });
      }
    }

    _layout() {
      if (!this.canvas) return;
      const r = this.canvas.getBoundingClientRect();
      if (r.width < 50 || r.height < 50) return;      // Spielbild noch nicht da
      this.rect = r;
      const vw = window.innerWidth, vh = window.innerHeight;
      const shortSide = Math.min(vw, vh);
      const R = this.radius = Math.round(clamp(shortSide * (this.kind === "handy" ? 0.17 : 0.12), 46, 92));

      // Joystick-Bereich: vom linken Rand bis zum Ende der linken Spielleiste, untere Haelfte
      const zoneW = Math.max(r.left + r.width * 0.23, R * 2.8);
      const zoneTop = Math.min(r.top + r.height * 0.5, vh - R * 2.6);
      Object.assign(this.zone.style, { width: zoneW + "px", top: zoneTop + "px" });
      this.home = {
        x: clamp(r.left + r.width * 0.115, R + 10, zoneW - R * 0.6),
        y: clamp(r.top + r.height * 0.8, zoneTop + R, vh - R - 12),
      };
      const size = 2 * R + "px";
      Object.assign(this.base.style, { width: size, height: size });
      if (!this.stick) this._placeBase(this.home.x, this.home.y, true);

      // Knoepfe: Schliessen oben rechts im Spielbild, Vent-Pfeile unten in der Mitte
      const b = Math.round(clamp(shortSide * 0.13, 46, 72));
      const style = (el, css) => Object.assign(el.style, css, { width: b + "px", height: b + "px", fontSize: Math.round(b * 0.42) + "px" });
      style(this.btnClose, { right: Math.max(8, vw - r.right + 12) + "px", top: Math.max(60, r.top + r.height * 0.1) + "px" });
      const ventY = Math.max(10, vh - r.bottom + r.height * 0.05) + "px";
      style(this.btnVentL, { left: r.left + r.width * 0.4 - b / 2 + "px", bottom: ventY });
      style(this.btnVentR, { left: r.left + r.width * 0.6 - b / 2 + "px", bottom: ventY });
    }

    // ------------------------------------------------------------------ Joystick
    _placeBase(x, y, animate) {
      const R = this.radius;
      x = clamp(x, R + 4, window.innerWidth - R - 4);
      y = clamp(y, R + 4, window.innerHeight - R - 4);
      this.base.style.transition = animate ? "" : "opacity .2s";
      this.base.style.left = x + "px";
      this.base.style.top = y + "px";
      if (this.stick) { this.stick.cx = x; this.stick.cy = y; }
    }

    _down(e) {
      if (this.stick || !this.enabled || !this.ctx.joy) return;
      e.preventDefault();
      this.stick = { id: e.pointerId, cx: e.clientX, cy: e.clientY };
      try { this.zone.setPointerCapture(e.pointerId); } catch (err) { /* egal */ }
      this._placeBase(e.clientX, e.clientY, false);
      this.base.classList.add("active");
      this._buzz();
      this._track(e.clientX, e.clientY);
    }

    _move(e) {
      if (!this.stick || e.pointerId !== this.stick.id) return;
      e.preventDefault();
      // gesammelte Zwischenpositionen braucht es nicht - die letzte zaehlt
      this._track(e.clientX, e.clientY);
    }

    _up(e) {
      if (!this.stick || e.pointerId !== this.stick.id) return;
      this._release();
    }

    _release() {
      if (!this.stick) {
        this._setAxis(0, 0);
        return;
      }
      try { this.zone.releasePointerCapture(this.stick.id); } catch (err) { /* egal */ }
      this.stick = null;
      this.base.classList.remove("active");
      this.knob.style.transform = "translate(0px, 0px)";
      this._placeBase(this.home.x, this.home.y, true);
      this._setAxis(0, 0);
    }

    _track(px, py) {
      const s = this.stick, R = this.radius;
      let dx = px - s.cx, dy = py - s.cy;
      let dist = Math.hypot(dx, dy);
      const follow = R * 1.1;
      if (dist > follow) {
        // Daumen zieht ueber den Rand: der Joystick wandert mit (kein "Festhaengen" am Rand)
        const k = (dist - follow) / dist;
        this._placeBase(s.cx + dx * k, s.cy + dy * k, false);
        dx = px - s.cx; dy = py - s.cy;
        dist = Math.hypot(dx, dy);
      }
      const m = Math.min(1, dist / R);
      const nx = dist > 0 ? dx / dist : 0, ny = dist > 0 ? dy / dist : 0;
      this.knob.style.transform = `translate(${(nx * m * R).toFixed(1)}px, ${(ny * m * R).toFixed(1)}px)`;
      const out = m <= DEAD_ZONE ? 0 : Math.min(1, (m - DEAD_ZONE) / (FULL_SPEED - DEAD_ZONE));
      this._setAxis(nx * out, ny * out);
    }

    _setAxis(x, y) {
      x = Math.round(x * 1000) / 1000;
      y = Math.round(y * 1000) / 1000;
      if (x === this.axis.x && y === this.axis.y) return;
      this.axis = { x, y };
      this.onAxis(x, y);
    }

    // ------------------------------------------------------------------ Chat
    openChat() {
      if (!this.enabled || !this.ctx.chat) return;
      this.chat.classList.remove("tt-hide");
      this.chatInput.focus();
    }

    closeChat() {
      if (this.chat.classList.contains("tt-hide")) return;
      this.chatInput.blur();
      this.chat.classList.add("tt-hide");
    }

    _buzz() {
      try { if (navigator.vibrate) navigator.vibrate(8); } catch (e) { /* egal */ }
    }
  }

  TiauTouch.detect = detect;
  window.TiauTouch = TiauTouch;
})();
