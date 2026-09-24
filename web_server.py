"""NEU: Web-Server fuer Thalheimer is Among Us (laeuft im Container auf dem Ubuntu-Server).

Aufgaben:
  * liefert die Webseite aus (Raumliste, Beitreten per Code, Raum erstellen)
  * verwaltet die Raeume: jeder Raum ist ein eigener server.py-Prozess auf einem internen Port
  * STANDARD (Browser-Modus): /play/ liefert das Spiel als WebAssembly aus (tools/build_web_client.py);
    es laeuft auf dem Geraet des Spielers. /ws/game reicht nur die kleinen Spielpakete zwischen
    Browser und Raum-Server durch -> kaum Serverlast, fluessig.
  * Kompatibilitaets-Modus (/ws): startet pro Spieler "main.py --web-session" auf dem Server und
    streamt das Bild (fuer sehr schwache Geraete; braucht viel Server-Leistung)
  * loescht Raeume, in denen 10 Sekunden lang niemand ist (Spam-Schutz)

Start:  python web_server.py            (Port ueber Umgebungsvariable PORT, Standard 8080)
"""
import asyncio
import json
import mimetypes
import os
import random
import re
import socket
import struct
import sys
import time

from aiohttp import web, WSMsgType

import sound

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
CLIENT_DIR = os.path.join(WEB_DIR, "client")     # von tools/build_web_client.py erzeugt
CDN_DIR = os.path.join(WEB_DIR, "cdn")           # gespiegelte WebAssembly-Laufzeit (Python + pygame)
mimetypes.add_type("application/wasm", ".wasm")  # sonst kann der Browser WebAssembly nicht direkt kompilieren
SOUND_DIR = os.path.join(BASE_DIR, "Assets", "Sounds")
VIDEO_FILE = os.path.join(BASE_DIR, "Assets", "OshiNoKoIntro.m4v")
PYTHON = sys.executable


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


HTTP_PORT = env_int("PORT", 8080)
PUBLIC_PORT = env_int("PUBLIC_PORT", HTTP_PORT)      # Port, den die Spieler im Link sehen
GAME_RESOLUTION = os.environ.get("GAME_RESOLUTION", "1440x810")
JPEG_QUALITY = env_int("JPEG_QUALITY", 72)       # Menues/Seitenleisten/Meeting
WORLD_QUALITY = env_int("WORLD_QUALITY", 78)     # Spielwelt (wird im Browser pixelgenau vergroessert)
MAX_FPS = env_int("MAX_FPS", 30)                 # bei schwachem WLAN z.B. 20
ROOM_EMPTY_TIMEOUT = env_int("ROOM_EMPTY_TIMEOUT", 10)   # laut Vorgabe: 10s leer -> Raum weg
MAX_ROOMS = env_int("MAX_ROOMS", 12)
MAX_ROOMS_PER_IP = env_int("MAX_ROOMS_PER_IP", 3)
CREATE_COOLDOWN = env_int("CREATE_COOLDOWN", 3)            # Sekunden zwischen zwei Raeumen pro Geraet
MAX_SESSIONS = env_int("MAX_SESSIONS", 60)
MAX_PLAYERS_PER_ROOM = 15
ROOM_PORT_START = env_int("ROOM_PORT_START", 6100)
ROOM_PORT_END = env_int("ROOM_PORT_END", 6199)

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # ohne I/O -> keine Verwechslung mit 1/0
CODE_LENGTH = 5
CODE_RE = re.compile(r"^[A-Z]{%d}$" % CODE_LENGTH)


def log(*args):
    print("[WEB]", *args, flush=True)


def safe_print(text):
    try:
        print(text, flush=True)
    except Exception:
        pass


def clean_text(value, max_len):
    """Steuerzeichen raus, Leerzeichen zusammenfassen, Laenge begrenzen."""
    value = "".join(ch for ch in str(value or "") if ch.isprintable())
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len]


