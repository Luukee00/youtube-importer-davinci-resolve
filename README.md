# RossiAPP — pannello per DaVinci Resolve

Applicazione Windows in italiano che raccoglie strumenti aggiuntivi per un progetto aperto in DaVinci Resolve. La schermata iniziale mostra i plug-in installati; il primo incluso è **YouTube Importer**.

> Usa ogni plug-in e scarica contenuti soltanto quando hai il diritto di farlo. I plug-in Python aggiunti sono codice eseguibile sul tuo PC: installa solo pacchetti provenienti da persone o progetti di cui ti fidi.

## Avvio su Windows

### 1. Installa Python e FFmpeg

Apri PowerShell e installa Python 3.13 e FFmpeg:

```powershell
winget install --exact --id Python.Python.3.13
winget install --exact --id Gyan.FFmpeg
```

Chiudi e riapri PowerShell, poi controlla che i comandi rispondano mostrando una versione:

```powershell
py -3.13 --version
ffmpeg -version
ffprobe -version
```

### 2. Scarica e avvia RossiAPP

1. Apri il [repository GitHub](https://github.com/Luukee00/youtube-importer-davinci-resolve) e scegli **Code → Download ZIP**.
2. In Esplora file fai clic destro sullo ZIP, scegli **Estrai tutto…** e poi **Estrai**.
3. Apri la cartella estratta e fai doppio clic su **Avvia RossiAPP.bat**. Il file apre il pannello RossiAPP.
4. Al primo avvio il programma crea un ambiente Python locale e installa le dipendenze. Attendi che finisca; serve una connessione Internet.

Ai successivi avvii usa lo stesso file `.bat`. Al momento il progetto distribuisce il codice sorgente e non contiene un file `.exe`.

### 3. Collega DaVinci Resolve

Questa configurazione serve per i plug-in che inviano elementi a Resolve.

1. Chiudi Resolve.
2. Dalla cartella del progetto fai doppio clic su **Installa bridge Resolve.bat**. Non serve avviarlo come amministratore.
3. Premi un tasto quando compare il messaggio di completamento.
4. Avvia DaVinci Resolve e apri il progetto desiderato.
5. Nel menu scegli **Workspace → Scripts → Utility → YouTubeImporterBridge** e lascia Resolve aperto.
6. Nel plug-in YouTube Importer usa **Verifica connessione a DaVinci Resolve**.

Il passaggio 5 va ripetuto dopo ogni riavvio di Resolve. Il bridge usa funzioni locali disponibili in Resolve Free.

## Usa YouTube Importer

1. Nella schermata iniziale premi **Apri plug-in** sulla scheda YouTube Importer.
2. Incolla il link YouTube, scegli video o audio, qualità e cartella.
3. Scegli se scaricare soltanto, aggiungere al Media Pool o aggiungere in fondo alla timeline attiva.
4. Premi **Scarica e importa** e attendi il completamento. Unione delle tracce e conversione possono richiedere tempo.
5. Premi **OK** per chiudere il plug-in.

Per importare nella timeline, apri prima in Resolve la timeline corretta. Le clip vengono aggiunte in fondo; quelle già presenti non vengono sostituite.

## Aggiungi un plug-in

Nella schermata principale premi **Aggiungi plug-in…** e scegli un pacchetto ZIP. Dopo aver confermato l’installazione, l’app lo copia in `%APPDATA%\RossiAPP\plugins\<id>` e aggiorna l’elenco. Il pacchetto deve contenere `plugin.json` e `plugin.py` nella cartella principale dello ZIP, oppure in una sola cartella interna. Se lo stesso ID è già presente, l’installazione viene rifiutata: per ora non c’è un aggiornamento automatico o un pulsante di disinstallazione.

Struttura minima:

```text
mio_plugin.zip
├── plugin.json
└── plugin.py
```

`plugin.json` descrive il plug-in:

```json
{
  "id": "mio_plugin",
  "name": "Il mio plug-in",
  "version": "1.0.0",
  "description": "Descrizione breve della funzione.",
  "entrypoint": "plugin.py"
}
```

L’ID deve contenere lettere minuscole, numeri e underscore, iniziare con una lettera e avere da 2 a 48 caratteri. `plugin.py` deve definire `create_window(parent)`, che restituisce una finestra/widget Qt:

```python
from PySide6.QtWidgets import QLabel, QWidget


def create_window(parent=None):
    window = QWidget()
    window.setWindowTitle("Il mio plug-in")
    window.resize(600, 400)
    from PySide6.QtWidgets import QVBoxLayout
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel("Il plug-in è pronto."))
    return window
```

Il plug-in può includere altri file Python nella propria cartella. Può riutilizzare il bridge locale importando, ad esempio, `from resolve_bridge.client import send`; per i dettagli delle richieste vedere `resolve_bridge/client.py` e lo script Lua. Le dipendenze aggiuntive devono essere dichiarate e installate tramite `requirements.txt` del progetto: il gestore attuale non esegue installazioni automatiche di dipendenze indicate da plug-in ZIP.

**Nota di sicurezza:** il caricamento da ZIP non isola il codice. Un plug-in Python ha gli stessi permessi dell’utente Windows che esegue RossiAPP. Il gestore rifiuta ID non validi, file mancanti, archivi troppo grandi o percorsi di estrazione non sicuri, ma non può certificare che il codice sia affidabile.

## Struttura del progetto

```text
main.py                              Pannello e caricatore plug-in
plugins/youtube_importer/            Primo plug-in, incluso nel progetto
  plugin.json                        Nome, versione e descrizione
  plugin.py                          Interfaccia e funzioni YouTube
resolve_bridge/client.py             Comunicazione locale con Resolve
resolve_bridge/resolve_import_bridge.lua  Bridge Lua da avviare in Resolve
Avvia RossiAPP.bat                   Crea l’ambiente e avvia il pannello
Installa bridge Resolve.bat          Installa lo script Lua nel profilo utente
requirements.txt                     Dipendenze Python dell’app e dei plug-in inclusi
```

## Risoluzione problemi

- **Resolve non si collega**: verifica che sia aperto, che tu abbia avviato lo script dal menu Workspace e che il bridge sia stato installato.
- **Manca una timeline**: apri la timeline desiderata prima di importare.
- **FFmpeg o FFprobe non trovati**: riavvia l’app dopo l’installazione; se i comandi non sono riconosciuti in PowerShell, riavvia Windows e controlla l’installazione di FFmpeg.
- **Un plug-in ZIP non appare**: controlla che contenga `plugin.json` e `plugin.py` e che l’ID sia valido. Se compare un messaggio di errore, correggi il pacchetto e riprova.
- **YouTube rifiuta un link valido**: aggiorna yt-dlp da PowerShell aperto nella cartella del progetto:

  ```powershell
  .venv\Scripts\python.exe -m pip install --upgrade yt-dlp
  ```

## Compatibilità e licenza

Il collegamento d’importazione è stato verificato su DaVinci Resolve Free 20.2.3.6 per Windows. Il caricatore di plug-in introduce un formato iniziale semplice; l’interfaccia pubblica e le dipendenze esterne potranno essere ampliate man mano che si aggiungono plug-in.

Questo progetto non dichiara una licenza open source per il proprio codice. Le dipendenze mantengono le rispettive licenze.
