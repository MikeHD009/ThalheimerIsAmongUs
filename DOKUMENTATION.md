# Thalheimer is Among Us – Server-Umbau & Änderungen

Dieses Dokument hält fest, **was** umgesetzt wurde, **wie** alles aufgebaut ist und **wie** man den
Server auf Ubuntu einrichtet. Grundlage waren `Änderungen.docx` (Phase 1) und die zweite
Änderungsliste (Phase 2: Regeln, Einstellungen, Cheat-Zuteilung und vor allem **flüssiges Spielen**).
Am Ende steht das vollständige Änderungsprotokoll.

---

## 1. Umsetzungsstand

### Phase 1 – Punkte aus Änderungen.docx

| # | Anforderung | Status | Wo |
|---|-------------|--------|----|
| 1 | Soundeffekte aus `SoundeffectsAmogus` einbauen | ✅ alle 10 Dateien eingebaut | `Assets/Sounds/`, `sound.py`, `main.py` |
| 2 | Startbarer Container + „exe“, die im aktuellen Ordner den Container erstellt; läuft dauerhaft; Beitritt per Link im WLAN; Spiel im Browser (Vollbild), Server rechnet alles | ✅ `setup.sh` (Linux-Gegenstück zur .exe) baut + startet den Docker-Container, Neustart-Automatik | `setup.sh`, `Dockerfile`, `web_server.py`, `web/` |
| 3 | Join-Codes statt IP, Liste aktiver Räume, Räume erstellen, Raum nach 10 s ohne Spieler löschen | ✅ 5-stellige Codes, Live-Raumliste, Löschung nach 10 s | `web_server.py`, `web/app.js` |
| 4 | Kurze Todes-Animation, nur für den getöteten Spieler | ✅ inkl. Varianten (Messer, Schere, Explosion, Falle, Fenster) | `fx.py` (`DeathAnimation`) |
| 5 | Animation für im Meeting Rausgeworfene + Role-Reveal | ✅ Weltraum-Animation, Rolle + Team + „Noch X Imposter“ | `fx.py` (`EjectAnimation`), Paket 43 |
| 6 | Win-Animation | ✅ „SIEG!“ mit Konfetti, Lichtstrahlen, Gewinner-Aufstellung | `fx.py` (`EndScreen`) |
| 7 | Lose-Animation | ✅ „NIEDERLAGE“ mit Asche, Gewinner + eigene Figur | `fx.py` (`EndScreen`) |
| 8 | Schönere/übersichtlichere UI für Fähigkeiten, Kill-, Task- und Vent-Buttons | ✅ Aktions-Buttons mit Symbol, Taste, Cooldown, Zähler; linke Info-Leiste; Markierungen in der Welt | `hud.py`, `main.py` |
| – | Die MD-Datei mit Struktur & Plan | ✅ dieses Dokument | `DOKUMENTATION.md` |
| – | Auf Fehler prüfen, flüssig, keine Errors | ✅ 22 Fehler behoben (Abschnitt 12), automatisierte Tests (Abschnitt 13) | – |

### Phase 2 – zweite Änderungsliste

| # | Anforderung | Status | Wo |
|---|-------------|--------|----|
| 1 | Tote Spieler können nicht in den Chat schreiben | ✅ Eingabe gesperrt + Hinweis „Als Geist kannst du nicht mehr schreiben.“; der Server verwirft Nachrichten von Toten zusätzlich | `main.py`, `server.py` (Paket 50) |
| 2 | Jeder Spieler kann nur **einmal** ein Meeting starten, Leichen melden geht immer | ✅ Notfallknopf 1× pro Spieler und Runde (Button zeigt danach „VERBRAUCHT“), Melden unbegrenzt – vom Server geprüft | `server.py` (Paket 40), `main.py` |
| 3 | Meeting-Cooldown startet erst, wenn das Meeting **endet**; vom Host vor Spielbeginn einstellbar; Chat- und Abstimmungszeit ebenfalls einstellbar | ✅ Lobby-Menü **EINSTELLUNGEN**: Notfall-Cooldown, Diskussionszeit, Abstimmungszeit | `server.py` (Pakete 16/17), `main.py` |
| 4 | Spiel ist langsam → Rechenleistung der **Spieler-Geräte** nutzen | ✅ Das Spiel läuft jetzt **im Browser jedes Spielers** (WebAssembly); der Server verwaltet nur noch Räume und die Spiellogik | `browser_bridge.py`, `tools/build_web_client.py`, `web/` |
| 5 | Host kann Spielern feste Rollen zuteilen (Cheat) | ✅ Lobby-Menü **ZUTEILEN** – nur der Host sieht es und die Zuteilung | `server.py` (Pakete 18/19), `roles.py`, `main.py` |
| 6 | Noahs Fallen sollen sichtbar sein | ✅ für **alle** Spieler sichtbar (im eigenen Sichtfeld) | `server.py` (Pakete 67/70), `main.py` |
| 7 | David verwürfelt **alle** Nachrichten einer Person, bis er jemand anderen auswählt | ✅ | `server.py` (Pakete 65/50) |
| 8 | Alle können in der Lobby die Rollen nachschlagen | ✅ Button **ROLLEN-INFO** für alle (Host: ROLLEN), Details per Mauszeiger/Klick | `main.py` |
| 9 | Spiel soll **sehr flüssig** laufen | ✅ Zeichen-Code optimiert: **52 ms → ~3–4 ms Rechenzeit pro Bild, 54–55 FPS** im Browser | `main.py`, `fx.py`, `hud.py` (Abschnitt 11) |

> **Hinweis „exe“:** Ubuntu kann keine Windows-`.exe` ausführen. Das Gegenstück unter Linux ist ein
> ausführbares Skript – `setup.sh`. Es macht genau das Verlangte: im aktuellen Ordner den Container
> bauen, starten und dauerhaft laufen lassen.

---

## 2. Architektur – wie das Spiel im Browser läuft

Die Spieler haben **nur den Link**. Seit Phase 2 gibt es zwei Betriebsarten; der Spieler merkt davon
nichts außer der Geschwindigkeit.

### 2a. Browser-Modus (Standard, seit Phase 2)

Das bestehende pygame-Spiel (`main.py`, `tasks.py`, …) wird mit **pygbag** zu WebAssembly verpackt
und läuft **im Browser jedes Spielers** – mit dessen Rechenleistung. Der Server rechnet keine Bilder
mehr, sondern leitet nur die kleinen Spiel-Pakete zwischen Browser und Raumserver weiter.

```
 Browser (Spieler)                             Ubuntu-Server (Docker-Container)
 ────────────────────────────────              ──────────────────────────────────────────────
  /play/?PYGPI=/cdn/&room=KXQPT&name=Leo  ──►  web_server.py (aiohttp)
   • lädt Python+pygame (WebAssembly)            • /cdn/   Laufzeit (22 MB, einmal gespiegelt)
     und das Spielpaket (4,7 MB)                 • /play/  Spielpaket thalheimer.tar.gz
   • main.py läuft im Browser:                   • /ws/game WebSocket  ◄──►  TCP  ──►  server.py
     zeichnet, Tasks, Animationen, Sound                                        (1 Prozess je Raum)
   • WebSocket /ws/game  ◄──── Spielpakete (wie bisher das TCP-Protokoll) ────►
```

