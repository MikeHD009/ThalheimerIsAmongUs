"""NEU: Schriften ohne installiertes Arial (Linux-Server, Browser/WebAssembly).

Das Spiel nutzt ueberall pygame.font.SysFont("arial", ...). Wo es kein Arial gibt, leitet
install() diese Aufrufe auf die mitgelieferte "Liberation Sans" um (Assets/Fonts, freie Lizenz
SIL OFL). Sie hat exakt dieselben Zeichenbreiten wie Arial - alle Layouts bleiben gleich.
Unter Windows (Arial vorhanden) aendert sich nichts.
"""
import os

FONT_DIR = os.path.join("Assets", "Fonts")
REGULAR = os.path.join(FONT_DIR, "LiberationSans-Regular.ttf")
BOLD = os.path.join(FONT_DIR, "LiberationSans-Bold.ttf")
MONO = os.path.join(FONT_DIR, "LiberationMono-Regular.ttf")   # Ersatz fuer "consolas" (Download-Task)


def install(pygame, force=False):
    need = force
    if not need:
        try:
            need = not pygame.font.match_font("arial")
        except Exception:
            need = True
    if not need or not os.path.exists(REGULAR):
        return False

    original_sysfont = pygame.font.SysFont

    def sysfont(name, size, bold=False, italic=False, constructor=None):
        wanted = name if isinstance(name, str) else ""
        key = wanted.lower().replace(" ", "")
        if key in ("consolas", "couriernew", "monospace", "liberationmono") and os.path.exists(MONO):
            try:
                return pygame.font.Font(MONO, size)
            except Exception:
                pass
        if key in ("arial", "liberationsans", "freesansbold", ""):
            path = BOLD if (bold and os.path.exists(BOLD)) else REGULAR
            try:
                font = pygame.font.Font(path, size)
                if italic:
                    font.set_italic(True)
                return font
            except Exception:
                pass
        if constructor is not None:
            return original_sysfont(name, size, bold, italic, constructor)
        return original_sysfont(name, size, bold, italic)

    pygame.font.SysFont = sysfont
    return True
