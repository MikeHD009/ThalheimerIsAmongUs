# Thalheimer is Among Us - Server-Container
# Wird von setup.sh automatisch gebaut und gestartet.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SDL_VIDEODRIVER=dummy \
    SDL_AUDIODRIVER=dummy \
    PYGAME_HIDE_SUPPORT_PROMPT=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    PORT=8080

# fontconfig: damit pygame Schriften findet (Arial-Ersatz liegt in Assets/Fonts)
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-liberation fontconfig \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f

WORKDIR /app
COPY requirements-server.txt .
RUN pip install -r requirements-server.txt pygbag==0.9.3

# Browser-Laufzeit (Python + pygame als WebAssembly, ca. 22 MB) EINMAL laden und im Container
# ablegen - eigene Docker-Schicht, damit sie bei Code-Aenderungen nicht neu geladen werden muss.
COPY tools/build_web_client.py tools/
RUN python tools/build_web_client.py --mirror-only

COPY . .

# Browser-Version des Spiels bauen (das Spiel laeuft spaeter auf den Geraeten der Spieler)
RUN python tools/build_web_client.py --client-only \
 && rm -rf build

# Nicht als root laufen
RUN useradd --create-home --uid 1000 spiel && chown -R spiel:spiel /app
USER spiel

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/rooms' % os.environ.get('PORT','8080'), timeout=4)" || exit 1

CMD ["python", "web_server.py"]
