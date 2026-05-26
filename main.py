import pygame
import socket
import threading
import struct
import math
import json
import sys
import os

import tasks

# =========================
# EINSTELLUNGEN & KONSTANTEN
# =========================
TILE_SIZE = 24
TILES_VISIBLE = 15
INTERNAL_SIZE = TILE_SIZE * TILES_VISIBLE  # 360x360 Pixel Renderfläche
PLAYER_SPEED = 3
PORT = 5555

pygame.init()

# Hauptfenster-Größe (Lobby & Menü nutzen diesen Platz)
screen_width, screen_height = 1200, 900
screen = pygame.display.set_mode((screen_width, screen_height))
WIDTH = screen.get_width()
HEIGHT = screen.get_height()

pygame.display.set_caption("Thalheimer is Among Us - Map Edition")
clock = pygame.time.Clock()

# Internal Surface für die pixelgenaue Map-Skalierung
internal_surface = pygame.Surface((INTERNAL_SIZE, INTERNAL_SIZE))

# =========================
# BILDER LADEN & SKALIEREN
# =========================
PLAYER_SIZE = int(TILE_SIZE * 0.6)  # Spielergröße an Tiled-Map anpassen
PLAYER_COLORS = ["lime", "banana", "red", "blue", "green", "orange", "yellow", "black", "white", "purple", "brown", "cyan", "maroon", "rose", "coral"]
player_images = {}

for i, color in enumerate(PLAYER_COLORS):
    try:
        img = pygame.image.load(f"Assets/Character/All_colors/{color}.png").convert_alpha()
        player_images[i] = pygame.transform.scale(img, (PLAYER_SIZE, PLAYER_SIZE))
    except:
        img = pygame.image.load("Assets/Character/All_colors/lime.png").convert_alpha()
        player_images[i] = pygame.transform.scale(img, (PLAYER_SIZE, PLAYER_SIZE))

# =========================
# SPIELER KLASSE (Maptest-Logik)
# =========================
class Player:
    def __init__(self, x, y, image):
        self.rect = pygame.Rect(x, y, PLAYER_SIZE, PLAYER_SIZE)
        self.image = image

    def move(self, keys, hitboxes):
        old_x = self.rect.x
        old_y = self.rect.y
        dx, dy = 0, 0

        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= PLAYER_SPEED
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += PLAYER_SPEED
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= PLAYER_SPEED
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += PLAYER_SPEED

        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071

        # X-Achse bewegen und prüfen
        self.rect.x += int(dx)
        for box in hitboxes:
            if self.rect.colliderect(box):
                if dx > 0: self.rect.right = box.left
                if dx < 0: self.rect.left = box.right

        # Y-Achse bewegen und prüfen
        self.rect.y += int(dy)
        for box in hitboxes:
            if self.rect.colliderect(box):
                if dy > 0: self.rect.bottom = box.top
                if dy < 0: self.rect.top = box.bottom

        return self.rect.x != old_x or self.rect.y != old_y

    def draw(self, surface, camera_x, camera_y):
        draw_rect = self.rect.copy()
        draw_rect.x -= camera_x
        draw_rect.y -= camera_y
        surface.blit(self.image, (draw_rect.x, draw_rect.y))

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
    hitboxes, vents, plants, tasks_hitboxes, spawnpoints = [], [], [], [], []
    if not os.path.exists(filepath):
        print(f"WARNUNG: Hitbox-Datei nicht gefunden: {filepath}")
        return hitboxes, vents, plants, tasks_hitboxes, spawnpoints
    
    with open(filepath, "r", encoding="utf-8-sig") as f:
        map_data = json.load(f)
    map_width = map_data.get("width", 100)

    for layer in map_data.get("layers", []):
        name = layer.get("name")
        if name in ["Hitbox", "ObjectsHitbox"]:
            if "objects" in layer:
                for obj in layer["objects"]:
                    hitboxes.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, tile_id in enumerate(layer["data"]):
                    if tile_id != 0:
                        hitboxes.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name == "VentsHitbox":
            if "objects" in layer:
                for obj in layer["objects"]:
                    vents.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, tile_id in enumerate(layer["data"]):
                    if tile_id != 0:
                        vents.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name == "PlantTeleport":
            if "objects" in layer:
                for obj in layer["objects"]:
                    plants.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, tile_id in enumerate(layer["data"]):
                    if tile_id != 0:
                        plants.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name in ["Tasks", "Tasks"]:
            if "objects" in layer:
                for obj in layer["objects"]:
                    tasks_hitboxes.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))
            elif "data" in layer:
                for i, tile_id in enumerate(layer["data"]):
                    if tile_id != 0:
                        tasks_hitboxes.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        elif name in ["Spawnpoints", "Spawnpoints"]:
            if "objects" in layer:
                for obj in layer["objects"]:
                    spawnpoints.append(pygame.Rect(obj["x"], obj["y"], 0, 0))
            elif "data" in layer:
                for i, tile_id in enumerate(layer["data"]):
                    if tile_id != 0:
                        spawnpoints.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
                        
    return hitboxes, vents, plants, tasks_hitboxes, spawnpoints

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
my_id = None
player_names = {}
player_count = 0
host_id = 0
game_started = False
state = "menu"

