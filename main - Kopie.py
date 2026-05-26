import pygame
import socket
import threading
import struct
import math

import tasks
# =========================
# Einstellungen
# =========================
PLAYER_SIZE = 50
SPEED = 300
PORT = 5555

pygame.init()

screen_width, screen_height = 1200, 900
screen = pygame.display.set_mode((screen_width, screen_height))
WIDTH = screen.get_width()
HEIGHT = screen.get_height()

pygame.display.set_caption("Thalheimer is Among Us")

clock = pygame.time.Clock()

# =========================
# Bilder laden
# =========================
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
# Wände
# =========================
walls = []

# =========================
# Spieler Klasse
# =========================
class Player:
    def __init__(self, x, y, image):
        self.x = float(x)
        self.y = float(y)
        self.image = image
        self.rect = pygame.Rect(int(self.x), int(self.y), PLAYER_SIZE, PLAYER_SIZE)

    def move(self, keys, dt, walls):
        moved = False
        old_x = self.x
        old_y = self.y
        dx = 0
        dy = 0

        if keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_s]:
            dy += 1
        if keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_d]:
            dx += 1

        # =========================
        # DIAGONAL NORMALIZATION
        # =========================
        length = math.hypot(dx, dy)

        if length > 0:
            dx /= length
            dy /= length

        dx *= SPEED * dt
        dy *= SPEED * dt

        # =========================
        # X Bewegung
        # =========================
        self.x += dx
        self.rect.x = int(self.x)

        for wall in walls:
            if self.rect.colliderect(wall):
                self.x = old_x
                self.rect.x = int(self.x)

        # =========================
        # Y Bewegung
        # =========================
        self.y += dy
        self.rect.y = int(self.y)

        for wall in walls:
            if self.rect.colliderect(wall):
                self.y = old_y
                self.rect.y = int(self.y)

        # =========================
        # Bildschirmgrenzen
        # =========================
        self.x = max(0, min(self.x, WIDTH - PLAYER_SIZE))
        self.y = max(0, min(self.y, HEIGHT - PLAYER_SIZE))
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        if int(old_x) != int(self.x) or int(old_y) != int(self.y):
            moved = True

        return moved

    def draw(self, win):
        win.blit(self.image, (int(self.x), int(self.y)))

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
# Netzwerk
# =========================
other_players = {}
my_id = None
player_names = {}
player_count = 0
host_id = 0
game_started = False

def setup_socket(s):
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

def receive_data(sock):
    print("RECEIVE THREAD STARTED")
    global other_players, player_names, player_count, host_id, game_started

    while True:
        try:
            data = sock.recv(1)
            if not data:
                return
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
                data = b""
                while len(data) < 9:
                    packet = sock.recv(9 - len(data))
                    if not packet:
                        return
                    data += packet
                p_id, x, y = struct.unpack("!Bii", data)
                other_players[p_id] = [x, y]

            elif packet_type == 3:
                game_started = True
                try:
                    sock.sendall(struct.pack('!B', 2))
                    sock.sendall(struct.pack('!ii', int(my_player.x), int(my_player.y)))
                except:
                    pass

            elif packet_type == 4:
                disconnect_data = sock.recv(9)
                if len(disconnect_data) == 9:
                    p_id, x, y = struct.unpack("!Bii", disconnect_data)
                    if p_id in other_players:
                        del other_players[p_id]

        except Exception as e:
            print("RECEIVE THREAD ERROR:", e)
            break

def connect_to_server(ip, name):
    global sock, my_id, my_player, connected

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, PORT))

        setup_socket(sock)

        name_data = name.encode()

        sock.sendall(struct.pack("!B", len(name_data)))
        sock.sendall(name_data)

        my_id = struct.unpack('!B', sock.recv(1))[0]

        print("Verbunden mit ID:", my_id)

        my_player = Player(
            100 + (my_id * 30),
            100,
            player_images[my_id % len(player_images)]
        )

        threading.Thread(
            target=receive_data,
            args=(sock,),
            daemon=True
        ).start()

        connected = True

        return True

    except Exception as e:
        print("CONNECT ERROR:", e)
        return False

