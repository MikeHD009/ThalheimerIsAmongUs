import socket
import threading
import struct
import random
import time

import roles

PORT = 5555
MAX_PLAYERS = 15

clients = {}
player_positions = {}
player_names = {}

host_id = 0
player_id_counter = 0

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
# ROLLEN-SYSTEM: Server-Zustand
# =========================
RAMONA_MIN_PLAYERS = 4        # Ramona braucht genug Spieler, sonst wird sie nicht vergeben
MAX_IMPOSTERS = 3             # harte Obergrenze fuer die Imposter-Anzahl
IMMORTALITY_DURATION = 10.0   # Tappeihnachtsmann
WINDOW_HAZARD_DURATION = 20.0 # Evelyn
INVISIBILITY_DURATION = 8.0   # Vogelscheicher
RAMONA_FORGE_COOLDOWN = 10.0  # Ramona
TRAP_HIT_RADIUS = 20          # Noah
NOAH_TRAP_LIMIT = 3           # Noah: hoechstens 3 gleichzeitige Fallen, die aelteste wird ersetzt
EVELYN_COOLDOWN = 30.0        # Evelyn: alle 30s ein Fensterraum sabotierbar
MEETING_DISCUSSION_TIME = 45.0  # Reine Chat-Phase vor der Abstimmung
MEETING_VOTE_TIME = 30.0        # Danach kann abgestimmt werden

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
chat_scramble_armed = set()    # pids deren naechste Chat-Nachricht verwuerfelt wird (David)
global_immortal_until = 0.0    # Zeitstempel bis wann NIEMAND sterben kann (Tappeihnachtsmann)
window_hazard_active_until = 0.0  # Zeitstempel bis wann Evelyns Fenster-Falle aktiv ist
window_hazard_room = 255       # Index des aktuell geoeffneten Fensterraums (255 = keiner)
evelyn_last_use = 0.0          # Zeitstempel der letzten Fenster-Sabotage
player_completed_tasks = {}    # pid -> Set erledigter Task-Indizes (fuer Laurins Sabotage)
meeting_phase = 0              # 0 = kein Meeting, 1 = Diskussion, 2 = Abstimmung