def setup_socket(s):
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

def receive_data(sock):
    print("RECEIVE THREAD STARTED")
    global other_players, player_names, player_count, host_id, game_started, state

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
                try:
                    sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: pass

            elif packet_type == 4:
                disconnect_data = sock.recv(9)
                if len(disconnect_data) == 9:
                    p_id, x, y = struct.unpack("!Bii", disconnect_data)
                    if p_id in other_players: del other_players[p_id]

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
        print("Verbunden mit ID:", my_id)

        my_player = Player(spawnpoints[my_id].x, spawnpoints[my_id].y, player_images[my_id % len(player_images)])
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
proximity_font = pygame.font.SysFont("arial", 11, bold=True)
already_done_timer = 0
warning_font = pygame.font.SysFont("arial", 11, bold=True)

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

for t in tasks_instances:
    task_manager.add_task(t)

# Template zur dynamischen Generierung der Task-Buttons aus der JSON
TASK_TEMPLATES = [
    {"type": "books", "name": "Bücher sortieren"},
    {"type": "chair_stack", "name": "Stühle stapeln"},
    {"type": "window", "name": "Fenster lüften"},
    {"type": "pc_download", "name": "Daten downloaden"},
    {"type": "board", "name": "Tafel wischen"},
    {"type": "projector", "name": "Beamer verkabeln"},
    {"type": "pc_scan", "name": "Virenscan"},
    {"type": "printer", "name": "Druckerpapier auffüllen"},
    {"type": "bunsen", "name": "Bunsenbrenner einstellen"},
    {"type": "chemical", "name": "Chemikalien mischen"},
    {"type": "pencil_case", "name": "Mäppchen packen"},
    {"type": "keyboard", "name": "Tastatur reinigen"},
    {"type": "microscope", "name": "Mikroskop fokussieren"},
    {"type": "circuit", "name": "Schaltkreis reparieren"},
    {"type": "ball_basket", "name": "Bälle einsammeln"},
    {"type": "mats", "name": "Matten stapeln"},
    {"type": "tray_sort", "name": "Tablett sortieren"},
    {"type": "milk_carton", "name": "Milch einfüllen"},
    {"type": "pizza", "name": "Pizza schneiden"},
    {"type": "vending", "name": "Automat klemmt"},
    {"type": "barcode", "name": "Barcodes scannen"},
    {"type": "locker", "name": "Spind aufräumen"},
    {"type": "trash_bin", "name": "Müll wegbringen"},
    {"type": "pipe_leak", "name": "Rohrbruch dichten"},
]

task_buttons = [] # Wird weiter unten nach dem Laden der JSON befüllt

