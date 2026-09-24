#!/usr/bin/env bash
# Thalheimer is Among Us - Server wieder entfernen (Container + Image loeschen).
set -euo pipefail
NAME="thalheimer-among-us"
IMAGE="thalheimer-among-us:latest"

if [ "$(id -u)" -ne 0 ]; then
    exec sudo -E bash "$(readlink -f "$0")" "$@"
fi

if docker rm -f "$NAME" >/dev/null 2>&1; then
    echo "Container '$NAME' gestoppt und geloescht."
else
    echo "Kein Container '$NAME' gefunden."
fi
if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker rmi "$IMAGE" >/dev/null
    echo "Image '$IMAGE' geloescht."
fi
echo "Fertig. Der Spielserver startet nicht mehr automatisch."