def max_imposters_for(n_players):
    """Obergrenze fuer die Imposter-Anzahl: es muss immer mindestens ein Crewmate uebrig
    bleiben und es muss mehr freundliche als feindliche Spieler geben."""
    if n_players < 3:
        return 1
    return max(1, min(MAX_IMPOSTERS, (n_players - 1) // 2))

def role_setup_status():
    """Autoritative Pruefung der Rollen-Konfiguration (dieselben Regeln wie im Client):
      - Mindestens ein Imposter / eine feindliche Rolle ist Pflicht.
      - Mindestens ein Crewmate ist Pflicht.
      - Es muss mehr freundliche als feindliche Spieler geben (Imposter zaehlen feindlich).
      - Nicht mehr feindliche Spezialrollen als Imposter-Plaetze.
      - Jede Spezialrolle hoechstens einmal, alle Rollen zusammen <= Spielerzahl.
    Rueckgabe: (ok, meldung)"""
    n_players = len(clients)
    friendly_n = sum(1 for k in enabled_roles if roles.team_of(k) == roles.TEAM_CREW)
    enemy_n = sum(1 for k in enabled_roles if roles.team_of(k) == roles.TEAM_IMPOSTOR)
    independent_n = sum(1 for k in enabled_roles if roles.team_of(k) == roles.TEAM_INDEPENDENT)

    if n_players < 2:
        return False, "Zu wenige Spieler verbunden"
    if imposter_count < 1:
        return False, "Mindestens ein Imposter ist Pflicht"
    if enemy_n > imposter_count:
        return False, f"Zu viele feindliche Rollen ({enemy_n}) fuer {imposter_count} Imposter"

    ind_slots = independent_n if n_players >= RAMONA_MIN_PLAYERS else 0
    crew_slots = n_players - imposter_count - ind_slots
    if crew_slots < 1:
        return False, "Mindestens ein Crewmate ist Pflicht"
    if crew_slots <= imposter_count:
        return False, "Es muessen mehr freundliche als feindliche Spieler sein"
    if friendly_n > crew_slots:
        return False, f"Zu viele freundliche Rollen ({friendly_n}) fuer {crew_slots} Besatzungsplaetze"
    return True, "ok"

def start_voting_phase():
    """NEU: Nach der reinen Chat-/Diskussionszeit wird die Abstimmung freigeschaltet."""
    global meeting_phase, meeting_timer_obj
    if not in_meeting:
        return
    meeting_phase = 2
    broadcast_to_all(struct.pack("!B", 42))
    meeting_timer_obj = threading.Timer(MEETING_VOTE_TIME, end_meeting)
    meeting_timer_obj.start()

def end_meeting():
    """Wertet die Stimmen aus, wirft ggf. einen Spieler raus und beendet das Meeting."""
    global in_meeting, meeting_phase
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

    if not tie and evicted_id != 255 and time.time() >= global_immortal_until:
        dead_players.add(evicted_id)
        broadcast_to_all(struct.pack("!BBBBB", 31, evicted_id, 0, 0, 0))
        check_win_conditions()

    in_meeting = False
    meeting_phase = 0
    # Ergebnis mitschicken: 255 = niemand rausgeworfen (Skip oder Gleichstand)
    broadcast_to_all(struct.pack("!BB", 43, evicted_id if not tie else 255))

def send_lobby_update():
    player_count = len(clients)
    for pid, conn in list(clients.items()):
        try:
            conn.sendall(struct.pack("!BBB", 1, player_count, host_id))
            for other_id, name in player_names.items():
                name_bytes = name.encode()
                conn.sendall(struct.pack(f"!BB{len(name_bytes)}s", other_id, len(name_bytes), name_bytes))
        except:
            disconnect(player_id=pid)

def broadcast_to_all(data, exclude_id=None):
    for pid, conn in list(clients.items()):
        if pid != exclude_id:
            try:
                conn.sendall(data)
            except:
                disconnect(pid)

# NEU: Helfer-Funktion zum Checken der Imposter-Siegbedingungen
def check_win_conditions():
    global game_active
    if not game_active: return

    alive_imps = sum(1 for pid, team in player_base_team.items()
                      if team == roles.TEAM_IMPOSTOR and pid not in dead_players and pid in clients)
    alive_crew = sum(1 for pid, team in player_base_team.items()
                      if team == roles.TEAM_CREW and pid not in dead_players and pid in clients)

    # Imposter gewinnen, wenn gleich viele oder mehr Imposter als Crewmates leben
    # (Eigenständige zaehlen weder zu Imposter noch zu Crew)
    if alive_imps >= alive_crew and alive_crew > 0:
        game_active = False
        imp_ids = [pid for pid, team in player_base_team.items() if team == roles.TEAM_IMPOSTOR]
        win_packet = struct.pack("!BB", 32, len(imp_ids))
        for imp_id in imp_ids:
            win_packet += struct.pack("!B", imp_id)
        broadcast_to_all(win_packet)

def disconnect(player_id):
    global host_id

    print(f"[SERVER] Player {player_id} disconnected")

    if player_id in clients:
        try: clients[player_id].close()
        except: pass
        del clients[player_id]
    if player_id in player_names: del player_names[player_id]
    if player_id in player_positions: del player_positions[player_id]

    disconnect_packet = struct.pack("!BBii", 4, player_id, -1000, -1000)
    broadcast_to_all(disconnect_packet)

    if player_id == host_id:
        if len(clients) > 0: host_id = list(clients.keys())[0]
        else: host_id = 0

    # Falls Spieler verlässt, Win Conditions neu evaluieren
    check_win_conditions()
    send_lobby_update()

def handle_client(conn, player_id):
    global host_id, total_crew_tasks, completed_crew_tasks, game_active
    global player_base_team, player_roles, ability_uses, player_rights
    global ramona_id, ramona_last_use, active_traps, next_trap_id
    global invisible_until, chat_scramble_armed, global_immortal_until, window_hazard_active_until
    global window_hazard_room, evelyn_last_use, player_completed_tasks
    global active_imposters, imposter_count
    global in_meeting, meeting_timer_obj, meeting_phase

    print(f"[SERVER] Thread gestartet für Player {player_id}")
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    try:
        while True:
            data = conn.recv(1)
            if not data: break
            packet = struct.unpack("!B", data)[0]

            if packet == 10:
                for c in list(clients.values()):
                    try: c.sendall(struct.pack("!B", 10))
                    except: pass

            elif packet == 11:
                new_count = struct.unpack("!B", conn.recv(1))[0]
                # Nie mehr Imposter als freundliche Spieler zulassen
                imposter_count = max(1, min(new_count, max_imposters_for(len(clients))))
                broadcast_to_all(struct.pack("!BB", 12, imposter_count))

            # NEU: Host togglet eine Custom-Rolle an/aus
            elif packet == 13:
                role_id, enabled_flag = struct.unpack("!BB", conn.recv(2))
                if player_id == host_id:
                    key = roles.role_key_of(role_id)
                    if key is not None:
                        if enabled_flag:
                            enabled_roles.add(key)
                        else:
                            enabled_roles.discard(key)
                broadcast_to_all(struct.pack("!BI", 14, roles.bitmask_of(enabled_roles)))

            elif packet == 99:
                print(f"[SERVER] Gameplay aktiviert von {player_id}")

                enemy_keys = [k for k in enabled_roles if roles.team_of(k) == roles.TEAM_IMPOSTOR]
                friendly_keys = [k for k in enabled_roles if roles.team_of(k) == roles.TEAM_CREW]
                setup_ok, setup_msg = role_setup_status()
                if not setup_ok:
                    print(f"[SERVER] Rollen-Konfiguration ungueltig ({setup_msg}), Start abgebrochen")
                    continue

                dead_players.clear()
                game_active = True

                pool = list(clients.keys())

                player_base_team = {}
                player_roles = {}
                ability_uses = {}
                player_rights = {}
                active_traps = {}
                next_trap_id = 0
                invisible_until = {}
                chat_scramble_armed = set()
                global_immortal_until = 0.0
                window_hazard_active_until = 0.0
                window_hazard_room = 255
                evelyn_last_use = 0.0
                player_completed_tasks = {pid: set() for pid in clients}
                ramona_last_use = 0.0
                ramona_id = None

                # 1) Eigenständig (Ramona) -- nur wenn aktiviert und genug Spieler da sind
                if "ramona" in enabled_roles and len(pool) >= RAMONA_MIN_PLAYERS:
                    ramona_id = random.choice(pool)
                    pool.remove(ramona_id)
                    player_base_team[ramona_id] = roles.TEAM_INDEPENDENT
                    player_roles[ramona_id] = "ramona"

                # 2) Imposter-Team (Anzahl wie bisher ueber imposter_count gesteuert)
                max_imps = max(1, min(imposter_count, len(pool) - 1)) if len(pool) > 1 else 0
                imposter_ids = random.sample(pool, max_imps) if max_imps > 0 else []
                for pid in imposter_ids:
                    pool.remove(pid)
                    player_base_team[pid] = roles.TEAM_IMPOSTOR
                active_imposters = list(imposter_ids)

                # 3) Rest ist Besatzung
                crew_ids = list(pool)
                for pid in crew_ids:
                    player_base_team[pid] = roles.TEAM_CREW

                # 4) Konkrete aktivierte Rollen ohne Zuruecklegen auf die Slots verteilen
                avail_enemy = list(enemy_keys)
                random.shuffle(avail_enemy)
                for pid in imposter_ids:
                    player_roles[pid] = avail_enemy.pop() if avail_enemy else None

                avail_friendly = list(friendly_keys)
                random.shuffle(avail_friendly)
                for pid in crew_ids:
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

                modifiers = 1 if "vladimir" in enabled_roles else 0

                # NEU: Paket 15 traegt die Imposter-Teamliste und geht AUSSCHLIESSLICH an die
                # Imposter selbst - damit sie wissen, wer ihre Teammates sind. Es muss nach
                # Paket 5 (Rollenzuweisung) und vor Paket 3 (Spielstart) verschickt werden.
                imposter_team_packet = struct.pack("!BB", 15, len(imposter_ids))
                for imp_id in imposter_ids:
                    imposter_team_packet += struct.pack("!B", imp_id)

                for pid, c in list(clients.items()):
                    try:
                        base_team = player_base_team.get(pid, roles.TEAM_CREW)
                        base_team_byte = 1 if base_team == roles.TEAM_IMPOSTOR else (2 if base_team == roles.TEAM_INDEPENDENT else 0)
                        role_id = roles.role_id_of(player_roles.get(pid))
                        c.sendall(struct.pack("!BBB", 5, base_team_byte, role_id))
                        if pid in imposter_ids:
                            c.sendall(imposter_team_packet)
                        c.sendall(struct.pack("!BB", 3, modifiers))
                    except:
                        disconnect(pid)

            elif packet == 20:
                # NEU: Der Client schickt jetzt mit, WELCHE Aufgabe erledigt wurde (255 = keine
                # Karten-Aufgabe, z.B. Raphis Pfandflaschen). Nur so kann Laurin gezielt eine
                # Aufgabe fuer alle wieder zuruecksetzen.
                done_task_idx = struct.unpack("!B", conn.recv(1))[0]
                if player_roles.get(player_id) != "felix":
                    completed_crew_tasks += 1
                    if done_task_idx != 255:
                        player_completed_tasks.setdefault(player_id, set()).add(done_task_idx)
                broadcast_to_all(struct.pack("!BHH", 21, completed_crew_tasks, total_crew_tasks))

                if completed_crew_tasks >= total_crew_tasks and game_active:
                    game_active = False
                    win_packet = struct.pack("!BB", 22, len(active_imposters))
                    for imp_id in active_imposters:
                        win_packet += struct.pack("!B", imp_id)
                    broadcast_to_all(win_packet)

            # NEU: Kill-Paket verarbeiten
            elif packet == 30:
                target_id = struct.unpack("!B", conn.recv(1))[0]
                if (player_id in active_imposters and player_id not in dead_players
                        and time.time() >= global_immortal_until):
                    if target_id not in dead_players and target_id not in active_imposters:
                        dead_players.add(target_id)
                        killer_role = player_roles.get(player_id)
                        no_corpse = 1 if killer_role == "steinermike" else 0
                        weapon_id = 1 if killer_role == "martin" else 0
                        # NEU: Bit 0 = das Opfer wurde von Vladimir getoetet -> Anime-Intro abspielen
                        death_flags = 1 if killer_role == "vladimir" else 0
                        broadcast_to_all(struct.pack("!BBBBB", 31, target_id, no_corpse, weapon_id, death_flags))
                        check_win_conditions()

            elif packet == 23:
                if player_id == host_id:
                    game_active = False
                    broadcast_to_all(struct.pack("!B", 23))

            elif packet == 2:
                buffer = b""
                while len(buffer) < 8:
                    chunk = conn.recv(8 - len(buffer))
                    if not chunk: break
                    buffer += chunk
                if len(buffer) < 8: break

                x, y = struct.unpack("!ii", buffer)
                player_positions[player_id] = (x, y)

                # Noah: Fallenkollision pruefen
                if (game_active and player_id not in dead_players
                        and time.time() >= global_immortal_until and active_traps):
                    for trap_id, (owner_id, tx, ty) in list(active_traps.items()):
                        if owner_id != player_id and abs(x - tx) < TRAP_HIT_RADIUS and abs(y - ty) < TRAP_HIT_RADIUS:
                            del active_traps[trap_id]
                            dead_players.add(player_id)
                            broadcast_to_all(struct.pack("!BBBBB", 31, player_id, 0, 0, 0))
                            check_win_conditions()
                            break

                # Vogelscheicher: waehrend Unsichtbarkeit Position nicht an andere weiterleiten
                if time.time() < invisible_until.get(player_id, 0):
                    pass
                else:
                    broadcast_to_all(struct.pack("!BBii", 2, player_id, x, y), exclude_id=player_id)

            elif packet == 40:
                reason = struct.unpack("!B", conn.recv(1))[0]
                # NEU: Kaliyoga darf einmal pro Spiel von ueberall aus ein Meeting rufen -
                # das wird hier autoritativ geprueft und verbraucht.
                allowed = game_active and not in_meeting and player_id not in dead_players
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
                    meeting_timer_obj = threading.Timer(MEETING_DISCUSSION_TIME, start_voting_phase)
                    meeting_timer_obj.start()

            elif packet == 41:
                target_id = struct.unpack("!B", conn.recv(1))[0]
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
                msg_len = struct.unpack("!B", conn.recv(1))[0]
                msg_bytes = b""
                while len(msg_bytes) < msg_len:
                    chunk = conn.recv(msg_len - len(msg_bytes))
                    if not chunk: break
                    msg_bytes += chunk
                if in_meeting and len(msg_bytes) == msg_len and msg_len > 0:
                    if player_id in chat_scramble_armed:
                        chat_scramble_armed.discard(player_id)
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
                room_idx = struct.unpack("!B", conn.recv(1))[0]
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
                reported_room = struct.unpack("!B", conn.recv(1))[0]
                if (game_active and time.time() < window_hazard_active_until
                        and reported_room == window_hazard_room
                        and player_id not in dead_players and time.time() >= global_immortal_until):
                    dead_players.add(player_id)
                    # NEU: Evelyns Fensterfalle hinterlaesst jetzt eine ganz normale Leiche
                    broadcast_to_all(struct.pack("!BBBBB", 31, player_id, 0, 0, 0))
                    check_win_conditions()

            # Laurin: Aufgaben-Fortschritt sabotieren
            elif packet == 63:
                # NEU: Laurin geht zu einer konkreten Aufgabe und macht sie fuer ALLE Spieler
                # wieder unerledigt. Betroffen sind nur Spieler, die sie wirklich schon hatten.
                sabotage_task_idx = struct.unpack("!B", conn.recv(1))[0]
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
                target_id = struct.unpack("!B", conn.recv(1))[0]
                if game_active and player_roles.get(player_id) == "david" and target_id in clients:
                    chat_scramble_armed.add(target_id)

            # Noah: Falle platzieren (maximal NOAH_TRAP_LIMIT, die aelteste wird ersetzt)
            elif packet == 66:
                x, y = struct.unpack("!ii", conn.recv(8))
                if game_active and player_roles.get(player_id) == "noah":
                    own_traps = sorted(tid for tid, (oid, _tx, _ty) in active_traps.items() if oid == player_id)
                    while len(own_traps) >= NOAH_TRAP_LIMIT:
                        del active_traps[own_traps.pop(0)]
                    trap_id = next_trap_id
                    next_trap_id += 1
                    active_traps[trap_id] = (player_id, x, y)

            # Vogelscheicher: Attrappe platzieren + unsichtbar werden
            elif packet == 68:
                x, y = struct.unpack("!ii", conn.recv(8))
                if game_active and player_roles.get(player_id) == "vogelscheicher":
                    invisible_until[player_id] = time.time() + INVISIBILITY_DURATION
                    broadcast_to_all(struct.pack("!BBii", 69, player_id, x, y))

            # Pleschbergsteiger: Geist wiederbeleben
            elif packet == 73:
                target_id = struct.unpack("!B", conn.recv(1))[0]
                if (game_active and player_roles.get(player_id) == "pleschbergsteiger"
                        and ability_uses.get(player_id, 0) > 0
                        and target_id in dead_players and target_id in clients):
                    ability_uses[player_id] -= 1
                    dead_players.discard(target_id)
                    broadcast_to_all(struct.pack("!BB", 74, target_id))

            # Yoshi: Rolle eines Spielers aufdecken
            elif packet == 75:
                target_id = struct.unpack("!B", conn.recv(1))[0]
                if (game_active and player_roles.get(player_id) == "yoshi"
                        and ability_uses.get(player_id, 0) > 0 and target_id in clients):
                    ability_uses[player_id] -= 1
                    target_team = player_base_team.get(target_id, roles.TEAM_CREW)
                    team_byte = 1 if target_team == roles.TEAM_IMPOSTOR else (2 if target_team == roles.TEAM_INDEPENDENT else 0)
                    target_role_id = roles.role_id_of(player_roles.get(target_id))
                    try:
                        conn.sendall(struct.pack("!BBBB", 76, target_id, team_byte, target_role_id))
                    except:
                        pass

            # Tappeihnachtsmann: Unsterblichkeit fuer alle aktivieren
            elif packet == 77:
                if (game_active and player_roles.get(player_id) == "tappeihnachtsmann"
                        and ability_uses.get(player_id, 0) > 0):
                    ability_uses[player_id] -= 1
                    global_immortal_until = time.time() + IMMORTALITY_DURATION
                    broadcast_to_all(struct.pack("!B", 78))

            # Ramona: Unterschrift faelschen, Rechte entziehen
            elif packet == 79:
                target_id = struct.unpack("!B", conn.recv(1))[0]
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
                        game_active = False
                        broadcast_to_all(struct.pack("!BB", 82, player_id))

            # Beim Zurücksetzen der Lobby (Paket 23) oder Match-Start (99) Timer abbrechen:
            if packet == 23 or packet == 99:
                if meeting_timer_obj:
                    meeting_timer_obj.cancel()
                in_meeting = False
                meeting_phase = 0

    except Exception as e:
        print(f"[SERVER ERROR] Player {player_id}: {e}")

    disconnect(player_id)

def start_server():
    global player_id_counter, host_id

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        temp.connect(("8.8.8.8", 80))
        host_ip = temp.getsockname()[0]
    finally:
        temp.close()

    server.bind((host_ip, PORT))
    server.listen(MAX_PLAYERS)

    print(f"[SERVER] Läuft auf {host_ip}:{PORT}")

    while True:
        conn, addr = server.accept()
        if len(clients) >= MAX_PLAYERS:
            conn.close()
            continue

        print(f"[SERVER] Neue Verbindung von {addr}")

        try:
            name_len = struct.unpack("!B", conn.recv(1))[0]
            # NEU: Prüfen, ob der Name leer ist. Wenn ja, nutze die ID.
            if name_len > 0:
                player_name = conn.recv(name_len).decode()
            else:
                player_name = ""

            if not player_name.strip():
                player_name = str(player_id_counter)

            player_names[player_id_counter] = player_name
            player_positions[player_id_counter] = (100 + player_id_counter * 30, 100)

            if len(clients) == 0: host_id = player_id_counter

            conn.sendall(struct.pack("!B", player_id_counter))
            clients[player_id_counter] = conn

            send_lobby_update()
            try:
                conn.sendall(struct.pack("!BI", 14, roles.bitmask_of(enabled_roles)))
            except:
                pass

            threading.Thread(target=handle_client, args=(conn, player_id_counter), daemon=True).start()
            player_id_counter += 1

        except Exception as e:
            print("[SERVER ERROR]", e)
            conn.close()

if __name__ == "__main__":
    start_server()