* **Kein neues Spiel:** Es ist derselbe `main.py`-Code. Nur das Netzwerk (`browser_bridge.py`,
  WebSocket statt TCP-Socket) und die Hauptschleife (asynchron, weil Browser keine Threads haben)
  wurden angepasst. Der Raumserver `server.py` merkt keinen Unterschied.
* **Offline im WLAN:** Die Browser-Laufzeit (Python 3.12 + pygame-ce 2.5.7 für WebAssembly) wird beim
  Einrichten **einmal** aus dem Internet geladen und unter `web/cdn/` abgelegt. Danach liefert der
  eigene Server alles aus – die Spieler brauchen kein Internet. Der Parameter `PYGPI=/cdn/` in der
  Adresse sorgt dafür, dass pygbag die Pakete vom eigenen Server holt (der Server ergänzt ihn
  automatisch, falls er fehlt).
* **Pakete zerlegen:** Der WebSocket liefert Daten in beliebigen Stücken. `browser_bridge.packet_length`
  kennt die Länge jedes Pakettyps und gibt nur vollständige Pakete an `handle_packet` weiter –
  dieselbe Funktion, die der Desktop-Client im Empfangs-Thread benutzt.
* **Sound & Video:** Sounds über Web Audio (`web/audio.js`), Vladimirs Intro als `<video>`-Element.
  Browser erlauben Ton erst nach der ersten Taste/dem ersten Klick – danach geht er automatisch an.
* **Laden:** Im Test war das Spiel nach **3,5 s** bereit (Laufzeit + Spielpaket ≈ 27 MB beim ersten
  Mal; danach kann der Browser seinen Cache nutzen).

### 2b. Server-Modus (Rückfalloption)

Die Phase-1-Lösung ist weiterhin eingebaut – für sehr schwache Geräte. Auf der Startseite gibt es den
Haken **„Server berechnet das Spiel“** (standardmäßig aus, wird im Browser gespeichert). Dann läuft
`main.py` pro Spieler auf dem Server, und der Browser zeigt nur das fertige Bild an
(„Cloud-Gaming im WLAN“):

```
 Browser (Spieler)                         Ubuntu-Server  (Docker-Container)
 ───────────────────                       ─────────────────────────────────────────────────────
  Canvas + Web Audio   ◄──── WebSocket ────►  web_server.py → pro Spieler eine Sitzung:
   • zeigt Bilder an        Bilder ▼             main.py --web-session   (pygame ohne Fenster)
   • spielt Sounds          Tasten ▲              ├─ zeichnet, Bild → JPEG → Browser
   • schickt Tasten/Maus                          └─ TCP ─►  server.py --port 61xx  (1 Prozess je Raum)
```

Die Zeichen-Optimierungen aus Phase 2 (Abschnitt 11) wirken auch hier.

### Prozesse
| Prozess | Anzahl | Aufgabe |
|---------|--------|---------|
| `web_server.py` | 1 | Webseite, REST-API, WebSockets, Browser-Spiel ausliefern, startet/beendet Räume und Spielersitzungen |
| `server.py --host 127.0.0.1 --port 6100…6199 --room CODE` | 1 pro Raum | Der bisherige Spielserver (Rollen, Kills, Meetings …), nur intern erreichbar |
| `main.py --web-session …` | 1 pro Spieler **nur im Server-Modus** | Der bisherige Client, zeichnet ohne Fenster (`SDL_VIDEODRIVER=dummy`) |

Ein abgestürzter Raum oder Spieler reißt dadurch nie andere Räume mit.

### Bild-Übertragung im Server-Modus (`web_bridge.py`, Klasse `_FrameEncoder`)
Einfach jedes Bild als JPEG zu schicken hätte ~21 Mbit/s pro Spieler gekostet (gemessen). Deshalb:

1. **Spielwelt separat in Originalgröße:** Die Welt ist intern 360×360 Pixel und wird nur hochskaliert.
   Sie wird als kleines JPEG (≈ 30 KB, Qualität 78, 4:4:4) geschickt und **im Browser pixelgenau**
   vergrößert – schärfer und ~⅔ weniger Daten.
2. **Texte/Buttons über der Welt** (Namen, Banner, Lobby-Texte) werden automatisch erkannt und als
   kleine, transparente PNG-Streifen mitgeschickt.
3. **Alles andere** (Seitenleisten, Menüs, Meetings, Tasks) wird nur dort neu übertragen, wo sich
   etwas geändert hat (Rechtecke auf 16-Pixel-Raster).
4. **Stillstand kostet nichts:** Ändert sich nichts, wird nichts gesendet.
5. **Flusskontrolle:** Höchstens 2 unbestätigte Bilder unterwegs. Ist das WLAN langsam, sinkt nur die
   Bildrate – es baut sich **keine Verzögerung** auf.

Gemessen (1440×810, 30 Bilder/s Obergrenze): **~29 Bilder/s, ~7 Mbit/s pro laufendem Spieler**,
im Stand ~0 Mbit/s; 8 Spieler gleichzeitig: je 27–30 Bilder/s.

Eingaben: Der Browser schickt `KeyboardEvent.key/code` und Mausposition (umgerechnet auf 1440×810);
in der Sitzung werden daraus echte `pygame`-Events. Sound: `sound.py` schickt kleine Ereignisse
(`{"t":"sfx","n":"kill"}`) an den Browser.

### Schriften
Linux-Server und Browser haben kein Arial. Im Projekt liegen daher **Liberation Sans** (exakt gleiche
Zeichenbreiten wie Arial) und **Liberation Mono** (statt Consolas) unter `Assets/Fonts/`
(freie Lizenz SIL OFL, Lizenztext liegt bei). `fonts.py` leitet `SysFont("arial")` usw. automatisch
darauf um – im Server-Modus und im Browser. Alle Layouts bleiben pixelgleich zu Windows.

---

## 3. Ordnerstruktur (neu = ★)