# ===================
# TASK SYSTEM
# ===================
task_manager = tasks.TaskManager()
proximity_font = pygame.font.SysFont("arial", 20, bold = True)
already_done_timer = 0
warning_font = pygame.font.SysFont("arial", 24, bold = True)

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

task_buttons = [
    {"rect": pygame.Rect(100, 100, 60, 70), "type": "books", "task_index": 0, "name": "Bücher sortieren"},
    {"rect": pygame.Rect(200, 100, 50, 70), "type": "chair_stack", "task_index": 1, "name": "Stühle stapeln"},
    {"rect": pygame.Rect(70, 250, 80, 80),  "type": "window", "task_index": 2, "name": "Fenster lüften"},
    {"rect": pygame.Rect(400, 100, 60, 50), "type": "pc_download", "task_index": 3, "name": "Daten downloaden"},
    {"rect": pygame.Rect(150, 380, 80, 50), "type": "board", "task_index": 4, "name": "Tafel wischen"},
    {"rect": pygame.Rect(460, 340, 70, 50), "type": "projector", "task_index": 5, "name": "Beamer verkabeln"},
    {"rect": pygame.Rect(520, 100, 60, 50), "type": "pc_scan", "task_index": 6, "name": "Virenscan"},
    {"rect": pygame.Rect(520, 220, 65, 60), "type": "printer", "task_index": 7, "name": "Druckerpapier auffüllen"},
    {"rect": pygame.Rect(750, 100, 40, 70), "type": "bunsen", "task_index": 8, "name": "Bunsenbrenner einstellen"},
    {"rect": pygame.Rect(850, 100, 50, 65), "type": "chemical", "task_index": 9, "name": "Chemikalien mischen"},
    {"rect": pygame.Rect(220, 250, 50, 60), "type": "pencil_case", "task_index": 10, "name": "Mäppchen packen"},
    {"rect": pygame.Rect(400, 220, 60, 40), "type": "keyboard", "task_index": 11, "name": "Tastatur reinigen"},
    {"rect": pygame.Rect(750, 220, 45, 65), "type": "microscope", "task_index": 12, "name": "Mikroskop fokussieren"},
    {"rect": pygame.Rect(850, 220, 60, 60), "type": "circuit", "task_index": 13, "name": "Schaltkreis reparieren"},
    {"rect": pygame.Rect(100, 520, 60, 60), "type": "ball_basket", "task_index": 14, "name": "Bälle einsammeln"},
    {"rect": pygame.Rect(220, 530, 80, 45), "type": "mats", "task_index": 15, "name": "Matten stapeln"},
    {"rect": pygame.Rect(420, 540, 70, 65), "type": "tray_sort", "task_index": 16, "name": "Tablett sortieren"},
    {"rect": pygame.Rect(540, 540, 50, 65), "type": "milk_carton", "task_index": 17, "name": "Milch einfüllen"},
    {"rect": pygame.Rect(640, 540, 60, 60), "type": "pizza", "task_index": 18, "name": "Pizza schneiden"},
    {"rect": pygame.Rect(760, 510, 65, 90), "type": "vending", "task_index": 19, "name": "Automat klemmt"},
    {"rect": pygame.Rect(880, 540, 55, 60), "type": "barcode", "task_index": 20, "name": "Barcodes scannen"},
    {"rect": pygame.Rect(1020, 200, 45, 70), "type": "locker", "task_index": 21, "name": "Spind aufräumen"},
    {"rect": pygame.Rect(1020, 340, 50, 70), "type": "trash_bin", "task_index": 22, "name": "Müll wegbringen"},
    {"rect": pygame.Rect(800, 340, 70, 40), "type": "pipe_leak", "task_index": 23, "name": "Rohrbruch dichten"},
]

