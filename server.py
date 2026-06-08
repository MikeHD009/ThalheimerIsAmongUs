import socket
import threading
import struct
import random

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

    alive_imps = sum(1 for pid in active_imposters if pid not in dead_players and pid in clients)
    alive_crew = sum(1 for pid in clients if pid not in active_imposters and pid not in dead_players)
    
    # Imposter gewinnen, wenn gleich viele oder mehr Imposter als Crewmates leben
    if alive_imps >= alive_crew and alive_crew > 0:
        game_active = False
        win_packet = struct.pack("!BB", 32, len(active_imposters))
        for imp_id in active_imposters:
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
                global imposter_count
                imposter_count = max(1, min(new_count, 3))
                broadcast_to_all(struct.pack("!BB", 12, imposter_count))

            elif packet == 99:
                print(f"[SERVER] Gameplay aktiviert von {player_id}")
                dead_players.clear()
                game_active = True
                
                max_imps = max(1, min(imposter_count, len(clients) - 1)) if len(clients) > 1 else 0
                imposter_ids = random.sample(list(clients.keys()), max_imps) if max_imps > 0 else []
                global active_imposters
                active_imposters = imposter_ids

                total_crew_tasks = max(1, (len(clients) - max_imps) * 10)
                completed_crew_tasks = 0

                for pid, c in list(clients.items()):
                    try:
                        role = 1 if pid in imposter_ids else 0
                        c.sendall(struct.pack("!BB", 5, role))
                        c.sendall(struct.pack("!B", 3))
                    except:
                        disconnect(pid)

            elif packet == 20: 
                completed_crew_tasks += 1
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
                if player_id in active_imposters and player_id not in dead_players:
                    if target_id not in dead_players and target_id not in active_imposters:
                        dead_players.add(target_id)
                        broadcast_to_all(struct.pack("!BB", 31, target_id))
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
                broadcast_to_all(struct.pack("!BBii", 2, player_id, x, y), exclude_id=player_id)

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

            threading.Thread(target=handle_client, args=(conn, player_id_counter), daemon=True).start()
            player_id_counter += 1

        except Exception as e:
            print("[SERVER ERROR]", e)
            conn.close()

if __name__ == "__main__":
    start_server()