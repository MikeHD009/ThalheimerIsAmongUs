"""NEU: Web-Session-Modus fuer main.py ("Cloud-Gaming" im WLAN).

Im Web-Betrieb laeuft main.py NICHT beim Spieler, sondern als eigener Prozess pro Spieler auf
dem Server (gestartet von web_server.py):

    Browser  <--WebSocket-->  web_server.py  <--stdin/stdout-->  main.py --web-session
                                                                     |
                                                                     +--TCP-->  server.py (Raum)

  * Eingaben (Tasten/Maus) kommen als JSON-Zeilen ueber stdin und werden in ganz normale
    pygame-Events uebersetzt. main.py und tasks.py merken davon nichts.
  * Das fertig gezeichnete Bild wird als JPEG ueber stdout zurueckgeschickt
    (Format: 1 Byte Typ, 4 Byte Laenge, Nutzdaten). Typ 1 = Bild, Typ 2 = JSON-Ereignis
    (Sounds, Video, Spielende ...).
  * print()-Ausgaben landen auf stderr, damit sie den Bild-Datenstrom nicht stoeren.

Ohne das Argument --web-session ist dieses Modul komplett inaktiv (lokales Spielen wie bisher).
"""
import io
import json
import os
import struct
import sys
import threading
import time
from collections import deque

ACTIVE = False
WIDTH, HEIGHT = 1440, 810
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555
PLAYER_NAME = ""
ROOM_CODE = ""
JPEG_QUALITY = 72
MAX_FPS = 30

MSG_FRAME = 1
MSG_EVENT = 2

_out = None
_out_lock = threading.Lock()
_events = deque()
_pressed = {}               # KeyboardEvent.code -> pygame-Keycode
_pressed_keys = set()
_mouse_pos = [0, 0]
_mouse_buttons = [False, False, False]
_video_ended = threading.Event()
_quit_requested = threading.Event()

_frame_lock = threading.Lock()
_frame_ready = threading.Event()
_pending_raw = None
_encoder_busy = False
_last_capture = 0.0
_encode_times = deque(maxlen=120)


def _parse_args(argv):
    global WIDTH, HEIGHT, SERVER_HOST, SERVER_PORT, PLAYER_NAME, ROOM_CODE, JPEG_QUALITY, MAX_FPS
    global WORLD_JPEG_QUALITY
    args = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--") and "=" in a:
            # --name=... (sicher auch fuer Namen, die mit "--" beginnen)
            key, _, value = a[2:].partition("=")
            args[key] = value
            i += 1
        elif a.startswith("--") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            args[a[2:]] = argv[i + 1]
            i += 2
        else:
            args[a[2:] if a.startswith("--") else a] = True
            i += 1
    if "server" in args:
        host, _, port = str(args["server"]).rpartition(":")
        SERVER_HOST = host or "127.0.0.1"
        SERVER_PORT = int(port)
    PLAYER_NAME = str(args.get("name", "")).strip()[:16]
    ROOM_CODE = str(args.get("room", ""))
    if "size" in args:
        w, h = str(args["size"]).lower().split("x")
        WIDTH, HEIGHT = int(w), int(h)
    JPEG_QUALITY = int(args.get("quality", JPEG_QUALITY))
    MAX_FPS = max(5, min(60, int(args.get("fps", MAX_FPS))))
    WORLD_JPEG_QUALITY = max(30, min(95, int(args.get("world-quality", WORLD_JPEG_QUALITY))))


def init_from_argv(argv=None):
    """Muss VOR pygame.init() aufgerufen werden. Gibt True zurueck, wenn der Web-Modus aktiv ist."""
    global ACTIVE, _out
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--web-session" not in argv:
        return False
    ACTIVE = True
    _parse_args(argv)

    # Kein Fenster, keine Soundkarte - alles passiert im Speicher
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    # numpy wird nur fuer einfache Bildvergleiche gebraucht - ohne diese Begrenzung legt OpenBLAS
    # pro Spieler einen Thread-Pool fuer ALLE Kerne an (gemessen: 635 MB statt 124 MB reserviert)
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")

    # stdout gehoert ab jetzt exklusiv dem Bild-/Ereignis-Strom; print() geht nach stderr
    _out = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    _install_pygame_patches()
    threading.Thread(target=_stdin_reader, daemon=True).start()
    threading.Thread(target=_encoder_loop, daemon=True).start()
    return True


