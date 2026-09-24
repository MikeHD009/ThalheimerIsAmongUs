#!/usr/bin/env bash
# =====================================================================
#  Thalheimer is Among Us - Server einrichten (Ubuntu)
#
#  Aufruf im Projektordner:   ./setup.sh        (oder: bash setup.sh)
#
#  Was passiert:
#   1. Docker wird installiert, falls es fehlt (und beim Systemstart aktiviert)
#   2. Aus DIESEM Ordner wird ein Container-Image gebaut
#   3. Der Container wird gestartet und startet ab jetzt automatisch neu -
#      auch nach einem Neustart des Servers - bis er mit ./remove.sh geloescht wird
#   4. Der Beitrittslink fuer das WLAN wird angezeigt
#
#  Optionen (Umgebungsvariablen):
#   PORT=8080 ./setup.sh     festen Port waehlen (Standard: 80, falls frei, sonst 8080)
# =====================================================================
set -euo pipefail

NAME="thalheimer-among-us"
IMAGE="thalheimer-among-us:latest"

cd "$(dirname "$(readlink -f "$0")")"

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[FEHLER]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------- root-Rechte (Docker + Paketinstallation brauchen sie) ----------
if [ "$(id -u)" -ne 0 ]; then
    say "Administrator-Rechte werden benoetigt (sudo) ..."
    exec sudo -E bash "$(readlink -f "$0")" "$@"
fi

[ -f Dockerfile ] && [ -f web_server.py ] && [ -f main.py ] \
    || fail "setup.sh muss im Projektordner liegen (neben Dockerfile, main.py, web_server.py)."

# ---------- 1. Docker ----------
if ! command -v docker >/dev/null 2>&1; then
    say "Docker ist nicht installiert - wird jetzt installiert ..."
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
    else
        fail "Kein apt-get gefunden. Bitte Docker manuell installieren: https://docs.docker.com/engine/install/"
    fi
fi
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now docker >/dev/null 2>&1 || warn "Docker-Dienst konnte nicht per systemctl aktiviert werden."
fi
docker info >/dev/null 2>&1 || fail "Docker laeuft nicht. Pruefe mit: systemctl status docker"

# ---------- 2. Image bauen (die alte Version laeuft waehrenddessen weiter) ----------
say "Baue das Spiel-Image (beim ersten Mal dauert das ein paar Minuten) ..."
docker build -t "$IMAGE" .

# ---------- 3. Alte Version ersetzen + Port waehlen ----------
docker rm -f "$NAME" >/dev/null 2>&1 || true

port_in_use() {
    if command -v ss >/dev/null 2>&1; then
        [ -n "$(ss -ltnH "( sport = :$1 )" 2>/dev/null)" ]
    else
        (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
    fi
}
if [ -z "${PORT:-}" ]; then
    if port_in_use 80; then
        PORT=8080
        if port_in_use "$PORT"; then
            fail "Port 80 und 8080 sind belegt. Starte mit freiem Port, z.B.: PORT=8090 ./setup.sh"
        fi
    else
        PORT=80
    fi
elif port_in_use "$PORT"; then
    fail "Port $PORT ist belegt. Bitte einen anderen waehlen: PORT=8090 ./setup.sh"
fi

# ---------- 4. Container starten ----------
IPS="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | grep -v '^127\.' | grep -v '^172\.17\.' || true)"
URLS=""
for ip in $IPS; do
    if [ "$PORT" = "80" ]; then u="http://$ip"; else u="http://$ip:$PORT"; fi
    URLS="${URLS:+$URLS,}$u"
done

say "Starte den Container '$NAME' auf Port $PORT ..."
docker run -d \
    --name "$NAME" \
    --restart unless-stopped \
    -p "$PORT:8080" \
    -e PUBLIC_PORT="$PORT" \
    -e PUBLIC_URLS="$URLS" \
    --log-opt max-size=10m --log-opt max-file=3 \
    "$IMAGE" >/dev/null

# ---------- 5. Firewall (falls ufw aktiv ist) ----------
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    say "Firewall: Port $PORT/tcp wird freigegeben ..."
    ufw allow "$PORT/tcp" >/dev/null || warn "ufw-Regel konnte nicht gesetzt werden."
fi

# ---------- 6. Warten bis der Server antwortet ----------
say "Warte auf den Spielserver ..."
ok=0
for _ in $(seq 1 30); do
    if docker exec "$NAME" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/rooms', timeout=2)" >/dev/null 2>&1; then
        ok=1; break
    fi
    sleep 1
done
[ "$ok" = "1" ] || { docker logs --tail 50 "$NAME" || true; fail "Der Server antwortet nicht. Log siehe oben."; }

echo
printf '\033[1;32m%s\033[0m\n' "============================================================"
printf '\033[1;32m%s\033[0m\n' "  Thalheimer is Among Us laeuft!"
printf '\033[1;32m%s\033[0m\n' "============================================================"
if [ -n "$URLS" ]; then
    echo "  Beitrittslink(s) - im selben WLAN im Browser oeffnen:"
    echo "$URLS" | tr ',' '\n' | sed 's/^/     /'
else
    echo "  Beitrittslink: http://<IP-dieses-Servers>$( [ "$PORT" = "80" ] || echo ":$PORT" )"
fi
echo
echo "  Der Server startet ab jetzt automatisch (auch nach Neustart)."
echo "  Logs ansehen:     sudo docker logs -f $NAME"
echo "  Neu einrichten:   ./setup.sh      Entfernen:  ./remove.sh"
echo
