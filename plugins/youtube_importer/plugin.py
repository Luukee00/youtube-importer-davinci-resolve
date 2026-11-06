from __future__ import annotations

import os
import re
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QRadioButton, QButtonGroup, QVBoxLayout, QWidget,
    QScrollArea,
)

from resolve_bridge.client import send as send_resolve_request


class WorkerSignals(QObject):
    progress = Signal(dict)
    result = Signal(object)
    error = Signal(str)


class Worker(QRunnable):
    def __init__(self, task, *args):
        super().__init__()
        self.task = task
        self.args = args
        self.signals = WorkerSignals()
        self.cancel_event = threading.Event()

    @Slot()
    def run(self):
        try:
            value = self.task(self.signals, self.cancel_event, *self.args)
            self.signals.result.emit(value)
        except Exception as exc:
            self.signals.error.emit(str(exc))


def valid_youtube_url(url: str) -> bool:
    try:
        host = (urlparse(url.strip()).hostname or "").lower()
    except ValueError:
        return False
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"}


def clean_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return (value or "video_youtube")[:180]


def probe_task(signals, cancel_event, url):
    from yt_dlp import YoutubeDL
    with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return {"title": info.get("title") or "", "duration": info.get("duration"), "id": info.get("id")}


def download_task(signals, cancel_event, options):
    from yt_dlp import YoutubeDL

    def hook(data):
        if cancel_event.is_set():
            raise InterruptedError("Download annullato dall’utente")
        signals.progress.emit(data)

    mode = options["mode"]
    height = options["height"]
    if mode == "audio":
        fmt = "bestaudio[ext=m4a]/bestaudio" if options["audio_format"] == "m4a" else "bestaudio/best"
        postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": options["audio_format"],
                           "preferredquality": "0"}]
    else:
        cap = f"[height<={height}]" if height else ""
        fmt = f"bestvideo{cap}[ext=mp4]+bestaudio[ext=m4a]/best{cap}[ext=mp4]/best"
        postprocessors = []
    outtmpl = str(Path(options["folder"]) / (clean_name(options["filename"]) + ".%(ext)s"))
    ydl_opts = {
        "format": fmt,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "windowsfilenames": True,
        "merge_output_format": "mp4" if mode == "video" else None,
        "postprocessors": postprocessors,
        "progress_hooks": [hook],
        "postprocessor_hooks": [lambda data: signals.progress.emit({"status": "postprocessing", "stage": data.get("postprocessor") or "FFmpeg"})],
        "quiet": True,
        "no_warnings": True,
        "overwrites": False,
        "continuedl": True,
        "ffmpeg_location": options.get("ffmpeg") or None,
    }
    ydl_opts = {key: value for key, value in ydl_opts.items() if value is not None}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(options["url"], download=True)
        final_path = Path(ydl.prepare_filename(info))
    if mode == "audio":
        final_path = final_path.with_suffix("." + options["audio_format"])
    if not final_path.exists():
        matches = list(Path(options["folder"]).glob(clean_name(options["filename"]) + ".*"))
        if not matches:
            raise FileNotFoundError("yt-dlp ha terminato ma non trovo il file finale nella cartella scelta")
        final_path = max(matches, key=lambda path: path.stat().st_mtime)
    if mode == "video":
        final_path = ensure_resolve_video(final_path, cancel_event, signals)
    return final_path


