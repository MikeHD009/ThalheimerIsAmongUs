"""NEU: Soundeffekte fuer Thalheimer is Among Us.

Zwei Betriebsarten:
  - lokal (python main.py):   Wiedergabe direkt ueber pygame.mixer
  - Web-Session (Server):     der Server hat keine Lautsprecher - jedes Geraeusch wird als
                              kleines Ereignis an den Browser geschickt, der die MP3 selbst
                              abspielt (siehe web/app.js).

Die Dateinamen in Assets/Sounds sagen, was sie darstellen. Fehlende Dateien werden einfach
uebersprungen, daher koennen die optionalen Eintraege (z.B. CrewWin.mp3) spaeter ohne
Code-Aenderung ergaenzt werden.

Dieses Modul importiert pygame NICHT beim Laden, damit web_server.py die Tabelle unten
ebenfalls benutzen kann.
"""
import os

SOUND_DIR = os.path.join("Assets", "Sounds")

# name -> (Datei, Lautstaerke 0..1)
SOUND_FILES = {
    "music":        ("BackgroundMusic.mp3", 0.35),   # Lobby/Menue, im Spiel leiser
    "report":       ("DeadBodyReport.mp3", 0.9),     # Leiche gemeldet -> Meeting
    "emergency":    ("Emergency Meeting.mp3", 0.9),  # Notfallknopf / Kaliyoga -> Meeting
    "imposter_win": ("ImposterWin.mp3", 0.9),        # Imposter gewinnen
    "kill":         ("Kill.mp3", 1.0),               # Mord (Opfer + Killer)
    "eject":        ("KillByMeeting.mp3", 0.9),      # im Meeting rausgewaehlt
    "role_reveal":  ("RoleReveal.mp3", 0.85),        # Rollen-Aufdeckung zu Spielbeginn
    "vent":         ("Vent.mp3", 0.8),               # Vent betreten / verlassen
    "enter_game":   ("enter-game.mp3", 0.8),         # Raum/Lobby betreten, neuer Spieler kommt dazu
    "walking":      ("walking.mp3", 0.45),           # Schritte (Schleife, solange man laeuft)
    # Optional - werden automatisch benutzt, sobald die Datei in Assets/Sounds liegt:
    "crew_win":     ("CrewWin.mp3", 0.9),
    "independent_win": ("IndependentWin.mp3", 0.9),
}

MUSIC_VOLUME_LOBBY = 1.0    # Faktor auf die Grundlautstaerke von "music"
MUSIC_VOLUME_GAME = 0.35


def available_sounds():
    """name -> Dateiname, nur fuer tatsaechlich vorhandene Dateien."""
    result = {}
    for name, (filename, _vol) in SOUND_FILES.items():
        if os.path.exists(os.path.join(SOUND_DIR, filename)):
            result[name] = filename
    return result


class SoundManager:
    def __init__(self, bridge=None, assume_available=False):
        """bridge = web_bridge/browser_bridge im Web-/Browser-Modus, sonst None (lokale Wiedergabe).
        assume_available: im Browser liegen die MP3s nicht im Spielpaket, sondern werden von der
        Webseite geladen - dann einfach alle Namen verschicken."""
        self.bridge = bridge
        self.enabled = True
        self.sounds = {}
        self.loop_channels = {}
        self.loops_on = set()
        self.music_factor = 0.0
        self.music_loaded = False
        self.available = ({name: f for name, (f, _v) in SOUND_FILES.items()} if assume_available
                          else available_sounds())

        if bridge is not None:
            return  # Browser spielt ab - hier muss nichts geladen werden

        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            for name, filename in self.available.items():
                if name == "music":
                    continue  # Musik wird gestreamt (pygame.mixer.music)
                snd = pygame.mixer.Sound(os.path.join(SOUND_DIR, filename))
                snd.set_volume(SOUND_FILES[name][1])
                self.sounds[name] = snd
        except Exception as e:
            print("SOUND: Audio nicht verfuegbar -", e)
            self.enabled = False

    # ---------- Einmalige Effekte ----------
    def play(self, name):
        if name not in self.available:
            return
        if self.bridge is not None:
            self.bridge.send_event({"t": "sfx", "n": name})
            return
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            try:
                snd.play()
            except Exception:
                pass

    # ---------- Schleifen (z.B. Schritte) ----------
    def set_loop(self, name, on):
        if name not in self.available:
            return
        if on == (name in self.loops_on):
            return  # nur Zustandswechsel verschicken/ausfuehren
        if on:
            self.loops_on.add(name)
        else:
            self.loops_on.discard(name)

        if self.bridge is not None:
            self.bridge.send_event({"t": "loop", "n": name, "on": bool(on)})
            return
        if not self.enabled:
            return
        try:
            if on:
                snd = self.sounds.get(name)
                if snd is not None:
                    self.loop_channels[name] = snd.play(loops=-1)
            else:
                ch = self.loop_channels.pop(name, None)
                if ch is not None:
                    ch.stop()
        except Exception:
            pass

    def stop_loops(self):
        for name in list(self.loops_on):
            self.set_loop(name, False)

    # ---------- Hintergrundmusik ----------
    def set_music(self, factor):
        """factor 0 = aus, sonst Anteil der Grundlautstaerke (siehe MUSIC_VOLUME_*)."""
        if "music" not in self.available:
            return
        factor = max(0.0, min(1.0, factor))
        if abs(factor - self.music_factor) < 0.01:
            return
        self.music_factor = factor

        if self.bridge is not None:
            self.bridge.send_event({"t": "music", "v": round(factor, 2)})
            return
        if not self.enabled:
            return
        try:
            import pygame
            if factor <= 0:
                pygame.mixer.music.fadeout(600)
                self.music_loaded = False
                return
            if not self.music_loaded:
                pygame.mixer.music.load(os.path.join(SOUND_DIR, self.available["music"]))
                pygame.mixer.music.play(loops=-1, fade_ms=800)
                self.music_loaded = True
            pygame.mixer.music.set_volume(SOUND_FILES["music"][1] * factor)
        except Exception as e:
            print("SOUND: Musikfehler -", e)
