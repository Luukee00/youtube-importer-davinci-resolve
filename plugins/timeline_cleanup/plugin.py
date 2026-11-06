from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from resolve_bridge.client import send as send_resolve_request


class TimelineCleanupWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pulizia della timeline — RossiAPP")
        self.resize(850, 560)
        self.setMinimumSize(650, 420)
        self._build_ui()
        self._style()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("PULIZIA DELLA TIMELINE")
        title.setObjectName("title")
        layout.addWidget(title)
        intro = QLabel("Controlla la timeline attiva. L’analisi è in sola lettura: non sposta né elimina clip.")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        toolbar = QHBoxLayout()
        self.timeline_label = QLabel("Apri Resolve e avvia YouTubeImporterBridge.")
        self.timeline_label.setObjectName("muted")
        toolbar.addWidget(self.timeline_label, 1)
        self.scan_button = QPushButton("Analizza timeline")
        self.scan_button.setObjectName("primary")
        self.scan_button.clicked.connect(self.analyze)
        toolbar.addWidget(self.scan_button)
        layout.addLayout(toolbar)

        self.close_gaps_button = QPushButton("Chiudi tutti gli spazi vuoti")
        self.close_gaps_button.setObjectName("danger")
        self.close_gaps_button.setEnabled(False)
        self.close_gaps_button.clicked.connect(self.close_gaps)
        layout.addWidget(self.close_gaps_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self.summary = QLabel("Nessuna analisi eseguita.")
        self.summary.setObjectName("summary")
        layout.addWidget(self.summary)

        self.results = QTableWidget(0, 3)
        self.results.setHorizontalHeaderLabels(["Tipo", "Traccia", "Dettaglio"])
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results.setWordWrap(True)
        layout.addWidget(self.results, 1)

        hint = QLabel("I vuoti rilevati sono solo quelli tra clip consecutive sulla stessa traccia. Le tracce vuote sono suggerimenti: potrebbero essere intenzionali.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def _style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#17191d; color:#eceef2; font:10pt 'Segoe UI'; }
            QLabel#title { font-size:18pt; font-weight:700; color:#f0c15a; }
            QLabel#muted { color:#9da3ad; }
            QLabel#summary { color:#f0c15a; font-weight:700; }
            QLabel { background:transparent; }
            QPushButton { background:#30343b; border:1px solid #4a505b; border-radius:5px; padding:9px 14px; }
            QPushButton#primary { background:#c69736; color:#17191d; font-weight:700; border:0; }
            QPushButton#danger { background:#8f493e; color:#fff; font-weight:700; border:0; }
            QPushButton:disabled { color:#717783; }
            QTableWidget { background:#202329; alternate-background-color:#252930; gridline-color:#383d46; border:1px solid #383d46; }
            QHeaderView::section { background:#30343b; color:#d3a94e; padding:7px; border:0; font-weight:700; }
        """)

    def analyze(self):
        self.scan_button.setEnabled(False)
        self.timeline_label.setText("Lettura della timeline attiva in Resolve…")
        try:
            response = send_resolve_request("analyze_timeline")
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Resolve non ha completato l’analisi.")
            data = json.loads(response.get("message", "{}"))
            findings = data.get("findings", [])
            self._show_results(findings)
            self.gap_count = sum(1 for item in findings if item.get("category") == "Spazio vuoto")
            self.close_gaps_button.setEnabled(self.gap_count > 0)
            project = response.get("project") or "Progetto"
            timeline = response.get("timeline") or "Timeline attiva"
            self.timeline_label.setText(f"{project}  ·  {timeline}")
        except Exception as exc:
            QMessageBox.warning(self, "Analisi non riuscita", str(exc))
            self.timeline_label.setText("Controlla che Resolve sia aperto e che il bridge sia avviato.")
        finally:
            self.scan_button.setEnabled(True)

    def close_gaps(self):
        count = getattr(self, "gap_count", 0)
        if count <= 0:
            return
        answer = QMessageBox.warning(
            self,
            "Conferma chiusura spazi",
            f"Resolve chiuderà tutti gli spazi vuoti della timeline attiva, non solo i {count} rilevati.\n\n"
            "Le clip successive verranno spostate a sinistra. Anche gli spazi lasciati intenzionalmente "
            "verranno rimossi e l’operazione può modificare la sincronizzazione tra tracce.\n\n"
            "Vuoi continuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.close_gaps_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        try:
            response = send_resolve_request("delete_gaps")
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Resolve non ha chiuso gli spazi.")
            QMessageBox.information(
                self, "Timeline aggiornata",
                f"Gli spazi vuoti sono stati chiusi in {response.get('timeline') or 'la timeline attiva'}."
            )
            self.analyze()
        except Exception as exc:
            QMessageBox.critical(self, "Modifica non riuscita", str(exc))
            self.scan_button.setEnabled(True)

    def _show_results(self, findings):
        self.results.setRowCount(len(findings))
        errors = warnings = info = 0
        for row, finding in enumerate(findings):
            severity = finding.get("severity", "info")
            category = finding.get("category", "Suggerimento")
            errors += severity == "error"
            warnings += severity == "warning"
            info += severity == "info"
            values = (category, finding.get("track", ""), finding.get("detail", ""))
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results.setItem(row, column, cell)
        self.results.resizeColumnsToContents()
        self.summary.setText(
            f"Analisi completata  ·  {errors} problemi  ·  {warnings} avvisi  ·  {info} suggerimenti"
            if findings else "Nessun problema rilevato nelle categorie controllate."
        )


def create_window(parent=None):
    return TimelineCleanupWindow(parent)
