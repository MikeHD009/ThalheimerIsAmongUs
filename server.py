import socket
import threading
import struct
import random
import time
import argparse
import json
import sys

import roles

PORT = 5555
MAX_PLAYERS = 15

clients = {}
player_positions = {}
player_names = {}

host_id = 0

imposter_count = 1
active_imposters = []
dead_players = set() # NEU: Globale Set für tote Spieler
game_active = False  # NEU: Um Status-Prüfungen nur im Spiel auszuführen

total_crew_tasks = 0
completed_crew_tasks = 0

in_meeting = False
meeting_votes = {}
meeting_timer_obj = None

# =========================
# SERVER-MODUS / THREAD-SICHERHEIT (NEU)
# =========================
# Alle Client-Threads und die Meeting-Timer greifen auf dieselben globalen Variablen zu.
# Ein gemeinsames RLock verhindert, dass sich z.B. zwei gleichzeitige Kills oder ein Kill
# waehrend der Meeting-Auswertung gegenseitig ueberschreiben.
state_lock = threading.RLock()
# Pro Verbindung ein eigenes Sende-Lock: sonst koennen zwei Threads ihre Bytes ineinander
# schieben (z.B. Lobby-Update + Positionspaket) und der Client liest danach nur noch Muell.
send_locks = {}
SEND_TIMEOUT = 10.0           # haengt ein Client so lange, wird er getrennt (statt alle zu blockieren)
HANDSHAKE_TIMEOUT = 5.0       # so lange darf ein neuer Client fuer seinen Namen brauchen
ROOM_CODE = ""                # nur im Web-Modus gesetzt (fuer Log-Ausgaben)

# Paket-Nutzlasten (Bytes nach dem Typ-Byte). Wird VOR dem Sperren komplett gelesen, damit ein
# langsamer Client nie das Lock festhaelt. None = variable Laenge (Chat, Paket 50).
PAYLOAD_SIZES = {
    10: 0, 11: 1, 13: 2, 99: 0, 20: 1, 30: 1, 23: 0, 2: 8, 40: 1, 41: 1, 50: None,
    60: 1, 62: 1, 63: 1, 65: 1, 66: 8, 68: 8, 73: 1, 75: 1, 77: 0, 79: 1, 81: 0,
    16: 3, 18: 2,   # NEU: Host-Einstellungen, feste Rollen-Zuteilung
}

# NEU: Todesursachen-Bits in Paket 31 (Byte "death_flags")
DEATH_FLAG_VLADIMIR = 1    # Opfer muss das Anime-Intro schauen
DEATH_FLAG_EJECTED = 2     # im Meeting rausgewaehlt
DEATH_FLAG_TRAP = 4        # in Noahs Falle getreten
DEATH_FLAG_WINDOW = 8      # an Evelyns offenem Fenster gestorben
DEATH_FLAG_EXPLOSION = 16  # von Steinermike gesprengt
NO_KILLER = 255

# NEU: Ergebnis-Codes in Paket 43 (Meeting-Ende)
MEETING_RESULT_EJECTED = 0
MEETING_RESULT_SKIPPED = 1
MEETING_RESULT_TIE = 2
MEETING_RESULT_IMMORTAL = 3   # waere rausgeflogen, war aber durch den Tappeihnachtsmann geschuetzt

# =========================
# ROLLEN-SYSTEM: Server-Zustand
# =========================
RAMONA_MIN_PLAYERS = roles.RAMONA_MIN_PLAYERS   # Ramona braucht genug Spieler (Regel in roles.py)
MAX_IMPOSTERS = roles.MAX_IMPOSTERS             # harte Obergrenze fuer die Imposter-Anzahl
IMMORTALITY_DURATION = 10.0   # Tappeihnachtsmann
WINDOW_HAZARD_DURATION = 20.0 # Evelyn
INVISIBILITY_DURATION = 8.0   # Vogelscheicher
RAMONA_FORGE_COOLDOWN = 10.0  # Ramona
TRAP_HIT_RADIUS = 20          # Noah
NOAH_TRAP_LIMIT = 3           # Noah: hoechstens 3 gleichzeitige Fallen, die aelteste wird ersetzt
EVELYN_COOLDOWN = 30.0        # Evelyn: alle 30s ein Fensterraum sabotierbar
# NEU: Vom Host vor Spielbeginn einstellbar (Paket 16), wird an alle verteilt (Paket 17)
DEFAULT_SETTINGS = {"cooldown": 30, "discussion": 45, "vote": 30}
SETTING_LIMITS = {"cooldown": (0, 120), "discussion": (0, 180), "vote": (10, 180)}
settings = dict(DEFAULT_SETTINGS)   # cooldown = Notfall-Cooldown nach Spielstart/Meeting-Ende (s)

# Grund fuer ein Meeting (Paket 40)
MEETING_REASON_BUTTON = 0
MEETING_REASON_BODY = 1
MEETING_REASON_KALIYOGA = 2   # Kaliyoga: einmal pro Spiel von ueberall aus

enabled_roles = set()          # vom Host per Paket 13 gesetzte Rollen-Keys

player_base_team = {}          # pid -> roles.TEAM_CREW / TEAM_IMPOSTOR / TEAM_INDEPENDENT
player_roles = {}              # pid -> role_key oder None (generisch)
ability_uses = {}              # pid -> verbleibende Nutzungen (limitierte Fähigkeiten)
player_rights = {}             # pid -> verbleibende "Rechte" (Ramona)
ramona_id = None                # pid der/des Eigenständigen dieser Runde, oder None
ramona_last_use = 0.0           # Zeitstempel des letzten Unterschrift-Fälschens

