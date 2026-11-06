@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
if not exist ".venv\Lib\site-packages\PySide6" (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)
.venv\Scripts\python.exe main.py
if errorlevel 1 pause
goto :eof
:error
echo Installazione dipendenze non riuscita. Controlla la connessione e riprova.
pause