def draw_task_buttons(screen, buttons, player_obj):
    for btn in buttons:
        r = btn["rect"]
        t = btn["type"]
        
        # Abstand zwischen der Mitte des Spieler-Rects und der Mitte des Button-Rects
        player_center = player_obj.rect.center
        button_center = r.center
        distance = math.hypot(player_center[0] - button_center[0], player_center[1] - button_center[1])
        
        # Text-Indikator rendern, wenn man in der Nähe steht
        if distance < 85:
            lbl_text = proximity_font.render(f"[E] {btn['name']}", True, (255, 255, 255))
            lbl_bg = pygame.Rect(button_center[0] - lbl_text.get_width() // 2 - 6, r.y - 32, lbl_text.get_width() + 12, 24)
            pygame.draw.rect(screen, (20, 20, 20), lbl_bg, border_radius=4)
            pygame.draw.rect(screen, (0, 220, 100), lbl_bg, width=1, border_radius=4)
            screen.blit(lbl_text, (button_center[0] - lbl_text.get_width() // 2, r.y - 30))

        # --- AB HIER FOLGT DAS VISUELLE DESIGN DER BUTTONS ---
        # Optionaler Hover-Effekt per Maus
        mouse_pos = pygame.mouse.get_pos()
        if r.collidepoint(mouse_pos):
            pygame.draw.rect(screen, (60, 60, 70), r.inflate(8, 8), border_radius=8)

        # 1. BÜCHERSORTIEREN
        if t == "books":
            pygame.draw.rect(screen, (200, 50, 50), (r.x, r.y, 18, r.height), border_radius=3)
            pygame.draw.rect(screen, (50, 120, 200), (r.x + 21, r.y + 10, 18, r.height - 10), border_radius=3)
            pygame.draw.rect(screen, (50, 180, 80), (r.x + 42, r.y + 5, 18, r.height - 5), border_radius=3)

        # 2. STUHLSTAPEL
        elif t == "chair_stack":
            for offset in [0, 15]:
                cy = r.y + offset
                pygame.draw.rect(screen, (160, 100, 60), (r.x, cy + 20, r.width, 10))
                pygame.draw.rect(screen, (140, 80, 40), (r.x, cy, 8, 20))
                pygame.draw.line(screen, (50, 50, 50), (r.x + 5, cy + 30), (r.x + 5, r.y + 65), 3)
                pygame.draw.line(screen, (50, 50, 50), (r.x + r.width - 5, cy + 30), (r.x + r.width - 5, r.y + 65), 3)

        # 3. VENDING MACHINE (Der Snackautomat)
        elif t == "vending":
            pygame.draw.rect(screen, (30, 40, 50), r, border_radius=5)
            pygame.draw.rect(screen, (100, 200, 255), (r.x + 8, r.y + 10, r.width - 16, 40))
            pygame.draw.circle(screen, (230, 50, 50), (r.x + 18, r.y + 25), 4)
            pygame.draw.circle(screen, (230, 200, 50), (r.x + 32, r.y + 25), 4)
            pygame.draw.rect(screen, (200, 200, 200), (r.x + r.width - 12, r.y + 55, 6, 12)) 
            pygame.draw.rect(screen, (10, 10, 10), (r.x + 12, r.y + 72, r.width - 24, 12))

        # 4. PC / DATA DOWNLOAD & SCANS
        elif t in ["pc_download", "pc_download_2", "pc_scan"]:
            pygame.draw.rect(screen, (190, 195, 200), (r.x, r.y, r.width, r.height - 15), border_radius=4)
            pygame.draw.rect(screen, (20, 20, 20), (r.x + 4, r.y + 4, r.width - 8, r.height - 23))
            pygame.draw.rect(screen, (130, 135, 140), (r.x + r.width//2 - 6, r.y + r.height - 15, 12, 15))
            if "download" in t:
                pygame.draw.rect(screen, (0, 200, 50), (r.x + 10, r.y + 15, r.width - 20, 8))
            else:
                pygame.draw.line(screen, (220, 40, 40), (r.x + 15, r.y + 6), (r.x + r.width - 15, r.y + r.height - 25), 3)
                pygame.draw.line(screen, (220, 40, 40), (r.x + r.width - 15, r.y + 6), (r.x + 15, r.y + r.height - 25), 3)

        # 5. FENSTER
        elif t == "window":
            pygame.draw.rect(screen, (100, 180, 240), r)
            pygame.draw.rect(screen, (240, 240, 240), r, width=4)
            pygame.draw.line(screen, (240, 240, 240), (r.centerx, r.y), (r.centerx, r.bottom), 3)
            pygame.draw.line(screen, (240, 240, 240), (r.x, r.centery), (r.right, r.centery), 3)

        # 6. TAFEL
        elif t == "board":
            pygame.draw.rect(screen, (30, 90, 50), r)
            pygame.draw.rect(screen, (139, 69, 19), r, width=4)
            pygame.draw.line(screen, (255, 255, 255), (r.x + 15, r.y + 15), (r.x + 40, r.y + 20), 2)

        # 7. PROJEKTOR (Beamer)
        elif t == "projector":
            pygame.draw.rect(screen, (220, 220, 220), (r.x, r.y, r.width, r.height - 10), border_radius=3)
            pygame.draw.circle(screen, (50, 50, 50), (r.right - 15, r.y + r.height // 2 - 5), 8)
            pygame.draw.polygon(screen, (255, 255, 200), [(r.right - 10, r.y + 15), (r.right + 20, r.y - 5), (r.right + 20, r.y + 35)])

        # 8. PRINTER
        elif t == "printer":
            pygame.draw.rect(screen, (100, 105, 110), (r.x, r.y, r.width, r.height - 15), border_top_left_radius=5, border_top_right_radius=5)
            pygame.draw.rect(screen, (20, 20, 20), (r.x + 10, r.y + r.height - 20, r.width - 20, 6))
            pygame.draw.rect(screen, (255, 255, 255), (r.x + 15, r.y + r.height - 15, r.width - 30, 15))

        # 9. BUNSENBRENNER
        elif t == "bunsen":
            pygame.draw.line(screen, (80, 80, 80), (r.centerx, r.y + 20), (r.centerx, r.bottom), 4)
            pygame.draw.rect(screen, (50, 80, 200), (r.x, r.bottom - 12, r.width, 12), border_radius=3)
            pygame.draw.polygon(screen, (255, 120, 0), [(r.centerx, r.y), (r.centerx - 10, r.y + 22), (r.centerx + 10, r.y + 22)])

        # 10. CHEMIE-KOLBEN
        elif t == "chemical":
            pygame.draw.rect(screen, (200, 220, 240), (r.centerx - 6, r.y, 12, 30))
            pygame.draw.circle(screen, (200, 220, 240), (r.centerx, r.y + r.height - 22), 22)
            pygame.draw.circle(screen, (150, 50, 200), (r.centerx, r.y + r.height - 20), 16)

        # 11. FEDERMAPPE
        elif t == "pencil_case":
            pygame.draw.rect(screen, (210, 90, 150), r, border_radius=8)
            pygame.draw.line(screen, (50, 50, 50), (r.x, r.centery), (r.right, r.centery), 3)

        # 12. TASTATUR
        elif t == "keyboard":
            pygame.draw.rect(screen, (40, 40, 40), r, border_radius=4)
            for i in range(3):
                pygame.draw.line(screen, (200, 200, 200), (r.x + 5, r.y + 8 + i*10), (r.right - 5, r.y + 8 + i*10), 2)

        # 13. MIKROSKOP
        elif t == "microscope":
            pygame.draw.rect(screen, (40, 40, 45), (r.x + 5, r.bottom - 10, r.width - 10, 10))
            pygame.draw.line(screen, (100, 100, 100), (r.x + 10, r.bottom - 10), (r.x + 10, r.y + 15), 5)
            pygame.draw.rect(screen, (200, 200, 200), (r.x + 12, r.y + 10, 14, 25))

        # 14. SCHALTKREIS
        elif t == "circuit":
            pygame.draw.rect(screen, (20, 120, 60), r, border_radius=4)
            pygame.draw.line(screen, (200, 200, 200), (r.x + 10, r.y + 10), (r.x + 30, r.y + 30), 3)
            pygame.draw.circle(screen, (220, 220, 50), (r.x + 10, r.y + 10), 5)

        # 15. BALLKORB
        elif t == "ball_basket":
            pygame.draw.rect(screen, (210, 140, 60), r, width=3, border_radius=2)
            pygame.draw.circle(screen, (230, 90, 20), (r.x + 20, r.y + 40), 12)
            pygame.draw.circle(screen, (230, 90, 20), (r.x + 40, r.y + 35), 12)

        # 16. MATTENSTAPEL
        elif t == "mats":
            for i in range(3):
                pygame.draw.rect(screen, (30, 90, 180), (r.x, r.y + i*13, r.width, 10), border_radius=2)

        # 17. TABLETT-WAGEN
        elif t == "tray_sort":
            pygame.draw.rect(screen, (150, 155, 160), r, width=3)
            pygame.draw.line(screen, (180, 50, 50), (r.x + 5, r.y + 15), (r.right - 5, r.y + 15), 4)
            pygame.draw.line(screen, (50, 150, 50), (r.x + 5, r.y + 35), (r.right - 5, r.y + 35), 4)

        # 18. MILCHTÜTE
        elif t == "milk_carton":
            pygame.draw.rect(screen, (240, 240, 240), (r.x, r.y + 15, r.width, r.height - 15))
            pygame.draw.polygon(screen, (100, 150, 220), [(r.x, r.y + 15), (r.centerx, r.y), (r.right, r.y + 15)])
            pygame.draw.rect(screen, (100, 150, 220), (r.x, r.y + 30, r.width, 12))

        # 19. PIZZA
        elif t == "pizza":
            pygame.draw.circle(screen, (220, 160, 60), r.center, r.width // 2)
            pygame.draw.circle(screen, (200, 40, 40), r.center, r.width // 2 - 4)
            pygame.draw.circle(screen, (130, 20, 20), (r.centerx - 10, r.centery - 5), 5)

        # 20. BARCODE-SCANNER
        elif t == "barcode":
            pygame.draw.rect(screen, (30, 30, 30), (r.x + 15, r.y, r.width - 30, r.height))
            pygame.draw.rect(screen, (60, 65, 70), (r.x, r.y, r.width, 22), border_radius=4)
            pygame.draw.line(screen, (255, 0, 0), (r.x + 5, r.y + 11), (r.right - 5, r.y + 11), 2)

        # 21. SPIND
        elif t == "locker":
            pygame.draw.rect(screen, (120, 130, 140), r, border_radius=2)
            pygame.draw.rect(screen, (80, 90, 100), (r.x + 5, r.y + 5, r.width - 10, r.height - 10))
            pygame.draw.line(screen, (20, 20, 20), (r.right - 12, r.y + r.height // 2 - 8), (r.right - 12, r.y + r.height // 2 + 8), 3)

        # 22. MÜLLTONNE
        elif t == "trash_bin":
            pygame.draw.polygon(screen, (50, 50, 50), [(r.x + 8, r.bottom), (r.right - 8, r.bottom), (r.right, r.y + 15), (r.x, r.y + 15)])
            pygame.draw.rect(screen, (70, 70, 70), (r.x - 4, r.y, r.width + 8, 15), border_radius=3)

        # 23. ROHR / WASSERLECK
        elif t == "pipe_leak":
            pygame.draw.rect(screen, (100, 100, 100), r)
            pygame.draw.rect(screen, (50, 150, 255), (r.centerx - 5, r.y - 15, 10, 15))

        # Rahmen um den Button
        pygame.draw.rect(screen, (20, 20, 20), r, width=2, border_radius=4)

font = pygame.font.SysFont("arial", 40)

# ===================
# LOBBY SYSTEM
# ===================
state = "menu"

menu_font = pygame.font.SysFont("arial", 40)
small_font = pygame.font.SysFont("arial", 28)

ip_input = TextInput(420, 300, 350, 60, small_font)
name_input = TextInput(420, 400, 350, 60, small_font)

sock = None
connected = False

def draw_menu():
    screen.fill((25, 25, 35))

    title = menu_font.render("MULTIPLAYER LOGIN", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 150))

    ip_text = small_font.render("SERVER IP", True, (200, 200, 200))
    screen.blit(ip_text, (420, 260))

    name_text = small_font.render("NAME", True, (200, 200, 200))
    screen.blit(name_text, (420, 360))

    ip_input.draw(screen)
    name_input.draw(screen)

    info = small_font.render("ENTER = CONNECT", True, (100, 255, 100))
    screen.blit(info, (460, 520))

def draw_lobby():
    screen.fill((20, 20, 40))

    title = menu_font.render("LOBBY", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 60))

    y = 180

    for pid, pname in player_names.items():

        role = "HOST" if pid == host_id else "PLAYER"

        txt = small_font.render(
            f"{pname} ({role})",
            True,
            (255, 255, 0)
        )

        screen.blit(txt, (100, y))

        y += 50

    count = small_font.render(
        f"{len(player_names)}/15 PLAYERS",
        True,
        (255, 255, 255)
    )

    screen.blit(count, (100, HEIGHT - 100))

    # START BUTTON
    if my_id == host_id:

        button_rect = pygame.Rect(
            WIDTH - 250,
            HEIGHT - 140,
            180,
            70
        )

        pygame.draw.rect(
            screen,
            (0, 220, 100),
            button_rect,
            border_radius=10
        )

        txt = small_font.render(
            "START",
            True,
            (0, 0, 0)
        )

        screen.blit(
            txt,
            (
                button_rect.centerx - txt.get_width() // 2,
                button_rect.centery - txt.get_height() // 2
            )
        )

        return button_rect

    return None

# ===================
# Spielschleife
# ===================
running = True

while running:
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            pygame.quit()
            exit()

        if state == "menu":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if connect_to_server(ip_input.text, name_input.text):
                        state = "lobby"

            # Danach Inputs verarbeiten
            ip_input.handle_event(event)
            name_input.handle_event(event)

        elif state == "lobby":
            if event.type == pygame.MOUSEBUTTONDOWN:
                if my_id == host_id:
                    start_btn = pygame.Rect(WIDTH - 250, HEIGHT - 140, 180, 70)
                    if start_btn.collidepoint(event.pos):
                        try:
                            sock.sendall(struct.pack("!B", 99))
                            state = "game"
                        except:
                            pass

        elif state == "game":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if task_manager.active_task:
                        task_manager.reset_active_task()
                        task_manager.active_task = None
                    else:
                        running = False
                        pygame.quit()
                        exit()

                if event.key == pygame.K_e:
                    if task_manager.active_task is None:
                        for btn in task_buttons:
                            player_center = my_player.rect.center
                            button_center = btn["rect"].center
                            distance = math.hypot(player_center[0] - button_center[0], player_center[1] - button_center[1])
                            if distance < 85:
                                result = task_manager.start_task(btn["task_index"])
                                if result == "ALREADY_DONE":
                                    already_done_timer = 90 # Zeige Warnung für 1.5 Sek
                                break

        task_manager.handle_event(event)

    keys = pygame.key.get_pressed()
    has_moved = False

    if task_manager.active_task is None and game_started:
        has_moved = my_player.move(keys, dt, walls)

    if has_moved:
        try:
            data = struct.pack('!Bii', 2, int(my_player.x), int(my_player.y))
            sock.sendall(data)
        except Exception as e:
            print(f"Verbindung verloren: {e}")
            running = False

    # =========================
    # MENU
    # =========================
    if state == "menu":
        draw_menu()

    # =========================
    # LOBBY
    # =========================
    elif state == "lobby" and not game_started:
        draw_lobby()

    # =========================
    # GAME
    # =========================
    elif game_started:

        screen.fill((30, 30, 30))

        # Wände
        for wall in walls:
            pygame.draw.rect(screen, (100, 100, 100), wall)

        # Andere Spieler
        for p_id, pos in other_players.items():
            enemy_img = player_images.get(p_id % len(player_images))
            screen.blit(enemy_img, (pos[0], pos[1]))

        # Eigener Spieler
        my_player.draw(screen)

        # Buttons
        if task_manager.active_task is None:
            draw_task_buttons(screen, task_buttons, my_player)

        # Warning
        if already_done_timer > 0 and task_manager.active_task is None:
            already_done_timer -= 1

            msg_text = warning_font.render("Du hast diese Aufgabe bereits erledigt!", True, (255, 80, 80))
            msg_bg = pygame.Rect(WIDTH // 2 - msg_text.get_width() // 2 - 15, 30, msg_text.get_width() + 30, 40)
            pygame.draw.rect(screen, (20, 20, 20), msg_bg, border_radius = 6)
            pygame.draw.rect(screen, (255, 80, 80), msg_bg, width = 2, border_radius = 6)

            screen.blit(msg_text, (WIDTH // 2 - msg_text.get_width() // 2, 38))

        task_manager.draw(screen)
        task_manager.update()

    pygame.display.update()

try:
    sock.close()
except:
    pass

pygame.quit()