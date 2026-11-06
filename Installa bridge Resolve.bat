@echo off
setlocal
set "SOURCE=%~dp0resolve_bridge\resolve_import_bridge.lua"
if not exist "%SOURCE%" (
  echo Non trovo resolve_bridge\resolve_import_bridge.lua nella cartella del progetto.
  pause
  exit /b 1
)
set "DEST=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
if not exist "%DEST%" mkdir "%DEST%"
if errorlevel 1 (
  echo Impossibile creare la cartella degli script Resolve:
  echo %DEST%
  pause
  exit /b 1
)
copy /Y "%SOURCE%" "%DEST%\YouTubeImporterBridge.lua" >nul
if errorlevel 1 (
  echo Copia del bridge non riuscita.
  pause
  exit /b 1
)
echo Bridge installato correttamente in:
echo %DEST%\YouTubeImporterBridge.lua
echo Avvia Resolve e lancia Workspace ^> Scripts ^> Utility ^> YouTubeImporterBridge.
pause