active_traps = {}              # trap_id -> (owner_id, x, y)   (Noah)
next_trap_id = 0
invisible_until = {}           # pid -> Zeitstempel bis wann unsichtbar (Vogelscheicher)
david_targets = {}             # NEU: David-pid -> Spieler, dessen Nachrichten ALLE verwuerfelt werden
global_immortal_until = 0.0    # Zeitstempel bis wann NIEMAND sterben kann (Tappeihnachtsmann)
window_hazard_active_until = 0.0  # Zeitstempel bis wann Evelyns Fenster-Falle aktiv ist
window_hazard_room = 255       # Index des aktuell geoeffneten Fensterraums (255 = keiner)
evelyn_last_use = 0.0          # Zeitstempel der letzten Fenster-Sabotage
player_completed_tasks = {}    # pid -> Set erledigter Task-Indizes (fuer Laurins Sabotage)
meeting_phase = 0              # 0 = kein Meeting, 1 = Diskussion, 2 = Abstimmung
emergency_used = set()         # NEU: wer seinen EINEN Notfall-Knopf dieser Runde schon benutzt hat
emergency_ready_at = 0.0       # NEU: ab wann der Notfall-Knopf wieder geht (Cooldown nach Meeting-Ende)
fixed_roles = {}               # NEU: pid -> feste Zuteilung des Hosts (roles.FIXED_*), "Cheat"


_print_lock = threading.Lock()

def _emit_line(text):
    """FIX: Jede Ausgabe als EINE komplette Zeile schreiben. print() aus mehreren Threads konnte
    Zeilen ineinanderschieben - dann ging z.B. eine @@STATUS-Zeile fuer den Webserver verloren."""
    try:
        with _print_lock:
            sys.stdout.write(text + chr(10))
            sys.stdout.flush()
    except Exception:
        pass

def log(*args):
    prefix = f"[SERVER {ROOM_CODE}]" if ROOM_CODE else "[SERVER]"
    _emit_line(" ".join(str(a) for a in (prefix,) + args))

def recv_exact(conn, n):
    """NEU: Liest GENAU n Bytes. conn.recv(n) darf laut TCP auch weniger liefern - dann waere
    der Datenstrom ab da verschoben und jedes weitere Paket kaputt."""
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Verbindung waehrend eines Pakets getrennt")
        buf += chunk
    return buf

def team_byte_of(pid):
    team = player_base_team.get(pid, roles.TEAM_CREW)
    return 1 if team == roles.TEAM_IMPOSTOR else (2 if team == roles.TEAM_INDEPENDENT else 0)

def emit_status():
    """NEU: Maschinenlesbare Statuszeile fuer den Web-Raumverwalter (web_server.py).
    Im normalen LAN-Betrieb ist das nur eine zusaetzliche Log-Zeile."""
    try:
        status = {
            "players": len(clients),
            "game_active": bool(game_active),
            "host": player_names.get(host_id, "") if clients else "",
        }
        _emit_line("@@STATUS " + json.dumps(status))
    except Exception:
        pass

def max_imposters_for(n_players):
    return roles.max_imposters_for(n_players)

def current_fixed():
    """Feste Zuteilungen nur fuer Spieler, die gerade da sind."""
    return {pid: code for pid, code in fixed_roles.items() if pid in clients}

def role_setup_status():
    """Autoritative Pruefung - dieselbe Funktion wie im Client (roles.setup_status)."""
    ok, msg, _n_imp = roles.setup_status(len(clients), imposter_count, enabled_roles,
                                         current_fixed().values())
    return ok, msg

def settings_packet():
    return struct.pack("!BBBB", 17, settings["cooldown"], settings["discussion"], settings["vote"])

def fixed_roles_packet():
    fixed = current_fixed()
    packet = struct.pack("!BB", 19, len(fixed))
    for pid, code in sorted(fixed.items()):
        packet += struct.pack("!BB", pid, code)
    return packet

def send_fixed_roles_to_host():
    """Die festen Zuteilungen sieht NUR der Host (sonst waere der Cheat fuer alle sichtbar)."""
    if host_id in clients:
        send_to(host_id, fixed_roles_packet())

def start_meeting_timer(seconds, callback):
    global meeting_timer_obj
    meeting_timer_obj = threading.Timer(max(0.05, float(seconds)), callback)
    meeting_timer_obj.daemon = True
    meeting_timer_obj.start()

def start_voting_phase():
    """NEU: Nach der reinen Chat-/Diskussionszeit wird die Abstimmung freigeschaltet."""
    global meeting_phase, meeting_timer_obj
    with state_lock:
        if not in_meeting or meeting_phase != 1:
            return
        meeting_phase = 2
        broadcast_to_all(struct.pack("!B", 42))
        start_meeting_timer(settings["vote"], end_meeting)

def alive_imposter_count():
    return sum(1 for pid, team in player_base_team.items()
               if team == roles.TEAM_IMPOSTOR and pid not in dead_players and pid in clients)