```
ThalheimerIsAmongUs/
├─ main.py                  Spiel-Client: lokal im Vollbild, im Browser (WebAssembly) ODER als Server-Sitzung – geändert
├─ server.py                Spielserver für EINEN Raum                              – geändert
├─ roles.py                 + gemeinsame Regeln für Rollen-Setup und feste Zuteilung – ergänzt
├─ tasks.py                 unverändert
├─ ★ web_server.py          Webserver + Raumverwaltung + WebSocket-Brücken
├─ ★ web_bridge.py          Server-Modus: Eingaben rein, Bilder raus
├─ ★ browser_bridge.py      Browser-Modus: WebSocket-Verbindung, Paket-Zerlegung, Sound/Video-Ereignisse
├─ ★ fonts.py               Schrift-Umleitung (Arial → Liberation Sans, Consolas → Liberation Mono)
├─ ★ sound.py               Soundeffekte (lokal über pygame.mixer, im Web über den Browser)
├─ ★ fx.py                  Animationen: Tod, Rauswurf, Rollen-Intro, Sieg/Niederlage + Zeichen-Caches
├─ ★ hud.py                 Aktions-Buttons, Info-Leiste, Banner
├─ ★ tools/build_web_client.py  baut die Browser-Version (web/client) und spiegelt die Laufzeit (web/cdn)
├─ ★ web/                   index.html, style.css, app.js  (Startseite / Raumliste)
│    ├─ ★ client_template.tmpl  Spielseite des Browser-Modus (Ladeanzeige, Werkzeugleiste, Video)
│    ├─ ★ game_glue.js      Verbindung Webseite ↔ Spiel (WebSocket, Sounds, Video, Werkzeugleiste)
│    ├─ ★ audio.js          Web-Audio-Wiedergabe (von Startseite und Spielseite genutzt)
│    ├─ ★ cdn/              (wird erzeugt) WebAssembly-Laufzeit, ~22 MB – nicht in Git
│    └─ ★ client/           (wird erzeugt) fertiges Spielpaket, ~4,7 MB – nicht in Git
├─ ★ Assets/Sounds/         die 10 MP3s aus SoundeffectsAmogus
├─ ★ Assets/Fonts/          Liberation Sans/Mono + Lizenz
├─ ★ Dockerfile             Container-Bauplan (baut auch die Browser-Version)
├─ ★ requirements-server.txt  pygame, pillow, numpy, aiohttp (getestete Versionen)
├─ ★ setup.sh               „exe“: Docker installieren, Container bauen & dauerhaft starten
├─ ★ remove.sh              Container + Image wieder entfernen
├─ ★ start_lokal_windows.bat  Web-Version unter Windows ohne Docker testen
├─ ★ .dockerignore / .gitattributes / .gitignore
└─ ★ DOKUMENTATION.md       dieses Dokument
```

---

## 4. Einrichtung auf dem Ubuntu-Server

### Voraussetzungen
* Ubuntu 22.04 / 24.04 (andere Debian-Varianten gehen auch), Internet **nur beim ersten Einrichten**
  (Docker, Python-Pakete und die ~22 MB Browser-Laufzeit werden geladen). Danach läuft alles offline
  im WLAN.
* Server und Spieler im **selben WLAN/Netzwerk**.
* Hardware:
  * **Browser-Modus (Standard):** Der Server rechnet nur noch die Spiellogik und leitet Pakete weiter –
    die schwere Arbeit (Zeichnen) machen die Geräte der Spieler. Ein normaler Rechner reicht
    (die Last wurde nicht separat vermessen, ist aber nur ein Bruchteil des Server-Modus).
  * **Server-Modus (Haken auf der Startseite):** pro gleichzeitig spielender Person ca. **0,4 CPU-Kern**
    und **~140 MB RAM**, pro Raum zusätzlich ~20 MB. Für 10 Spieler also ≈ 4 Kerne / 2 GB RAM.
* WLAN: Browser-Modus – einmalig ~27 MB pro Gerät beim Laden, danach nur winzige Spielpakete.
  Server-Modus – ~7 Mbit/s pro laufendem Spieler (Server dann am besten per **LAN-Kabel** am Router).

### Schritt für Schritt
1. Den **ganzen Projektordner** auf den Server kopieren (USB-Stick, `scp`, WinSCP, `git clone` …).
2. Terminal im Ordner öffnen und ausführen:
   ```bash
   bash setup.sh
   ```
   (oder `chmod +x setup.sh` und dann `./setup.sh`)
3. Das Skript
   * installiert Docker, falls es fehlt, und aktiviert es beim Systemstart,
   * baut das Image aus dem aktuellen Ordner (beim ersten Mal einige Minuten). Dabei wird
     **automatisch auch die Browser-Version gebaut** (`tools/build_web_client.py`): erst die
     Laufzeit gespiegelt (eigene Docker-Schicht, wird bei Code-Änderungen nicht neu geladen), dann
     das Spielpaket gepackt,
   * ersetzt eine evtl. laufende alte Version (die läuft während des Bauens weiter),
   * wählt **Port 80** (falls frei, sonst 8080) → der Link ist dann einfach `http://192.168.x.y`,
   * startet den Container mit `--restart unless-stopped` → **läuft ab jetzt immer**, auch nach
     einem Neustart des Servers, bis `remove.sh` ausgeführt wird,
   * gibt die Firewall-Regel frei (falls `ufw` aktiv ist),
   * wartet, bis der Server antwortet, und **zeigt den Beitrittslink** an.
4. Link an die Mitspieler geben. Fertig.

### Betrieb
| Aufgabe | Befehl |
|---------|--------|
| Logs live ansehen | `sudo docker logs -f thalheimer-among-us` |
| Nach Code-Änderungen neu einrichten | `bash setup.sh` (baut neu – inkl. Browser-Version – und ersetzt die alte Version) |
| Festen Port wählen | `PORT=8090 bash setup.sh` |
| Server entfernen | `bash remove.sh` |
| Status | `sudo docker ps` |
| Ist die Browser-Version gebaut? | `http://<Server>/api/info` → `"browser_client": true` |

### Einstellungen (Umgebungsvariablen im Container, optional)
| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `ROOM_EMPTY_TIMEOUT` | 10 | Sekunden ohne Spieler, bis ein Raum gelöscht wird |
| `MAX_ROOMS` | 12 | max. gleichzeitige Räume |
| `MAX_ROOMS_PER_IP` | 3 | max. Räume pro Gerät (Spam-Schutz) |
| `CREATE_COOLDOWN` | 3 | Sekunden zwischen zwei Raum-Erstellungen pro Gerät |
| `MAX_SESSIONS` | 60 | max. Spieler auf dem ganzen Server |
| `MAX_FPS` | 30 | nur Server-Modus: Bildrate-Obergrenze – bei schwachem WLAN z.B. `20` |
| `WORLD_QUALITY` | 78 | nur Server-Modus: JPEG-Qualität der Spielwelt |
| `JPEG_QUALITY` | 72 | nur Server-Modus: JPEG-Qualität von Menüs/Leisten |
| `GAME_RESOLUTION` | 1440x810 | nur Server-Modus: Render-Auflösung (Tasks brauchen mind. 1250×760) |

Setzen z.B. mit `docker run … -e MAX_FPS=20 …` (Zeile in `setup.sh` ergänzen).

### Falls etwas nicht klappt
* `bad interpreter` / `$'\r': command not found` → die Datei hat Windows-Zeilenenden:
  `sed -i 's/\r$//' setup.sh remove.sh`
* Link geht nicht auf dem Handy/Laptop → gleiches WLAN? Gäste-WLAN trennt Geräte oft voneinander
  („Client-Isolation“) – dann das normale WLAN nutzen.
* Port 80 belegt (z.B. durch einen Webserver) → Skript nimmt automatisch 8080, Link dann `http://IP:8080`.
* Docker-Bau bricht mit „Konnte … nicht laden“ ab → der Server war beim Bauen offline; die Laufzeit
  kommt von `pygame-web.github.io`. Mit Internet erneut `bash setup.sh`.
* Statt des Spiels erscheint „Die Browser-Version ist noch nicht gebaut“ → `web/client` fehlt
  (nur beim Start ohne Docker möglich): `python tools/build_web_client.py` ausführen. Bis dahin
  funktioniert der Server-Modus.

---

## 5. Spielen im Browser

