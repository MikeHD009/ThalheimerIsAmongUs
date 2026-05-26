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
    hitboxes, vents, plants = [], [], []
    if not os.path.exists(filepath):
        print(f"WARNUNG: Hitbox-Datei nicht gefunden: {filepath}")
        return hitboxes, vents, plants
    
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
    return hitboxes, vents, plants

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

def connect_to_server(ip, name):
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

        my_player = Player(100 + (my_id * 30), 100, player_images[my_id % len(player_images)])
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
proximity_font = pygame.font.SysFont("arial", 16, bold=True)
already_done_timer = 0
warning_font = pygame.font.SysFont("arial", 24, bold=True)

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

# Die Task Buttons liegen im World-Space (Koordinaten auf der Tiled-Map)
task_buttons = [
    {"rect": pygame.Rect(100, 100, 24, 24), "type": "books", "task_index": 0, "name": "Bücher sortieren"},
    {"rect": pygame.Rect(200, 100, 24, 24), "type": "chair_stack", "task_index": 1, "name": "Stühle stapeln"},
    {"rect": pygame.Rect(70, 250, 24, 24),  "type": "window", "task_index": 2, "name": "Fenster lüften"},
    {"rect": pygame.Rect(400, 100, 24, 24), "type": "pc_download", "task_index": 3, "name": "Daten downloaden"},
    {"rect": pygame.Rect(150, 380, 24, 24), "type": "board", "task_index": 4, "name": "Tafel wischen"},
    {"rect": pygame.Rect(460, 340, 24, 24), "type": "projector", "task_index": 5, "name": "Beamer verkabeln"},
    {"rect": pygame.Rect(520, 100, 2424, 24), "type": "pc_scan", "task_index": 6, "name": "Virenscan"},
    {"rect": pygame.Rect(520, 220, 2424, 24), "type": "printer", "task_index": 7, "name": "Druckerpapier auffüllen"},
    {"rect": pygame.Rect(750, 100, 2424, 24), "type": "bunsen", "task_index": 8, "name": "Bunsenbrenner einstellen"},
    {"rect": pygame.Rect(850, 100, 2424, 24), "type": "chemical", "task_index": 9, "name": "Chemikalien mischen"},
    {"rect": pygame.Rect(220, 250, 2424, 24), "type": "pencil_case", "task_index": 10, "name": "Mäppchen packen"},
    {"rect": pygame.Rect(400, 220, 24, 24), "type": "keyboard", "task_index": 11, "name": "Tastatur reinigen"},
    {"rect": pygame.Rect(750, 220, 24, 24), "type": "microscope", "task_index": 12, "name": "Mikroskop fokussieren"},
    {"rect": pygame.Rect(850, 220, 24, 24), "type": "circuit", "task_index": 13, "name": "Schaltkreis reparieren"},
    {"rect": pygame.Rect(100, 520, 24, 24), "type": "ball_basket", "task_index": 14, "name": "Bälle einsammeln"},
    {"rect": pygame.Rect(220, 530, 24, 24), "type": "mats", "task_index": 15, "name": "Matten stapeln"},
    {"rect": pygame.Rect(420, 540, 24, 24), "type": "tray_sort", "task_index": 16, "name": "Tablett sortieren"},
    {"rect": pygame.Rect(540, 540, 24, 24), "type": "milk_carton", "task_index": 17, "name": "Milch einfüllen"},
    {"rect": pygame.Rect(640, 540, 24, 24), "type": "pizza", "task_index": 18, "name": "Pizza schneiden"},
    {"rect": pygame.Rect(760, 510, 24, 24), "type": "vending", "task_index": 19, "name": "Automat klemmt"},
    {"rect": pygame.Rect(880, 540, 24, 24), "type": "barcode", "task_index": 20, "name": "Barcodes scannen"},
    {"rect": pygame.Rect(1020, 200, 24, 24), "type": "locker", "task_index": 21, "name": "Spind aufräumen"},
    {"rect": pygame.Rect(1020, 340, 24, 24), "type": "trash_bin", "task_index": 22, "name": "Müll wegbringen"},
    {"rect": pygame.Rect(800, 340, 24, 24), "type": "pipe_leak", "task_index": 23, "name": "Rohrbruch dichten"},
]

