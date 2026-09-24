/* Thalheimer is Among Us - Spielseite (/play/).
 * Das Spiel (main.py) laeuft hier als WebAssembly direkt auf dem Geraet (pygbag).
 * Diese Datei verbindet Python mit dem Browser:
 *   window.tiauNet  - WebSocket zum Server (Bytes als base64, siehe browser_bridge.py)
 *   window.tiauGame - Sounds/Video/Spielende aus Python, Ladeanzeige, Werkzeugleiste
 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const ROOM = (params.get("room") || "").toUpperCase();
  const NAME = params.get("name") || "";

  // ---------------------------------------------------------------- base64 <-> Bytes
  function bytesToB64(u8) {
    let s = "";
    const CH = 0x8000;
    for (let i = 0; i < u8.length; i += CH) s += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
    return btoa(s);
  }
  function b64ToBytes(b64) {
    const s = atob(b64);
    const u8 = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) u8[i] = s.charCodeAt(i);
    return u8;
  }

  // ---------------------------------------------------------------- Netzwerk
  window.tiauNet = {
    ws: null,
    inbox: [],
    state: "new",
    closeReason: "",
    open(room, name) {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const url = `${proto}://${location.host}/ws/game?room=${encodeURIComponent(room)}&name=${encodeURIComponent(name)}`;
      this.state = "connecting";
      try {
        this.ws = new WebSocket(url);
      } catch (e) {
        this.state = "closed";
        this.closeReason = "Verbindung zum Server fehlgeschlagen.";
        return;
      }
      this.ws.binaryType = "arraybuffer";
      this.ws.onopen = () => { this.state = "open"; };
      this.ws.onclose = (e) => {
        this.state = "closed";
        if (e && e.reason) this.closeReason = e.reason;
      };
      this.ws.onerror = () => { if (!this.closeReason) this.closeReason = "Verbindung zum Server fehlgeschlagen."; };
      this.ws.onmessage = (e) => {
        if (typeof e.data === "string") return;
        this.inbox.push(bytesToB64(new Uint8Array(e.data)));
      };
    },
    send(b64) {
      if (this.ws && this.ws.readyState === 1) this.ws.send(b64ToBytes(b64));
    },
    poll() {
      if (!this.inbox.length) return "";
      const r = this.inbox.join(",");
      this.inbox = [];
      return r;
    },
    close() {
      if (this.ws) { try { this.ws.close(); } catch (e) { /* ok */ } }
    },
  };

  // ---------------------------------------------------------------- Sound
  const audio = new window.TiauAudio();
  fetch("/api/info", { cache: "no-store" })
    .then((r) => r.json())
    .then((info) => audio.configure(info.sounds))
    .catch(() => {});
  const unlockAudio = () => audio.unlock();
  window.addEventListener("keydown", unlockAudio, true);
  window.addEventListener("pointerdown", unlockAudio, true);

  // ---------------------------------------------------------------- Video (Vladimir)
  function playVideo(src) {
    const v = $("tiauVideo");
    window.tiauGame.videoEnded = false;
    v.src = src;
    v.muted = audio.muted;
    v.classList.remove("hidden");
    const p = v.play();
    if (p && p.catch) p.catch(() => { v.muted = true; v.play().catch(() => stopVideo(true)); });
  }
  function stopVideo(ended) {
    const v = $("tiauVideo");
    v.pause();
    v.classList.add("hidden");
    v.removeAttribute("src");
    v.load();
    if (ended) window.tiauGame.videoEnded = true;
    focusCanvas();
  }

  // ---------------------------------------------------------------- Spiel <-> Seite
  let ended = false;
  window.tiauGame = {
    videoEnded: false,
    loading(text) {
      const t = $("tiauLoadText");
      if (t) t.textContent = text;
    },
    fps(value, workMs) {
      const el = $("tiauFps");
      if (el) el.textContent = value + " FPS";
      if (el) el.title = `Rechenzeit pro Bild: ${workMs} ms`;
      window.tiauGame.lastFps = value;
      window.tiauGame.lastWorkMs = workMs;
    },
    ready() {
      $("tiauLoad").classList.add("hidden");
      $("tiauBar").classList.remove("hidden");
      focusCanvas();
    },
    onEvent(json) {
      let ev;
      try { ev = JSON.parse(json); } catch (e) { return; }
      if (audio.handle(ev)) return;
      if (ev.t === "video") {
        if (ev.on) playVideo(ev.src); else stopVideo(false);
      } else if (ev.t === "end") {
        showEnd(ev.text || "Die Verbindung wurde beendet.", ev.reason);
      }
    },
  };

  function showEnd(text, reason) {
    if (ended) return;
    ended = true;
    audio.stopAll();
    $("tiauLoad").classList.add("hidden");
    $("tiauEndTitle").textContent = reason === "join_failed" ? "Beitritt nicht möglich" : "Spiel beendet";
    $("tiauEndText").textContent = text;
    $("tiauEnd").classList.remove("hidden");
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  }

  function focusCanvas() {
    const c = $("canvas");
    if (c) c.focus();
  }

  // ---------------------------------------------------------------- Werkzeugleiste
  function toast(text) {
    const t = $("tiauToast");
    t.textContent = text;
    t.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove("show"), 3000);
  }

  function copyLink() {
    const link = `${location.origin}/?room=${ROOM}`;
    const done = () => toast("Einladungslink kopiert: " + link);
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(link).then(done, () => fallbackCopy(link, done));
    } else {
      fallbackCopy(link, done);
    }
  }
  function fallbackCopy(text, done) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); done(); } catch (e) { prompt("Link zum Kopieren:", text); }
    ta.remove();
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("tiauCode").textContent = ROOM || "-----";
    document.title = `Raum ${ROOM} - Thalheimer is Among Us`;
    $("tiauCopy").addEventListener("click", () => { copyLink(); focusCanvas(); });
    $("tiauSound").addEventListener("click", () => {
      audio.setMuted(!audio.muted);
      $("tiauSound").textContent = audio.muted ? "Ton: aus" : "Ton: an";
      $("tiauVideo").muted = audio.muted;
      focusCanvas();
    });
    $("tiauFull").addEventListener("click", () => {
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      else document.documentElement.requestFullscreen().catch(() => {});
      focusCanvas();
    });
    $("tiauLeave").addEventListener("click", () => {
      if (confirm("Raum wirklich verlassen?")) {
        window.tiauNet.close();
        location.href = "/";
      } else {
        focusCanvas();
      }
    });
    $("tiauBack").addEventListener("click", () => { location.href = "/"; });
    $("tiauVideo").addEventListener("ended", () => stopVideo(true));
    $("tiauVideo").addEventListener("error", () => { if (!$("tiauVideo").classList.contains("hidden")) stopVideo(true); });
    // Leiste nur zeigen, wenn die Maus nach oben geht
    window.addEventListener("mousemove", (e) => $("tiauBar").classList.toggle("show", e.clientY < 64));
    if (!ROOM || !NAME) {
      showEnd("Es fehlen Raum-Code oder Name. Bitte über die Raumliste beitreten.", "join_failed");
    }
  });

  window.addEventListener("pagehide", () => window.tiauNet.close());
})();
