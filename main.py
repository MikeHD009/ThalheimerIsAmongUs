import pygame
import socket
import threading
import struct
import math
import json
import sys
import os

import tasks
# HINWEIS: MeetingSystem aus Meeting.py wird nicht mehr eingebunden, siehe Kommentar weiter unten
# bei der Initialisierung der Meeting-Variablen.

# =========================
# EINSTELLUNGEN & KONSTANTEN
# =========================
TILE_SIZE = 24
TILES_VISIBLE = 15
INTERNAL_SIZE = TILE_SIZE * TILES_VISIBLE  # 360x360 Pixel Renderfläche
PLAYER_SPEED = 3
PORT = 5555

VISION_RADIUS = 7.2 * TILE_SIZE  # 6 Tiles Sichtweite
FADE_SPEED = 15                # Wie schnell die Deckkraft (0-255) pro Frame steigt/fällt
player_visibility = {}

pygame.init()

# Hauptfenster auf VOLLBILD setzen und Auflösung automatisch ermitteln
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
WIDTH = screen.get_width()
HEIGHT = screen.get_height()

pygame.display.set_caption("Thalheimer is Among Us")
clock = pygame.time.Clock()

internal_surface = pygame.Surface((INTERNAL_SIZE, INTERNAL_SIZE))

fog_overlay = pygame.Surface((INTERNAL_SIZE, INTERNAL_SIZE))
fog_overlay.fill((0, 0, 0))
pygame.draw.circle(fog_overlay, (255, 255, 255), (INTERNAL_SIZE // 2, INTERNAL_SIZE // 2), VISION_RADIUS)
fog_overlay.set_colorkey((255, 255, 255))

# =========================
# BILDER LADEN & SKALIEREN
# =========================
PLAYER_SIZE = int(TILE_SIZE * 0.6)
PLAYER_COLORS = ["lime", "banana", "red", "blue", "green", "orange", "yellow", "black", "white", "purple", "brown", "cyan", "maroon", "rose", "coral"]
player_images = {}
player_dead_images = {}

for i, color in enumerate(PLAYER_COLORS):
    try:
        img = pygame.image.load(f"Assets/Character/All_colors/{color}.png").convert_alpha()
        player_images[i] = pygame.transform.scale(img, (PLAYER_SIZE, PLAYER_SIZE))
    except:
        img = pygame.image.load("Assets/Character/All_colors/lime.png").convert_alpha()
        player_images[i] = pygame.transform.scale(img, (PLAYER_SIZE, PLAYER_SIZE))
        
    # Versuche _dead Bild zu laden, ansonsten rötlicher Fallback
    try:
        dead_img = pygame.image.load(f"Assets/Character/All_colors/{color}'s_dead_body.png").convert_alpha()
        player_dead_images[i] = pygame.transform.scale(dead_img, (int(PLAYER_SIZE*1.3), int(PLAYER_SIZE*0.765*1.3)))
    except Exception as e:
        print(e)
        fallback_dead = player_images[i].copy()
        fallback_dead.fill((255, 100, 100, 180), special_flags=pygame.BLEND_RGBA_MULT)
        player_dead_images[i] = fallback_dead

# =========================
# SPIELER KLASSE
# =========================
imposter_count = 1
intro_timer = 0

class Player:
    def __init__(self, x, y, image):
        self.rect = pygame.Rect(x, y, PLAYER_SIZE, PLAYER_SIZE)
        self.image = image
        self.role = "Crewmate" 
        self.role_desc = "Erledige alle Aufgaben und finde die Imposter."
        self.my_assigned_tasks = []
        self.my_completed_tasks = []
        self.is_dead = False 
        self.is_venting = False       # NEU: Ob der Imposter gerade im Vent ist
        self.current_vent_idx = -1    # NEU: Index des aktuellen Vents

    def move(self, keys, hitboxes):
        old_x = self.rect.x
        old_y = self.rect.y
        dx, dy = 0, 0

        # Geister sind langsamer (0.8x)
        current_speed = PLAYER_SPEED * 0.8 if self.is_dead else PLAYER_SPEED

        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= current_speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += current_speed
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= current_speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += current_speed

        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071

        self.rect.x += int(dx)
        # Geister gehen durch Wände
        if not self.is_dead:
            for box in hitboxes:
                if self.rect.colliderect(box):
                    if dx > 0: self.rect.right = box.left
                    if dx < 0: self.rect.left = box.right

        self.rect.y += int(dy)
        if not self.is_dead:
            for box in hitboxes:
                if self.rect.colliderect(box):
                    if dy > 0: self.rect.bottom = box.top
                    if dy < 0: self.rect.top = box.bottom

        return self.rect.x != old_x or self.rect.y != old_y

    def draw(self, surface, camera_x, camera_y):
        draw_rect = self.rect.copy()
        draw_rect.x -= camera_x
        draw_rect.y -= camera_y
        
        img_to_draw = self.image.copy()
        if self.is_dead:
            img_to_draw.set_alpha(128) # Eigener Geist ist leicht transparent
        elif self.is_venting:
            img_to_draw.set_alpha(100) # NEU: Eigener Imposter wird im Vent halbtransparent angezeigt
            
        surface.blit(img_to_draw, (draw_rect.x, draw_rect.y))

class TextInput:
    def __init__(self, x, y, w, h, font):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.text = ""
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                if event.unicode.isprintable() and event.key != pygame.K_RETURN:
                    self.text += event.unicode

    def draw(self, screen):
        pygame.draw.rect(screen, (255, 255, 255), self.rect, border_radius=8)
        pygame.draw.rect(screen, (0, 0, 0), self.rect, 2, border_radius=8)
        txt = self.font.render(self.text, True, (0, 0, 0))
        screen.blit(txt, (self.rect.x + 10, self.rect.y + 10))

# =========================
# MAP & HITBOX LOADER
# =========================
def load_hitboxes(filepath):
    hitboxes, vents, plants, tasks_hitboxes, mapwalls, spawnpoints, emergency_hitboxes = [], [], [], [], [], [], []
    if not os.path.exists(filepath):
        return hitboxes, vents, plants, tasks_hitboxes, mapwalls, spawnpoints, emergency_hitboxes
    
    with open(filepath, "r", encoding="utf-8-sig") as f:
        map_data = json.load(f)
    map_width = map_data.get("width", 100)

    for layer in map_data.get("layers", []):
        name = layer.get("name")
        if name in ["Hitbox", "ObjectsHitbox"]:
            if "objects" in layer:
                for obj in layer["objects"]: hitboxes.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, t_id in enumerate(layer["data"]):
                    if t_id != 0: hitboxes.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        if name in ["Hitbox", "Hitbox"]:
            if "objects" in layer:
                for obj in layer["objects"]: mapwalls.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, t_id in enumerate(layer["data"]):
                    if t_id != 0: mapwalls.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name == "VentsHitbox":
            if "objects" in layer:
                for obj in layer["objects"]: vents.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, t_id in enumerate(layer["data"]):
                    if t_id != 0: vents.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name == "PlantTeleport":
            if "objects" in layer:
                for obj in layer["objects"]: plants.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, t_id in enumerate(layer["data"]):
                    if t_id != 0: plants.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name in ["Tasks", "Tasks"]:
            if "objects" in layer:
                for obj in layer["objects"]: tasks_hitboxes.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, t_id in enumerate(layer["data"]):
                    if t_id != 0: tasks_hitboxes.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name in ["Spawnpoints", "Spawnpoints"]:
            if "objects" in layer:
                for obj in layer["objects"]: spawnpoints.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, t_id in enumerate(layer["data"]):
                    if t_id != 0: spawnpoints.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name == "EmergencyMeeting":
            if "objects" in layer:
                for obj in layer["objects"]: emergency_hitboxes.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, t_id in enumerate(layer["data"]):
                    if t_id != 0: emergency_hitboxes.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
                        
    return hitboxes, vents, plants, tasks_hitboxes, mapwalls, spawnpoints, emergency_hitboxes

def get_current_vent(player, vents):
    for vent in vents:
        if player.rect.colliderect(vent): return vent
    return None

def get_current_plant(player, plants):
    for plant in plants:
        if player.rect.colliderect(plant): return plant
    return None

# =========================
# NETZWERK LOGIK
# =========================
other_players = {}
player_names = {}
dead_players = set()     
dead_bodies = {}         

my_id = None
player_count = 0
host_id = 0
game_started = False
state = "menu"
imposter_reveal_ids = []

global_task_progress = 0
global_task_max = 0

def has_line_of_sight(p1, p2, hitboxes):
    min_x, max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
    min_y, max_y = min(p1[1], p2[1]), max(p1[1], p2[1])
    line_rect = pygame.Rect(min_x, min_y, (max_x - min_x) or 1, (max_y - min_y) or 1)
    for box in hitboxes:
        if line_rect.colliderect(box) and box.clipline(p1, p2):
            return False
    return True

def setup_socket(s):
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

def receive_data(sock):
    global other_players, player_names, player_count, host_id, game_started, state
    global imposter_count, intro_timer, global_task_progress, global_task_max, dead_players, dead_bodies
    # WICHTIG: Diese fehlten bisher -> ohne "global" wurden meeting_active/meeting_timer/has_voted/
    # meeting_cooldown nur LOKAL in dieser Funktion verändert und die Hauptschleife hat davon nie etwas gesehen.
    # Dadurch ist beim Empfang von Paket 40/43 nach außen hin scheinbar nichts passiert.
    global meeting_active, meeting_timer, has_voted, meeting_cooldown, meeting_caller_id, meeting_reason
    # show_minimap hatte denselben Fehler: wurde bei Meeting-Start lokal statt global auf False gesetzt
    global show_minimap

    while True:
        try:
            data = sock.recv(1)
            if not data: return
            packet_type = struct.unpack("!B", data)[0]

            if packet_type == 1:
                player_count, host_id = struct.unpack("!BB", sock.recv(2))
                player_names.clear()
                for _ in range(player_count):
                    p_id = struct.unpack("!B", sock.recv(1))[0]
                    name_length = struct.unpack("!B", sock.recv(1))[0]
                    pname = sock.recv(name_length).decode()
                    player_names[p_id] = pname

            elif packet_type == 2:
                data_b = b""
                while len(data_b) < 9:
                    packet = sock.recv(9 - len(data_b))
                    if not packet: return
                    data_b += packet
                p_id, x, y = struct.unpack("!Bii", data_b)
                other_players[p_id] = [x, y]

            elif packet_type == 3:
                game_started = True
                state = "game"
                intro_timer = 300
                my_player.rect.x = spawnpoints[my_id].x
                my_player.rect.y = spawnpoints[my_id].y
                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: pass

            elif packet_type == 4:
                disconnect_data = sock.recv(9)
                if len(disconnect_data) == 9:
                    p_id, x, y = struct.unpack("!Bii", disconnect_data)
                    if p_id in other_players: del other_players[p_id]

            elif packet_type == 5:
                role_id = struct.unpack("!B", sock.recv(1))[0]
                if role_id == 1:
                    my_player.role = "Imposter"
                    my_player.role_desc = "Eliminiere die Crew. Bleibe unentdeckt."
                    my_player.my_assigned_tasks = [] 
                else:
                    my_player.role = "Crewmate"
                    my_player.role_desc = "Erledige alle Aufgaben und finde die Imposter."
                    available_indices = list(range(len(TASK_TEMPLATES)))
                    import random
                    my_player.my_assigned_tasks = random.sample(available_indices, min(10, len(available_indices)))
                    my_player.my_completed_tasks = []

            elif packet_type == 12: 
                imposter_count = struct.unpack("!B", sock.recv(1))[0]

            elif packet_type == 21: 
                global_task_progress, global_task_max = struct.unpack("!HH", sock.recv(4))

            elif packet_type == 22: 
                global imposter_reveal_ids
                num_imps = struct.unpack("!B", sock.recv(1))[0]
                imposter_reveal_ids = []
                for _ in range(num_imps):
                    imposter_reveal_ids.append(struct.unpack("!B", sock.recv(1))[0])
                state = "crew_win"

            elif packet_type == 23:
                game_started = False
                state = "lobby"
                my_player.my_completed_tasks.clear()
                
                my_player.my_assigned_tasks.clear()
                global_task_progress = 0
                global_task_max = 0
                
                my_player.is_dead = False 
                my_player.is_venting = False       # NEU: Venting bei Reset zurücksetzen
                my_player.current_vent_idx = -1    # NEU: Vent-Index zurücksetzen
                dead_players.clear()
                dead_bodies.clear()
                my_player.rect.x = lobby_spawn_rects[my_id % len(lobby_spawn_rects)].x
                my_player.rect.y = lobby_spawn_rects[my_id % len(lobby_spawn_rects)].y
                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: pass
                
            elif packet_type == 31:
                dead_id = struct.unpack("!B", sock.recv(1))[0]
                dead_players.add(dead_id)
                if dead_id == my_id:
                    my_player.is_dead = True
                    dead_bodies[dead_id] = (my_player.rect.x, my_player.rect.y)
                elif dead_id in other_players:
                    dead_bodies[dead_id] = (other_players[dead_id][0], other_players[dead_id][1])

            elif packet_type == 32:
                num_imps = struct.unpack("!B", sock.recv(1))[0]
                imposter_reveal_ids = []
                for _ in range(num_imps):
                    imposter_reveal_ids.append(struct.unpack("!B", sock.recv(1))[0])
                state = "imposter_win"

            elif packet_type == 40:
                caller_id, reason = struct.unpack("!BB", sock.recv(2))
                meeting_active = True
                meeting_timer = 30.0
                meeting_caller_id = caller_id
                meeting_reason = reason
                has_voted = False
                player_votes.clear()
                if task_manager.active_task:
                    task_manager.reset_active_task()
                    task_manager.active_task = None
                show_minimap = False

            elif packet_type == 41:
                voter_id, target_id = struct.unpack("!BB", sock.recv(2))
                player_votes[voter_id] = target_id

            elif packet_type == 43:
                meeting_active = False
                meeting_cooldown = 30.0
                # Alle Spieler auf fixe Spawnpoints zurücksetzen
                if my_id is not None and my_id < len(spawnpoints):
                    my_player.rect.x = spawnpoints[my_id].x
                    my_player.rect.y = spawnpoints[my_id].y
                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: pass
                
            elif packet_type == 23:  # Erweitere den bestehenden Reset
                game_started = False
                state = "lobby"
                meeting_active = False
                meeting_cooldown = 0.0

        except Exception as e:
            print("RECEIVE THREAD ERROR:", e)
            break

def connect_to_server(ip, name, spawnpoints):
    global sock, my_id, my_player, connected, state
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, PORT))
        setup_socket(sock)

        name_data = name.encode()
        sock.sendall(struct.pack("!B", len(name_data)))
        sock.sendall(name_data)

        my_id = struct.unpack('!B', sock.recv(1))[0]
        lx = lobby_spawn_rects[my_id % len(lobby_spawn_rects)].x
        ly = lobby_spawn_rects[my_id % len(lobby_spawn_rects)].y
        my_player = Player(lx, ly, player_images[my_id % len(player_images)])
        threading.Thread(target=receive_data, args=(sock,), daemon=True).start()
        connected = True
        return True
    except Exception as e:
        print("CONNECT ERROR:", e)
        return False

