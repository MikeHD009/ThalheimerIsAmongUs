/* Thalheimer is Among Us - Soundeffekte im Browser (Web Audio).
 * Gemeinsam genutzt von der Raumliste (app.js, Server-Modus) und der Spielseite (game_glue.js).
 * Das Spiel schickt nur Ereignisse wie {"t":"sfx","n":"kill"}; die MP3s liegen unter /sounds/.
 */
(function () {
  "use strict";

  class TiauAudio {
    constructor() {
      this.ctx = null;
      this.master = null;
      this.sounds = {};      // name -> {file, volume}
      this.buffers = {};
      this.loops = {};
      this.music = null;
      this.musicGain = null;
      this.wantMusic = 0;
      this.muted = false;
    }

    configure(sounds) {
      this.sounds = sounds || {};
      if (this.ctx) this._loadAll();
    }

    /** Muss aus einer Nutzer-Aktion (Klick/Taste) heraus aufgerufen werden (Autoplay-Regeln). */
    unlock() {
      if (this.ctx) {
        if (this.ctx.state === "suspended") this.ctx.resume();
        return;
      }
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.muted ? 0 : 1;
      this.master.connect(this.ctx.destination);
      this._loadAll();
    }

    _loadAll() {
      for (const [name, s] of Object.entries(this.sounds)) {
        if (this.buffers[name]) continue;
        fetch("/sounds/" + encodeURIComponent(s.file))
          .then((r) => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); })
          .then((b) => new Promise((ok, err) => this.ctx.decodeAudioData(b, ok, err)))
          .then((buf) => {
            this.buffers[name] = buf;
            if (name === "music" && this.wantMusic > 0) this.setMusic(this.wantMusic, true);
            if (this.loops[name] === "pending") this.setLoop(name, true);
          })
          .catch(() => {});
      }
    }

    volumeOf(name) { return (this.sounds[name] && this.sounds[name].volume) || 0.8; }

    play(name) {
      const buf = this.buffers[name];
      if (!this.ctx || !buf) return;
      const src = this.ctx.createBufferSource();
      const g = this.ctx.createGain();
      g.gain.value = this.volumeOf(name);
      src.buffer = buf;
      src.connect(g).connect(this.master);
      src.start();
    }

    setLoop(name, on) {
      const cur = this.loops[name];
      if (on) {
        if (cur && cur !== "pending") return;
        const buf = this.buffers[name];
        if (!this.ctx || !buf) { this.loops[name] = "pending"; return; }
        const src = this.ctx.createBufferSource();
        const g = this.ctx.createGain();
        g.gain.value = this.volumeOf(name);
        src.buffer = buf;
        src.loop = true;
        src.connect(g).connect(this.master);
        src.start();
        this.loops[name] = src;
      } else {
        if (cur && cur !== "pending") { try { cur.stop(); } catch (e) { /* schon gestoppt */ } }
        delete this.loops[name];
      }
    }

    setMusic(factor, force) {
      this.wantMusic = factor;
      if (!this.ctx) return;
      const buf = this.buffers.music;
      if (!buf) return;
      const target = this.volumeOf("music") * factor;
      if (!this.music && factor > 0) {
        this.musicGain = this.ctx.createGain();
        this.musicGain.gain.value = 0;
        this.music = this.ctx.createBufferSource();
        this.music.buffer = buf;
        this.music.loop = true;
        this.music.connect(this.musicGain).connect(this.master);
        this.music.start();
      }
      if (this.musicGain) {
        const now = this.ctx.currentTime;
        this.musicGain.gain.cancelScheduledValues(now);
        this.musicGain.gain.setValueAtTime(this.musicGain.gain.value, now);
        this.musicGain.gain.linearRampToValueAtTime(target, now + (force ? 0.4 : 0.8));
      }
    }

    stopAll() {
      for (const n of Object.keys(this.loops)) this.setLoop(n, false);
      if (this.music) { try { this.music.stop(); } catch (e) { /* ok */ } }
      this.music = null;
      this.musicGain = null;
    }

    setMuted(muted) {
      this.muted = muted;
      if (this.master) this.master.gain.value = muted ? 0 : 1;
    }

    /** Ereignis aus dem Spiel verarbeiten. Gibt true zurueck, wenn es ein Sound-Ereignis war. */
    handle(ev) {
      switch (ev.t) {
        case "sfx": this.play(ev.n); return true;
        case "loop": this.setLoop(ev.n, !!ev.on); return true;
        case "music": this.setMusic(ev.v || 0); return true;
      }
      return false;
    }
  }

  window.TiauAudio = TiauAudio;
})();
