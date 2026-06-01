import socket
import threading
import struct
import random
import time

PORT = 5555
MAX_PLAYERS = 15

clients = {}
player_positions = {}
player_names = {}

host_id = 0
player_id_counter = 0

imposter_count = 1
active_imposters = []
dead_players = set() 
game_active = False  

total_crew_tasks = 0
completed_crew_tasks = 0

meeting_active = False
votes = {}

server_lock = threading.RLock()

# ========================================================
# THREAD-SICHERE NETZWERK-FUNKTIONEN (NUR NOCH EINMAL DA!)
# ========================================================
def broadcast_to_all(data, exclude_id=None):
    with server_lock:  
        for pid, conn in list(clients.items()):
            if pid != exclude_id:
                try:
                    conn.sendall(data)
                except:
                    disconnect(pid)

def disconnect(player_id):
    global host_id
    with server_lock:  
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

        check_win_conditions()
        send_lobby_update()

def send_lobby_update():
    with server_lock:
        player_count = len(clients)
        for pid, conn in list(clients.items()):
            try:
                conn.sendall(struct.pack("!BBB", 1, player_count, host_id))
                for other_id, name in player_names.items():
                    name_bytes = name.encode()
                    conn.sendall(struct.pack(f"!BB{len(name_bytes)}s", other_id, len(name_bytes), name_bytes))
            except:
                disconnect(pid)

def recv_exact(conn, num_bytes):
    buffer = b""
    while len(buffer) < num_bytes:
        chunk = conn.recv(num_bytes - len(buffer))
        if not chunk:
            raise ConnectionResetError("Client hat die Verbindung getrennt.")
        buffer += chunk
    return buffer

def check_win_conditions():
    global game_active
    if not game_active: return

    alive_imps = sum(1 for pid in active_imposters if pid not in dead_players and pid in clients)
    alive_crew = sum(1 for pid in clients if pid not in active_imposters and pid not in dead_players)
    
    if alive_imps >= alive_crew and alive_crew > 0:
        game_active = False
        win_packet = struct.pack("!BB", 32, len(active_imposters))
        for imp_id in active_imposters:
            win_packet += struct.pack("!B", imp_id)
        broadcast_to_all(win_packet)

def meeting_manager():
    global meeting_active, game_active
    
    time.sleep(20) # Chat Phase
    broadcast_to_all(struct.pack("!B", 43)) # Voting Phase freischalten
    time.sleep(30) # Voting Phase
    
    with server_lock:
        vote_counts = {}
        for v in votes.values():
            vote_counts[v] = vote_counts.get(v, 0) + 1
            
        ejected_id = 255 
        if vote_counts:
            max_votes = max(vote_counts.values())
            winners = [k for k, v in vote_counts.items() if v == max_votes]
            
            if len(winners) == 1 and winners[0] != 255:
                ejected_id = winners[0]
                dead_players.add(ejected_id)
                
        meeting_active = False
        broadcast_to_all(struct.pack("!BB", 42, ejected_id))
        check_win_conditions()

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
                broadcast_to_all(struct.pack("!B", 10))

            elif packet == 11:
                new_count = struct.unpack("!B", recv_exact(conn, 1))[0]
                global imposter_count
                imposter_count = max(1, min(new_count, 3))
                broadcast_to_all(struct.pack("!BB", 12, imposter_count))

            elif packet == 99:
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

            elif packet == 30:
                target_id = struct.unpack("!B", recv_exact(conn, 1))[0]
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
                # Koordinaten (X und Y) einlesen (8 Bytes)
                buffer = recv_exact(conn, 8)
                x, y = struct.unpack("!ii", buffer)
                player_positions[player_id] = (x, y)
                broadcast_to_all(struct.pack("!BBii", 2, player_id, x, y), exclude_id=player_id)

            elif packet == 40: 
                if not meeting_active and player_id not in dead_players:
                    meeting_active = True
                    votes.clear()
                    broadcast_to_all(struct.pack("!BB", 40, player_id))
                    threading.Thread(target=meeting_manager, daemon=True).start()
                    
            elif packet == 41: 
                target_id = struct.unpack("!B", recv_exact(conn, 1))[0]
                if player_id not in dead_players:
                    with server_lock:
                        votes[player_id] = target_id

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

        try:
            name_len = struct.unpack("!B", conn.recv(1))[0]
            player_name = conn.recv(name_len).decode() if name_len > 0 else str(player_id_counter)
            if not player_name.strip(): player_name = str(player_id_counter)
                
            player_names[player_id_counter] = player_name
            player_positions[player_id_counter] = (100, 100)

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