1. Link öffnen → Startseite mit **„Aktive Räume im WLAN“** (aktualisiert sich alle 2 s).
2. Namen eingeben, dann
   * in der Liste auf **Beitreten** klicken, **oder**
   * den **5-stelligen Raum-Code** eingeben (z.B. `KXQPT`), **oder**
   * **Neuen Raum erstellen** (Name optional) – man betritt ihn sofort und ist Host.
3. Das Spiel lädt (Fortschrittsanzeige) und startet im **Vollbild**. Oben gibt es eine Leiste mit
   Raum-Code, **Link kopieren**, Ton an/aus, Vollbild, Verlassen und der aktuellen **Bildrate**
   (Mauszeiger darauf zeigt die Rechenzeit pro Bild).
4. Der Raum-Code steht auch groß in der Lobby (links oben).
5. Direkt-Einladung: `http://<Server>/?room=KXQPT` füllt den Code automatisch aus.
6. Auf sehr schwachen Geräten vor dem Beitreten den Haken **„Server berechnet das Spiel“** setzen.

Regeln der Räume: max. 15 Spieler; Beitritt nur in der Lobby (nicht während einer laufenden Runde);
ein Raum ohne Spieler verschwindet nach 10 Sekunden.

**Lobby-Buttons** (links unten): **ROLLEN** (Host: Rollen an/aus) bzw. **ROLLEN-INFO** (alle anderen:
nur ansehen), **EINSTELLUNGEN** (Host: ändern, alle: ansehen), **ZUTEILEN** (nur Host, Cheat).
Rechts unten: **START** (nur Host) und daneben die Imposter-Anzahl mit − / +.

Steuerung wie bisher: **WASD** laufen, **E** benutzen/melden/töten, **F** Fähigkeit, **G** Monika-Reise,
**Leertaste** Vent, **M** Karte, **R** Rolle, **Q** Task/Karte schließen, **Enter** Chat. Alle
Aktions-Buttons unten rechts sind zusätzlich **anklickbar**. Im Browser beendet **Q** das Spiel nicht
(dafür gibt es „Verlassen“).

---

## 6. Lokal testen (ohne Ubuntu)

* **Web-Version unter Windows:** `start_lokal_windows.bat` doppelklicken. Es installiert die Pakete,
  baut die Browser-Version (beim ersten Mal werden ~22 MB Laufzeit geladen) und startet den Server →
  `http://localhost:8080`. Andere Geräte im WLAN: `http://<eigene-IP>:8080` (Windows-Firewall ggf. erlauben).
* **Bisheriger Desktop-Modus** funktioniert unverändert: `python server.py` und auf jedem PC
  `python main.py` (Vollbild, Eingabe der Server-IP). Die neuen Regeln, Sounds, Animationen und das
  neue HUD gibt es dort ebenfalls.

---

## 7. Sounds – welcher Effekt wann

| Datei | Wann | Wer hört es |
|-------|------|-------------|
| `BackgroundMusic.mp3` | Schleife im Menü/Lobby (voll), im Spiel leiser, am Rundenende aus | jeder |
| `enter-game.mp3` | eigener Beitritt in einen Raum + wenn neue Spieler in die Lobby kommen | jeder |
| `RoleReveal.mp3` | Rollen-Aufdeckung zu Spielbeginn | jeder |
| `walking.mp3` | Schleife, solange man läuft (nicht als Geist) | nur man selbst |
| `Kill.mp3` | Mord | Opfer (mit Todes-Animation) und Killer |
| `Vent.mp3` | Vent betreten und verlassen | nur der Imposter selbst |
| `DeadBodyReport.mp3` | Meeting durch gemeldete Leiche | jeder |
| `Emergency Meeting.mp3` | Meeting per Notfallknopf bzw. Kaliyoga | jeder |
| `KillByMeeting.mp3` | Rauswurf-Animation nach der Abstimmung | jeder |
| `ImposterWin.mp3` | Imposter gewinnen | jeder |

Optional: legt man `CrewWin.mp3` bzw. `IndependentWin.mp3` in `Assets/Sounds`, werden sie beim
Crew- bzw. Ramona-Sieg automatisch abgespielt (Tabelle in `sound.py`).

---

## 8. Animationen (`fx.py`)

* **Todes-Animation (nur Opfer, 3,4 s):** roter Blitz + Vignette, schwarzes Band fährt ein, der Killer
  (in seiner Farbe) stürzt auf das Opfer, Treffer mit Schnitt, Blutspritzern und Wackeln, das Opfer
  wird zur Leiche, „DU WURDEST GETÖTET“. Varianten: Martin (Schere steckt in der Leiche),
  Steinermike (Explosion, Opfer fliegt weg), Noahs Falle (Falle schnappt zu), Evelyns Fenster
  (Wind, Opfer wird hinausgeweht). Danach ggf. Vladimirs Anime-Intro. Steuerung ist währenddessen gesperrt.
* **Rauswurf + Role-Reveal (alle, 7 s):** Sternenhimmel, die Figur treibt drehend durchs Bild, der
  Text wird getippt: „Dora war ein Imposter.“ bzw. „… war Martin.“ / „… war kein Imposter.“, dann
  Team (farbig) und „Noch N Imposter übrig.“. Varianten für Überspringen, Gleichstand und
  „gerettet durch Unsterblichkeit“.
* **Rollen-Intro (Spielstart):** Rollenbild springt auf, Teamfarben-Leuchten, Titel, Team,
  Beschreibung, Mit-Imposter. Läuft seit Phase 2 **zeitbasiert** (gleich lang bei jeder Bildrate).
* **Sieg / Niederlage:** „SIEG!“ (goldene Schrift, rotierende Lichtstrahlen, Konfetti, hüpfende
  Gewinner) bzw. „NIEDERLAGE“ (rot, Asche fällt, Gewinner stehen still, eigene Figur ausgegraut).
  Unter jedem Gewinner steht seine Rolle (Server deckt alle Rollen am Ende auf). Der Host geht per
  **Enter oder Klick** zurück zur Lobby. Nach 6 s kommt alles zur Ruhe (Bild wird eingefroren).
* Ein Sieg, der durch einen Rauswurf/Mord entsteht, wird erst **nach** der laufenden Animation gezeigt.

---

## 9. Neues HUD (`hud.py`)

* **Aktions-Buttons unten rechts** (Among-Us-Stil): Symbol, Beschriftung, Tastenhinweis,
  Cooldown als dunkles Tortenstück mit Sekunden, Zähler-Badge (z.B. Fallen 1/3), ausgegraut wenn
  gerade nicht möglich, leuchtender Rand wenn bereit.
  * **TÖTEN** (Imposter, mit Kill-Cooldown), **MELDEN / NOTFALL / BENUTZEN** (je nach Situation – genau
    die Reihenfolge der E-Taste), **VENT / RAUS** (Leertaste), **Rollen-Fähigkeit** (F, mit dem
    Rollenbild als Symbol, z.B. FLAGGE, FALLE, AUFDECKEN, FÄLSCHEN …), **REISEN** (Monika, G),
    **KARTE** (M), **ROLLE** (R; im Meeting oben rechts).
  * Seit Phase 2: **NOTFALL** zeigt den Cooldown nach Spielstart/Meeting-Ende und nach der eigenen
    Nutzung „VERBRAUCHT“.
