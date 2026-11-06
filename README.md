# YouTube Importer per DaVinci Resolve

Applicazione Windows per scaricare video/audio da YouTube e inviare i file a DaVinci Resolve Free. Il video può essere aggiunto alla timeline attiva, importato soltanto nel Media Pool oppure salvato senza aprire Resolve.

> Usa il programma solo per contenuti che hai il diritto di scaricare. Non aggira DRM o restrizioni di accesso. YouTube e yt-dlp possono modificare i propri sistemi: il download può smettere di funzionare finché yt-dlp non viene aggiornato.

## Funzionalità

- Interfaccia Windows in italiano: URL, titolo automatico, modalità video/audio, qualità, nome e cartella di destinazione.
- Download con yt-dlp, aggiornamento dello stato, percentuale, velocità e annullamento.
- Muxing e conversione con FFmpeg/FFprobe. I video già compatibili (H.264/AAC) non vengono ricodificati.
- Quando serve H.264, prova gli encoder hardware NVENC, Intel Quick Sync e AMD AMF; se nessuno è utilizzabile, ricorre a x264 su CPU.
- Bridge Lua locale per importare in Resolve Free senza socket, cloud o API Studio.
- L’importazione in timeline usa la timeline attiva e aggiunge la clip in coda, senza sovrascrivere le clip esistenti.
- Pulsante finale **OK** per chiudere l’applicazione dopo un’operazione riuscita.

## Requisiti

### Avvio dal sorgente

- Windows 10/11 a 64 bit.
- Python 3.10 o successivo, installato con il launcher `py` disponibile nel prompt.
- FFmpeg e FFprobe installati e raggiungibili dal `PATH` di Windows.
- DaVinci Resolve Free per importare in Resolve. Resolve deve essere aperto con il progetto e la timeline desiderati.

### Applicazione EXE

L’EXE include Python, PySide6 e yt-dlp. **FFmpeg/FFprobe e DaVinci Resolve non sono inclusi**: installa FFmpeg e aggiungilo al `PATH`; avvia Resolve per usare il bridge. Il test dell’EXE compilato dipende dal PC e va fatto prima della distribuzione ad altri utenti.

## Installazione e uso dal sorgente

1. Installa Python 3.10+ e FFmpeg/FFprobe. In PowerShell, verifica con `py -3 --version`, `ffmpeg -version` e `ffprobe -version`.
2. Scarica o clona questo repository.
3. Fai doppio clic su **Avvia YouTube Importer.bat**. Al primo avvio crea `.venv` e installa le dipendenze Python.
4. Per importare in Resolve, installa il bridge come descritto sotto e avvialo in ogni sessione di Resolve.
5. Incolla il link, scegli **Video + audio** o **Solo audio**, qualità e destinazione; seleziona l’azione e premi **Scarica e importa**.
6. Attendi il download, il muxing/la conversione e l’importazione. Se l’operazione riesce, i dettagli residui si azzerano e compare **OK**.

### Installazione del bridge Lua

1. Chiudi DaVinci Resolve prima di installare o aggiornare il file.
2. Esegui **Installa bridge Resolve.bat** dalla cartella del progetto o dalla cartella dell’EXE distribuito. Lo script copia `resolve_import_bridge.lua` qui:

   `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\YouTubeImporterBridge.lua`

3. Avvia Resolve, apri il progetto e seleziona la timeline desiderata.
4. Nel menu di Resolve seleziona **Workspace → Scripts → Utility → YouTubeImporterBridge**. Lascia Resolve aperto. Va eseguito una volta dopo ogni riavvio di Resolve.
5. Nell’importer premi **Verifica connessione a DaVinci Resolve**. Il bridge deve essere attivo prima del download se vuoi l’importazione automatica.

Non serve installare lo script nella cartella di sistema né avviare DaVinci Resolve Studio.

### Modalità disponibili

- **Importa e aggiungi alla timeline attiva**: richiede un progetto e una timeline aperti. La clip viene aggiunta in fondo alla timeline, non al playhead.
- **Importa solo nel Media Pool**: richiede un progetto aperto, ma non una timeline.
- **Scarica soltanto**: non richiede che Resolve sia aperto.

Se non è disponibile una timeline attiva, il programma non ne crea una automaticamente. Un file scaricato correttamente resta nella cartella scelta anche se l’importazione non riesce.

