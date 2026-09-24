# NEU: Drei Betriebsarten
#   * lokal:        python main.py                 (Vollbild, Eingabe der Server-IP - wie bisher)
#   * Browser:      laeuft als WebAssembly (pygbag) auf dem Geraet des Spielers  -> BROWSER
#   * Server-Modus: python main.py --web-session   (Server rechnet + streamt das Bild) -> WEB_MODE
# Der Web-Session-Modus muss VOR pygame.init() aktiviert werden.
import sys
import asyncio
BROWSER = sys.platform == "emscripten"
if BROWSER:
    import browser_bridge as web_bridge   # gleiche Schnittstelle wie web_bridge
    WEB_MODE = False
else:
    import web_bridge
    WEB_MODE = web_bridge.init_from_argv()

import pygame
import socket
import threading
import struct
import math
import json
import sys
import os
import time
import random
from collections import deque

import tasks
import roles
import sound
import fx
import hud
import fonts
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

# =========================
# ROLLEN-SYSTEM: KONSTANTEN
# =========================
KILL_RANGE_DEFAULT = 60
KILL_COOLDOWN_DEFAULT = 20.0
KILL_RANGE_MARTIN = 90
KILL_COOLDOWN_MARTIN = 35.0
MONIKA_TELEPORT_COOLDOWN = 15.0  # Monika: erst danach ist die Reise zur Flagge wieder moeglich
MONIKA_FLAG_COOLDOWN = 20.0      # Monika: erst danach kann die Flagge neu gesetzt werden
STROBLPETER_MARK_DELAY = 10.0
STROBLPETER_MARK_RANGE = 250
EVELYN_COOLDOWN = 30.0
EVELYN_HAZARD_DURATION = 20.0
EVELYN_LINGER_LIMIT = 5.0
NOAH_TRAP_RANGE = 60
NOAH_TRAP_LIMIT = 3       # laut Dokument: maximal 3 Fallen, die aelteste wird ersetzt
NOAH_TRAP_COOLDOWN = 15.0 # laut Dokument: 15s Ablinkzeit
YOSHI_FIND_LIMIT = 3      # laut Dokument: bis zu 3 Standards, pro Fund eine Aufdeckung
EVELYN_FOG_COLOR = (200, 225, 255, 90)  # weissblaeulicher Nebel in den geoeffneten Raeumen
VOGELSCHEICHER_RANGE = 60
VOGELSCHEICHER_INVISIBLE_DURATION = 8.0
IMMORTALITY_DURATION_CLIENT = 10.0
PLESCHBERGSTEIGER_RANGE = 60
YOSHI_FIND_RANGE = 40
TAPPEIHNACHTSMANN_FIND_RANGE = 40
RAPHI_COLLECT_RANGE = 40
RAMONA_FORGE_RANGE = 80
RAMONA_FORGE_COOLDOWN_CLIENT = 10.0
RAMONA_WIN_STAND_TIME = 10.0
DAVID_MARK_RANGE = 250
VLADIMIR_INTRO_DURATION = 5.0        # Notfall-Wartezeit, falls das Video nicht abspielbar ist
VLADIMIR_VIDEO_PATH = "Assets/OshiNoKoIntro.m4v"
VLADIMIR_VIDEO_MAX_DURATION = 60.0   # Sicherheitsnetz, falls das Video nie ein EOF meldet
LAURIN_SABOTAGE_RANGE = 60           # Reichweite, in der Laurin eine Aufgabe zurücksetzen kann
MEETING_DISCUSSION_TIME = 45.0       # muss zu server.py passen
MEETING_VOTE_TIME = 30.0             # muss zu server.py passen
MEETING_PHASE_NONE = 0
MEETING_PHASE_DISCUSSION = 1
MEETING_PHASE_VOTE = 2
MEETING_REASON_KALIYOGA = 2          # Kaliyoga ruft von ueberall aus
# NEU: Todesursachen-Bits in Paket 31 (muss zu server.py passen)
DEATH_FLAG_VLADIMIR = 1
DEATH_FLAG_EJECTED = 2
DEATH_FLAG_TRAP = 4
DEATH_FLAG_WINDOW = 8
DEATH_FLAG_EXPLOSION = 16
NO_PLAYER = 255
# NEU: Ergebnis-Codes in Paket 43 (muss zu server.py passen)
MEETING_RESULT_EJECTED = 0
MEETING_RESULT_SKIPPED = 1
MEETING_RESULT_TIE = 2
MEETING_RESULT_IMMORTAL = 3
RAMONA_MIN_PLAYERS_CLIENT = roles.RAMONA_MIN_PLAYERS   # gemeinsame Regel in roles.py
MAX_IMPOSTERS = roles.MAX_IMPOSTERS
# NEU: Vom Host einstellbar (Paket 16/17) - Standardwerte wie in server.py
SETTING_LIMITS = {"cooldown": (0, 120), "discussion": (0, 180), "vote": (10, 180)}
SETTING_STEP = 5

# Lauf-Animation: das Spielerbild wippt beim Gehen leicht nach oben
WALK_BOB_PIXELS = 3      # maximale Auslenkung nach oben in Pixeln
WALK_BOB_SPEED = 14.0    # Schwingungen pro Sekunde (Radiant/s)
WALK_IDLE_TIMEOUT = 0.15 # so lange gilt ein anderer Spieler nach der letzten Positionsmeldung als "laufend"

# Einsammelbare Rollen-Items (Raphi/Tappeihnachtsmann/Yoshi)
ITEM_SIZE = int(TILE_SIZE * 0.8)
ITEM_MIN_SPACING = 110   # Mindestabstand zwischen zwei Items, damit sie sich verteilen

pygame.init()
# NEU: ohne Arial (Linux-Server, Browser) die mitgelieferte, gleich breite Liberation Sans verwenden
fonts.install(pygame, force=BROWSER)

# Hauptfenster auf VOLLBILD setzen und Auflösung automatisch ermitteln.
# NEU: Im Web-Modus gibt es kein echtes Fenster - es wird in fester Aufloesung in den Speicher
# gezeichnet und der Browser skaliert das Bild auf seine Vollbildgroesse.
if WEB_MODE:
    screen = pygame.display.set_mode((web_bridge.WIDTH, web_bridge.HEIGHT))
elif BROWSER:
    # Die Webseite skaliert das Bild auf Fenster-/Vollbildgroesse
    screen = pygame.display.set_mode((1440, 810))
else:
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

# NEU: Rollenbilder für den Reveal-Screen, analog zu player_images geladen (Cache, einmalig)
ROLE_IMAGES = {}
ROLE_THUMB_SIZE = int(TILE_SIZE * 1.4)
ROLE_REVEAL_SIZE = int(TILE_SIZE * 4)

def get_role_image(role_key, size):
    if role_key is None:
        return None
    cache_key = (role_key, size)
    if cache_key in ROLE_IMAGES:
        return ROLE_IMAGES[cache_key]
    try:
        filename = roles.ROLES[role_key]["image"]
        img = pygame.image.load(f"Assets/Character/Roles/{filename}").convert_alpha()
        img = pygame.transform.scale(img, (size, size))
    except Exception as e:
        print("ROLE IMAGE LOAD ERROR:", e)
        img = None
    ROLE_IMAGES[cache_key] = img
    return img