* **In der Welt:** rote Umrandung um das aktuelle Kill-Ziel, orange um meldbare Leichen, grün um den
  Vent unter einem; offene Aufgaben gelb mit „!“, erledigte grün mit Haken, in Reichweite
  „E: Aufgabenname“. Seit Phase 2 außerdem **Noahs Fallen** (für alle sichtbar).
* **Linke Leiste:** Rollenkarte (Bild, Name, Team, GEIST/IM VENT), Gesamtfortschritt, eigene
  Aufgabenliste mit Häkchen bzw. Auftrag + Kill-Cooldown + Mit-Imposter, Rollen-Infos (Ramonas
  Rechte, Markierungen …), kurze Steuerungshilfe.
* **Banner oben** einheitlich gestaltet (Unsterblichkeit, Fenster-Gefahr, sabotierte Aufgabe,
  Yoshis Aufdeckung, „bereits erledigt“).

---

## 10. Neue Regeln & Lobby-Menüs (Phase 2)

Alle Regeln werden **vom Server geprüft** (ein manipulierter Client kann sie nicht umgehen); der
Client zeigt sie nur passend an.

### Meeting-Regeln
* **Notfall-Meeting nur einmal pro Spieler und Runde.** Danach zeigt der Button „VERBRAUCHT“, die
  E-Taste löst am Notfallknopf nichts mehr aus, und der Server lehnt weitere Versuche ab.
* **Leichen melden geht immer** (auch nach dem eigenen Notfall-Meeting und ohne Cooldown).
* **Notfall-Cooldown** läuft **nach dem Ende jedes Meetings** (und zu Spielbeginn, damit niemand in
  der ersten Sekunde ein Meeting ruft). Wer vorher drückt, wird vom Server abgewiesen.
* **Diskussionszeit** (nur Chat) und **Abstimmungszeit** kommen aus den Einstellungen. Diskussionszeit
  0 = sofort abstimmen.
* **Tote können nicht schreiben:** Das Chat-Feld ist für Geister gesperrt („Als Geist kannst du nicht
  mehr schreiben.“), der Server verwirft ihre Nachrichten zusätzlich.

### Menü EINSTELLUNGEN (Lobby)
| Einstellung | Standard | Bereich | Schritt |
|-------------|----------|---------|---------|
| Notfall-Cooldown | 30 s | 0–120 s | 5 s |
| Diskussionszeit | 45 s | 0–180 s | 5 s |
| Abstimmungszeit | 30 s | 10–180 s | 5 s |

Nur der Host kann ändern (nur in der Lobby), alle anderen sehen die Werte. Änderungen gehen sofort an
alle Spieler (Paket 17); neu beitretende Spieler bekommen die aktuellen Werte beim Beitritt.

### Menü ZUTEILEN – feste Rollen (Cheat, nur Host)
* Pro Spieler per `<` / `>` wählbar: **Zufall** (normal), **Crewmate**, **Imposter** oder eine
  bestimmte **Rolle** (z.B. „Noah“). **ALLE AUF ZUFALL** setzt alles zurück.
* Nur der Host sieht dieses Menü und die Zuteilung – die anderen Spieler erfahren nichts davon.
* Beim Start werden zuerst die festen Zuteilungen vergeben, der Rest wird wie bisher zufällig verteilt.
  Eine Spezialrolle kann nur einer Person fest gegeben werden (wird sie einem zweiten Spieler
  gegeben, fällt der erste zurück auf Zufall).
* Fest zugeteilte Imposter zählen zur Imposter-Anzahl (sie wird bei Bedarf erhöht); die üblichen
  Prüfungen (mindestens ein Crewmate, mehr freundliche als feindliche Spieler) gelten weiterhin –
  START bleibt sonst grau, mit Begründung.
* Verlässt der Host den Raum, bekommt der neue Host die aktuelle Zuteilung.

### ROLLEN-INFO für alle
Alle Spieler können in der Lobby die Rollenübersicht öffnen. Mit dem Mauszeiger (oder Klick) auf eine
Rolle erscheint ein Detailfenster mit Bild, Team und Beschreibung. Nur der Host kann Rollen an- und
ausschalten.

### Noahs Fallen sichtbar
Gelegte Fallen werden an **alle** Spieler geschickt (Paket 67) und in der Welt gezeichnet – wie alles
andere nur im eigenen Sichtfeld und nicht durch Wände. Schnappt eine Falle zu, verschwindet sie bei
allen (Paket 70).

### David
David wählt ein Ziel; **alle** Chat-Nachrichten dieser Person werden verwürfelt, **bis** David eine
andere Person wählt (dann ist die erste wieder lesbar). Vorher galt es nur für eine Nachricht.

---

## 11. Leistung – flüssig spielen (Phase 2)

### Ausgangslage
Im Server-Modus rechnete der Server für jeden Spieler das komplette Spiel und schickte Bilder –
das begrenzte die Bildrate (max. 30) und hing an Server-CPU und WLAN. Als das Spiel zum ersten Mal im
Browser lief, brauchte ein Bild dort **52 ms** Rechenzeit (≈ 21 FPS). Ursache waren teure
Zeichenoperationen, die in **jedem** Bild wiederholt wurden.

### Maßnahmen
| Problem (pro Bild) | Lösung |
|--------------------|--------|
| Spiel lief auf dem Server | läuft im Browser des Spielers (Abschnitt 2a) |
| Bildschirmgroße halbtransparente Flächen neu erzeugt (Intro, Meeting, Rollen-Panel) | einmal erzeugte, zwischengespeicherte Abdunkel-Flächen (`fx.dim_surface`) |
| Drei Kartenebenen mit Transparenz übereinander gezeichnet | beim Laden zu **einem** Bild zusammengefügt (`map_combined`, `lobby_combined`) |
| Alle Texte (Namen, Buttons, Leiste) neu gerendert | Text-Cache (`fx.text`, `fx.render_cached`) |
| Aktions-Buttons, Rollenkarte, Banner neu gezeichnet | Cache nach Zustand (`hud._BUTTON_CACHE`, `_CARD_CACHE`, `_BANNER_CACHE`) |
| Linke Info-Leiste in jedem Bild neu aufgebaut | nur neu gezeichnet, wenn sich ihr Inhalt ändert (`left_panel_model`) |
| Animationen kopierten Bilder mit Transparenz | direkte Alpha-Blits, gecachte Glüh-/Rollenbilder, Endbildschirm friert nach 6 s ein |
| Laufgeschwindigkeit hing an der Bildrate | zeitbasierte Bewegung (mit Nachkommarest) – gleich schnell bei jeder Bildrate |

### Ergebnis (gemessen, 3 Browser + Bot gleichzeitig auf einem PC)
* **~3–4 ms Rechenzeit pro Bild** statt 52 ms, **54–55 FPS** (Browser-Obergrenze ~60).
* Einzelwerte: Welt 1,2 ms, Bildausgabe 0,8 ms, HUD 0,7 ms, Buttons 0,5 ms.

