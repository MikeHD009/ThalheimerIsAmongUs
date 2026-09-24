@echo off
REM Thalheimer is Among Us - Web-Version lokal unter Windows testen (ohne Docker).
REM Danach im Browser http://localhost:8080 oeffnen (andere im WLAN: http://<deine-IP>:8080).
cd /d "%~dp0"
python -m pip install -r requirements-server.txt pygbag==0.9.3
REM Browser-Version bauen (beim ersten Mal werden ca. 22 MB Laufzeit geladen)
python tools\build_web_client.py
python web_server.py
pause
