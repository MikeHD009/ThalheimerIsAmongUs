"""NEU: Uebersichtlicheres HUD - Aktions-Buttons (Toeten, Benutzen/Melden, Vent, Rollen-Faehigkeit,
Karte, Rolle) mit Symbol, Tastenhinweis, Cooldown-Anzeige und Zaehler.

main.py entscheidet, WELCHE Buttons gerade sinnvoll sind (ButtonSpec-Liste); dieses Modul
kuemmert sich nur um Layout und Zeichnen. Jeder Button kann auch angeklickt werden - main.py
loest dann einfach denselben Tastendruck aus wie die Tastatur.
"""
import math
import time

import pygame

from fx import font, clamp, text

# NEU (Leistung): fertige Button-/Karten-/Banner-Bilder wiederverwenden. Ein Button wird nur neu
# gezeichnet, wenn sich sein Zustand aendert (Beschriftung, Cooldown-Schritt, Zaehler ...).
_BUTTON_CACHE = {}
_CARD_CACHE = {}
_BANNER_CACHE = {}

# Farben je Button-Art
COL_KILL = (235, 60, 60)
COL_USE = (80, 190, 255)
COL_REPORT = (255, 150, 40)
COL_EMERGENCY = (255, 70, 70)
COL_VENT = (90, 220, 120)
COL_ABILITY = (190, 120, 255)
COL_NEUTRAL = (170, 180, 200)
COL_GOLD = (255, 210, 90)

PANEL_BG = (16, 18, 26, 215)


class ButtonSpec:
    def __init__(self, key_code, key_label, label, icon, color, enabled=True, cooldown=0.0,
                 cooldown_text="", badge="", image=None, small=False, active=False):
        self.key_code = key_code          # pygame-Taste, die ein Klick ausloest
        self.key_label = key_label        # z.B. "E"
        self.label = label                # z.B. "TÖTEN"
        self.icon = icon                  # Name der Symbol-Funktion (siehe ICONS)
        self.color = color
        self.enabled = enabled
        # 0..1 verbleibender Anteil - in 1/40-Schritten, damit sich das Bild nicht jeden Frame aendert
        self.cooldown = math.ceil(clamp(cooldown) * 40) / 40.0
        self.cooldown_text = cooldown_text
        self.badge = badge                # z.B. "3" oder "2/3"
        self.image = image                # Rollenbild statt Symbol
        self.small = small                # kleiner Neben-Button (Karte/Rolle)
        self.active = active              # gerade eingeschaltet (z.B. Karte offen)
        self.rect = pygame.Rect(0, 0, 0, 0)


# =========================
# SYMBOLE (reine Vektorgrafik)
# =========================
def _icon_kill(s, c, r, col):
    cx, cy = c
    ang = math.radians(-45)
    ca, sa = math.cos(ang), math.sin(ang)

    def rot(px, py):
        return (cx + px * ca - py * sa, cy + px * sa + py * ca)
    blade = [rot(-r * 0.15, -r * 0.13), rot(r * 0.85, -r * 0.05), rot(r * 0.95, 0), rot(r * 0.85, r * 0.12), rot(-r * 0.15, r * 0.13)]
    pygame.draw.polygon(s, (225, 230, 240), blade)
    pygame.draw.polygon(s, (120, 125, 140), blade, 2)
    guard = [rot(-r * 0.2, -r * 0.3), rot(-r * 0.12, -r * 0.3), rot(-r * 0.12, r * 0.3), rot(-r * 0.2, r * 0.3)]
    pygame.draw.polygon(s, col, guard)
    handle = [rot(-r * 0.85, -r * 0.12), rot(-r * 0.2, -r * 0.12), rot(-r * 0.2, r * 0.12), rot(-r * 0.85, r * 0.12)]
    pygame.draw.polygon(s, (110, 70, 45), handle)


def _icon_use(s, c, r, col):
    cx, cy = c
    board = pygame.Rect(0, 0, int(r * 1.2), int(r * 1.55))
    board.center = (cx, cy + int(r * 0.05))
    pygame.draw.rect(s, (200, 160, 110), board, border_radius=6)
    paper = board.inflate(-int(r * 0.25), -int(r * 0.35))
    paper.y += int(r * 0.08)
    pygame.draw.rect(s, (245, 245, 250), paper, border_radius=3)
    clip = pygame.Rect(0, 0, int(r * 0.55), int(r * 0.25))
    clip.center = (cx, board.top + 2)
    pygame.draw.rect(s, (150, 155, 170), clip, border_radius=4)
    for i in range(3):
        y = paper.top + int(paper.height * (0.25 + 0.27 * i))
        pygame.draw.line(s, col, (paper.left + 6, y), (paper.left + 12, y + 5), 3)
        pygame.draw.line(s, col, (paper.left + 12, y + 5), (paper.left + 20, y - 5), 3)
        pygame.draw.line(s, (170, 170, 180), (paper.left + 26, y), (paper.right - 6, y), 3)