### Selbst messen
* Die Werkzeugleiste zeigt die FPS; Mauszeiger darauf → Rechenzeit pro Bild.
* Detail-Messung: an die Spiel-Adresse `&perf=1` anhängen (z.B.
  `/play/?PYGPI=/cdn/&room=KXQPT&name=Leo&perf=1`) → alle 2 s eine Zeile
  `PERF state=game ms/Frame: …` in der Browser-Konsole (F12). Lokal: Umgebungsvariable `TIAU_PERF=1`.

---

## 12. Gefundene und behobene Fehler

| # | Fehler (vorher) | Folge | Behebung |
|---|-----------------|-------|----------|
| 1 | `sock.recv(n)` darf weniger als n Bytes liefern | Datenstrom verrutscht → Absturz/Unsinn | `recv_exact()` in Client und Server |
| 2 | Mehrere Threads senden gleichzeitig auf einen Socket (z.B. Lobby-Liste in mehreren `sendall`) | Pakete verschachtelt → Clients lesen Müll | ein Paket = ein `sendall`, Sende-Lock je Verbindung |
| 3 | Kein Lock für den Spielzustand (Client-Threads + Meeting-Timer) | Race Conditions bei Kill/Abstimmung | `state_lock` im Server |
| 4 | Spieler-IDs zählten ewig hoch | 16. Beitritt (Reconnects!) → `IndexError` bei den 15 Spawnpunkten; ab ID 255 Absturz | kleinste freie ID wird vergeben |
| 5 | Crew gewinnt nicht, wenn alle Imposter tot/rausgewählt sind | Spiel lief endlos weiter | Crew-Sieg ergänzt |
| 6 | Imposter-Sieg verlangte `alive_crew > 0` | starb die letzte Crew (z.B. Falle) → Spiel hing | Bedingung korrigiert |
| 7 | Zweiter `elif packet_type == 23`-Zweig war unerreichbar | Meeting blieb bis in die nächste Runde offen | zusammengeführt |
| 8 | Endbildschirm prüfte das zuletzt gesehene `event` außerhalb der Event-Schleife | ohne Event `NameError`-Absturz, Paket 23 mehrfach gesendet | in die Event-Schleife verschoben |
| 9 | Durch ein Meeting abgebrochene Aufgabe zählte als **erledigt** | Fortschritt ohne Arbeit | `task_aborted` wird gesetzt |
| 10 | Im Vent zu Meeting-Beginn → nach dem Meeting weiter „im Vent“ am Spawn | Imposter konnte sich nicht bewegen | Vent-Status nach Meeting/Tod zurückgesetzt |
| 11 | Davids Verwürfelung galt für alle weiteren Nachrichten | laut Rolle damals nur die nächste | in Phase 1 auf eine Nachricht begrenzt – **in Phase 2 auf Wunsch geändert:** alle Nachrichten des Ziels, bis David neu wählt |
| 12 | Kills auch während Meetings / außerhalb einer Runde möglich; Start (99) und Imposter-Anzahl (11) von jedem Spieler auslösbar | Manipulation | serverseitig geprüft (nur Host, nur im Spiel) |
| 13 | Ein Client, der nach dem Verbinden nichts schickt, blockierte die ganze Annahme neuer Spieler | Server nimmt niemanden mehr an | Handshake mit Timeout in eigenem Thread |
| 14 | Ohne Netzwerk-Route stürzte der Server beim Ermitteln der IP ab | kein Start offline | Fallback `0.0.0.0` |
| 15 | Karten-Ladefehler beendete das Spiel ohne Meldung | Fehlersuche unmöglich | Fehlermeldung wird ausgegeben |
| 16 | Layout: „Spieler online“ unter dem ROLLEN-Button; Hinweistext überlappte die Spaltenköpfe der Rollenwahl; Karte ragte bei kleinen Auflösungen aus dem Bild; Mausrad löste Lobby-Buttons aus | unleserlich / Fehlklicks | Positionen/Größen korrigiert, nur Linksklick |
| 17 | Rollenwechsel in Paket 3 nutzte eine Variable aus einem anderen Paket-Zweig (`role_key`) | fehleranfällig | `my_player.role_key` |

Beim Testen des neuen Server-Betriebs (Phase 1) zusätzlich gefunden und behoben:

| # | Fehler | Behebung |
|---|--------|----------|
| 18 | Log-Zeilen zweier Threads konnten sich im Raumserver vermischen → Statuszeile ging verloren, Raumliste zeigte „Lobby“ statt „Spiel läuft“ | thread-sichere, zeilenweise Ausgabe |
| 19 | Unter Windows erlaubt `SO_REUSEADDR` zwei Server auf demselben Port → Spieler landeten im falschen Raum | `SO_EXCLUSIVEADDRUSE` unter Windows |
| 20 | Unter Windows stürzte die Log-Weitergabe bei Umlauten/Emojis ab | alle Prozesse schreiben UTF-8 |
| 21 | numpy/OpenBLAS legte pro Spieler einen Thread-Pool für alle Kerne an (635 MB reserviert) | auf 1 Thread begrenzt → 124 MB |
| 22 | Sitzungsende konnte mit „could not acquire lock for stdin“ abbrechen | sauberes Beenden über `web_bridge.hard_exit()` |

Phase 2 (Browser-Version und neue Regeln):

| # | Fehler | Behebung |
|---|--------|----------|
| 23 | Browser: Das Spiel wurde direkt nach dem Start wieder beendet („video system not initialized“) – in pygbag kehrt `asyncio.run()` sofort zurück, das Aufräumen am Dateiende lief zu früh | Aufräumen in `shutdown_game()` am Ende der Hauptschleife; Fenster-Schließen wird im Browser ignoriert |
| 24 | Browser: pygame wurde von `localhost:8000` bzw. aus dem Internet geladen statt vom eigenen Server | `PYGPI=/cdn/` als **erster** Adress-Parameter, Server ergänzt ihn automatisch |
| 25 | Browser: fehlende Schrift „consolas“ (Warnung, falsche Breiten) | Liberation Mono mitgeliefert |
| 26 | Spielpaket 6,9 MB wegen bis zu 1280 px großer Rollenbilder | beim Bauen auf 256 px verkleinert → 4,7 MB |
| 27 | Lobby: − / + der Imposter-Anzahl überdeckten den Text | Buttons verschoben |
| 28 | Endbildschirm: Button-Text ragte aus dem Button | Button verbreitert |
| 29 | Werkzeugleiste brach in kleinen Fenstern um | kompakte Darstellung per CSS |
| 30 | Zwischengespeicherte, ausgegraute Buttons wurden doppelt abgedunkelt | Abdunkeln per `BLEND_RGBA_MULT` direkt im Cache-Bild |

---

## 13. Tests (durchgeführt)

Alle Tests liefen automatisiert gegen den echten Webserver (Bots über WebSocket bzw. direkt über
das TCP-Protokoll; in Phase 2 zusätzlich **echte Browser** – Microsoft Edge ohne Fenster, gesteuert
über das DevTools-Protokoll, mit echten Klicks und Tastendrücken).

### Phase 1
* **Kompletter Rundenablauf:** Raum erstellen → 3–4 Spieler → Rollenwahl per Klick → Start →
  Rollen-Intro → Kill → Todes-Animation (nur Opfer) → Leiche melden → Chat → Abstimmung mit
  Bestätigung → Rauswurf-Animation mit Role-Reveal → Sieg/Niederlage → zurück in die Lobby. ✅