# ===================
# TASK SYSTEM
# ===================
task_manager = tasks.TaskManager()
proximity_font = pygame.font.SysFont("arial", 12, bold=True)
name_font = pygame.font.SysFont("arial", 14, bold=True)
already_done_timer = 0
warning_font = pygame.font.SysFont("arial", 12, bold=True)

tasks_instances = [
    tasks.BookSortTask(screen), tasks.ChairStackTask(screen), tasks.WindowTask(screen),
    tasks.DownloadDataTask(screen), tasks.CleanBoardTask(screen), tasks.ProjectorWiresTask(screen),
    tasks.VirusScanTask(screen), tasks.PrinterPaperTask(screen), tasks.BunsenBurnerTask(screen),
    tasks.ChemicalMixTask(screen), tasks.PencilCaseTask(screen), tasks.KeyboardCleanTask(screen),
    tasks.MicroscopeFocusTask(screen), tasks.RepairCurcuit(screen), tasks.BallCollectTask(screen),
    tasks.MatStackTask(screen), tasks.TraySortingTask(screen), tasks.MilkFillTask(screen),
    tasks.PizzaCutTask(screen), tasks.VendingMachineTask(screen), tasks.BarcodeScanTask(screen),
    tasks.LockerCleanTask(screen), tasks.TrashDisposalTask(screen), tasks.PipeLeakTask(screen)
]
for t in tasks_instances: task_manager.add_task(t)

