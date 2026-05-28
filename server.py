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

total_crew_tasks = 0
completed_crew_tasks = 0

# =========================
# LOBBY UPDATE
# =========================
def send_lobby_update():
    player_count = len(clients)

    for pid, conn in list(clients.items()):
        try:
            # packet_type=1, player_count, host_id
            conn.sendall(struct.pack("!BBB", 1, player_count, host_id))

            # Alle Spielernamen senden
            for other_id, name in player_names.items():
                name_bytes = name.encode()

                conn.sendall(
                    struct.pack(
                        f"!BB{len(name_bytes)}s",
                        other_id,
                        len(name_bytes),
                        name_bytes
                    )
                )

        except:
            disconnect(player_id=pid)

# =========================
# BROADCAST
# =========================
def broadcast_to_all(data, exclude_id=None):
    for pid, conn in list(clients.items()):
        if pid != exclude_id:
            try:
                conn.sendall(data)
            except:
                disconnect(pid)

# =========================
# DISCONNECT
# =========================
def disconnect(player_id):
    global host_id

    print(f"[SERVER] Player {player_id} disconnected")

    if player_id in clients:
        try:
            clients[player_id].close()
        except:
            pass

        del clients[player_id]

    if player_id in player_names:
        del player_names[player_id]

    if player_id in player_positions:
        del player_positions[player_id]

    # Disconnect Packet senden
    disconnect_packet = struct.pack(
        "!BBii",
        4,              # packet type
        player_id,
        -1000,
        -1000
    )

    broadcast_to_all(disconnect_packet)

    # Neuer Host wenn Host disconnected
    if player_id == host_id:
        if len(clients) > 0:
            host_id = list(clients.keys())[0]
        else:
            host_id = 0

    send_lobby_update()

# =========================
# CLIENT THREAD
# =========================
def handle_client(conn, player_id):
    global host_id, total_crew_tasks, completed_crew_tasks

    print(f"[SERVER] Thread gestartet für Player {player_id}")

    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    try:
        while True:
            data = conn.recv(1)

            if not data:
                break

            packet = struct.unpack("!B", data)[0]

            print(f"[SERVER] Packet {packet} von {player_id}")

            # =========================
            # START BUTTON
            # =========================
            if packet == 10:
                print("[SERVER] Host hat Start gedrückt")

                for c in list(clients.values()):
                    try:
                        c.sendall(struct.pack("!B", 10))
                    except:
                        pass

            # =========================
            # LOBBY EINSTELLUNGEN (NEU)
            # =========================
            elif packet == 11:
                new_count = struct.unpack("!B", conn.recv(1))[0]
                global imposter_count
                imposter_count = max(1, min(new_count, 3)) # Maximal 3 Imposter
                
                # An alle Clients senden (Paket 12)
                update_packet = struct.pack("!BB", 12, imposter_count)
                broadcast_to_all(update_packet)

            # =========================
            # GAMEPLAY START
            # =========================
            elif packet == 99:
                print(f"[SERVER] Gameplay aktiviert von {player_id}")
                
                # Imposter zufällig bestimmen
                # Wenn wir alleine testen (1 Spieler), gibt es 0 Imposter, ansonsten das Minimum aus gewünschten Impostern und (Spielerzahl - 1)
                max_imps = max(1, min(imposter_count, len(clients) - 1)) if len(clients) > 1 else 0
                imposter_ids = random.sample(list(clients.keys()), max_imps) if max_imps > 0 else []
                active_imposters = imposter_ids

                # NEU: Jedes Crewmitglied bekommt 10 Tasks
                total_crew_tasks = max(1, (len(clients) - max_imps) * 10)
                completed_crew_tasks = 0

                for pid, c in list(clients.items()):
                    try:
                        # 1 = Imposter, 0 = Crewmate
                        role = 1 if pid in imposter_ids else 0
                        # Paket 5: Rolle zuweisen
                        c.sendall(struct.pack("!BB", 5, role))
                        # Paket 3: Spiel starten
                        c.sendall(struct.pack("!B", 3))
                    except:
                        disconnect(pid)

            # =========================
            # TASK UPDATE & WIN CHECK
            # =========================
            elif packet == 20: # Task wurde gelöst
                completed_crew_tasks += 1
                
                # Paket 21: Sende neuen Fortschritt an alle
                update_packet = struct.pack("!BHH", 21, completed_crew_tasks, total_crew_tasks)
                broadcast_to_all(update_packet)
                
                # Wenn alle Tasks fertig sind -> Crew gewinnt (Paket 22)
                if completed_crew_tasks >= total_crew_tasks:
                    win_packet = struct.pack("!BB", 22, len(active_imposters))
                    for imp_id in active_imposters:
                        win_packet += struct.pack("!B", imp_id)
                    broadcast_to_all(win_packet)

            # =========================
            # RÜCKKEHR ZUR LOBBY (Ganz NEU hinzufügen)
            # =========================
            elif packet == 23:
                if player_id == host_id:
                    # Befehl an alle Clients senden, in die Lobby zurückzukehren
                    broadcast_to_all(struct.pack("!B", 23))

            # =========================
            # POSITION UPDATE
            # =========================
            elif packet == 2:

                buffer = b""

                while len(buffer) < 8:
                    chunk = conn.recv(8 - len(buffer))

                    if not chunk:
                        break

                    buffer += chunk

                if len(buffer) < 8:
                    break

                x, y = struct.unpack("!ii", buffer)

                player_positions[player_id] = (x, y)

                update_packet = struct.pack(
                    "!BBii",
                    2,
                    player_id,
                    x,
                    y
                )

                broadcast_to_all(
                    update_packet,
                    exclude_id=player_id
                )

    except Exception as e:
        print(f"[SERVER ERROR] Player {player_id}: {e}")

    disconnect(player_id)

# =========================
# SERVER START
# =========================
def start_server():
    global player_id_counter
    global host_id

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Eigene IP automatisch holen
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
            # Namen empfangen
            name_len = struct.unpack("!B", conn.recv(1))[0]

            player_name = conn.recv(name_len).decode()

            player_names[player_id_counter] = player_name

            # Startposition
            player_positions[player_id_counter] = (
                100 + player_id_counter * 30,
                100
            )

            # Erster Spieler = Host
            if len(clients) == 0:
                host_id = player_id_counter

            # ID senden
            conn.sendall(
                struct.pack("!B", player_id_counter)
            )

            clients[player_id_counter] = conn

            send_lobby_update()

            threading.Thread(
                target=handle_client,
                args=(conn, player_id_counter),
                daemon=True
            ).start()

            print(
                f"[SERVER] Player '{player_name}' erhielt ID {player_id_counter}"
            )

            player_id_counter += 1

        except Exception as e:
            print("[SERVER ERROR]", e)
            conn.close()

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    start_server()