* **Imposter-Sicht:** Kill-Button + rote Zielmarkierung, Kill per E, Schere in der Leiche, Cooldown 35 s,
  Melden-Button, Karte, Rollen-Panel. ✅
* **Alle 19 Rollen** einzeln: HUD, F/G/E/Leertaste/M gedrückt – kein Absturz, Buttons korrekt. ✅
* **Vladimir:** Todes-Animation → Video-Ereignis an den Browser → Rückmeldung → Geist spielt weiter. ✅
* **Überspringen-Abstimmung** → „Niemand wurde rausgeworfen“. ✅
* **Robustheit:** leerer Raum nach 10,8 s gelöscht; unbekannter Code / laufendes Spiel → verständliche
  Meldung; Müll-Pakete und halbe Pakete trennen nur den Störer; 25× Beitreten/Verlassen → IDs werden
  wiederverwendet, Spielstart klappt; Pfad-Traversal auf statische Dateien blockiert. ✅
* **Last (Server-Modus):** 8 Web-Spieler gleichzeitig laufend: je 27–30 Bilder/s. Pro Spieler ~0,4 CPU-Kern. ✅

### Phase 2
* **Regeln (15/15 bestanden):** Einstellungen per Klick gesetzt und an alle verteilt · fest zugeteilter
  Noah und David · genau 2 Imposter trotz fester Zuteilung · Falle wird allen gemeldet (67), löst aus
  und verschwindet (70) · erstes Notfall-Meeting erlaubt · Geist kann nicht chatten · David verwürfelt
  **alle** Nachrichten des Ziels · nach Zielwechsel wieder lesbar · Meeting endet nach der eingestellten
  Abstimmungszeit · zweites Notfall-Meeting desselben Spielers abgelehnt · Leiche melden geht trotzdem. ✅
* **Echte Browser (13/13 bestanden):** 3 Browser + 1 Bot · Spiel nach 3,5 s geladen · Einstellungen per
  Klick im Browser · feste Rolle · **55 FPS, 2,9 ms Rechenzeit pro Bild** · Chat im Browser · toter
  Spieler kann nicht chatten · Meeting ausgewertet · Crew-Sieg · keine Python-/JavaScript-Fehler. ✅
* **Vladimir im Browser:** Kill durch fest zugeteilten Vladimir → Todes-Animation → Video wird angezeigt,
  Geist ist solange blockiert → nach Video-Ende läuft der Geist weiter. ✅
* **Lokaler Desktop-Modus** startet weiterhin fehlerfrei. ✅
* **Browser-Version bauen** (`tools/build_web_client.py`) läuft durch (Spielpaket 4,7 MB). ✅
* `setup.sh`/`remove.sh` wurden auf Syntax geprüft (`bash -n`) und haben LF-Zeilenenden. Ein echter
  Docker-Lauf war auf dem Entwicklungsrechner (Windows ohne Docker/WSL) nicht möglich – **beim ersten
  `bash setup.sh` auf dem Ubuntu-Server bitte die Ausgabe ansehen.**

---

## 14. Bekannte Grenzen / mögliche nächste Schritte

* Es wird eine **Tastatur** gebraucht (Laptop/PC). Für Handys wären Touch-Steuerung (virtueller
  Joystick) eine Erweiterung.
* Ein Beitritt ist nur in der Lobby möglich; wer die Seite neu lädt, betritt den Raum als neuer
  Spieler (in einer laufenden Runde also erst in der nächsten).
* Die Bildrate im Browser hängt vom Gerät ab. Gemessen wurde auf einem normalen Windows-PC; sehr alte
  Laptops schaffen evtl. weniger – dann hilft der Haken „Server berechnet das Spiel“.
* Beim Einrichten (Docker-Bau) wird Internet gebraucht, weil die Browser-Laufzeit geladen wird.
* Kein eigener Crew-Sieg-Sound vorhanden (siehe optionale Dateien in Abschnitt 7).
* HTTPS ist im LAN nicht nötig; einige Browser-Funktionen (Zwischenablage) nutzen daher einen Fallback.

---

## 15. Netzwerkprotokoll – Änderungen

Client und Server müssen zusammen aktualisiert werden (sind im selben Ordner). Im Browser-Modus
laufen **dieselben Pakete** über den WebSocket `/ws/game` (base64), `web_server.py` leitet sie 1:1 an
den TCP-Port des Raums weiter.

| Paket | Richtung | vorher | jetzt |
|-------|----------|--------|-------|
| 31 Tod | S→C | `id, no_corpse, waffe, flags` | + `killer_id` (255 = keiner); `flags`: 1 Vladimir, 2 Rauswurf, 4 Falle, 8 Fenster, 16 Explosion |
| 43 Meeting-Ende | S→C | `evicted_id` | `evicted_id, ergebnis (0 raus, 1 übersprungen, 2 Gleichstand, 3 unsterblich), team, rolle, imposter_übrig` – kommt jetzt **vor** der Siegprüfung |
| 83 Rollen-Aufdeckung | S→C | – | neu: am Spielende `n, (id, team, rolle)*n` |
| 21 Fortschritt | S→C | erst nach der 1. Aufgabe | zusätzlich direkt beim Spielstart |
| 5/15/3 Start | S→C | einzeln gesendet | als ein Block (Reihenfolge gleich) |
| **16** Einstellungen setzen | C→S | – | neu (Phase 2): `cooldown, diskussion, abstimmung` (je 1 Byte, Sekunden) – nur Host, nur Lobby, Server begrenzt die Werte |
| **17** Einstellungen | S→C | – | neu: `cooldown, diskussion, abstimmung` – an alle nach Änderung, beim Beitritt und beim Start |
| **18** feste Rolle setzen | C→S | – | neu: `spieler_id, code` (255 Zufall, 254 Imposter, 253 Crewmate, sonst Rollen-ID) – nur Host |
| **19** feste Rollen | S→C | – | neu: `n, (spieler_id, code)*n` – **nur an den Host** |
| **67** Falle gelegt | S→C | – (nur Noahs eigener Client kannte die Fallen) | neu: an **alle**: `fallen_id (2 Byte), besitzer, x, y` |
| **70** Falle weg | S→C | – | neu: `fallen_id (2 Byte)` – ausgelöst oder entfernt |
| 40 Meeting | C→S | – | Notfallknopf: 1× pro Spieler/Runde und erst nach dem Cooldown; Melden immer |
| 50 Chat | C→S | – | Nachrichten toter Spieler werden verworfen; Davids Ziel wird dauerhaft verwürfelt |

Ports: Web **80/8080** (von außen), Räume **6100–6199** nur intern im Container.
Neue Server-Kommandozeile: `python server.py [--host IP] [--port N] [--room CODE]` (ohne Argumente wie bisher).

Neue Web-Adressen: `/play/` (Spielseite + Spielpaket), `/cdn/` (Browser-Laufzeit), `/ws/game`
(Spiel-WebSocket), `/api/info` meldet zusätzlich `browser_client`.

---

## 16. Änderungsprotokoll

### Phase 1