def child_env():
    """Umgebung fuer Raum-/Spielprozesse: Ausgaben immer UTF-8 (unter Windows sonst cp1252 ->
    Namen mit Emojis/Sonderzeichen wuerden beim print() abstuerzen)."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    env["PYTHONWARNINGS"] = "ignore:pkg_resources is deprecated"
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        env.setdefault(var, "1")   # spart ~500 MB reservierten Speicher pro Spieler
    return env


def lan_addresses():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]


# =========================
# RAEUME
# =========================
class Room:
    def __init__(self, code, name, port, creator_ip):
        self.code = code
        self.name = name
        self.port = port
        self.creator_ip = creator_ip
        self.created = time.time()
        self.empty_since = time.time()
        self.sessions = set()
        self.process = None
        self.status = {"players": 0, "game_active": False, "host": ""}
        self.closed = False

    def public(self):
        return {
            "code": self.code,
            "name": self.name,
            "players": len(self.sessions),
            "max": MAX_PLAYERS_PER_ROOM,
            "game_active": bool(self.status.get("game_active")),
            "host": self.status.get("host", ""),
            "age": int(time.time() - self.created),
        }


class RoomManager:
    def __init__(self):
        self.rooms = {}
        self.last_create_by_ip = {}
        self.lock = asyncio.Lock()

    def session_count(self):
        return sum(len(r.sessions) for r in self.rooms.values())

    def _new_code(self):
        for _ in range(1000):
            code = "".join(random.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.rooms:
                return code
        raise RuntimeError("Kein freier Raumcode")

    def _free_port(self):
        used = {r.port for r in self.rooms.values()}
        for port in range(ROOM_PORT_START, ROOM_PORT_END + 1):
            if port in used:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        return None

    async def create(self, name, creator_ip):
        async with self.lock:
            if len(self.rooms) >= MAX_ROOMS:
                raise web.HTTPTooManyRequests(text="Zu viele Räume auf dem Server - tritt einem bestehenden bei.")
            own = sum(1 for r in self.rooms.values() if r.creator_ip == creator_ip)
            if own >= MAX_ROOMS_PER_IP:
                raise web.HTTPTooManyRequests(text=f"Du hast schon {own} Räume offen.")
            last = self.last_create_by_ip.get(creator_ip, 0)
            if time.time() - last < CREATE_COOLDOWN:
                raise web.HTTPTooManyRequests(text="Bitte kurz warten, bevor du noch einen Raum erstellst.")
            port = self._free_port()
            if port is None:
                raise web.HTTPServiceUnavailable(text="Kein freier Port für einen neuen Raum.")
            code = self._new_code()
            room = Room(code, name or f"Raum {code}", port, creator_ip)
            self.rooms[code] = room
            self.last_create_by_ip[creator_ip] = time.time()

        room.process = await asyncio.create_subprocess_exec(
            PYTHON, "-u", os.path.join(BASE_DIR, "server.py"),
            "--host", "127.0.0.1", "--port", str(port), "--room", code,
            cwd=BASE_DIR, env=child_env(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        asyncio.create_task(self._read_room_output(room))

        # Warten, bis der Raum-Server Verbindungen annimmt
        for _ in range(50):
            if room.process.returncode is not None:
                break
            try:
                _r, w = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 0.3)
                w.close()
                # Die Test-Verbindung schickt keinen Namen -> der Server verwirft sie nach dem Timeout
                break
            except Exception:
                await asyncio.sleep(0.1)
        if room.process.returncode is not None:
            await self.close(room, "Raum-Server konnte nicht starten")
            raise web.HTTPInternalServerError(text="Raum konnte nicht gestartet werden.")
        room.empty_since = time.time()
        log(f"Raum {code} erstellt ('{room.name}', Port {port}) von {creator_ip}")
        return room

    async def _read_room_output(self, room):
        try:
            while True:
                line = await room.process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text.startswith("@@STATUS "):
                    try:
                        room.status.update(json.loads(text[9:]))
                    except Exception:
                        pass
                elif text:
                    safe_print(text)
        except Exception as e:
            log(f"Ausgabe von Raum {room.code} nicht mehr lesbar: {e}")

    async def close(self, room, reason=""):
        if room.closed:
            return
        room.closed = True
        self.rooms.pop(room.code, None)
        for sess in list(room.sessions):
            await sess.stop(f"Der Raum wurde geschlossen. {reason}".strip())
        proc = room.process
        if proc is not None and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 3)
            except asyncio.TimeoutError:
                proc.kill()
        log(f"Raum {room.code} geschlossen ({reason or 'leer'})")

    async def janitor(self):
        """Loescht Raeume, die ROOM_EMPTY_TIMEOUT Sekunden leer sind oder deren Prozess abgestuerzt ist."""
        while True:
            await asyncio.sleep(1)
            now = time.time()
            for room in list(self.rooms.values()):
                if room.process is not None and room.process.returncode is not None:
                    await self.close(room, "Raum-Server beendet")
                elif not room.sessions:
                    if room.empty_since is None:
                        room.empty_since = now
                    elif now - room.empty_since >= ROOM_EMPTY_TIMEOUT:
                        await self.close(room, f"{ROOM_EMPTY_TIMEOUT}s leer")


manager = RoomManager()


# =========================
# SPIELER-SITZUNG (Browser <-> main.py --web-session)
# =========================
class Session:
    def __init__(self, room, name, ws, remote):
        self.room = room
        self.name = name
        self.ws = ws
        self.remote = remote
        self.process = None
        self.stopped = False

    async def start(self):
        args = [PYTHON, os.path.join(BASE_DIR, "main.py"), "--web-session",
                "--server", f"127.0.0.1:{self.room.port}", f"--name={self.name}", "--room", self.room.code,
                "--size", GAME_RESOLUTION, "--quality", str(JPEG_QUALITY), "--fps", str(MAX_FPS),
                "--world-quality", str(WORLD_QUALITY)]
        self.process = await asyncio.create_subprocess_exec(
            *args, cwd=BASE_DIR, env=child_env(),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    async def pump_output(self):
        """Bilder/Ereignisse des Spielprozesses an den Browser weiterreichen (Reihenfolge bleibt)."""
        out = self.process.stdout
        try:
            while True:
                header = await out.readexactly(5)
                msg_type, length = struct.unpack("!BI", header)
                payload = await out.readexactly(length)
                if self.ws.closed:
                    break
                if msg_type == 1:
                    await self.ws.send_bytes(payload)
                else:
                    await self.ws.send_str(payload.decode("utf-8", errors="replace"))
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception as e:
            log(f"[{self.room.code}/{self.name}] Ausgabefehler: {e}")

    async def pump_errors(self):
        prefix = f"[{self.room.code}/{self.name}]"
        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    safe_print(f"{prefix} {text}")
        except Exception:
            pass

    async def pump_input(self):
        """Tastatur/Maus aus dem Browser als JSON-Zeilen an den Spielprozess."""
        stdin = self.process.stdin
        async for msg in self.ws:
            if msg.type == WSMsgType.TEXT:
                data = msg.data
                if len(data) > 2000 or "\n" in data:
                    continue
                try:
                    stdin.write(data.encode("utf-8") + b"\n")
                    await stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break
            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break

    async def stop(self, text=""):
        if self.stopped:
            return
        self.stopped = True
        if text and not self.ws.closed:
            try:
                await self.ws.send_str(json.dumps({"t": "end", "reason": "closed", "text": text}))
            except Exception:
                pass
        proc = self.process
        if proc is not None and proc.returncode is None:
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                await asyncio.wait_for(proc.wait(), 2)
            except asyncio.TimeoutError:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), 2)
                except asyncio.TimeoutError:
                    proc.kill()
        if not self.ws.closed:
            await self.ws.close()


class BridgeSession:
    """NEU: Browser-Modus - reicht Bytes zwischen WebSocket (Browser) und TCP (Raum-Server) durch.
    Das Spiel selbst laeuft im Browser; der Server rechnet nur noch die Spiellogik."""

    def __init__(self, room, name, ws):
        self.room = room
        self.name = name
        self.ws = ws
        self.writer = None
        self.stopped = False

    async def stop(self, text=""):
        if self.stopped:
            return
        self.stopped = True
        if self.writer is not None:
            try:
                self.writer.close()
            except Exception:
                pass
        if not self.ws.closed:
            await self.ws.close(code=4000, message=text.encode("utf-8")[:120])


def join_problem(room, code, name):
    if not name:
        return "Bitte gib einen Namen ein."
    if room is None or room.closed:
        return f"Raum {code} gibt es nicht (mehr)."
    if len(room.sessions) >= MAX_PLAYERS_PER_ROOM:
        return "Der Raum ist voll (15 Spieler)."
    if room.status.get("game_active"):
        return "In diesem Raum läuft gerade ein Spiel - warte bis zur nächsten Runde."
    return None


async def ws_game_handler(request):
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=256 * 1024)
    await ws.prepare(request)
    code = clean_text(request.query.get("room", ""), CODE_LENGTH).upper()
    name = clean_text(request.query.get("name", ""), 16)
    room = manager.rooms.get(code)
    problem = join_problem(room, code, name)
    if problem:
        await ws.close(code=4000, message=problem.encode("utf-8")[:120])
        return ws

    session = BridgeSession(room, name, ws)
    room.sessions.add(session)
    room.empty_since = None
    log(f"{name} ({request.remote}) spielt im Browser in Raum {code} ({len(room.sessions)} Spieler)")
    got_data = False
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", room.port)
        session.writer = writer

        async def browser_to_room():
            async for msg in ws:
                if msg.type == WSMsgType.BINARY:
                    writer.write(msg.data)
                    await writer.drain()
                elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                    break

        async def room_to_browser():
            nonlocal got_data
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                got_data = True
                await ws.send_bytes(data)

        t_in = asyncio.create_task(browser_to_room())
        t_out = asyncio.create_task(room_to_browser())
        done, _pending = await asyncio.wait({t_in, t_out}, return_when=asyncio.FIRST_COMPLETED)
        for t in (t_in, t_out):
            if not t.done():
                t.cancel()
        if t_out in done and not session.stopped:
            text = ("Der Raum ist voll oder das Spiel läuft schon." if not got_data
                    else "Der Raum wurde geschlossen.")
            await session.stop(text)
    except Exception as e:
        log(f"Bruecken-Fehler {name}@{code}: {e}")
    finally:
        await session.stop("")
        room.sessions.discard(session)
        if not room.sessions:
            room.empty_since = time.time()
        log(f"{name} hat Raum {code} verlassen ({len(room.sessions)} Spieler)")
    return ws


async def play_page(request):
    # pygbag uebernimmt die Parameter der Seitenadresse als Umgebungsvariablen. PYGPI=/cdn/ sorgt
    # dafuer, dass Python-Pakete (pygame) vom eigenen Server kommen - ohne Internet. Muss VORNE stehen.
    if not request.query_string.startswith("PYGPI="):
        rest = "&".join(part for part in request.query_string.split("&") if part and not part.startswith("PYGPI="))
        raise web.HTTPFound("/play/?PYGPI=/cdn/" + ("&" + rest if rest else ""))
    index = os.path.join(CLIENT_DIR, "index.html")
    if not os.path.exists(index):
        return web.Response(content_type="text/html", text=(
            "<h2>Browser-Version noch nicht gebaut</h2><p>Auf dem Server einmal "
            "<code>python tools/build_web_client.py</code> ausführen (setup.sh macht das automatisch).</p>"
            "<p><a href='/'>Zurück</a></p>"))
    return web.FileResponse(index, headers={"Cache-Control": "no-cache"})


async def play_redirect(request):
    raise web.HTTPFound("/play/" + (("?" + request.query_string) if request.query_string else ""))


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=64 * 1024)
    await ws.prepare(request)

    async def fail(text):
        await ws.send_str(json.dumps({"t": "end", "reason": "join_failed", "text": text}))
        await ws.close()
        return ws

    code = clean_text(request.query.get("room", ""), CODE_LENGTH).upper()
    name = clean_text(request.query.get("name", ""), 16)
    room = manager.rooms.get(code)
    if not name:
        return await fail("Bitte gib einen Namen ein.")
    if room is None or room.closed:
        return await fail(f"Raum {code} gibt es nicht (mehr).")
    if len(room.sessions) >= MAX_PLAYERS_PER_ROOM:
        return await fail("Der Raum ist voll (15 Spieler).")
    if room.status.get("game_active"):
        return await fail("In diesem Raum läuft gerade ein Spiel - warte bis zur nächsten Runde.")
    if manager.session_count() >= MAX_SESSIONS:
        return await fail("Der Server ist ausgelastet - bitte später noch einmal versuchen.")

    session = Session(room, name, ws, request.remote)
    room.sessions.add(session)
    room.empty_since = None
    log(f"{name} ({request.remote}) betritt Raum {code} ({len(room.sessions)} Spieler)")
    try:
        await session.start()
        await ws.send_str(json.dumps({"t": "joined", "room": code, "name": name, "room_name": room.name,
                                      "size": GAME_RESOLUTION}))
        out_task = asyncio.create_task(session.pump_output())
        err_task = asyncio.create_task(session.pump_errors())
        in_task = asyncio.create_task(session.pump_input())
        proc_task = asyncio.create_task(session.process.wait())
        done, _pending = await asyncio.wait({out_task, in_task, proc_task}, return_when=asyncio.FIRST_COMPLETED)
        if in_task not in done:
            # Spielprozess ist fertig -> letzte Nachrichten (z.B. "Raum geschlossen") noch zustellen
            try:
                await asyncio.wait_for(asyncio.shield(out_task), 2)
            except Exception:
                pass
        for t in (out_task, in_task):
            if not t.done():
                t.cancel()
        await session.stop()
        err_task.cancel()
        proc_task.cancel()
    except Exception as e:
        log(f"Sitzungsfehler {name}@{code}: {e}")
        await session.stop("Interner Fehler")
    finally:
        room.sessions.discard(session)
        if not room.sessions:
            room.empty_since = time.time()
        log(f"{name} hat Raum {code} verlassen ({len(room.sessions)} Spieler)")
    return ws


# =========================
# HTTP-API + STATISCHE DATEIEN
# =========================
async def index(_request):
    return web.FileResponse(os.path.join(WEB_DIR, "index.html"), headers={"Cache-Control": "no-cache"})


async def api_rooms(_request):
    rooms = sorted((r.public() for r in manager.rooms.values() if not r.closed),
                   key=lambda r: (r["game_active"], -r["players"], r["age"]))
    return web.json_response({"rooms": rooms, "max_rooms": MAX_ROOMS, "empty_timeout": ROOM_EMPTY_TIMEOUT})


async def api_create_room(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    name = clean_text(data.get("name", ""), 24)
    creator = clean_text(data.get("creator", ""), 16)
    if not name and creator:
        name = f"Raum von {creator}"
    room = await manager.create(name, request.remote or "?")
    return web.json_response({"code": room.code, "name": room.name})


async def api_info(_request):
    sounds = {}
    for key, filename in sound.available_sounds().items():
        sounds[key] = {"file": filename, "volume": sound.SOUND_FILES[key][1]}
    w, h = GAME_RESOLUTION.lower().split("x")
    return web.json_response({
        "browser_client": os.path.exists(os.path.join(CLIENT_DIR, "index.html")),
        "sounds": sounds,
        "music_lobby": sound.MUSIC_VOLUME_LOBBY,
        "width": int(w), "height": int(h),
        "room_empty_timeout": ROOM_EMPTY_TIMEOUT,
        "max_players": MAX_PLAYERS_PER_ROOM,
    })


async def media_video(_request):
    if not os.path.exists(VIDEO_FILE):
        raise web.HTTPNotFound()
    return web.FileResponse(VIDEO_FILE, headers={"Content-Type": "video/mp4"})


async def on_startup(app):
    app["janitor"] = asyncio.create_task(manager.janitor())
    # Im Container kennt nur setup.sh die echte WLAN-IP des Servers -> PUBLIC_URLS
    urls = [u for u in os.environ.get("PUBLIC_URLS", "").split(",") if u.strip()]
    if not urls:
        urls = [f"http://{ip}" + ("" if PUBLIC_PORT == 80 else f":{PUBLIC_PORT}") for ip in lan_addresses()]
    log("=" * 60)
    log("Thalheimer is Among Us laeuft!")
    for u in urls:
        log(f"  Beitrittslink im WLAN:  {u}")
    log(f"  Raeume werden nach {ROOM_EMPTY_TIMEOUT}s ohne Spieler geloescht.")
    log("=" * 60)


async def on_shutdown(_app):
    for room in list(manager.rooms.values()):
        await manager.close(room, "Server wird beendet")


def make_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/rooms", api_rooms)
    app.router.add_post("/api/rooms", api_create_room)
    app.router.add_get("/api/info", api_info)
    app.router.add_get("/media/OshiNoKoIntro.m4v", media_video)
    app.router.add_get("/ws/game", ws_game_handler)
    app.router.add_get("/play", play_redirect)
    app.router.add_get("/play/", play_page)
    if os.path.isdir(CLIENT_DIR):
        app.router.add_static("/play/", CLIENT_DIR)
    if os.path.isdir(CDN_DIR):
        app.router.add_static("/cdn/", CDN_DIR)
    app.router.add_static("/static/", WEB_DIR)
    app.router.add_static("/sounds/", SOUND_DIR)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    web.run_app(make_app(), host="0.0.0.0", port=HTTP_PORT, access_log=None, print=None)