def end_meeting():
    """Wertet die Stimmen aus, wirft ggf. einen Spieler raus und beendet das Meeting."""
    global in_meeting, meeting_phase, emergency_ready_at
    with state_lock:
        if not in_meeting:
            return

        tally = {}
        skip_count = 0
        for v_id, t_id in list(meeting_votes.items()):
            if v_id in clients and v_id not in dead_players:
                weight = 3 if player_roles.get(v_id) == "orakel" else 1
                if t_id == 255:
                    skip_count += weight
                elif t_id in clients and t_id not in dead_players:
                    tally[t_id] = tally.get(t_id, 0) + weight

        max_votes = skip_count
        evicted_id = 255
        tie = False
        for t_id, count in tally.items():
            if count > max_votes:
                max_votes = count
                evicted_id = t_id
                tie = False
            elif count == max_votes:
                tie = True

        # NEU: Ergebnis genauer unterscheiden (fuer die Rauswurf-Animation beim Client)
        if tie:
            result = MEETING_RESULT_TIE
            evicted_id = 255
        elif evicted_id == 255:
            result = MEETING_RESULT_SKIPPED
        elif time.time() < global_immortal_until:
            result = MEETING_RESULT_IMMORTAL
        else:
            result = MEETING_RESULT_EJECTED
            dead_players.add(evicted_id)
            broadcast_to_all(struct.pack("!BBBBBB", 31, evicted_id, 1, 0, DEATH_FLAG_EJECTED, NO_KILLER))

        in_meeting = False
        meeting_phase = 0
        # NEU: Der Notfall-Cooldown startet erst, wenn das Meeting vorbei ist
        emergency_ready_at = time.time() + settings["cooldown"]

        # NEU: Paket 43 traegt jetzt Ergebnis, Team + Rolle des Rausgeworfenen (Role-Reveal)
        # und wie viele Imposter noch leben. Es geht VOR der Siegpruefung raus, damit alle
        # Clients zuerst die Rauswurf-Animation zeigen und erst danach den Sieg-Bildschirm.
        if evicted_id != 255:
            reveal_team = team_byte_of(evicted_id)
            reveal_role = roles.role_id_of(player_roles.get(evicted_id))
        else:
            reveal_team, reveal_role = 0, roles.NO_ROLE_ID
        broadcast_to_all(struct.pack("!BBBBBB", 43, evicted_id, result, reveal_team, reveal_role,
                                     min(255, alive_imposter_count())))
        check_win_conditions()

def send_lobby_update():
    with state_lock:
        # Anzahl und Namensliste aus DERSELBEN Momentaufnahme bauen und als EIN Paket senden
        entries = [(pid, player_names.get(pid, str(pid))) for pid in list(clients.keys())]
        packet = struct.pack("!BBB", 1, len(entries), host_id)
        for other_id, name in entries:
            name_bytes = name.encode("utf-8")[:255]
            packet += struct.pack(f"!BB{len(name_bytes)}s", other_id, len(name_bytes), name_bytes)
        broadcast_to_all(packet)

def send_to(pid, data):
    """NEU: Sendet ein komplettes Paket an genau einen Client (thread-sicher)."""
    conn = clients.get(pid)
    lock = send_locks.get(pid)
    if conn is None or lock is None:
        return False
    try:
        with lock:
            conn.sendall(data)
        return True
    except Exception:
        # Nicht direkt hier trennen (wir koennten mitten in einer Schleife ueber clients sein)
        threading.Thread(target=disconnect, args=(pid,), daemon=True).start()
        return False

def broadcast_to_all(data, exclude_id=None):
    for pid in list(clients.keys()):
        if pid != exclude_id:
            send_to(pid, data)

def broadcast_final_roles():
    """NEU: Paket 83 - deckt am Spielende alle Rollen auf (fuer den Sieg-/Niederlagen-Bildschirm)."""
    entries = [pid for pid in player_base_team.keys() if pid in clients]
    packet = struct.pack("!BB", 83, len(entries))
    for pid in entries:
        packet += struct.pack("!BBB", pid, team_byte_of(pid), roles.role_id_of(player_roles.get(pid)))
    broadcast_to_all(packet)

def finish_game(win_packet):
    global game_active, in_meeting, meeting_phase
    game_active = False
    # Laufendes Meeting abbrechen, sonst feuert spaeter noch ein Timer in die Lobby hinein
    if meeting_timer_obj:
        meeting_timer_obj.cancel()
    in_meeting = False
    meeting_phase = 0
    broadcast_final_roles()
    broadcast_to_all(win_packet)
    emit_status()

# NEU: Helfer-Funktion zum Checken der Siegbedingungen
def check_win_conditions():
    with state_lock:
        if not game_active: return

        alive_imps = alive_imposter_count()
        alive_crew = sum(1 for pid, team in player_base_team.items()
                          if team == roles.TEAM_CREW and pid not in dead_players and pid in clients)
        imp_ids = [pid for pid, team in player_base_team.items() if team == roles.TEAM_IMPOSTOR]

        # Imposter gewinnen, wenn gleich viele oder mehr Imposter als Crewmates leben
        # (Eigenständige zaehlen weder zu Imposter noch zu Crew).
        # FIX: vorher wurde "alive_crew > 0" verlangt - starb die letzte Crew z.B. in einer Falle,
        # blieb das Spiel fuer immer haengen.
        if alive_imps > 0 and alive_imps >= alive_crew:
            win_packet = struct.pack("!BB", 32, len(imp_ids))
            for imp_id in imp_ids:
                win_packet += struct.pack("!B", imp_id)
            finish_game(win_packet)
        # FIX/NEU: Sind alle Imposter tot (rausgewaehlt oder vom Spiel gegangen), gewinnt die Crew.
        elif imp_ids and alive_imps == 0:
            win_packet = struct.pack("!BB", 22, len(imp_ids))
            for imp_id in imp_ids:
                win_packet += struct.pack("!B", imp_id)
            finish_game(win_packet)