def _icon_report(s, c, r, col):
    cx, cy = c
    cone = [(cx - r * 0.5, cy - r * 0.25), (cx + r * 0.35, cy - r * 0.7), (cx + r * 0.35, cy + r * 0.7), (cx - r * 0.5, cy + r * 0.25)]
    pygame.draw.polygon(s, col, cone)
    pygame.draw.rect(s, (230, 230, 235), (cx - r * 0.8, cy - r * 0.25, r * 0.32, r * 0.5), border_radius=3)
    for i in range(1, 3):
        rect = pygame.Rect(0, 0, int(r * (0.5 + 0.45 * i)), int(r * (0.7 + 0.5 * i)))
        rect.center = (int(cx + r * 0.35), cy)
        pygame.draw.arc(s, (255, 255, 255), rect, -0.9, 0.9, 3)


def _icon_emergency(s, c, r, col):
    cx, cy = c
    pygame.draw.ellipse(s, (120, 125, 140), (cx - r * 0.9, cy + r * 0.05, r * 1.8, r * 0.7))
    pygame.draw.ellipse(s, (150, 20, 20), (cx - r * 0.65, cy - r * 0.35, r * 1.3, r * 0.75))
    pygame.draw.ellipse(s, col, (cx - r * 0.65, cy - r * 0.55, r * 1.3, r * 0.75))
    pygame.draw.ellipse(s, (255, 170, 170), (cx - r * 0.35, cy - r * 0.45, r * 0.45, r * 0.22))


def _icon_vent(s, c, r, col):
    cx, cy = c
    rect = pygame.Rect(0, 0, int(r * 1.7), int(r * 1.25))
    rect.center = c
    pygame.draw.rect(s, (70, 75, 88), rect, border_radius=8)
    pygame.draw.rect(s, (160, 165, 180), rect, 3, border_radius=8)
    for i in range(4):
        y = rect.top + int(rect.height * (0.2 + 0.2 * i))
        pygame.draw.line(s, (25, 27, 33), (rect.left + 8, y), (rect.right - 8, y), 4)
    pygame.draw.polygon(s, col, [(cx - r * 0.2, cy - r * 0.95), (cx + r * 0.2, cy - r * 0.95), (cx, cy - r * 0.62)])


def _icon_map(s, c, r, col):
    cx, cy = c
    pts = [(cx - r * 0.9, cy - r * 0.6), (cx - r * 0.3, cy - r * 0.8), (cx + r * 0.3, cy - r * 0.6), (cx + r * 0.9, cy - r * 0.8),
           (cx + r * 0.9, cy + r * 0.6), (cx + r * 0.3, cy + r * 0.8), (cx - r * 0.3, cy + r * 0.6), (cx - r * 0.9, cy + r * 0.8)]
    pygame.draw.polygon(s, (225, 215, 180), pts)
    pygame.draw.polygon(s, (120, 105, 70), pts, 2)
    pygame.draw.line(s, (170, 150, 110), (cx - r * 0.3, cy - r * 0.8), (cx - r * 0.3, cy + r * 0.6), 2)
    pygame.draw.line(s, (170, 150, 110), (cx + r * 0.3, cy - r * 0.6), (cx + r * 0.3, cy + r * 0.8), 2)
    pygame.draw.circle(s, col, (int(cx + r * 0.05), int(cy - r * 0.05)), max(3, int(r * 0.18)))


def _icon_role(s, c, r, col):
    cx, cy = c
    pygame.draw.circle(s, col, (cx, int(cy - r * 0.3)), int(r * 0.38))
    pygame.draw.ellipse(s, col, (cx - r * 0.7, cy + r * 0.1, r * 1.4, r * 0.9))


def _icon_flag(s, c, r, col):
    cx, cy = c
    pygame.draw.line(s, (220, 220, 225), (cx - r * 0.5, cy - r * 0.8), (cx - r * 0.5, cy + r * 0.85), 4)
    pygame.draw.polygon(s, col, [(cx - r * 0.45, cy - r * 0.8), (cx + r * 0.7, cy - r * 0.5), (cx - r * 0.45, cy - r * 0.15)])


def _icon_star(s, c, r, col):
    cx, cy = c
    pts = []
    for i in range(10):
        rr = r * (0.9 if i % 2 == 0 else 0.4)
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(s, col, pts)


ICONS = {
    "kill": _icon_kill, "use": _icon_use, "report": _icon_report, "emergency": _icon_emergency,
    "vent": _icon_vent, "map": _icon_map, "role": _icon_role, "flag": _icon_flag, "star": _icon_star,
}


