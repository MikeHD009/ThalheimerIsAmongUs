"""NEU: Browser-Modus – das Spiel laeuft als WebAssembly (pygbag) direkt auf dem Geraet des Spielers.

  Browser (main.py als WebAssembly)  <--WebSocket /ws/game-->  web_server.py  <--TCP-->  server.py

Der Server rechnet nur noch die Spiellogik (server.py wie bisher); Grafik, Bewegung, Tasks und
Animationen berechnet jedes Geraet selbst -> fluessig und unabhaengig von der Server-Leistung.

Dieses Modul hat bewusst dieselbe Schnittstelle wie web_bridge.py (set_world, present,
send_event, notify_end ...), damit main.py an diesen Stellen nicht unterscheiden muss.
Die Verbindung zu JavaScript (WebSocket, Web Audio, Video, Vollbild) steht in
web/client_template.tmpl (window.tiauNet / window.tiauGame).
"""
import base64
import json
import time

try:
    import platform as _pf
    window = _pf.window          # pygbag: Zugriff auf das JavaScript-window
except Exception:                # ausserhalb des Browsers (z.B. Syntax-Check) einfach inaktiv
    window = None

ACTIVE = False                   # kein Bild-Streaming (das ist nur im alten Server-Modus aktiv)
ROOM_CODE = ""
PLAYER_NAME = ""
PERF = False                     # /play/?...&perf=1 -> Zeitmessung pro Abschnitt in der Konsole


# ---------------------------------------------------------------- web_bridge-kompatible Schnittstelle
def set_world(*_args):
    pass


def present(*_args):
    pass


def send_event(obj):
    """Sounds, Video, Spielende ... an die Webseite (gleiche Ereignisse wie im Server-Modus)."""
    try:
        window.tiauGame.onEvent(json.dumps(obj))
    except Exception as e:
        print("BROWSER EVENT ERROR:", e)


def notify_end(reason, text=""):
    send_event({"t": "end", "reason": reason, "text": text})


def hard_exit(code=0):
    # Im Browser gibt es kein Prozessende - die Seite zeigt den Endbildschirm und bietet "Zurueck" an
    pass


def signal_ready():
    try:
        window.tiauGame.ready()
    except Exception:
        pass


_last_fps_report = 0.0


def report_fps(fps, work_ms=0.0):
    """Etwa einmal pro Sekunde Bildrate + Rechenzeit pro Frame an die Werkzeugleiste melden."""
    global _last_fps_report
    now = time.time()
    if now - _last_fps_report < 1.0:
        return
    _last_fps_report = now
    try:
        window.tiauGame.fps(int(round(fps)), round(work_ms, 1))
    except Exception:
        pass


def get_params():
    """Raum-Code und Name aus der Adresse (/play/?room=ABCDE&name=Leander)."""
    global ROOM_CODE, PLAYER_NAME, PERF
    try:
        from urllib.parse import parse_qs
        query = str(window.location.search or "")
        params = parse_qs(query[1:] if query.startswith("?") else query)
        ROOM_CODE = (params.get("room", [""])[0] or "").strip().upper()[:5]
        PLAYER_NAME = (params.get("name", [""])[0] or "").strip()[:16]
        PERF = params.get("perf", ["0"])[0] == "1"
    except Exception as e:
        print("PARAM ERROR:", e)
    return ROOM_CODE, PLAYER_NAME


# ---------------------------------------------------------------- Netzwerk
class Connection:
    """Ersatz fuer den TCP-Socket: Bytes laufen base64-kodiert ueber einen JavaScript-WebSocket.
    Pro Frame: pump() holt alles Empfangene, flush() schickt alles Gesammelte in EINER Nachricht."""

    def __init__(self):
        self.buf = bytearray()
        self.out = bytearray()
        self.name_sent = False

    def open(self, room, name):
        window.tiauNet.open(room, name)

    def state(self):
        try:
            return str(window.tiauNet.state)
        except Exception:
            return "closed"

    def close_reason(self):
        try:
            return str(window.tiauNet.closeReason or "")
        except Exception:
            return ""

    def pump(self):
        data = str(window.tiauNet.poll() or "")
        if data:
            for chunk in data.split(","):
                if chunk:
                    self.buf += base64.b64decode(chunk)

    def sendall(self, data):
        self.out += data

    def flush(self):
        if self.out:
            window.tiauNet.send(base64.b64encode(bytes(self.out)).decode("ascii"))
            self.out.clear()

    def recv(self, _n):
        return b""   # wird im Browser nicht benutzt (kein Empfangs-Thread)

    def close(self):
        try:
            window.tiauNet.close()
        except Exception:
            pass