def disconnect(player_id):
    global host_id

    with state_lock:
        conn = clients.pop(player_id, None)
        if conn is None:
            return  # schon getrennt (kann von mehreren Threads gleichzeitig kommen)
        log(f"Player {player_id} disconnected")
        try: conn.close()
        except: pass
        send_locks.pop(player_id, None)
        player_names.pop(player_id, None)
        player_positions.pop(player_id, None)
        fixed_roles.pop(player_id, None)   # IDs werden wiederverwendet -> Zuteilung nicht vererben
        david_targets.pop(player_id, None)

        disconnect_packet = struct.pack("!BBii", 4, player_id, -1000, -1000)
        broadcast_to_all(disconnect_packet)

        if player_id == host_id:
            if len(clients) > 0: host_id = sorted(clients.keys())[0]
            else: host_id = 0
            send_fixed_roles_to_host()

        # Falls Spieler verlässt, Win Conditions neu evaluieren
        check_win_conditions()
        send_lobby_update()
        emit_status()

def read_packet(conn, packet):
    """NEU: Liest die komplette Nutzlast eines Pakets (ohne das Typ-Byte)."""
    if packet not in PAYLOAD_SIZES:
        raise ConnectionError(f"Unbekanntes Paket {packet}")
    size = PAYLOAD_SIZES[packet]
    if size is None:  # Chat: 1 Byte Laenge + Text
        msg_len = recv_exact(conn, 1)[0]
        return bytes([msg_len]) + (recv_exact(conn, msg_len) if msg_len else b"")
    return recv_exact(conn, size) if size else b""

def handle_client(conn, player_id):
    log(f"Thread gestartet für Player {player_id}")
    try:
        while True:
            try:
                data = conn.recv(1)
            except socket.timeout:
                continue  # nur Leerlauf (z.B. Spieler steht still) - kein Fehler
            if not data: break
            packet = data[0]
            payload = read_packet(conn, packet)
            with state_lock:
                if player_id not in clients:
                    break
                process_packet(conn, player_id, packet, payload)

    except (ConnectionError, OSError):
        pass  # normales Verlassen (Fenster/Tab geschlossen) - kein Fehler
    except Exception as e:
        log(f"ERROR Player {player_id}: {e}")

    disconnect(player_id)