# =========================
# AUSGABE (Bilder + Ereignisse)
# =========================
def _write_msg(msg_type, payload):
    if _out is None:
        return
    try:
        with _out_lock:
            _out.write(struct.pack("!BI", msg_type, len(payload)) + payload)
    except (BrokenPipeError, OSError, ValueError):
        _quit_requested.set()


def send_event(obj):
    if ACTIVE:
        _write_msg(MSG_EVENT, json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def notify_end(reason, text=""):
    send_event({"t": "end", "reason": reason, "text": text})


def set_world(world_surface, scaled_surface, rect):
    """Von main.py aufgerufen, nachdem die Spielwelt (360x360-Pixelgrafik inkl. Nebel) skaliert
    auf den Bildschirm geblittet wurde. Die Welt wird dann in Originalgroesse verschickt und erst
    im Browser pixelgenau hochskaliert - das spart etwa 2/3 der Datenmenge."""
    global _world_info
    if ACTIVE:
        _world_info = (world_surface, scaled_surface, rect)


_world_info = None
_credits = 2                 # so viele Bilder duerfen unbestaetigt unterwegs sein (Flusskontrolle)
_force_full = threading.Event()


def present(surface):
    """Am Ende jedes Frames aufrufen. Nimmt hoechstens MAX_FPS Bilder pro Sekunde auf. Ist der
    Browser mit dem Anzeigen noch nicht fertig (keine Bestaetigung), wird das Bild ausgelassen
    statt Verzoegerung aufzubauen - dadurch bleibt das Spiel auch bei schwachem WLAN direkt."""
    global _last_capture, _pending_raw, _world_info
    if not ACTIVE:
        return
    world_info = _world_info
    _world_info = None
    now = time.perf_counter()
    if now - _last_capture < 1.0 / MAX_FPS - 0.004:   # kleine Toleranz gegen Takt-Schwankungen
        return
    with _frame_lock:
        if _encoder_busy or _pending_raw is not None or _credits <= 0:
            return
    import pygame
    _last_capture = now
    screen_raw = pygame.image.tobytes(surface, "RGBX")
    world = None
    if world_info is not None:
        w_surf, s_surf, rect = world_info
        try:
            world = (pygame.image.tobytes(w_surf, "RGBX"), w_surf.get_size(),
                     pygame.image.tobytes(s_surf, "RGBX"), tuple(int(v) for v in rect))
        except Exception:
            world = None
    with _frame_lock:
        _pending_raw = (screen_raw, world)
    _frame_ready.set()


class _FrameEncoder:
    """Schickt nur, was sich geaendert hat:
       * Spielwelt: 360x360-JPEG (der Browser skaliert pixelgenau hoch)
       * Texte/Knoepfe ueber der Welt: kleine PNG-Streifen mit Transparenz
       * Rest (Seitenleisten, Menues, Meetings, Tasks): nur die geaenderten Rechtecke als JPEG
    Frame-Format (nach dem Typ-Byte/Laenge):
       u8 flags (1 = Welt aktiv, 2 = Weltbild dabei, 4 = Overlay-Liste dabei)
       [flags&1] u16 x, u16 y, u16 groesse
       [flags&2] u32 len, JPEG
       [flags&4] u8 n, n x (u16 x, u16 y, u32 len, PNG)
       u8 n, n x (u16 x, u16 y, u32 len, JPEG)   -> Flicken fuer das Grundbild"""

    OVERLAY_MAX_FRACTION = 0.22   # mehr Deckung ueber der Welt -> normales Vollbild-Verfahren
    MASK = 0x00FFFFFF            # RGBX: das Fuellbyte ignorieren
    ALIGN = 16                   # JPEG-Bloecke (4:2:0) liegen dann exakt auf dem Raster

    def __init__(self):
        import numpy as np
        from PIL import Image
        self.np = np
        self.Image = Image
        self.sent = None
        self.last_world = None
        self.last_overlay_sig = None
        self.world_was_active = False
        self.bytes_sent = 0

    def reset(self):
        self.sent = None
        self.last_world = None
        self.last_overlay_sig = None

    def _jpeg(self, rgb_array, quality, subsampling=2):
        buf = io.BytesIO()
        self.Image.fromarray(rgb_array).save(buf, "JPEG", quality=quality, subsampling=subsampling)
        return buf.getvalue()

    def _rgb(self, u32_block):
        np = self.np
        return np.ascontiguousarray(u32_block.view(np.uint8).reshape(u32_block.shape[0], u32_block.shape[1], 4)[:, :, :3])

    @staticmethod
    def _bands(mask, np, max_gap=24):
        rows = np.flatnonzero(mask.any(axis=1))
        if rows.size == 0:
            return []
        rects = []
        start = prev = int(rows[0])
        for r in rows[1:]:
            r = int(r)
            if r - prev > max_gap:
                rects.append((start, prev + 1))
                start = r
            prev = r
        rects.append((start, prev + 1))
        out = []
        for r0, r1 in rects:
            cols = np.flatnonzero(mask[r0:r1].any(axis=0))
            out.append((int(cols[0]), r0, int(cols[-1]) + 1, r1))
        return out

    def encode(self, screen_raw, world):
        np = self.np
        scr = np.frombuffer(screen_raw, dtype=np.uint32).reshape(HEIGHT, WIDTH) & self.MASK
        if self.sent is None:
            self.sent = np.zeros((HEIGHT, WIDTH), dtype=np.uint32)
            self.last_world = None
            self.last_overlay_sig = None

        world_mode = False
        flags = 0
        parts = []
        if world is not None:
            w_raw, w_size, s_raw, (wx, wy, ws) = world
            if (0 <= wx and 0 <= wy and wx + ws <= WIDTH and wy + ws <= HEIGHT
                    and len(s_raw) == ws * ws * 4):
                scaled = np.frombuffer(s_raw, dtype=np.uint32).reshape(ws, ws) & self.MASK
                square = scr[wy:wy + ws, wx:wx + ws]
                omask = square != scaled
                if omask.mean() < self.OVERLAY_MAX_FRACTION:
                    world_mode = True

        if world_mode:
            flags |= 1
            parts.append(struct.pack("!HHH", wx, wy, ws))
            base = scr.copy()
            base[wy:wy + ws, wx:wx + ws] = 0
            world_changed = (w_raw != self.last_world)
            if world_changed:
                flags |= 2
                self.last_world = w_raw
                w_arr = np.frombuffer(w_raw, dtype=np.uint32).reshape(w_size[1], w_size[0])
                jpg = self._jpeg(self._rgb(w_arr), WORLD_JPEG_QUALITY, WORLD_SUBSAMPLING)
                parts.append(struct.pack("!I", len(jpg)) + jpg)
            # Overlays: alles, was ueber der Welt gezeichnet wurde (Namen, Banner, Buttons ...)
            overlays = []
            for x0, y0, x1, y1 in self._bands(omask, np):
                block = square[y0:y1, x0:x1]
                rgba = block.view(np.uint8).reshape(y1 - y0, x1 - x0, 4).copy()
                rgba[:, :, 3] = omask[y0:y1, x0:x1] * 255
                overlays.append((wx + x0, wy + y0, rgba))
            sig = hash(tuple((ox, oy, o.tobytes()) for ox, oy, o in overlays))
            if world_changed or sig != self.last_overlay_sig or not self.world_was_active:
                flags |= 4
                self.last_overlay_sig = sig
                chunk = struct.pack("!B", min(255, len(overlays)))
                for ox, oy, rgba in overlays[:255]:
                    buf = io.BytesIO()
                    self.Image.fromarray(rgba).save(buf, "PNG", compress_level=1)
                    png = buf.getvalue()
                    chunk += struct.pack("!HHI", ox, oy, len(png)) + png
                parts.append(chunk)
        else:
            base = scr
            self.last_world = None
            self.last_overlay_sig = None

        # Grundbild: nur geaenderte Rechtecke schicken (pro Bildschirm-Drittel bzw. Seitenleiste)
        diff = base != self.sent
        if world_mode:
            columns = [(0, wx), (wx, wx + ws), (wx + ws, WIDTH)]
        else:
            third = (WIDTH // 3) // self.ALIGN * self.ALIGN
            columns = [(0, third), (third, 2 * third), (2 * third, WIDTH)]
        rects = []
        for c0, c1 in columns:
            if c1 <= c0:
                continue
            for x0, y0, x1, y1 in self._bands(diff[:, c0:c1], np, max_gap=32):
                a = self.ALIGN
                rects.append((max(0, (c0 + x0) // a * a), max(0, y0 // a * a),
                              min(WIDTH, -(-(c0 + x1) // a) * a), min(HEIGHT, -(-y1 // a) * a)))
        area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in rects)
        if area > 0.6 * WIDTH * HEIGHT:
            rects = [(0, 0, WIDTH, HEIGHT)]
        patch_chunk = struct.pack("!B", len(rects))
        for x0, y0, x1, y1 in rects:
            jpg = self._jpeg(self._rgb(base[y0:y1, x0:x1]), JPEG_QUALITY)
            patch_chunk += struct.pack("!HHI", x0, y0, len(jpg)) + jpg
            self.sent[y0:y1, x0:x1] = base[y0:y1, x0:x1]
        parts.append(patch_chunk)

        changed = bool(rects) or (flags & 6) or (world_mode != self.world_was_active)
        self.world_was_active = world_mode
        if not changed:
            return None
        payload = struct.pack("!B", flags) + b"".join(parts)
        self.bytes_sent += len(payload)
        return payload


WORLD_JPEG_QUALITY = 78      # getestet: optisch wie das Original, ~30 KB pro Weltbild
WORLD_SUBSAMPLING = 0        # 4:4:4 - 4:2:0 verschmiert die kleinen Figuren sichtbar


def _encoder_loop():
    global _pending_raw, _encoder_busy, _credits
    try:
        encoder = _FrameEncoder()
    except Exception as e:
        print("WEB-BRIDGE: numpy/Pillow fehlen -", e, file=sys.stderr)
        _quit_requested.set()
        return
    stats_t = time.time()
    stats_cpu = time.process_time()
    while not _quit_requested.is_set():
        _frame_ready.wait(0.5)
        _frame_ready.clear()
        if _force_full.is_set():
            _force_full.clear()
            encoder.reset()
        with _frame_lock:
            job = _pending_raw
            _pending_raw = None
            if job is None:
                continue
            _encoder_busy = True
        try:
            t0 = time.perf_counter()
            payload = encoder.encode(*job)
            _encode_times.append(time.perf_counter() - t0)
            if payload is not None:
                with _frame_lock:
                    _credits -= 1
                _write_msg(MSG_FRAME, payload)
        except Exception as e:
            print("WEB-BRIDGE ENCODE ERROR:", e, file=sys.stderr)
            encoder.reset()
        finally:
            with _frame_lock:
                _encoder_busy = False
        if os.environ.get("WEB_BRIDGE_STATS") and time.time() - stats_t > 10:
            dt = time.time() - stats_t
            cpu = (time.process_time() - stats_cpu) / dt * 100
            print(f"[BRIDGE {ROOM_CODE} {PLAYER_NAME}] {encoder.bytes_sent * 8 / dt / 1e6:.2f} Mbit/s, "
                  f"encode {average_encode_ms():.1f} ms, CPU {cpu:.0f}% eines Kerns", file=sys.stderr, flush=True)
            encoder.bytes_sent = 0
            stats_t = time.time()
            stats_cpu = time.process_time()


def average_encode_ms():
    if not _encode_times:
        return 0.0
    return 1000.0 * sum(_encode_times) / len(_encode_times)


# =========================
# EINGABE (Browser -> pygame-Events)
# =========================
def _key_tables():
    import pygame
    special = {
        "Enter": pygame.K_RETURN, "Backspace": pygame.K_BACKSPACE, "Tab": pygame.K_TAB,
        "Escape": pygame.K_ESCAPE, " ": pygame.K_SPACE, "Spacebar": pygame.K_SPACE,
        "ArrowUp": pygame.K_UP, "ArrowDown": pygame.K_DOWN,
        "ArrowLeft": pygame.K_LEFT, "ArrowRight": pygame.K_RIGHT,
        "Delete": pygame.K_DELETE, "Home": pygame.K_HOME, "End": pygame.K_END,
        "Shift": pygame.K_LSHIFT, "Control": pygame.K_LCTRL, "Alt": pygame.K_LALT,
        "AltGraph": pygame.K_RALT, "Meta": pygame.K_LMETA, "CapsLock": pygame.K_CAPSLOCK,
    }
    for n in range(1, 13):
        special[f"F{n}"] = getattr(pygame, f"K_F{n}")
    uni = {"Enter": "\r", "Backspace": "\b", "Tab": "\t", " ": " ", "Spacebar": " ", "Escape": "\x1b"}
    return special, uni


_SPECIAL = None
_UNICODE = None


def _translate_key(key_name):
    """Browser-KeyboardEvent.key -> (pygame-Keycode, unicode)."""
    if key_name in _SPECIAL:
        return _SPECIAL[key_name], _UNICODE.get(key_name, "")
    if len(key_name) == 1:
        # SDL-Keycodes fuer druckbare Zeichen entsprechen ihrem (kleingeschriebenen) Unicode-Wert
        return ord(key_name.lower()), key_name
    return 0, ""


def _current_mods():
    import pygame
    mods = 0
    if pygame.K_LSHIFT in _pressed_keys: mods |= pygame.KMOD_LSHIFT
    if pygame.K_LCTRL in _pressed_keys: mods |= pygame.KMOD_LCTRL
    if pygame.K_LALT in _pressed_keys: mods |= pygame.KMOD_LALT
    return mods


def _handle_input(msg):
    global _credits
    import pygame
    t = msg.get("t")
    if t == "kd":
        code = str(msg.get("c", ""))
        key, uni = _translate_key(str(msg.get("k", "")))
        if key == 0:
            return
        if msg.get("ctrl") or msg.get("alt"):
            uni = ""
        _pressed[code or str(key)] = key
        _pressed_keys.add(key)
        _events.append(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=uni, mod=_current_mods(), scancode=0))
    elif t == "ku":
        code = str(msg.get("c", ""))
        key = _pressed.pop(code, None)
        if key is None:
            key, _uni = _translate_key(str(msg.get("k", "")))
        _pressed_keys.discard(key)
        if key:
            _events.append(pygame.event.Event(pygame.KEYUP, key=key, unicode="", mod=_current_mods(), scancode=0))
    elif t in ("md", "mu", "mm"):
        x = max(0, min(WIDTH - 1, int(msg.get("x", 0))))
        y = max(0, min(HEIGHT - 1, int(msg.get("y", 0))))
        rel = (x - _mouse_pos[0], y - _mouse_pos[1])
        _mouse_pos[0], _mouse_pos[1] = x, y
        if t == "mm":
            _events.append(pygame.event.Event(pygame.MOUSEMOTION, pos=(x, y), rel=rel,
                                              buttons=tuple(int(b) for b in _mouse_buttons), touch=False))
            return
        button = {0: 1, 1: 2, 2: 3}.get(int(msg.get("b", 0)), 1)
        _mouse_buttons[button - 1] = (t == "md")
        etype = pygame.MOUSEBUTTONDOWN if t == "md" else pygame.MOUSEBUTTONUP
        _events.append(pygame.event.Event(etype, pos=(x, y), button=button, touch=False))
    elif t == "wh":
        dy = float(msg.get("dy", 0))
        if dy == 0:
            return
        step = -1 if dy > 0 else 1
        _events.append(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=step, flipped=False,
                                          precise_x=0.0, precise_y=float(step), touch=False))
        button = 4 if step > 0 else 5
        pos = tuple(_mouse_pos)
        _events.append(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button, touch=False))
        _events.append(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button, touch=False))
    elif t == "blur":
        # Fenster hat den Fokus verloren -> alle Tasten loslassen (sonst "klebt" z.B. W)
        for code, key in list(_pressed.items()):
            _events.append(pygame.event.Event(pygame.KEYUP, key=key, unicode="", mod=0, scancode=0))
        _pressed.clear()
        _pressed_keys.clear()
        for i in range(3):
            _mouse_buttons[i] = False
    elif t == "video_end":
        _video_ended.set()
    elif t == "ack":
        with _frame_lock:
            _credits = min(2, _credits + 1)
        _frame_ready.set()
    elif t == "refresh":
        # Browser hat seinen Bildzustand verloren (z.B. Fehler beim Dekodieren) -> alles neu
        with _frame_lock:
            _credits = 2
        _force_full.set()


def _stdin_reader():
    import pygame
    stream = sys.stdin.buffer
    while True:
        try:
            line = stream.readline()
        except Exception:
            line = b""
        if not line:
            break  # Webserver hat die Verbindung beendet (Browser zu) -> Spiel beenden
        try:
            _handle_input(json.loads(line))
        except Exception as e:
            print("WEB-BRIDGE INPUT ERROR:", e, file=sys.stderr)
    _quit_requested.set()
    _events.append(pygame.event.Event(pygame.QUIT))


class _KeyState:
    """Ersatz fuer pygame.key.get_pressed(): keys[pygame.K_w] funktioniert wie gewohnt."""
    __slots__ = ("_keys",)

    def __init__(self, keys):
        self._keys = keys

    def __getitem__(self, key):
        return key in self._keys

    def __len__(self):
        return 512


def _install_pygame_patches():
    global _SPECIAL, _UNICODE
    import pygame
    _SPECIAL, _UNICODE = _key_tables()

    original_get = pygame.event.get

    def event_get(*_args, **_kwargs):
        try:
            original_get()  # interne SDL-Warteschlange leeren (Dummy-Treiber)
        except Exception:
            pass
        out = []
        while _events:
            out.append(_events.popleft())
        return out

    def event_post(event):
        _events.append(event)
        return True

    pygame.event.get = event_get
    pygame.event.post = event_post
    pygame.key.get_pressed = lambda: _KeyState(frozenset(_pressed_keys))
    pygame.key.get_mods = _current_mods
    pygame.mouse.get_pos = lambda: (_mouse_pos[0], _mouse_pos[1])
    pygame.mouse.get_pressed = lambda num_buttons=3: tuple(_mouse_buttons[:3]) + ((False, False) if num_buttons == 5 else ())
    pygame.mouse.set_visible = lambda *_a, **_k: True

    # Linux-Server haben kein Arial -> mitgelieferte Liberation Sans (gleiche Zeichenbreiten), siehe fonts.py
    import fonts
    fonts.install(pygame)


def quit_requested():
    return _quit_requested.is_set()


def hard_exit(code=0):
    """Sitzung sofort beenden. Ein normales sys.exit() kann haengen bzw. mit
    "could not acquire lock for <stdin>" abbrechen, weil der Eingabe-Thread noch auf stdin wartet."""
    _quit_requested.set()
    try:
        with _out_lock:
            if _out is not None:
                _out.flush()
    except Exception:
        pass
    try:
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(code)


# =========================
# VIDEO (Vladimirs Anime-Intro laeuft im Browser)
# =========================
class RemoteVideoPlayer:
    """Gleiche Schnittstelle wie main.VideoPlayer - das Video spielt aber der Browser des
    Spielers ab (mit Ton). Fertig ist es, wenn der Browser 'video_end' meldet oder die
    Sicherheits-Hoechstdauer abgelaufen ist."""

    def __init__(self, url, max_duration):
        _video_ended.clear()
        self.started_at = time.time()
        self.max_duration = max_duration
        self.finished = False
        self.surface = None
        send_event({"t": "video", "on": True, "src": url})

    @property
    def active(self):
        return not self.finished

    def update(self):
        if self.finished:
            return
        if _video_ended.is_set() or time.time() - self.started_at > self.max_duration:
            self.close()

    def draw(self, target):
        target.fill((0, 0, 0))

    def close(self):
        if not self.finished:
            self.finished = True
            send_event({"t": "video", "on": False})
