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

pygame.display.set_caption("WLAN Multiplayer")

clock = pygame.time.Clock()

# =========================
# Bilder laden
# =========================
PLAYER_COLORS = ["lime", "banana", "red", "blue", "green", "orange", "yellow", "black", "white", "purple", "brown", "cyan", "maroon", "rose", "coral"]
player_images = {}

# Hier laden wir einfach alle verfügbaren Assets (du musst schauen, wie sie in deinem Ordner heißen)
for i, color in enumerate(PLAYER_COLORS):
    try:
        img = pygame.image.load(f"Assets/Character/All_colors/{color}.png").convert_alpha()
        player_images[i] = pygame.transform.scale(img, (PLAYER_SIZE, PLAYER_SIZE))
    except:
        # Fallback, falls eine Farbe fehlt, nimm die erste
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

        self.rect = pygame.Rect(
            int(self.x),
            int(self.y),
            PLAYER_SIZE,
            PLAYER_SIZE
        )

    def move(self, keys, dt, walls):
        moved = False

        old_x = self.x
        old_y = self.y

        dx = 0
        dy = 0

        if keys[pygame.K_w]:
            dy -= SPEED * dt

        if keys[pygame.K_s]:
            dy += SPEED * dt

        if keys[pygame.K_a]:
            dx -= SPEED * dt

        if keys[pygame.K_d]:
            dx += SPEED * dt

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

        # Bildschirmgrenzen
        self.x = max(0, min(self.x, WIDTH - PLAYER_SIZE))
        self.y = max(0, min(self.y, HEIGHT - PLAYER_SIZE))

        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        if int(old_x) != int(self.x) or int(old_y) != int(self.y):
            moved = True

        return moved

    def draw(self, win):
        win.blit(self.image, (int(self.x), int(self.y)))

# =========================
# Button Klasse
# =========================
class Button:
    def __init__(self, x, y, w, h, text, font):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.font = font

    def draw(self, screen):
        pygame.draw.rect(screen, (0, 200, 255), self.rect, border_radius=10)
        label = self.font.render(self.text, True, (0, 0, 0))
        screen.blit(
            label,
            (
                self.rect.x + (self.rect.width - label.get_width()) // 2,
                self.rect.y + (self.rect.height - label.get_height()) // 2
            )
        )

    def clicked(self, pos):
        return self.rect.collidepoint(pos)

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
                self.text += event.unicode

    def draw(self, screen):
        pygame.draw.rect(screen, (255, 255, 255), self.rect, border_radius=8)
        pygame.draw.rect(screen, (0, 0, 0), self.rect, 2, border_radius=8)

        txt = self.font.render(self.text, True, (0, 0, 0))
        screen.blit(txt, (self.rect.x + 10, self.rect.y + 10))

# =========================
# Netzwerk
# =========================
# Speichert alle ANDEREN Spieler: {player_id: [x, y]}
other_players = {}
my_id = None
player_names = {}
player_count = 0
host_id = 0
game_started = False

def setup_socket(s):
    # TCP_NODELAY sorgt dafür, dass Positionsdaten ohne Verzögerung 
    # direkt gesendet werden (wichtig für Echtzeit-Spiele)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

def receive_data(sock):

    print("RECEIVE THREAD STARTED")

    global other_players
    global player_names
    global player_count
    global host_id
    global game_started

    while True:
        try:
            data = sock.recv(1)
            print("RAW BYTE:", data)
            while len(data) < 1:
                more = sock.recv(1)
                if not more:
                    return
                data += more

            packet_type = struct.unpack("!B", data)[0]
            # =========================
            # LOBBY UPDATE
            # =========================
            if packet_type == 1:
                player_count, host_id = struct.unpack("!BB", sock.recv(2))
                player_names.clear()

                for _ in range(player_count):
                    p_id = struct.unpack("!B", sock.recv(1))[0]
                    name_length = struct.unpack("!B", sock.recv(1))[0]
                    pname = sock.recv(name_length).decode()
                    player_names[p_id] = pname

            # =========================
            # POSITION UPDATE
            # =========================
            elif packet_type == 2:
                data = b""

                while len(data) < 9:
                    packet = sock.recv(9 - len(data))

                    if not packet:
                        return

                    data += packet

                p_id, x, y = struct.unpack("!Bii", data)

                if x == -1000 and y == -1000:
                    if p_id in other_players:
                        del other_players[p_id]
                else:
                    other_players[p_id] = [x, y]

            # =========================
            # SPIEL STARTET
            # =========================
            elif packet_type == 3:
                print(">>> GAME START PACKET RECEIVED")
                game_started = True

            # =========================
            # Disconnect
            # =========================
            elif packet_type == 4:
                p_id, x, y = struct.unpack("!Bii", sock.recv(10))
                if p_id in other_players:
                    del other_players[p_id]
        except:
            print("RECEIVE THREAD ERROR:", e)
            break

# Verbindung zum zentralen Server herstellen
ip = input("Server IP eingeben: ")
name = input("Dein Name: ")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((ip, PORT))
setup_socket(sock)

# Namen senden
name_data = name.encode()
sock.sendall(struct.pack("!B", len(name_data)))
sock.sendall(name_data)

# Eigene ID empfangen
my_id = struct.unpack('!B', sock.recv(1))[0]

print(f"Erfolgreich verbunden! Deine Spieler-ID ist: {my_id}")

# Eigenen Spieler erstellen (Farbe basiert auf der ID)
my_player = Player(100 + (my_id * 30), 100, player_images[my_id % len(player_images)])

# Thread starten
threading.Thread(target = receive_data, args=(sock,), daemon = True).start()

# Startposition sofort senden
sock.sendall(struct.pack('!Bii', 2, int(my_player.x), int(my_player.y)))