def process_packet(conn, player_id, packet, payload):
    global host_id, total_crew_tasks, completed_crew_tasks, game_active
    global player_base_team, player_roles, ability_uses, player_rights
    global ramona_id, ramona_last_use, active_traps, next_trap_id
    global invisible_until, david_targets, global_immortal_until, window_hazard_active_until
    global window_hazard_room, evelyn_last_use, player_completed_tasks
    global active_imposters, imposter_count
    global in_meeting, meeting_timer_obj, meeting_phase
    global emergency_ready_at

    if packet == 10:
        broadcast_to_all(struct.pack("!B", 10))

    elif packet == 11:
        new_count = struct.unpack("!B", payload)[0]
        if player_id == host_id and not game_active:
            # Nie mehr Imposter als freundliche Spieler zulassen
            imposter_count = max(1, min(new_count, max_imposters_for(len(clients))))
        broadcast_to_all(struct.pack("!BB", 12, imposter_count))

    # NEU: Host togglet eine Custom-Rolle an/aus
    elif packet == 13:
        role_id, enabled_flag = struct.unpack("!BB", payload)
        if player_id == host_id and not game_active:
            key = roles.role_key_of(role_id)
            if key is not None:
                if enabled_flag:
                    enabled_roles.add(key)
                else:
                    enabled_roles.discard(key)
        broadcast_to_all(struct.pack("!BI", 14, roles.bitmask_of(enabled_roles)))

    # NEU: Host stellt Notfall-Cooldown, Diskussions- und Abstimmungszeit ein (nur vor Spielbeginn)
    elif packet == 16:
        cooldown, discussion, vote = struct.unpack("!BBB", payload)
        if player_id == host_id and not game_active:
            for key, value in (("cooldown", cooldown), ("discussion", discussion), ("vote", vote)):
                lo, hi = SETTING_LIMITS[key]
                settings[key] = max(lo, min(hi, value))
        broadcast_to_all(settings_packet())

    # NEU: Host teilt einem Spieler fest eine Rolle/ein Team zu ("Cheat", nur der Host sieht es)
    elif packet == 18:
        target_id, code = struct.unpack("!BB", payload)
        if player_id == host_id and not game_active and target_id in clients and code in roles.FIXED_OPTIONS:
            if code == roles.FIXED_NONE:
                fixed_roles.pop(target_id, None)
            else:
                # Jede Spezialrolle nur einmal: gleiche Rolle bei einem anderen Spieler entfernen
                if roles.role_key_of(code) is not None and code not in (roles.FIXED_IMPOSTER, roles.FIXED_CREW):
                    for other, other_code in list(fixed_roles.items()):
                        if other_code == code and other != target_id:
                            del fixed_roles[other]
                fixed_roles[target_id] = code
        send_fixed_roles_to_host()

    elif packet == 99:
        if player_id != host_id or game_active:
            return
        log(f"Gameplay aktiviert von {player_id}")

        enemy_keys = [k for k in enabled_roles if roles.team_of(k) == roles.TEAM_IMPOSTOR]
        friendly_keys = [k for k in enabled_roles if roles.team_of(k) == roles.TEAM_CREW]
        setup_ok, setup_msg = role_setup_status()
        if not setup_ok:
            log(f"Rollen-Konfiguration ungueltig ({setup_msg}), Start abgebrochen")
            return

        # Beim Match-Start laufende Meeting-Timer abbrechen
        if meeting_timer_obj:
            meeting_timer_obj.cancel()
        in_meeting = False
        meeting_phase = 0

        dead_players.clear()
        game_active = True

        pool = list(clients.keys())
        fixed = current_fixed()
        _ok, _msg, n_imp = roles.setup_status(len(pool), imposter_count, enabled_roles, fixed.values())

        player_base_team = {}
        player_roles = {}
        ability_uses = {}
        player_rights = {}
        active_traps = {}
        next_trap_id = 0
        invisible_until = {}
        david_targets = {}
        global_immortal_until = 0.0
        window_hazard_active_until = 0.0
        window_hazard_room = 255
        evelyn_last_use = 0.0
        player_completed_tasks = {pid: set() for pid in clients}
        ramona_last_use = 0.0
        ramona_id = None
        emergency_used.clear()
        # Auch direkt nach dem Start gilt der Notfall-Cooldown (alle stehen am Notfallknopf)
        emergency_ready_at = time.time() + settings["cooldown"]

        def fixed_key(pid):
            code = fixed.get(pid)
            if code in (None, roles.FIXED_NONE, roles.FIXED_IMPOSTER, roles.FIXED_CREW):
                return None
            return roles.role_key_of(code)

        # 1) Eigenständig (Ramona) -- fest zugeteilt, oder zufaellig wenn aktiviert und genug Spieler
        ramona_fixed = [pid for pid in pool if fixed_key(pid) == "ramona"]
        if ramona_fixed:
            ramona_id = ramona_fixed[0]
        elif "ramona" in enabled_roles and len(pool) >= RAMONA_MIN_PLAYERS:
            candidates = [pid for pid in pool if pid not in fixed]
            ramona_id = random.choice(candidates) if candidates else None
        if ramona_id is not None:
            pool.remove(ramona_id)
            player_base_team[ramona_id] = roles.TEAM_INDEPENDENT
            player_roles[ramona_id] = "ramona"

        # 2) Imposter-Team: fest zugeteilte zuerst, der Rest zufaellig (nie alle Spieler)
        fixed_imps = [pid for pid in pool if roles.fixed_team(fixed.get(pid)) == roles.TEAM_IMPOSTOR]
        free = [pid for pid in pool if roles.fixed_team(fixed.get(pid)) is None]
        want = max(1, min(n_imp, len(pool) - 1)) if len(pool) > 1 else 0
        extra = max(0, want - len(fixed_imps))
        imposter_ids = fixed_imps + random.sample(free, min(extra, len(free)))
        for pid in imposter_ids:
            pool.remove(pid)
            player_base_team[pid] = roles.TEAM_IMPOSTOR
        active_imposters = list(imposter_ids)

        # 3) Rest ist Besatzung
        crew_ids = list(pool)
        for pid in crew_ids:
            player_base_team[pid] = roles.TEAM_CREW

        # 4) Fest zugeteilte Spezialrollen setzen, die uebrigen aktivierten Rollen ohne
        #    Zuruecklegen zufaellig auf die restlichen Plaetze des passenden Teams verteilen
        used_keys = set()
        for pid in imposter_ids + crew_ids:
            key = fixed_key(pid)
            if key is not None and roles.team_of(key) == player_base_team[pid]:
                player_roles[pid] = key
                used_keys.add(key)
        avail_enemy = [k for k in enemy_keys if k not in used_keys]
        random.shuffle(avail_enemy)
        for pid in imposter_ids:
            if pid not in player_roles:
                player_roles[pid] = avail_enemy.pop() if avail_enemy else None

        avail_friendly = [k for k in friendly_keys if k not in used_keys]
        random.shuffle(avail_friendly)
        for pid in crew_ids:
            if pid not in player_roles:
                player_roles[pid] = avail_friendly.pop() if avail_friendly else None

        # 5) Fähigkeits-Kontingente & Rechte initialisieren
        for pid, key in player_roles.items():
            mu = roles.max_uses_of(key)
            if mu is not None:
                ability_uses[pid] = mu
        for pid in clients.keys():
            if pid != ramona_id:
                player_rights[pid] = 3

        # 6) Aufgaben-Gesamtzahl: Felix zaehlt nicht mit (seine Aufgaben zaehlen nie)
        felix_count = sum(1 for k in player_roles.values() if k == "felix")
        contributing_crew = max(0, len(crew_ids) - felix_count)
        total_crew_tasks = max(1, contributing_crew * 10)
        completed_crew_tasks = 0

        modifiers = 1 if "vladimir" in player_roles.values() else 0

        # NEU: Paket 15 traegt die Imposter-Teamliste und geht AUSSCHLIESSLICH an die
        # Imposter selbst - damit sie wissen, wer ihre Teammates sind. Es muss nach
        # Paket 5 (Rollenzuweisung) und vor Paket 3 (Spielstart) verschickt werden.
        imposter_team_packet = struct.pack("!BB", 15, len(imposter_ids))
        for imp_id in imposter_ids:
            imposter_team_packet += struct.pack("!B", imp_id)

        for pid in list(clients.keys()):
            role_id = roles.role_id_of(player_roles.get(pid))
            start_packet = struct.pack("!BBB", 5, team_byte_of(pid), role_id)
            if pid in imposter_ids:
                start_packet += imposter_team_packet
            start_packet += struct.pack("!BB", 3, modifiers)
            send_to(pid, start_packet)
        # Erster Fortschritts-Stand, damit die Leiste sofort die richtige Gesamtzahl zeigt
        broadcast_to_all(struct.pack("!BHH", 21, completed_crew_tasks, total_crew_tasks))
        broadcast_to_all(settings_packet())
        emit_status()

    elif packet == 20:
        # NEU: Der Client schickt jetzt mit, WELCHE Aufgabe erledigt wurde (255 = keine
        # Karten-Aufgabe, z.B. Raphis Pfandflaschen). Nur so kann Laurin gezielt eine
        # Aufgabe fuer alle wieder zuruecksetzen.
        done_task_idx = struct.unpack("!B", payload)[0]
        if not game_active:
            return
        if player_roles.get(player_id) != "felix":
            completed_crew_tasks += 1
            if done_task_idx != 255:
                player_completed_tasks.setdefault(player_id, set()).add(done_task_idx)
        broadcast_to_all(struct.pack("!BHH", 21, completed_crew_tasks, total_crew_tasks))

        if completed_crew_tasks >= total_crew_tasks and game_active:
            win_packet = struct.pack("!BB", 22, len(active_imposters))
            for imp_id in active_imposters:
                win_packet += struct.pack("!B", imp_id)
            finish_game(win_packet)

    # NEU: Kill-Paket verarbeiten
    elif packet == 30:
        target_id = struct.unpack("!B", payload)[0]
        # FIX: Kills nur im laufenden Spiel und nicht waehrend eines Meetings
        if (game_active and not in_meeting
                and player_id in active_imposters and player_id not in dead_players
                and time.time() >= global_immortal_until):
            if target_id in clients and target_id not in dead_players and target_id not in active_imposters:
                dead_players.add(target_id)
                killer_role = player_roles.get(player_id)
                no_corpse = 1 if killer_role == "steinermike" else 0
                weapon_id = 1 if killer_role == "martin" else 0
                # Bit 0 = das Opfer wurde von Vladimir getoetet -> Anime-Intro abspielen
                death_flags = DEATH_FLAG_VLADIMIR if killer_role == "vladimir" else 0
                if killer_role == "steinermike":
                    death_flags |= DEATH_FLAG_EXPLOSION
                # NEU: Killer-ID wird mitgeschickt (nur das Opfer sieht ihn in der Todes-Animation)
                broadcast_to_all(struct.pack("!BBBBBB", 31, target_id, no_corpse, weapon_id, death_flags, player_id))
                check_win_conditions()

    elif packet == 23:
        if player_id == host_id:
            if meeting_timer_obj:
                meeting_timer_obj.cancel()
            in_meeting = False
            meeting_phase = 0
            game_active = False
            dead_players.clear()
            broadcast_to_all(struct.pack("!B", 23))
            emit_status()

    elif packet == 2:
        x, y = struct.unpack("!ii", payload)
        player_positions[player_id] = (x, y)

        # Noah: Fallenkollision pruefen
        if (game_active and not in_meeting and player_id not in dead_players
                and time.time() >= global_immortal_until and active_traps):
            for trap_id, (owner_id, tx, ty) in list(active_traps.items()):
                if owner_id != player_id and abs(x - tx) < TRAP_HIT_RADIUS and abs(y - ty) < TRAP_HIT_RADIUS:
                    del active_traps[trap_id]
                    broadcast_to_all(struct.pack("!BH", 70, trap_id))   # NEU: Falle ist zugeschnappt
                    dead_players.add(player_id)
                    broadcast_to_all(struct.pack("!BBBBBB", 31, player_id, 0, 0, DEATH_FLAG_TRAP, owner_id))
                    check_win_conditions()
                    break

        # Vogelscheicher: waehrend Unsichtbarkeit Position nicht an andere weiterleiten
        if time.time() < invisible_until.get(player_id, 0):
            pass
        else:
            broadcast_to_all(struct.pack("!BBii", 2, player_id, x, y), exclude_id=player_id)

    elif packet == 40:
        reason = struct.unpack("!B", payload)[0]
        # NEU: Kaliyoga darf einmal pro Spiel von ueberall aus ein Meeting rufen -
        # das wird hier autoritativ geprueft und verbraucht.
        allowed = game_active and not in_meeting and player_id not in dead_players
        # NEU: Notfallknopf nur EINMAL pro Spieler und Runde und erst nach dem Cooldown.
        #      Leichen melden geht immer.
        if allowed and reason == MEETING_REASON_BUTTON:
            if player_id in emergency_used or time.time() < emergency_ready_at:
                allowed = False
            else:
                emergency_used.add(player_id)
        if allowed and reason == MEETING_REASON_KALIYOGA:
            if player_roles.get(player_id) == "kaliyoga" and ability_uses.get(player_id, 0) > 0:
                ability_uses[player_id] -= 1
            else:
                allowed = False

        if allowed:
            in_meeting = True
            meeting_phase = 1          # 1 = Diskussion (nur Chat)
            meeting_votes.clear()
            broadcast_to_all(struct.pack("!BBB", 40, player_id, reason))
            if settings["discussion"] > 0:
                start_meeting_timer(settings["discussion"], start_voting_phase)
            else:
                start_voting_phase()   # keine Diskussionszeit eingestellt -> sofort abstimmen

    elif packet == 41:
        target_id = struct.unpack("!B", payload)[0]
        # Stimmen zaehlen nur in der Abstimmungsphase und nur einmal pro Spieler
        if in_meeting and meeting_phase == 2 and player_id not in dead_players and player_id not in meeting_votes:
            meeting_votes[player_id] = target_id
            broadcast_to_all(struct.pack("!BBB", 41, player_id, target_id))
            # Haben alle Lebenden abgestimmt, sofort auswerten (kein Warten auf den Timer)
            alive = [pid for pid in clients if pid not in dead_players]
            if alive and all(pid in meeting_votes for pid in alive):
                if meeting_timer_obj:
                    meeting_timer_obj.cancel()
                threading.Thread(target=end_meeting, daemon=True).start()

    elif packet == 50:
        msg_len = payload[0]
        msg_bytes = payload[1:]
        # NEU: Tote Spieler koennen nicht in den Chat schreiben
        if in_meeting and len(msg_bytes) == msg_len and msg_len > 0 and player_id not in dead_players:
            # NEU: Davids Ziel wird verwuerfelt - ALLE Nachrichten, bis David jemand anderen waehlt
            if player_id in david_targets.values():
                try:
                    text = msg_bytes.decode("utf-8")
                    words = text.split(" ")
                    scrambled = []
                    for w in words:
                        if len(w) > 3:
                            chars = list(w)
                            mid = chars[1:-1]
                            random.shuffle(mid)
                            scrambled.append(chars[0] + "".join(mid) + chars[-1])
                        else:
                            scrambled.append(w)
                    new_bytes = " ".join(scrambled).encode("utf-8")[:120]
                    msg_bytes = new_bytes
                    msg_len = len(msg_bytes)
                except Exception:
                    pass
            broadcast_to_all(struct.pack("!BBB", 50, player_id, msg_len) + msg_bytes)

    # ===== ROLLEN-FÄHIGKEITEN =====

    # Evelyn: Fenster-Sabotage aktivieren
    elif packet == 60:
        # NEU: Evelyn waehlt gezielt EINEN Fensterraum aus (Index aus der Karte).
        # Der Raum bleibt WINDOW_HAZARD_DURATION offen und ist danach erst nach
        # EVELYN_COOLDOWN wieder ausloesbar.
        room_idx = struct.unpack("!B", payload)[0]
        now = time.time()
        if (game_active and player_roles.get(player_id) == "evelyn"
                and player_id not in dead_players
                and now - evelyn_last_use >= EVELYN_COOLDOWN):
            evelyn_last_use = now
            window_hazard_room = room_idx
            window_hazard_active_until = now + WINDOW_HAZARD_DURATION
            broadcast_to_all(struct.pack("!BB", 61, room_idx))

    # Selbstmeldung: an Evelyns Fensterfalle gestorben
    elif packet == 62:
        reported_room = struct.unpack("!B", payload)[0]
        if (game_active and not in_meeting and time.time() < window_hazard_active_until
                and reported_room == window_hazard_room
                and player_id not in dead_players and time.time() >= global_immortal_until):
            dead_players.add(player_id)
            # NEU: Evelyns Fensterfalle hinterlaesst jetzt eine ganz normale Leiche
            broadcast_to_all(struct.pack("!BBBBBB", 31, player_id, 0, 0, DEATH_FLAG_WINDOW, NO_KILLER))
            check_win_conditions()

    # Laurin: Aufgaben-Fortschritt sabotieren
    elif packet == 63:
        # NEU: Laurin geht zu einer konkreten Aufgabe und macht sie fuer ALLE Spieler
        # wieder unerledigt. Betroffen sind nur Spieler, die sie wirklich schon hatten.
        sabotage_task_idx = struct.unpack("!B", payload)[0]
        if (game_active and player_roles.get(player_id) == "laurin"
                and player_id not in dead_players
                and ability_uses.get(player_id, 0) > 0):
            affected = [pid for pid, done in player_completed_tasks.items()
                        if sabotage_task_idx in done]
            ability_uses[player_id] -= 1
            for pid in affected:
                player_completed_tasks[pid].discard(sabotage_task_idx)
            completed_crew_tasks = max(0, completed_crew_tasks - len(affected))
            broadcast_to_all(struct.pack("!BB", 64, sabotage_task_idx))
            broadcast_to_all(struct.pack("!BHH", 21, completed_crew_tasks, total_crew_tasks))

    # David: Ziel fuer Chat-Verwuerfelung markieren
    elif packet == 65:
        target_id = struct.unpack("!B", payload)[0]
        if game_active and player_roles.get(player_id) == "david" and target_id in clients:
            david_targets[player_id] = target_id   # ersetzt das vorherige Ziel

    # Noah: Falle platzieren (maximal NOAH_TRAP_LIMIT, die aelteste wird ersetzt)
    elif packet == 66:
        x, y = struct.unpack("!ii", payload)
        if game_active and player_roles.get(player_id) == "noah":
            own_traps = sorted(tid for tid, (oid, _tx, _ty) in active_traps.items() if oid == player_id)
            while len(own_traps) >= NOAH_TRAP_LIMIT:
                old_id = own_traps.pop(0)
                del active_traps[old_id]
                broadcast_to_all(struct.pack("!BH", 70, old_id))
            trap_id = next_trap_id % 65536
            next_trap_id += 1
            active_traps[trap_id] = (player_id, x, y)
            # NEU: Fallen sind fuer ALLE sichtbar (Paket 67)
            broadcast_to_all(struct.pack("!BHBii", 67, trap_id, player_id, x, y))

    # Vogelscheicher: Attrappe platzieren + unsichtbar werden
    elif packet == 68:
        x, y = struct.unpack("!ii", payload)
        if game_active and player_roles.get(player_id) == "vogelscheicher":
            invisible_until[player_id] = time.time() + INVISIBILITY_DURATION
            broadcast_to_all(struct.pack("!BBii", 69, player_id, x, y))

    # Pleschbergsteiger: Geist wiederbeleben
    elif packet == 73:
        target_id = struct.unpack("!B", payload)[0]
        if (game_active and player_roles.get(player_id) == "pleschbergsteiger"
                and ability_uses.get(player_id, 0) > 0
                and target_id in dead_players and target_id in clients):
            ability_uses[player_id] -= 1
            dead_players.discard(target_id)
            broadcast_to_all(struct.pack("!BB", 74, target_id))

    # Yoshi: Rolle eines Spielers aufdecken
    elif packet == 75:
        target_id = struct.unpack("!B", payload)[0]
        if (game_active and player_roles.get(player_id) == "yoshi"
                and ability_uses.get(player_id, 0) > 0 and target_id in clients):
            ability_uses[player_id] -= 1
            target_role_id = roles.role_id_of(player_roles.get(target_id))
            send_to(player_id, struct.pack("!BBBB", 76, target_id, team_byte_of(target_id), target_role_id))

    # Tappeihnachtsmann: Unsterblichkeit fuer alle aktivieren
    elif packet == 77:
        if (game_active and player_roles.get(player_id) == "tappeihnachtsmann"
                and ability_uses.get(player_id, 0) > 0):
            ability_uses[player_id] -= 1
            global_immortal_until = time.time() + IMMORTALITY_DURATION
            broadcast_to_all(struct.pack("!B", 78))

    # Ramona: Unterschrift faelschen, Rechte entziehen
    elif packet == 79:
        target_id = struct.unpack("!B", payload)[0]
        if (game_active and player_roles.get(player_id) == "ramona"
                and target_id in clients and target_id != player_id):
            now = time.time()
            if now - ramona_last_use >= RAMONA_FORGE_COOLDOWN:
                ramona_last_use = now
                player_rights[target_id] = max(0, player_rights.get(target_id, 3) - 1)
                broadcast_to_all(struct.pack("!BBB", 80, target_id, player_rights[target_id]))

    # Ramona: Sieg als Eigenständige beanspruchen
    elif packet == 81:
        if game_active and player_roles.get(player_id) == "ramona" and player_id not in dead_players:
            others_rights = [v for pid, v in player_rights.items() if pid != player_id and pid in clients]
            if others_rights and all(v <= 0 for v in others_rights):
                finish_game(struct.pack("!BB", 82, player_id))