# =========================
# LAYOUT
# =========================
def side_panel_rects(screen_w, screen_h):
    """Linke/rechte Leiste neben der quadratischen Spielwelt."""
    sq = min(screen_w, screen_h)
    side = (screen_w - sq) // 2
    left = pygame.Rect(0, 0, side, screen_h)
    right = pygame.Rect(screen_w - side, 0, side, screen_h)
    return left, right


def layout_buttons(specs, screen_w, screen_h):
    """Ordnet die Buttons unten rechts in der rechten Leiste an (2 Spalten, von unten nach oben).
    Kleine Buttons (Karte/Rolle) kommen in eine eigene Reihe darueber."""
    _left, right = side_panel_rects(screen_w, screen_h)
    scale = screen_h / 810.0
    gap = int(12 * scale)
    margin = int(18 * scale)
    big = int(116 * scale)
    avail = max(right.width, 140) - 2 * margin
    if 2 * big + gap > avail:
        big = max(64, (avail - gap) // 2)
    small = int(big * 0.62)
    x_right = screen_w - margin

    main_specs = [s for s in specs if not s.small]
    small_specs = [s for s in specs if s.small]
    y = screen_h - margin
    for i, spec in enumerate(main_specs):
        col = i % 2
        row = i // 2
        x = x_right - big - col * (big + gap)
        spec.rect = pygame.Rect(x, y - big - row * (big + gap), big, big)
    rows = (len(main_specs) + 1) // 2
    y_small = y - rows * (big + gap) - small
    for i, spec in enumerate(small_specs):
        spec.rect = pygame.Rect(x_right - small - i * (small + gap), y_small, small, small)
    return specs


def draw_buttons(screen, specs):
    t = time.time()
    for spec in specs:
        if spec.rect.width <= 0:
            continue
        key = (spec.rect.size, spec.key_label, spec.label, spec.icon, spec.color, spec.enabled, spec.cooldown,
               spec.cooldown_text, spec.badge, id(spec.image) if spec.image is not None else 0, spec.small, spec.active)
        surf = _BUTTON_CACHE.get(key)
        if surf is None:
            if len(_BUTTON_CACHE) > 300:
                _BUTTON_CACHE.clear()
            surf = _render_button(spec, t)
            _BUTTON_CACHE[key] = surf
        screen.blit(surf, spec.rect)


def _render_button(spec, t):
    r = spec.rect
    surf = pygame.Surface(r.size, pygame.SRCALPHA)
    local = surf.get_rect()
    radius = max(8, r.width // 6)
    col = spec.color if spec.enabled else (110, 112, 122)

    pygame.draw.rect(surf, (18, 20, 28, 225), local, border_radius=radius)
    if spec.active:
        pygame.draw.rect(surf, (*col, 70), local, border_radius=radius)

    # Symbol bzw. Rollenbild
    icon_c = (local.centerx, int(local.height * (0.42 if not spec.small else 0.45)))
    icon_r = int(local.width * (0.27 if not spec.small else 0.3))
    if spec.image is not None:
        size = int(icon_r * 2.1)
        img = pygame.transform.smoothscale(spec.image, (size, size))
        surf.blit(img, img.get_rect(center=icon_c))
    else:
        fn = ICONS.get(spec.icon)
        if fn:
            fn(surf, icon_c, icon_r, col)

    if not spec.small:
        lbl_font = font(max(10, int(local.width * 0.125)))
        lbl = lbl_font.render(spec.label, True, (255, 255, 255) if spec.enabled else (160, 162, 170))
        if lbl.get_width() > local.width - 8:
            lbl = pygame.transform.smoothscale(lbl, (local.width - 8, lbl.get_height()))
        surf.blit(lbl, lbl.get_rect(center=(local.centerx, int(local.height * 0.84))))

    # Cooldown: dunkles Tortenstueck + verbleibende Sekunden
    if spec.cooldown > 0:
        shade = pygame.Surface(r.size, pygame.SRCALPHA)
        cx, cy = local.center
        rad = local.width
        pts = [(cx, cy)]
        steps = max(2, int(36 * spec.cooldown))
        for i in range(steps + 1):
            a = -math.pi / 2 + (i / steps) * spec.cooldown * math.tau
            pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
        pygame.draw.polygon(shade, (0, 0, 0, 150), pts)
        mask = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), local, border_radius=radius)
        shade.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(shade, (0, 0))
        if spec.cooldown_text:
            cd = font(max(12, int(local.width * 0.3))).render(spec.cooldown_text, True, (255, 255, 255))
            sh = font(max(12, int(local.width * 0.3))).render(spec.cooldown_text, True, (0, 0, 0))
            rr = cd.get_rect(center=(local.centerx, int(local.height * 0.42)))
            surf.blit(sh, rr.move(2, 2))
            surf.blit(cd, rr)

    # Rahmen: bereit = leuchtend + pulsierend
    ready = spec.enabled and spec.cooldown <= 0
    border_w = max(2, r.width // 30)
    if ready and not spec.small:
        # bewusst ohne Pulsieren: ein ruhiges Bild spart im Web-Modus Bandbreite
        pygame.draw.rect(surf, (*col, 60), local.inflate(-border_w * 2, -border_w * 2), border_w + 2, border_radius=radius)
        pygame.draw.rect(surf, col, local, border_w + 1, border_radius=radius)
    else:
        pygame.draw.rect(surf, (*col, 200) if spec.enabled else (80, 82, 92, 220), local, border_w, border_radius=radius)

    # Tastenhinweis oben links
    kf = font(max(9, int(local.width * (0.13 if not spec.small else 0.2))))
    key_s = kf.render(spec.key_label, True, (20, 20, 25))
    kr = pygame.Rect(0, 0, max(key_s.get_width() + 10, key_s.get_height() + 4), key_s.get_height() + 2)
    kr.topleft = (5, 5)
    pygame.draw.rect(surf, (235, 235, 240) if spec.enabled else (150, 150, 158), kr, border_radius=5)
    surf.blit(key_s, key_s.get_rect(center=kr.center))

    # Zaehler oben rechts
    if spec.badge:
        bf = font(max(9, int(local.width * 0.12)))
        b_s = bf.render(spec.badge, True, (255, 255, 255))
        br = pygame.Rect(0, 0, max(b_s.get_width() + 10, b_s.get_height() + 4), b_s.get_height() + 4)
        br.topright = (local.width - 5, 5)
        pygame.draw.rect(surf, (*col,) if spec.enabled else (90, 92, 100), br, border_radius=br.height // 2)
        surf.blit(b_s, b_s.get_rect(center=br.center))

    if not spec.enabled:
        # ausgegraut: Deckkraft fest ins Bild einrechnen (damit das Zwischenspeichern klappt)
        surf.fill((255, 255, 255, 165), special_flags=pygame.BLEND_RGBA_MULT)   # nur Alpha * 165/255
    return surf


def button_at(specs, pos):
    for spec in specs:
        if spec.rect.collidepoint(pos):
            return spec
    return None


# =========================
# LINKE LEISTE (Rolle, Fortschritt, Aufgaben, Hinweise)
# =========================
def draw_panel_card(screen, rect, border=(70, 80, 110)):
    key = (rect.size, tuple(border))
    card = _CARD_CACHE.get(key)
    if card is None:
        if len(_CARD_CACHE) > 100:
            _CARD_CACHE.clear()
        card = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(card, PANEL_BG, card.get_rect(), border_radius=12)
        pygame.draw.rect(card, (*border, 255), card.get_rect(), 2, border_radius=12)
        _CARD_CACHE[key] = card
    screen.blit(card, rect)


def draw_progress_bar(screen, rect, value, maximum, label):
    pygame.draw.rect(screen, (35, 38, 48), rect, border_radius=rect.height // 2)
    if maximum > 0 and value > 0:
        fill = rect.copy()
        fill.width = max(rect.height, int(rect.width * clamp(value / maximum)))
        pygame.draw.rect(screen, (40, 200, 110), fill, border_radius=rect.height // 2)
    pygame.draw.rect(screen, (230, 235, 245), rect, 2, border_radius=rect.height // 2)
    txt = text(label, max(10, int(rect.height * 0.62)), (255, 255, 255))
    screen.blit(txt, txt.get_rect(center=rect.center))


def draw_banner(screen, message, y, color, bg=(18, 20, 28)):
    """Einheitliche Hinweis-Banner (oben mittig) - fertiges Banner wird zwischengespeichert."""
    w, h = screen.get_size()
    size = max(14, int(h * 0.028))
    key = (message, size, tuple(color), tuple(bg))
    card = _BANNER_CACHE.get(key)
    if card is None:
        if len(_BANNER_CACHE) > 100:
            _BANNER_CACHE.clear()
        txt = text(message, size, color)
        card = pygame.Surface((txt.get_width() + 36, txt.get_height() + 14), pygame.SRCALPHA)
        cr = card.get_rect()
        pygame.draw.rect(card, (*bg, 225), cr, border_radius=cr.height // 2)
        pygame.draw.rect(card, (*color, 255), cr, 2, border_radius=cr.height // 2)
        card.blit(txt, txt.get_rect(center=cr.center))
        _BANNER_CACHE[key] = card
    rect = card.get_rect(midtop=(w // 2, y))
    screen.blit(card, rect)
    return rect.bottom