**Assets**
* `Assets/Sounds/` angelegt, alle 10 MP3s aus `SoundeffectsAmogus` kopiert (Namen unverändert).

**server.py**
* Kommandozeilen-Argumente `--host/--port/--room`, Statuszeilen `@@STATUS {…}` für die Raumliste.
* `recv_exact`, Nutzlast wird vor dem Sperren komplett gelesen, `state_lock`, Sende-Lock je Client,
  Sende-Timeout 10 s, Handshake-Timeout 5 s in eigenem Thread, zeilenweise thread-sichere Logs.
* Freie-ID-Vergabe, Beitritt während laufender Runde abgelehnt, `SO_EXCLUSIVEADDRUSE` unter Windows.
* Pakete 31/43 erweitert, Paket 83 neu, Crew-Sieg bei 0 Imposter, Imposter-Sieg-Bedingung korrigiert,
  laufendes Meeting wird beim Spielende abgebrochen, Host-/Spiel-Prüfungen für 11/13/99/30/20.
* Davids Verwürfelung nur für die nächste Nachricht (in Phase 2 wieder geändert).

**main.py**
* Web-Sitzungsmodus (`--web-session`): festes 1440×810-Bild statt Vollbild, direkter Beitritt,
  Bildausgabe über `web_bridge`, Q beendet nicht, sauberes Beenden.
* Sounds an allen in Abschnitt 7 genannten Stellen.
* Empfangs-Thread: `recv_exact`, `LockedSocket`, neue Paketformate, Paket 83, Aufträge an die
  Hauptschleife (`ui_events`) statt Grafik im Thread.
* Animationen eingebunden (Tod, Rauswurf, Intro, Sieg/Niederlage), Siege warten auf laufende Animationen.
* Neues HUD: `build_action_buttons`, `role_ability_spec`, `draw_left_panel`, `draw_game_hud`,
  Weltmarkierungen (`draw_task_buttons` neu, `draw_world_highlights`), klickbare Buttons.
* Fehlerbehebungen aus Abschnitt 12 (Client-Seite), Raum-Code in der Lobby.

**Neu:** `web_server.py`, `web_bridge.py`, `sound.py`, `fx.py`, `hud.py`, `web/index.html`,
`web/style.css`, `web/app.js`, `Dockerfile`, `requirements-server.txt`, `setup.sh`, `remove.sh`,
`start_lokal_windows.bat`, `.dockerignore`, `.gitattributes`, `.gitignore`, `DOKUMENTATION.md`.

### Phase 2

**roles.py** (nur ergänzt, bestehende Rollen unverändert)
* Gemeinsame Regeln für Server und Client: `max_imposters_for`, `setup_status` (prüft Rollen-Setup
  inkl. fester Zuteilungen), Codes `FIXED_NONE/CREW/IMPOSTER`, `FIXED_OPTIONS`, `fixed_team`, `fixed_label`.

**server.py**
* Einstellungen `settings` (Pakete 16/17) mit Grenzen `SETTING_LIMITS`; Meeting-Timer aus den
  Einstellungen (`start_meeting_timer`), Diskussionszeit 0 = direkt abstimmen.
* Notfall-Meeting: `emergency_used` (1× pro Spieler), `emergency_ready_at` (Cooldown ab Spielstart
  und ab Meeting-Ende).
* Feste Rollen `fixed_roles` (Pakete 18/19): beim Start zuerst vergeben, Rest zufällig; Weitergabe an
  neuen Host; Aufräumen beim Verlassen.
* Chat (50): Tote werden ignoriert; David: `david_targets` – alle Nachrichten des Ziels verwürfelt, bis
  David neu wählt (65).
* Fallen: Paket 67 an alle, neues Paket 70 beim Auslösen/Entfernen.

**main.py**
* Browser-Modus (`BROWSER = sys.platform == "emscripten"`): `browser_bridge` statt `web_bridge`,
  `browser_start`/`browser_net_step` (Handshake, Paket-Zerlegung), Ladeanzeige `draw_connecting`,
  Beitritts-Timeout 20 s, asynchrone Hauptschleife `main_loop()` mit `await asyncio.sleep(0)`,
  Aufräumen in `shutdown_game()`.
* Paketverarbeitung aus dem Empfangs-Thread in `handle_packet()` ausgelagert (Desktop: Thread,
  Browser: pro Bild); `finish_connect()` gemeinsam für beide.
* Neue Lobby-Zustände `settings`, `role_assign`, `connecting`; Menüs EINSTELLUNGEN, ZUTEILEN,
  ROLLEN-INFO mit Detailfenster; Layout `get_lobby_layout()`.
* Pakete 17/19/67/70; NOTFALL-Button mit Cooldown/„VERBRAUCHT“; Chat-Sperre für Geister; Fallen für alle.
* Leistung: zusammengefügte Karten (`map_combined`, `lobby_combined`), Text-/Panel-Caches
  (`left_panel_model`), Abdunkel-Flächen aus dem Cache, zeitbasiertes Intro, zeitbasierte Bewegung
  (`Player.move(..., speed_factor)`), Messwerkzeug `perf_mark`/`perf_frame_end`.
* Schriften über `fonts.install`.

**fx.py / hud.py** – Caches (`text`, `render_cached`, `dim_surface`, `blit_alpha`, Button-/Karten-/
Banner-Cache), Animationen ohne Bildkopien, Endbildschirm friert nach dem Einschwingen ein,
breiterer Endbildschirm-Button.

**web_server.py** – `/play/` (mit automatischem `PYGPI`), `/cdn/`, `/ws/game` (WebSocket↔TCP-Brücke
`BridgeSession`, verständliche Abbruchgründe), `api_info.browser_client`, Hilfeseite, falls die
Browser-Version fehlt.

**web/** – Startseite: Haken „Server berechnet das Spiel“ (gespeichert), Beitritt öffnet standardmäßig
`/play/…`; neu `client_template.tmpl`, `game_glue.js`, `audio.js` (Sound-Code aus `app.js` ausgelagert).

**Neu:** `browser_bridge.py`, `fonts.py`, `Assets/Fonts/` (Liberation Sans/Mono + Lizenz),
`tools/build_web_client.py`.

**Build/Betrieb** – `Dockerfile` installiert pygbag 0.9.3, spiegelt die Laufzeit in einer eigenen
Schicht und baut das Spielpaket; `.dockerignore`/`.gitignore` ignorieren `build/`, `web/cdn/`,
`web/client/`; `start_lokal_windows.bat` baut vor dem Start die Browser-Version; `web_bridge.py` nutzt
`fonts.install`.

**Hinweis Git:** Die Änderungen sind noch **nicht committet**. Die schon früher eingecheckten
`__pycache__/*.pyc` ändern sich bei jedem Start – wer sie loswerden will:
`git rm -r --cached __pycache__`. Damit `setup.sh`/`remove.sh` nach einem `git clone` direkt
ausführbar sind: `git update-index --chmod=+x setup.sh remove.sh` (sonst einfach `bash setup.sh`).

**Unverändert:** `tasks.py`, `Meeting.py`, `maptest.py`, `Task_test.py`, alle Grafiken im Projekt
(verkleinerte Rollenbilder entstehen nur im Browser-Paket).
