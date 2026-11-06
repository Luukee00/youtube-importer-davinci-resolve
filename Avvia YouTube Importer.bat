@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creo l'ambiente Python dell'applicazione...
  py -3.13 -m venv .venv
  if errorlevel 1 goto :python_error
)
if not exist ".venv\Lib\site-packages\PySide6\__init__.py" goto :install
if not exist ".venv\Lib\site-packages\yt_dlp\__init__.py" goto :install
goto :run
:install
echo Installo le dipendenze al primo avvio. Attendi il completamento...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :error
:run
.venv\Scripts\python.exe main.py
if errorlevel 1 pause
goto :eof
:python_error
echo Python 3.13 non trovato. Installa Python seguendo il README e riapri questa finestra.
pause
exit /b 1
:error
echo Installazione dipendenze non riuscita. Controlla la connessione e riprova.
pause