def free_player_id():
    """FIX: Vergibt die kleinste freie ID (0..MAX_PLAYERS-1) statt immer weiter hochzuzaehlen.
    Vorher bekam der 16. Beitritt (z.B. nach Reconnects) ID 15+ -> es gibt nur 15 Spawnpunkte
    (IndexError beim Spielstart) und ab ID 255 stuerzte das Paket-Format ab."""
    for pid in range(MAX_PLAYERS):
        if pid not in clients:
            return pid
    return None

def detect_lan_ip():
    temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        temp.connect(("8.8.8.8", 80))
        return temp.getsockname()[0]
    except Exception:
        return "0.0.0.0"   # FIX: ohne Netzwerk-Route nicht abstuerzen, sondern auf allen Adressen lauschen
    finally:
        temp.close()

def register_client(conn, addr):
    global host_id
    conn.settimeout(HANDSHAKE_TIMEOUT)
    name_len = recv_exact(conn, 1)[0]
    # NEU: Prüfen, ob der Name leer ist. Wenn ja, nutze die ID.
    player_name = recv_exact(conn, name_len).decode("utf-8", errors="replace") if name_len > 0 else ""

    with state_lock:
        new_id = free_player_id()
        if new_id is None or game_active:
            # Raum voll oder Spiel laeuft schon -> Verbindung ablehnen
            conn.close()
            return
        if not player_name.strip():
            player_name = str(new_id)

        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conn.settimeout(SEND_TIMEOUT)
        # Erst die ID schicken - schlaegt das fehl, bleiben keine halben Eintraege zurueck
        conn.sendall(struct.pack("!B", new_id))

        player_names[new_id] = player_name.strip()[:24]
        player_positions[new_id] = (100 + new_id * 30, 100)
        send_locks[new_id] = threading.Lock()

        if len(clients) == 0: host_id = new_id
        clients[new_id] = conn
        log(f"Neue Verbindung von {addr} -> Player {new_id} ({player_names[new_id]})")

        send_lobby_update()
        send_to(new_id, struct.pack("!BI", 14, roles.bitmask_of(enabled_roles)))
        send_to(new_id, struct.pack("!BB", 12, imposter_count))
        send_to(new_id, settings_packet())
        if new_id == host_id:
            send_fixed_roles_to_host()
        emit_status()

    threading.Thread(target=handle_client, args=(conn, new_id), daemon=True).start()

