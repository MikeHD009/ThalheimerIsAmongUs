"""NEU: Animationen fuer Thalheimer is Among Us.

  * DeathAnimation   - kurze Todes-Animation, die NUR der getoetete Spieler sieht
  * EjectAnimation   - Rauswurf nach einem Meeting inkl. Rollen-Aufdeckung (sehen alle)
  * RoleRevealIntro  - animierte Rollen-Anzeige zu Spielbeginn
  * EndScreen        - Sieg- bzw. Niederlagen-Animation am Spielende

Alles wird nur mit pygame gezeichnet (keine zusaetzlichen Grafiken noetig). Jede Klasse kennt
ihre eigene Startzeit; main.py ruft nur draw(screen) auf und prueft done.
"""
import math
import random
import time

import pygame

_FONT_CACHE = {}


def font(size, bold=True):
    key = (size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.SysFont("arial", size, bold=bold)
    return _FONT_CACHE[key]


# NEU (Leistung): fertig gerenderte Texte und Flaechen wiederverwenden statt sie jedes Bild neu zu
# erzeugen - besonders wichtig im Browser (WebAssembly), wo jede Neuerzeugung spuerbar kostet.
_TEXT_CACHE = {}
_SURFACE_CACHE = {}


def text(txt, size, color, bold=True):
    """Gerenderten Text aus dem Zwischenspeicher (nicht veraendern - bei Bedarf .copy())."""
    key = (txt, size, tuple(color), bold)
    surf = _TEXT_CACHE.get(key)
    if surf is None:
        if len(_TEXT_CACHE) > 800:
            _TEXT_CACHE.clear()
        surf = font(size, bold).render(txt, True, color)
        _TEXT_CACHE[key] = surf
    return surf


def render_cached(fnt, txt, color):
    """Wie fnt.render(txt, True, color), aber zwischengespeichert (fuer beliebige Font-Objekte)."""
    key = (id(fnt), txt, tuple(color))
    surf = _TEXT_CACHE.get(key)
    if surf is None:
        if len(_TEXT_CACHE) > 800:
            _TEXT_CACHE.clear()
        surf = fnt.render(txt, True, color)
        _TEXT_CACHE[key] = surf
    return surf


def dim_surface(size, color=(0, 0, 0)):
    """Einfarbige Vollflaeche (ohne Pixel-Alpha) zum Abdunkeln - Deckkraft per set_alpha()."""
    key = ("dim", size, tuple(color))
    surf = _SURFACE_CACHE.get(key)
    if surf is None:
        surf = pygame.Surface(size).convert()
        surf.fill(color)
        _SURFACE_CACHE[key] = surf
    return surf


def blit_alpha(target, surf, pos, alpha):
    """surf mit Gesamt-Deckkraft zeichnen, ohne die (zwischengespeicherte) Flaeche zu veraendern."""
    if alpha <= 0:
        return
    if alpha >= 255:
        target.blit(surf, pos)
        return
    surf.set_alpha(int(alpha))
    target.blit(surf, pos)
    surf.set_alpha(255)


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_cubic(t):
    t = clamp(t)
    return t * t * t


def ease_out_back(t, s=1.70158):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def scale_sprite(img, size):
    """Pixelgrafik ohne Weichzeichnen vergroessern (Seitenverhaeltnis bleibt)."""
    if img is None:
        return None
    w, h = img.get_size()
    f = size / max(w, h)
    return pygame.transform.scale(img, (max(1, int(w * f)), max(1, int(h * f))))


def text_with_shadow(screen, txt, fnt, color, center, shadow=(0, 0, 0), offset=3, alpha=255):
    surf = render_cached(fnt, txt, color)
    sh = render_cached(fnt, txt, shadow)
    r = surf.get_rect(center=center)
    blit_alpha(screen, sh, (r.x + offset, r.y + offset), int(alpha * 0.8) if alpha < 255 else 255)
    blit_alpha(screen, surf, r, alpha)
    return r


def _vertical_gradient(size, top, bottom, alpha=255):
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        f = y / max(1, h - 1)
        c = [int(top[i] + (bottom[i] - top[i]) * f) for i in range(3)]
        pygame.draw.line(surf, (*c, alpha), (0, y), (w, y))
    return surf


def _radial_vignette(size, color, inner=0.25, max_alpha=230):
    """Dunkler Rand, zur Mitte hin durchsichtig (einmalig berechnet)."""
    w, h = size
    small = pygame.Surface((64, 36), pygame.SRCALPHA)
    for y in range(36):
        for x in range(64):
            dx = (x - 31.5) / 32.0
            dy = (y - 17.5) / 18.0
            d = math.sqrt(dx * dx + dy * dy)
            a = clamp((d - inner) / (1.2 - inner))
            small.set_at((x, y), (*color, int(max_alpha * a)))
    return pygame.transform.smoothscale(small, (w, h))


class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color", "rot", "vrot", "gravity")

    def __init__(self, x, y, vx, vy, life, size, color, gravity=0.0, vrot=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.size, self.color, self.gravity = size, color, gravity
        self.rot = random.uniform(0, 360)
        self.vrot = vrot

    def step(self, dt):
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.vrot * dt
        self.life -= dt
        return self.life > 0


# =====================================================================
# TODES-ANIMATION (nur der getoetete Spieler sieht sie)
# =====================================================================
CAUSE_KILL = "kill"
CAUSE_EXPLOSION = "explosion"
CAUSE_TRAP = "trap"
CAUSE_WINDOW = "window"
CAUSE_SCISSORS = "scissors"


class DeathAnimation:
    DURATION = 3.4
    IMPACT = 0.75

    def __init__(self, screen_size, victim_img, victim_dead_img, killer_img=None, cause=CAUSE_KILL,
                 item_images=None, subtitle=""):
        self.w, self.h = screen_size
        self.start = time.time()
        self.cause = cause
        self.subtitle = subtitle
        sprite = int(self.h * 0.2)
        self.victim = scale_sprite(victim_img, sprite)
        self.victim_dead = scale_sprite(victim_dead_img, int(sprite * 1.25))
        self.killer = scale_sprite(killer_img, int(sprite * 1.1)) if killer_img is not None else None
        self.item_images = item_images or {}
        self.vignette = _radial_vignette((self.w, self.h), (90, 0, 0), inner=0.15, max_alpha=240)
        self.band_h = int(self.h * 0.42)
        self.band = _vertical_gradient((self.w, self.band_h), (25, 5, 8), (60, 8, 12), 235)
        self.tint = dim_surface((self.w, self.h), (255, 30, 30))
        self.particles = []
        self.impact_done = False
        self.last_t = 0.0
        self.shake = 0.0

    @property
    def elapsed(self):
        return time.time() - self.start

    @property
    def done(self):
        return self.elapsed >= self.DURATION

    def _impact(self, cx, cy):
        self.impact_done = True
        self.shake = 18
        if self.cause == CAUSE_EXPLOSION:
            for _ in range(90):
                ang = random.uniform(0, math.tau)
                spd = random.uniform(200, 900)
                col = random.choice([(255, 220, 90), (255, 150, 40), (255, 90, 30), (120, 120, 120)])
                self.particles.append(_Particle(cx, cy, math.cos(ang) * spd, math.sin(ang) * spd,
                                                random.uniform(0.5, 1.4), random.randint(4, 12), col, 500))
        elif self.cause == CAUSE_WINDOW:
            for _ in range(60):
                self.particles.append(_Particle(random.uniform(0, self.w), cy + random.uniform(-self.band_h / 2, self.band_h / 2),
                                                random.uniform(900, 1600), random.uniform(-40, 40),
                                                random.uniform(0.6, 1.6), random.randint(2, 4), (200, 230, 255), 0))
        else:
            for _ in range(55):
                ang = random.uniform(-math.pi * 0.9, -math.pi * 0.1)
                spd = random.uniform(150, 650)
                col = random.choice([(200, 0, 20), (150, 0, 10), (240, 30, 40)])
                self.particles.append(_Particle(cx, cy, math.cos(ang) * spd, math.sin(ang) * spd,
                                                random.uniform(0.6, 1.5), random.randint(3, 9), col, 1100))

    def draw(self, screen):
        t = self.elapsed
        dt = max(0.0, min(0.1, t - self.last_t))
        self.last_t = t
        fade_out = 1.0 - clamp((t - (self.DURATION - 0.55)) / 0.55)
        alpha = int(255 * fade_out)

        # Rote Blitz-Toenung + Vignette (zwischengespeicherte Flaechen, nur Deckkraft aendert sich)
        flash = clamp(1 - t / 0.35) * 170 + (clamp(1 - abs(t - self.IMPACT) / 0.18) * 160 if t > self.IMPACT - 0.2 else 0)
        blit_alpha(screen, self.vignette, (0, 0), alpha)
        blit_alpha(screen, self.tint, (0, 0), int(min(200, flash) * fade_out))

        # Schwarzes Band faehrt von links herein
        band_in = ease_out_cubic(t / 0.3)
        shake_x = shake_y = 0
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 60)
            shake_x = random.randint(-int(self.shake), int(self.shake))
            shake_y = random.randint(-int(self.shake), int(self.shake))
        band_y = self.h // 2 - self.band_h // 2 + shake_y
        blit_alpha(screen, self.band, (int(-self.w + self.w * band_in) + shake_x, band_y), alpha)

        cy = self.h // 2 + shake_y
        vx = int(self.w * 0.58) + shake_x
        # Opfer: zittert vor dem Treffer, danach Leiche (bzw. weggesprengt / rausgeweht)
        if t < self.IMPACT:
            if self.victim is not None:
                jitter = int(math.sin(t * 60) * 4 * clamp((t - 0.3) / 0.3))
                img = self.victim.copy()
                img.set_alpha(alpha)
                screen.blit(img, img.get_rect(center=(vx + jitter, cy)))
        else:
            if not self.impact_done:
                self._impact(vx, cy)
            after = t - self.IMPACT
            if self.cause == CAUSE_EXPLOSION and self.victim is not None:
                img = pygame.transform.rotate(self.victim, after * 720)
                img.set_alpha(int(alpha * clamp(1 - after / 1.2)))
                screen.blit(img, img.get_rect(center=(vx + after * 300, cy - after * 500 + after * after * 300)))
            elif self.cause == CAUSE_WINDOW and self.victim is not None:
                img = pygame.transform.rotate(self.victim, -after * 400)
                img.set_alpha(int(alpha * clamp(1 - after / 1.4)))
                screen.blit(img, img.get_rect(center=(vx + ease_in_cubic(after / 1.3) * self.w * 0.6, cy + after * 40)))
            elif self.victim_dead is not None:
                img = self.victim_dead.copy()
                img.set_alpha(alpha)
                screen.blit(img, img.get_rect(center=(vx, cy + 12)))
                if self.cause == CAUSE_SCISSORS and self.item_images.get("schere") is not None:
                    sc = scale_sprite(self.item_images["schere"], int(self.h * 0.09))
                    sc.set_alpha(alpha)
                    screen.blit(sc, sc.get_rect(center=(vx, cy)))

        # Killer stuerzt von links auf das Opfer (bzw. Falle schnappt zu)
        if self.cause == CAUSE_TRAP:
            trap = self.item_images.get("falle")
            if trap is not None:
                snap = ease_out_back(clamp((t - (self.IMPACT - 0.15)) / 0.25))
                size = int(self.h * (0.08 + 0.05 * snap))
                tr = scale_sprite(trap, size)
                tr.set_alpha(alpha)
                screen.blit(tr, tr.get_rect(center=(vx, cy + int(self.h * 0.09))))
        elif self.killer is not None and self.cause != CAUSE_WINDOW:
            enter = ease_out_cubic((t - 0.15) / 0.35)
            lunge = ease_in_cubic((t - 0.5) / (self.IMPACT - 0.5))
            back = ease_out_cubic((t - self.IMPACT) / 0.5)
            kx = int(-self.killer.get_width() + (self.w * 0.3 + self.killer.get_width()) * enter
                     + (vx - self.w * 0.3 - self.killer.get_width() * 0.8) * lunge
                     - self.w * 0.08 * back) + shake_x
            img = self.killer.copy()
            img.set_alpha(alpha)
            screen.blit(img, img.get_rect(center=(kx, cy)))
            # Schnitt-Linie beim Treffer
            if self.IMPACT <= t < self.IMPACT + 0.25 and self.cause in (CAUSE_KILL, CAUSE_SCISSORS):
                k = (t - self.IMPACT) / 0.25
                length = int(self.h * 0.28)
                x0, y0 = vx - length // 2, cy - length // 2
                pygame.draw.line(screen, (255, 255, 255), (x0, y0), (x0 + int(length * k), y0 + int(length * k)), 6)

        # Partikel
        alive = []
        for p in self.particles:
            if p.step(dt):
                alive.append(p)
                a = clamp(p.life / p.max_life)
                if self.cause == CAUSE_WINDOW:
                    pygame.draw.line(screen, p.color, (int(p.x), int(p.y)), (int(p.x - 40), int(p.y)), p.size)
                else:
                    r = max(1, int(p.size * (0.5 + 0.5 * a)))
                    pygame.draw.circle(screen, p.color, (int(p.x), int(p.y)), r)
        self.particles = alive

        # Text
        if t > self.IMPACT + 0.05:
            k = ease_out_back((t - self.IMPACT) / 0.4)
            big = font(max(10, int(self.h * 0.085 * k)))
            text_with_shadow(screen, "DU WURDEST GETÖTET", big, (255, 60, 60),
                             (self.w // 2 + shake_x, band_y + int(self.band_h * 0.14)), alpha=alpha)
        if t > self.IMPACT + 0.45 and self.subtitle:
            a2 = int(alpha * clamp((t - self.IMPACT - 0.45) / 0.3))
            text_with_shadow(screen, self.subtitle, font(int(self.h * 0.032), False), (240, 225, 225),
                             (self.w // 2, band_y + int(self.band_h * 0.88)), alpha=a2, offset=2)


# =====================================================================
# RAUSWURF-ANIMATION (nach dem Meeting, sehen alle)
# =====================================================================
class EjectAnimation:
    DURATION = 7.0

    def __init__(self, screen_size, lines, sprite=None, line_colors=None):
        """lines: Liste von Textzeilen. Die erste wird Buchstabe fuer Buchstabe getippt,
        die weiteren blenden danach ein."""
        self.w, self.h = screen_size
        self.start = time.time()
        self.lines = lines
        self.line_colors = line_colors or [(255, 255, 255)] * len(lines)
        self.sprite = scale_sprite(sprite, int(self.h * 0.16)) if sprite is not None else None
        rnd = random.Random(7)
        self.stars = [(rnd.uniform(0, self.w), rnd.uniform(0, self.h), rnd.choice([1, 1, 1, 2, 2, 3]),
                       rnd.uniform(0.2, 1.0)) for _ in range(220)]
        self.bg = _vertical_gradient((self.w, self.h), (4, 6, 20), (14, 10, 35)).convert()
        self.layer = None

    @property
    def elapsed(self):
        return time.time() - self.start

    @property
    def done(self):
        return self.elapsed >= self.DURATION

    def draw(self, screen):
        t = self.elapsed
        fade_in = clamp(t / 0.45)
        fade_out = 1.0 - clamp((t - (self.DURATION - 0.6)) / 0.6)
        alpha = int(255 * min(fade_in, fade_out))

        # Voll sichtbar: direkt auf den Bildschirm; nur beim Ein-/Ausblenden ueber eine Zwischenebene
        if alpha >= 255:
            layer = screen
        else:
            if self.layer is None:
                self.layer = pygame.Surface((self.w, self.h)).convert()
            layer = self.layer
        layer.blit(self.bg, (0, 0))
        # Sterne ziehen von rechts nach links vorbei (Parallax)
        for sx, sy, size, speed in self.stars:
            x = (sx - t * 140 * speed * size) % self.w
            c = int(120 + 135 * speed)
            pygame.draw.circle(layer, (c, c, min(255, c + 20)), (int(x), int(sy)), size)

        # Rausgeworfener Spieler treibt drehend durchs Bild
        if self.sprite is not None:
            p = clamp((t - 0.4) / 4.6)
            x = -self.sprite.get_width() + p * (self.w + 2 * self.sprite.get_width())
            y = self.h * 0.5 + math.sin(t * 1.3) * self.h * 0.04
            img = pygame.transform.rotate(self.sprite, -t * 150)
            layer.blit(img, img.get_rect(center=(int(x), int(y))))

        # Erste Zeile tippen, danach die restlichen Zeilen einblenden
        type_start = 1.1
        first = self.lines[0] if self.lines else ""
        n_chars = int(max(0.0, t - type_start) * 26)
        shown = first[:n_chars]
        big = font(int(self.h * 0.05))
        if shown:
            text_with_shadow(layer, shown, big, self.line_colors[0], (self.w // 2, int(self.h * 0.5)))
        typed_done_at = type_start + len(first) / 26.0
        for i, line in enumerate(self.lines[1:], start=1):
            appear = typed_done_at + 0.35 * i
            if t >= appear:
                a = int(255 * clamp((t - appear) / 0.4))
                text_with_shadow(layer, line, font(int(self.h * 0.032), i > 1), self.line_colors[i],
                                 (self.w // 2, int(self.h * 0.5) + int(self.h * 0.075) * i), alpha=a, offset=2)

        if layer is not screen:
            blit_alpha(screen, layer, (0, 0), alpha)


# =====================================================================
# ROLLEN-AUFDECKUNG ZU SPIELBEGINN
# =====================================================================
def draw_role_reveal(screen, elapsed, total, title, title_color, team_text, team_color,
                     desc_lines, role_image=None, mate_text="", mate_hint="", footer=""):
    """Animierte Version des bisherigen Intro-Overlays (gleiche Inhalte).
    desc_lines = bereits gerenderte Textzeilen (Surfaces)."""
    w, h = screen.get_size()
    fade_out = 1.0 - clamp((elapsed - (total - 0.5)) / 0.5)
    base_alpha = int(215 * clamp(elapsed / 0.3) * fade_out)
    blit_alpha(screen, dim_surface((w, h)), (0, 0), base_alpha)
    # farbiger Lichtkegel in Teamfarbe hinter dem Bild (eigene Ebene, sonst wuerde er die
    # Abdunklung ueberschreiben statt sich darueberzulegen) - pro Groesse nur einmal erzeugt
    glow_r = int(h * 0.32 * ease_out_cubic(elapsed / 0.8)) // 6 * 6
    if glow_r > 4:
        key = ("glow", glow_r, tuple(title_color))
        glow = _SURFACE_CACHE.get(key)
        if glow is None:
            glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            for i in range(6, 0, -1):
                pygame.draw.circle(glow, (*title_color, 10 + (6 - i) * 9), (glow_r, glow_r), int(glow_r * i / 6))
            _SURFACE_CACHE[key] = glow
        blit_alpha(screen, glow, (w // 2 - glow_r, int(h * 0.3) - glow_r), int(255 * fade_out))
    a = int(255 * fade_out)

    y_img = int(h * 0.3)
    if role_image is not None:
        k = ease_out_back(clamp((elapsed - 0.15) / 0.6))
        size = max(2, int(role_image.get_width() * 1.4 * k) // 2 * 2)
        key = ("roleimg", id(role_image), size)
        img = _SURFACE_CACHE.get(key)
        if img is None:
            img = pygame.transform.smoothscale(role_image, (size, size))
            _SURFACE_CACHE[key] = img
        blit_alpha(screen, img, img.get_rect(center=(w // 2, y_img)), a)

    k_title = ease_out_back(clamp((elapsed - 0.35) / 0.5))
    if k_title > 0.02:
        text_with_shadow(screen, title, font(max(8, int(h * 0.06 * k_title))), title_color,
                         (w // 2, int(h * 0.5)), alpha=a)
    if elapsed > 0.7:
        a2 = int(a * clamp((elapsed - 0.7) / 0.4))
        text_with_shadow(screen, team_text, font(int(h * 0.034)), team_color, (w // 2, int(h * 0.565)), alpha=a2, offset=2)
    y = int(h * 0.61)
    if elapsed > 1.0:
        a3 = int(a * clamp((elapsed - 1.0) / 0.5))
        for surf in desc_lines:
            blit_alpha(screen, surf, (w // 2 - surf.get_width() // 2, y), a3)
            y += surf.get_height() + 4
    if mate_text and elapsed > 1.4:
        a4 = int(a * clamp((elapsed - 1.4) / 0.4))
        text_with_shadow(screen, mate_text, font(int(h * 0.03)), (255, 120, 120), (w // 2, y + 24), alpha=a4, offset=2)
        if mate_hint:
            text_with_shadow(screen, mate_hint, font(int(h * 0.022), False), (220, 160, 160), (w // 2, y + 56), alpha=a4, offset=2)
    if footer:
        text_with_shadow(screen, footer, font(int(h * 0.022), False), (170, 175, 190), (w // 2, h - 50), alpha=a, offset=2)


# =====================================================================
# SIEG / NIEDERLAGE
# =====================================================================
class EndScreen:
    """Sieg- oder Niederlagen-Animation. winners = Liste von (bild, name, rollentext, farbe).
    Nach SETTLE_TIME Sekunden kommt alles zur Ruhe (kein Konfetti mehr, Strahlen stehen) -
    ein stehendes Bild kostet im Web-Modus keine Bandbreite mehr."""

    SETTLE_TIME = 6.0

    def __init__(self, screen_size, victory, headline, subline, winners, my_image=None, my_dead_image=None,
                 accent=(90, 200, 255)):
        self.w, self.h = screen_size
        self.start = time.time()
        self.victory = victory
        self.headline = headline
        self.subline = subline
        self.accent = accent
        sprite = int(self.h * (0.12 if len(winners) <= 5 else 0.09))
        self.winners = [(scale_sprite(img, sprite), name, role, col) for img, name, role, col in winners]
        self.me = scale_sprite(my_dead_image if my_dead_image is not None else my_image, int(self.h * 0.1))
        if victory:
            self.bg = _vertical_gradient((self.w, self.h), (8, 20, 55), (40, 12, 70)).convert()
        else:
            self.bg = _vertical_gradient((self.w, self.h), (45, 4, 8), (8, 4, 6)).convert()
        self.rays = None
        self.static_frame = None      # nach dem Ausklingen wird das fertige Bild nur noch kopiert
        self.static_host = None
        self.vignette = _radial_vignette((self.w, self.h), (0, 0, 0), inner=0.35, max_alpha=200)
        self.particles = []
        self.last_t = 0.0
        self.button_rect = pygame.Rect(0, 0, 0, 0)
        rnd = random.Random()
        if victory:
            for _ in range(170):
                self.particles.append(self._confetti(rnd, initial=True))
        else:
            for _ in range(110):
                self.particles.append(self._ash(rnd, initial=True))

    def _confetti(self, rnd, initial=False):
        col = rnd.choice([(255, 215, 70), (90, 200, 255), (255, 90, 140), (120, 255, 150), (200, 120, 255), (255, 255, 255)])
        y = rnd.uniform(-self.h, 0) if initial else rnd.uniform(-60, -10)
        return _Particle(rnd.uniform(0, self.w), y, rnd.uniform(-60, 60), rnd.uniform(120, 260), 99,
                         rnd.randint(5, 10), col, 0, rnd.uniform(-360, 360))

    def _ash(self, rnd, initial=False):
        g = rnd.randint(70, 130)
        y = rnd.uniform(0, self.h) if initial else rnd.uniform(-40, -5)
        return _Particle(rnd.uniform(0, self.w), y, rnd.uniform(-25, -5), rnd.uniform(40, 110), 99,
                         rnd.randint(2, 4), (g, g - 10, g - 10), 0)

    @property
    def elapsed(self):
        return time.time() - self.start

    def draw(self, screen, is_host):
        t = self.elapsed
        if self.static_frame is not None and self.static_host == is_host:
            screen.blit(self.static_frame, (0, 0))
            return
        dt = max(0.0, min(0.1, t - self.last_t))
        self.last_t = t
        screen.blit(self.bg, (0, 0))

        cx = self.w // 2
        # Sieg: rotierende Lichtstrahlen hinter der Ueberschrift
        if self.victory:
            if self.rays is None:
                self.rays = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            rays = self.rays
            rays.fill((0, 0, 0, 0))
            ry = int(self.h * 0.26)
            reach = self.w
            for i in range(14):
                ang = min(t, self.SETTLE_TIME) * 0.25 + i * math.tau / 14
                p1 = (cx + math.cos(ang) * reach, ry + math.sin(ang) * reach)
                p2 = (cx + math.cos(ang + 0.12) * reach, ry + math.sin(ang + 0.12) * reach)
                pygame.draw.polygon(rays, (*self.accent, 26), [(cx, ry), p1, p2])
            screen.blit(rays, (0, 0))

        # Partikel (Konfetti bzw. Asche)
        rnd = random.Random()
        alive = []
        for p in self.particles:
            p.step(dt)
            if p.y > self.h + 20:
                if t > self.SETTLE_TIME:
                    continue
                p = self._confetti(rnd) if self.victory else self._ash(rnd)
            alive.append(p)
            if self.victory:
                a = math.radians(p.rot)
                dx, dy = math.cos(a) * p.size, math.sin(a) * p.size * 0.45
                pts = [(p.x - dx - dy, p.y - dy + dx * 0.45), (p.x + dx - dy, p.y + dy + dx * 0.45),
                       (p.x + dx + dy, p.y + dy - dx * 0.45), (p.x - dx + dy, p.y - dy - dx * 0.45)]
                pygame.draw.polygon(screen, p.color, pts)
            else:
                pygame.draw.circle(screen, p.color, (int(p.x), int(p.y)), p.size)
        self.particles = alive

        screen.blit(self.vignette, (0, 0))

        # Ueberschrift
        if self.victory:
            k = ease_out_back(t / 0.7)
            pulse = 1.0 + 0.03 * math.sin(t * 4) * clamp(self.SETTLE_TIME - t)
            size = max(8, int(self.h * 0.14 * k * pulse))
            text_with_shadow(screen, self.headline, font(size), (255, 215, 70), (cx, int(self.h * 0.2)), offset=5)
        else:
            k = ease_out_cubic(t / 1.2)
            size = int(self.h * 0.13)
            y = int(self.h * 0.2 - (1 - k) * self.h * 0.08)
            text_with_shadow(screen, self.headline, font(size), (230, 50, 50), (cx, y), offset=5, alpha=int(255 * k))
        if t > 0.6:
            a = int(255 * clamp((t - 0.6) / 0.5))
            text_with_shadow(screen, self.subline, font(int(self.h * 0.037)), (240, 240, 245),
                             (cx, int(self.h * 0.33)), alpha=a, offset=2)

        # Gewinner-Aufstellung
        n = len(self.winners)
        if n:
            spacing = min(int(self.w * 0.8 / n), int(self.h * 0.2))
            x0 = cx - spacing * (n - 1) // 2
            base_y = int(self.h * 0.56)
            for i, (img, name, role, col) in enumerate(self.winners):
                appear = 0.9 + i * 0.12
                if t < appear or img is None:
                    continue
                k = ease_out_back((t - appear) / 0.45)
                x = x0 + i * spacing
                if self.victory:
                    hop = abs(math.sin(t * 3.2 + i * 0.7)) * self.h * 0.03 * clamp(self.SETTLE_TIME - t)
                else:
                    hop = 0
                y = int(base_y + (1 - k) * self.h * 0.2 - hop)
                shadow_w = int(img.get_width() * 0.9)
                pygame.draw.ellipse(screen, (0, 0, 0), (x - shadow_w // 2, base_y + img.get_height() // 2 - 6, shadow_w, 12))
                screen.blit(img, img.get_rect(center=(x, y)))
                name_s = font(int(self.h * 0.024)).render(name, True, (255, 255, 255))
                screen.blit(name_s, name_s.get_rect(center=(x, base_y + img.get_height() // 2 + 18)))
                if role:
                    role_s = font(int(self.h * 0.019), False).render(role, True, col)
                    screen.blit(role_s, role_s.get_rect(center=(x, base_y + img.get_height() // 2 + 40)))

        # Verlierer sieht sich selbst ausgegraut am Rand liegen
        if not self.victory and self.me is not None and t > 1.2:
            img = self.me.copy()
            img.fill((110, 110, 110, 255), special_flags=pygame.BLEND_RGBA_MULT)
            pos = (int(self.w * 0.12), int(self.h * 0.84))
            screen.blit(img, img.get_rect(center=pos))
            du = font(int(self.h * 0.022), False).render("Du", True, (150, 150, 160))
            screen.blit(du, du.get_rect(center=(pos[0], pos[1] + img.get_height() // 2 + 14)))

        # Zurueck zur Lobby (bewusst ohne Blinken: ein ruhiges Bild kostet im Web-Modus nichts)
        bw, bh = int(self.h * 0.52), int(self.h * 0.075)
        self.button_rect = pygame.Rect(cx - bw // 2, int(self.h * 0.86), bw, bh)
        if t > 1.5:
            if is_host:
                pygame.draw.rect(screen, (0, 190, 95), self.button_rect, border_radius=14)
                pygame.draw.rect(screen, (255, 255, 255), self.button_rect, 3, border_radius=14)
                lbl = font(int(self.h * 0.03)).render("ZURÜCK ZUR LOBBY  (Enter)", True, (255, 255, 255))
                screen.blit(lbl, lbl.get_rect(center=self.button_rect.center))
            else:
                lbl = font(int(self.h * 0.028), False).render("Warte auf den Host für die Lobby-Rückkehr ...", True, (170, 175, 190))
                screen.blit(lbl, lbl.get_rect(center=self.button_rect.center))
        # Alles zur Ruhe gekommen (kein Konfetti/keine Asche mehr) -> Bild einfrieren
        if t > self.SETTLE_TIME + 1.5 and not self.particles:
            self.static_frame = screen.copy()
            self.static_host = is_host
