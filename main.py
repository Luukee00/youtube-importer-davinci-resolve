from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


ROOT = Path(__file__).resolve().parent
PLUGIN_DIR = ROOT / "plugins"
USER_PLUGIN_DIR = Path(os.environ.get("APPDATA", Path.home())) / "RossiAPP" / "plugins"


def valid_plugin_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{1,47}", value))


def read_plugin(folder: Path) -> dict | None:
    manifest = folder / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not valid_plugin_id(data.get("id", "")):
            return None
        entry = data.get("entrypoint", "plugin.py")
        if entry != "plugin.py" or not (folder / entry).is_file():
            return None
        if not all(isinstance(data.get(key), str) and data[key].strip()
                   for key in ("name", "version", "description")):
            return None
        data["folder"] = folder
        return data
    except (OSError, ValueError, TypeError):
        return None


class PluginHost(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RossiAPP — Pannello per DaVinci Resolve")
        self.setMinimumSize(700, 500)
        self.resize(920, 680)
        self.plugin_windows = []
        self._build_ui()
        self._style()
        self.refresh_plugins()

    def _build_ui(self):
        base = QWidget()
        self.setCentralWidget(base)
        layout = QVBoxLayout(base)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)

        title = QLabel("ROSSIAPP  /  DAVINCI RESOLVE")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("Scegli uno strumento da aprire oppure aggiungi un plug-in.")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)

        header = QHBoxLayout()
        section = QLabel("I TUOI PLUG-IN")
        section.setObjectName("caption")
        header.addWidget(section)
        header.addStretch()
        install = QPushButton("Aggiungi plug-in…")
        install.setObjectName("primary")
        install.clicked.connect(self.install_plugin)
        header.addWidget(install)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards = QWidget()
        self.grid = QGridLayout(self.cards)
        self.grid.setContentsMargins(2, 2, 2, 2)
        self.grid.setSpacing(14)
        scroll.setWidget(self.cards)
        layout.addWidget(scroll, 1)

        self.footer = QLabel("I plug-in vengono eseguiti sul tuo PC con le autorizzazioni del tuo account Windows.")
        self.footer.setObjectName("muted")
        layout.addWidget(self.footer)

    def _style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#17191d; color:#eceef2; font:10pt 'Segoe UI'; }
            QLabel#title { font-size:20pt; font-weight:700; color:#f0c15a; }
            QLabel#muted { color:#9da3ad; }
            QLabel#caption { color:#d3a94e; font-size:9pt; font-weight:700; }
            QLabel { background:transparent; }
            QFrame#card { background:#202329; border:1px solid #30343c; border-radius:9px; }
            QLabel#pluginName { font-size:13pt; font-weight:700; }
            QLabel#version { color:#9da3ad; font-size:9pt; }
            QPushButton { background:#30343b; border:1px solid #4a505b; border-radius:5px; padding:9px 14px; }
            QPushButton:hover { background:#3c424b; }
            QPushButton#primary { background:#c69736; color:#17191d; font-weight:700; border:0; padding:10px 16px; }
            QPushButton#primary:hover { background:#dfb44f; }
            QScrollBar:vertical { background:#17191d; width:12px; margin:2px; }
            QScrollBar::handle:vertical { background:#505660; min-height:28px; border-radius:5px; }
        """)

    def refresh_plugins(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        PLUGIN_DIR.mkdir(exist_ok=True)
        USER_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        folders = [path for directory in (PLUGIN_DIR, USER_PLUGIN_DIR)
                   for path in sorted(directory.iterdir()) if path.is_dir()]
        plugins = [read_plugin(path) for path in folders]
        plugins = [plugin for plugin in plugins if plugin]
        seen_ids = set()
        unique_plugins = []
        for plugin in plugins:
            if plugin["id"] not in seen_ids:
                unique_plugins.append(plugin)
                seen_ids.add(plugin["id"])
        plugins = unique_plugins
        for index, plugin in enumerate(plugins):
            row, column = divmod(index, 2)
            self.grid.addWidget(self._plugin_card(plugin), row, column)
        if not plugins:
            empty = QLabel("Nessun plug-in installato. Usa “Aggiungi plug-in…” per installarne uno.")
            empty.setObjectName("muted")
            self.grid.addWidget(empty, 0, 0)

    def _plugin_card(self, plugin):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(185)
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        top = QHBoxLayout()
        name = QLabel(plugin["name"])
        name.setObjectName("pluginName")
        top.addWidget(name)
        top.addStretch()
        version = QLabel("v" + plugin["version"])
        version.setObjectName("version")
        top.addWidget(version)
        box.addLayout(top)
        description = QLabel(plugin["description"])
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignTop)
        box.addWidget(description, 1)
        open_button = QPushButton("Apri plug-in")
        open_button.setObjectName("primary")
        open_button.clicked.connect(lambda _checked=False, p=plugin: self.open_plugin(p))
        box.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignRight)
        return card

    def open_plugin(self, plugin):
        module_path = plugin["folder"] / plugin["entrypoint"]
        module_name = f"rossi_plugin_{plugin['id']}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise RuntimeError("Impossibile caricare il file principale del plug-in.")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            plugin_path = str(plugin["folder"])
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            spec.loader.exec_module(module)
            create_window = getattr(module, "create_window", None)
            if not callable(create_window):
                raise RuntimeError("Il plug-in non definisce la funzione richiesta create_window(parent).")
            window = create_window(self)
            if not isinstance(window, QWidget):
                raise RuntimeError("Il plug-in non ha restituito una finestra Qt valida.")
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self.plugin_windows.append(window)
            window_id = id(window)
            window.destroyed.connect(lambda _obj=None, wid=window_id: self._forget_window(wid))
            window.show()
            window.raise_()
            window.activateWindow()
        except Exception as exc:
            QMessageBox.critical(self, "Plug-in non avviato", f"{plugin['name']}:\n{exc}")

    def _forget_window(self, window_id):
        self.plugin_windows = [window for window in self.plugin_windows if id(window) != window_id]

    def install_plugin(self):
        archive, _ = QFileDialog.getOpenFileName(self, "Seleziona il pacchetto del plug-in", "", "Pacchetto plug-in (*.zip)")
        if not archive:
            return
        temporary = None
        try:
            with zipfile.ZipFile(archive) as package:
                members = package.infolist()
                if len(members) > 500 or sum(item.file_size for item in members) > 100 * 1024 * 1024:
                    raise ValueError("Il pacchetto supera i limiti consentiti (500 file, 100 MB).")
                names = [Path(item.filename.rstrip("/\\")) for item in members]
                file_names = [name for name, item in zip(names, members) if not item.is_dir()]
                # Accept either files at the archive root or one containing folder.
                roots = {name.parts[0] for name in file_names if name.parts}
                nested = bool(file_names) and len(roots) == 1 and all(len(name.parts) > 1 for name in file_names)
                prefix = next(iter(roots)) if nested else None
                manifest_name = f"{prefix}/plugin.json" if prefix else "plugin.json"
                if manifest_name not in package.namelist():
                    raise ValueError("Nel pacchetto manca plugin.json nella cartella principale.")
                manifest = json.loads(package.read(manifest_name).decode("utf-8"))
                plugin_id = manifest.get("id", "")
                if not valid_plugin_id(plugin_id):
                    raise ValueError("L'identificativo del plug-in non è valido.")
                for name in names:
                    parts = name.parts[1:] if prefix and name.parts and name.parts[0] == prefix else name.parts
                    if prefix and name.parts and name.parts[0] != prefix:
                        raise ValueError("Il pacchetto deve contenere una sola cartella principale.")
                    if not parts:  # Root directory entry in a ZIP made from a folder.
                        continue
                    if (not parts or any(part in ("..", "") for part in parts)
                            or name.is_absolute() or any(":" in part for part in parts)):
                        raise ValueError("Il pacchetto contiene un percorso non sicuro.")
                    if parts[0].lower() in {"__pycache__", ".git"}:
                        raise ValueError("Il pacchetto contiene file non ammessi.")
                existing_ids = {plugin["id"] for directory in (PLUGIN_DIR, USER_PLUGIN_DIR)
                                for path in directory.iterdir() if path.is_dir()
                                for plugin in [read_plugin(path)] if plugin}
                if plugin_id in existing_ids:
                    raise FileExistsError(f"Esiste già un plug-in con ID '{plugin_id}'. Rimuovi o rinomina prima quello esistente.")
                target = USER_PLUGIN_DIR / plugin_id
                if target.exists():
                    raise FileExistsError(f"Esiste già un plug-in con ID '{plugin_id}'. Rimuovi o rinomina prima quello esistente.")
                answer = QMessageBox.question(
                    self,
                    "Conferma installazione",
                    f"Stai per installare “{manifest.get('name', plugin_id)}”.\n\n"
                    "I plug-in eseguono codice Python con i permessi del tuo account Windows. "
                    "Installa solo pacchetti provenienti da fonti fidate.\n\nVuoi continuare?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                temporary = Path(tempfile.mkdtemp(prefix="rossi-plugin-", dir=USER_PLUGIN_DIR))
                for item in members:
                    raw = Path(item.filename.rstrip("/\\"))
                    if prefix:
                        if not raw.parts or raw.parts[0] != prefix:
                            continue
                        relative = Path(*raw.parts[1:]) if len(raw.parts) > 1 else Path()
                    else:
                        relative = raw
                    if not relative.parts:
                        continue
                    destination = temporary / relative
                    if item.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(package.read(item))
            installed = read_plugin(temporary)
            if not installed:
                raise ValueError("Manifest o file plugin.py non validi.")
            temporary.rename(target)
            temporary = None
            self.refresh_plugins()
            QMessageBox.information(self, "Plug-in aggiunto", f"{installed['name']} è pronto nella schermata principale.")
        except Exception as exc:
            QMessageBox.critical(self, "Installazione non riuscita", str(exc))
        finally:
            if temporary and temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("RossiAPP")
    app.setApplicationName("DaVinciPluginHub")
    window = PluginHost()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
