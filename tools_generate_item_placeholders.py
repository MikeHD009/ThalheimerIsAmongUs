"""Erzeugt einfache Platzhalter-Texturen fuer die Rollen-Items (Assets/Items/*.png).
Einfach die PNGs spaeter durch echte Grafiken mit denselben Dateinamen ersetzen."""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

pygame.init()
pygame.display.set_mode((1, 1))

S = 32
OUT = os.path.join("Assets", "Items")
os.makedirs(OUT, exist_ok=True)


def new_surf():
    return pygame.Surface((S, S), pygame.SRCALPHA)


def outline(surf, color=(20, 20, 25)):
    """Duenner dunkler Rand, damit die Items auf dem Boden nicht untergehen."""
    mask = pygame.mask.from_surface(surf)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        for x, y in mask.outline(2):
            px, py = x + dx, y + dy
            if 0 <= px < S and 0 <= py < S and not mask.get_at((px, py)):
                surf.set_at((px, py), color)
    return surf


def pfandflasche():
    s = new_surf()
    pygame.draw.rect(s, (70, 170, 110), (10, 12, 12, 17), border_radius=3)   # Flaschenkoerper
    pygame.draw.rect(s, (70, 170, 110), (13, 6, 6, 7))                        # Hals
    pygame.draw.rect(s, (235, 235, 245), (10, 18, 12, 6))                     # Etikett
    pygame.draw.rect(s, (200, 60, 60), (13, 3, 6, 4), border_radius=1)        # Deckel
    return s


def geschenk():
    s = new_surf()
    pygame.draw.rect(s, (200, 55, 70), (5, 12, 22, 16), border_radius=2)      # Karton
    pygame.draw.rect(s, (230, 80, 95), (4, 9, 24, 5), border_radius=2)        # Deckel
    pygame.draw.rect(s, (250, 220, 90), (14, 9, 4, 19))                       # Band senkrecht
    pygame.draw.rect(s, (250, 220, 90), (4, 17, 24, 3))                       # Band waagrecht
    pygame.draw.circle(s, (250, 220, 90), (13, 7), 4)                         # Schleife
    pygame.draw.circle(s, (250, 220, 90), (19, 7), 4)
    return s


def standard():
    s = new_surf()
    pygame.draw.rect(s, (120, 90, 55), (7, 4, 3, 25))                         # Fahnenstange
    pygame.draw.polygon(s, (90, 130, 235), [(10, 5), (27, 10), (10, 16)])     # Wimpel
    pygame.draw.circle(s, (250, 225, 110), (8, 3), 3)                         # Spitze
    return s


def flagge():
    s = new_surf()
    pygame.draw.rect(s, (170, 170, 180), (6, 3, 3, 26))                       # Mast
    pygame.draw.rect(s, (215, 40, 55), (9, 5, 19, 13))                        # rote Bahnen
    for i in range(3):
        pygame.draw.rect(s, (245, 245, 250), (9, 7 + i * 4, 19, 2))           # weisse Streifen
    pygame.draw.rect(s, (45, 60, 150), (9, 5, 9, 7))                          # blaues Feld
    return s


def falle():
    s = new_surf()
    pygame.draw.ellipse(s, (60, 60, 70), (4, 14, 24, 12))                     # Grundplatte
    pygame.draw.ellipse(s, (150, 40, 45), (9, 8, 14, 14))                     # Ausloeser
    pygame.draw.ellipse(s, (200, 70, 75), (12, 10, 8, 8))
    for x in range(6, 27, 5):                                                 # Zaehne
        pygame.draw.polygon(s, (190, 190, 200), [(x, 16), (x + 2, 10), (x + 4, 16)])
    return s


def schere():
    s = new_surf()
    pygame.draw.line(s, (200, 200, 215), (9, 6), (23, 24), 3)                 # Klingen
    pygame.draw.line(s, (200, 200, 215), (23, 6), (9, 24), 3)
    pygame.draw.circle(s, (60, 60, 70), (10, 26), 4, 2)                       # Griffe
    pygame.draw.circle(s, (60, 60, 70), (22, 26), 4, 2)
    pygame.draw.circle(s, (120, 120, 135), (16, 15), 2)                       # Niete
    return s


ITEMS = {
    "pfandflasche.png": pfandflasche,
    "geschenk.png": geschenk,
    "standard.png": standard,
    "flagge.png": flagge,
    "falle.png": falle,
    "schere.png": schere,
}

for filename, builder in ITEMS.items():
    surf = outline(builder())
    pygame.image.save(surf, os.path.join(OUT, filename))
    print("erzeugt:", filename)

pygame.quit()