# ===================
# TASK SYSTEM
# ===================
task_manager = tasks.TaskManager()

# Font für die Interaktionsanzeige in der Nähe von Buttons initialisieren
proximity_font = pygame.font.SysFont("arial", 20, bold=True)

# 1. Alle Tasks ganz normal instanziieren
tasks_instances = [
    tasks.BookSortTask(screen),       # 0
    tasks.ChairStackTask(screen),     # 1
    tasks.WindowTask(screen),         # 2
    tasks.DownloadDataTask(screen),   # 3
    tasks.CleanBoardTask(screen),     # 4
    tasks.ProjectorWiresTask(screen), # 5
    tasks.VirusScanTask(screen),      # 6
    tasks.PrinterPaperTask(screen),   # 7
    tasks.BunsenBurnerTask(screen),   # 8
    tasks.ChemicalMixTask(screen),    # 9
    tasks.PencilCaseTask(screen),     # 10
    tasks.KeyboardCleanTask(screen),  # 11
    tasks.MicroscopeFocusTask(screen),# 12
    tasks.RepairCurcuit(screen),      # 13
    tasks.BallCollectTask(screen),    # 14
    tasks.MatStackTask(screen),       # 15
    tasks.TraySortingTask(screen),    # 16
    tasks.MilkFillTask(screen),       # 17
    tasks.PizzaCutTask(screen),       # 18
    tasks.VendingMachineTask(screen), # 19
    tasks.BarcodeScanTask(screen),    # 20
    tasks.LockerCleanTask(screen),    # 21
    tasks.TrashDisposalTask(screen),  # 22
    tasks.PipeLeakTask(screen)        # 23
]

# 2. Dem Task-Manager die erstellten Tasks übergeben
for t in tasks_instances:
    task_manager.add_task(t)

# 3. Die Buttonliste, verknüpft mit dem Index aus dem TaskManager und Grafik-Typen
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

start_button = Button(WIDTH // 2 - 150, HEIGHT - 150, 300, 80, "SPIEL STARTEN", font)

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

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:

                # Wenn Task offen -> nur Task schließen
                if task_manager.active_task:
                    task_manager.active_task = None

                # Sonst Spiel schließen
                else:
                    running = False
                    pygame.quit()
                    exit()

            if event.key == pygame.K_e:

                for btn in task_buttons:
                    # Hier greifen wir korrekt auf das .rect des Spielers und des Buttons zu:
                    player_center = my_player.rect.center
                    button_center = btn["rect"].center
                    
                    # Abstand berechnen
                    distance = math.hypot(player_center[0] - button_center[0], player_center[1] - button_center[1])
                    
                    # Wenn nahe genug dran (z.B. weniger als 85 Pixel), starte den Task
                    if distance < 85:
                        task_manager.start_task(btn["task_index"])
                        break

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            if not game_started:
                if my_id == host_id and start_button.clicked(mouse_pos):
                    print("SENDING START PACKET")
                    sock.sendall(struct.pack("!B", 99))
                    print("CLICK:", my_id, host_id, start_button.clicked(mouse_pos))
                continue

            for btn in task_buttons:
                # Hier greifen wir korrekt auf das .rect des Spielers und des Buttons zu:
                player_center = my_player.rect.center
                button_center = btn["rect"].center
                
                # Abstand berechnen
                distance = math.hypot(player_center[0] - button_center[0], player_center[1] - button_center[1])
                
                # Wenn nahe genug dran (z.B. weniger als 85 Pixel), starte den Task
                if distance < 85:
                    task_manager.start_task(btn["task_index"])
                    break

        # =========================
        # TASK EVENTS
        # =========================
        task_manager.handle_event(event)

    keys = pygame.key.get_pressed()

    # Bewegung
    has_moved = False

    if task_manager.active_task is None and game_started:

        has_moved = my_player.move(
            keys,   
            dt,
            walls
        )

    # Netzwerk senden
    if has_moved:
        try:
            data = struct.pack('!Bii', 2, int(my_player.x), int(my_player.y))
            sock.sendall(data)
        except Exception as e:
            print(f"Verbindung verloren: {e}")
            running = False

    # =========================
    # Zeichnen
    # =========================
    screen.fill((30, 30, 30))

    if not game_started:
        title = font.render("LOBBY", True, (255,255,255))
        screen.blit(title, (WIDTH//2 - 80, 40))
        info = font.render(f"Spieler: {player_count}", True, (255,255,255))
        screen.blit(info, (50,120))
        y = 220

        for pid, pname in player_names.items():
            text = font.render(pname, True, (255,255,255))
            screen.blit(text, (100, y))
            y += 60

        # Host Anzeige
        host_text = font.render(f"Host: {player_names.get(host_id, '')}", True, (255,255,0))
        screen.blit(host_text, (50,170))

        # Nur Host sieht Button
        if my_id == host_id:
            start_button.draw(screen)

        pygame.display.update()
        continue

    # Wände
    for wall in walls:
        pygame.draw.rect(
            screen,
            (100, 100, 100),
            wall
        )

    # ALLE ANDEREN GEGNER ZEICHNEN
    for p_id, pos in other_players.items():
        # Wähle die Textur basierend auf der ID des Gegners
        enemy_img = player_images.get(p_id % len(player_images))
        screen.blit(enemy_img, (pos[0], pos[1]))

    # Eigener Spieler
    my_player.draw(screen)

    # Buttons 
    if task_manager.active_task is None and game_started:
        draw_task_buttons(screen, task_buttons, my_player)

    # draw & update task
    task_manager.draw(screen)
    task_manager.update()

    pygame.display.update()

# =========================
# Beenden
# =========================
try:
    sock.close()
except:
    pass

pygame.quit()