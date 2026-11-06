@echo off
cd /d "%~dp0.."
echo Invio a DaVinci Resolve il video locale di prova...
python "%~dp0client.py" --file "%~dp0test_assets\resolve-free-import-test.mp4" --timeout 30
echo.
echo Il risultato deve indicare "ok": true e il nome della timeline.
pause