TASK_TEMPLATES = [
    {"type": "books", "name": "Bücher sortieren"}, {"type": "chair_stack", "name": "Stühle stapeln"},
    {"type": "window", "name": "Fenster lüften"}, {"type": "pc_download", "name": "Daten downloaden"},
    {"type": "board", "name": "Tafel wischen"}, {"type": "projector", "name": "Beamer verkabeln"},
    {"type": "pc_scan", "name": "Virenscan"}, {"type": "printer", "name": "Druckerpapier auffüllen"},
    {"type": "bunsen", "name": "Bunsenbrenner einstellen"}, {"type": "chemical", "name": "Chemikalien mischen"},
    {"type": "pencil_case", "name": "Mäppchen packen"}, {"type": "keyboard", "name": "Tastatur reinigen"},
    {"type": "microscope", "name": "Mikroskop fokussieren"}, {"type": "circuit", "name": "Schaltkreis reparieren"},
    {"type": "ball_basket", "name": "Bälle einsammeln"}, {"type": "mats", "name": "Matten stapeln"},
    {"type": "tray_sort", "name": "Tablett sortieren"}, {"type": "milk_carton", "name": "Milch einfüllen"},
    {"type": "pizza", "name": "Pizza schneiden"}, {"type": "vending", "name": "Automat klemmt"},
    {"type": "barcode", "name": "Barcodes scannen"}, {"type": "locker", "name": "Spind aufräumen"},
    {"type": "trash_bin", "name": "Müll wegbringen"}, {"type": "pipe_leak", "name": "Rohrbruch dichten"},
]
task_buttons = []

def get_meeting_layout():
    """Liefert Spieler-Boxen + Skip-Button für die Meeting-Ansicht.
    Wird sowohl von draw_meeting() (Zeichnen) als auch vom Mausklick-Handler
    (Abstimmen) benutzt, damit beide garantiert dieselben Koordinaten verwenden."""
    box_w, box_h = 280, 60
    start_x = (WIDTH - (3 * (box_w + 20))) // 2
    start_y = 120

    boxes = []
    all_p_ids = sorted(list(player_names.keys()))
    for idx, p_id in enumerate(all_p_ids):
        col = idx % 3
        row = idx // 3
        bx = start_x + col * (box_w + 20)
        by = start_y + row * (box_h + 20)
        boxes.append((p_id, pygame.Rect(bx, by, box_w, box_h)))

    skip_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT - 100, 300, 50)
    return boxes, skip_rect

