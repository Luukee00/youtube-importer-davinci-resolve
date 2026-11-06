# Bridge Lua per DaVinci Resolve Free

Il prototipo dimostra il passaggio di un file locale dall’app Python a Resolve Free: ping, importazione nel Media Pool e aggiunta alla timeline attiva. È incluso insieme all’app completa per diagnosticare separatamente l’integrazione.

## Prova confermata

La prova è stata eseguita su DaVinci Resolve Free **20.2.3.6** per Windows. Il client ha ricevuto `ok: true` sia per il ping sia per l’importazione e l’aggiunta di un MP4 locale alla timeline attiva. La clip viene aggiunta in coda, senza sovrascrivere clip esistenti.

## Installazione e uso

1. Installa `resolve_import_bridge.lua` con `Installa bridge Resolve.bat` nella cartella principale, oppure copialo manualmente in `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\YouTubeImporterBridge.lua`.
2. Avvia Resolve e apri un progetto e una timeline di prova.
3. Scegli **Workspace → Scripts → Utility → YouTubeImporterBridge** e lascia Resolve aperto. Ripeti dopo ogni riavvio di Resolve.
4. Dal progetto, esegui `prototype\1 - Verifica bridge.bat` oppure `python prototype\client.py --ping`.
5. Per importare un file locale e aggiungerlo alla timeline, esegui `prototype\2 - Importa video di prova.bat` oppure `python prototype\client.py --file "C:\percorso\file.mp4"`.

## Protocollo

- Il client crea `%USERPROFILE%\.ytresolve-importer\request.lua` con una richiesta atomica.
- Lo script Lua la legge con `bmd.fileexists` e `loadfile`, invoca solo azioni previste e salva la risposta nelle preferenze Fusion.
- Il client attende la risposta in `Fusion.prefs`; log e diagnostica sono in `%USERPROFILE%\.ytresolve-importer\bridge_debug.log` e nella Console Lua di Resolve (`YTDIAG`).
- Non vengono usati socket, cloud, API Studio o codice Lua arbitrario ricevuto dal client.

## Limiti

- Verificato solo su Resolve Free 20.2.3.6; altre versioni, incluse 21.x, non sono state testate.
- Il bridge va avviato manualmente per ogni sessione di Resolve.
- L’aggiunta alla timeline richiede una timeline attiva; se manca, il file può risultare importato nel Media Pool ma l’azione viene segnalata come non riuscita.
- L’inserimento è append-only; non colloca al playhead e non crea timeline.
- L’ambiente Lua e alcune API non hanno garanzie di compatibilità documentate da questo progetto. La risposta distingue sempre un errore da un’importazione riuscita.