# NEU: Texturen fuer die einsammelbaren Rollen-Items und die platzierbaren Objekte.
# Es sind bewusst schlichte Platzhalter - einfach die PNGs in Assets/Items durch echte
# Grafiken mit denselben Dateinamen ersetzen (siehe tools_generate_item_placeholders.py).
ITEM_FILES = {
    "pfandflasche": "pfandflasche.png",   # Raphi
    "geschenk": "geschenk.png",           # Tappeihnachtsmann
    "standard": "standard.png",           # Yoshi
    "flagge": "flagge.png",               # Monika
    "falle": "falle.png",                 # Noah
    "schere": "schere.png",               # Martin (steckt in der Leiche)
}
item_images = {}
for _item_key, _item_file in ITEM_FILES.items():
    try:
        _item_img = pygame.image.load(f"Assets/Items/{_item_file}").convert_alpha()
        item_images[_item_key] = pygame.transform.scale(_item_img, (ITEM_SIZE, ITEM_SIZE))
    except Exception as _e:
        print("ITEM IMAGE LOAD ERROR:", _item_file, _e)
        _fallback = pygame.Surface((ITEM_SIZE, ITEM_SIZE), pygame.SRCALPHA)
        pygame.draw.circle(_fallback, (80, 180, 255), (ITEM_SIZE // 2, ITEM_SIZE // 2), ITEM_SIZE // 2)
        item_images[_item_key] = _fallback

# =========================
# VIDEO-WIEDERGABE (Vladimirs Anime-Intro)
# =========================
try:
    from ffpyplayer.player import MediaPlayer
    VIDEO_SUPPORTED = True
except Exception as _video_err:
    MediaPlayer = None
    VIDEO_SUPPORTED = False
    print("VIDEO: ffpyplayer nicht verfuegbar -", _video_err)


class VideoPlayer:
    """Spielt ein Video samt Ton bildschirmfuellend ab (fuer Vladimirs Opfer).
    Ist ffpyplayer nicht installiert oder die Datei nicht vorhanden, meldet sich der Player
    sofort als 'fertig' und der Aufrufer zeigt stattdessen einen einfachen Warte-Bildschirm."""

    def __init__(self, path):
        self.player = None
        self.surface = None
        self.finished = False
        self.started_at = time.time()
        if not VIDEO_SUPPORTED or not os.path.exists(path):
            if not os.path.exists(path):
                print("VIDEO: Datei nicht gefunden:", path)
            self.finished = True
            return
        try:
            self.player = MediaPlayer(path)
        except Exception as e:
            print("VIDEO OPEN ERROR:", e)
            self.finished = True

    @property
    def active(self):
        return not self.finished

    def update(self):
        if self.player is None or self.finished:
            return
        # Sicherheitsnetz gegen ein Video, das nie ein EOF meldet
        if time.time() - self.started_at > VLADIMIR_VIDEO_MAX_DURATION:
            self.close()
            return
        try:
            frame, val = self.player.get_frame()
        except Exception as e:
            print("VIDEO ERROR:", e)
            self.close()
            return
        if val == "eof":
            self.close()
            return
        if frame is None:
            return
        img, _pts = frame
        try:
            if img.get_pixel_format() != "rgb24":
                from ffpyplayer.pic import SWScale
                w0, h0 = img.get_size()
                img = SWScale(w0, h0, img.get_pixel_format(), ofmt="rgb24").scale(img)
            w, h = img.get_size()
            self.surface = pygame.image.frombuffer(bytes(img.to_bytearray()[0]), (w, h), "RGB")
        except Exception as e:
            print("VIDEO FRAME ERROR:", e)
            self.close()

    def draw(self, target):
        target.fill((0, 0, 0))
        if self.surface is None:
            return
        tw, th = target.get_size()
        sw, sh = self.surface.get_size()
        scale = min(tw / sw, th / sh)
        dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))
        target.blit(pygame.transform.smoothscale(self.surface, (dw, dh)),
                    ((tw - dw) // 2, (th - dh) // 2))

    def close(self):
        self.finished = True
        self.surface = None
        if self.player is not None:
            try:
                self.player.close_player()
            except Exception:
                pass
            self.player = None


def make_ghost_video():
    """NEU: Im Web-Modus spielt der Browser des Opfers das Video ab (mit Ton), lokal wie bisher
    ffpyplayer."""
    if BROWSER:
        return web_bridge.JSVideoPlayer("/media/" + os.path.basename(VLADIMIR_VIDEO_PATH),
                                        VLADIMIR_VIDEO_MAX_DURATION)
    if WEB_MODE:
        return web_bridge.RemoteVideoPlayer("/media/" + os.path.basename(VLADIMIR_VIDEO_PATH),
                                            VLADIMIR_VIDEO_MAX_DURATION)
    return VideoPlayer(VLADIMIR_VIDEO_PATH)


# =========================
# SOUND (NEU)
# =========================
sfx = sound.SoundManager(web_bridge if (WEB_MODE or BROWSER) else None, assume_available=BROWSER)
walking_sound_until = 0.0   # kleine Nachlaufzeit, damit der Schritt-Loop an Waenden nicht flackert

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
        self.role_key = None                    # NEU: z.B. "steinermike", None = generische Rolle
        self.role_display_name = "Crewmate"      # NEU: Anzeigename für den Reveal-Screen
        self.role_image = None                   # NEU: geladenes Rollenbild (pygame.Surface)
        self.my_assigned_tasks = []
        self.my_completed_tasks = []
        self.is_dead = False 
        self.is_venting = False       # NEU: Ob der Imposter gerade im Vent ist
        self.current_vent_idx = -1    # NEU: Index des aktuellen Vents
        self.facing_left = False      # NEU: Blickrichtung fürs Spiegeln (Bild schaut standardmäßig nach rechts)
        self.is_moving = False        # NEU: Laufanimation - bewegt sich der Spieler gerade?
        self.walk_phase = 0.0         # NEU: Laufanimation - Phase der Auf-/Ab-Schwingung

    def move(self, keys, hitboxes, speed_factor=1.0):
        """speed_factor = Frame-Dauer relativ zu 60 FPS. Bei 60 FPS (=1.0) exakt wie bisher;
        NEU: im Browser mit 50 oder 144 Hz laeuft die Figur dadurch trotzdem gleich schnell."""
        old_x = self.rect.x
        old_y = self.rect.y
        dx, dy = 0, 0

        # Geister sind langsamer (0.8x)
        current_speed = (PLAYER_SPEED * 0.8 if self.is_dead else PLAYER_SPEED) * speed_factor

        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= current_speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += current_speed
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= current_speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += current_speed

        # NEU: Blickrichtung nur anhand der horizontalen Eingabe setzen (kein Sprung/Hüpfen,
        # nur ein reiner Links/Rechts-Flip des Bildes)
        if dx < 0:
            self.facing_left = True
        elif dx > 0:
            self.facing_left = False

        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071

        # Nachkommastellen aufheben, damit auch kleine Schritte (hohe Bildrate) nicht verloren gehen
        self.move_rest_x = getattr(self, "move_rest_x", 0.0) + dx
        self.move_rest_y = getattr(self, "move_rest_y", 0.0) + dy
        dx, dy = int(self.move_rest_x), int(self.move_rest_y)
        self.move_rest_x -= dx
        self.move_rest_y -= dy

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

        moved = self.rect.x != old_x or self.rect.y != old_y
        self.is_moving = moved
        return moved

    def update_walk_anim(self, dt, moving=None):
        """NEU: Laufanimation. Solange sich der Spieler bewegt, laeuft eine Sinus-Phase
        weiter, aus der walk_offset() einen leichten Versatz nach oben berechnet. Im Stand wird
        die Phase zurueckgesetzt, damit der Spieler sauber auf dem Boden steht."""
        if moving is not None:
            self.is_moving = moving
        if self.is_moving:
            self.walk_phase += WALK_BOB_SPEED * dt
        else:
            self.walk_phase = 0.0

    def walk_offset(self):
        if not self.is_moving:
            return 0
        return -int(round(abs(math.sin(self.walk_phase)) * WALK_BOB_PIXELS))

    def draw(self, surface, camera_x, camera_y):
        draw_rect = self.rect.copy()
        draw_rect.x -= camera_x
        draw_rect.y -= camera_y
        
        img_to_draw = self.image.copy()
        if self.facing_left:
            img_to_draw = pygame.transform.flip(img_to_draw, True, False)
        if self.is_dead:
            img_to_draw.set_alpha(128) # Eigener Geist ist leicht transparent
        elif self.is_venting:
            img_to_draw.set_alpha(100) # NEU: Eigener Imposter wird im Vent halbtransparent angezeigt

        surface.blit(img_to_draw, (draw_rect.x, draw_rect.y + self.walk_offset()))

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
    hitboxes, vents, plants, tasks_hitboxes, mapwalls, spawnpoints, emergency_hitboxes, window_zones = [], [], [], [], [], [], [], []
    # NEU: room_rects sind die Innenflaechen der echten Raeume (Tiled-Layer "Sabotage" und
    # "WindowSabotage"). Nur dort duerfen Rollen-Items liegen - ausserhalb waere es "neben der Map".
    room_rects = []
    if not os.path.exists(filepath):
        return hitboxes, vents, plants, tasks_hitboxes, mapwalls, spawnpoints, emergency_hitboxes, window_zones, room_rects
    
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
        # NEU: Fensterräume für Evelyns Fähigkeit (bisher ungenutzter Tiled-Layer)
        elif name == "WindowSabotage":
            if "objects" in layer:
                for obj in layer["objects"]:
                    r = pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"])
                    window_zones.append(r)
                    room_rects.append(r)
            elif "data" in layer:
                for i, t_id in enumerate(layer["data"]):
                    if t_id != 0: window_zones.append(pygame.Rect((i % map_width) * TILE_SIZE, (i // map_width) * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        # NEU: "Sabotage" markiert ebenfalls komplette Raeume - zusammen mit WindowSabotage
        # ergibt das die Liste aller Innenraeume, in denen Items liegen duerfen.
        elif name == "Sabotage":
            if "objects" in layer:
                for obj in layer["objects"]: room_rects.append(pygame.Rect(obj["x"], obj["y"], obj["width"], obj["height"]))

    return hitboxes, vents, plants, tasks_hitboxes, mapwalls, spawnpoints, emergency_hitboxes, window_zones, room_rects

def get_current_vent(player, vents):
    for vent in vents:
        if player.rect.colliderect(vent): return vent
    return None

def get_current_plant(player, plants):
    for plant in plants:
        if player.rect.colliderect(plant): return plant
    return None

def pick_item_spots(count):
    """NEU: Sucht Positionen fuer einsammelbare Rollen-Items (Pfandflaschen, Geschenke,
    Standards). Es werden ausschliesslich Punkte INNERHALB der Raeume verwendet (room_rects aus
    den Tiled-Layern 'Sabotage'/'WindowSabotage'), die auf keiner Wand- oder Objekt-Hitbox liegen.
    Damit kann nie ein Item ausserhalb der Map oder in einer Wand landen.
    Rueckgabe: Liste von pygame.Rect in Item-Groesse."""
    spots = []
    if count <= 0:
        return spots

    attempts = 0
    while room_rects and len(spots) < count and attempts < count * 400:
        attempts += 1
        room = random.choice(room_rects)
        if room.width < ITEM_SIZE * 3 or room.height < ITEM_SIZE * 3:
            continue
        x = random.randint(room.left + ITEM_SIZE, room.right - 2 * ITEM_SIZE)
        y = random.randint(room.top + ITEM_SIZE, room.bottom - 2 * ITEM_SIZE)
        cand = pygame.Rect(x, y, ITEM_SIZE, ITEM_SIZE)
        if any(cand.colliderect(box) for box in hitboxes):
            continue
        if any(math.hypot(cand.centerx - s.centerx, cand.centery - s.centery) < ITEM_MIN_SPACING for s in spots):
            continue
        spots.append(cand)

    # Notfall-Auffuellung: Task-Positionen liegen garantiert in Raeumen
    if len(spots) < count and tasks_hitboxes:
        for t in random.sample(tasks_hitboxes, len(tasks_hitboxes)):
            if len(spots) >= count:
                break
            cand = pygame.Rect(0, 0, ITEM_SIZE, ITEM_SIZE)
            cand.center = t.center
            if not any(cand.colliderect(s) for s in spots):
                spots.append(cand)
    return spots

def draw_world_items(surface, spots, image_key, my_center, camera_x, camera_y):
    """NEU: Zeichnet die noch nicht eingesammelten Rollen-Items auf der Map - nur im
    Sichtradius und mit freier Sichtlinie, genau wie Spieler und Leichen."""
    img = item_images.get(image_key)
    if img is None:
        return
    for spot in spots:
        if math.hypot(my_center[0] - spot.centerx, my_center[1] - spot.centery) > VISION_RADIUS:
            continue
        if not has_line_of_sight(my_center, spot.center, mapwalls):
            continue
        surface.blit(img, (spot.x - camera_x, spot.y - camera_y))

def update_other_walk_anims(dt):
    """NEU: Laufanimation der anderen Spieler. Wer kuerzlich eine neue Position gemeldet
    hat, gilt als laufend und bekommt eine weiterlaufende Sinus-Phase."""
    now = time.time()
    for p_id in list(other_players.keys()):
        if now - player_last_move_time.get(p_id, 0.0) < WALK_IDLE_TIMEOUT:
            player_walk_phase[p_id] = player_walk_phase.get(p_id, 0.0) + WALK_BOB_SPEED * dt
        else:
            player_walk_phase[p_id] = 0.0

def get_walk_offset(p_id):
    """NEU: Aktueller vertikaler Versatz der Laufanimation eines anderen Spielers."""
    phase = player_walk_phase.get(p_id, 0.0)
    if phase <= 0.0:
        return 0
    return -int(round(abs(math.sin(phase)) * WALK_BOB_PIXELS))

def find_nearest_player(my_center, other_players_dict, range_limit, dead_players_set, want_dead=False, exclude_ids=()):
    """Sucht den naechsten Spieler aus other_players in Reichweite. want_dead=True sucht
    ausschliesslich unter Geistern (fuer Pleschbergsteigers Wiederbelebung), sonst nur Lebende.
    exclude_ids blendet Spieler komplett aus (z.B. die eigenen Imposter-Mitspieler beim Kill)."""
    closest_id, closest_dist = None, range_limit
    for p_id, pos in other_players_dict.items():
        if p_id in exclude_ids:
            continue
        is_dead = p_id in dead_players_set
        if is_dead != want_dead:
            continue
        p_center = (pos[0] + PLAYER_SIZE // 2, pos[1] + PLAYER_SIZE // 2)
        dist = math.hypot(my_center[0] - p_center[0], my_center[1] - p_center[1])
        if dist < closest_dist:
            closest_dist = dist
            closest_id = p_id
    return closest_id

# =========================
# NETZWERK LOGIK
# =========================
other_players = {}
player_names = {}
dead_players = set()     
dead_bodies = {}
player_facing_left = {}  # NEU: Blickrichtung anderer Spieler (True = schaut/geht nach links)
player_last_move_time = {}  # NEU: Zeitpunkt der letzten Positionsmeldung (fuer die Laufanimation)
player_walk_phase = {}      # NEU: aktuelle Laufanimations-Phase je Spieler

my_id = None
player_count = 0
host_id = 0
game_started = False
state = "menu"
imposter_reveal_ids = []

global_task_progress = 0
global_task_max = 0

# =========================
# ROLLEN-SYSTEM: NETZWERK- UND FÄHIGKEITS-ZUSTAND
# =========================
enabled_roles = set()          # vom Server per Paket 14 gesyncte aktive Rollen (nur Anzeige für Nicht-Host)
independent_winner_id = None   # für den "independent_win"-Screen
my_imposter_teammates = []     # NEU: IDs der anderen Imposter (nur Imposter bekommen diese Liste)
show_role_info = False         # NEU: Rollen-Info-Panel (Button am Bildschirmrand) sichtbar?

kill_cooldown_remaining = 0.0

monika_flag_pos = None

# NEU: Einstellungen des Hosts, feste Rollen (nur Host), sichtbare Fallen, Notfall-Regel
game_settings = {"cooldown": 30, "discussion": 45, "vote": 30}
fixed_role_map = {}            # pid -> roles.FIXED_* (nur der Host bekommt diese Liste)
visible_traps = {}             # trap_id -> (owner_id, x, y) - Noahs Fallen sieht jetzt jeder
my_emergency_used = False      # jeder Spieler darf den Notfallknopf nur EINMAL pro Runde benutzen
role_detail_key = None         # Rolle, deren Beschreibung in der Rollen-Uebersicht gezeigt wird
monika_flag_cooldown = 0.0      # bis die Flagge neu gesetzt werden darf
monika_teleport_cooldown = 0.0  # bis die Reise zur Flagge wieder moeglich ist

stroblpeter_marked_id = None
stroblpeter_mark_timer = 0.0
stroblpeter_ready_to_strike = False

evelyn_cooldown_remaining = 0.0
window_hazard_until = 0.0      # von Server (Paket 61) - bis wann die Fenster-Gefahr aktiv ist
window_hazard_room = -1        # welcher Fensterraum gerade offen steht (-1 = keiner)
window_zone_timer = 0.0        # wie lange man schon ununterbrochen in der Gefahrenzone steht

laurin_uses_left = 0

david_marked_id = None

noah_traps = []            # bis zu NOAH_TRAP_LIMIT eigene Fallen [(x, y), ...]
noah_trap_cooldown = 0.0

vogelscheicher_invisible_until = 0.0
decoys = {}                    # pid -> [x, y, expire_time] -- Attrappen anderer Spieler

pleschbergsteiger_uses_left = 0

yoshi_finds = 0
yoshi_find_points = []
yoshi_reveals_left = 0     # pro gefundenem Standard eine Rollen-Aufdeckung
yoshi_reveal_result = None     # (target_id, team_str, role_name)
yoshi_reveal_timer = 0.0

kaliyoga_bonus_used = False

tappeihnachtsmann_uses_left = 0
tappeihnachtsmann_find_points = []
immortal_until = 0.0           # lokale Anzeige (von Server Paket 78 gesetzt)
immortal_banner_timer = 0.0

raphi_collected = 0
raphi_collect_points = []

ramona_last_forge = 0.0
ramona_others_rights = {}      # pid -> verbleibende Rechte (aus Paket 80)
ramona_stand_timer = 0.0

vladimir_active = False
ghost_intro_timer = 0.0
ghost_video = None             # laufender VideoPlayer fuer Vladimirs Opfer
task_reset_banner_timer = 0.0  # Hinweis, dass Laurin eine Aufgabe zurueckgesetzt hat
task_reset_banner_name = ""

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

def recv_exact(s, n):
    """FIX: Liest GENAU n Bytes. sock.recv(n) darf laut TCP auch weniger liefern - dann waere
    der Datenstrom verschoben und alle folgenden Pakete wuerden falsch gelesen."""
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Verbindung zum Server getrennt")
        buf += chunk
    return buf

class LockedSocket:
    """FIX: Haupt- und Empfangs-Thread senden beide ueber denselben Socket. Mit dem Lock
    koennen sich zwei Pakete nie mehr ineinander schieben."""
    def __init__(self, raw):
        self._raw = raw
        self._lock = threading.Lock()

    def sendall(self, data):
        with self._lock:
            return self._raw.sendall(data)

    def recv(self, n):
        return self._raw.recv(n)

    def close(self):
        return self._raw.close()

# NEU: Der Empfangs-Thread darf keine Schriften rendern/Animationen bauen (SDL_ttf ist nicht
# thread-sicher). Er legt nur Auftraege hier ab, die Hauptschleife arbeitet sie ab.
ui_events = deque()

def receive_data(sock):
    """Empfangs-Thread (lokaler Modus und Server-Modus): liest Pakete vom Socket."""
    while True:
        try:
            data = sock.recv(1)
            if not data: break
            handle_packet(sock, data[0])
        except Exception as e:
            print("RECEIVE THREAD ERROR:", e)
            break

    # NEU: Verbindung zum Raum ist weg. Im Web-Modus den Browser informieren und die Sitzung beenden.
    if WEB_MODE and running:
        web_bridge.notify_end("room_closed", "Die Verbindung zum Raum wurde getrennt.")
        pygame.event.post(pygame.event.Event(pygame.QUIT))


def handle_packet(sock, packet_type):
    """Verarbeitet EIN Paket (das Typ-Byte ist schon gelesen). NEU: ausgelagert, damit der
    Browser-Modus - dort gibt es keine Threads - dieselbe Verarbeitung pro Frame nutzen kann."""
    global other_players, player_names, player_count, host_id, game_started, state
    global imposter_count, intro_timer, global_task_progress, global_task_max, dead_players, dead_bodies
    # WICHTIG: Diese fehlten bisher -> ohne "global" wurden meeting_active/meeting_timer/has_voted/
    # meeting_cooldown nur LOKAL in dieser Funktion verändert und die Hauptschleife hat davon nie etwas gesehen.
    # Dadurch ist beim Empfang von Paket 40/43 nach außen hin scheinbar nichts passiert.
    global meeting_active, meeting_timer, has_voted, meeting_cooldown, meeting_caller_id, meeting_reason
    global meeting_chat_input
    # show_minimap hatte denselben Fehler: wurde bei Meeting-Start lokal statt global auf False gesetzt
    global show_minimap
    # NEU: Rollen-System - alle Namen, die in dieser Funktion (neu) zugewiesen werden, müssen global sein
    global enabled_roles, independent_winner_id, vladimir_active, ghost_intro_timer
    global my_imposter_teammates, show_role_info
    global kill_cooldown_remaining
    global monika_flag_pos, monika_flag_cooldown, monika_teleport_cooldown
    global stroblpeter_marked_id, stroblpeter_mark_timer, stroblpeter_ready_to_strike
    global evelyn_cooldown_remaining, window_hazard_until, window_hazard_room, window_zone_timer
    global laurin_uses_left, david_marked_id, noah_traps, noah_trap_cooldown
    global meeting_phase, meeting_selected_target, meeting_result_id, meeting_result_timer
    global ghost_video, task_reset_banner_timer, task_reset_banner_name
    global vogelscheicher_invisible_until, decoys
    global pleschbergsteiger_uses_left
    global yoshi_finds, yoshi_find_points, yoshi_reveals_left, yoshi_reveal_result, yoshi_reveal_timer
    global kaliyoga_bonus_used
    global tappeihnachtsmann_uses_left, tappeihnachtsmann_find_points, immortal_until, immortal_banner_timer
    global raphi_collected, raphi_collect_points
    global ramona_last_forge, ramona_others_rights, ramona_stand_timer
    global task_aborted, final_roles, pending_end_state, pending_vladimir_video
    global intro_started_at
    global game_settings, fixed_role_map, visible_traps, my_emergency_used


    if packet_type == 1:
        old_ids = set(player_names.keys())
        player_count, host_id = struct.unpack("!BB", recv_exact(sock, 2))
        new_names = {}
        for _ in range(player_count):
            p_id = struct.unpack("!B", recv_exact(sock, 1))[0]
            name_length = struct.unpack("!B", recv_exact(sock, 1))[0]
            pname = recv_exact(sock, name_length).decode("utf-8", errors="replace")
            new_names[p_id] = pname
        player_names.clear()
        player_names.update(new_names)
        # NEU: Beitritts-Sound, wenn in der Lobby ein neuer Spieler dazukommt
        if old_ids and (set(new_names.keys()) - old_ids - {my_id}) and not game_started:
            sfx.play("enter_game")

    elif packet_type == 2:
        data_b = b""
        while len(data_b) < 9:
            packet = sock.recv(9 - len(data_b))
            if not packet: raise ConnectionError("Verbindung zum Server getrennt")
            data_b += packet
        p_id, x, y = struct.unpack("!Bii", data_b)
        if p_id in other_players:
            old_x, old_y = other_players[p_id][0], other_players[p_id][1]
            if x < old_x:
                player_facing_left[p_id] = True
            elif x > old_x:
                player_facing_left[p_id] = False
            # NEU: Laufanimation - merken, wann sich der Spieler zuletzt wirklich bewegt hat
            if (x, y) != (old_x, old_y):
                player_last_move_time[p_id] = time.time()
        else:
            player_last_move_time[p_id] = time.time()
        other_players[p_id] = [x, y]

    elif packet_type == 3:
        game_started = True
        state = "game"
        intro_timer = 300
        intro_started_at = time.time()
        # FIX: Modulo als Absicherung (es gibt nur so viele Spawnpunkte wie in der Karte)
        my_player.rect.x = spawnpoints[my_id % len(spawnpoints)].x
        my_player.rect.y = spawnpoints[my_id % len(spawnpoints)].y

        modifiers = struct.unpack("!B", recv_exact(sock, 1))[0]
        vladimir_active = bool(modifiers & 1)

        # Lokalen Fähigkeits-Zustand für die neue Runde zurücksetzen
        # (rollenspezifische Felder wie yoshi_finds/laurin_uses_left etc. werden
        # bereits in Paket 5 gesetzt, das immer VOR Paket 3 eintrifft)
        kill_cooldown_remaining = 0.0
        monika_flag_pos = None
        monika_flag_cooldown = 0.0
        monika_teleport_cooldown = 0.0
        stroblpeter_marked_id = None
        stroblpeter_mark_timer = 0.0
        stroblpeter_ready_to_strike = False
        evelyn_cooldown_remaining = 0.0
        window_hazard_until = 0.0
        window_hazard_room = -1
        window_zone_timer = 0.0
        david_marked_id = None
        noah_traps = []
        noah_trap_cooldown = 0.0
        vogelscheicher_invisible_until = 0.0
        decoys = {}
        yoshi_reveal_result = None
        yoshi_reveal_timer = 0.0
        kaliyoga_bonus_used = False
        immortal_until = 0.0
        immortal_banner_timer = 0.0
        ramona_last_forge = 0.0
        ramona_others_rights = {pid: 3 for pid in player_names.keys() if pid != my_id} if my_player.role_key == "ramona" else {}
        ramona_stand_timer = 0.0
        ghost_intro_timer = 0.0
        if ghost_video is not None:
            ghost_video.close()
        ghost_video = None
        task_reset_banner_timer = 0.0
        meeting_phase = MEETING_PHASE_NONE
        meeting_selected_target = None
        meeting_result_id = None
        meeting_result_timer = 0.0
        independent_winner_id = None
        show_role_info = False
        player_walk_phase.clear()
        player_last_move_time.clear()
        # NEU: Zustand der Animationen/Endbildschirme fuer die neue Runde leeren
        final_roles = {}
        pending_end_state = None
        pending_vladimir_video = False
        visible_traps = {}
        my_emergency_used = False
        meeting_cooldown = float(game_settings["cooldown"])   # Notfall-Cooldown auch nach dem Start
        ui_events.append(("round_start", None))

        try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
        except: pass

    elif packet_type == 4:
        disconnect_data = recv_exact(sock, 9)
        if len(disconnect_data) == 9:
            p_id, x, y = struct.unpack("!Bii", disconnect_data)
            if p_id in other_players: del other_players[p_id]

    elif packet_type == 5:
        base_team_byte, role_id = struct.unpack("!BB", recv_exact(sock, 2))
        role_key = roles.role_key_of(role_id)

        if base_team_byte == 1:
            my_player.role = "Imposter"
        elif base_team_byte == 2:
            my_player.role = "Independent"
        else:
            my_player.role = "Crewmate"
        my_player.role_key = role_key

        if role_key is not None:
            info = roles.ROLES[role_key]
            my_player.role_display_name = info["name"]
            my_player.role_desc = info["desc"]
            my_player.role_image = get_role_image(role_key, ROLE_REVEAL_SIZE)
        else:
            my_player.role_image = None
            if my_player.role == "Imposter":
                my_player.role_display_name = "Imposter"
                my_player.role_desc = "Eliminiere die Crew. Bleibe unentdeckt."
            elif my_player.role == "Independent":
                my_player.role_display_name = "Eigenständig"
                my_player.role_desc = "Verfolge dein eigenes, geheimes Ziel."
            else:
                my_player.role_display_name = "Crewmate"
                my_player.role_desc = "Erledige alle Aufgaben und finde die Imposter."

        # Rollenspezifische lokale Zähler/Fundpunkte zurücksetzen bzw. neu aufsetzen
        laurin_uses_left = roles.max_uses_of(role_key) if role_key == "laurin" else 0
        pleschbergsteiger_uses_left = roles.max_uses_of(role_key) if role_key == "pleschbergsteiger" else 0
        yoshi_finds = 0
        yoshi_reveals_left = 0
        # NEU: Fund-/Sammelpunkte werden zufaellig INNERHALB der Raeume verteilt
        # (siehe pick_item_spots) - nie ausserhalb der Map oder in einer Wand.
        yoshi_find_points = pick_item_spots(YOSHI_FIND_LIMIT) if role_key == "yoshi" else []
        tappeihnachtsmann_uses_left = roles.max_uses_of(role_key) if role_key == "tappeihnachtsmann" else 0
        tappeihnachtsmann_find_points = pick_item_spots(5) if role_key == "tappeihnachtsmann" else []
        raphi_collected = 0
        raphi_collect_points = pick_item_spots(10) if role_key == "raphi" else []
        # Die Imposter-Teamliste kommt separat per Paket 15 und gilt nur fuer Imposter
        my_imposter_teammates = []

        if my_player.role == "Imposter" or my_player.role == "Independent":
            my_player.my_assigned_tasks = []
            my_player.my_completed_tasks = []
        elif role_key == "raphi":
            my_player.my_assigned_tasks = []
            my_player.my_completed_tasks = []
        else:
            available_indices = list(range(len(TASK_TEMPLATES)))
            my_player.my_assigned_tasks = random.sample(available_indices, min(10, len(available_indices)))
            my_player.my_completed_tasks = []

    # NEU: Paket 15 - Liste der Mit-Imposter. Wird vom Server ausschliesslich an die
    # Imposter selbst geschickt, damit sie ihre Teammates kennen (und nicht killen).
    elif packet_type == 15:
        num_mates = struct.unpack("!B", recv_exact(sock, 1))[0]
        my_imposter_teammates = []
        for _ in range(num_mates):
            mate_id = struct.unpack("!B", recv_exact(sock, 1))[0]
            if mate_id != my_id:
                my_imposter_teammates.append(mate_id)

    # NEU: Sync der vom Host aktivierten Rollen (auch für Nicht-Host-Clients zur Anzeige)
    elif packet_type == 14:
        mask = struct.unpack("!I", recv_exact(sock, 4))[0]
        enabled_roles = set(roles.keys_from_bitmask(mask))

    elif packet_type == 12:
        imposter_count = struct.unpack("!B", recv_exact(sock, 1))[0]

    elif packet_type == 21: 
        global_task_progress, global_task_max = struct.unpack("!HH", recv_exact(sock, 4))

    elif packet_type == 22: 
        global imposter_reveal_ids
        num_imps = struct.unpack("!B", recv_exact(sock, 1))[0]
        imposter_reveal_ids = []
        for _ in range(num_imps):
            imposter_reveal_ids.append(struct.unpack("!B", recv_exact(sock, 1))[0])
        # NEU: erst nach einer laufenden Rauswurf-/Todes-Animation umschalten (Hauptschleife)
        pending_end_state = "crew_win"
        # Ein Sieg mitten im Meeting (z.B. Spieler verlaesst das Spiel) beendet das Meeting sofort
        meeting_active = False
        meeting_phase = MEETING_PHASE_NONE

    elif packet_type == 23:
        game_started = False
        state = "lobby"
        # FIX: stand vorher in einem zweiten "elif packet_type == 23"-Zweig, der nie
        # erreicht wurde - ein laufendes Meeting blieb so bis in die naechste Runde offen.
        meeting_active = False
        meeting_phase = MEETING_PHASE_NONE
        meeting_cooldown = 0.0
        pending_end_state = None
        pending_vladimir_video = False
        ui_events.append(("back_to_lobby", None))
        my_player.my_completed_tasks.clear()

        my_player.my_assigned_tasks.clear()
        global_task_progress = 0
        global_task_max = 0

        my_player.is_dead = False 
        my_player.is_venting = False       # NEU: Venting bei Reset zurücksetzen
        my_player.current_vent_idx = -1    # NEU: Vent-Index zurücksetzen
        dead_players.clear()
        dead_bodies.clear()
        player_facing_left.clear()
        player_walk_phase.clear()
        player_last_move_time.clear()
        my_imposter_teammates = []
        show_role_info = False
        my_player.rect.x = lobby_spawn_rects[my_id % len(lobby_spawn_rects)].x
        my_player.rect.y = lobby_spawn_rects[my_id % len(lobby_spawn_rects)].y
        try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
        except: pass

    elif packet_type == 31:
        # NEU: + Killer-ID (255 = keiner, z.B. Rauswurf/Fenster) fuer die Todes-Animation
        dead_id, no_corpse, weapon_id, death_flags, killer_id = struct.unpack("!BBBBB", recv_exact(sock, 5))
        dead_players.add(dead_id)
        ejected = bool(death_flags & DEATH_FLAG_EJECTED)
        if dead_id == my_id:
            my_player.is_dead = True
            my_player.is_venting = False
            if not ejected:
                # NEU: kurze Todes-Animation, die nur das Opfer selbst sieht
                ui_events.append(("death", (killer_id, death_flags, weapon_id)))
                # Nur wer von Vladimir getoetet wurde, muss das Anime-Intro abwarten -
                # es startet direkt nach der Todes-Animation (siehe Hauptschleife)
                if death_flags & DEATH_FLAG_VLADIMIR:
                    pending_vladimir_video = True
        elif killer_id == my_id and not ejected:
            sfx.play("kill")   # der Killer hoert den eigenen Mord
        # Im Meeting rausgevotete Spieler hinterlassen keine Leiche (wie im Original-Spiel),
        # genauso wie Steinermikes Opfer (no_corpse) oder Evelyns Fensterfalle -
        # nur ein "echter" Mord außerhalb eines Meetings erzeugt eine meldbare Leiche.
        if not meeting_active and not no_corpse:
            if dead_id == my_id:
                dead_bodies[dead_id] = (my_player.rect.x, my_player.rect.y, weapon_id)
            elif dead_id in other_players:
                dead_bodies[dead_id] = (other_players[dead_id][0], other_players[dead_id][1], weapon_id)

    elif packet_type == 32:
        num_imps = struct.unpack("!B", recv_exact(sock, 1))[0]
        imposter_reveal_ids = []
        for _ in range(num_imps):
            imposter_reveal_ids.append(struct.unpack("!B", recv_exact(sock, 1))[0])
        pending_end_state = "imposter_win"
        # Ein Sieg mitten im Meeting (z.B. Spieler verlaesst das Spiel) beendet das Meeting sofort
        meeting_active = False
        meeting_phase = MEETING_PHASE_NONE

    elif packet_type == 40:
        caller_id, reason = struct.unpack("!BB", recv_exact(sock, 2))
        meeting_active = True
        # NEU: Erst wird nur diskutiert/gechattet, die Abstimmung kommt mit Paket 42
        meeting_phase = MEETING_PHASE_DISCUSSION
        meeting_timer = float(game_settings["discussion"])
        meeting_selected_target = None
        meeting_result_id = None
        meeting_caller_id = caller_id
        meeting_reason = reason
        if caller_id == my_id and reason == MEETING_REASON_BUTTON:
            my_emergency_used = True   # NEU: nur ein Notfall-Meeting pro Spieler
        has_voted = False
        player_votes.clear()
        meeting_chat_log.clear()
        meeting_chat_input = ""
        dead_bodies.clear()  # Nach einem Meeting (egal ob Knopf oder Leiche) sind alle Leichen weg
        if task_manager.active_task:
            # FIX: vorher zaehlte eine durch das Meeting abgebrochene Aufgabe als ERLEDIGT
            task_aborted = True
            task_manager.reset_active_task()
            task_manager.active_task = None
        show_minimap = False
        show_role_info = False
        sfx.play("report" if reason == MEETING_REASON_BODY else "emergency")

    # NEU: Die Abstimmungsphase beginnt
    elif packet_type == 42:
        meeting_phase = MEETING_PHASE_VOTE
        meeting_timer = float(game_settings["vote"])
        meeting_selected_target = None

    elif packet_type == 41:
        voter_id, target_id = struct.unpack("!BB", recv_exact(sock, 2))
        player_votes[voter_id] = target_id

    elif packet_type == 50:
        sender_id, msg_len = struct.unpack("!BB", recv_exact(sock, 2))
        msg_bytes = b""
        while len(msg_bytes) < msg_len:
            chunk = sock.recv(msg_len - len(msg_bytes))
            if not chunk: break
            msg_bytes += chunk
        message = msg_bytes.decode("utf-8", errors="replace")
        sender_name = player_names.get(sender_id, f"Spieler {sender_id}")
        meeting_chat_log.append(f"{sender_name}: {message}")

    elif packet_type == 43:
        # NEU: Der Server schickt mit, wer rausgeworfen wurde (255 = niemand), warum, dessen
        # Team + Rolle (Role-Reveal) und wie viele Imposter noch leben
        evicted_id, result_code, ev_team, ev_role, imps_left = struct.unpack("!BBBBB", recv_exact(sock, 5))
        meeting_result_id = evicted_id
        meeting_result_timer = 6.0
        ui_events.append(("eject", (evicted_id, result_code, ev_team, ev_role, imps_left)))
        meeting_active = False
        meeting_phase = MEETING_PHASE_NONE
        meeting_selected_target = None
        # NEU: Der Notfall-Cooldown startet erst, wenn das Meeting endet (vom Host einstellbar)
        meeting_cooldown = float(game_settings["cooldown"])
        # Alle Spieler auf fixe Spawnpoints zurücksetzen
        if my_id is not None and spawnpoints:
            my_player.rect.x = spawnpoints[my_id % len(spawnpoints)].x
            my_player.rect.y = spawnpoints[my_id % len(spawnpoints)].y
            my_player.is_venting = False
        try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
        except: pass

    # ===== ROLLEN-FÄHIGKEITEN =====

    # Evelyn: Fenster-Sabotage ist jetzt aktiv
    elif packet_type == 61:
        window_hazard_room = struct.unpack("!B", recv_exact(sock, 1))[0]
        window_hazard_until = time.time() + EVELYN_HAZARD_DURATION
        window_zone_timer = 0.0

    # NEU: Laurin hat eine Aufgabe fuer alle wieder unerledigt gemacht
    elif packet_type == 64:
        reset_idx = struct.unpack("!B", recv_exact(sock, 1))[0]
        if reset_idx in my_player.my_completed_tasks:
            my_player.my_completed_tasks.remove(reset_idx)
            reset_task_instance(reset_idx)
            task_reset_banner_timer = 5.0
            task_reset_banner_name = TASK_TEMPLATES[reset_idx]["name"] if reset_idx < len(TASK_TEMPLATES) else "?"

    # Vogelscheicher: Attrappen-Position eines anderen Spielers
    elif packet_type == 69:
        owner_id, dx, dy = struct.unpack("!Bii", recv_exact(sock, 9))
        decoys[owner_id] = [dx, dy, time.time() + VOGELSCHEICHER_INVISIBLE_DURATION]

    # Pleschbergsteiger: ein Geist wurde wiederbelebt
    elif packet_type == 74:
        revived_id = struct.unpack("!B", recv_exact(sock, 1))[0]
        dead_players.discard(revived_id)
        if revived_id in dead_bodies:
            del dead_bodies[revived_id]
        if revived_id == my_id:
            my_player.is_dead = False

    # Yoshi: Antwort auf die Rollen-Aufdeckung
    elif packet_type == 76:
        target_id, team_byte, target_role_id = struct.unpack("!BBB", recv_exact(sock, 3))
        team_str = {0: "Besatzung", 1: "Imposter", 2: "Eigenständig"}.get(team_byte, "?")
        revealed_key = roles.role_key_of(target_role_id)
        role_name = roles.ROLES[revealed_key]["name"] if revealed_key is not None else team_str
        yoshi_reveal_result = (target_id, team_str, role_name)
        yoshi_reveal_timer = 6.0

    # Tappeihnachtsmann: Unsterblichkeit ist jetzt für alle aktiv
    elif packet_type == 78:
        immortal_until = time.time() + IMMORTALITY_DURATION_CLIENT
        immortal_banner_timer = IMMORTALITY_DURATION_CLIENT

    # Ramona: Rechte-Update eines Spielers
    elif packet_type == 80:
        target_id, new_rights = struct.unpack("!BB", recv_exact(sock, 2))
        ramona_others_rights[target_id] = new_rights

    # Eigenständig gewinnt (Ramona)
    elif packet_type == 82:
        winner_id = struct.unpack("!B", recv_exact(sock, 1))[0]
        independent_winner_id = winner_id
        pending_end_state = "independent_win"
        # Ein Sieg mitten im Meeting (z.B. Spieler verlaesst das Spiel) beendet das Meeting sofort
        meeting_active = False
        meeting_phase = MEETING_PHASE_NONE

    # NEU: Paket 17 - Einstellungen des Hosts (Notfall-Cooldown, Diskussion, Abstimmung)
    elif packet_type == 17:
        cd, disc, vote = struct.unpack("!BBB", recv_exact(sock, 3))
        game_settings = {"cooldown": cd, "discussion": disc, "vote": vote}

    # NEU: Paket 19 - feste Rollen-Zuteilung (bekommt nur der Host)
    elif packet_type == 19:
        count = struct.unpack("!B", recv_exact(sock, 1))[0]
        new_map = {}
        for _ in range(count):
            pid, code = struct.unpack("!BB", recv_exact(sock, 2))
            new_map[pid] = code
        fixed_role_map = new_map

    # NEU: Paket 67/70 - Noahs Fallen sind fuer alle sichtbar
    elif packet_type == 67:
        trap_id, owner_id, tx, ty = struct.unpack("!HBii", recv_exact(sock, 11))
        visible_traps[trap_id] = (owner_id, tx, ty)
    elif packet_type == 70:
        trap_id = struct.unpack("!H", recv_exact(sock, 2))[0]
        visible_traps.pop(trap_id, None)

    # NEU: Paket 83 - am Spielende deckt der Server alle Rollen auf (fuer den Endbildschirm)
    elif packet_type == 83:
        count = struct.unpack("!B", recv_exact(sock, 1))[0]
        revealed = {}
        for _ in range(count):
            pid, team_b, role_b = struct.unpack("!BBB", recv_exact(sock, 3))
            revealed[pid] = (team_b, role_b)
        final_roles = revealed

def finish_connect(new_id):
    """Nach dem Handshake: eigene ID + Spielfigur (gemeinsam fuer TCP und Browser)."""
    global my_id, my_player, connected
    my_id = new_id
    lx = lobby_spawn_rects[my_id % len(lobby_spawn_rects)].x
    ly = lobby_spawn_rects[my_id % len(lobby_spawn_rects)].y
    my_player = Player(lx, ly, player_images[my_id % len(player_images)])
    connected = True
    sfx.play("enter_game")

def connect_to_server(ip, name, spawnpoints, port=PORT):
    global sock, my_id, my_player, connected, state
    try:
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(5)
        raw_sock.connect((ip, port))
        setup_socket(raw_sock)
        sock = LockedSocket(raw_sock)

        name_data = name.encode()
        sock.sendall(struct.pack("!B", len(name_data)))
        sock.sendall(name_data)

        # Name + ID-Antwort noch mit Timeout (Raum voll/Spiel laeuft -> Server schliesst sofort)
        new_id = struct.unpack('!B', recv_exact(sock, 1))[0]
        raw_sock.settimeout(None)
        finish_connect(new_id)
        threading.Thread(target=receive_data, args=(sock,), daemon=True).start()
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

def get_minimap_origin():
    """Linke obere Ecke der Minimap - wird zum Zeichnen UND fuer Klicks gebraucht."""
    return (WIDTH - MINIMAP_WIDTH) // 2, (HEIGHT - MINIMAP_HEIGHT) // 2

def get_window_room_minimap_rects():
    """NEU: Anklickbare Rechtecke der Fensterraeume auf der Minimap (fuer Evelyn).
    Rueckgabe: Liste von (raum_index, rect)."""
    mm_x, mm_y = get_minimap_origin()
    result = []
    for idx, zone in enumerate(window_zones):
        rx = mm_x + int((zone.x / MAP_WIDTH_PX) * MINIMAP_WIDTH)
        ry = mm_y + int((zone.y / MAP_HEIGHT_PX) * MINIMAP_HEIGHT)
        rw = max(10, int((zone.width / MAP_WIDTH_PX) * MINIMAP_WIDTH))
        rh = max(10, int((zone.height / MAP_HEIGHT_PX) * MINIMAP_HEIGHT))
        result.append((idx, pygame.Rect(rx, ry, rw, rh)))
    return result

def ghost_intro_blocking():
    """NEU: True, solange ein von Vladimir getoeteter Spieler noch das Intro sehen muss."""
    if not my_player.is_dead:
        return False
    if ghost_video is not None and ghost_video.active:
        return True
    return ghost_intro_timer > 0

def reset_task_instance(idx):
    """NEU: Ersetzt die Aufgaben-Instanz durch eine frische, damit eine von Laurin
    zurueckgesetzte Aufgabe wirklich wieder von vorne gespielt werden kann (sonst gilt sie
    intern weiter als abgeschlossen und wuerde sofort wieder zugehen)."""
    try:
        old_task = task_manager.tasks[idx]
        if task_manager.active_task is old_task:
            return  # laeuft gerade - nicht unter den Fuessen wegziehen
        task_manager.tasks[idx] = type(old_task)(old_task.screen)
    except Exception as e:
        print("TASK RESET ERROR:", e)

def get_meeting_layout():
    """Liefert Spieler-Boxen, Skip-Button und Chat-Bereiche für die Meeting-Ansicht.
    Wird sowohl von draw_meeting() (Zeichnen) als auch vom Event-Handler (Abstimmen/Chat)
    benutzt, damit beide garantiert dieselben Koordinaten verwenden."""
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

    # Chat-Bereich unten: Log-Fenster + Eingabezeile mit Skip-Button daneben
    input_row_y = HEIGHT - 60
    chat_rect = pygame.Rect(40, HEIGHT - 230, WIDTH - 80, 150)
    chat_input_rect = pygame.Rect(40, input_row_y, WIDTH - 80 - 210, 40)
    skip_rect = pygame.Rect(WIDTH - 40 - 200, input_row_y, 200, 40)

    # NEU: Bestaetigungsleiste ueber dem Chat. Sie erscheint erst, wenn man in der
    # Abstimmungsphase jemanden angeklickt hat: Haken = Stimme abgeben, X = Auswahl loeschen.
    bar_w, bar_h = 520, 52
    bar_rect = pygame.Rect((WIDTH - bar_w) // 2, chat_rect.top - bar_h - 14, bar_w, bar_h)
    confirm_rect = pygame.Rect(bar_rect.right - 110, bar_rect.y + 6, 46, bar_h - 12)
    cancel_rect = pygame.Rect(bar_rect.right - 58, bar_rect.y + 6, 46, bar_h - 12)
    return boxes, skip_rect, chat_rect, chat_input_rect, bar_rect, confirm_rect, cancel_rect

def meeting_selection_label():
    """Text der Bestaetigungsleiste fuer die aktuelle Auswahl."""
    if meeting_selected_target is None:
        return ""
    if meeting_selected_target == 255:
        return "Abstimmung überspringen?"
    name = player_names.get(meeting_selected_target, f"Spieler {meeting_selected_target}")
    return f"Für {name} stimmen?"

def draw_meeting():
    # Dunkler Overlay-Hintergrund (wie die Map) - NEU: Flaeche wird wiederverwendet
    fx.blit_alpha(screen, fx.dim_surface((WIDTH, HEIGHT), (15, 20, 30)), (0, 0), 230)

    caller_name = player_names.get(meeting_caller_id, f"Spieler {meeting_caller_id}")
    if meeting_reason == MEETING_REASON_BODY:
        title_str = f"{caller_name} hat eine Leiche gemeldet!"
    elif meeting_reason == MEETING_REASON_KALIYOGA:
        title_str = f"{caller_name} hat ein Yoga-Meeting einberufen!"
    else:
        title_str = f"{caller_name} hat ein Meeting einberufen!"
    title_txt = menu_font.render(title_str, True, (255, 255, 255))
    screen.blit(title_txt, (WIDTH // 2 - title_txt.get_width() // 2, 30))

    # NEU: Phasenanzeige - erst reine Diskussion, danach die Abstimmung
    if meeting_phase == MEETING_PHASE_VOTE:
        phase_str = f"ABSTIMMUNG - noch {int(meeting_timer)}s"
        phase_color = (255, 210, 90)
    else:
        phase_str = f"DISKUSSION - Abstimmung startet in {int(meeting_timer)}s"
        phase_color = (120, 200, 255)
    phase_txt = small_font.render(phase_str, True, phase_color)
    screen.blit(phase_txt, (WIDTH // 2 - phase_txt.get_width() // 2, 78))

    boxes, skip_rect, chat_rect, chat_input_rect, bar_rect, confirm_rect, cancel_rect = get_meeting_layout()
    voting_open = (meeting_phase == MEETING_PHASE_VOTE) and not has_voted and not my_player.is_dead

    for p_id, rect in boxes:
        is_p_dead = p_id in dead_players
        is_selected = (meeting_selected_target == p_id)
        bg_color = (25, 25, 30) if is_p_dead else ((55, 70, 45) if is_selected else (40, 45, 55))

        pygame.draw.rect(screen, bg_color, rect, border_radius=8)
        if is_selected:
            border_color = (255, 210, 90)
        elif p_id == my_id:
            border_color = (0, 255, 255)
        else:
            border_color = (100, 100, 110)
        pygame.draw.rect(screen, border_color, rect, 3 if is_selected else 2, border_radius=8)

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
        name_txt = fx.render_cached(name_font, p_name, name_color)
        screen.blit(name_txt, (rect.x + 15 + PLAYER_SIZE, rect.y + (rect.height - name_txt.get_height()) // 2))

        # Wie viele Stimmen hat dieser Spieler schon bekommen?
        votes_for = sum(1 for v in player_votes.values() if v == p_id)
        if votes_for > 0:
            votes_txt = name_font.render("O " * votes_for, True, (255, 90, 90))
            screen.blit(votes_txt, (rect.right - 12 - votes_txt.get_width(), rect.y + 6))

        # Hat dieser Spieler bereits abgestimmt?
        if p_id in player_votes:
            voted_marker = proximity_font.render("hat gewählt", True, (0, 220, 120))
            screen.blit(voted_marker, (rect.right - 12 - voted_marker.get_width(), rect.bottom - 20))

    # Skip-Button (rechts neben der Chat-Eingabe)
    skip_selected = (meeting_selected_target == 255)
    pygame.draw.rect(screen, (75, 90, 60) if skip_selected else (60, 65, 75), skip_rect, border_radius=8)
    pygame.draw.rect(screen, (255, 210, 90) if skip_selected else (200, 200, 200), skip_rect,
                     3 if skip_selected else 2, border_radius=8)
    skip_txt = name_font.render("SKIP", True, (255, 255, 255))
    screen.blit(skip_txt, (skip_rect.centerx - skip_txt.get_width() // 2, skip_rect.centery - skip_txt.get_height() // 2))

    skip_voters = sum(1 for v in player_votes.values() if v == 255)
    if skip_voters > 0:
        sv_txt = name_font.render(f"({skip_voters})", True, (0, 255, 0))
        screen.blit(sv_txt, (skip_rect.centerx - sv_txt.get_width() // 2, skip_rect.top - 22))

    # NEU: Erst anklicken, dann bestätigen - Haken gibt die Stimme ab, X verwirft die Auswahl
    if voting_open and meeting_selected_target is not None:
        pygame.draw.rect(screen, (30, 34, 44), bar_rect, border_radius=10)
        pygame.draw.rect(screen, (255, 210, 90), bar_rect, 2, border_radius=10)
        label = name_font.render(meeting_selection_label(), True, (255, 255, 255))
        screen.blit(label, (bar_rect.x + 16, bar_rect.centery - label.get_height() // 2))

        pygame.draw.rect(screen, (0, 180, 90), confirm_rect, border_radius=8)
        pygame.draw.rect(screen, (255, 255, 255), confirm_rect, 2, border_radius=8)
        ok_txt = menu_font.render("v", True, (255, 255, 255))
        screen.blit(ok_txt, (confirm_rect.centerx - ok_txt.get_width() // 2, confirm_rect.centery - ok_txt.get_height() // 2))

        pygame.draw.rect(screen, (190, 60, 60), cancel_rect, border_radius=8)
        pygame.draw.rect(screen, (255, 255, 255), cancel_rect, 2, border_radius=8)
        x_txt = menu_font.render("x", True, (255, 255, 255))
        screen.blit(x_txt, (cancel_rect.centerx - x_txt.get_width() // 2, cancel_rect.centery - x_txt.get_height() // 2))
    else:
        if meeting_phase == MEETING_PHASE_DISCUSSION:
            hint_str, hint_col = "Jetzt wird nur diskutiert - abgestimmt wird gleich.", (170, 175, 190)
        elif has_voted:
            hint_str, hint_col = "Deine Stimme ist abgegeben.", (0, 220, 120)
        elif my_player.is_dead:
            hint_str, hint_col = "Als Geist darfst du nicht abstimmen.", (170, 175, 190)
        else:
            hint_str, hint_col = "Klicke einen Spieler oder SKIP an - danach mit dem Haken bestätigen.", (255, 210, 90)
        hint = chat_font.render(hint_str, True, hint_col)
        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, bar_rect.centery - hint.get_height() // 2))

    # =========================
    # CHAT (unter der Abstimmung)
    # =========================
    pygame.draw.rect(screen, (25, 28, 35), chat_rect, border_radius=8)
    pygame.draw.rect(screen, (90, 95, 105), chat_rect, width=2, border_radius=8)

    line_height = 22
    visible_lines = max(1, (chat_rect.height - 12) // line_height)
    y_off = chat_rect.bottom - 8 - line_height
    for msg in reversed(meeting_chat_log[-visible_lines:]):
        msg_surf = fx.render_cached(chat_font, msg, (230, 230, 230))
        screen.blit(msg_surf, (chat_rect.x + 10, y_off))
        y_off -= line_height

    # Eingabezeile
    pygame.draw.rect(screen, (245, 245, 245), chat_input_rect, border_radius=6)
    if my_player.is_dead:
        # NEU: Geister koennen nicht schreiben - Hinweis statt Eingabezeile
        pygame.draw.rect(screen, (60, 62, 72), chat_input_rect, border_radius=6)
        ghost_txt = chat_font.render("Als Geist kannst du nicht mehr schreiben.", True, (185, 188, 200))
        screen.blit(ghost_txt, (chat_input_rect.x + 10, chat_input_rect.centery - ghost_txt.get_height() // 2))
        return
    input_display = meeting_chat_input
    # Text abschneiden, falls er breiter als das Feld wird (neueste Zeichen bleiben sichtbar)
    while chat_font.size(input_display + "|")[0] > chat_input_rect.width - 16 and len(input_display) > 0:
        input_display = input_display[1:]
    input_surf = chat_font.render(input_display + "|", True, (20, 20, 20))
    screen.blit(input_surf, (chat_input_rect.x + 8, chat_input_rect.y + (chat_input_rect.height - input_surf.get_height()) // 2))

def nearest_task_button(max_dist=50):
    """NEU: Aufgabe in Benutzungs-Reichweite (gleiche Regel wie Taste E)."""
    for btn in task_buttons:
        if btn["task_index"] not in my_player.my_assigned_tasks:
            continue
        d = math.hypot(my_player.rect.centerx - btn["rect"].centerx, my_player.rect.centery - btn["rect"].centery)
        if d < max_dist:
            return btn
    return None

def nearest_body_id(max_dist=60):
    """NEU: Leiche in Melde-Reichweite (gleicher Radius wie im E-Handler)."""
    my_center = my_player.rect.center
    for body_id, (bx, by, _weapon_id) in dead_bodies.items():
        body_center = (bx + PLAYER_SIZE // 2, by + PLAYER_SIZE // 2)
        if math.hypot(my_center[0] - body_center[0], my_center[1] - body_center[1]) < max_dist:
            return body_id
    return None

def at_emergency_button():
    return any(my_player.rect.colliderect(box) for box in emergency_hitboxes)

def current_kill_target():
    """NEU: Wen wuerde E jetzt toeten? (fuer Button-Zustand + rote Markierung)"""
    if my_player.role != "Imposter" or my_player.is_dead or my_player.is_venting:
        return None
    kill_range = KILL_RANGE_MARTIN if my_player.role_key == "martin" else KILL_RANGE_DEFAULT
    return find_nearest_player(my_player.rect.center, other_players, kill_range, dead_players,
                               exclude_ids=my_imposter_teammates)

def draw_task_buttons(surface, buttons, player_obj, camera_x, camera_y):
    """NEU: Aufgaben-Markierungen auf der Karte - offene Aufgaben gelb mit "!", erledigte gruen
    mit Haken, in Reichweite mit Beschriftung "E: Name" (vorher wurde die Beschriftung zwar
    berechnet, aber nie gezeichnet)."""
    view = surface.get_rect()
    near_btn = nearest_task_button() if player_obj.role == "Crewmate" else None
    for btn in buttons:
        t_idx = btn["task_index"]
        is_crew = player_obj.role == "Crewmate"
        if is_crew and t_idx not in player_obj.my_assigned_tasks:
            continue

        dr = btn["rect"].move(-camera_x, -camera_y)
        if not dr.inflate(40, 40).colliderect(view):
            continue
        done = t_idx in player_obj.my_completed_tasks

        if not is_crew:
            # Imposter/Eigenstaendige sehen alle Aufgaben dezent (zum Vortaeuschen bzw. fuer Laurin)
            pygame.draw.rect(surface, (150, 150, 165), dr, 1, border_radius=4)
            continue

        if done:
            pygame.draw.rect(surface, (40, 200, 110), dr, 1, border_radius=4)
            cx, cy = dr.right - 2, dr.top + 2
            pygame.draw.circle(surface, (40, 200, 110), (cx, cy), 5)
            pygame.draw.line(surface, (255, 255, 255), (cx - 3, cy), (cx - 1, cy + 2), 2)
            pygame.draw.line(surface, (255, 255, 255), (cx - 1, cy + 2), (cx + 3, cy - 2), 2)
        else:
            pygame.draw.rect(surface, (255, 215, 60), dr, 2, border_radius=4)
            bx, by = dr.centerx, dr.top - 7
            pygame.draw.circle(surface, (255, 215, 60), (bx, by), 6)
            pygame.draw.line(surface, (40, 30, 0), (bx, by - 3), (bx, by + 1), 2)
            pygame.draw.circle(surface, (40, 30, 0), (bx, by + 3), 1)

        if near_btn is btn:
            text = f"Erledigt: {btn['name']}" if done else f"E: {btn['name']}"
            lbl = proximity_font.render(text, True, (255, 255, 255) if not done else (160, 230, 180))
            bg = pygame.Rect(0, 0, lbl.get_width() + 8, lbl.get_height() + 2)
            bg.midbottom = (dr.centerx, dr.top - 14)
            pygame.draw.rect(surface, (15, 17, 24), bg, border_radius=4)
            pygame.draw.rect(surface, (255, 215, 60) if not done else (40, 200, 110), bg, 1, border_radius=4)
            surface.blit(lbl, (bg.x + 4, bg.y + 1))

def draw_world_highlights(surface, camera_x, camera_y):
    """NEU: Hervorhebungen in der Welt - Kill-Ziel rot, meldbare Leiche orange, benutzbarer Vent gruen."""
    if my_player.is_dead:
        return
    target = current_kill_target() if kill_cooldown_remaining <= 0 else None
    if target is not None and target in other_players:
        tx, ty = other_players[target]
        r = pygame.Rect(tx - camera_x - 3, ty - camera_y - 3 + get_walk_offset(target), PLAYER_SIZE + 6, PLAYER_SIZE + 6)
        pygame.draw.rect(surface, (255, 50, 50), r, 2, border_radius=5)
    body = nearest_body_id()
    if body is not None and body in dead_bodies:
        bx, by, _w = dead_bodies[body]
        r = pygame.Rect(bx - camera_x - 3, by - camera_y - 3, int(PLAYER_SIZE * 1.3) + 6, PLAYER_SIZE + 6)
        pygame.draw.rect(surface, (255, 150, 40), r, 2, border_radius=5)
    if my_player.role == "Imposter" and not my_player.is_venting:
        cv = get_current_vent(my_player, vents)
        if cv is not None:
            pygame.draw.rect(surface, (90, 220, 120), cv.move(-camera_x, -camera_y).inflate(4, 4), 2, border_radius=4)

# =========================
# MENÜ DRAWING
# =========================
menu_font = pygame.font.SysFont("arial", 40)
small_font = pygame.font.SysFont("arial", 28)
chat_font = pygame.font.SysFont("arial", 18)

info_text1 = small_font.render(f"Bewegung: WASD", True, (255, 255, 255))
info_text2 = small_font.render(f"Map öffnen/schließen: M", True, (255, 255, 255))
info_text3 = small_font.render(f"Benutzen/Interagieren/Kill: E", True, (255, 255, 255))
info_text4 = small_font.render(f"Rollen-Fähigkeit: F", True, (255, 255, 255))
info_text5 = small_font.render(f"Rolle nachschlagen: R", True, (255, 255, 255))

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

def role_counts(enabled_set):
    friendly_n = sum(1 for k in enabled_set if roles.team_of(k) == roles.TEAM_CREW)
    enemy_n = sum(1 for k in enabled_set if roles.team_of(k) == roles.TEAM_IMPOSTOR)
    independent_n = sum(1 for k in enabled_set if roles.team_of(k) == roles.TEAM_INDEPENDENT)
    return friendly_n, enemy_n, independent_n

def max_imposters_for(n_players):
    return roles.max_imposters_for(n_players)

def current_role_setup_status():
    """Gleiche Pruefung wie der Server (roles.setup_status). Der Host kennt auch die festen Zuteilungen."""
    fixed_codes = [c for pid, c in fixed_role_map.items() if pid in player_names] if my_id == host_id else []
    ok, msg, _n_imp = roles.setup_status(max(1, len(player_names)), imposter_count, enabled_roles, fixed_codes)
    return ok, msg

def get_role_select_layout():
    """Liefert Spalten-Layout (Team-Überschrift + je Rolle ein Zeilen-Rect + Checkbox-Rect)
    sowie den Zurück-Button. Wird von draw_role_select() UND dem Klick-Handler benutzt,
    analog zu get_meeting_layout()."""
    columns = [
        (roles.TEAM_IMPOSTOR, "FEINDLICH", (255, 90, 90)),
        (roles.TEAM_CREW, "FREUNDLICH", (100, 255, 130)),
        (roles.TEAM_INDEPENDENT, "EIGENSTÄNDIG", (255, 210, 90)),
    ]
    col_w = min(460, (WIDTH - 160) // 3)
    total_w = col_w * 3 + 80
    start_x = (WIDTH - total_w) // 2
    start_y = 222   # FIX: vorher ueberlappte der Hinweistext (y=154) die Spaltenueberschriften
    # Zeilenhoehe an die Bildschirmhoehe anpassen, damit die laengste Spalte nicht
    # in den ZURUECK-Button unten laeuft
    max_rows = max(len(roles.keys_by_team(team)) for team, _label, _color in columns)
    avail_h = max(60, (HEIGHT - 120) - start_y)
    row_h = max(34, min(52, avail_h // max(1, max_rows)))

    rows = []  # (role_key, row_rect, checkbox_rect)
    headers = []  # (text, color, x, y)
    for i, (team, label, color) in enumerate(columns):
        col_x = start_x + i * (col_w + 40)
        headers.append((label, color, col_x, start_y - 40))
        for j, key in enumerate(roles.keys_by_team(team)):
            row_rect = pygame.Rect(col_x, start_y + j * row_h, col_w, row_h - 8)
            checkbox_rect = pygame.Rect(col_x + col_w - 36, row_rect.y + (row_rect.height - 26) // 2, 26, 26)
            rows.append((key, row_rect, checkbox_rect))

    back_rect = pygame.Rect(40, HEIGHT - 100, 200, 60)
    return rows, headers, back_rect

def role_detail_rect(rows):
    """NEU: Beschreibungs-Feld unter der (kurzen) Spalte EIGENSTAENDIG."""
    ind_rows = [r for key, r, _c in rows if roles.team_of(key) == roles.TEAM_INDEPENDENT]
    top = (ind_rows[-1].bottom + 24) if ind_rows else 260
    col_x = ind_rows[0].x if ind_rows else WIDTH - 480
    col_w = ind_rows[0].width if ind_rows else 440
    return pygame.Rect(col_x, top, col_w, max(160, HEIGHT - 120 - top))

def draw_role_detail(rect, key):
    hud.draw_panel_card(screen, rect, border=(90, 110, 200))
    if key is None:
        hint = wrap_text_render("Fahre mit der Maus über eine Rolle oder klicke sie an, um die ganze Beschreibung zu lesen.",
                                chat_font, (170, 175, 190), rect.width - 32)
        y = rect.y + 20
        for line in hint:
            screen.blit(line, (rect.x + 16, y))
            y += line.get_height() + 4
        return
    info = roles.ROLES[key]
    team = info["team"]
    team_col = {roles.TEAM_IMPOSTOR: (255, 90, 90), roles.TEAM_CREW: (100, 255, 130)}.get(team, (255, 210, 90))
    team_txt = {roles.TEAM_IMPOSTOR: "Feindlich (Imposter-Team)", roles.TEAM_CREW: "Freundlich (Besatzung)"}.get(team, "Eigenständig")
    img = get_role_image(key, ROLE_REVEAL_SIZE)
    y = rect.y + 16
    if img:
        screen.blit(img, (rect.x + 16, y))
    tx = rect.x + 16 + (ROLE_REVEAL_SIZE + 14 if img else 0)
    screen.blit(fx.font(24).render(info["name"], True, (255, 255, 255)), (tx, y + 8))
    screen.blit(fx.font(16).render(team_txt, True, team_col), (tx, y + 42))
    if info.get("max_uses"):
        screen.blit(fx.font(14, False).render(f"Nutzungen pro Spiel: {info['max_uses']}", True, (190, 195, 210)), (tx, y + 66))
    y += (ROLE_REVEAL_SIZE if img else 60) + 14
    for line in wrap_text_render(info["desc"], chat_font, (230, 232, 240), rect.width - 32):
        if y + line.get_height() > rect.bottom - 8:
            break
        screen.blit(line, (rect.x + 16, y))
        y += line.get_height() + 4

def draw_role_select():
    global role_detail_key
    screen.fill((18, 18, 26))
    is_host = my_id == host_id
    title = menu_font.render("ROLLEN AUSWÄHLEN" if is_host else "ROLLEN-ÜBERSICHT", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))

    friendly_n, enemy_n, independent_n = role_counts(enabled_roles)
    valid, status_msg = current_role_setup_status()
    count_color = (100, 255, 130) if valid else (255, 90, 90)
    count_text = small_font.render(
        f"Freundlich: {friendly_n}   |   Feindlich: {enemy_n}   |   Eigenständig: {independent_n}"
        f"   |   Imposter: {imposter_count}   |   Spieler: {len(player_names)}",
        True, count_color)
    screen.blit(count_text, (WIDTH // 2 - count_text.get_width() // 2, 100))
    warn_text = chat_font.render(status_msg, True, count_color)
    screen.blit(warn_text, (WIDTH // 2 - warn_text.get_width() // 2, 132))
    hint_str = ("Klick auf eine Rolle schaltet sie an/aus. Jede Spezialrolle wird höchstens einmal vergeben."
                if is_host else "Nur der Host kann Rollen an- und abschalten. Grün = in dieser Runde aktiv.")
    hint_text = chat_font.render(hint_str, True, (170, 170, 180))
    screen.blit(hint_text, (WIDTH // 2 - hint_text.get_width() // 2, 154))

    rows, headers, back_rect = get_role_select_layout()
    # NEU: Beschreibung der Rolle unter der Maus (sonst der zuletzt angeklickten)
    mouse = pygame.mouse.get_pos()
    hovered = next((key for key, r, _c in rows if r.collidepoint(mouse)), None)
    draw_role_detail(role_detail_rect(rows), hovered or role_detail_key)

    for label, color, hx, hy in headers:
        h_text = small_font.render(label, True, color)
        screen.blit(h_text, (hx, hy))

    for key, row_rect, checkbox_rect in rows:
        is_on = key in enabled_roles
        info = roles.ROLES[key]
        row_bg = (40, 45, 55) if not is_on else (35, 60, 45)
        pygame.draw.rect(screen, row_bg, row_rect, border_radius=6)
        if key == role_detail_key:
            pygame.draw.rect(screen, (120, 140, 230), row_rect, 2, border_radius=6)

        thumb = get_role_image(key, ROLE_THUMB_SIZE)
        tx = row_rect.x + 6
        if thumb:
            screen.blit(thumb, (tx, row_rect.y + (row_rect.height - ROLE_THUMB_SIZE) // 2))
            name_x = tx + ROLE_THUMB_SIZE + 10
        else:
            name_x = tx

        name_text = chat_font.render(info["name"], True, (255, 255, 255))
        screen.blit(name_text, (name_x, row_rect.y + 2))
        # Kurzbeschreibung direkt in der Zeile, damit der Host weiss was die Rolle kann
        desc_short = info["desc"]
        while desc_short and chat_font.size(desc_short)[0] > (checkbox_rect.x - name_x - 10):
            desc_short = desc_short[:-2]
        if desc_short != info["desc"]:
            desc_short = desc_short.rstrip() + "..."
        desc_text = proximity_font.render(desc_short, True, (180, 185, 195))
        screen.blit(desc_text, (name_x, row_rect.y + 22))

        box_color = (100, 255, 130) if is_on else (90, 90, 90)
        pygame.draw.rect(screen, box_color, checkbox_rect, border_radius=4)
        pygame.draw.rect(screen, (255, 255, 255), checkbox_rect, 2, border_radius=4)
        if is_on:
            pygame.draw.line(screen, (0, 0, 0), (checkbox_rect.x + 5, checkbox_rect.centery), (checkbox_rect.centerx - 1, checkbox_rect.bottom - 6), 3)
            pygame.draw.line(screen, (0, 0, 0), (checkbox_rect.centerx - 1, checkbox_rect.bottom - 6), (checkbox_rect.right - 4, checkbox_rect.y + 5), 3)

    pygame.draw.rect(screen, (200, 60, 60), back_rect, border_radius=10)
    back_text = small_font.render("ZURÜCK", True, (255, 255, 255))
    screen.blit(back_text, (back_rect.centerx - back_text.get_width() // 2, back_rect.centery - back_text.get_height() // 2))

def wrap_text_render(text, font, color, max_width):
    words = text.split(" ")
    lines = []
    current = ""
    for w in words:
        trial = (current + " " + w).strip()
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return [font.render(line, True, color) for line in lines]

def team_label():
    """NEU: Kurzer Text + Farbe fuer die Seite, auf der man steht."""
    if my_player.role == "Imposter":
        return "Feindlich - Imposter", (255, 90, 90)
    if my_player.role == "Independent":
        return "Eigenständig - du gewinnst allein", (255, 210, 90)
    return "Freundlich - Besatzung", (100, 255, 130)

def imposter_teammate_names():
    """NEU: Namen der anderen Imposter (leer, wenn man kein Imposter ist)."""
    return [player_names.get(pid, f"Spieler {pid}") for pid in my_imposter_teammates]

current_buttons = []   # NEU: zuletzt gezeichnete Aktions-Buttons (fuer Mausklicks)

def get_role_info_button_rect():
    """Der Rollen-Button ist jetzt Teil der Button-Leiste unten rechts (Taste R)."""
    for spec in current_buttons:
        if spec.key_code == pygame.K_r:
            return spec.rect
    return pygame.Rect(0, 0, 0, 0)

def team_color():
    if my_player.role == "Imposter":
        return (255, 90, 90)
    if my_player.role == "Independent":
        return (255, 210, 90)
    return (100, 220, 255)

def _cd_spec(key, key_label, label, icon, color, enabled, cd=0.0, cd_total=1.0, badge="", image=None):
    frac = (cd / cd_total) if (cd_total > 0 and cd > 0) else 0.0
    return hud.ButtonSpec(key, key_label, label, icon, color, enabled=enabled, cooldown=frac,
                          cooldown_text=(str(int(math.ceil(cd))) if cd > 0 else ""), badge=badge, image=image)

def role_ability_spec():
    """NEU: Button fuer die Rollen-Faehigkeit (Taste F) - Beschriftung, Cooldown und Zaehler
    spiegeln exakt die Bedingungen des F-Handlers in der Hauptschleife wider."""
    rk = my_player.role_key
    if rk is None:
        return None
    alive = not my_player.is_dead
    img = get_role_image(rk, ROLE_REVEAL_SIZE)
    my_center = my_player.rect.center
    K = pygame.K_f
    col = hud.COL_ABILITY

    def near_point(points, rng):
        return any(math.hypot(my_center[0] - pt.centerx, my_center[1] - pt.centery) < rng for pt in points)

    if rk == "monika":
        return _cd_spec(K, "F", "FLAGGE", "flag", col, alive and monika_flag_cooldown <= 0,
                        monika_flag_cooldown, MONIKA_FLAG_COOLDOWN, image=img)
    if rk == "stroblpeter":
        if stroblpeter_marked_id is None:
            tgt = find_nearest_player(my_center, other_players, STROBLPETER_MARK_RANGE, dead_players,
                                      exclude_ids=my_imposter_teammates)
            return _cd_spec(K, "F", "MARKIEREN", "star", col, alive and tgt is not None, image=img)
        if not stroblpeter_ready_to_strike:
            return _cd_spec(K, "F", "MARKIERT", "star", col, False, max(0.0, stroblpeter_mark_timer),
                            STROBLPETER_MARK_DELAY, image=img)
        ok = stroblpeter_marked_id in other_players and stroblpeter_marked_id not in dead_players
        return _cd_spec(K, "F", "ZUSCHLAGEN", "kill", hud.COL_KILL, alive and ok, image=img)
    if rk == "evelyn":
        # Evelyn waehlt den Raum auf der Karte aus -> Button oeffnet die Karte (M)
        return _cd_spec(pygame.K_m, "M", "FENSTER", "map", col, alive and evelyn_cooldown_remaining <= 0,
                        evelyn_cooldown_remaining, EVELYN_COOLDOWN, image=img)
    if rk == "laurin":
        near = any(math.hypot(my_center[0] - b["rect"].centerx, my_center[1] - b["rect"].centery) < LAURIN_SABOTAGE_RANGE
                   for b in task_buttons)
        return _cd_spec(K, "F", "SABOTAGE", "star", col, alive and laurin_uses_left > 0 and near,
                        badge=str(laurin_uses_left), image=img)
    if rk == "kaliyoga":
        return _cd_spec(K, "F", "YOGA-MEETING", "emergency", col, alive and not kaliyoga_bonus_used,
                        badge="0" if kaliyoga_bonus_used else "1", image=img)
    if rk == "david":
        tgt = find_nearest_player(my_center, other_players, DAVID_MARK_RANGE, dead_players)
        return _cd_spec(K, "F", "VERWÜRFELN", "star", col, alive and tgt is not None, image=img)
    if rk == "noah":
        return _cd_spec(K, "F", "FALLE", "star", col, alive and noah_trap_cooldown <= 0, noah_trap_cooldown,
                        NOAH_TRAP_COOLDOWN, badge=f"{len(noah_traps)}/{NOAH_TRAP_LIMIT}", image=img)
    if rk == "vogelscheicher":
        remaining = vogelscheicher_invisible_until - time.time()
        return _cd_spec(K, "F", "ATTRAPPE" if remaining <= 0 else "UNSICHTBAR", "star", col, alive,
                        max(0.0, remaining), VOGELSCHEICHER_INVISIBLE_DURATION, image=img)
    if rk == "pleschbergsteiger":
        tgt = find_nearest_player(my_center, other_players, PLESCHBERGSTEIGER_RANGE, dead_players, want_dead=True)
        return _cd_spec(K, "F", "WIEDERBELEBEN", "star", col, pleschbergsteiger_uses_left > 0 and tgt is not None,
                        badge=str(pleschbergsteiger_uses_left), image=img)
    if rk == "yoshi":
        if near_point(yoshi_find_points, YOSHI_FIND_RANGE):
            return _cd_spec(K, "F", "EINSAMMELN", "star", col, alive, badge=f"{yoshi_finds}/{YOSHI_FIND_LIMIT}", image=img)
        tgt = find_nearest_player(my_center, other_players, DAVID_MARK_RANGE, dead_players)
        return _cd_spec(K, "F", "AUFDECKEN", "star", col, alive and yoshi_reveals_left > 0 and tgt is not None,
                        badge=str(yoshi_reveals_left), image=img)
    if rk == "tappeihnachtsmann":
        return _cd_spec(K, "F", "GESCHENK", "star", col, alive and near_point(tappeihnachtsmann_find_points, TAPPEIHNACHTSMANN_FIND_RANGE),
                        badge=str(len(tappeihnachtsmann_find_points)), image=img)
    if rk == "raphi":
        return _cd_spec(K, "F", "SAMMELN", "star", col, near_point(raphi_collect_points, RAPHI_COLLECT_RANGE),
                        badge=f"{raphi_collected}/10", image=img)
    if rk == "ramona":
        forge_remaining = RAMONA_FORGE_COOLDOWN_CLIENT - (time.time() - ramona_last_forge)
        tgt = find_nearest_player(my_center, other_players, RAMONA_FORGE_RANGE, dead_players)
        return _cd_spec(K, "F", "FÄLSCHEN", "star", hud.COL_GOLD, alive and forge_remaining <= 0 and tgt is not None,
                        max(0.0, forge_remaining), RAMONA_FORGE_COOLDOWN_CLIENT, image=img)
    return None  # passive Rollen (z.B. Orakel, Felix, Martin) haben keinen Faehigkeits-Button

def build_action_buttons():
    """NEU: Welche Buttons gerade sichtbar sind - abhaengig von Rolle, Leben/Tod und Umgebung."""
    specs = []
    if state != "game" or not game_started or my_id is None:
        return specs
    alive = not my_player.is_dead
    rk = my_player.role_key
    near_body = alive and nearest_body_id() is not None
    at_button = alive and at_emergency_button()

    # E-Kontext: Melden > Notfallknopf > Aufgabe (dieselbe Reihenfolge wie der E-Handler)
    if near_body:
        context = hud.ButtonSpec(pygame.K_e, "E", "MELDEN", "report", hud.COL_REPORT, enabled=True)
    elif at_button:
        if my_emergency_used:
            # NEU: jeder Spieler hat nur EIN Notfall-Meeting pro Runde
            context = hud.ButtonSpec(pygame.K_e, "E", "VERBRAUCHT", "emergency", hud.COL_EMERGENCY, enabled=False)
        else:
            context = _cd_spec(pygame.K_e, "E", "NOTFALL", "emergency", hud.COL_EMERGENCY, meeting_cooldown <= 0,
                               meeting_cooldown, max(1.0, float(game_settings["cooldown"])))
    elif my_player.role == "Crewmate" and rk != "raphi":
        btn = nearest_task_button()
        usable = btn is not None and btn["task_index"] not in my_player.my_completed_tasks
        context = hud.ButtonSpec(pygame.K_e, "E", "BENUTZEN", "use", hud.COL_USE, enabled=usable)
    elif alive:
        context = hud.ButtonSpec(pygame.K_e, "E", "MELDEN", "report", hud.COL_REPORT, enabled=False)
    else:
        context = None

    if my_player.role == "Imposter" and alive:
        kill_total = KILL_COOLDOWN_MARTIN if rk == "martin" else KILL_COOLDOWN_DEFAULT
        target = current_kill_target()
        specs.append(_cd_spec(pygame.K_e, "E", "TÖTEN", "kill", hud.COL_KILL,
                              target is not None and kill_cooldown_remaining <= 0 and not near_body and not at_button,
                              kill_cooldown_remaining, kill_total))
        if context is not None:
            specs.append(context)
        on_vent = my_player.is_venting or get_current_vent(my_player, vents) is not None
        specs.append(hud.ButtonSpec(pygame.K_SPACE, "LEER", "RAUS" if my_player.is_venting else "VENT", "vent",
                                    hud.COL_VENT, enabled=on_vent, active=my_player.is_venting))
    elif context is not None:
        specs.append(context)

    ability = role_ability_spec()
    if ability is not None:
        specs.append(ability)
    if rk == "monika":
        specs.append(_cd_spec(pygame.K_g, "G", "REISEN", "flag", hud.COL_GOLD,
                              alive and monika_flag_pos is not None and monika_teleport_cooldown <= 0,
                              monika_teleport_cooldown if monika_flag_pos is not None else 0.0, MONIKA_TELEPORT_COOLDOWN))

    specs.append(hud.ButtonSpec(pygame.K_m, "M", "KARTE", "map", hud.COL_NEUTRAL, small=True, active=show_minimap))
    specs.append(hud.ButtonSpec(pygame.K_r, "R", "ROLLE", "role", team_color(), small=True, active=show_role_info,
                                image=get_role_image(my_player.role_key, ROLE_THUMB_SIZE) if my_player.role_key else None))
    return specs

def draw_role_info_panel():
    """NEU: Zeigt Rollenbild, Name, Seite und Beschreibung - jederzeit im Spiel
    ueber den Button am Bildschirmrand (oder Taste R) aufrufbar."""
    panel_w = min(820, WIDTH - 120)
    panel_h = min(560, HEIGHT - 120)
    panel = pygame.Rect((WIDTH - panel_w) // 2, (HEIGHT - panel_h) // 2, panel_w, panel_h)

    fx.blit_alpha(screen, fx.dim_surface((WIDTH, HEIGHT)), (0, 0), 170)

    pygame.draw.rect(screen, (18, 20, 28), panel, border_radius=14)
    pygame.draw.rect(screen, team_color(), panel, 3, border_radius=14)

    y = panel.y + 24
    title = small_font.render("DEINE ROLLE", True, (200, 210, 255))
    screen.blit(title, (panel.centerx - title.get_width() // 2, y))
    y += title.get_height() + 12

    if my_player.role_image:
        screen.blit(my_player.role_image, (panel.centerx - ROLE_REVEAL_SIZE // 2, y))
        y += ROLE_REVEAL_SIZE + 12

    name_txt = menu_font.render(my_player.role_display_name, True, (255, 255, 255))
    screen.blit(name_txt, (panel.centerx - name_txt.get_width() // 2, y))
    y += name_txt.get_height() + 6

    tl_text, tl_color = team_label()
    team_txt = small_font.render(tl_text, True, tl_color)
    screen.blit(team_txt, (panel.centerx - team_txt.get_width() // 2, y))
    y += team_txt.get_height() + 12

    for line_surf in wrap_text_render(my_player.role_desc, chat_font, (230, 230, 235), panel_w - 60):
        screen.blit(line_surf, (panel.centerx - line_surf.get_width() // 2, y))
        y += line_surf.get_height() + 3

    mates = imposter_teammate_names()
    if mates:
        y += 10
        mate_txt = chat_font.render("Deine Mit-Imposter: " + ", ".join(mates), True, (255, 120, 120))
        screen.blit(mate_txt, (panel.centerx - mate_txt.get_width() // 2, y))
        y += mate_txt.get_height() + 2
        hint_txt = proximity_font.render("Ihr könnt euch gegenseitig nicht töten.", True, (200, 140, 140))
        screen.blit(hint_txt, (panel.centerx - hint_txt.get_width() // 2, y))

    close_txt = proximity_font.render("R oder Klick auf den ROLLE-Button schließt dieses Fenster", True, (150, 155, 170))
    screen.blit(close_txt, (panel.centerx - close_txt.get_width() // 2, panel.bottom - 26))

def _panel_text(text, size, color, bold=False):
    return fx.font(size, bold).render(text, True, color)

_left_panel_cache = {"key": None, "surf": None}

def left_panel_model():
    """Alles, was die linke Leiste anzeigt, als Daten. Aendert sich davon nichts, wird das fertige
    Bild der Leiste wiederverwendet (NEU: spart im Browser mehrere Millisekunden pro Bild)."""
    rk = my_player.role_key
    lines = []   # (text, farbe, symbol) symbol: "done", "open", None
    if my_player.role == "Crewmate":
        header = "DEINE AUFGABEN"
        if rk == "raphi":
            lines.append((f"Pfandflaschen gesammelt: {raphi_collected}/10", (255, 255, 255), "done" if raphi_collected >= 10 else "open"))
        else:
            for idx in my_player.my_assigned_tasks:
                name = TASK_TEMPLATES[idx]["name"] if idx < len(TASK_TEMPLATES) else f"Aufgabe {idx}"
                done = idx in my_player.my_completed_tasks
                lines.append((name, (140, 220, 160) if done else (240, 240, 245), "done" if done else "open"))
        if rk == "felix":
            lines.append(("Deine Aufgaben zählen nicht mit.", (255, 180, 120), None))
    elif my_player.role == "Imposter":
        header = "DEIN AUFTRAG"
        lines.append(("Töte die Besatzung und bleib unentdeckt.", (255, 200, 200), None))
        if not my_player.is_dead:
            cd_txt = "Kill bereit!" if kill_cooldown_remaining <= 0 else f"Kill wieder in {kill_cooldown_remaining:.0f}s"
            lines.append((cd_txt, (255, 120, 120), None))
        mates = imposter_teammate_names()
        if mates:
            lines.append(("Mit-Imposter: " + ", ".join(mates), (255, 120, 120), None))
    else:
        header = "DEIN AUFTRAG"
        lines.append(("Verfolge dein eigenes Ziel.", (255, 220, 150), None))

    # Rollen-spezifische Zusatzinfos (vorher in draw_ability_hud als Textzeilen)
    info_col = (200, 205, 220)
    if rk == "monika" and monika_flag_pos is not None:
        lines.append(("Flagge gesetzt - G reist dorthin.", info_col, None))
    elif rk == "stroblpeter" and stroblpeter_marked_id is not None:
        lines.append((f"Markiert: {player_names.get(stroblpeter_marked_id, '?')}", info_col, None))
    elif rk == "evelyn":
        lines.append(("Karte (M) öffnen und Fensterraum anklicken.", info_col, None))
    elif rk == "david" and david_marked_id is not None:
        lines.append((f"Verwürfelt: {player_names.get(david_marked_id, '?')}", info_col, None))
    elif rk == "ramona":
        if ramona_others_rights:
            rights_str = ", ".join(f"{player_names.get(pid, '?')}: {v}" for pid, v in ramona_others_rights.items())
            lines.append(("Rechte - " + rights_str, (255, 210, 90), None))
        if ramona_stand_timer > 0:
            lines.append((f"Am Regal: {ramona_stand_timer:.1f}/{RAMONA_WIN_STAND_TIME:.0f}s", (100, 255, 130), None))

    status = "GEIST" if my_player.is_dead else ("IM VENT" if my_player.is_venting else "")
    return (WIDTH, HEIGHT, my_id, rk, my_player.role_display_name, my_player.role, my_player.is_dead, status,
            global_task_progress, global_task_max, header, tuple(lines))

def draw_left_panel():
    """NEU: Linke Leiste - Rollenkarte, Gesamtfortschritt, eigene Aufgaben/Auftrag, Rollen-Status
    und eine kurze Steuerungs-Hilfe. Ersetzt die alten Textzeilen oben links."""
    model = left_panel_model()
    if model != _left_panel_cache["key"]:
        left, _right = hud.side_panel_rects(WIDTH, HEIGHT)
        s = HEIGHT / 810.0
        pad = int(16 * s)
        w = max(int(230 * s), left.width - 2 * pad)
        if w + 2 * pad <= left.width:
            # liegt komplett auf dem schwarzen Rand -> deckend zeichnen (viel schneller als Alpha-Mischen)
            surf = pygame.Surface((w + 2 * pad, HEIGHT)).convert()
            surf.fill((0, 0, 0))
        else:
            surf = pygame.Surface((w + 2 * pad, HEIGHT), pygame.SRCALPHA)
        _render_left_panel(surf, model)
        _left_panel_cache["key"] = model
        _left_panel_cache["surf"] = surf
    screen.blit(_left_panel_cache["surf"], (0, 0))

def _render_left_panel(target, model):
    (_w, _h, _id, rk, display_name, team_role, is_dead, status, progress, progress_max, header, lines) = model
    left, _right = hud.side_panel_rects(WIDTH, HEIGHT)
    s = HEIGHT / 810.0
    pad = int(16 * s)
    gap = int(10 * s)
    w = max(int(230 * s), left.width - 2 * pad)
    x, y = pad, pad

    # --- Rollenkarte ---
    card_h = int(92 * s)
    card = pygame.Rect(x, y, w, card_h)
    hud.draw_panel_card(target, card, border=team_color())
    thumb_size = int(card_h * 0.72)
    thumb = get_role_image(rk, thumb_size) if rk else None
    if thumb is None:
        thumb = fx.scale_sprite(player_images.get(my_id % len(player_images)), thumb_size)
    if thumb is not None:
        if is_dead:
            thumb = thumb.copy()
            thumb.set_alpha(120)
        target.blit(thumb, (card.x + int(10 * s), card.centery - thumb.get_height() // 2))
    tx = card.x + int(18 * s) + thumb_size
    name_s = _panel_text(display_name, int(21 * s), (255, 255, 255), True)
    if name_s.get_width() > card.right - tx - 8:
        name_s = pygame.transform.smoothscale(name_s, (card.right - tx - 8, name_s.get_height()))
    target.blit(name_s, (tx, card.y + int(14 * s)))
    team_txt = {"Imposter": "Imposter", "Independent": "Eigenständig"}.get(team_role, "Besatzung")
    target.blit(_panel_text(team_txt, int(15 * s), team_color(), True), (tx, card.y + int(42 * s)))
    if status:
        tag = _panel_text(status, int(13 * s), (20, 20, 25), True)
        tr = pygame.Rect(tx, card.y + int(64 * s), tag.get_width() + 12, tag.get_height() + 2)
        pygame.draw.rect(target, (255, 120, 120) if is_dead else (90, 220, 120), tr, border_radius=6)
        target.blit(tag, (tr.x + 6, tr.y + 1))
    y = card.bottom + gap

    # --- Gesamtfortschritt ---
    bar = pygame.Rect(x, y, w, int(26 * s))
    hud.draw_progress_bar(target, bar, progress, progress_max, f"Aufgaben gesamt  {progress}/{progress_max}")
    y = bar.bottom + gap

    # --- Aufgaben / Auftrag + Rollen-Status (mit Zeilenumbruch) ---
    line_h = int(21 * s)
    f_line = fx.font(int(15 * s), False)
    wrapped = []
    for text, color, sym in lines:
        max_w = w - int(40 * s)
        words, cur = text.split(" "), ""
        first = True
        for word in words:
            trial = (cur + " " + word).strip()
            if f_line.size(trial)[0] <= max_w:
                cur = trial
            else:
                if cur:
                    wrapped.append((cur, color, sym if first else None))
                    first = False
                cur = word
        if cur:
            wrapped.append((cur, color, sym if first else None))
    controls_h = int(78 * s)
    max_h = HEIGHT - y - controls_h - 2 * gap
    body_h = min(max_h, int(38 * s) + len(wrapped) * line_h + int(8 * s))
    tcard = pygame.Rect(x, y, w, max(int(60 * s), body_h))
    hud.draw_panel_card(target, tcard)
    target.blit(_panel_text(header, int(14 * s), (170, 180, 210), True), (tcard.x + int(12 * s), tcard.y + int(10 * s)))
    ly = tcard.y + int(34 * s)
    for text, color, sym in wrapped:
        if ly + line_h > tcard.bottom - 4:
            break
        bx = tcard.x + int(14 * s)
        box = pygame.Rect(bx, ly + int(3 * s), int(13 * s), int(13 * s))
        if sym == "done":
            pygame.draw.rect(target, (40, 200, 110), box, border_radius=3)
            pygame.draw.line(target, (255, 255, 255), (box.x + 2, box.centery), (box.centerx - 1, box.bottom - 3), 2)
            pygame.draw.line(target, (255, 255, 255), (box.centerx - 1, box.bottom - 3), (box.right - 2, box.y + 2), 2)
        elif sym == "open":
            pygame.draw.rect(target, (255, 215, 60), box, 2, border_radius=3)
        target.blit(f_line.render(text, True, color), (bx + int(20 * s), ly))
        ly += line_h

    # --- Steuerung (kurz) ---
    ctrl = pygame.Rect(x, HEIGHT - pad - controls_h, w, controls_h)
    hud.draw_panel_card(target, ctrl, border=(55, 60, 80))
    f_small = fx.font(int(13 * s), False)
    hints = ["WASD laufen  ·  E benutzen/töten  ·  F Fähigkeit",
             "Leertaste Vent  ·  M Karte  ·  R Rolle",
             "Q Aufgabe/Karte schließen  ·  Buttons auch klickbar"]
    for i, h_txt in enumerate(hints):
        target.blit(f_small.render(h_txt, True, (175, 180, 198)), (ctrl.x + int(12 * s), ctrl.y + int(10 * s) + i * int(21 * s)))

def draw_game_hud():
    """NEU: komplettes Spiel-HUD (linke Leiste, Aktions-Buttons, Banner). Rein lesend."""
    global current_buttons
    rk = my_player.role_key
    draw_left_panel()

    if task_manager.active_task is None and not meeting_active:
        current_buttons = hud.layout_buttons(build_action_buttons(), WIDTH, HEIGHT)
        hud.draw_buttons(screen, current_buttons)
    else:
        current_buttons = []

    # Globale Banner oben mittig (fuer alle Spieler sichtbar)
    banner_y = 12
    if already_done_timer > 0 and task_manager.active_task is None:
        banner_y = hud.draw_banner(screen, "Du hast diese Aufgabe bereits erledigt!", banner_y, (255, 80, 80)) + 8
    if immortal_banner_timer > 0:
        banner_y = hud.draw_banner(screen, f"UNSTERBLICHKEIT AKTIV  ({immortal_banner_timer:.0f}s)", banner_y, (255, 230, 80)) + 8
    if time.time() < window_hazard_until:
        banner_y = hud.draw_banner(screen, "GEFAHR: Fenster offen - nicht in Fensterräumen aufhalten!", banner_y, (255, 90, 90)) + 8
    if task_reset_banner_timer > 0:
        banner_y = hud.draw_banner(screen, f"Aufgabe sabotiert: {task_reset_banner_name} muss neu erledigt werden!",
                                   banner_y, (255, 180, 90)) + 8
    if rk == "yoshi" and yoshi_reveal_result is not None and yoshi_reveal_timer > 0:
        target_id, team_str, role_name = yoshi_reveal_result
        banner_y = hud.draw_banner(screen, f"{player_names.get(target_id, '?')} ist: {role_name} ({team_str})",
                                   banner_y, (255, 255, 100)) + 8

    # Poeschl&Froeschl: Pfeil rund um die eigene Figur zeigt zur naechsten Leiche
    if rk == "poeschl_froeschl":
        my_center = my_player.rect.center
        nearest, nearest_dist = None, None
        for d_id, (dx, dy, _w) in dead_bodies.items():
            body_center = (dx + PLAYER_SIZE // 2, dy + PLAYER_SIZE // 2)
            dist = math.hypot(my_center[0] - body_center[0], my_center[1] - body_center[1])
            if nearest_dist is None or dist < nearest_dist:
                nearest_dist, nearest = dist, body_center
        if nearest is not None:
            angle = math.atan2(nearest[1] - my_center[1], nearest[0] - my_center[0])
            s = HEIGHT / 810.0
            ax, ay = WIDTH // 2 + math.cos(angle) * 70 * s, HEIGHT // 2 + math.sin(angle) * 70 * s
            tip = (ax + math.cos(angle) * 16 * s, ay + math.sin(angle) * 16 * s)
            l = (ax + math.cos(angle + 2.5) * 12 * s, ay + math.sin(angle + 2.5) * 12 * s)
            r = (ax + math.cos(angle - 2.5) * 12 * s, ay + math.sin(angle - 2.5) * 12 * s)
            pygame.draw.polygon(screen, (255, 200, 0), [tip, l, r])
            pygame.draw.polygon(screen, (60, 40, 0), [tip, l, r], 2)

def get_lobby_layout():
    """NEU: Alle Lobby-Knoepfe an einer Stelle (Zeichnen UND Klicken benutzen dieselben Rechtecke)."""
    return {
        "start": pygame.Rect(WIDTH - 240, HEIGHT - 100, 200, 60),
        "roles": pygame.Rect(40, HEIGHT - 100, 200, 60),
        "settings": pygame.Rect(40, HEIGHT - 170, 200, 60),
        "assign": pygame.Rect(40, HEIGHT - 240, 200, 60),
        "minus": pygame.Rect(WIDTH // 2 - 130, HEIGHT - 155, 40, 40),   # FIX: mehr Abstand zum Text
        "plus": pygame.Rect(WIDTH // 2 + 90, HEIGHT - 155, 40, 40),
    }

def draw_menu_button(rect, label, color, text_color=(255, 255, 255), font_obj=None):
    pygame.draw.rect(screen, color, rect, border_radius=10)
    txt = (font_obj or small_font).render(label, True, text_color)
    if txt.get_width() > rect.width - 16:
        txt = pygame.transform.smoothscale(txt, (rect.width - 16, txt.get_height()))
    screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))

def settings_summary():
    return (f"Notfall-Cooldown {game_settings['cooldown']}s  ·  Diskussion {game_settings['discussion']}s"
            f"  ·  Abstimmung {game_settings['vote']}s  ·  1 Notfall-Meeting pro Spieler")

SETTING_ROWS = [
    ("cooldown", "Notfall-Cooldown", "nach Spielstart und nach jedem Meeting"),
    ("discussion", "Diskussionszeit", "nur Chat, noch keine Abstimmung"),
    ("vote", "Abstimmungszeit", "Zeit zum Abstimmen"),
]

def get_settings_layout():
    rows = []
    y0 = 220
    for i, (key, _label, _sub) in enumerate(SETTING_ROWS):
        row = pygame.Rect(WIDTH // 2 - 420, y0 + i * 110, 840, 90)
        minus = pygame.Rect(row.right - 250, row.centery - 26, 52, 52)
        plus = pygame.Rect(row.right - 70, row.centery - 26, 52, 52)
        rows.append((key, row, minus, plus))
    back = pygame.Rect(40, HEIGHT - 100, 200, 60)
    return rows, back

def draw_settings():
    screen.fill((18, 18, 26))
    is_host = my_id == host_id
    title = menu_font.render("EINSTELLUNGEN", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))
    sub = chat_font.render("Gilt für die nächste Runde." + ("" if is_host else "  Nur der Host kann die Werte ändern."),
                           True, (170, 175, 190))
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 100))
    rows, back = get_settings_layout()
    for key, row, minus, plus in rows:
        label = next(l for k, l, _s in SETTING_ROWS if k == key)
        subtitle = next(sb for k, _l, sb in SETTING_ROWS if k == key)
        hud.draw_panel_card(screen, row)
        screen.blit(fx.font(26).render(label, True, (255, 255, 255)), (row.x + 24, row.y + 14))
        screen.blit(fx.font(16, False).render(subtitle, True, (170, 175, 190)), (row.x + 24, row.y + 52))
        value = fx.font(32).render(f"{game_settings[key]} s", True, (255, 215, 70))
        screen.blit(value, (minus.right + (plus.x - minus.right) // 2 - value.get_width() // 2, row.centery - value.get_height() // 2))
        if is_host:
            draw_menu_button(minus, "-", (90, 95, 110))
            draw_menu_button(plus, "+", (90, 95, 110))
    info = chat_font.render("Jeder Spieler kann den Notfallknopf nur EINMAL pro Runde drücken. Leichen melden geht immer.",
                            True, (200, 205, 220))
    screen.blit(info, (WIDTH // 2 - info.get_width() // 2, rows[-1][1].bottom + 30))
    draw_menu_button(back, "ZURÜCK", (200, 60, 60))

def get_assign_layout():
    ids = sorted(player_names.keys())
    row_h = max(34, min(44, (HEIGHT - 300) // max(1, len(ids))))
    rows = []
    for i, pid in enumerate(ids):
        row = pygame.Rect(WIDTH // 2 - 420, 170 + i * row_h, 840, row_h - 6)
        prev_b = pygame.Rect(row.right - 330, row.y + 3, 40, row.height - 6)
        next_b = pygame.Rect(row.right - 50, row.y + 3, 40, row.height - 6)
        rows.append((pid, row, prev_b, next_b))
    back = pygame.Rect(40, HEIGHT - 100, 200, 60)
    reset = pygame.Rect(260, HEIGHT - 100, 260, 60)
    return rows, back, reset

def draw_role_assign():
    screen.fill((20, 14, 26))
    title = menu_font.render("ROLLEN ZUTEILEN (CHEAT)", True, (255, 150, 220))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))
    ok, msg = current_role_setup_status()
    for i, (text, col) in enumerate([
            ("Nur du als Host siehst das. Fest zugeteilte Rollen werden in der nächsten Runde garantiert vergeben.", (190, 180, 200)),
            (msg, (100, 255, 130) if ok else (255, 90, 90))]):
        t = chat_font.render(text, True, col)
        screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 100 + i * 26))
    rows, back, reset = get_assign_layout()
    for pid, row, prev_b, next_b in rows:
        code = fixed_role_map.get(pid, roles.FIXED_NONE)
        team = roles.fixed_team(code)
        col = {roles.TEAM_IMPOSTOR: (255, 90, 90), roles.TEAM_CREW: (100, 220, 255),
               roles.TEAM_INDEPENDENT: (255, 210, 90)}.get(team, (170, 175, 190))
        pygame.draw.rect(screen, (40, 36, 52) if code == roles.FIXED_NONE else (55, 40, 60), row, border_radius=8)
        img = player_images.get(pid % len(player_images))
        if img:
            screen.blit(img, (row.x + 12, row.centery - img.get_height() // 2))
        screen.blit(chat_font.render(player_names.get(pid, f"Spieler {pid}"), True, (255, 255, 255)),
                    (row.x + 40, row.centery - 11))
        lbl = chat_font.render(roles.fixed_label(code), True, col)
        screen.blit(lbl, (prev_b.right + (next_b.x - prev_b.right) // 2 - lbl.get_width() // 2, row.centery - lbl.get_height() // 2))
        draw_menu_button(prev_b, "<", (80, 70, 95), font_obj=chat_font)
        draw_menu_button(next_b, ">", (80, 70, 95), font_obj=chat_font)
    draw_menu_button(back, "ZURÜCK", (200, 60, 60))
    draw_menu_button(reset, "ALLE AUF ZUFALL", (90, 80, 110))

def cycle_fixed_role(pid, step):
    options = roles.FIXED_OPTIONS
    current = fixed_role_map.get(pid, roles.FIXED_NONE)
    idx = options.index(current) if current in options else 0
    new_code = options[(idx + step) % len(options)]
    try: sock.sendall(struct.pack("!BBB", 18, pid, new_code))
    except: pass

def send_settings(changed_key=None, delta=0):
    values = dict(game_settings)
    if changed_key:
        lo, hi = SETTING_LIMITS[changed_key]
        values[changed_key] = max(lo, min(hi, values[changed_key] + delta))
    try: sock.sendall(struct.pack("!BBBB", 16, values["cooldown"], values["discussion"], values["vote"]))
    except: pass

def draw_lobby():
    camera_x = my_player.rect.x - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)
    camera_y = my_player.rect.y - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)

    internal_surface.fill((20, 20, 30))
    internal_surface.blit(lobby_combined, (-camera_x, -camera_y))

    for p_id, pos in other_players.items():
        enemy_img = player_images.get(p_id % len(player_images))
        if enemy_img:
            if player_facing_left.get(p_id):
                enemy_img = pygame.transform.flip(enemy_img, True, False)
            internal_surface.blit(enemy_img, (pos[0] - camera_x, pos[1] - camera_y + get_walk_offset(p_id)))
            e_name = player_names.get(p_id, f"Player {p_id}")
            name_text = fx.render_cached(name_font, e_name, (255, 255, 255))
            internal_surface.blit(name_text, ((pos[0] - camera_x) + (PLAYER_SIZE // 2) - (name_text.get_width() // 2), (pos[1] - camera_y) - 16))

    my_player.draw(internal_surface, camera_x, camera_y)
    my_name = player_names.get(my_id, "Ich")
    my_name_text = fx.render_cached(name_font, my_name, (255, 255, 255))
    internal_surface.blit(my_name_text, ((my_player.rect.x - camera_x) + (PLAYER_SIZE // 2) - (my_name_text.get_width() // 2), (my_player.rect.y - camera_y) - 16))

    scaled_size = min(WIDTH, HEIGHT)
    scaled_surface = pygame.transform.scale(internal_surface, (scaled_size, scaled_size))
    screen.fill((0, 0, 0))
    world_pos = ((WIDTH - scaled_size) // 2, (HEIGHT - scaled_size) // 2)
    screen.blit(scaled_surface, world_pos)
    web_bridge.set_world(internal_surface, scaled_surface, (world_pos[0], world_pos[1], scaled_size))

    title = menu_font.render("LOBBY", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))
    # NEU: Im Web-Modus den Raum-Code gross anzeigen, damit andere einfach beitreten koennen
    if (WEB_MODE or BROWSER) and web_bridge.ROOM_CODE:
        code_lbl = small_font.render("RAUM-CODE", True, (170, 180, 210))
        code_txt = fx.font(52).render(web_bridge.ROOM_CODE, True, (255, 215, 70))
        screen.blit(code_lbl, (40, 40))
        screen.blit(code_txt, (40, 40 + code_lbl.get_height() + 4))
    # FIX: lag vorher genau unter dem ROLLEN-Button des Hosts
    screen.blit(small_font.render(f"Spieler online: {len(player_names)} / 15", True, (255, 255, 255)), (40, HEIGHT - 290))
    # NEU: aktuelle Meeting-Einstellungen fuer alle sichtbar
    summary = chat_font.render(settings_summary(), True, (190, 200, 230))
    screen.blit(summary, (WIDTH // 2 - summary.get_width() // 2, HEIGHT - 240))
    imp_text = small_font.render(f"Imposter: {imposter_count}", True, (255, 255, 255))
    screen.blit(imp_text, (WIDTH // 2 - imp_text.get_width() // 2, HEIGHT - 150))

    friendly_n, enemy_n, independent_n = role_counts(enabled_roles)
    roles_valid, roles_status_msg = current_role_setup_status()
    rc_color = (100, 255, 130) if roles_valid else (255, 90, 90)
    if enabled_roles:
        rc_text = small_font.render(
            f"Rollen aktiv: {friendly_n} freundlich / {enemy_n} feindlich / {independent_n} eigenständig",
            True, rc_color)
        screen.blit(rc_text, (WIDTH // 2 - rc_text.get_width() // 2, HEIGHT - 190))
    status_text = chat_font.render(roles_status_msg, True, rc_color)
    screen.blit(status_text, (WIDTH // 2 - status_text.get_width() // 2, HEIGHT - 215))

    lay = get_lobby_layout()
    # NEU: Rollen-Uebersicht und Einstellungen koennen ALLE ansehen (nur der Host kann aendern)
    draw_menu_button(lay["roles"], "ROLLEN" if my_id == host_id else "ROLLEN-INFO", (70, 100, 220))
    draw_menu_button(lay["settings"], "EINSTELLUNGEN", (60, 120, 150))
    if my_id == host_id:
        btn = lay["start"]
        btn_color = (0, 220, 100) if roles_valid else (90, 90, 90)
        # (roles_valid stammt aus current_role_setup_status() weiter oben)
        draw_menu_button(btn, "START", btn_color, (0, 0, 0) if roles_valid else (180, 180, 180))
        draw_menu_button(lay["assign"], "ZUTEILEN", (140, 70, 150))
        draw_menu_button(lay["minus"], "-", (100, 100, 100))
        draw_menu_button(lay["plus"], "+", (100, 100, 100))
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
    # FIX: vorher wurde ohne jede Meldung beendet - im Server-Log sieht man jetzt den Grund
    print("MAP LOAD ERROR:", e)
    pygame.quit()
    if WEB_MODE:
        web_bridge.notify_end("error", "Kartendateien fehlen auf dem Server.")
        web_bridge.hard_exit(1)
    sys.exit(1)

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

# NEU (Leistung): Boden, Waende und Objekte sind feste Ebenen - einmal zu EINEM deckenden Bild
# zusammenfuegen statt jedes Bild drei grosse Alpha-Ebenen zu mischen (gleiches Aussehen).
map_combined = pygame.Surface(floor_img.get_size()).convert()
map_combined.fill((40, 80, 40))
map_combined.blit(floor_img, (0, 0))
map_combined.blit(walls_img, (0, 0))
map_combined.blit(objects_img, (0, 0))
lobby_combined = pygame.Surface(lobby_bg.get_size()).convert()
lobby_combined.fill((20, 20, 30))
lobby_combined.blit(lobby_bg, (0, 0))

MAP_WIDTH_PX, MAP_HEIGHT_PX = floor_img.get_size()
MINIMAP_WIDTH = 800
# FIX: Karte an die Bildschirmhoehe anpassen (sonst ragt sie bei kleinen Aufloesungen aus dem Bild)
if MAP_HEIGHT_PX * (MINIMAP_WIDTH / MAP_WIDTH_PX) > HEIGHT - 40:
    MINIMAP_WIDTH = int((HEIGHT - 40) * MAP_WIDTH_PX / MAP_HEIGHT_PX)
MINIMAP_HEIGHT = int(MAP_HEIGHT_PX * (MINIMAP_WIDTH / MAP_WIDTH_PX))
minimap_bg = pygame.Surface((MINIMAP_WIDTH, MINIMAP_HEIGHT))
minimap_bg.blit(pygame.transform.scale(floor_img, (MINIMAP_WIDTH, MINIMAP_HEIGHT)), (0, 0))
minimap_bg.blit(pygame.transform.scale(walls_img, (MINIMAP_WIDTH, MINIMAP_HEIGHT)), (0, 0))

hitboxes, vents, plants, tasks_hitboxes, mapwalls, spawnpoints, emergency_hitboxes, window_zones, room_rects = load_hitboxes(os.path.join(base_path, "Hitboxes.json"))

# NEU: Ramonas Siegzone ("Regal beim Spawn") - es gibt keine eigene Karten-Zone dafür,
# daher wird der bereits vorhandene erste Spawnpunkt vergrößert wiederverwendet.
RAMONA_WIN_ZONE = spawnpoints[0].inflate(80, 80) if spawnpoints else pygame.Rect(0, 0, 50, 50)

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
meeting_chat_log = []
meeting_chat_input = ""
meeting_phase = MEETING_PHASE_NONE   # Diskussion -> Abstimmung, siehe Pakete 40/42/43
meeting_selected_target = None       # angeklickter, noch NICHT bestaetigter Stimmzettel
meeting_result_id = None             # wer beim letzten Meeting rausgeflogen ist (255 = niemand)
meeting_result_timer = 0.0           # wie lange das Ergebnis noch eingeblendet wird
running = True
show_minimap = False

# NEU: Animationen, Endbildschirm und Hilfszustand
death_anim = None              # fx.DeathAnimation - nur fuer das Opfer
eject_anim = None              # fx.EjectAnimation - Rauswurf + Rollen-Aufdeckung
end_screen = None              # fx.EndScreen - Sieg/Niederlage
pending_end_state = None       # Sieg-Paket kam, waehrend noch eine Animation lief
pending_vladimir_video = False # Anime-Intro startet erst nach der Todes-Animation
final_roles = {}               # pid -> (team_byte, role_id) aus Paket 83
intro_started_at = 0.0
intro_desc_cache = [None, []]   # (Beschreibung, Breite) -> fertig umgebrochene Textzeilen
task_aborted = False           # FIX: vorher erst beim ersten Task-Start definiert
active_task_idx = -1
TEAM_NAMES = {0: "Besatzung", 1: "Imposter", 2: "Eigenständig"}
TEAM_COLORS = {0: (100, 220, 255), 1: (255, 90, 90), 2: (255, 210, 90)}

def cutscene_active():
    """NEU: Waehrend Todes-/Rauswurf-Animation ist keine Steuerung moeglich."""
    return death_anim is not None or eject_anim is not None

def role_text_of(team_b, role_b):
    key = roles.role_key_of(role_b)
    if key is not None:
        return roles.ROLES[key]["name"]
    return {0: "Crewmate", 1: "Imposter", 2: "Eigenständig"}.get(team_b, "?")

def handle_ui_event(kind, data):
    """NEU: Vom Empfangs-Thread gemeldete Ereignisse im Haupt-Thread umsetzen."""
    global death_anim, eject_anim, end_screen, ghost_video, ghost_intro_timer
    if kind == "death":
        killer_id, flags, weapon_id = data
        cause, subtitle = fx.CAUSE_KILL, ""
        killer_img = player_images.get(killer_id % len(player_images)) if killer_id != NO_PLAYER else None
        if flags & DEATH_FLAG_TRAP:
            cause, subtitle, killer_img = fx.CAUSE_TRAP, "Du bist in eine Falle getreten!", None
        elif flags & DEATH_FLAG_WINDOW:
            cause, subtitle, killer_img = fx.CAUSE_WINDOW, "Du warst zu lange am offenen Fenster.", None
        elif flags & DEATH_FLAG_EXPLOSION:
            cause, subtitle = fx.CAUSE_EXPLOSION, "Du wurdest in die Luft gesprengt!"
        elif weapon_id == 1:
            cause = fx.CAUSE_SCISSORS
        if not subtitle:
            subtitle = ("Du bist jetzt ein Geist - erledige weiter deine Aufgaben."
                        if my_player.role == "Crewmate" else "Du bist jetzt ein Geist.")
        death_anim = fx.DeathAnimation((WIDTH, HEIGHT), player_images.get(my_id % len(player_images)),
                                       player_dead_images.get(my_id % len(player_dead_images)),
                                       killer_img, cause, item_images, subtitle)
        sfx.play("kill")
        sfx.set_loop("walking", False)
    elif kind == "eject":
        evicted_id, result_code, ev_team, ev_role, imps_left = data
        name = player_names.get(evicted_id, f"Spieler {evicted_id}")
        sprite = None
        if result_code == MEETING_RESULT_SKIPPED:
            lines, colors = ["Niemand wurde rausgeworfen.", "(Abstimmung übersprungen)"], [(255, 255, 255), (170, 175, 190)]
        elif result_code == MEETING_RESULT_TIE:
            lines, colors = ["Niemand wurde rausgeworfen.", "(Gleichstand)"], [(255, 255, 255), (170, 175, 190)]
        elif result_code == MEETING_RESULT_IMMORTAL:
            lines = [f"{name} sollte rausfliegen ...", "... aber die Unsterblichkeit hat gerettet!"]
            colors = [(255, 255, 255), (255, 230, 80)]
        else:
            sprite = player_images.get(evicted_id % len(player_images))
            key = roles.role_key_of(ev_role)
            if key is not None:
                first = f"{name} war {roles.ROLES[key]['name']}."
            elif ev_team == 1:
                first = f"{name} war ein Imposter."
            elif ev_team == 2:
                first = f"{name} war eigenständig."
            else:
                first = f"{name} war kein Imposter."
            lines = [first, f"Team: {TEAM_NAMES.get(ev_team, '?')}",
                     f"Noch {imps_left} Imposter übrig." if imps_left != 1 else "Noch 1 Imposter übrig."]
            colors = [(255, 255, 255), TEAM_COLORS.get(ev_team, (255, 255, 255)), (170, 175, 190)]
            sfx.play("eject")
        eject_anim = fx.EjectAnimation((WIDTH, HEIGHT), lines, sprite, colors)
        sfx.set_loop("walking", False)
    elif kind == "round_start":
        death_anim = eject_anim = end_screen = None
        sfx.play("role_reveal")
    elif kind == "back_to_lobby":
        death_anim = eject_anim = end_screen = None
        if ghost_video is not None:
            ghost_video.close()
        ghost_video = None
        ghost_intro_timer = 0.0

def start_end_screen(new_state):
    """NEU: Sieg-/Niederlagen-Animation starten (nach laufenden Animationen)."""
    global state, end_screen, show_minimap, show_role_info, task_aborted
    state = new_state
    show_minimap = False
    show_role_info = False
    if task_manager.active_task:
        task_aborted = True
        task_manager.reset_active_task()
    if ghost_video is not None:
        ghost_video.close()

    def entry(pid):
        team_b, role_b = final_roles.get(pid, (0, roles.NO_ROLE_ID))
        return (player_images.get(pid % len(player_images)), player_names.get(pid, f"Spieler {pid}"),
                role_text_of(team_b, role_b), TEAM_COLORS.get(team_b, (255, 255, 255)))

    all_ids = sorted(player_names.keys())
    if new_state == "crew_win":
        if final_roles:
            winner_ids = [pid for pid in all_ids if final_roles.get(pid, (0,))[0] == 0]
        else:
            winner_ids = [pid for pid in all_ids if pid not in imposter_reveal_ids]
        victory = my_player.role == "Crewmate"
        subline = "Die Besatzung hat gewonnen!"
        sound_name = "crew_win"
        accent = (90, 200, 255)
    elif new_state == "imposter_win":
        if final_roles:
            winner_ids = [pid for pid in all_ids if final_roles.get(pid, (0,))[0] == 1]
        else:
            winner_ids = [pid for pid in all_ids if pid in imposter_reveal_ids]
        victory = my_player.role == "Imposter"
        subline = "Die Imposter haben gewonnen!"
        sound_name = "imposter_win"
        accent = (255, 90, 90)
    else:
        winner_ids = [independent_winner_id] if independent_winner_id is not None else []
        victory = my_id == independent_winner_id
        winner_name = player_names.get(independent_winner_id, "Unbekannt")
        subline = f"{winner_name} gewinnt allein - Besatzung UND Imposter verlieren."
        sound_name = "independent_win"
        accent = (255, 210, 90)
    end_screen = fx.EndScreen((WIDTH, HEIGHT), victory, "SIEG!" if victory else "NIEDERLAGE", subline,
                              [entry(pid) for pid in winner_ids],
                              player_images.get(my_id % len(player_images)),
                              player_dead_images.get(my_id % len(player_dead_images)), accent)
    sfx.stop_loops()
    sfx.set_music(0)
    sfx.play(sound_name)

def draw_action_buttons_layer():
    """NEU: Aktions-Buttons ganz oben zeichnen. Im Meeting bleibt nur der ROLLE-Button (oben rechts)."""
    global current_buttons
    if task_manager.active_task is not None or cutscene_active():
        current_buttons = []
        return
    if meeting_active:
        s = HEIGHT / 810.0
        size = int(72 * s)
        spec = hud.ButtonSpec(pygame.K_r, "R", "ROLLE", "role", team_color(), small=True, active=show_role_info,
                              image=get_role_image(my_player.role_key, ROLE_THUMB_SIZE) if my_player.role_key else None)
        spec.rect = pygame.Rect(WIDTH - size - int(16 * s), int(16 * s), size, size)
        current_buttons = [spec]
    else:
        current_buttons = hud.layout_buttons(build_action_buttons(), WIDTH, HEIGHT)
    hud.draw_buttons(screen, current_buttons)

# =========================
# NEU: BROWSER-MODUS (WebAssembly) - Verbindung ohne Threads, einmal pro Frame
# =========================
browser_conn = None
browser_join_started = 0.0
last_frame_time = 0.0
frame_work_start = 0.0
frame_work_ms = 0.0            # gleitender Mittelwert der Rechenzeit pro Frame (Anzeige in der Leiste)
BROWSER_JOIN_TIMEOUT = 20.0

# NEU: Zeitmessung pro Abschnitt (Browser: /play/?...&perf=1, lokal: Umgebungsvariable TIAU_PERF=1)
PERF = bool(os.environ.get("TIAU_PERF"))
_perf_t = 0.0
_perf_acc = {}
_perf_frames = 0
_perf_last = 0.0

def perf_mark(label):
    global _perf_t
    if not PERF:
        return
    now = time.perf_counter()
    if label is not None:
        _perf_acc[label] = _perf_acc.get(label, 0.0) + (now - _perf_t)
    _perf_t = now

def perf_frame_end():
    global _perf_frames, _perf_last
    if not PERF:
        return
    _perf_frames += 1
    now = time.time()
    if now - _perf_last >= 2.0 and _perf_frames:
        parts = "  ".join(f"{k}={v * 1000 / _perf_frames:.1f}" for k, v in sorted(_perf_acc.items(), key=lambda kv: -kv[1]))
        print(f"PERF state={state} ms/Frame: {parts}")
        _perf_acc.clear()
        _perf_frames = 0
        _perf_last = now

def browser_start():
    global browser_conn, sock, state, browser_join_started, PERF
    room, name = web_bridge.get_params()
    PERF = PERF or web_bridge.PERF
    browser_conn = web_bridge.Connection()
    sock = browser_conn
    state = "connecting"
    browser_join_started = time.time()
    browser_conn.open(room, name)

def browser_net_step():
    """Empfangenes verarbeiten: erst der Handshake (eigene ID), danach vollstaendige Pakete."""
    global state, running
    conn = browser_conn
    conn.pump()
    status = conn.state()
    if my_id is None:
        if status == "open" and not conn.name_sent:
            name_data = web_bridge.PLAYER_NAME.encode("utf-8")[:255]
            conn.sendall(struct.pack("!B", len(name_data)) + name_data)
            conn.name_sent = True
        if conn.name_sent and len(conn.buf) >= 1:
            new_id = conn.buf[0]
            del conn.buf[:1]
            finish_connect(new_id)
            state = "lobby"
            web_bridge.signal_ready()
        elif status != "closed" and time.time() - browser_join_started > BROWSER_JOIN_TIMEOUT:
            conn.close()
            status = "closed"
    if my_id is not None:
        while True:
            try:
                n = web_bridge.packet_length(conn.buf)
            except ValueError as e:
                print("PROTOKOLLFEHLER:", e)
                conn.close()
                status = "closed"
                break
            if n is None:
                break
            packet = bytes(conn.buf[:n])
            del conn.buf[:n]
            try:
                handle_packet(web_bridge.PacketReader(packet[1:], conn), packet[0])
            except Exception as e:
                print("PAKETFEHLER", packet[0], e)
    if status == "closed" and running:
        reason = conn.close_reason()
        if my_id is None:
            web_bridge.notify_end("join_failed", reason or "Der Raum ist nicht erreichbar.")
        else:
            web_bridge.notify_end("room_closed", reason or "Die Verbindung zum Raum wurde getrennt.")
        sfx.stop_loops()
        sfx.set_music(0)
        running = False

def draw_connecting():
    screen.fill((10, 12, 24))
    dots = "." * (int(time.time() * 3) % 4)
    txt = menu_font.render(f"Verbinde mit Raum {web_bridge.ROOM_CODE}{dots}", True, (255, 255, 255))
    screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 30))

# NEU: Im Web-Modus direkt dem Raum beitreten (Name/Port kommen vom Webserver)
if BROWSER:
    browser_start()
elif WEB_MODE:
    if connect_to_server(web_bridge.SERVER_HOST, web_bridge.PLAYER_NAME, spawnpoints, port=web_bridge.SERVER_PORT):
        state = "lobby"
    else:
        web_bridge.notify_end("connect_failed", "Der Raum ist voll, das Spiel läuft schon oder er existiert nicht mehr.")
        pygame.quit()
        web_bridge.hard_exit(1)

async def main_loop():
    """Die bisherige Hauptschleife - NEU als async-Funktion, damit sie auch im Browser laeuft
    (dort muss jeder Frame mit "await asyncio.sleep(0)" an den Browser zurueckgeben).
    Alle Variablen sind wie vorher globale Modul-Variablen."""
    global frame_work_start, frame_work_ms
    global _data, _kind, _next_state, _owner, _row, _weapon_id, active_task_idx, all_zero
    global already_done_timer, at_meeting_box, b_img, back, back_clicked, back_rect, bar_rect
    global body_center, body_id, border_col, box, boxes, btn, btn_minus, btn_plus, bx, by, camera_x
    global camera_y, cancel_rect, chat_input_rect, chat_rect, checkbox_rect, clicked, closest_id
    global collected, confirm_rect, current_alpha, cv, d, d_id, david_marked_id, death_anim
    global distance, dt, dx, dy, e_name, eject_anim, enemy_center, enemy_img
    global evelyn_cooldown_remaining, event, fill_col, flag_img, ghost_intro_timer, ghost_video
    global has_voted, haze, headers, i_x, i_y, img_copy, immortal_banner_timer, info, info_col
    global intro_timer, intro_txt, is_open, is_task_active, is_visible, item_spots
    global kaliyoga_bonus_used, key, kill_cd, kill_cooldown_remaining, kill_range, last_frame_time
    global laurin_uses_left, lay, lbl, mates, meeting_chat_input, meeting_cooldown
    global meeting_result_timer, meeting_selected_target, meeting_timer, minus, mm_x, mm_y
    global monika_flag_cooldown, monika_flag_pos, monika_teleport_cooldown, moved_this_frame, msg
    global msg_bytes, my_center, my_name, my_name_text, n_x, n_y, name_color, name_text, near_body
    global nearest_btn, nearest_dist, new_state, next_b, noah_trap_cooldown, note, note_bg, nx, ny
    global overlay, p_col, p_id, pending_end_state, pending_vladimir_video, pid, player_mm_x
    global player_mm_y, pleschbergsteiger_uses_left, plus, pos, prev_b, pt, ramona_last_forge
    global ramona_stand_timer, raphi_collected, ready, rect, reset, rk, role_detail_key
    global role_info_click_consumed, room_idx, room_rect, row, row_rect, rows, running, scaled_size
    global scaled_surface, scissors_img, shade, show_minimap, show_role_info, skip_rect, spot, state
    global stroblpeter_mark_timer, stroblpeter_marked_id, stroblpeter_ready_to_strike, sub_txt
    global t_col, t_idx, t_x, t_y, target, task_aborted, task_reset_banner_timer, title_color
    global tl_color, tl_text, trap_img, tx, ty, v, vogelscheicher_invisible_until
    global walking_sound_until, was_task_active, weapon_id, window_zone_timer, world_pos
    global yoshi_finds, yoshi_reveal_timer, yoshi_reveals_left, zr
    while running:
        # NEU: Im Browser gibt der Bildschirm (requestAnimationFrame) den Takt vor; Spiel-Logik
        # hoechstens ~60x pro Sekunde, damit Zaehler/Tasks auf 120/144-Hz-Monitoren nicht zu schnell laufen
        if BROWSER:
            _now = time.perf_counter()
            if _now - last_frame_time < 1.0 / 62:
                await asyncio.sleep(0)
                continue
            last_frame_time = _now
            perf_mark(None)
            browser_net_step()
            perf_mark("net")
        frame_work_start = time.perf_counter()
        dt = min(0.1, clock.tick(0 if BROWSER else 60) / 1000.0)
        was_task_active = task_manager.active_task is not None

        # NEU: Auftraege aus dem Empfangs-Thread abarbeiten (Animationen bauen, Sounds)
        while ui_events:
            _kind, _data = ui_events.popleft()
            try:
                handle_ui_event(_kind, _data)
            except Exception as _e:
                print("UI EVENT ERROR:", _kind, _e)
        if death_anim is not None and death_anim.done:
            death_anim = None
        if eject_anim is not None and eject_anim.done:
            eject_anim = None
        # Vladimirs Anime-Intro startet direkt nach der Todes-Animation
        if pending_vladimir_video and death_anim is None and state == "game":
            pending_vladimir_video = False
            if my_player.is_dead:
                ghost_video = make_ghost_video()
                ghost_intro_timer = 0.0 if ghost_video.active else VLADIMIR_INTRO_DURATION
        # Sieg/Niederlage erst zeigen, wenn Rauswurf-/Todes-Animation fertig sind
        if pending_end_state and not cutscene_active() and state == "game":
            _next_state = pending_end_state
            pending_end_state = None
            start_end_screen(_next_state)

        # Meeting-Timer & Notfallknopf-Cooldown laufend runterzählen (sonst bleibt die Anzeige stehen)
        if meeting_active:
            meeting_timer = max(0.0, meeting_timer - dt)
        if meeting_cooldown > 0:
            meeting_cooldown = max(0.0, meeting_cooldown - dt)

        # NEU: Lokale Rollen-Fähigkeits-Timer laufend runterzählen
        if state == "game" and game_started:
            if kill_cooldown_remaining > 0:
                kill_cooldown_remaining = max(0.0, kill_cooldown_remaining - dt)
            if evelyn_cooldown_remaining > 0:
                evelyn_cooldown_remaining = max(0.0, evelyn_cooldown_remaining - dt)
            if noah_trap_cooldown > 0:
                noah_trap_cooldown = max(0.0, noah_trap_cooldown - dt)
            if immortal_banner_timer > 0:
                immortal_banner_timer = max(0.0, immortal_banner_timer - dt)
            if yoshi_reveal_timer > 0:
                yoshi_reveal_timer = max(0.0, yoshi_reveal_timer - dt)
            if ghost_intro_timer > 0:
                ghost_intro_timer = max(0.0, ghost_intro_timer - dt)

            # NEU: Monika entscheidet selbst, wann sie reist - hier laufen nur die Cooldowns
            if monika_flag_cooldown > 0:
                monika_flag_cooldown = max(0.0, monika_flag_cooldown - dt)
            if monika_teleport_cooldown > 0:
                monika_teleport_cooldown = max(0.0, monika_teleport_cooldown - dt)
            if task_reset_banner_timer > 0:
                task_reset_banner_timer = max(0.0, task_reset_banner_timer - dt)
            if meeting_result_timer > 0:
                meeting_result_timer = max(0.0, meeting_result_timer - dt)

            # Stroblpeter: nach Ablauf der Merk-Zeit bereit zum Zuschlagen
            if my_player.role_key == "stroblpeter" and stroblpeter_marked_id is not None and not stroblpeter_ready_to_strike:
                stroblpeter_mark_timer -= dt
                if stroblpeter_mark_timer <= 0:
                    stroblpeter_ready_to_strike = True

            # Evelyn: Fensterfalle - nur der EINE geoeffnete Raum ist gefaehrlich
            if (time.time() < window_hazard_until and not my_player.is_dead
                    and 0 <= window_hazard_room < len(window_zones)):
                if window_zones[window_hazard_room].collidepoint(my_player.rect.center):
                    window_zone_timer += dt
                    if window_zone_timer > EVELYN_LINGER_LIMIT:
                        window_zone_timer = -999.0  # schon gemeldet, nicht erneut senden
                        try: sock.sendall(struct.pack("!BB", 62, window_hazard_room))
                        except: pass
                else:
                    window_zone_timer = 0.0
            else:
                window_zone_timer = 0.0

            # Attrappen (Vogelscheicher) ablaufen lassen
            for pid in list(decoys.keys()):
                if time.time() >= decoys[pid][2]:
                    del decoys[pid]

            # Ramona: Stehzeit am Regal (Spawnbereich) tracken, Sieg automatisch beanspruchen sobald
            # alle bekannten Spieler bei 0 Rechten sind. Der Server validiert das nochmal autoritativ.
            if my_player.role_key == "ramona" and not my_player.is_dead:
                all_zero = bool(ramona_others_rights) and all(v <= 0 for v in ramona_others_rights.values())
                if all_zero and RAMONA_WIN_ZONE.collidepoint(my_player.rect.center):
                    ramona_stand_timer += dt
                    if ramona_stand_timer >= RAMONA_WIN_STAND_TIME:
                        try: sock.sendall(struct.pack("!B", 81))
                        except: pass
                        ramona_stand_timer = -999.0
                else:
                    ramona_stand_timer = 0.0

        perf_mark("timers")
        for event in pygame.event.get():
            # NEU: True, sobald ein Klick vom Rollen-Info-Panel verbraucht wurde (dann nicht abstimmen)
            role_info_click_consumed = False

            if event.type == pygame.QUIT and not BROWSER:   # im Browser verlaesst man ueber die Leiste
                running = False
                pygame.quit()
                if WEB_MODE:
                    web_bridge.hard_exit(0)
                sys.exit()

            if state == "menu":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    if connect_to_server(ip_input.text, name_input.text, spawnpoints):
                        state = "lobby"
                ip_input.handle_event(event)
                name_input.handle_event(event)

            elif state == "lobby":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    lay = get_lobby_layout()
                    if lay["roles"].collidepoint(event.pos):
                        state = "role_select"          # NEU: fuer alle (Nicht-Hosts nur lesen)
                    elif lay["settings"].collidepoint(event.pos):
                        state = "settings"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and my_id == host_id:
                    lay = get_lobby_layout()
                    btn, btn_minus, btn_plus = lay["start"], lay["minus"], lay["plus"]

                    if btn.collidepoint(event.pos):
                        if current_role_setup_status()[0]:
                            try: sock.sendall(struct.pack("!B", 99))
                            except: pass
                    elif lay["assign"].collidepoint(event.pos):
                        state = "role_assign"
                    elif btn_minus.collidepoint(event.pos):
                        if imposter_count > 1:
                            try: sock.sendall(struct.pack("!BB", 11, imposter_count - 1))
                            except: pass
                    elif btn_plus.collidepoint(event.pos):
                        # Nicht mehr Imposter zulassen als es freundliche Spieler gibt
                        if imposter_count < max_imposters_for(len(player_names)):
                            try: sock.sendall(struct.pack("!BB", 11, imposter_count + 1))
                            except: pass

            elif state == "role_select":
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE):
                    state = "lobby"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    rows, headers, back_rect = get_role_select_layout()
                    if back_rect.collidepoint(event.pos):
                        state = "lobby"
                    else:
                        for key, row_rect, checkbox_rect in rows:
                            if row_rect.collidepoint(event.pos):
                                role_detail_key = key          # NEU: Beschreibung anzeigen (alle)
                                if my_id == host_id:
                                    new_state = 0 if key in enabled_roles else 1
                                    try: sock.sendall(struct.pack("!BBB", 13, roles.role_id_of(key), new_state))
                                    except: pass
                                break

            # NEU: Einstellungen (Host aendert, alle koennen lesen)
            elif state == "settings":
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE):
                    state = "lobby"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    rows, back = get_settings_layout()
                    if back.collidepoint(event.pos):
                        state = "lobby"
                    elif my_id == host_id:
                        for key, _row, minus, plus in rows:
                            if minus.collidepoint(event.pos):
                                send_settings(key, -SETTING_STEP)
                            elif plus.collidepoint(event.pos):
                                send_settings(key, SETTING_STEP)

            # NEU: Feste Rollen zuteilen (nur Host, "Cheat")
            elif state == "role_assign":
                if my_id != host_id:
                    state = "lobby"
                elif event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE):
                    state = "lobby"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                    rows, back, reset = get_assign_layout()
                    if back.collidepoint(event.pos):
                        state = "lobby"
                    elif reset.collidepoint(event.pos):
                        for pid in list(fixed_role_map.keys()):
                            try: sock.sendall(struct.pack("!BBB", 18, pid, roles.FIXED_NONE))
                            except: pass
                    else:
                        for pid, row, prev_b, next_b in rows:
                            if prev_b.collidepoint(event.pos):
                                cycle_fixed_role(pid, -1)
                            elif next_b.collidepoint(event.pos) or (row.collidepoint(event.pos) and event.button == 1):
                                cycle_fixed_role(pid, 1)
                            elif row.collidepoint(event.pos) and event.button == 3:
                                cycle_fixed_role(pid, -1)

            elif state == "game":
                # NEU: Klick auf einen Aktions-Button (Toeten, Benutzen, Vent, Faehigkeit, Karte, Rolle).
                # Der Klick loest einfach denselben Tastendruck aus wie die Tastatur. Der ROLLE-Button
                # funktioniert auch im Meeting.
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and task_manager.active_task is None:
                    clicked = hud.button_at(current_buttons, event.pos)
                    if clicked is not None:
                        role_info_click_consumed = True
                        if clicked.key_code == pygame.K_r:
                            show_role_info = not show_role_info
                        elif clicked.enabled or clicked.small:
                            show_role_info = False
                            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=clicked.key_code,
                                                                 unicode="", mod=0, scancode=0))
                    elif show_role_info:
                        show_role_info = False
                        role_info_click_consumed = True

                # NEU: Evelyn waehlt ihren Fensterraum direkt auf der geoeffneten Karte aus
                if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                        and show_minimap and not role_info_click_consumed
                        and my_player.role_key == "evelyn" and not my_player.is_dead
                        and evelyn_cooldown_remaining <= 0 and not meeting_active):
                    for room_idx, room_rect in get_window_room_minimap_rects():
                        if room_rect.collidepoint(event.pos):
                            try: sock.sendall(struct.pack("!BB", 60, room_idx))
                            except: pass
                            evelyn_cooldown_remaining = EVELYN_COOLDOWN
                            break

                if event.type == pygame.KEYDOWN:
                    if meeting_active:
                        # Während eines Meetings sind Tasten NUR für den Chat da - Q/M/E/Leertaste/
                        # Vent-Wechsel dürfen hier nicht mehr durchgreifen (sonst würde z.B. "q" im
                        # Chattext das ganze Spiel beenden oder "Leertaste" den Imposter venten lassen).
                        if my_player.is_dead:
                            pass   # NEU: Tote Spieler koennen nicht in den Chat schreiben
                        elif event.key == pygame.K_RETURN:
                            msg = meeting_chat_input.strip()
                            if msg:
                                msg_bytes = msg.encode("utf-8")[:120]
                                try: sock.sendall(struct.pack("!BB", 50, len(msg_bytes)) + msg_bytes)
                                except: pass
                            meeting_chat_input = ""
                        elif event.key == pygame.K_BACKSPACE:
                            meeting_chat_input = meeting_chat_input[:-1]
                        elif event.unicode and event.unicode.isprintable() and len(meeting_chat_input) < 120:
                            meeting_chat_input += event.unicode
                    elif not cutscene_active():
                        if event.key == pygame.K_q:
                            if task_manager.active_task:
                                task_aborted = True
                                task_manager.reset_active_task()
                                task_manager.active_task = None
                            elif show_minimap: show_minimap = False
                            elif show_role_info: show_role_info = False
                            elif not WEB_MODE and not BROWSER:
                                # Im Browser beendet Q das Spiel NICHT (Verlassen ueber den Button oben rechts)
                                running = False
                                pygame.quit()
                                sys.exit()

                        if event.key == pygame.K_m and task_manager.active_task is None:
                            show_minimap = not show_minimap

                        # NEU: Rollenbeschreibung jederzeit nachschlagen
                        if event.key == pygame.K_r and task_manager.active_task is None:
                            show_role_info = not show_role_info

                        # NEU: Monika entscheidet selbst, wann sie zu ihrer Flagge reist.
                        # (Q ist schon mit "Spiel beenden" belegt, deshalb G wie "Gehe zur Flagge".)
                        if (event.key == pygame.K_g and my_player.role_key == "monika"
                                and not my_player.is_dead and not my_player.is_venting
                                and task_manager.active_task is None and not show_minimap):
                            if monika_flag_pos is not None and monika_teleport_cooldown <= 0:
                                my_player.rect.centerx, my_player.rect.centery = monika_flag_pos
                                monika_teleport_cooldown = MONIKA_TELEPORT_COOLDOWN
                                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                                except: pass

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

                        # Interaktions-Logik (Blockiert, wenn man im Vent abgetaucht ist)
                        if event.key == pygame.K_e and task_manager.active_task is None and not show_minimap and not my_player.is_venting:
                            at_meeting_box = False
                            for box in emergency_hitboxes:
                                if my_player.rect.colliderect(box):
                                    at_meeting_box = True
                                    break

                            # Liegt eine Leiche in Melde-Reichweite? (gleicher Radius wie beim Töten)
                            near_body = False
                            my_center = my_player.rect.center
                            for body_id, (bx, by, _weapon_id) in dead_bodies.items():
                                body_center = (bx + PLAYER_SIZE // 2, by + PLAYER_SIZE // 2)
                                if math.hypot(my_center[0] - body_center[0], my_center[1] - body_center[1]) < 60:
                                    near_body = True
                                    break

                            if near_body and not my_player.is_dead:
                                # Leiche melden -> Meeting starten (kein Cooldown, wie im echten Spiel)
                                try: sock.sendall(struct.pack("!BB", 40, MEETING_REASON_BODY))
                                except: pass
                            elif at_meeting_box and not my_player.is_dead and meeting_cooldown <= 0 and not my_emergency_used:
                                try: sock.sendall(struct.pack("!BB", 40, MEETING_REASON_BUTTON))
                                except: pass
                            elif my_player.role == "Imposter" and not my_player.is_dead and kill_cooldown_remaining <= 0:
                                # Kill Suche (Martin hat größere Reichweite & höheren Cooldown)
                                kill_range = KILL_RANGE_MARTIN if my_player.role_key == "martin" else KILL_RANGE_DEFAULT
                                kill_cd = KILL_COOLDOWN_MARTIN if my_player.role_key == "martin" else KILL_COOLDOWN_DEFAULT
                                my_center = my_player.rect.center
                                # NEU: Mit-Imposter sind vom Kill ausgenommen (der Server blockt das ebenfalls)
                                closest_id = find_nearest_player(my_center, other_players, kill_range, dead_players,
                                                                 exclude_ids=my_imposter_teammates)

                                if closest_id is not None:
                                    try: sock.sendall(struct.pack("!BB", 30, closest_id)) # Sende Kill-Paket
                                    except: pass
                                    kill_cooldown_remaining = kill_cd

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
                    
                        # NEU: Spezialfähigkeiten-Taste (F) - Aktion hängt von der zugewiesenen Rolle ab
                        if event.key == pygame.K_f and not show_minimap and not my_player.is_venting:
                            my_center = my_player.rect.center
                            rk = my_player.role_key

                            if rk == "monika" and not my_player.is_dead:
                                # NEU: Flagge setzen. Sie bleibt liegen und kann nach dem Cooldown
                                # an einer anderen Stelle neu gesetzt werden.
                                if monika_flag_cooldown <= 0:
                                    monika_flag_pos = my_player.rect.center
                                    monika_flag_cooldown = MONIKA_FLAG_COOLDOWN
                                    monika_teleport_cooldown = MONIKA_TELEPORT_COOLDOWN

                            elif rk == "stroblpeter" and not my_player.is_dead:
                                if stroblpeter_marked_id is None:
                                    target = find_nearest_player(my_center, other_players, STROBLPETER_MARK_RANGE, dead_players,
                                                                 exclude_ids=my_imposter_teammates)
                                    if target is not None:
                                        stroblpeter_marked_id = target
                                        stroblpeter_mark_timer = STROBLPETER_MARK_DELAY
                                        stroblpeter_ready_to_strike = False
                                elif stroblpeter_ready_to_strike and stroblpeter_marked_id in other_players and stroblpeter_marked_id not in dead_players:
                                    tx, ty = other_players[stroblpeter_marked_id]
                                    my_player.rect.centerx, my_player.rect.centery = tx + PLAYER_SIZE, ty
                                    try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                                    except: pass
                                    try: sock.sendall(struct.pack("!BB", 30, stroblpeter_marked_id))
                                    except: pass
                                    stroblpeter_marked_id = None
                                    stroblpeter_ready_to_strike = False

                            elif rk == "laurin" and laurin_uses_left > 0 and not my_player.is_dead:
                                # NEU: Laurin geht zu einer Aufgabe und macht sie fuer alle wieder offen
                                nearest_btn, nearest_dist = None, LAURIN_SABOTAGE_RANGE
                                for btn in task_buttons:
                                    d = math.hypot(my_center[0] - btn["rect"].centerx, my_center[1] - btn["rect"].centery)
                                    if d < nearest_dist:
                                        nearest_dist, nearest_btn = d, btn
                                if nearest_btn is not None:
                                    try: sock.sendall(struct.pack("!BB", 63, nearest_btn["task_index"]))
                                    except: pass
                                    laurin_uses_left -= 1

                            elif rk == "kaliyoga" and not my_player.is_dead and not kaliyoga_bonus_used:
                                # NEU: einmal pro Spiel ein Notfallmeeting von ueberall aus
                                kaliyoga_bonus_used = True
                                try: sock.sendall(struct.pack("!BB", 40, MEETING_REASON_KALIYOGA))
                                except: pass

                            elif rk == "david" and not my_player.is_dead:
                                target = find_nearest_player(my_center, other_players, DAVID_MARK_RANGE, dead_players)
                                if target is not None:
                                    david_marked_id = target
                                    try: sock.sendall(struct.pack("!BB", 65, target))
                                    except: pass

                            elif rk == "noah" and not my_player.is_dead and noah_trap_cooldown <= 0:
                                # Bis zu NOAH_TRAP_LIMIT Fallen, danach wird die aelteste ersetzt
                                noah_traps.append((my_center[0], my_center[1]))
                                if len(noah_traps) > NOAH_TRAP_LIMIT:
                                    noah_traps.pop(0)
                                noah_trap_cooldown = NOAH_TRAP_COOLDOWN
                                try: sock.sendall(struct.pack('!Bii', 66, int(my_center[0]), int(my_center[1])))
                                except: pass

                            elif rk == "vogelscheicher" and not my_player.is_dead:
                                vogelscheicher_invisible_until = time.time() + VOGELSCHEICHER_INVISIBLE_DURATION
                                try: sock.sendall(struct.pack('!Bii', 68, int(my_center[0]), int(my_center[1])))
                                except: pass

                            elif rk == "pleschbergsteiger" and pleschbergsteiger_uses_left > 0:
                                target = find_nearest_player(my_center, other_players, PLESCHBERGSTEIGER_RANGE, dead_players, want_dead=True)
                                if target is not None:
                                    try: sock.sendall(struct.pack("!BB", 73, target))
                                    except: pass
                                    pleschbergsteiger_uses_left -= 1

                            elif rk == "yoshi" and not my_player.is_dead:
                                # Zuerst einen danebenliegenden Standard einsammeln - jeder Fund gibt
                                # eine Rollen-Aufdeckung. Steht man an keinem Fundpunkt, wird eine
                                # vorhandene Aufdeckung auf den naechsten Spieler angewendet.
                                collected = False
                                for pt in list(yoshi_find_points):
                                    if math.hypot(my_center[0] - pt.centerx, my_center[1] - pt.centery) < YOSHI_FIND_RANGE:
                                        yoshi_find_points.remove(pt)
                                        yoshi_finds += 1
                                        yoshi_reveals_left += 1
                                        collected = True
                                        break
                                if not collected and yoshi_reveals_left > 0:
                                    target = find_nearest_player(my_center, other_players, DAVID_MARK_RANGE, dead_players)
                                    if target is not None:
                                        try: sock.sendall(struct.pack("!BB", 75, target))
                                        except: pass
                                        yoshi_reveals_left -= 1

                            elif rk == "tappeihnachtsmann" and not my_player.is_dead:
                                for pt in list(tappeihnachtsmann_find_points):
                                    if math.hypot(my_center[0] - pt.centerx, my_center[1] - pt.centery) < TAPPEIHNACHTSMANN_FIND_RANGE:
                                        tappeihnachtsmann_find_points.remove(pt)
                                        try: sock.sendall(struct.pack("!B", 77))
                                        except: pass
                                        break

                            elif rk == "raphi":
                                for pt in list(raphi_collect_points):
                                    if math.hypot(my_center[0] - pt.centerx, my_center[1] - pt.centery) < RAPHI_COLLECT_RANGE:
                                        raphi_collect_points.remove(pt)
                                        raphi_collected += 1
                                        # 255 = keine Karten-Aufgabe (Pfandflasche), fuer Laurin nicht sabotierbar
                                        try: sock.sendall(struct.pack("!BB", 20, 255))
                                        except: pass
                                        break

                            elif rk == "ramona" and not my_player.is_dead and (time.time() - ramona_last_forge) >= RAMONA_FORGE_COOLDOWN_CLIENT:
                                target = find_nearest_player(my_center, other_players, RAMONA_FORGE_RANGE, dead_players)
                                if target is not None:
                                    try: sock.sendall(struct.pack("!BB", 79, target))
                                    except: pass
                                    ramona_last_forge = time.time()

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
                                        sfx.play("vent")
                                        # Sende ungültige Off-Screen Position an den Server, damit wir unsichtbar werden
                                        try: sock.sendall(struct.pack('!Bii', 2, -2000, -2000))
                                        except: pass
                                else:
                                    # Auftauchen aus dem aktuellen Vent
                                    my_player.is_venting = False
                                    sfx.play("vent")
                                    if vents:
                                        my_player.rect.center = vents[my_player.current_vent_idx].center
                                    # Sende die echte Position wieder an den Server
                                    try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                                    except: pass

            # NEU: Abstimmen in zwei Schritten - erst einen Spieler (oder SKIP) anklicken,
            # dann in der Bestaetigungsleiste den Haken druecken. Das X verwirft die Auswahl.
            if (meeting_active and meeting_phase == MEETING_PHASE_VOTE
                    and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and not has_voted and not my_player.is_dead
                    and not role_info_click_consumed):
                boxes, skip_rect, chat_rect, chat_input_rect, bar_rect, confirm_rect, cancel_rect = get_meeting_layout()

                if meeting_selected_target is not None and confirm_rect.collidepoint(event.pos):
                    try: sock.sendall(struct.pack("!BB", 41, meeting_selected_target))
                    except: pass
                    has_voted = True
                    meeting_selected_target = None
                elif meeting_selected_target is not None and cancel_rect.collidepoint(event.pos):
                    meeting_selected_target = None
                else:
                    for p_id, rect in boxes:
                        if p_id in dead_players:
                            continue  # Tote können nicht gewählt werden
                        if rect.collidepoint(event.pos):
                            meeting_selected_target = p_id
                            break
                    else:
                        if skip_rect.collidepoint(event.pos):
                            meeting_selected_target = 255  # 255 = Skip, siehe Server-Protokoll

            # NEU: Endbildschirm - der Host holt alle per Enter ODER Klick auf den Button zurueck.
            # (FIX: vorher wurde das nach der Event-Schleife mit dem zuletzt gesehenen Event geprueft -
            # ohne jedes Event gab es einen NameError, und Paket 23 wurde mehrfach geschickt.)
            elif state in ("crew_win", "imposter_win", "independent_win") and my_id == host_id:
                back_clicked = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                                and end_screen is not None and end_screen.button_rect.collidepoint(event.pos))
                if (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN) or back_clicked:
                    try: sock.sendall(struct.pack("!B", 23))
                    except: pass

            if not cutscene_active():
                task_manager.handle_event(event)

        perf_mark("events")
        moved_this_frame = False

        if state == "game" and task_manager.active_task is None and not show_minimap and not show_role_info and game_started:
            # NEU: Normale WASD Bewegung blockieren, falls man im Vent sitzt oder (Vladimir) noch
            # als frisch getöteter Geist das Intro abwarten muss
            if not my_player.is_venting and not meeting_active and not ghost_intro_blocking() and not cutscene_active():
                moved_this_frame = my_player.move(pygame.key.get_pressed(), hitboxes, min(3.0, dt * 60.0))
                if moved_this_frame:
                    try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                    except: running = False

        elif state == "lobby" and not game_started and my_id is not None:
            moved_this_frame = my_player.move(pygame.key.get_pressed(), lobby_hitboxes, min(3.0, dt * 60.0))
            if moved_this_frame:
                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: running = False

        # NEU: Laufanimation fortschreiben - eigener Spieler und alle anderen
        if my_id is not None:
            my_player.update_walk_anim(dt, moved_this_frame)
        update_other_walk_anims(dt)

        # NEU: Schritt-Geraeusch (mit kurzer Nachlaufzeit gegen Flackern an Waenden) + Hintergrundmusik
        if moved_this_frame and not my_player.is_dead:
            walking_sound_until = time.time() + 0.15
        sfx.set_loop("walking", time.time() < walking_sound_until and state in ("game", "lobby"))
        if state in ("menu", "lobby", "role_select"):
            sfx.set_music(sound.MUSIC_VOLUME_LOBBY)
        elif state == "game":
            sfx.set_music(sound.MUSIC_VOLUME_GAME)
        else:
            sfx.set_music(0)

        perf_mark("logic")
        # --- RENDERING ---
        if state == "menu":
            draw_menu()
        elif state == "connecting":
            draw_connecting()
        elif state == "lobby" and not game_started:
            draw_lobby()
        elif state == "role_select":
            draw_role_select()
        elif state == "settings":
            draw_settings()
        elif state == "role_assign":
            draw_role_assign()
        elif state == "game":
            camera_x = my_player.rect.x - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)
            camera_y = my_player.rect.y - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)

            internal_surface.fill((40, 80, 40))
            internal_surface.blit(map_combined, (-camera_x, -camera_y))

            draw_task_buttons(internal_surface, task_buttons, my_player, camera_x, camera_y)

            my_center = my_player.rect.center

            # NEU: Einsammelbare Rollen-Items mit eigener Textur. Die Listen sind nur bei der
            # jeweiligen Rolle gefuellt, deshalb koennen alle drei bedenkenlos gezeichnet werden.
            draw_world_items(internal_surface, raphi_collect_points, "pfandflasche", my_center, camera_x, camera_y)
            draw_world_items(internal_surface, tappeihnachtsmann_find_points, "geschenk", my_center, camera_x, camera_y)
            draw_world_items(internal_surface, yoshi_find_points, "standard", my_center, camera_x, camera_y)

            # Leichen rendern
            for d_id, (dx, dy, weapon_id) in dead_bodies.items():
                b_img = player_dead_images.get(d_id % len(player_dead_images))
                if not b_img: continue

                body_center = (dx + (PLAYER_SIZE // 2), dy + (PLAYER_SIZE // 2))
                distance = math.hypot(my_center[0] - body_center[0], my_center[1] - body_center[1])

                if distance <= VISION_RADIUS:
                    if has_line_of_sight(my_center, body_center, mapwalls):
                        internal_surface.blit(b_img, (dx - camera_x, dy - camera_y))
                        # Martin: Schere steckt in der Leiche (eigene Textur, Assets/Items/schere.png)
                        if weapon_id == 1:
                            scissors_img = item_images.get("schere")
                            if scissors_img:
                                internal_surface.blit(scissors_img, (body_center[0] - camera_x - ITEM_SIZE // 2,
                                                                     body_center[1] - camera_y - ITEM_SIZE // 2))

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
                    if player_facing_left.get(p_id):
                        img_copy = pygame.transform.flip(img_copy, True, False)
                    if p_id in dead_players: img_copy.set_alpha(min(current_alpha, 128))
                    else: img_copy.set_alpha(current_alpha)
                    
                    internal_surface.blit(img_copy, (pos[0] - camera_x, pos[1] - camera_y + get_walk_offset(p_id)))
                
                    e_name = player_names.get(p_id, f"Player {p_id}")
                    # NEU: Mit-Imposter werden fuer Imposter rot hervorgehoben
                    name_color = (255, 90, 90) if p_id in my_imposter_teammates else (255, 255, 255)
                    name_text = fx.render_cached(name_font, e_name, name_color)
                    nx = (pos[0] - camera_x) + (PLAYER_SIZE // 2) - (name_text.get_width() // 2)
                    ny = (pos[1] - camera_y) - 16
                    fx.blit_alpha(internal_surface, name_text, (nx, ny), current_alpha)

            # NEU: Noahs Fallen sieht jetzt JEDER (wie Spieler/Items nur im Sichtradius mit freier Sicht)
            trap_img = item_images.get("falle")
            if trap_img and visible_traps:
                for _owner, tx, ty in list(visible_traps.values()):
                    if math.hypot(my_center[0] - tx, my_center[1] - ty) > VISION_RADIUS:
                        continue
                    if not has_line_of_sight(my_center, (tx, ty), mapwalls):
                        continue
                    internal_surface.blit(trap_img, (tx - camera_x - ITEM_SIZE // 2, ty - camera_y - ITEM_SIZE // 2))

            # NEU: Monikas gesetzte Flagge (nur für Monika selbst sichtbar, eigene Textur)
            if monika_flag_pos is not None and my_player.role_key == "monika":
                flag_img = item_images.get("flagge")
                if flag_img:
                    internal_surface.blit(flag_img, (monika_flag_pos[0] - camera_x - ITEM_SIZE // 2,
                                                     monika_flag_pos[1] - camera_y - ITEM_SIZE // 2))

            # Eigenen Spieler zeichnen
            my_player.draw(internal_surface, camera_x, camera_y)
            my_name = player_names.get(my_id, "Ich")
            my_name_text = fx.render_cached(name_font, my_name, (255, 255, 255))
            fx.blit_alpha(internal_surface, my_name_text, ((my_player.rect.x - camera_x) + (PLAYER_SIZE // 2) - (my_name_text.get_width() // 2), (my_player.rect.y - camera_y) - 16),
                          128 if (my_player.is_dead or my_player.is_venting) else 255)

            # NEU: Kill-Ziel / meldbare Leiche / Vent hervorheben
            draw_world_highlights(internal_surface, camera_x, camera_y)

            # NEU: Evelyns geöffnetes Fenster - nur der ausgewählte Raum bekommt den Nebel
            if time.time() < window_hazard_until and 0 <= window_hazard_room < len(window_zones):
                zr = window_zones[window_hazard_room].move(-camera_x, -camera_y)
                if zr.colliderect(internal_surface.get_rect()):
                    haze = pygame.Surface((zr.width, zr.height), pygame.SRCALPHA)
                    haze.fill(EVELYN_FOG_COLOR)
                    internal_surface.blit(haze, (zr.x, zr.y))

            internal_surface.blit(fog_overlay, (0, 0))

            scaled_size = min(WIDTH, HEIGHT)
            scaled_surface = pygame.transform.scale(internal_surface, (scaled_size, scaled_size))
            screen.fill((0, 0, 0))
            world_pos = ((WIDTH - scaled_size) // 2, (HEIGHT - scaled_size) // 2)
            screen.blit(scaled_surface, world_pos)
            web_bridge.set_world(internal_surface, scaled_surface, (world_pos[0], world_pos[1], scaled_size))
            perf_mark("world")

            if already_done_timer > 0 and task_manager.active_task is None:
                already_done_timer -= 1

            # NEU: HUD (linke Leiste + Banner) VOR dem Aufgabenfenster zeichnen, damit es nie darueber liegt
            draw_game_hud()
            perf_mark("hud")

            task_manager.draw(screen)
            task_manager.update()

            is_task_active = task_manager.active_task is not None
            if was_task_active and not is_task_active:
                if not task_aborted and active_task_idx != -1:
                    if active_task_idx not in my_player.my_completed_tasks:
                        my_player.my_completed_tasks.append(active_task_idx)
                        # Index mitschicken, damit Laurin gezielt genau diese Aufgabe zuruecksetzen kann
                        try: sock.sendall(struct.pack("!BB", 20, active_task_idx))
                        except: pass
                active_task_idx = -1
                task_aborted = False


            if intro_timer > 0:
                # NEU: 5 Sekunden nach echter Zeit (vorher 300 Bilder - bei weniger FPS dauerte es laenger)
                intro_elapsed = time.time() - intro_started_at
                intro_timer = max(0, 300 - int(intro_elapsed * 60))
                if intro_desc_cache[0] != (my_player.role_desc, WIDTH):
                    intro_desc_cache[0] = (my_player.role_desc, WIDTH)
                    intro_desc_cache[1] = wrap_text_render(my_player.role_desc, small_font, (255, 255, 255), WIDTH - 200)
                # NEU: animierte Rollen-Aufdeckung (gleiche Inhalte wie vorher, jetzt mit Einblendungen)
                title_color = (255, 50, 50) if my_player.role == "Imposter" else ((255, 210, 90) if my_player.role == "Independent" else (50, 200, 255))
                tl_text, tl_color = team_label()
                mates = imposter_teammate_names()
                fx.draw_role_reveal(
                    screen, min(5.0, intro_elapsed), 5.0,
                    f"DU BIST: {my_player.role_display_name.upper()}", title_color, tl_text, tl_color,
                    intro_desc_cache[1],
                    my_player.role_image,
                    ("Deine Mit-Imposter: " + ", ".join(mates)) if mates else "",
                    "Ihr könnt euch gegenseitig nicht töten." if mates else "",
                    "Taste R oder der ROLLE-Button unten rechts zeigt die Rolle jederzeit erneut.")

            if show_minimap and task_manager.active_task is None:
                mm_x, mm_y = get_minimap_origin()
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

                # NEU: Einsammelbare Rollen-Items zusätzlich zu den Tasks in Blau einzeichnen
                for item_spots in (raphi_collect_points, tappeihnachtsmann_find_points, yoshi_find_points):
                    for spot in item_spots:
                        i_x = mm_x + int((spot.centerx / MAP_WIDTH_PX) * MINIMAP_WIDTH)
                        i_y = mm_y + int((spot.centery / MAP_HEIGHT_PX) * MINIMAP_HEIGHT)
                        pygame.draw.circle(screen, (60, 140, 255), (i_x, i_y), 6)
                        pygame.draw.circle(screen, (0, 0, 0), (i_x, i_y), 6, 1)

                # NEU: Noah sieht seine eigenen Fallen auf der Karte
                if my_player.role_key == "noah":
                    for tx, ty in noah_traps:
                        n_x = mm_x + int((tx / MAP_WIDTH_PX) * MINIMAP_WIDTH)
                        n_y = mm_y + int((ty / MAP_HEIGHT_PX) * MINIMAP_HEIGHT)
                        pygame.draw.circle(screen, (255, 80, 80), (n_x, n_y), 6)
                        pygame.draw.circle(screen, (0, 0, 0), (n_x, n_y), 6, 1)

                # NEU: Evelyn hat keine Aufgaben auf der Karte - stattdessen kann sie hier direkt
                # einen der Fensterräume anklicken, der dann 20s lang geöffnet wird.
                if my_player.role_key == "evelyn":
                    ready = evelyn_cooldown_remaining <= 0 and not my_player.is_dead
                    for room_idx, room_rect in get_window_room_minimap_rects():
                        is_open = (room_idx == window_hazard_room and time.time() < window_hazard_until)
                        if is_open:
                            fill_col, border_col = (120, 190, 255, 110), (150, 220, 255)
                        elif ready:
                            fill_col, border_col = (255, 210, 90, 70), (255, 210, 90)
                        else:
                            fill_col, border_col = (140, 140, 150, 50), (140, 140, 150)
                        shade = pygame.Surface((room_rect.width, room_rect.height), pygame.SRCALPHA)
                        shade.fill(fill_col)
                        screen.blit(shade, room_rect.topleft)
                        pygame.draw.rect(screen, border_col, room_rect, 2, border_radius=4)
                        lbl = proximity_font.render(f"Fenster {room_idx + 1}", True, border_col)
                        screen.blit(lbl, (room_rect.centerx - lbl.get_width() // 2,
                                          room_rect.centery - lbl.get_height() // 2))

                    if ready:
                        info = "Klicke einen Fensterraum an, um ihn 20s lang zu öffnen"
                        info_col = (255, 210, 90)
                    else:
                        info = f"Nächste Fenster-Sabotage in {evelyn_cooldown_remaining:.1f}s"
                        info_col = (170, 175, 190)
                    # FIX: als Banner, das immer im Bild bleibt (bei kleiner Hoehe lag der Text vorher oberhalb)
                    hud.draw_banner(screen, info, max(6, mm_y - 46), info_col)

                player_mm_x = mm_x + int((my_player.rect.centerx / MAP_WIDTH_PX) * MINIMAP_WIDTH)
                player_mm_y = mm_y + int((my_player.rect.centery / MAP_HEIGHT_PX) * MINIMAP_HEIGHT)
                p_col = (150, 50, 50) if my_player.is_dead else (255, 30, 30)
                pygame.draw.circle(screen, p_col, (player_mm_x, player_mm_y), 8)
                pygame.draw.circle(screen, (255, 255, 255), (player_mm_x, player_mm_y), 8, 2)

            if meeting_active:
                draw_meeting()

            # NEU: Aktions-Buttons + Rollen-Info-Panel (immer ganz oben zeichnen)
            perf_mark("overlays")
            draw_action_buttons_layer()
            perf_mark("buttons")
            if task_manager.active_task is None and show_role_info:
                draw_role_info_panel()

            # NEU: Rauswurf-Animation (alle) und Todes-Animation (nur das Opfer) liegen ueber allem
            if eject_anim is not None:
                eject_anim.draw(screen)
            if death_anim is not None:
                death_anim.draw(screen)

            # NEU: Wer von Vladimir getötet wurde, sieht zuerst das komplette Anime-Intro.
            # Das Video liegt ganz oben und blockiert solange die Geister-Steuerung.
            if my_player.is_dead and ghost_video is not None and ghost_video.active:
                ghost_video.update()
                ghost_video.draw(screen)
                note = small_font.render("Vladimir hat dich getötet - warte, bis das Intro durch ist.",
                                         True, (235, 235, 240))
                note_bg = pygame.Rect(WIDTH // 2 - note.get_width() // 2 - 16, HEIGHT - 64,
                                      note.get_width() + 32, note.get_height() + 12)
                pygame.draw.rect(screen, (0, 0, 0), note_bg, border_radius=8)
                screen.blit(note, (WIDTH // 2 - note.get_width() // 2, note_bg.y + 6))
            elif ghost_intro_timer > 0 and my_player.is_dead:
                # Fallback, falls das Video nicht abgespielt werden kann
                fx.blit_alpha(screen, fx.dim_surface((WIDTH, HEIGHT)), (0, 0), 230)
                intro_txt = menu_font.render("Oshi no Ko Intro läuft...", True, (255, 255, 255))
                screen.blit(intro_txt, (WIDTH // 2 - intro_txt.get_width() // 2, HEIGHT // 2 - 20))
                sub_txt = small_font.render("(Vladimir hat dich getötet - Geister müssen kurz warten)", True, (180, 180, 180))
                screen.blit(sub_txt, (WIDTH // 2 - sub_txt.get_width() // 2, HEIGHT // 2 + 30))

        elif state in ("crew_win", "imposter_win", "independent_win"):
            # NEU: Sieg-/Niederlagen-Animation statt der statischen Texte
            if end_screen is None:
                start_end_screen(state)
            end_screen.draw(screen, my_id == host_id)

        perf_mark("render")
        if WEB_MODE:
            web_bridge.present(screen)   # Bild an den Browser schicken (statt Fenster)
        else:
            pygame.display.update()
        perf_mark("present")
        perf_frame_end()
        if BROWSER and browser_conn is not None:
            browser_conn.flush()         # alles in diesem Frame Gesendete in EINER Nachricht
            frame_work_ms = frame_work_ms * 0.95 + (time.perf_counter() - frame_work_start) * 50.0
            web_bridge.report_fps(clock.get_fps(), frame_work_ms)
        await asyncio.sleep(0)           # Browser/Event-Loop kurz arbeiten lassen

    shutdown_game()


def shutdown_game():
    """Aufraeumen nach der Hauptschleife. NEU: steht jetzt IN main_loop - im Browser kehrt
    asyncio.run() sofort zurueck, Code danach wuerde das laufende Spiel sofort beenden."""
    try: sock.close()
    except: pass
    pygame.quit()
    if WEB_MODE:
        web_bridge.hard_exit(0)


asyncio.run(main_loop())