def draw_meeting():
    # Dunkler Overlay-Hintergrund (wie die Map)
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(230)
    overlay.fill((15, 20, 30))
    screen.blit(overlay, (0, 0))

    caller_name = player_names.get(meeting_caller_id, f"Spieler {meeting_caller_id}")
    if meeting_reason == MEETING_REASON_BODY:
        title_str = f"{caller_name} hat eine Leiche gemeldet! ({int(meeting_timer)}s)"
    else:
        title_str = f"{caller_name} hat ein Meeting einberufen! ({int(meeting_timer)}s)"
    title_txt = menu_font.render(title_str, True, (255, 255, 255))
    screen.blit(title_txt, (WIDTH // 2 - title_txt.get_width() // 2, 40))

    boxes, skip_rect = get_meeting_layout()
    for p_id, rect in boxes:
        is_p_dead = p_id in dead_players
        bg_color = (25, 25, 30) if is_p_dead else (40, 45, 55)
        
        pygame.draw.rect(screen, bg_color, rect, border_radius=8)
        border_color = (0, 255, 255) if p_id == my_id else (100, 100, 110)
        pygame.draw.rect(screen, border_color, rect, 2, border_radius=8)
        
        # Spielerbild links (tot = ausgegraut)
        p_img = player_images.get(p_id % len(player_images))
        if p_img:
            img_copy = p_img.copy()
            if is_p_dead:
                img_copy.fill((80, 80, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(img_copy, (rect.x + 10, rect.y + (rect.height - PLAYER_SIZE) // 2))
            
        # Name rechts daneben
        name_color = (120, 120, 120) if is_p_dead else (255, 255, 255)
        p_name = player_names.get(p_id, f"Player {p_id}")
        name_txt = name_font.render(p_name, True, name_color)
        screen.blit(name_txt, (rect.x + 15 + PLAYER_SIZE, rect.y + (rect.height - name_txt.get_height()) // 2))
        
        # Häkchen, wenn der Spieler bereits gewählt hat
        if p_id in player_votes:
            voted_marker = name_font.render("✔", True, (0, 255, 0))
            screen.blit(voted_marker, (rect.x + rect.width - 25, rect.y + (rect.height - voted_marker.get_height()) // 2))
            
    # Skip-Button am unteren Rand
    pygame.draw.rect(screen, (60, 65, 75), skip_rect, border_radius=8)
    pygame.draw.rect(screen, (200, 200, 200), skip_rect, 2, border_radius=8)
    skip_txt = name_font.render("VOTING ÜBERSPRINGEN", True, (255, 255, 255))
    screen.blit(skip_txt, (skip_rect.centerx - skip_txt.get_width() // 2, skip_rect.centery - skip_txt.get_height() // 2))
    
    skip_voters = sum(1 for v in player_votes.values() if v == 255)
    if skip_voters > 0:
        sv_txt = name_font.render(f"Stimmen: {skip_voters}", True, (0, 255, 0))
        screen.blit(sv_txt, (skip_rect.right + 15, skip_rect.centery - sv_txt.get_height() // 2))

def draw_task_buttons(surface, buttons, player_obj, camera_x, camera_y):
    for btn in buttons:
        t_idx = btn["task_index"]
        if player_obj.role == "Crewmate" and t_idx not in player_obj.my_assigned_tasks:
            continue

        r = btn["rect"]
        player_center = player_obj.rect.center
        button_center = r.center
        distance = math.hypot(player_center[0] - button_center[0], player_center[1] - button_center[1])
        
        dr = r.copy()
        dr.x -= camera_x
        dr.y -= camera_y
        
        color = (0, 255, 0) if t_idx in player_obj.my_completed_tasks else (0, 255, 255)
        pygame.draw.rect(surface, color, dr, 2, border_radius=4)
        
        if distance < 30:
            if t_idx in player_obj.my_completed_tasks:
                lbl_text = proximity_font.render(f"[ERLEDIGT] {btn['name']}", True, (150, 150, 150))
            else:
                lbl_text = proximity_font.render(f"[E] {btn['name']}", True, (255, 255, 255))

# =========================
# MENÜ DRAWING
# =========================
menu_font = pygame.font.SysFont("arial", 40)
small_font = pygame.font.SysFont("arial", 28)

info_text1 = small_font.render(f"Bewegung: WASD", True, (255, 255, 255))
info_text2 = small_font.render(f"Map öffnen/schließen: M", True, (255, 255, 255))
info_text3 = small_font.render(f"Benutzen/Interagieren/Kill: E", True, (255, 255, 255))

ip_input = TextInput(WIDTH // 2 - 175, HEIGHT // 2 - 100, 350, 60, small_font)
name_input = TextInput(WIDTH // 2 - 175, HEIGHT // 2 + 20, 350, 60, small_font)

def draw_menu():
    screen.fill((25, 25, 35))
    title = menu_font.render("MULTIPLAYER LOGIN", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 220))
    screen.blit(small_font.render("SERVER IP", True, (200, 200, 200)), (WIDTH // 2 - 175, HEIGHT // 2 - 140))
    screen.blit(small_font.render("NAME", True, (200, 200, 200)), (WIDTH // 2 - 175, HEIGHT // 2 - 20))
    ip_input.draw(screen)
    name_input.draw(screen)
    connect_txt = small_font.render("ENTER = CONNECT", True, (100, 255, 100))
    screen.blit(connect_txt, (WIDTH // 2 - connect_txt.get_width() // 2, HEIGHT // 2 + 120))

def draw_lobby():
    camera_x = my_player.rect.x - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)
    camera_y = my_player.rect.y - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)

    internal_surface.fill((20, 20, 30))
    internal_surface.blit(lobby_bg, (-camera_x, -camera_y))

    for p_id, pos in other_players.items():
        enemy_img = player_images.get(p_id % len(player_images))
        if enemy_img:
            internal_surface.blit(enemy_img, (pos[0] - camera_x, pos[1] - camera_y))
            e_name = player_names.get(p_id, f"Player {p_id}")
            name_text = name_font.render(e_name, True, (255, 255, 255))
            internal_surface.blit(name_text, ((pos[0] - camera_x) + (PLAYER_SIZE // 2) - (name_text.get_width() // 2), (pos[1] - camera_y) - 16))

    my_player.draw(internal_surface, camera_x, camera_y)
    my_name = player_names.get(my_id, "Ich")
    my_name_text = name_font.render(my_name, True, (255, 255, 255))
    internal_surface.blit(my_name_text, ((my_player.rect.x - camera_x) + (PLAYER_SIZE // 2) - (my_name_text.get_width() // 2), (my_player.rect.y - camera_y) - 16))

    scaled_size = min(WIDTH, HEIGHT)
    scaled_surface = pygame.transform.scale(internal_surface, (scaled_size, scaled_size))
    screen.fill((0, 0, 0))
    screen.blit(scaled_surface, ((WIDTH - scaled_size) // 2, (HEIGHT - scaled_size) // 2))

    title = menu_font.render("LOBBY", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))
    screen.blit(small_font.render(f"Spieler online: {len(player_names)} / 15", True, (255, 255, 255)), (40, HEIGHT - 80))
    imp_text = small_font.render(f"Imposter: {imposter_count}", True, (255, 255, 255))
    screen.blit(imp_text, (WIDTH // 2 - imp_text.get_width() // 2, HEIGHT - 150))

    if my_id == host_id:
        btn = pygame.Rect(WIDTH - 240, HEIGHT - 100, 200, 60)
        pygame.draw.rect(screen, (0, 220, 100), btn, border_radius=10)
        txt = small_font.render("START", True, (0, 0, 0))
        screen.blit(txt, (btn.centerx - txt.get_width() // 2, btn.centery - txt.get_height() // 2))

        btn_minus = pygame.Rect(WIDTH // 2 - 100, HEIGHT - 155, 40, 40)
        btn_plus = pygame.Rect(WIDTH // 2 + 60, HEIGHT - 155, 40, 40)
        pygame.draw.rect(screen, (100, 100, 100), btn_minus, border_radius=5)
        pygame.draw.rect(screen, (100, 100, 100), btn_plus, border_radius=5)
        
        minus_txt = small_font.render("-", True, (255, 255, 255))
        plus_txt = small_font.render("+", True, (255, 255, 255))
        screen.blit(minus_txt, (btn_minus.centerx - minus_txt.get_width() // 2, btn_minus.centery - minus_txt.get_height() // 2))
        screen.blit(plus_txt, (btn_plus.centerx - plus_txt.get_width() // 2, btn_plus.centery - plus_txt.get_height() // 2))
    else:
        wait_txt = small_font.render("Warte auf Host...", True, (185, 185, 185))
        screen.blit(wait_txt, (WIDTH - 260, HEIGHT - 80))

base_path = "Assets/Map/Map/"
try:
    floor_img = pygame.image.load(os.path.join(base_path, "Floor.png")).convert_alpha()
    walls_img = pygame.image.load(os.path.join(base_path, "Walls.png")).convert_alpha()
    objects_img = pygame.image.load(os.path.join(base_path, "Objects.png")).convert_alpha()
    lobby_bg = pygame.image.load(os.path.join(base_path, "Lobby.png")).convert_alpha()
except Exception as e:
    pygame.quit()
    sys.exit()

def load_lobby_map():
    lobby_hitboxes, lobby_spawns, fallback_spawns = [], [None] * 15, []
    try:
        with open(os.path.join("Assets", "Map", "Map", "Lobby.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        for layer in data.get("layers", []):
            if layer.get("type") == "objectgroup":
                if layer.get("name") in ["Hitboxes", "ObjectsHitbox"]:
                    for obj in layer.get("objects", []):
                        lobby_hitboxes.append(pygame.Rect(obj.get("x",0), obj.get("y",0), obj.get("width",0), obj.get("height",0)))
                elif layer.get("name") == "Spawnpoints":
                    for obj in layer.get("objects", []):
                        x, y, name = obj.get("x",0), obj.get("y",0), obj.get("name","")
                        fallback_spawns.append((x, y))
                        try:
                            num = int(''.join(filter(str.isdigit, name)))
                            if 1 <= num <= 15: lobby_spawns[num - 1] = (x, y)
                            elif 0 <= num < 15: lobby_spawns[num] = (x, y)
                        except ValueError: pass
    except: pass
    final_spawns = [(s if s is not None else (fallback_spawns[0] if fallback_spawns else (100, 100))) for s in lobby_spawns]
    return lobby_hitboxes, final_spawns

lobby_hitboxes, lobby_spawnpoints = load_lobby_map()
lobby_spawn_rects = [pygame.Rect(pos[0], pos[1], PLAYER_SIZE, PLAYER_SIZE) for pos in lobby_spawnpoints]

MAP_WIDTH_PX, MAP_HEIGHT_PX = floor_img.get_size()
MINIMAP_WIDTH = 800  
MINIMAP_HEIGHT = int(MAP_HEIGHT_PX * (MINIMAP_WIDTH / MAP_WIDTH_PX))
minimap_bg = pygame.Surface((MINIMAP_WIDTH, MINIMAP_HEIGHT))
minimap_bg.blit(pygame.transform.scale(floor_img, (MINIMAP_WIDTH, MINIMAP_HEIGHT)), (0, 0))
minimap_bg.blit(pygame.transform.scale(walls_img, (MINIMAP_WIDTH, MINIMAP_HEIGHT)), (0, 0))

hitboxes, vents, plants, tasks_hitboxes, mapwalls, spawnpoints, emergency_hitboxes = load_hitboxes(os.path.join(base_path, "Hitboxes.json"))

for i, rect in enumerate(tasks_hitboxes):
    if i < len(TASK_TEMPLATES):
        task_buttons.append({"rect": rect, "type": TASK_TEMPLATES[i]["type"], "task_index": i, "name": TASK_TEMPLATES[i]["name"]})

# HINWEIS: Das alte MeetingSystem aus Meeting.py wird hier bewusst NICHT mehr verwendet.
# Es erwartet ein "game_state"-Objekt mit .players/.bodies (echte Spieler-Objekte), das es in
# diesem Netzwerk-Code gar nicht gibt (andere Spieler sind nur Positions-Dicts + IDs), und lief
# außerdem komplett lokal ohne Server-Sync. Die Datei bleibt unverändert liegen, falls ihr Teile
# davon (z.B. die Chat-Idee) später in das unten stehende, server-synchronisierte System einbauen wollt.

# =========================
# HAUPTSCHLEIFE
# =========================
MEETING_REASON_BUTTON = 0
MEETING_REASON_BODY = 1

meeting_active = False
meeting_cooldown = 0.0
meeting_timer = 30.0
has_voted = False
player_votes = {}
meeting_caller_id = None
meeting_reason = MEETING_REASON_BUTTON
running = True
show_minimap = False  

while running:
    dt = clock.tick(60) / 1000.0
    was_task_active = task_manager.active_task is not None

    # Meeting-Timer & Notfallknopf-Cooldown laufend runterzählen (sonst bleibt die Anzeige stehen)
    if meeting_active:
        meeting_timer = max(0.0, meeting_timer - dt)
    if meeting_cooldown > 0:
        meeting_cooldown = max(0.0, meeting_cooldown - dt)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            pygame.quit()
            sys.exit()

        if state == "menu":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if connect_to_server(ip_input.text, name_input.text, spawnpoints):
                    state = "lobby"
            ip_input.handle_event(event)
            name_input.handle_event(event)

        elif state == "lobby":
            if event.type == pygame.MOUSEBUTTONDOWN and my_id == host_id:
                btn = pygame.Rect(WIDTH - 240, HEIGHT - 100, 200, 60)
                btn_minus = pygame.Rect(WIDTH // 2 - 100, HEIGHT - 155, 40, 40)
                btn_plus = pygame.Rect(WIDTH // 2 + 60, HEIGHT - 155, 40, 40)
                
                if btn.collidepoint(event.pos):
                    try: sock.sendall(struct.pack("!B", 99))
                    except: pass
                elif btn_minus.collidepoint(event.pos):
                    if imposter_count > 1:
                        try: sock.sendall(struct.pack("!BB", 11, imposter_count - 1))
                        except: pass
                elif btn_plus.collidepoint(event.pos):
                    if imposter_count < 3:
                        try: sock.sendall(struct.pack("!BB", 11, imposter_count + 1))
                        except: pass

        elif state == "game":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    if task_manager.active_task:
                        task_aborted = True
                        task_manager.reset_active_task()
                        task_manager.active_task = None
                    elif show_minimap: show_minimap = False
                    else:
                        running = False
                        pygame.quit()
                        sys.exit()

                if event.key == pygame.K_HASH:
                    mapwalls = []

                if event.key == pygame.K_m and task_manager.active_task is None:
                    show_minimap = not show_minimap

                # NEU: Pfeiltasten / AD Steuerung zum Durchwechseln, wenn man im Vent ist
                if my_player.is_venting:
                    if event.key in [pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w]:
                        if vents:
                            my_player.current_vent_idx = (my_player.current_vent_idx - 1) % len(vents)
                            my_player.rect.center = vents[my_player.current_vent_idx].center
                            # Versteckte Koordinaten halten, damit andere uns nicht sehen
                            try: sock.sendall(struct.pack('!Bii', 2, -2000, -2000))
                            except: pass
                    elif event.key in [pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s]:
                        if vents:
                            my_player.current_vent_idx = (my_player.current_vent_idx + 1) % len(vents)
                            my_player.rect.center = vents[my_player.current_vent_idx].center
                            try: sock.sendall(struct.pack('!Bii', 2, -2000, -2000))
                            except: pass

                # Interaktions-Logik (Blockiert, wenn man im Vent abgetaucht ist oder gerade ein Meeting läuft)
                if event.key == pygame.K_e and task_manager.active_task is None and not show_minimap and not my_player.is_venting and not meeting_active:
                    at_meeting_box = False
                    for box in emergency_hitboxes:
                        if my_player.rect.colliderect(box):
                            at_meeting_box = True
                            break

                    # Liegt eine Leiche in Melde-Reichweite? (gleicher Radius wie beim Töten)
                    near_body = False
                    my_center = my_player.rect.center
                    for body_id, (bx, by) in dead_bodies.items():
                        body_center = (bx + PLAYER_SIZE // 2, by + PLAYER_SIZE // 2)
                        if math.hypot(my_center[0] - body_center[0], my_center[1] - body_center[1]) < 60:
                            near_body = True
                            break

                    if near_body and not my_player.is_dead:
                        # Leiche melden -> Meeting starten (kein Cooldown, wie im echten Spiel)
                        try: sock.sendall(struct.pack("!BB", 40, MEETING_REASON_BODY))
                        except: pass
                    elif at_meeting_box and meeting_cooldown <= 0 and not my_player.is_dead:
                        try: sock.sendall(struct.pack("!BB", 40, MEETING_REASON_BUTTON))
                        except: pass
                    elif my_player.role == "Imposter" and not my_player.is_dead:
                        # Kill Suche
                        closest_id = None
                        closest_dist = 60 # Kill-Reichweite
                        my_center = my_player.rect.center
                        for p_id, pos in other_players.items():
                            if p_id not in dead_players:
                                e_center = (pos[0] + PLAYER_SIZE//2, pos[1] + PLAYER_SIZE//2)
                                dist = math.hypot(my_center[0] - e_center[0], my_center[1] - e_center[1])
                                if dist < closest_dist:
                                    closest_dist = dist
                                    closest_id = p_id
                        
                        if closest_id is not None:
                            try: sock.sendall(struct.pack("!BB", 30, closest_id)) # Sende Kill-Paket
                            except: pass

                    elif my_player.role == "Crewmate":
                        # Aufgaben erledigen (auch als Geist möglich)
                        for btn in task_buttons:
                            t_idx = btn["task_index"]
                            if t_idx not in my_player.my_assigned_tasks: continue

                            distance = math.hypot(my_player.rect.centerx - btn["rect"].centerx, my_player.rect.centery - btn["rect"].centery)
                            if distance < 50:
                                if t_idx in my_player.my_completed_tasks:
                                    already_done_timer = 90
                                else:
                                    if task_manager.start_task(t_idx) == "ALREADY_DONE":
                                        already_done_timer = 90
                                    else:
                                        active_task_idx = t_idx
                                        task_aborted = False 
                                break
                
                # NEU: Überarbeitetes Vent-System mit Leertaste (Abtauchen / Auftauchen)
                if event.key == pygame.K_SPACE and not show_minimap and not my_player.is_dead:
                    if my_player.role == "Imposter":
                        if not my_player.is_venting:
                            # Abtauchen versuchen
                            cv = get_current_vent(my_player, vents)
                            if cv:
                                my_player.is_venting = True
                                my_player.current_vent_idx = vents.index(cv)
                                my_player.rect.center = cv.center
                                # Sende ungültige Off-Screen Position an den Server, damit wir unsichtbar werden
                                try: sock.sendall(struct.pack('!Bii', 2, -2000, -2000))
                                except: pass
                        else:
                            # Auftauchen aus dem aktuellen Vent
                            my_player.is_venting = False
                            if vents:
                                my_player.rect.center = vents[my_player.current_vent_idx].center
                            # Sende die echte Position wieder an den Server
                            try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                            except: pass

        # Abstimmen per Mausklick, während ein Meeting läuft (siehe draw_meeting())
        if meeting_active and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not has_voted and not my_player.is_dead:
            boxes, skip_rect = get_meeting_layout()
            voted_target = None
            for p_id, rect in boxes:
                if p_id in dead_players:
                    continue  # Tote können nicht gewählt werden
                if rect.collidepoint(event.pos):
                    voted_target = p_id
                    break
            if voted_target is None and skip_rect.collidepoint(event.pos):
                voted_target = 255  # 255 = Skip, siehe Server-Protokoll

            if voted_target is not None:
                try: sock.sendall(struct.pack("!BB", 41, voted_target))
                except: pass
                has_voted = True

        task_manager.handle_event(event)

    if state == "game" and task_manager.active_task is None and not show_minimap and game_started:
        # NEU: Normale WASD Bewegung blockieren, falls man im Vent sitzt
        if not my_player.is_venting and not meeting_active:
            if my_player.move(pygame.key.get_pressed(), hitboxes):
                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: running = False

    elif state == "lobby" and not game_started and my_id is not None:
        if my_player.move(pygame.key.get_pressed(), lobby_hitboxes):
            try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
            except: running = False

    elif state in ["crew_win", "imposter_win"]:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if my_id == host_id:
                    try: sock.sendall(struct.pack("!B", 23))
                    except: pass

    # --- RENDERING ---
    if state == "menu":
        draw_menu()
    elif state == "lobby" and not game_started:
        draw_lobby()
    elif state == "game":
        camera_x = my_player.rect.x - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)
        camera_y = my_player.rect.y - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)

        internal_surface.fill((40, 80, 40))
        internal_surface.blit(floor_img, (-camera_x, -camera_y))
        internal_surface.blit(walls_img, (-camera_x, -camera_y))
        internal_surface.blit(objects_img, (-camera_x, -camera_y))

        draw_task_buttons(internal_surface, task_buttons, my_player, camera_x, camera_y)

        my_center = my_player.rect.center

        # Leichen rendern
        for d_id, (dx, dy) in dead_bodies.items():
            b_img = player_dead_images.get(d_id % len(player_dead_images))
            if not b_img: continue
            
            body_center = (dx + (PLAYER_SIZE // 2), dy + (PLAYER_SIZE // 2))
            distance = math.hypot(my_center[0] - body_center[0], my_center[1] - body_center[1])
            
            if distance <= VISION_RADIUS:
                if has_line_of_sight(my_center, body_center, mapwalls):
                    internal_surface.blit(b_img, (dx - camera_x, dy - camera_y))

        # Andere Spieler zeichnen
        my_center = my_player.rect.center
        for p_id, pos in other_players.items():
            if p_id in dead_players:
                if not my_player.is_dead:
                    continue 
                enemy_img = player_images.get(p_id % len(player_images)).copy()
                enemy_img.set_alpha(128)
            else:
                enemy_img = player_images.get(p_id % len(player_images))
                
            if not enemy_img: continue
            
            enemy_center = (pos[0] + (PLAYER_SIZE // 2), pos[1] + (PLAYER_SIZE // 2))
            distance = math.hypot(my_center[0] - enemy_center[0], my_center[1] - enemy_center[1])
            is_visible = False
            
            if distance <= VISION_RADIUS:
                if has_line_of_sight(my_center, enemy_center, mapwalls):
                    is_visible = True
                    
            if p_id not in player_visibility: player_visibility[p_id] = 0.0
                
            if is_visible: player_visibility[p_id] = min(255.0, player_visibility[p_id] + FADE_SPEED)
            else: player_visibility[p_id] = max(0.0, player_visibility[p_id] - FADE_SPEED)
                
            current_alpha = int(player_visibility[p_id])
            
            if current_alpha > 0:
                img_copy = enemy_img.copy()
                if p_id in dead_players: img_copy.set_alpha(min(current_alpha, 128))
                else: img_copy.set_alpha(current_alpha)
                    
                internal_surface.blit(img_copy, (pos[0] - camera_x, pos[1] - camera_y))
                
                e_name = player_names.get(p_id, f"Player {p_id}")
                name_text = name_font.render(e_name, True, (255, 255, 255))
                name_text.set_alpha(current_alpha)
                nx = (pos[0] - camera_x) + (PLAYER_SIZE // 2) - (name_text.get_width() // 2)
                ny = (pos[1] - camera_y) - 16
                internal_surface.blit(name_text, (nx, ny))

        # Eigenen Spieler zeichnen
        my_player.draw(internal_surface, camera_x, camera_y)
        my_name = player_names.get(my_id, "Ich")
        my_name_text = name_font.render(my_name, True, (255, 255, 255))
        if my_player.is_dead or my_player.is_venting: my_name_text.set_alpha(128)
        internal_surface.blit(my_name_text, ((my_player.rect.x - camera_x) + (PLAYER_SIZE // 2) - (my_name_text.get_width() // 2), (my_player.rect.y - camera_y) - 16))

        internal_surface.blit(fog_overlay, (0, 0))

        scaled_size = min(WIDTH, HEIGHT)
        scaled_surface = pygame.transform.scale(internal_surface, (scaled_size, scaled_size))
        screen.fill((0, 0, 0))
        screen.blit(scaled_surface, ((WIDTH - scaled_size) // 2, (HEIGHT - scaled_size) // 2))

        if already_done_timer > 0 and task_manager.active_task is None:
            already_done_timer -= 1
            msg_text = warning_font.render("Du hast diese Aufgabe bereits erledigt!", True, (255, 80, 80))
            msg_bg = pygame.Rect(WIDTH // 2 - msg_text.get_width() // 2 - 15, 30, msg_text.get_width() + 30, 40)
            pygame.draw.rect(screen, (20, 20, 20), msg_bg, border_radius=6)
            pygame.draw.rect(screen, (255, 80, 80), msg_bg, width=2, border_radius=6)
            screen.blit(msg_text, (WIDTH // 2 - msg_text.get_width() // 2, 38))

        task_manager.draw(screen)
        task_manager.update()

        is_task_active = task_manager.active_task is not None
        if was_task_active and not is_task_active:
            if not task_aborted and active_task_idx != -1:
                if active_task_idx not in my_player.my_completed_tasks:
                    my_player.my_completed_tasks.append(active_task_idx)
                    try: sock.sendall(struct.pack("!B", 20)) 
                    except: pass
            active_task_idx = -1
            task_aborted = False

        bar_width, bar_height, bar_x, bar_y = 300, 20, 20, 170
        pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y, bar_width, bar_height), border_radius=10)
        if global_task_max > 0:
            fill_width = int(bar_width * (global_task_progress / global_task_max))
            if fill_width > 0: pygame.draw.rect(screen, (0, 220, 100), (bar_x, bar_y, fill_width, bar_height), border_radius=10)
        pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 2, border_radius=10)
        
        prog_txt = proximity_font.render(f"Gesamt-Fortschritt ({global_task_progress}/{global_task_max})", True, (255, 255, 255))
        screen.blit(prog_txt, (bar_x + bar_width//2 - prog_txt.get_width()//2, bar_y + 3))

        status_str = f"Rolle: {my_player.role} {'(GEIST)' if my_player.is_dead else ('(VENT)' if my_player.is_venting else '')}"
        role_hud = small_font.render(status_str, True, (255, 100, 100) if (my_player.is_dead or my_player.is_venting) else (255, 255, 255))
        screen.blit(role_hud, (20, 20))
        screen.blit(info_text1, (20, 80))
        screen.blit(info_text2, (20, 110))
        screen.blit(info_text3, (20, 140))

        if intro_timer > 0:
            intro_timer -= 1
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(180)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))
            
            title_color = (255, 50, 50) if my_player.role == "Imposter" else (50, 200, 255)
            role_text = menu_font.render(f"DU BIST: {my_player.role.upper()}", True, title_color)
            desc_text = small_font.render(my_player.role_desc, True, (255, 255, 255))
            screen.blit(role_text, (WIDTH // 2 - role_text.get_width() // 2, HEIGHT // 2 - 60))
            screen.blit(desc_text, (WIDTH // 2 - desc_text.get_width() // 2, HEIGHT // 2 + 10))

        if show_minimap and task_manager.active_task is None:
            mm_x, mm_y = (WIDTH - MINIMAP_WIDTH) // 2, (HEIGHT - MINIMAP_HEIGHT) // 2
            pygame.draw.rect(screen, (25, 25, 30), (mm_x - 12, mm_y - 12, MINIMAP_WIDTH + 24, MINIMAP_HEIGHT + 24), border_radius=12)
            screen.blit(minimap_bg, (mm_x, mm_y))
            pygame.draw.rect(screen, (240, 240, 240), (mm_x, mm_y, MINIMAP_WIDTH, MINIMAP_HEIGHT), 2, border_radius=4)

            if my_player.role == "Crewmate":
                for btn in task_buttons:
                    t_idx = btn["task_index"]
                    if t_idx in my_player.my_assigned_tasks:
                        t_x = mm_x + int((btn["rect"].centerx / MAP_WIDTH_PX) * MINIMAP_WIDTH)
                        t_y = mm_y + int((btn["rect"].centery / MAP_HEIGHT_PX) * MINIMAP_HEIGHT)
                        t_col = (0, 255, 0) if t_idx in my_player.my_completed_tasks else (255, 255, 0)
                        pygame.draw.circle(screen, t_col, (t_x, t_y), 6)
                        pygame.draw.circle(screen, (0, 0, 0), (t_x, t_y), 6, 1)

            player_mm_x = mm_x + int((my_player.rect.centerx / MAP_WIDTH_PX) * MINIMAP_WIDTH)
            player_mm_y = mm_y + int((my_player.rect.centery / MAP_HEIGHT_PX) * MINIMAP_HEIGHT)
            p_col = (150, 50, 50) if my_player.is_dead else (255, 30, 30)
            pygame.draw.circle(screen, p_col, (player_mm_x, player_mm_y), 8)
            pygame.draw.circle(screen, (255, 255, 255), (player_mm_x, player_mm_y), 8, 2)

        if meeting_active:
            draw_meeting()

    elif state in ["crew_win", "imposter_win"]:
        screen.fill((20, 25, 30))
        if state == "crew_win":
            win_title = menu_font.render("CREWMATES GEWINNEN!", True, (0, 255, 150))
            win_sub = small_font.render("Alle Aufgaben wurden erledigt.", True, (255, 255, 255))
        else:
            win_title = menu_font.render("IMPOSTER GEWINNEN!", True, (255, 50, 50))
            win_sub = small_font.render("Die Crew wurde eliminiert.", True, (255, 255, 255))

        screen.blit(win_title, (WIDTH // 2 - win_title.get_width() // 2, HEIGHT // 2 - 100))
        screen.blit(win_sub, (WIDTH // 2 - win_sub.get_width() // 2, HEIGHT // 2 - 40))
        
        imp_names = [player_names.get(i_id, f"Spieler {i_id}") for i_id in imposter_reveal_ids]
        imp_text = small_font.render(f"Imposter war(en): {', '.join(imp_names)}", True, (255, 50, 50))
        screen.blit(imp_text, (WIDTH // 2 - imp_text.get_width() // 2, HEIGHT // 2 + 20))
        
        if my_id == host_id: back_txt = small_font.render("Drücke ENTER, um alle in die Lobby zurückzuholen", True, (255, 255, 255))
        else: back_txt = small_font.render("Warte auf den Host für Lobby-Rückkehr...", True, (150, 150, 150))
        screen.blit(back_txt, (WIDTH // 2 - back_txt.get_width() // 2, HEIGHT // 2 + 100))

    pygame.display.update()

try: sock.close()
except: pass
pygame.quit()