def draw_task_buttons(surface, buttons, player_obj, camera_x, camera_y):
    for btn in buttons:
        r = btn["rect"]
        
        player_center = player_obj.rect.center
        button_center = r.center
        distance = math.hypot(player_center[0] - button_center[0], player_center[1] - button_center[1])
        
        # Auf die Kamera-Ansicht umrechnen
        dr = r.copy()
        dr.x -= camera_x
        dr.y -= camera_y
        dr_center = dr.center
        
        # Einheitlicher, simpler Rahmen für alle Hitboxes (keine spezifischen Bilder/Zeichnungen)
        pygame.draw.rect(surface, (0, 255, 255), dr, 2, border_radius=4)
        
        if distance < 35:
            lbl_text = proximity_font.render(f"[E] {btn['name']}", True, (255, 255, 255))
            lbl_bg = pygame.Rect(dr_center[0] - lbl_text.get_width() // 2 - 6, dr.y - 32, lbl_text.get_width() + 10, lbl_text.get_height() + 5)
            pygame.draw.rect(surface, (20, 20, 20), lbl_bg, border_radius = 4)
            pygame.draw.rect(surface, (0, 220, 100), lbl_bg, width = 1, border_radius = 4)
            surface.blit(lbl_text, (dr_center[0] - lbl_text.get_width() // 2, dr.y - 30))

# ===================
# LOBBY MENÜ DRAWING
# ===================
menu_font = pygame.font.SysFont("arial", 40)
small_font = pygame.font.SysFont("arial", 28)
ip_input = TextInput(420, 300, 350, 60, small_font)
name_input = TextInput(420, 400, 350, 60, small_font)

def draw_menu():
    screen.fill((25, 25, 35))
    title = menu_font.render("MULTIPLAYER LOGIN", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 150))
    screen.blit(small_font.render("SERVER IP", True, (200, 200, 200)), (420, 260))
    screen.blit(small_font.render("NAME", True, (200, 200, 200)), (420, 360))
    ip_input.draw(screen)
    name_input.draw(screen)
    screen.blit(small_font.render("ENTER = CONNECT", True, (100, 255, 100)), (460, 520))

def draw_lobby():
    screen.fill((20, 20, 40))
    title = menu_font.render("LOBBY", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 60))
    y = 180
    for pid, pname in player_names.items():
        role = "HOST" if pid == host_id else "PLAYER"
        screen.blit(small_font.render(f"{pname} ({role})", True, (255, 255, 0)), (100, y))
        y += 50
    screen.blit(small_font.render(f"{len(player_names)}/15 PLAYERS", True, (255, 255, 255)), (100, HEIGHT - 100))
    
    if my_id == host_id:
        btn = pygame.Rect(WIDTH - 250, HEIGHT - 140, 180, 70)
        pygame.draw.rect(screen, (0, 220, 100), btn, border_radius=10)
        txt = small_font.render("START", True, (0, 0, 0))
        screen.blit(txt, (btn.centerx - txt.get_width() // 2, btn.centery - txt.get_height() // 2))

# =========================
# ASSETS & MAP INITIALISIERUNG
# =========================
base_path = "Assets/Map/Map/"
try:
    floor_img = pygame.image.load(os.path.join(base_path, "Floor.png")).convert_alpha()
    walls_img = pygame.image.load(os.path.join(base_path, "Walls.png")).convert_alpha()
    objects_img = pygame.image.load(os.path.join(base_path, "Objects.png")).convert_alpha()
except Exception as e:
    print(f"Fehler beim Laden der Map-Bilder: {e}")
    pygame.quit()
    sys.exit()

# Hitboxen und Task-Hitboxen aus der JSON laden
hitboxes, vents, plants, tasks_hitboxes, spawnpoints = load_hitboxes(os.path.join(base_path, "Hitboxes.json"))

# Task Buttons dynamisch anhand des Hitbox-Indexes generieren
for i, rect in enumerate(tasks_hitboxes):
    if i < len(TASK_TEMPLATES):
        template = TASK_TEMPLATES[i]
        task_buttons.append({
            "rect": rect,
            "type": template["type"],
            "task_index": i,
            "name": template["name"]
        })

# =========================
# HAUPTSCHLEIFE
# =========================
running = True

while running:
    dt = clock.tick(60) / 1000.0

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
                if pygame.Rect(WIDTH - 250, HEIGHT - 140, 180, 70).collidepoint(event.pos):
                    try:
                        sock.sendall(struct.pack("!B", 99))
                    except: pass

        elif state == "game":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if task_manager.active_task:
                        task_manager.reset_active_task()
                        task_manager.active_task = None
                    else:
                        running = False
                        pygame.quit()
                        sys.exit()

                # --- INTERAKTIONSTASTEN ---
                # 1. Tasks erledigen (E)
                if event.key == pygame.K_e and task_manager.active_task is None:
                    for btn in task_buttons:
                        distance = math.hypot(my_player.rect.centerx - btn["rect"].centerx, my_player.rect.centery - btn["rect"].centery)
                        if distance < 50:
                            if task_manager.start_task(btn["task_index"]) == "ALREADY_DONE":
                                already_done_timer = 90
                            break
                
                # 2. Vents und Pflanzen benutzen (Space)
                if event.key == pygame.K_SPACE:
                    cv = get_current_vent(my_player, vents)
                    if cv:
                        next_vent = vents[(vents.index(cv) + 1) % len(vents)]
                        my_player.rect.center = next_vent.center
                        try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                        except: pass
                    else:
                        cp = get_current_plant(my_player, plants)
                        if cp:
                            next_plant = plants[(plants.index(cp) + 1) % len(plants)]
                            my_player.rect.center = next_plant.center
                            try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                            except: pass

        task_manager.handle_event(event)

    # --- LOGIK & NETZWERK-UPDATES ---
    if state == "game" and task_manager.active_task is None and game_started:
        if my_player.move(pygame.key.get_pressed(), hitboxes):
            try:
                sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
            except Exception as e:
                print(f"Verbindung verloren: {e}")
                running = False

    # --- RENDERING ---
    if state == "menu":
        draw_menu()
    elif state == "lobby" and not game_started:
        draw_lobby()
    elif game_started:
        # 1. Kamera-Position berechnen
        camera_x = my_player.rect.x - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)
        camera_y = my_player.rect.y - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)

        # 2. Auf interner Surface zeichnen
        internal_surface.fill((40, 80, 40))
        internal_surface.blit(floor_img, (-camera_x, -camera_y))
        internal_surface.blit(walls_img, (-camera_x, -camera_y))
        internal_surface.blit(objects_img, (-camera_x, -camera_y))

        # Task Buttons & Overlays rendern
        draw_task_buttons(internal_surface, task_buttons, my_player, camera_x, camera_y)

        # Andere Spieler zeichnen
        for p_id, pos in other_players.items():
            enemy_img = player_images.get(p_id % len(player_images))
            if enemy_img:
                internal_surface.blit(enemy_img, (pos[0] - camera_x, pos[1] - camera_y))

        # Eigenen Spieler zeichnen
        my_player.draw(internal_surface, camera_x, camera_y)

        # 3. Interne Surface skalieren & zentrieren
        scaled_size = min(WIDTH, HEIGHT)
        scaled_surface = pygame.transform.scale(internal_surface, (scaled_size, scaled_size))
        draw_x = (WIDTH - scaled_size) // 2
        draw_y = (HEIGHT - scaled_size) // 2

        screen.fill((40, 80, 40))
        screen.blit(scaled_surface, (draw_x, draw_y))

        # 4. HUD / Task-Overlays direkt auf den Screen blitten
        if already_done_timer > 0 and task_manager.active_task is None:
            already_done_timer -= 1
            msg_text = warning_font.render("Du hast diese Aufgabe bereits erledigt!", True, (255, 80, 80))
            msg_bg = pygame.Rect(WIDTH // 2 - msg_text.get_width() // 2 - 15, 30, msg_text.get_width() + 30, 40)
            pygame.draw.rect(screen, (20, 20, 20), msg_bg, border_radius=6)
            pygame.draw.rect(screen, (255, 80, 80), msg_bg, width=2, border_radius=6)
            screen.blit(msg_text, (WIDTH // 2 - msg_text.get_width() // 2, 38))

        task_manager.draw(screen)
        task_manager.update()

    pygame.display.update()

try: sock.close()
except: pass
pygame.quit()