def ensure_resolve_video(path: Path, cancel_event, signals) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg e FFprobe devono essere installati e disponibili nel PATH")
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(probe.stdout).get("streams", [])
    video_codecs = [s.get("codec_name") for s in streams if s.get("codec_type") == "video"]
    audio_codecs = [s.get("codec_name") for s in streams if s.get("codec_type") == "audio"]
    if not video_codecs:
        raise RuntimeError("Il file scaricato non contiene un flusso video")
    if video_codecs[0] == "h264" and all(codec == "aac" for codec in audio_codecs):
        return path
    duration = float(json.loads(probe.stdout).get("format", {}).get("duration") or 0)
    temp = path.with_name(path.stem + ".resolve-compat.mp4")
    # Use an available GPU H.264 encoder when its driver/device works. Some FFmpeg
    # builds list hardware encoders even when the PC cannot use them, so keep a CPU fallback.
    encoder_list = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    video_encoders = [("NVENC", ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-b:v", "0"]),
                      ("Quick Sync", ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "20"]),
                      ("AMF", ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "20", "-qp_p", "20"])]
    # Match the actual FFmpeg encoder names; try the hardware paths before software.
    encoders = []
    for name, encoder, args in [
        ("NVENC", "h264_nvenc", video_encoders[0][1]),
        ("Quick Sync", "h264_qsv", video_encoders[1][1]),
        ("AMF", "h264_amf", video_encoders[2][1]),
    ]:
        if re.search(rf"\b{encoder}\b", encoder_list):
            encoders.append((name, args))
    encoders.append(("CPU", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]))

    for encoder_name, video_args in encoders:
        if cancel_event.is_set():
            temp.unlink(missing_ok=True)
            raise InterruptedError("Conversione annullata dall’utente")
        signals.progress.emit({"status": "processing", "percent": 0, "filename": path.name,
                               "encoder": encoder_name,
                               "message": f"Conversione con accelerazione {encoder_name}…" if encoder_name != "CPU" else "Conversione veloce su CPU…"})
        command = [ffmpeg, "-y", "-i", str(path), *video_args]
        if audio_codecs:
            command += ["-c:a", "aac", "-b:a", "192k"]
        else:
            command += ["-an"]
        command += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-nostdin", "-nostats",
                    "-stats_period", "0.5", "-progress", "pipe:1", str(temp)]
        # Drain progress continuously and send stderr to a file-like temporary handle
        # so neither pipe can fill up and block FFmpeg on long videos.
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as error_log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_log, text=True, bufsize=1)
            while process.poll() is None:
                if cancel_event.wait(0.25):
                    process.terminate()
                    process.wait()
                    if process.stdout:
                        process.stdout.close()
                    temp.unlink(missing_ok=True)
                    raise InterruptedError("Conversione annullata dall’utente")
                line = process.stdout.readline() if process.stdout else ""
                if line.startswith("out_time_ms=") and duration > 0:
                    try:
                        percent = min(99, int(float(line.partition("=")[2]) / 1_000_000 / duration * 100))
                        signals.progress.emit({"status": "processing", "percent": percent, "filename": path.name,
                                               "encoder": encoder_name})
                    except ValueError:
                        pass
            if process.stdout:
                process.stdout.close()
            if process.returncode == 0:
                path.unlink(missing_ok=True)
                temp.replace(path.with_suffix(".mp4"))
                return path.with_suffix(".mp4")
            error_log.seek(0)
            last_error = error_log.read()[-1500:] or f"encoder {encoder_name} non disponibile"
            temp.unlink(missing_ok=True)

    raise RuntimeError("Conversione per Resolve fallita: " + last_error)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Importer — DaVinci Resolve")
        self.setMinimumSize(600, 540)
        self.resize(700, 720)
        self.settings = QSettings("RossiAPP", "YouTubeImporter")
        self.pool = QThreadPool.globalInstance()
        self.worker = None
        self.busy = False
        self._build_ui()
        self._style()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("mainScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        outer.addWidget(scroll)
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(30, 26, 30, 24)
        layout.setSpacing(14)

        title = QLabel("YOUTUBE  /  RESOLVE")
        title.setObjectName("title")
        subtitle = QLabel("Scarica contenuti che sei autorizzato a usare e inviali al progetto aperto.")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.url = QLineEdit()
        self.url.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url.editingFinished.connect(self._probe)
        paste = QPushButton("Incolla")
        paste.clicked.connect(lambda: self.url.setText(QApplication.clipboard().text().strip()))
        urlrow = QHBoxLayout()
        urlrow.addWidget(self.url, 1)
        urlrow.addWidget(paste)
        layout.addWidget(self._section("LINK YOUTUBE", urlrow))

        self.video = QRadioButton("Video + audio")
        self.audio = QRadioButton("Solo audio")
        self.video.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.video)
        group.addButton(self.audio)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.video)
        mode_row.addWidget(self.audio)
        mode_row.addStretch()
        self.video.toggled.connect(self._mode_changed)
        layout.addWidget(self._section("MODALITÀ", mode_row))

        controls = QGridLayout()
        controls.addWidget(QLabel("Qualità video"), 0, 0)
        self.quality = QComboBox()
        for label, height in [("Migliore disponibile", 0), ("720p", 720), ("1080p", 1080),
                              ("1440p", 1440), ("2160p / 4K", 2160)]:
            self.quality.addItem(label, height)
        controls.addWidget(self.quality, 0, 1)
        controls.addWidget(QLabel("Formato audio"), 1, 0)
        self.audio_format = QComboBox()
        self.audio_format.addItems(["m4a", "wav", "mp3"])
        controls.addWidget(self.audio_format, 1, 1)
        layout.addWidget(self._section("QUALITÀ E FORMATO", controls))

        self.filename = QLineEdit()
        self.filename.setPlaceholderText("Nome file (si compila dal titolo)")
        layout.addWidget(self._section("NOME FILE", self.filename))

        self.folder = QLineEdit(self.settings.value("folder", str(Path.home() / "Videos")))
        browse = QPushButton("Sfoglia…")
        browse.clicked.connect(self._choose_folder)
        folderrow = QHBoxLayout()
        folderrow.addWidget(self.folder, 1)
        folderrow.addWidget(browse)
        layout.addWidget(self._section("CARTELLA DESTINAZIONE", folderrow))

        self.import_mode = QComboBox()
        self.import_mode.addItem("Importa e aggiungi alla timeline attiva", "append")
        self.import_mode.addItem("Importa solo nel Media Pool", "pool")
        self.import_mode.addItem("Scarica soltanto", "download")
        layout.addWidget(self._section("DOPO IL DOWNLOAD", self.import_mode))

        self.status = QLabel("Pronto. La connessione a Resolve si verifica al momento dell’importazione.")
        self.status.setObjectName("muted")
        layout.addWidget(self.status)
        self.check_button = QPushButton("Verifica connessione a DaVinci Resolve")
        self.check_button.clicked.connect(self._check_resolve)
        layout.addWidget(self.check_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.details = QLabel("")
        self.details.setObjectName("muted")
        layout.addWidget(self.details)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = QPushButton("Annulla")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.go_button = QPushButton("Scarica e importa")
        self.go_button.setObjectName("primary")
        self.go_button.clicked.connect(self._start)
        self.ok_button = QPushButton("OK")
        self.ok_button.setObjectName("primary")
        self.ok_button.clicked.connect(self.close)
        self.ok_button.hide()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.go_button)
        buttons.addWidget(self.ok_button)
        layout.addLayout(buttons)
        self._mode_changed(True)

    def _section(self, label, content):
        frame = QFrame()
        frame.setObjectName("card")
        box = QVBoxLayout(frame)
        box.setContentsMargins(14, 10, 14, 12)
        head = QLabel(label)
        head.setObjectName("caption")
        box.addWidget(head)
        if isinstance(content, QHBoxLayout) or isinstance(content, QGridLayout):
            box.addLayout(content)
        else:
            box.addWidget(content)
        return frame

    def _style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#17191d; color:#eceef2; font: 10pt 'Segoe UI'; }
            QLabel#title { font-size:20pt; font-weight:700; color:#f0c15a; }
            QLabel#muted { color:#9da3ad; }
            QLabel#caption { background:transparent; color:#d3a94e; font-size:8pt; font-weight:700; }
            QLabel { background:transparent; }
            QFrame#card { background:#202329; border:1px solid #30343c; border-radius:8px; }
            QLineEdit, QComboBox { background:#121418; border:1px solid #414650; border-radius:5px; padding:9px; min-height:20px; }
            QComboBox QAbstractItemView { background:#202329; selection-background-color:#b38b38; }
            QPushButton { background:#30343b; border:1px solid #4a505b; border-radius:5px; padding:9px 14px; }
            QPushButton:hover { background:#3c424b; }
            QPushButton#primary { background:#c69736; color:#17191d; font-weight:700; border:0; padding:11px 20px; }
            QPushButton#primary:hover { background:#dfb44f; }
            QPushButton:disabled { color:#717783; }
            QProgressBar { background:#111317; border:1px solid #383d46; border-radius:5px; min-height:16px; text-align:center; }
            QProgressBar::chunk { background:#c69736; border-radius:4px; }
            QRadioButton { spacing:8px; }
            QScrollArea#mainScroll { background:#17191d; }
            QScrollBar:vertical { background:#17191d; width:12px; margin:2px; }
            QScrollBar::handle:vertical { background:#505660; min-height:28px; border-radius:5px; }
        """)

    def _mode_changed(self, _checked):
        is_video = self.video.isChecked()
        self.quality.setEnabled(is_video)
        self.audio_format.setEnabled(not is_video)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Scegli cartella", self.folder.text())
        if folder:
            self.folder.setText(folder)
            self.settings.setValue("folder", folder)

    def _probe(self):
        url = self.url.text().strip()
        if not valid_youtube_url(url) or self.busy:
            return
        self.status.setText("Recupero il titolo…")
        worker = Worker(probe_task, url)
        worker.signals.result.connect(self._title_received)
        worker.signals.error.connect(lambda error: self.status.setText("Titolo non disponibile: " + error))
        self.pool.start(worker)

    def _check_resolve(self):
        self.check_button.setEnabled(False)
        self.status.setText("Verifico il bridge Lua…")
        worker = Worker(lambda _signals, _cancel: send_resolve_request("ping"))
        worker.signals.result.connect(self._connection_result)
        worker.signals.error.connect(lambda error: self._connection_error(error))
        self.pool.start(worker)

    def _connection_result(self, result):
        self.check_button.setEnabled(True)
        self.status.setText(f"Resolve collegato — versione {result.get('resolve_version', '?')}" if result.get("ok") else result.get("message", "Bridge non disponibile"))

    def _connection_error(self, error):
        self.check_button.setEnabled(True)
        self.status.setText("Bridge non raggiungibile: " + error)

    def _title_received(self, info):
        if not self.filename.text().strip():
            self.filename.setText(clean_name(info.get("title", "")))
        self.status.setText("Video trovato: " + info.get("title", "Video YouTube"))

    def _start(self):
        url = self.url.text().strip()
        if not valid_youtube_url(url):
            QMessageBox.warning(self, "Link non valido", "Inserisci un URL di YouTube valido.")
            return
        folder = Path(self.folder.text()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Cartella non disponibile", str(exc))
            return
        name = clean_name(self.filename.text().strip())
        self.filename.setText(name)
        self.settings.setValue("folder", str(folder))
        options = {
            "url": url, "folder": str(folder), "filename": name,
            "mode": "audio" if self.audio.isChecked() else "video",
            "height": self.quality.currentData(), "audio_format": self.audio_format.currentText(),
        }
        self.busy = True
        self.go_button.setEnabled(False)
        self.go_button.show()
        self.ok_button.hide()
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.details.setText("")
        self.status.setText("Download in corso…")
        self.worker = Worker(download_task, options)
        self.worker.signals.progress.connect(self._download_progress)
        self.worker.signals.result.connect(self._downloaded)
        self.worker.signals.error.connect(self._failed)
        self.pool.start(self.worker)

    def _download_progress(self, data):
        status = data.get("status")
        if status == "postprocessing":
            self.status.setText("Finalizzazione con FFmpeg…")
            self.details.setText(str(data.get("stage", "Muxing")))
        elif status == "processing":
            pct = int(data.get("percent", 0))
            encoder = data.get("encoder", "")
            message = data.get("message") or (f"Conversione con {encoder}…" if encoder else "Conversione in formato compatibile con Resolve…")
            self.status.setText(message)
            self.progress.setValue(pct)
            self.details.setText(f"Conversione: {pct}%  ·  {encoder}  ·  {data.get('filename', '')}")
        elif status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            pct = int(downloaded * 100 / total) if total else 0
            self.progress.setValue(max(0, min(100, pct)))
            speed = data.get("speed")
            speed_text = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "velocità non disponibile"
            self.details.setText(f"{pct}%  ·  {speed_text}")
        elif status == "finished":
            self.progress.setValue(100)
            self.status.setText("Download completato, finalizzazione file…")

    def _downloaded(self, path):
        self.progress.setValue(100)
        mode = self.import_mode.currentData()
        if mode == "download":
            self._finish(f"Download completato: {path}", success=True)
            return
        self.status.setText("Invio del file a DaVinci Resolve…")
        action = "import_append" if mode == "append" else "import_pool"
        worker = Worker(lambda _signals, _cancel, p, a: send_resolve_request(a, p), path, action)
        worker.signals.result.connect(lambda result: self._import_result(path, result))
        worker.signals.error.connect(lambda error: self._finish(f"Download completato, importazione non riuscita: {error}"))
        self.worker = worker
        self.pool.start(worker)

    def _import_result(self, path, result):
        if result.get("ok"):
            self._finish(f"Completato: {result.get('media')} — {result.get('timeline') or 'Media Pool'}", success=True)
        else:
            self._finish(f"Download completato ({path}), importazione non riuscita: {result.get('message')}")

    def _failed(self, error):
        self._finish("Operazione non completata: " + error)

    def _finish(self, message, success=False):
        self.status.setText(message)
        self.busy = False
        self.cancel_button.setEnabled(False)
        if success:
            self.progress.setValue(100)
            self.details.clear()
            self.cancel_button.hide()
            self.go_button.hide()
            self.ok_button.show()
        else:
            self.go_button.setEnabled(True)
        self.worker = None

    def _cancel(self):
        if self.worker:
            self.worker.cancel_event.set()
            self.status.setText("Annullamento richiesto…")
            self.cancel_button.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("RossiAPP")
    app.setApplicationName("YouTubeImporter")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


def create_window(parent=None):
    """Entry point used by the RossiAPP plug-in host."""
    return MainWindow()
