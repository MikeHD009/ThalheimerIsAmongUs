import pygame
import sys

# Pygame initialisieren
pygame.init()

# Bildschirm-Einstellungen
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Among Us - Schul-Map")
clock = pygame.time.Clock()

# Farbdefinitionen (Among Us Palette & Raumfarben)
COLOR_BG = (15, 15, 20)          # Weltraum/Hintergrund
COLOR_WALL = (60, 65, 75)        # Dunkle, dicke Wände
COLOR_HALLWAY = (130, 140, 150)  # Breite Gänge (Beton/Boden)

# Raumfarben zur besseren Unterscheidung
ROOM_COLORS = {
    "Klassenzimmer": (100, 150, 100),   # Grün (Tafel-Stil)
    "Sporthalle": (210, 140, 80),       # Hallenboden-Orange
    "Cafeteria": (180, 80, 80),         # Rotbraun
    "Computerraum": (70, 100, 140),     # Bläulich
    "Serverraum": (50, 50, 70),         # Dunkel/Technisch
    "Schließfächer": (160, 160, 110),   # Gelblich
    "Gartenbereich": (50, 130, 70),     # Grasgrün
    "Chemielabor": (120, 80, 150),      # Lila/Chemie
    "Yogaraum": (200, 120, 160),        # Rosa/Entspannend
    "Lehrerzimmer": (140, 110, 90),     # Holzfarben
    "Bibliothek": (100, 80, 60)         # Dunkelholz/Bücher
}

# Raster-Einstellungen (Tile-basiert für einfaches Design)
TILE_SIZE = 40
# Die Map ist 60x45 Tiles groß (2400 x 1800 Pixel)
MAP_TILES_X = 60
MAP_TILES_Y = 45
MAP_WIDTH = MAP_TILES_X * TILE_SIZE
MAP_HEIGHT = MAP_TILES_Y * TILE_SIZE

# --- RAUM-LAYOUT DEFINIEREN ---
# Format: [X-Tile, Y-Tile, Breite-Tiles, Höhe-Tiles, Name]
# Die Räume sind kompakt beieinander, getrennt durch breite Gänge.
ROOMS_DATA = [
    # Reihe oben
    [4, 4, 10, 8, "Sporthalle"],
    [16, 4, 12, 10, "Cafeteria"],
    [30, 4, 8, 7, "Klassenzimmer 1"],
    [40, 4, 8, 7, "Klassenzimmer 2"],
    [50, 4, 6, 8, "Chemielabor"],
    
    # Reihe Mitte
    [4, 16, 7, 7, "Computerraum 1"],
    [13, 16, 7, 7, "Computerraum 2"],
    [22, 18, 5, 5, "Serverraum"],
    [29, 15, 12, 8, "Gartenbereich"], # offener Innenhof
    [43, 15, 6, 7, "Schließfächer"],
    [51, 16, 5, 6, "Yogaraum"],

    # Reihe unten
    [4, 27, 8, 7, "Lehrerzimmer"],
    [14, 27, 12, 9, "Bibliothek"],
    [28, 27, 8, 7, "Klassenzimmer 3"]
]

# Map-Matrix erstellen: 0 = Wand/Vakuum, 1 = Gang/Boden
# Startet komplett als Wand, wir "graben" die Gänge und Räume frei
map_grid = [[0 for _ in range(MAP_TILES_Y)] for _ in range(MAP_TILES_X)]

# 1. Hauptgänge "graben" (Verbindungswege, immer 4 Tiles = 160px breit für viel Platz)
# Horizontaler Hauptgang Mitte
for x in range(2, MAP_TILES_X - 2):
    for y in range(12, 15): map_grid[x][y] = 1
    for y in range(24, 27): map_grid[x][y] = 1

# Vertikale Hauptgänge
for y in range(2, MAP_TILES_Y - 2):
    for x in range(2, 4): map_grid[x][y] = 1        # Ganz links
    for x in range(27, 29): map_grid[x][y] = 1      # Mitte-Links
    for x in range(41, 43): map_grid[x][y] = 1      # Mitte-Rechts
    for x in range(57, 59): map_grid[x][y] = 1      # Ganz rechts

# 2. Räume in die Map stanzen und Türen einbauen
rooms = []
walls = []

class Room:
    def __init__(self, tx, ty, tw, th, name):
        self.rect = pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, tw * TILE_SIZE, th * TILE_SIZE)
        self.name = name
        # Typ für Farbauswahl bestimmen
        self.type = "Klassenzimmer" if "Klassenzimmer" in name else name
        self.color = ROOM_COLORS.get(self.type, (100, 100, 100))
        
        # Boden im Grid freischalten
        for x in range(tx, tx + tw):
            for y in range(ty, ty + th):
                if 0 <= x < MAP_TILES_X and 0 <= y < MAP_TILES_Y:
                    map_grid[x][y] = 2 # 2 steht für Raumboden

for r in ROOMS_DATA:
    rooms.append(Room(r[0], r[1], r[2], r[3], r[4]))

