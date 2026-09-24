/* Thalheimer is Among Us - Browser-Client.
 * Der Browser zeigt nur das Bild an, das der Server berechnet, und schickt Tastatur/Maus zurueck.
 * Protokoll siehe web_bridge.py (_FrameEncoder).
 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const home = $("home"), game = $("game"), canvas = $("screen");
  const ctx = canvas.getContext("2d", { alpha: false });
  const base = document.createElement("canvas");
  const baseCtx = base.getContext("2d", { alpha: false });

  let info = { width: 1440, height: 810, sounds: {}, room_empty_timeout: 10 };
  let ws = null;
  let currentRoom = null;
  let ended = false;

  // ---------------------------------------------------------------- Hilfen
  function toast(text, isError) {
    const t = $("toast");
    t.textContent = text;
    t.className = "toast show" + (isError ? " error" : "");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (t.className = "toast"), 3500);
  }

  function storedName() {
    try { return localStorage.getItem("tiau_name") || ""; } catch (e) { return ""; }
  }
  function storeName(v) {
    try { localStorage.setItem("tiau_name", v); } catch (e) { /* privat/gesperrt - egal */ }
  }
  function playerName() {
    const v = $("playerName").value.trim();
    if (!v) {
      toast("Bitte zuerst einen Namen eingeben.", true);
      $("playerName").focus();
      return null;
    }
    storeName(v);
    return v;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---------------------------------------------------------------- Raumliste
  async function refreshRooms() {
    if (!home.classList.contains("hidden")) {
      try {
        const res = await fetch("/api/rooms", { cache: "no-store" });
        const data = await res.json();
        renderRooms(data.rooms || []);
        $("liveDot").classList.remove("offline");
        $("liveDot").textContent = "aktualisiert laufend";
      } catch (e) {
        $("liveDot").classList.add("offline");
        $("liveDot").textContent = "Server nicht erreichbar";
      }
    }
    setTimeout(refreshRooms, 2000);
  }

  function renderRooms(rooms) {
    const list = $("roomList");
    if (!rooms.length) {
      list.innerHTML = '<div class="empty">Noch keine Räume offen – erstelle einfach einen!</div>';
      return;
    }
    list.innerHTML = rooms.map((r) => {
      const full = r.players >= r.max;
      const status = r.game_active ? '<span class="badge ingame">Spiel läuft</span>' : '<span class="badge lobby">Lobby</span>';
      const host = r.host ? `Host: ${escapeHtml(r.host)}` : "wartet auf Spieler";
      const disabled = r.game_active || full ? "disabled" : "";
      const label = r.game_active ? "läuft" : full ? "voll" : "Beitreten";
      return `<div class="room">
        <div class="code">${escapeHtml(r.code)}</div>
        <div class="meta"><b>${escapeHtml(r.name)}${status}</b><small>${host}</small></div>
        <div class="players">${r.players}/${r.max} Spieler<div class="bar"><i style="width:${Math.round((100 * r.players) / r.max)}%"></i></div></div>
        <button class="btn small primary" data-code="${escapeHtml(r.code)}" ${disabled}>${label}</button>
      </div>`;
    }).join("");
  }

  $("roomList").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-code]");
    if (btn && !btn.disabled) joinRoom(btn.dataset.code);
  });

  $("joinBtn").addEventListener("click", () => {
    const code = $("joinCode").value.trim().toUpperCase();
    if (!/^[A-Z]{5}$/.test(code)) {
      toast("Der Raum-Code hat genau 5 Buchstaben.", true);
      return;
    }
    joinRoom(code);
  });
  $("joinCode").addEventListener("input", (e) => {
    e.target.value = e.target.value.toUpperCase().replace(/[^A-Z]/g, "");
  });
  $("joinCode").addEventListener("keydown", (e) => { if (e.key === "Enter") $("joinBtn").click(); });

  $("createBtn").addEventListener("click", async () => {
    const name = playerName();
    if (!name) return;
    $("createBtn").disabled = true;
    try {
      const res = await fetch("/api/rooms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: $("roomName").value.trim(), creator: name }),
      });
      if (!res.ok) {
        toast(await res.text(), true);
        return;
      }
      const data = await res.json();
      joinRoom(data.code);
    } catch (e) {
      toast("Raum konnte nicht erstellt werden.", true);
    } finally {
      $("createBtn").disabled = false;
    }
  });
  $("roomName").addEventListener("keydown", (e) => { if (e.key === "Enter") $("createBtn").click(); });

  // ---------------------------------------------------------------- Sound (Web Audio, siehe audio.js)
  const audio = new window.TiauAudio();
  const initAudio = () => { audio.configure(info.sounds); audio.unlock(); };
  const stopAllAudio = () => audio.stopAll();

  $("tbSound").addEventListener("click", () => {
    audio.setMuted(!audio.muted);
    const video = $("introVideo");
    video.muted = audio.muted;
    $("tbSound").textContent = audio.muted ? "Ton: aus" : "Ton: an";
    canvas.focus();
  });

  // ---------------------------------------------------------------- Bildanzeige
  const view = { worldActive: false, worldRect: null, worldImg: null, overlays: [] };
  let frameChain = Promise.resolve();
  let lastFrameAt = 0, framesThisSecond = 0, fps = 0;

  function fitCanvas() {
    const vw = window.innerWidth, vh = window.innerHeight;
    const scale = Math.min(vw / canvas.width, vh / canvas.height);
    canvas.style.width = Math.floor(canvas.width * scale) + "px";
    canvas.style.height = Math.floor(canvas.height * scale) + "px";
  }
  window.addEventListener("resize", fitCanvas);

  function decode(buf, offset, length, type) {
    return createImageBitmap(new Blob([new Uint8Array(buf, offset, length)], { type }));
  }

  async function handleFrame(buf) {
    const dv = new DataView(buf);
    let o = 0;
    const flags = dv.getUint8(o); o += 1;
    let worldRect = null, worldP = null, overlaysP = null;
    if (flags & 1) { worldRect = [dv.getUint16(o), dv.getUint16(o + 2), dv.getUint16(o + 4)]; o += 6; }
    if (flags & 2) { const len = dv.getUint32(o); o += 4; worldP = decode(buf, o, len, "image/jpeg"); o += len; }
    if (flags & 4) {
      const n = dv.getUint8(o); o += 1;
      overlaysP = [];
      for (let i = 0; i < n; i++) {
        const x = dv.getUint16(o), y = dv.getUint16(o + 2), len = dv.getUint32(o + 4); o += 8;
        overlaysP.push(decode(buf, o, len, "image/png").then((img) => ({ x, y, img })));
        o += len;
      }
    }
    const np = dv.getUint8(o); o += 1;
    const patchesP = [];
    for (let i = 0; i < np; i++) {
      const x = dv.getUint16(o), y = dv.getUint16(o + 2), len = dv.getUint32(o + 4); o += 8;
      patchesP.push(decode(buf, o, len, "image/jpeg").then((img) => ({ x, y, img })));
      o += len;
    }
    const [worldImg, overlays, patches] = await Promise.all([
      worldP, overlaysP ? Promise.all(overlaysP) : null, Promise.all(patchesP),
    ]);

    for (const p of patches) { baseCtx.drawImage(p.img, p.x, p.y); p.img.close && p.img.close(); }
    view.worldActive = !!(flags & 1);
    if (worldRect) view.worldRect = worldRect;
    if (worldImg) { if (view.worldImg && view.worldImg.close) view.worldImg.close(); view.worldImg = worldImg; }
    if (overlays || !view.worldActive) {
      for (const ov of view.overlays) ov.img.close && ov.img.close();
      view.overlays = overlays || [];
    }
    render();
  }

  function render() {
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(base, 0, 0);
    if (view.worldActive && view.worldImg && view.worldRect) {
      const [x, y, s] = view.worldRect;
      ctx.imageSmoothingEnabled = false;      // Pixelgrafik bleibt scharf
      ctx.drawImage(view.worldImg, x, y, s, s);
      ctx.imageSmoothingEnabled = true;
      for (const ov of view.overlays) ctx.drawImage(ov.img, ov.x, ov.y);
    }
  }

  function onBinary(buf) {
    frameChain = frameChain
      .then(() => handleFrame(buf))
      .then(() => {
        send({ t: "ack" });
        $("loading").classList.add("hidden");
        framesThisSecond++;
        const now = performance.now();
        if (now - lastFrameAt > 1000) {
          fps = framesThisSecond; framesThisSecond = 0; lastFrameAt = now;
          $("tbPing").textContent = fps + " Bilder/s";
        }
      })
      .catch((err) => {
        console.warn("Bildfehler", err);
        send({ t: "refresh" });
      });
  }

  // ---------------------------------------------------------------- Ereignisse vom Server
  function onEvent(msg) {
    switch (msg.t) {
      case "joined":
        currentRoom = msg.room;
        $("tbCode").textContent = msg.room;
        $("loadingText").textContent = "Lade das Spiel …";
        try { history.replaceState(null, "", "/?room=" + msg.room); } catch (e) { /* egal */ }
        break;
      case "sfx": case "loop": case "music": audio.handle(msg); break;
      case "video": msg.on ? playVideo(msg.src) : stopVideo(false); break;
      case "end": showEnded(msg.text || "Die Verbindung wurde beendet.", msg.reason); break;
    }
  }

  // ---------------------------------------------------------------- Video (Vladimirs Intro)
  function playVideo(src) {
    const v = $("introVideo");
    v.src = src;
    v.muted = audio.muted;
    v.classList.remove("hidden");
    const p = v.play();
    if (p && p.catch) {
      p.catch(() => { v.muted = true; v.play().catch(() => stopVideo(true)); });
    }
  }
  function stopVideo(notify) {
    const v = $("introVideo");
    v.pause();
    v.classList.add("hidden");
    v.removeAttribute("src");
    v.load();
    if (notify) send({ t: "video_end" });
  }
  $("introVideo").addEventListener("ended", () => stopVideo(true));
  $("introVideo").addEventListener("error", () => { if (!$("introVideo").classList.contains("hidden")) stopVideo(true); });

  // ---------------------------------------------------------------- Verbindung
  function send(obj) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
  }

  function joinRoom(code) {
    const name = playerName();
    if (!name) return;
    // NEU: Standard ist die Browser-Version (das Spiel rechnet auf diesem Geraet -> fluessig).
    // Nur mit Haken "Server berechnet das Spiel" (oder wenn sie nicht gebaut ist) der alte Streaming-Modus.
    if (!$("serverMode").checked && info.browser_client !== false) {
      location.href = `/play/?PYGPI=/cdn/&room=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`;
      return;
    }
    ended = false;
    initAudio();
    home.classList.add("hidden");
    game.classList.remove("hidden");
    $("ended").classList.add("hidden");
    $("loading").classList.remove("hidden");
    $("loadingText").textContent = `Verbinde mit Raum ${code} …`;
    $("tbCode").textContent = code;
    canvas.width = base.width = info.width;
    canvas.height = base.height = info.height;
    baseCtx.fillStyle = "#000";
    baseCtx.fillRect(0, 0, base.width, base.height);
    view.worldActive = false; view.worldImg = null; view.overlays = [];
    frameChain = Promise.resolve();
    fitCanvas();
    goFullscreen();
    canvas.focus();

    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws?room=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`);
    ws.binaryType = "arraybuffer";
    ws.onmessage = (e) => {
      if (typeof e.data === "string") {
        try { onEvent(JSON.parse(e.data)); } catch (err) { /* ignorieren */ }
      } else {
        onBinary(e.data);
      }
    };
    ws.onclose = () => {
      if (!ended) showEnded("Die Verbindung zum Server wurde getrennt.");
      releaseAllKeys();
      stopAllAudio();
      stopVideo(false);
    };
  }

  function showEnded(text, reason) {
    ended = true;
    $("loading").classList.add("hidden");
    $("endTitle").textContent = reason === "join_failed" ? "Beitritt nicht möglich" : "Spiel verlassen";
    $("endText").textContent = text;
    $("ended").classList.remove("hidden");
    stopAllAudio();
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  }

  function backToHome() {
    if (ws) { ended = true; try { ws.close(); } catch (e) { /* ok */ } ws = null; }
    game.classList.add("hidden");
    home.classList.remove("hidden");
    try { history.replaceState(null, "", "/"); } catch (e) { /* ok */ }
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  }
  $("endBack").addEventListener("click", backToHome);
  $("tbLeave").addEventListener("click", () => {
    if (confirm("Raum wirklich verlassen?")) backToHome();
    else canvas.focus();
  });

  $("tbCopy").addEventListener("click", () => {
    const link = `${location.origin}/?room=${currentRoom || ""}`;
    const done = () => toast("Link kopiert: " + link);
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(link).then(done, () => fallbackCopy(link, done));
    } else {
      fallbackCopy(link, done);
    }
    canvas.focus();
  });
  function fallbackCopy(text, done) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); done(); } catch (e) { prompt("Link zum Kopieren:", text); }
    ta.remove();
  }

  function goFullscreen() {
    const el = document.documentElement;
    if (!document.fullscreenElement && el.requestFullscreen) el.requestFullscreen().catch(() => {});
  }
  $("tbFull").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else goFullscreen();
    canvas.focus();
  });
  document.addEventListener("fullscreenchange", () => setTimeout(fitCanvas, 50));

  // Leiste kurz einblenden, wenn die Maus nach oben geht
  game.addEventListener("mousemove", (e) => {
    $("toolbar").classList.toggle("show", e.clientY < 70);
  });

  // ---------------------------------------------------------------- Eingaben
  const GAME_KEYS = new Set([" ", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Tab", "Backspace", "Enter", "'", "/"]);
  const downCodes = new Map();

  function inGame() { return !game.classList.contains("hidden") && ws && ws.readyState === 1; }

  window.addEventListener("keydown", (e) => {
    if (!inGame()) return;
    if (e.key === "F11" || e.key === "F12" || (e.ctrlKey && e.key.toLowerCase() === "r")) return;
    if (GAME_KEYS.has(e.key) || e.key.length === 1 || /^F\d+$/.test(e.key)) e.preventDefault();
    if (e.repeat) return;          // wie in pygame: gehaltene Tasten erzeugen kein neues KEYDOWN
    downCodes.set(e.code, e.key);
    send({ t: "kd", k: e.key, c: e.code, ctrl: e.ctrlKey || e.metaKey, alt: e.altKey });
  });
  window.addEventListener("keyup", (e) => {
    if (!inGame()) return;
    e.preventDefault();
    downCodes.delete(e.code);
    send({ t: "ku", k: e.key, c: e.code });
  });
  function releaseAllKeys() {
    downCodes.clear();
    send({ t: "blur" });
  }
  window.addEventListener("blur", () => { if (inGame()) { releaseAllKeys(); $("focusHint").classList.remove("hidden"); } });
  window.addEventListener("focus", () => $("focusHint").classList.add("hidden"));
  document.addEventListener("visibilitychange", () => { if (document.hidden && inGame()) releaseAllKeys(); });

  function toGame(e) {
    const r = canvas.getBoundingClientRect();
    return {
      x: Math.round(((e.clientX - r.left) * canvas.width) / r.width),
      y: Math.round(((e.clientY - r.top) * canvas.height) / r.height),
    };
  }
  canvas.addEventListener("mousedown", (e) => {
    if (!inGame()) return;
    canvas.focus();
    $("focusHint").classList.add("hidden");
    const p = toGame(e);
    send({ t: "md", b: e.button, x: p.x, y: p.y });
    e.preventDefault();
  });
  window.addEventListener("mouseup", (e) => {
    if (!inGame()) return;
    const p = toGame(e);
    send({ t: "mu", b: e.button, x: p.x, y: p.y });
  });
  let pendingMove = null;
  canvas.addEventListener("mousemove", (e) => {
    if (!inGame()) return;
    const first = pendingMove === null;
    pendingMove = toGame(e);
    if (first) {
      requestAnimationFrame(() => {   // hoechstens einmal pro Bildschirm-Frame senden
        if (pendingMove) send({ t: "mm", x: pendingMove.x, y: pendingMove.y });
        pendingMove = null;
      });
    }
  });
  canvas.addEventListener("wheel", (e) => {
    if (!inGame()) return;
    e.preventDefault();
    send({ t: "wh", dy: e.deltaY });
  }, { passive: false });
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());

  // ---------------------------------------------------------------- Start
  async function init() {
    $("playerName").value = storedName();
    try { $("serverMode").checked = localStorage.getItem("tiau_server_mode") === "1"; } catch (e) { /* egal */ }
    $("serverMode").addEventListener("change", (e) => {
      try { localStorage.setItem("tiau_server_mode", e.target.checked ? "1" : "0"); } catch (err) { /* egal */ }
    });
    $("playerName").addEventListener("change", (e) => storeName(e.target.value.trim()));
    try {
      const res = await fetch("/api/info", { cache: "no-store" });
      info = await res.json();
      $("emptyHint").textContent = `Leere Räume werden nach ${info.room_empty_timeout} Sekunden automatisch gelöscht.`;
    } catch (e) { /* Standardwerte behalten */ }
    const params = new URLSearchParams(location.search);
    const code = (params.get("room") || "").toUpperCase();
    if (/^[A-Z]{5}$/.test(code)) {
      $("joinCode").value = code;
      toast(`Einladung zu Raum ${code} – Namen eingeben und „Beitreten“ drücken.`);
      (storedName() ? $("joinBtn") : $("playerName")).focus();
    }
    refreshRooms();
  }
  init();
})();
