@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name YouTubeImporter --collect-all yt_dlp main.py
if errorlevel 1 goto :error
copy /Y "prototype\resolve_import_bridge.lua" "dist\resolve_import_bridge.lua" >nul
if errorlevel 1 goto :error
copy /Y "Installa bridge Resolve.bat" "dist\Installa bridge Resolve.bat" >nul
if errorlevel 1 goto :error
copy /Y "README.md" "dist\README.md" >nul
if errorlevel 1 goto :error
powershell -NoProfile -Command "Compress-Archive -Path '%CD%\dist\YouTubeImporter.exe','%CD%\dist\resolve_import_bridge.lua','%CD%\dist\Installa bridge Resolve.bat','%CD%\dist\README.md' -DestinationPath '%CD%\dist\YouTubeImporter-Windows.zip' -Force"
if errorlevel 1 goto :error
echo.
echo EXE creato: %CD%\dist\YouTubeImporter.exe
echo Pacchetto pronto: %CD%\dist\YouTubeImporter-Windows.zip
pause
exit /b 0
:error
echo Build non riuscita. Controlla il messaggio di errore precedente.
pause
exit /b 1