## Creazione dell’EXE

1. Dal sorgente, fai doppio clic su **Crea EXE.bat**. È necessaria una connessione Internet per installare PyInstaller la prima volta.
2. Al termine trovi `dist\YouTubeImporter.exe`, il bridge, l’installer e le istruzioni in `dist\YouTubeImporter-Windows.zip`.
3. Sul computer di destinazione estrai lo ZIP, installa FFmpeg/FFprobe, esegui l’installer del bridge, avvia Resolve e poi l’EXE.

PyInstaller può far scattare avvisi di Windows Defender perché l’EXE non è firmato. Il progetto non include un certificato di firma.

## Avvio manuale per sviluppo

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

CLI per verificare il bridge o importare un file locale:

```powershell
python prototype\client.py --ping
python prototype\client.py --file "C:\percorso\video.mp4"
```

Il client scrive la richiesta in `%USERPROFILE%\.ytresolve-importer\request.lua`; il bridge legge solo azioni predefinite (`ping`, `import_pool`, `import_append`), senza eseguire codice Lua ricevuto dall’app. I risultati e gli errori vengono restituiti all’app. I log restano in `%USERPROFILE%\.ytresolve-importer\bridge_debug.log`.

## Diagnostica

- **Bridge non raggiungibile**: avvia Resolve, apri un progetto e la timeline, rilancia lo script dal menu Workspace → Scripts e verifica che Resolve resti aperto.
- **Nessun progetto/timeline**: apri un progetto; per l’aggiunta in timeline seleziona anche una timeline.
- **CPU alta o conversione lenta**: controlla lo stato mostrato. Se compare Quick Sync/NVENC/AMF è in uso un encoder hardware; se compare CPU, il programma sta usando il fallback x264. La disponibilità dipende da GPU, driver e build FFmpeg.
- **FFmpeg non trovato**: aggiungi al `PATH` la cartella che contiene `ffmpeg.exe` e `ffprobe.exe`, poi riavvia l’importer.
- **Download completo ma importazione fallita**: il file resta nella cartella di destinazione; il messaggio dell’app distingue il download dall’importazione.
- **Errore yt-dlp**: aggiorna le dipendenze con `.venv\Scripts\python.exe -m pip install --upgrade yt-dlp`.
- **Diagnostica bridge**: consulta la console Lua di Resolve per righe `YTDIAG` e `%USERPROFILE%\.ytresolve-importer\bridge_debug.log` per le richieste del client.

## Architettura

- `main.py`: interfaccia PySide6, worker asincroni, download e conversione.
- `prototype/client.py`: client IPC locale e lettura delle preferenze Fusion.
- `prototype/resolve_import_bridge.lua`: polling delle richieste e uso dell’API Resolve dall’interno dell’applicazione.
- `requirements.txt`: dipendenze Python dell’applicazione.
- `Avvia YouTube Importer.bat`: avvio dal sorgente.
- `Crea EXE.bat`: build PyInstaller.
- `Installa bridge Resolve.bat`: installazione del bridge Lua.

## Verifiche e compatibilità

Verifiche effettuate sulla **DaVinci Resolve Free 20.2.3.6** installata su Windows:

- Risposta `ok: true` dal ping del bridge Lua.
- Importazione di un MP4 locale nel Media Pool e aggiunta alla timeline attiva, con risposta `ok: true`.
- Download video YouTube, conversione con Intel Quick Sync mostrata nell’interfaccia e importazione riuscita nella timeline attiva.
- Avvio della GUI e controllo sintattico Python dopo le modifiche recenti.

Non dichiarati come verificati: Resolve 21.x, modalità audio-only WAV/MP3/M4A singolarmente, esecuzione dell’EXE su un altro computer, assenza di progetto/timeline, annullamento durante ogni fase e altri encoder hardware. La compatibilità può variare tra versioni di Resolve, driver GPU, FFmpeg e yt-dlp.

L’importazione automatica è confermata sulla sola versione Free indicata. Il bridge va avviato manualmente a ogni sessione di Resolve: l’avvio automatico persistente non è implementato.

## Licenze

Questo repository non dichiara una licenza open source per il codice del progetto. Le dipendenze (tra cui PySide6, yt-dlp e FFmpeg) mantengono le rispettive licenze; verifica i relativi termini prima di redistribuire un pacchetto compilato.
