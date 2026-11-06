@echo off
cd /d "%~dp0.."
echo Controllo la connessione a DaVinci Resolve...
python "%~dp0client.py" --ping --timeout 15
echo.
echo Se il bridge risponde, sopra vedrai "ok": true.
pause