class PacketReader:
    """Liest EIN vollstaendig empfangenes Paket - main.handle_packet() merkt keinen Unterschied
    zu einem echten Socket (recv / recv_exact / sendall)."""

    def __init__(self, data, conn):
        self.data = data
        self.pos = 0
        self.conn = conn

    def recv(self, n):
        chunk = self.data[self.pos:self.pos + n]
        self.pos += len(chunk)
        return bytes(chunk)

    def sendall(self, data):
        self.conn.sendall(data)


# Laenge jedes Server->Client-Pakets INKLUSIVE Typ-Byte (muss zu server.py passen).
_FIXED = {2: 10, 3: 2, 4: 10, 5: 3, 10: 1, 12: 2, 14: 5, 17: 4, 21: 5, 23: 1, 31: 6, 40: 3, 41: 3,
          42: 1, 43: 6, 61: 2, 64: 2, 67: 12, 69: 10, 70: 3, 74: 2, 76: 4, 78: 1, 80: 3, 82: 2}


def packet_length(buf):
    """Gesamtlaenge des ersten Pakets in buf, None wenn es noch nicht vollstaendig da ist.
    Unbekannter Typ -> ValueError (Protokollfehler)."""
    if not buf:
        return None
    t = buf[0]
    if t in _FIXED:
        n = _FIXED[t]
        return n if len(buf) >= n else None
    if t in (15, 22, 32):              # Anzahl + n IDs
        return (2 + buf[1]) if len(buf) >= 2 and len(buf) >= 2 + buf[1] else None
    if t == 83:                        # Anzahl + n * (id, team, rolle)
        return (2 + 3 * buf[1]) if len(buf) >= 2 and len(buf) >= 2 + 3 * buf[1] else None
    if t == 19:                        # Anzahl + n * (id, code)
        return (2 + 2 * buf[1]) if len(buf) >= 2 and len(buf) >= 2 + 2 * buf[1] else None
    if t == 50:                        # Absender, Laenge, Text
        return (3 + buf[2]) if len(buf) >= 3 and len(buf) >= 3 + buf[2] else None
    if t == 1:                         # Anzahl, Host, n * (id, laenge, name)
        if len(buf) < 3:
            return None
        pos = 3
        for _ in range(buf[1]):
            if len(buf) < pos + 2:
                return None
            pos += 2 + buf[pos + 1]
        return pos if len(buf) >= pos else None
    raise ValueError(f"unbekanntes Paket {t}")


# ---------------------------------------------------------------- Video (Vladimirs Intro)
class JSVideoPlayer:
    """Gleiche Schnittstelle wie main.VideoPlayer - die Webseite spielt das Video ab."""

    def __init__(self, url, max_duration):
        self.started_at = time.time()
        self.max_duration = max_duration
        self.finished = False
        self.surface = None
        # die Webseite setzt tiauGame.videoEnded beim Start selbst auf false
        send_event({"t": "video", "on": True, "src": url})

    @property
    def active(self):
        return not self.finished

    def update(self):
        if self.finished:
            return
        ended = False
        try:
            ended = bool(window.tiauGame.videoEnded)
        except Exception:
            ended = True
        if ended or time.time() - self.started_at > self.max_duration:
            self.close()

    def draw(self, target):
        target.fill((0, 0, 0))

    def close(self):
        if not self.finished:
            self.finished = True
            send_event({"t": "video", "on": False})