def draw_task_buttons(surface, buttons, player_obj, camera_x, camera_y):
    for btn in buttons:
        r = btn["rect"]
        t = btn["type"]
        
        player_center = player_obj.rect.center
        button_center = r.center
        distance = math.hypot(player_center[0] - button_center[0], player_center[1] - button_center[1])
        
        # Auf die Kamera-Ansicht umrechnen
        dr = r.copy()
        dr.x -= camera_x
        dr.y -= camera_y
        dr_center = dr.center
        
        if distance < 50:
            lbl_text = proximity_font.render(f"[E] {btn['name']}", True, (255, 255, 255))
            lbl_bg = pygame.Rect(dr_center[0] - lbl_text.get_width() // 2 - 6, dr.y - 32, lbl_text.get_width() + 12, 24)
            pygame.draw.rect(surface, (20, 20, 20), lbl_bg, border_radius=4)
            pygame.draw.rect(surface, (0, 220, 100), lbl_bg, width=1, border_radius=4)
            surface.blit(lbl_text, (dr_center[0] - lbl_text.get_width() // 2, dr.y - 30))

        # Render-Anweisungen angepasst auf das kleine Koordinatensystem
        if t == "books":
            pygame.draw.rect(surface, (200, 50, 50), (dr.x, dr.y, 18, dr.height), border_radius=3)
            pygame.draw.rect(surface, (50, 120, 200), (dr.x + 21, dr.y + 10, 18, dr.height - 10), border_radius=3)
            pygame.draw.rect(surface, (50, 180, 80), (dr.x + 42, dr.y + 5, 18, dr.height - 5), border_radius=3)
        elif t == "chair_stack":
            for offset in [0, 15]:
                cy = dr.y + offset
                pygame.draw.rect(surface, (160, 100, 60), (dr.x, cy + 20, dr.width, 10))
                pygame.draw.rect(surface, (140, 80, 40), (dr.x, cy, 8, 20))
                pygame.draw.line(surface, (50, 50, 50), (dr.x + 5, cy + 30), (dr.x + 5, dr.y + 65), 3)
                pygame.draw.line(surface, (50, 50, 50), (dr.x + dr.width - 5, cy + 30), (dr.x + dr.width - 5, dr.y + 65), 3)
        elif t == "vending":
            pygame.draw.rect(surface, (30, 40, 50), dr, border_radius=5)
            pygame.draw.rect(surface, (100, 200, 255), (dr.x + 8, dr.y + 10, dr.width - 16, 40))
            pygame.draw.circle(surface, (230, 50, 50), (dr.x + 18, dr.y + 25), 4)
            pygame.draw.circle(surface, (230, 200, 50), (dr.x + 32, dr.y + 25), 4)
            pygame.draw.rect(surface, (200, 200, 200), (dr.right - 12, dr.y + 55, 6, 12)) 
            pygame.draw.rect(surface, (10, 10, 10), (dr.x + 12, dr.y + 72, dr.width - 24, 12))
        elif t in ["pc_download", "pc_download_2", "pc_scan"]:
            pygame.draw.rect(surface, (190, 195, 200), (dr.x, dr.y, dr.width, dr.height - 15), border_radius=4)
            pygame.draw.rect(surface, (20, 20, 20), (dr.x + 4, dr.y + 4, dr.width - 8, dr.height - 23))
            pygame.draw.rect(surface, (130, 135, 140), (dr.x + dr.width//2 - 6, dr.y + dr.height - 15, 12, 15))
            if "download" in t: pygame.draw.rect(surface, (0, 200, 50), (dr.x + 10, dr.y + 15, dr.width - 20, 8))
            else:
                pygame.draw.line(surface, (220, 40, 40), (dr.x + 15, dr.y + 6), (dr.right - 15, dr.bottom - 25), 3)
                pygame.draw.line(surface, (220, 40, 40), (dr.right - 15, dr.y + 6), (dr.x + 15, dr.bottom - 25), 3)
        elif t == "window":
            pygame.draw.rect(surface, (100, 180, 240), dr)
            pygame.draw.rect(surface, (240, 240, 240), dr, width=4)
            pygame.draw.line(surface, (240, 240, 240), (dr.centerx, dr.y), (dr.centerx, dr.bottom), 3)
            pygame.draw.line(surface, (240, 240, 240), (dr.x, dr.centery), (dr.right, dr.centery), 3)
        elif t == "board":
            pygame.draw.rect(surface, (30, 90, 50), dr)
            pygame.draw.rect(surface, (139, 69, 19), dr, width=4)
            pygame.draw.line(surface, (255, 255, 255), (dr.x + 15, dr.y + 15), (dr.x + 40, dr.y + 20), 2)
        elif t == "projector":
            pygame.draw.rect(surface, (220, 220, 220), (dr.x, dr.y, dr.width, dr.height - 10), border_radius=3)
            pygame.draw.circle(surface, (50, 50, 50), (dr.right - 15, dr.y + dr.height // 2 - 5), 8)
            pygame.draw.polygon(surface, (255, 255, 200), [(dr.right - 10, dr.y + 15), (dr.right + 20, dr.y - 5), (dr.right + 20, dr.y + 35)])
        elif t == "printer":
            pygame.draw.rect(surface, (100, 105, 110), (dr.x, dr.y, dr.width, dr.height - 15), border_top_left_radius=5, border_top_right_radius=5)
            pygame.draw.rect(surface, (20, 20, 20), (dr.x + 10, dr.y + dr.height - 20, dr.width - 20, 6))
            pygame.draw.rect(surface, (255, 255, 255), (dr.x + 15, dr.y + dr.height - 15, dr.width - 30, 15))
        elif t == "bunsen":
            pygame.draw.line(surface, (80, 80, 80), (dr.centerx, dr.y + 20), (dr.centerx, dr.bottom), 4)
            pygame.draw.rect(surface, (50, 80, 200), (dr.x, dr.bottom - 12, dr.width, 12), border_radius=3)
            pygame.draw.polygon(surface, (255, 120, 0), [(dr.centerx, dr.y), (dr.centerx - 10, dr.y + 22), (dr.centerx + 10, dr.y + 22)])
        elif t == "chemical":
            pygame.draw.rect(surface, (200, 220, 240), (dr.centerx - 6, dr.y, 12, 30))
            pygame.draw.circle(surface, (200, 220, 240), (dr.centerx, dr.bottom - 22), 22)
            pygame.draw.circle(surface, (150, 50, 200), (dr.centerx, dr.bottom - 20), 16)
        elif t == "pencil_case":
            pygame.draw.rect(surface, (210, 90, 150), dr, border_radius=8)
            pygame.draw.line(surface, (50, 50, 50), (dr.x, dr.centery), (dr.right, dr.centery), 3)
        elif t == "keyboard":
            pygame.draw.rect(surface, (40, 40, 40), dr, border_radius=4)
            for i in range(3): pygame.draw.line(surface, (200, 200, 200), (dr.x + 5, dr.y + 8 + i*10), (dr.right - 5, dr.y + 8 + i*10), 2)
        elif t == "microscope":
            pygame.draw.rect(surface, (40, 40, 45), (dr.x + 5, dr.bottom - 10, dr.width - 10, 10))
            pygame.draw.line(surface, (100, 100, 100), (dr.x + 10, dr.bottom - 10), (dr.x + 10, dr.y + 15), 5)
            pygame.draw.rect(surface, (200, 200, 200), (dr.x + 12, dr.y + 10, 14, 25))
        elif t == "circuit":
            pygame.draw.rect(surface, (20, 120, 60), dr, border_radius=4)
            pygame.draw.line(surface, (200, 200, 200), (dr.x + 10, dr.y + 10), (dr.x + 30, dr.y + 30), 3)
            pygame.draw.circle(surface, (220, 220, 50), (dr.x + 10, dr.y + 10), 5)
        elif t == "ball_basket":
            pygame.draw.rect(surface, (210, 140, 60), dr, width=3, border_radius=2)
            pygame.draw.circle(surface, (230, 90, 20), (dr.x + 20, dr.y + 40), 12)
            pygame.draw.circle(surface, (230, 90, 20), (dr.x + 40, dr.y + 35), 12)
        elif t == "mats":
            for i in range(3): pygame.draw.rect(surface, (30, 90, 180), (dr.x, dr.y + i*13, dr.width, 10), border_radius=2)
        elif t == "tray_sort":
            pygame.draw.rect(surface, (150, 155, 160), dr, width=3)
            pygame.draw.line(surface, (180, 50, 50), (dr.x + 5, dr.y + 15), (dr.right - 5, dr.y + 15), 4)
            pygame.draw.line(surface, (50, 150, 50), (dr.x + 5, dr.y + 35), (dr.right - 5, dr.y + 35), 4)
        elif t == "milk_carton":
            pygame.draw.rect(surface, (240, 240, 240), (dr.x, dr.y + 15, dr.width, dr.height - 15))
            pygame.draw.polygon(surface, (100, 150, 220), [(dr.x, dr.y + 15), (dr.centerx, dr.y), (dr.right, dr.y + 15)])
            pygame.draw.rect(surface, (100, 150, 220), (dr.x, dr.y + 30, dr.width, 12))
        elif t == "pizza":
            pygame.draw.circle(surface, (220, 160, 60), dr_center, dr.width // 2)
            pygame.draw.circle(surface, (200, 40, 40), dr_center, dr.width // 2 - 4)
            pygame.draw.circle(surface, (130, 20, 20), (dr_center[0] - 10, dr_center[1] - 5), 5)
        elif t == "barcode":
            pygame.draw.rect(surface, (30, 30, 30), (dr.x + 15, dr.y, dr.width - 30, dr.height))
            pygame.draw.rect(surface, (60, 65, 70), (dr.x, dr.y, dr.width, 22), border_radius=4)
            pygame.draw.line(surface, (255, 0, 0), (dr.x + 5, dr.y + 11), (dr.right - 5, dr.y + 11), 2)
        elif t == "locker":
            pygame.draw.rect(surface, (120, 130, 140), dr, border_radius=2)
            pygame.draw.rect(surface, (80, 90, 100), (dr.x + 5, dr.y + 5, dr.width - 10, dr.height - 10))
            pygame.draw.line(surface, (20, 20, 20), (dr.right - 12, dr.y + dr.height // 2 - 8), (dr.right - 12, dr.y + dr.height // 2 + 8), 3)
        elif t == "trash_bin":
            pygame.draw.polygon(surface, (50, 50, 50), [(dr.x + 8, dr.bottom), (dr.right - 8, dr.bottom), (dr.right, dr.y + 15), (dr.x, dr.y + 15)])
            pygame.draw.rect(surface, (70, 70, 70), (dr.x - 4, dr.y, dr.width + 8, 15), border_radius=3)
        elif t == "pipe_leak":
            pygame.draw.rect(surface, (100, 100, 100), dr)
            pygame.draw.rect(surface, (50, 150, 255), (dr.centerx - 5, dr.y - 15, 10, 15))
        pygame.draw.rect(surface, (20, 20, 20), dr, width=2, border_radius=4)

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

hitboxes, vents, plants = load_hitboxes(os.path.join(base_path, "Hitboxes.json"))

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
                if connect_to_server(ip_input.text, name_input.text):
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