def start_server(host=None, port=PORT):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        # FIX (Windows): SO_REUSEADDR erlaubt dort ZWEI Server auf demselben Port -
        # Spieler landeten dann im falschen (alten) Raum
        server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    host_ip = host if host else detect_lan_ip()

    server.bind((host_ip, port))
    server.listen(MAX_PLAYERS)

    log(f"Läuft auf {host_ip}:{port}")
    emit_status()

    while True:
        conn, addr = server.accept()
        # Handshake in eigenem Thread, damit ein haengender Client den Accept nicht blockiert
        def _register(c=conn, a=addr):
            try:
                register_client(c, a)
            except (ConnectionError, socket.timeout, OSError):
                # z.B. Erreichbarkeits-Test des Webservers oder abgebrochener Beitritt
                try: c.close()
                except: pass
            except Exception as e:
                log("ERROR beim Beitritt:", e)
                try: c.close()
                except: pass
        threading.Thread(target=_register, daemon=True).start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thalheimer is Among Us - Spielserver (ein Raum)")
    parser.add_argument("--host", default=None, help="IP zum Lauschen (Standard: eigene LAN-IP)")
    parser.add_argument("--port", type=int, default=PORT, help=f"TCP-Port (Standard: {PORT})")
    parser.add_argument("--room", default="", help="Raumcode (nur fuer Log-Ausgaben im Web-Modus)")
    args = parser.parse_args()
    ROOM_CODE = args.room
    try:
        start_server(args.host, args.port)
    except KeyboardInterrupt:
        sys.exit(0)
