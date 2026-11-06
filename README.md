# YouTube Importer per DaVinci Resolve

Programma Windows con interfaccia in italiano per scaricare video o audio da YouTube e, se vuoi, importarli nel progetto aperto in DaVinci Resolve Free.

> Usalo solo per scaricare contenuti che hai il diritto di usare. Il programma non aggira DRM o restrizioni di accesso.

## Installazione e primo avvio

Segui questi passaggi nell’ordine. Non serve Git e non devi creare un file EXE.

### 1. Installa Python e FFmpeg

Su Windows 10/11 apri **PowerShell** e incolla questi comandi, uno alla volta:

```powershell
winget install --exact --id Python.Python.3.13
winget install --exact --id Gyan.FFmpeg
```

Se Windows chiede di accettare i termini delle sorgenti o dei pacchetti, digita `Y` e premi Invio. Al termine chiudi PowerShell e aprilo di nuovo.

Controlla che tutti e tre i comandi rispondano con informazioni di versione:

```powershell
py -3.13 --version
ffmpeg -version
ffprobe -version
```

Se `winget` non è disponibile, installa Python dal [sito ufficiale Python](https://www.python.org/downloads/windows/) e FFmpeg dal [sito del progetto FFmpeg](https://ffmpeg.org/download.html). Per Python installa la versione 3.13 e assicurati che il comando `py` sia disponibile.

### 2. Scarica il progetto

1. Apri il [repository GitHub](https://github.com/Luukee00/youtube-importer-davinci-resolve).
2. Premi il pulsante verde **Code** e scegli **Download ZIP**.
3. In Esplora file fai clic destro sul file ZIP scaricato, scegli **Estrai tutto…** e poi **Estrai**.

### 3. Avvia l’applicazione

1. Apri la cartella estratta.
2. Fai doppio clic su **Avvia YouTube Importer.bat**.
3. Al primo avvio il programma crea il proprio ambiente Python e scarica le dipendenze. Serve Internet; attendi che termini.
4. Si apre la finestra **YouTube Importer per DaVinci Resolve**. Lascia aperta la finestra nera mentre l’applicazione è in uso.

Ai successivi avvii basta fare doppio clic sullo stesso file `.bat`.

## Collega DaVinci Resolve (una volta per ogni avvio di Resolve)

Questi passaggi servono solo per importare direttamente in Resolve. Per scaricare un file sul PC puoi saltare questa sezione.

1. Chiudi DaVinci Resolve.
2. Dalla cartella del progetto fai doppio clic su **Installa bridge Resolve.bat**. Non serve avviarlo come amministratore.
3. Quando compare il messaggio di completamento, premi un tasto per chiudere la finestra.
4. Avvia DaVinci Resolve e apri il progetto in cui vuoi lavorare.
5. Se vuoi inserire il video in timeline, apri anche la timeline corretta.
6. Nel menu di Resolve scegli **Workspace → Scripts → Utility → YouTubeImporterBridge**. Lascia Resolve aperto.
7. Nell’importer premi **Verifica connessione a DaVinci Resolve**. Deve comparire la conferma della connessione.

Il punto 6 va ripetuto dopo ogni riavvio di DaVinci Resolve. Il bridge usa solo funzioni locali di Resolve Free; non servono Resolve Studio, account o servizi cloud.

## Scarica e importa un video

1. Copia l’indirizzo del video YouTube e incollalo in **Link YouTube**.
2. Scegli **Video + audio**.
3. Seleziona la qualità video, il nome del file e la cartella di destinazione.
4. In **Dopo il download** scegli **Importa e aggiungi alla timeline attiva** oppure **Importa solo nel Media Pool**.
5. Premi **Scarica e importa** e attendi il completamento. Download, unione delle tracce e conversione possono richiedere tempo.
6. Quando l’operazione riesce, premi **OK** per chiudere la finestra.

Per salvare senza importare, scegli **Scarica soltanto**. Per scaricare solo l’audio, seleziona **Solo audio**.

### Dove viene inserito il video

- **Timeline attiva**: la clip viene aggiunta alla fine della timeline selezionata; non viene spostata sul playhead e le clip esistenti non vengono sostituite.
- **Media Pool**: il file viene aggiunto al progetto, senza inserirlo in timeline.
- Se l’importazione non riesce, il file scaricato resta nella cartella di destinazione.

## Se qualcosa non funziona

- **La connessione a Resolve non riesce**: controlla che Resolve sia aperto e che tu abbia eseguito lo script al punto 6. Poi premi di nuovo **Verifica connessione a DaVinci Resolve**.
- **Resolve dice che manca una timeline**: apri la timeline desiderata prima di importare. Il programma non ne crea una automaticamente.
- **FFmpeg o FFprobe non trovati**: chiudi e riapri l’app dopo l’installazione. In PowerShell controlla `ffmpeg -version` e `ffprobe -version`; se non vengono riconosciuti, riavvia Windows e verifica che FFmpeg sia installato.
- **La conversione è lenta**: può usare l’encoder CPU se l’encoder hardware non è disponibile. Attendi che la percentuale di conversione avanzi.
- **Il download da YouTube fallisce**: il servizio può cambiare. Riprova più tardi; se il problema persiste, apri PowerShell nella cartella estratta ed esegui:

  ```powershell
  .venv\Scripts\python.exe -m pip install --upgrade yt-dlp
  ```

## Cosa contiene il progetto

- `main.py`: interfaccia, download e conversione.
- `resolve_bridge/client.py`: comunicazione locale tra il programma e Resolve.
- `resolve_bridge/resolve_import_bridge.lua`: script da avviare dentro Resolve.
- `Avvia YouTube Importer.bat`: primo avvio e avvii successivi.
- `Installa bridge Resolve.bat`: installa lo script nel profilo Windows dell’utente.
- `requirements.txt`: dipendenze Python installate automaticamente al primo avvio.

Il progetto distribuisce il codice sorgente; non include un EXE. Non c’è una procedura di compilazione necessaria per usare l’applicazione.

## Compatibilità verificata

È stata verificata l’importazione automatica con DaVinci Resolve Free **20.2.3.6** su Windows, compresi il download di un video, la conversione Intel Quick Sync e l’inserimento nella timeline attiva. Altre versioni di Resolve, altri encoder e l’esecuzione su altri computer non sono stati verificati.

## Licenza

Questo progetto non dichiara una licenza open source per il proprio codice. Le dipendenze mantengono le rispettive licenze.
