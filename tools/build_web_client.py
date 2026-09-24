"""NEU: Baut die Browser-Version des Spiels (WebAssembly mit pygbag) fuer web_server.py.

Aufruf (im Projektordner):   python tools/build_web_client.py
Voraussetzung:               pip install pygbag==0.9.3   (im Container automatisch)

Was passiert:
  1. Die WebAssembly-Laufzeit (Python + pygame fuer den Browser, ca. 22 MB) wird EINMAL aus dem
     Internet geladen und unter web/cdn/ abgelegt. Danach liefert der eigene Server sie aus ->
     Spieler brauchen kein Internet, nur das WLAN.
  2. Die fuer das Spiel noetigen Dateien (main.py, tasks.py, ..., Grafiken, Schriften) werden in
     build/client_src/thalheimer zusammengestellt (ohne Server-Dateien, Video, Sounds).
  3. pygbag packt daraus web/client/ (index.html + thalheimer.tar.gz).
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "build", "client_src", "thalheimer")
OUT = os.path.join(ROOT, "web", "client")
CDN_DIR = os.path.join(ROOT, "web", "cdn")
TEMPLATE = os.path.join(ROOT, "web", "client_template.tmpl")

PYGBAG_VERSION = "0.9.3"
CDN_SOURCE = "https://pygame-web.github.io/cdn/"
RUNTIME_FILES = [
    f"{PYGBAG_VERSION}/pythons.js",
    f"{PYGBAG_VERSION}/cpythonrc.py",
    f"{PYGBAG_VERSION}/empty.html",
    f"{PYGBAG_VERSION}/empty.ogg",
    f"{PYGBAG_VERSION}/cpython312/main.js",
    f"{PYGBAG_VERSION}/cpython312/main.wasm",
    f"{PYGBAG_VERSION}/cpython312/main.data",
    f"index-{PYGBAG_VERSION}-cp312.json",
    "cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl",
]

CLIENT_FILES = ["main.py", "tasks.py", "roles.py", "sound.py", "fx.py", "hud.py", "fonts.py", "browser_bridge.py"]
CLIENT_DIRS = ["Assets/Character", "Assets/Items", "Assets/Fonts"]
CLIENT_MAP_FILES = ["Floor.png", "Walls.png", "Objects.png", "Lobby.png", "Hitboxes.json", "Lobby.json"]


def log(*args):
    print("[BUILD]", *args, flush=True)


def mirror_runtime():
    for rel in RUNTIME_FILES:
        dest = os.path.join(CDN_DIR, *rel.split("/"))
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        url = CDN_SOURCE + rel
        log("lade", url)
        tmp = dest + ".part"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                    shutil.copyfileobj(r, f)
                os.replace(tmp, dest)
                break
            except Exception as e:
                log(f"  Fehler ({e}), neuer Versuch ...")
                time.sleep(2 + attempt * 3)
        else:
            raise SystemExit(f"Konnte {url} nicht laden - ist der Server beim Einrichten online?")
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _d, fs in os.walk(CDN_DIR) for f in fs)
    log(f"Laufzeit vorhanden in web/cdn ({total / 1e6:.1f} MB)")


def stage_client():
    if os.path.exists(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)
    for name in CLIENT_FILES:
        shutil.copy2(os.path.join(ROOT, name), os.path.join(STAGE, name))
    for rel in CLIENT_DIRS:
        shutil.copytree(os.path.join(ROOT, *rel.split("/")), os.path.join(STAGE, *rel.split("/")))
    map_dir = os.path.join(STAGE, "Assets", "Map", "Map")
    os.makedirs(map_dir)
    for name in CLIENT_MAP_FILES:
        shutil.copy2(os.path.join(ROOT, "Assets", "Map", "Map", name), os.path.join(map_dir, name))
    shrink_role_images()
    log("Spieldateien zusammengestellt in", os.path.relpath(STAGE, ROOT))


def shrink_role_images(max_side=256):
    """Rollenbilder sind bis zu 1280 px gross, im Spiel aber hoechstens ~135 px -> kleiner laden."""
    try:
        from PIL import Image
    except ImportError:
        return
    folder = os.path.join(STAGE, "Assets", "Character", "Roles")
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not name.lower().endswith(".png"):
            continue
        with Image.open(path) as img:
            if max(img.size) <= max_side:
                continue
            img = img.convert("RGBA")
            img.thumbnail((max_side, max_side), Image.LANCZOS)
            img.save(path, optimize=True)


def build_client():
    icon = os.path.join(ROOT, "build", "favicon.png")
    shutil.copy2(os.path.join(ROOT, "Assets", "Character", "All_colors", "red.png"), icon)
    cmd = [sys.executable, "-m", "pygbag", "--build", "--no_opt",
           "--template", TEMPLATE, "--cdn", f"/cdn/{PYGBAG_VERSION}/",
           "--title", "Thalheimer is Among Us", "--icon", icon, STAGE]
    log("pygbag:", " ".join(cmd[3:]))
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(cmd, cwd=os.path.join(ROOT, "build"), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace")
    web = os.path.join(STAGE, "build", "web")
    if result.returncode != 0 or not os.path.exists(os.path.join(web, "thalheimer.tar.gz")):
        print(result.stdout[-4000:])
        raise SystemExit("pygbag-Build fehlgeschlagen")
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for name in ("index.html", "thalheimer.tar.gz", "favicon.png"):
        shutil.copy2(os.path.join(web, name), os.path.join(OUT, name))
    with open(os.path.join(OUT, "build_info.json"), "w", encoding="utf-8") as f:
        json.dump({"built": time.strftime("%Y-%m-%d %H:%M:%S"), "pygbag": PYGBAG_VERSION}, f)
    size = os.path.getsize(os.path.join(OUT, "thalheimer.tar.gz"))
    log(f"Browser-Version fertig: web/client/ (Spielpaket {size / 1e6:.1f} MB)")


def main():
    """--mirror-only: nur die Laufzeit spiegeln (Docker-Schicht, die zwischengespeichert wird)
    --client-only: nur das Spielpaket bauen (Laufzeit schon vorhanden)"""
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    if "--client-only" not in sys.argv:
        mirror_runtime()
    if "--mirror-only" not in sys.argv:
        stage_client()
        build_client()


if __name__ == "__main__":
    main()