# 3. Wände generieren (Überall wo eine 0 an eine 1 oder 2 grenzt)
for x in range(MAP_TILES_X):
    for y in range(MAP_TILES_Y):
        if map_grid[x][y] == 0:
            # Prüfen ob ein Nachbartile Boden ist
            is_wall = False
            for nx, ny in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
                if 0 <= nx < MAP_TILES_X and 0 <= ny < MAP_TILES_Y:
                    if map_grid[nx][ny] in [1, 2]:
                        is_wall = True
            if is_wall:
                walls.append(pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))


# --- SPIELER KLASSE ---
class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 32, 32) # Typische Among Us Breite
        self.color = (255, 0, 0) # Roter Astronaut
        self.speed = 5

    def move(self, dx, dy, obstacles):
        # Horizontale Bewegung & Kollision
        if dx != 0:
            self.rect.x += dx * self.speed
            for wall in obstacles:
                if self.rect.colliderect(wall):
                    if dx > 0: self.rect.right = wall.left
                    if dx < 0: self.rect.left = wall.right

        # Vertikale Bewegung & Kollision
        if dy != 0:
            self.rect.y += dy * self.speed
            for wall in obstacles:
                if self.rect.colliderect(wall):
                    if dy > 0: self.rect.bottom = wall.top
                    if dy < 0: self.rect.top = wall.bottom


# --- KAMERA KLASSE ---
class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height

    def apply(self, entity):
        # Verschiebt ein Objekt (Rect) relativ zur Kameraposition
        if isinstance(entity, pygame.Rect):
            return entity.move(self.camera.topleft)
        return entity.rect.move(self.camera.topleft)

    def update(self, target):
        # Folgt dem Spieler und zentriert ihn
        x = -target.rect.centerx + int(SCREEN_WIDTH / 2)
        y = -target.rect.centery + int(SCREEN_HEIGHT / 2)

        # Kamera stoppen, wenn wir am Rand der riesigen Map sind
        x = min(0, x) # Links
        y = min(0, y) # Oben
        x = max(-(self.width - SCREEN_WIDTH), x) # Rechts
        y = max(-(self.height - SCREEN_HEIGHT), y) # Unten
        self.camera.topleft = (x, y)


# Instanzen erstellen (Spieler startet in der Cafeteria)
player = Player(800, 300)
camera = Camera(MAP_WIDTH, MAP_HEIGHT)
font = pygame.font.SysFont("Arial", 16, bold=True)

# Game Loop
running = True
while running:
    clock.tick(60) # 60 FPS
    
    # Event-Handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Steuerung abfragen
    keys = pygame.key.get_pressed()
    dx, dy = 0, 0
    if keys[pygame.K_LEFT] or keys[pygame.K_a]:  dx = -1
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx = 1
    if keys[pygame.K_UP] or keys[pygame.K_w]:    dy = -1
    if keys[pygame.K_DOWN] or keys[pygame.K_s]:  dy = 1

    # Diagonale Bewegung normalisieren (optional, hier einfach direkt angewendet)
    player.move(dx, dy, walls)
    camera.update(player)

    # --- ZEICHNEN ---
    screen.fill(COLOR_BG)

    # 1. Gänge/Hintergrundboden zeichnen (Alles was im Grid 1 ist)
    # Performanz-Tipp: In einem echten Spiel würde man nur zeichnen, was im Kamerasichtfeld ist.
    for x in range(MAP_TILES_X):
        for y in range(MAP_TILES_Y):
            if map_grid[x][y] == 1:
                tile_rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                screen.blit(font.render("", True, (0,0,0)), camera.apply(tile_rect).topleft) # Nur Platzhalter für Verschiebung
                pygame.draw.rect(screen, COLOR_HALLWAY, camera.apply(tile_rect))

    # 2. Räume zeichnen
    for room in rooms:
        pygame.draw.rect(screen, room.color, camera.apply(room.rect))
        # Raumname in die Mitte des Raumes schreiben
        text_surf = font.render(room.name, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=room.rect.center)
        screen.blit(text_surf, camera.apply(text_rect))

    # 3. Wände zeichnen
    for wall in walls:
        pygame.draw.rect(screen, COLOR_WALL, camera.apply(wall))

    # 4. Spieler zeichnen
    pygame.draw.rect(screen, player.color, camera.apply(player))
    # Visier des Among Us Astronauten zeichnen
    visor_rect = pygame.Rect(player.rect.x + 12, player.rect.y + 6, 16, 10)
    pygame.draw.rect(screen, (150, 220, 255), camera.apply(visor_rect))

    # Minimap oben rechts anzeigen (Zusatz-Feature!)
    minimap_scale = 0.08
    minimap_surf = pygame.Surface((MAP_WIDTH * minimap_scale, MAP_HEIGHT * minimap_scale))
    minimap_surf.fill((30, 30, 30))
    for room in rooms:
        m_rect = pygame.Rect(room.rect.x * minimap_scale, room.rect.y * minimap_scale, room.rect.width * minimap_scale, room.rect.height * minimap_scale)
        pygame.draw.rect(minimap_surf, room.color, m_rect)
    # Spieler auf Minimap
    pygame.draw.circle(minimap_surf, (255, 0, 0), (int(player.rect.centerx * minimap_scale), int(player.rect.centery * minimap_scale)), 3)
    screen.blit(minimap_surf, (SCREEN_WIDTH - minimap_surf.get_width() - 10, 10))

    pygame.display.flip()

pygame.quit()
sys.exit()