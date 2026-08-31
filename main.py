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

import tasks
import roles
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
RAMONA_MIN_PLAYERS_CLIENT = 4  # muss zu RAMONA_MIN_PLAYERS in server.py passen
MAX_IMPOSTERS = 3

# Lauf-Animation: das Spielerbild wippt beim Gehen leicht nach oben
WALK_BOB_PIXELS = 3      # maximale Auslenkung nach oben in Pixeln
WALK_BOB_SPEED = 14.0    # Schwingungen pro Sekunde (Radiant/s)
WALK_IDLE_TIMEOUT = 0.15 # so lange gilt ein anderer Spieler nach der letzten Positionsmeldung als "laufend"

# Einsammelbare Rollen-Items (Raphi/Tappeihnachtsmann/Yoshi)
ITEM_SIZE = int(TILE_SIZE * 0.8)
ITEM_MIN_SPACING = 110   # Mindestabstand zwischen zwei Items, damit sie sich verteilen

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

        # NEU: Blickrichtung nur anhand der horizontalen Eingabe setzen (kein Sprung/Hüpfen,
        # nur ein reiner Links/Rechts-Flip des Bildes)
        if dx < 0:
            self.facing_left = True
        elif dx > 0:
            self.facing_left = False

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

def receive_data(sock):
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
                my_player.rect.x = spawnpoints[my_id].x
                my_player.rect.y = spawnpoints[my_id].y

                modifiers = struct.unpack("!B", sock.recv(1))[0]
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
                ramona_others_rights = {pid: 3 for pid in player_names.keys() if pid != my_id} if role_key == "ramona" else {}
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

                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: pass

            elif packet_type == 4:
                disconnect_data = sock.recv(9)
                if len(disconnect_data) == 9:
                    p_id, x, y = struct.unpack("!Bii", disconnect_data)
                    if p_id in other_players: del other_players[p_id]

            elif packet_type == 5:
                base_team_byte, role_id = struct.unpack("!BB", sock.recv(2))
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
                num_mates = struct.unpack("!B", sock.recv(1))[0]
                my_imposter_teammates = []
                for _ in range(num_mates):
                    mate_id = struct.unpack("!B", sock.recv(1))[0]
                    if mate_id != my_id:
                        my_imposter_teammates.append(mate_id)

            # NEU: Sync der vom Host aktivierten Rollen (auch für Nicht-Host-Clients zur Anzeige)
            elif packet_type == 14:
                mask = struct.unpack("!I", sock.recv(4))[0]
                enabled_roles = set(roles.keys_from_bitmask(mask))

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
                dead_id, no_corpse, weapon_id, death_flags = struct.unpack("!BBBB", sock.recv(4))
                dead_players.add(dead_id)
                if dead_id == my_id:
                    my_player.is_dead = True
                    # NEU: Nur wer von Vladimir getoetet wurde, muss das Anime-Intro abwarten
                    if death_flags & 1:
                        ghost_video = VideoPlayer(VLADIMIR_VIDEO_PATH)
                        # Ohne abspielbares Video bleibt es beim kurzen Warte-Bildschirm
                        ghost_intro_timer = 0.0 if ghost_video.active else VLADIMIR_INTRO_DURATION
                # Im Meeting rausgevotete Spieler hinterlassen keine Leiche (wie im Original-Spiel),
                # genauso wie Steinermikes Opfer (no_corpse) oder Evelyns Fensterfalle -
                # nur ein "echter" Mord außerhalb eines Meetings erzeugt eine meldbare Leiche.
                if not meeting_active and not no_corpse:
                    if dead_id == my_id:
                        dead_bodies[dead_id] = (my_player.rect.x, my_player.rect.y, weapon_id)
                    elif dead_id in other_players:
                        dead_bodies[dead_id] = (other_players[dead_id][0], other_players[dead_id][1], weapon_id)

            elif packet_type == 32:
                num_imps = struct.unpack("!B", sock.recv(1))[0]
                imposter_reveal_ids = []
                for _ in range(num_imps):
                    imposter_reveal_ids.append(struct.unpack("!B", sock.recv(1))[0])
                state = "imposter_win"

            elif packet_type == 40:
                caller_id, reason = struct.unpack("!BB", sock.recv(2))
                meeting_active = True
                # NEU: Erst wird nur diskutiert/gechattet, die Abstimmung kommt mit Paket 42
                meeting_phase = MEETING_PHASE_DISCUSSION
                meeting_timer = MEETING_DISCUSSION_TIME
                meeting_selected_target = None
                meeting_result_id = None
                meeting_caller_id = caller_id
                meeting_reason = reason
                has_voted = False
                player_votes.clear()
                meeting_chat_log.clear()
                meeting_chat_input = ""
                dead_bodies.clear()  # Nach einem Meeting (egal ob Knopf oder Leiche) sind alle Leichen weg
                if task_manager.active_task:
                    task_manager.reset_active_task()
                    task_manager.active_task = None
                show_minimap = False

            # NEU: Die Abstimmungsphase beginnt
            elif packet_type == 42:
                meeting_phase = MEETING_PHASE_VOTE
                meeting_timer = MEETING_VOTE_TIME
                meeting_selected_target = None

            elif packet_type == 41:
                voter_id, target_id = struct.unpack("!BB", sock.recv(2))
                player_votes[voter_id] = target_id

            elif packet_type == 50:
                sender_id, msg_len = struct.unpack("!BB", sock.recv(2))
                msg_bytes = b""
                while len(msg_bytes) < msg_len:
                    chunk = sock.recv(msg_len - len(msg_bytes))
                    if not chunk: break
                    msg_bytes += chunk
                message = msg_bytes.decode("utf-8", errors="replace")
                sender_name = player_names.get(sender_id, f"Spieler {sender_id}")
                meeting_chat_log.append(f"{sender_name}: {message}")

            elif packet_type == 43:
                # NEU: Der Server schickt mit, wer rausgeworfen wurde (255 = niemand)
                evicted_id = struct.unpack("!B", sock.recv(1))[0]
                meeting_result_id = evicted_id
                meeting_result_timer = 6.0
                meeting_active = False
                meeting_phase = MEETING_PHASE_NONE
                meeting_selected_target = None
                meeting_cooldown = 30.0
                # Alle Spieler auf fixe Spawnpoints zurücksetzen
                if my_id is not None and my_id < len(spawnpoints):
                    my_player.rect.x = spawnpoints[my_id].x
                    my_player.rect.y = spawnpoints[my_id].y
                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: pass

            # ===== ROLLEN-FÄHIGKEITEN =====

            # Evelyn: Fenster-Sabotage ist jetzt aktiv
            elif packet_type == 61:
                window_hazard_room = struct.unpack("!B", sock.recv(1))[0]
                window_hazard_until = time.time() + EVELYN_HAZARD_DURATION
                window_zone_timer = 0.0

            # NEU: Laurin hat eine Aufgabe fuer alle wieder unerledigt gemacht
            elif packet_type == 64:
                reset_idx = struct.unpack("!B", sock.recv(1))[0]
                if reset_idx in my_player.my_completed_tasks:
                    my_player.my_completed_tasks.remove(reset_idx)
                    reset_task_instance(reset_idx)
                    task_reset_banner_timer = 5.0
                    task_reset_banner_name = TASK_TEMPLATES[reset_idx]["name"] if reset_idx < len(TASK_TEMPLATES) else "?"

            # Vogelscheicher: Attrappen-Position eines anderen Spielers
            elif packet_type == 69:
                owner_id, dx, dy = struct.unpack("!Bii", sock.recv(9))
                decoys[owner_id] = [dx, dy, time.time() + VOGELSCHEICHER_INVISIBLE_DURATION]

            # Pleschbergsteiger: ein Geist wurde wiederbelebt
            elif packet_type == 74:
                revived_id = struct.unpack("!B", sock.recv(1))[0]
                dead_players.discard(revived_id)
                if revived_id in dead_bodies:
                    del dead_bodies[revived_id]
                if revived_id == my_id:
                    my_player.is_dead = False

            # Yoshi: Antwort auf die Rollen-Aufdeckung
            elif packet_type == 76:
                target_id, team_byte, target_role_id = struct.unpack("!BBB", sock.recv(3))
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
                target_id, new_rights = struct.unpack("!BB", sock.recv(2))
                ramona_others_rights[target_id] = new_rights

            # Eigenständig gewinnt (Ramona)
            elif packet_type == 82:
                winner_id = struct.unpack("!B", sock.recv(1))[0]
                independent_winner_id = winner_id
                state = "independent_win"

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
    # Dunkler Overlay-Hintergrund (wie die Map)
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(230)
    overlay.fill((15, 20, 30))
    screen.blit(overlay, (0, 0))

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
        name_txt = name_font.render(p_name, True, name_color)
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
        msg_surf = chat_font.render(msg, True, (230, 230, 230))
        screen.blit(msg_surf, (chat_rect.x + 10, y_off))
        y_off -= line_height

    # Eingabezeile
    pygame.draw.rect(screen, (245, 245, 245), chat_input_rect, border_radius=6)
    input_display = meeting_chat_input
    # Text abschneiden, falls er breiter als das Feld wird (neueste Zeichen bleiben sichtbar)
    while chat_font.size(input_display + "|")[0] > chat_input_rect.width - 16 and len(input_display) > 0:
        input_display = input_display[1:]
    input_surf = chat_font.render(input_display + "|", True, (20, 20, 20))
    screen.blit(input_surf, (chat_input_rect.x + 8, chat_input_rect.y + (chat_input_rect.height - input_surf.get_height()) // 2))

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
    """Wie viele Imposter maximal einstellbar sind: es muss immer mindestens ein
    Crewmate uebrig bleiben UND es muss mehr freundliche als feindliche Spieler geben."""
    if n_players < 3:
        return 1
    return max(1, min(MAX_IMPOSTERS, (n_players - 1) // 2))

def role_setup_status(enabled_set, n_players, n_imposters):
    """Prueft die Rollen-Konfiguration des Hosts vor dem Start.

    Regeln (aus der Aufgabenstellung):
      - Mindestens ein Imposter bzw. eine feindliche Rolle ist Pflicht.
      - Mindestens ein Crewmate ist Pflicht.
      - Es muss mehr freundliche als feindliche Spieler geben; Imposter zaehlen dabei
        komplett zur feindlichen Seite (auch die ohne eigene Spezialrolle).
      - Feindliche Spezialrollen belegen Imposter-Plaetze, es kann also nie mehr
        feindliche Spezialrollen geben als eingestellte Imposter.
      - Jede Spezialrolle wird hoechstens einmal vergeben, alle Rollen zusammen duerfen
        die Spielerzahl nicht ueberschreiten.

    Rueckgabe: (ok, meldung)"""
    friendly_n, enemy_n, independent_n = role_counts(enabled_set)

    if n_players < 2:
        return False, "Zu wenige Spieler verbunden."
    if n_imposters < 1:
        return False, "Mindestens ein Imposter ist Pflicht."
    if enemy_n > n_imposters:
        return False, f"Zu viele feindliche Rollen ({enemy_n}) fuer {n_imposters} Imposter."

    # Eigenstaendige bekommen einen eigenen Platz, aber nur bei genug Spielern
    ind_slots = independent_n if n_players >= RAMONA_MIN_PLAYERS_CLIENT else 0
    crew_slots = n_players - n_imposters - ind_slots
    if crew_slots < 1:
        return False, "Mindestens ein Crewmate ist Pflicht - zu wenige Spieler."
    if crew_slots <= n_imposters:
        return False, "Es muessen mehr freundliche als feindliche Spieler sein."
    if friendly_n > crew_slots:
        return False, f"Zu viele freundliche Rollen ({friendly_n}) fuer {crew_slots} Besatzungsplaetze."
    return True, "Konfiguration in Ordnung."

def current_role_setup_status():
    return role_setup_status(enabled_roles, max(1, len(player_names)), imposter_count)

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
    start_y = 200
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

def draw_role_select():
    screen.fill((18, 18, 26))
    title = menu_font.render("ROLLEN AUSWÄHLEN", True, (255, 255, 255))
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
    hint_text = chat_font.render(
        "Jede Spezialrolle wird höchstens einmal vergeben - nur die Imposter-Anzahl ist einstellbar. Der Rest ist Besatzung.",
        True, (170, 170, 180))
    screen.blit(hint_text, (WIDTH // 2 - hint_text.get_width() // 2, 154))

    rows, headers, back_rect = get_role_select_layout()

    for label, color, hx, hy in headers:
        h_text = small_font.render(label, True, color)
        screen.blit(h_text, (hx, hy))

    for key, row_rect, checkbox_rect in rows:
        is_on = key in enabled_roles
        info = roles.ROLES[key]
        row_bg = (40, 45, 55) if not is_on else (35, 60, 45)
        pygame.draw.rect(screen, row_bg, row_rect, border_radius=6)

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

def get_role_info_button_rect():
    """NEU: Button am rechten Bildschirmrand, ueber den man jederzeit die eigene
    Rollenbeschreibung nachlesen kann."""
    return pygame.Rect(WIDTH - 66, HEIGHT // 2 - 60, 52, 120)

def draw_role_info_button():
    btn = get_role_info_button_rect()
    bg = (90, 110, 210) if not show_role_info else (60, 75, 150)
    pygame.draw.rect(screen, bg, btn, border_radius=10)
    pygame.draw.rect(screen, (230, 235, 255), btn, 2, border_radius=10)

    thumb = get_role_image(my_player.role_key, ROLE_THUMB_SIZE) if my_player.role_key else None
    if thumb:
        screen.blit(thumb, (btn.centerx - ROLE_THUMB_SIZE // 2, btn.y + 8))
        label_y = btn.y + 12 + ROLE_THUMB_SIZE
    else:
        label_y = btn.y + 14

    # "ROLLE" senkrecht, damit es in den schmalen Button passt
    label = proximity_font.render("ROLLE", True, (255, 255, 255))
    label = pygame.transform.rotate(label, 90)
    screen.blit(label, (btn.centerx - label.get_width() // 2, label_y))
    key_hint = proximity_font.render("R", True, (230, 235, 255))
    screen.blit(key_hint, (btn.centerx - key_hint.get_width() // 2, btn.bottom - 16))

def draw_role_info_panel():
    """NEU: Zeigt Rollenbild, Name, Seite und Beschreibung - jederzeit im Spiel
    ueber den Button am Bildschirmrand (oder Taste R) aufrufbar."""
    panel_w = min(820, WIDTH - 120)
    panel_h = min(560, HEIGHT - 120)
    panel = pygame.Rect((WIDTH - panel_w) // 2, (HEIGHT - panel_h) // 2, panel_w, panel_h)

    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(170)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    pygame.draw.rect(screen, (18, 20, 28), panel, border_radius=14)
    pygame.draw.rect(screen, (90, 110, 200), panel, 3, border_radius=14)

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

    close_txt = proximity_font.render("R oder Klick auf den Button schließt dieses Fenster", True, (150, 155, 170))
    screen.blit(close_txt, (panel.centerx - close_txt.get_width() // 2, panel.bottom - 26))

def draw_ability_hud():
    """Zeigt rollenspezifische Cooldowns/Zähler links unten und globale Banner (Unsterblichkeit,
    Fenster-Gefahr) oben mittig an. Rein lesend - verändert keinen Zustand."""
    rk = my_player.role_key

    # Steuerungs-Hinweise unterhalb der Fortschrittsleiste (die liegt bei y=170..190)
    screen.blit(info_text4, (20, 200))
    screen.blit(info_text5, (20, 232))
    y = 272

    if my_player.role == "Imposter" and not my_player.is_dead:
        cd_txt = "Kill bereit!" if kill_cooldown_remaining <= 0 else f"Kill-Cooldown: {kill_cooldown_remaining:.1f}s"
        screen.blit(proximity_font.render(cd_txt, True, (255, 180, 180)), (20, y)); y += 20

    # NEU: Imposter sehen dauerhaft, wer noch im Team ist (und koennen sich nicht gegenseitig killen)
    mates = imposter_teammate_names()
    if mates:
        screen.blit(proximity_font.render("Mit-Imposter: " + ", ".join(mates), True, (255, 120, 120)), (20, y)); y += 20

    if rk == "monika":
        # NEU: Flagge setzen (F) und selbst entscheiden, wann man hinreist (G)
        if monika_flag_pos is None:
            txt = "F: Flagge platzieren"
        else:
            flag_part = "F: Flagge neu setzen" if monika_flag_cooldown <= 0 else f"Flagge neu in {monika_flag_cooldown:.1f}s"
            tp_part = "G: zur Flagge reisen!" if monika_teleport_cooldown <= 0 else f"Reise bereit in {monika_teleport_cooldown:.1f}s"
            txt = flag_part + "   |   " + tp_part
        screen.blit(proximity_font.render(txt, True, (255, 220, 150)), (20, y)); y += 20

    elif rk == "stroblpeter":
        if stroblpeter_marked_id is None:
            txt = "F: Spieler markieren"
        elif not stroblpeter_ready_to_strike:
            txt = f"Markiert - bereit in {max(0.0, stroblpeter_mark_timer):.1f}s"
        else:
            txt = "F: Zuschlagen!"
        screen.blit(proximity_font.render(txt, True, (255, 220, 150)), (20, y)); y += 20

    elif rk == "evelyn":
        # NEU: Der Raum wird auf der Karte ausgewaehlt (Evelyn hat ja keine Tasks dort)
        if evelyn_cooldown_remaining > 0:
            txt = f"Fenster-Cooldown: {evelyn_cooldown_remaining:.1f}s"
        else:
            txt = "Karte öffnen (M) und einen Fensterraum anklicken"
        screen.blit(proximity_font.render(txt, True, (255, 220, 150)), (20, y)); y += 20

    elif rk == "laurin":
        screen.blit(proximity_font.render(f"F bei einer Aufgabe: für alle zurücksetzen ({laurin_uses_left} übrig)", True, (255, 220, 150)), (20, y)); y += 20

    elif rk == "kaliyoga":
        txt = "F: Yoga-Notfallmeeting von überall" if not kaliyoga_bonus_used else "Yoga-Meeting bereits verbraucht"
        screen.blit(proximity_font.render(txt, True, (150, 220, 255)), (20, y)); y += 20

    elif rk == "david":
        marked_name = player_names.get(david_marked_id) if david_marked_id is not None else None
        txt = "F: Spieler fürs Verwürfeln markieren" + (f" (markiert: {marked_name})" if marked_name else "")
        screen.blit(proximity_font.render(txt, True, (255, 220, 150)), (20, y)); y += 20

    elif rk == "noah":
        if noah_trap_cooldown > 0:
            txt = f"Fallen-Cooldown: {noah_trap_cooldown:.1f}s ({len(noah_traps)}/{NOAH_TRAP_LIMIT} gelegt)"
        else:
            txt = f"F: Falle platzieren ({len(noah_traps)}/{NOAH_TRAP_LIMIT} gelegt)"
        screen.blit(proximity_font.render(txt, True, (255, 220, 150)), (20, y)); y += 20

    elif rk == "vogelscheicher":
        remaining = vogelscheicher_invisible_until - time.time()
        txt = "F: Attrappe + Unsichtbarkeit" if remaining <= 0 else f"Unsichtbar noch {remaining:.1f}s"
        screen.blit(proximity_font.render(txt, True, (150, 220, 255)), (20, y)); y += 20

    elif rk == "pleschbergsteiger":
        screen.blit(proximity_font.render(f"F bei Geist: Wiederbeleben ({pleschbergsteiger_uses_left} übrig)", True, (150, 220, 255)), (20, y)); y += 20

    elif rk == "yoshi":
        txt = f"F beim Standard: einsammeln ({yoshi_finds}/{YOSHI_FIND_LIMIT})"
        if yoshi_reveals_left > 0:
            txt += f"  |  F bei Spieler: Rolle aufdecken ({yoshi_reveals_left}x)"
        screen.blit(proximity_font.render(txt, True, (150, 220, 255)), (20, y)); y += 20
        if yoshi_reveal_result is not None and yoshi_reveal_timer > 0:
            target_id, team_str, role_name = yoshi_reveal_result
            reveal_txt = small_font.render(f"{player_names.get(target_id, '?')} ist: {role_name} ({team_str})", True, (255, 255, 100))
            screen.blit(reveal_txt, (WIDTH // 2 - reveal_txt.get_width() // 2, 200))

    elif rk == "tappeihnachtsmann":
        screen.blit(proximity_font.render(f"F beim Geschenk: einsammeln ({len(tappeihnachtsmann_find_points)} übrig)", True, (150, 220, 255)), (20, y)); y += 20

    elif rk == "raphi":
        screen.blit(proximity_font.render(f"F bei der Flasche: einsammeln ({raphi_collected}/10)", True, (150, 220, 255)), (20, y)); y += 20

    elif rk == "ramona":
        forge_remaining = RAMONA_FORGE_COOLDOWN_CLIENT - (time.time() - ramona_last_forge)
        txt = "F bei Spieler: Unterschrift fälschen" if forge_remaining <= 0 else f"Fälschen-Cooldown: {forge_remaining:.1f}s"
        screen.blit(proximity_font.render(txt, True, (255, 210, 90)), (20, y)); y += 20
        if ramona_others_rights:
            rights_str = ", ".join(f"{player_names.get(pid, '?')}:{v}" for pid, v in ramona_others_rights.items())
            screen.blit(proximity_font.render(f"Rechte -> {rights_str}", True, (255, 210, 90)), (20, y)); y += 20
        if ramona_stand_timer > 0:
            screen.blit(proximity_font.render(f"Stehe am Regal: {ramona_stand_timer:.1f}/{RAMONA_WIN_STAND_TIME:.0f}s", True, (100, 255, 130)), (20, y)); y += 20

    elif rk == "poeschl_froeschl":
        my_center = my_player.rect.center
        nearest, nearest_dist = None, None
        for d_id, (dx, dy, _w) in dead_bodies.items():
            body_center = (dx + PLAYER_SIZE // 2, dy + PLAYER_SIZE // 2)
            dist = math.hypot(my_center[0] - body_center[0], my_center[1] - body_center[1])
            if nearest_dist is None or dist < nearest_dist:
                nearest_dist, nearest = dist, body_center
        if nearest is not None:
            angle = math.atan2(nearest[1] - my_center[1], nearest[0] - my_center[0])
            ax, ay = WIDTH // 2, 200
            ex, ey = ax + math.cos(angle) * 30, ay + math.sin(angle) * 30
            pygame.draw.line(screen, (255, 200, 0), (ax, ay), (ex, ey), 4)
            pygame.draw.circle(screen, (255, 200, 0), (int(ex), int(ey)), 6)
            screen.blit(proximity_font.render("Leiche in der Nähe!", True, (255, 200, 0)), (ax - 60, ay + 20))

    # Globale Banner (für alle Spieler sichtbar, unabhängig von der eigenen Rolle)
    banner_y = 170
    if immortal_banner_timer > 0:
        banner = small_font.render(f"UNSTERBLICHKEIT AKTIV ({immortal_banner_timer:.1f}s)", True, (255, 230, 80))
        screen.blit(banner, (WIDTH // 2 - banner.get_width() // 2, banner_y))
        banner_y += 30
    if time.time() < window_hazard_until:
        banner = small_font.render("GEFAHR: Fenster offen - nicht in Fensterräumen aufhalten!", True, (255, 90, 90))
        screen.blit(banner, (WIDTH // 2 - banner.get_width() // 2, banner_y))

def draw_lobby():
    camera_x = my_player.rect.x - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)
    camera_y = my_player.rect.y - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)

    internal_surface.fill((20, 20, 30))
    internal_surface.blit(lobby_bg, (-camera_x, -camera_y))

    for p_id, pos in other_players.items():
        enemy_img = player_images.get(p_id % len(player_images))
        if enemy_img:
            if player_facing_left.get(p_id):
                enemy_img = pygame.transform.flip(enemy_img, True, False)
            internal_surface.blit(enemy_img, (pos[0] - camera_x, pos[1] - camera_y + get_walk_offset(p_id)))
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

    if my_id == host_id:
        btn = pygame.Rect(WIDTH - 240, HEIGHT - 100, 200, 60)
        btn_color = (0, 220, 100) if roles_valid else (90, 90, 90)
        # (roles_valid stammt aus current_role_setup_status() weiter oben)
        pygame.draw.rect(screen, btn_color, btn, border_radius=10)
        txt = small_font.render("START", True, (0, 0, 0) if roles_valid else (180, 180, 180))
        screen.blit(txt, (btn.centerx - txt.get_width() // 2, btn.centery - txt.get_height() // 2))

        btn_roles = pygame.Rect(40, HEIGHT - 100, 200, 60)
        pygame.draw.rect(screen, (70, 100, 220), btn_roles, border_radius=10)
        roles_txt = small_font.render("ROLLEN", True, (255, 255, 255))
        screen.blit(roles_txt, (btn_roles.centerx - roles_txt.get_width() // 2, btn_roles.centery - roles_txt.get_height() // 2))

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

while running:
    dt = clock.tick(60) / 1000.0
    was_task_active = task_manager.active_task is not None

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

    for event in pygame.event.get():
        # NEU: True, sobald ein Klick vom Rollen-Info-Panel verbraucht wurde (dann nicht abstimmen)
        role_info_click_consumed = False

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
                btn_roles = pygame.Rect(40, HEIGHT - 100, 200, 60)
                btn_minus = pygame.Rect(WIDTH // 2 - 100, HEIGHT - 155, 40, 40)
                btn_plus = pygame.Rect(WIDTH // 2 + 60, HEIGHT - 155, 40, 40)

                if btn.collidepoint(event.pos):
                    if current_role_setup_status()[0]:
                        try: sock.sendall(struct.pack("!B", 99))
                        except: pass
                elif btn_roles.collidepoint(event.pos):
                    state = "role_select"
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
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                state = "lobby"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                rows, headers, back_rect = get_role_select_layout()
                if back_rect.collidepoint(event.pos):
                    state = "lobby"
                elif my_id == host_id:
                    for key, row_rect, checkbox_rect in rows:
                        if row_rect.collidepoint(event.pos):
                            new_state = 0 if key in enabled_roles else 1
                            try: sock.sendall(struct.pack("!BBB", 13, roles.role_id_of(key), new_state))
                            except: pass
                            break

        elif state == "game":
            # NEU: Klick auf den Rollen-Button am Bildschirmrand (funktioniert auch im Meeting)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and task_manager.active_task is None:
                if get_role_info_button_rect().collidepoint(event.pos):
                    show_role_info = not show_role_info
                    role_info_click_consumed = True
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
                    if event.key == pygame.K_RETURN:
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
                else:
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
                        elif at_meeting_box and not my_player.is_dead and meeting_cooldown <= 0:
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

        task_manager.handle_event(event)

    moved_this_frame = False

    if state == "game" and task_manager.active_task is None and not show_minimap and not show_role_info and game_started:
        # NEU: Normale WASD Bewegung blockieren, falls man im Vent sitzt oder (Vladimir) noch
        # als frisch getöteter Geist das Intro abwarten muss
        if not my_player.is_venting and not meeting_active and not ghost_intro_blocking():
            moved_this_frame = my_player.move(pygame.key.get_pressed(), hitboxes)
            if moved_this_frame:
                try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
                except: running = False

    elif state == "lobby" and not game_started and my_id is not None:
        moved_this_frame = my_player.move(pygame.key.get_pressed(), lobby_hitboxes)
        if moved_this_frame:
            try: sock.sendall(struct.pack('!Bii', 2, int(my_player.rect.x), int(my_player.rect.y)))
            except: running = False

    elif state in ["crew_win", "imposter_win", "independent_win"]:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if my_id == host_id:
                    try: sock.sendall(struct.pack("!B", 23))
                    except: pass

    # NEU: Laufanimation fortschreiben - eigener Spieler und alle anderen
    if my_id is not None:
        my_player.update_walk_anim(dt, moved_this_frame)
    update_other_walk_anims(dt)

    # --- RENDERING ---
    if state == "menu":
        draw_menu()
    elif state == "lobby" and not game_started:
        draw_lobby()
    elif state == "role_select":
        draw_role_select()
    elif state == "game":
        camera_x = my_player.rect.x - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)
        camera_y = my_player.rect.y - (INTERNAL_SIZE // 2) + (PLAYER_SIZE // 2)

        internal_surface.fill((40, 80, 40))
        internal_surface.blit(floor_img, (-camera_x, -camera_y))
        internal_surface.blit(walls_img, (-camera_x, -camera_y))
        internal_surface.blit(objects_img, (-camera_x, -camera_y))

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
                name_text = name_font.render(e_name, True, name_color)
                name_text.set_alpha(current_alpha)
                nx = (pos[0] - camera_x) + (PLAYER_SIZE // 2) - (name_text.get_width() // 2)
                ny = (pos[1] - camera_y) - 16
                internal_surface.blit(name_text, (nx, ny))

        # NEU: Eigene platzierte Noah-Fallen (nur für Noah selbst sichtbar, eigene Textur)
        if my_player.role_key == "noah" and noah_traps:
            trap_img = item_images.get("falle")
            if trap_img:
                for tx, ty in noah_traps:
                    internal_surface.blit(trap_img, (tx - camera_x - ITEM_SIZE // 2,
                                                     ty - camera_y - ITEM_SIZE // 2))

        # NEU: Monikas gesetzte Flagge (nur für Monika selbst sichtbar, eigene Textur)
        if monika_flag_pos is not None and my_player.role_key == "monika":
            flag_img = item_images.get("flagge")
            if flag_img:
                internal_surface.blit(flag_img, (monika_flag_pos[0] - camera_x - ITEM_SIZE // 2,
                                                 monika_flag_pos[1] - camera_y - ITEM_SIZE // 2))

        # Eigenen Spieler zeichnen
        my_player.draw(internal_surface, camera_x, camera_y)
        my_name = player_names.get(my_id, "Ich")
        my_name_text = name_font.render(my_name, True, (255, 255, 255))
        if my_player.is_dead or my_player.is_venting: my_name_text.set_alpha(128)
        internal_surface.blit(my_name_text, ((my_player.rect.x - camera_x) + (PLAYER_SIZE // 2) - (my_name_text.get_width() // 2), (my_player.rect.y - camera_y) - 16))

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
                    # Index mitschicken, damit Laurin gezielt genau diese Aufgabe zuruecksetzen kann
                    try: sock.sendall(struct.pack("!BB", 20, active_task_idx))
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

        status_str = f"Rolle: {my_player.role_display_name} {'(GEIST)' if my_player.is_dead else ('(VENT)' if my_player.is_venting else '')}"
        role_hud = small_font.render(status_str, True, (255, 100, 100) if (my_player.is_dead or my_player.is_venting) else (255, 255, 255))
        screen.blit(role_hud, (20, 20))
        screen.blit(info_text1, (20, 80))
        screen.blit(info_text2, (20, 110))
        screen.blit(info_text3, (20, 140))

        draw_ability_hud()

        if intro_timer > 0:
            intro_timer -= 1
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(180)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))

            title_color = (255, 50, 50) if my_player.role == "Imposter" else ((255, 210, 90) if my_player.role == "Independent" else (50, 200, 255))
            role_text = menu_font.render(f"DU BIST: {my_player.role_display_name.upper()}", True, title_color)

            img_y = HEIGHT // 2 - 60 - ROLE_REVEAL_SIZE - 20
            if my_player.role_image:
                screen.blit(my_player.role_image, (WIDTH // 2 - ROLE_REVEAL_SIZE // 2, img_y))

            desc_text = wrap_text_render(my_player.role_desc, small_font, (255, 255, 255), WIDTH - 200)
            screen.blit(role_text, (WIDTH // 2 - role_text.get_width() // 2, HEIGHT // 2 - 60))

            # NEU: kurz sagen, auf welcher Seite man steht
            tl_text, tl_color = team_label()
            team_surf = small_font.render(tl_text, True, tl_color)
            screen.blit(team_surf, (WIDTH // 2 - team_surf.get_width() // 2, HEIGHT // 2 - 18))

            desc_y = HEIGHT // 2 + 20
            for line_surf in desc_text:
                screen.blit(line_surf, (WIDTH // 2 - line_surf.get_width() // 2, desc_y))
                desc_y += line_surf.get_height() + 4

            # NEU: Imposter erfahren beim Rollen-Reveal, wer noch im Team ist
            mates = imposter_teammate_names()
            if mates:
                mate_surf = small_font.render("Deine Mit-Imposter: " + ", ".join(mates), True, (255, 120, 120))
                screen.blit(mate_surf, (WIDTH // 2 - mate_surf.get_width() // 2, desc_y + 10))
                desc_y += mate_surf.get_height() + 14
                kill_hint = chat_font.render("Ihr könnt euch gegenseitig nicht töten.", True, (220, 160, 160))
                screen.blit(kill_hint, (WIDTH // 2 - kill_hint.get_width() // 2, desc_y))

            hint_surf = chat_font.render("Taste R oder der Button am rechten Rand zeigt die Rolle jederzeit erneut.", True, (170, 175, 190))
            screen.blit(hint_surf, (WIDTH // 2 - hint_surf.get_width() // 2, HEIGHT - 70))

        # NEU: Ergebnis der letzten Abstimmung kurz einblenden
        if meeting_result_timer > 0 and not meeting_active:
            if meeting_result_id is None or meeting_result_id == 255:
                res_str, res_col = "Niemand wurde rausgeworfen.", (200, 200, 210)
            else:
                res_name = player_names.get(meeting_result_id, f"Spieler {meeting_result_id}")
                res_str, res_col = f"{res_name} wurde rausgeworfen!", (255, 120, 120)
            res_txt = small_font.render(res_str, True, res_col)
            res_bg = pygame.Rect(WIDTH // 2 - res_txt.get_width() // 2 - 16, 34,
                                 res_txt.get_width() + 32, res_txt.get_height() + 12)
            pygame.draw.rect(screen, (18, 20, 28), res_bg, border_radius=8)
            pygame.draw.rect(screen, res_col, res_bg, 2, border_radius=8)
            screen.blit(res_txt, (WIDTH // 2 - res_txt.get_width() // 2, res_bg.y + 6))

        # NEU: Hinweis, dass Laurin eine Aufgabe fuer alle zurueckgesetzt hat
        if task_reset_banner_timer > 0:
            reset_txt = small_font.render(f"Aufgabe sabotiert: {task_reset_banner_name} muss neu erledigt werden!",
                                          True, (255, 180, 90))
            reset_bg = pygame.Rect(WIDTH // 2 - reset_txt.get_width() // 2 - 16, 84,
                                   reset_txt.get_width() + 32, reset_txt.get_height() + 12)
            pygame.draw.rect(screen, (25, 20, 15), reset_bg, border_radius=8)
            pygame.draw.rect(screen, (255, 180, 90), reset_bg, 2, border_radius=8)
            screen.blit(reset_txt, (WIDTH // 2 - reset_txt.get_width() // 2, reset_bg.y + 6))

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
                info_txt = small_font.render(info, True, info_col)
                screen.blit(info_txt, (WIDTH // 2 - info_txt.get_width() // 2, mm_y - 46))

            player_mm_x = mm_x + int((my_player.rect.centerx / MAP_WIDTH_PX) * MINIMAP_WIDTH)
            player_mm_y = mm_y + int((my_player.rect.centery / MAP_HEIGHT_PX) * MINIMAP_HEIGHT)
            p_col = (150, 50, 50) if my_player.is_dead else (255, 30, 30)
            pygame.draw.circle(screen, p_col, (player_mm_x, player_mm_y), 8)
            pygame.draw.circle(screen, (255, 255, 255), (player_mm_x, player_mm_y), 8, 2)

        if meeting_active:
            draw_meeting()

        # NEU: Button am Bildschirmrand + Rollen-Info-Panel (immer ganz oben zeichnen)
        if task_manager.active_task is None:
            draw_role_info_button()
            if show_role_info:
                draw_role_info_panel()

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
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(230)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))
            intro_txt = menu_font.render("Oshi no Ko Intro läuft...", True, (255, 255, 255))
            screen.blit(intro_txt, (WIDTH // 2 - intro_txt.get_width() // 2, HEIGHT // 2 - 20))
            sub_txt = small_font.render("(Vladimir hat dich getötet - Geister müssen kurz warten)", True, (180, 180, 180))
            screen.blit(sub_txt, (WIDTH // 2 - sub_txt.get_width() // 2, HEIGHT // 2 + 30))

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

    elif state == "independent_win":
        screen.fill((30, 24, 10))
        win_title = menu_font.render("EIGENSTÄNDIG GEWINNT!", True, (255, 210, 90))
        winner_name = player_names.get(independent_winner_id, "Unbekannt")
        win_sub = small_font.render(f"{winner_name} hat das eigene Ziel erreicht.", True, (255, 255, 255))
        # Eine eigenständige Rolle gewinnt allein - Besatzung UND Imposter verlieren zusammen
        win_sub2 = small_font.render("Besatzung UND Imposter haben verloren.", True, (255, 120, 120))
        screen.blit(win_title, (WIDTH // 2 - win_title.get_width() // 2, HEIGHT // 2 - 100))
        screen.blit(win_sub, (WIDTH // 2 - win_sub.get_width() // 2, HEIGHT // 2 - 40))
        screen.blit(win_sub2, (WIDTH // 2 - win_sub2.get_width() // 2, HEIGHT // 2))

        if my_id == host_id: back_txt = small_font.render("Drücke ENTER, um alle in die Lobby zurückzuholen", True, (255, 255, 255))
        else: back_txt = small_font.render("Warte auf den Host für Lobby-Rückkehr...", True, (150, 150, 150))
        screen.blit(back_txt, (WIDTH // 2 - back_txt.get_width() // 2, HEIGHT // 2 + 100))

    pygame.display.update()

try: sock.close()
except: pass
pygame.quit()