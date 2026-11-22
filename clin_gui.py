"""
Clin - Interfaccia grafica per l'anonimizzazione di PDF sanitari.

Tre aree di lavoro:
  * sinistra  : documenti di input (con spunte) e cartella di output
  * centro    : anteprima del documento con evidenziazione degli oscuramenti
  * destra    : elenchi di termini, opzioni, avvio e registro

L'aspetto (palette, icone, componenti) e' definito in `ui_kit`.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import pymupdf as fitz  # noqa: E402
except ImportError:
    import fitz  # noqa: E402
from PySide6.QtCore import (
    QEasingCurve, QElapsedTimer, QEvent, QPoint, QPropertyAnimation, QSettings, QSize, Qt,
    QThread, QTimer, QUrl, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QDesktopServices, QFont, QImage, QKeySequence,
    QNativeGestureEvent, QPainter, QPen, QPixmap, QTextCursor, QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QStackedWidget, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

import clin_llm
from anonymize_engine import (
    CATEGORY_COLORS, MAX_LEVEL,
    BatchResult, Detection, FileResult, _PageIndex, analyze_page, collect_document_names,
    parse_lines_exact,
    parse_text_lines, process_batch_files,
)
from tabular_engine import TABLE_SUFFIXES, TableSettings, is_table_file
from table_preview import TablePreviewWidget
from ui_kit import (
    ACCENT, ACCENT_HOVER, ACCENT_INK, ACCENT_LINE, ACCENT_SOFT, BORDER, BTN_DANGER,
    BTN_GHOST, BTN_PRIMARY, BTN_SECONDARY, CANVAS, DANGER, DANGER_SOFT, FAINT,
    HAIRLINE, INK, INK_SOFT, MONO_STACK, MUTED, R_LG, R_MD, R_PILL, R_SM,
    SUCCESS, SURFACE, SURFACE_ALT, SURFACE_SUNK, WARNING, WARNING_SOFT,
    SOFT, Panel, Segmented, ToggleRow, app_icon, app_stylesheet, caption, fade_in, hairline,
    load_brand_font,
    icon, make_button, pill,
)

APP_NAME = "Clin"
ORG_NAME = "Clin"
OUTPUT_SUFFIX = "_ANONIMIZZATO"
# output -> originale, in memoria: i nomi dei file in uscita vengono ripuliti
# e non permettono piu' di risalire all'originale
ORIGINS: Dict[Path, Path] = {}

SUPPORTED_SUFFIXES = {".pdf"} | TABLE_SUFFIXES
FILE_DIALOG_FILTER = (
    "Documenti supportati (*.pdf *.csv *.tsv *.txt *.xlsx *.xlsm);;"
    "PDF (*.pdf);;Fogli di calcolo (*.csv *.tsv *.txt *.xlsx *.xlsm)"
)
FILE_ICONS = {".pdf": "page", ".csv": "list", ".tsv": "list", ".txt": "list",
              ".xlsx": "list", ".xlsm": "list"}

FILL_COLORS = [
    ("Nero pieno (standard)", (0.0, 0.0, 0.0)),
    ("Bianco (sbiancamento)", (1.0, 1.0, 1.0)),
    ("Grigio discreto", (0.5, 0.5, 0.5)),
]
DPI_CHOICES = [
    ("Alta qualita' · 150 DPI", 150),
    ("Standard · 135 DPI", 135),
    ("Veloce · 100 DPI", 100),
]


def human_size(num_bytes: float) -> str:
    kb = num_bytes / 1024
    return f"{kb:.0f} KB" if kb < 1024 else f"{kb / 1024:.1f} MB"


def animate_widget_flash(widget: QWidget) -> None:
    """Evidenzia brevemente un elenco appena aggiornato."""
    base_qss = getattr(widget, "base_stylesheet", "")
    anim = QVariantAnimation(widget)
    anim.setDuration(560)
    anim.setStartValue(QColor(ACCENT_SOFT))
    anim.setEndValue(QColor(SURFACE_ALT))
    anim.setEasingCurve(QEasingCurve.OutQuad)

    def update_style(col: QColor):
        widget.setStyleSheet(
            base_qss + f"\nQTextEdit {{ background-color: {col.name()};"
            f" border: 1px solid {ACCENT_LINE}; }}"
        )

    anim.valueChanged.connect(update_style)
    anim.finished.connect(lambda: widget.setStyleSheet(base_qss))
    anim.start(QVariantAnimation.DeleteWhenStopped)
    widget._active_anim = anim


# --------------------------------------------------------------------------
# Worker
# --------------------------------------------------------------------------
class ContextAnalysisWorker(QThread):
    """Passa i testi delle pagine al modello locale; i risultati restano in cache."""

    finished_signal = Signal(str, bool)  # stato del motore, almeno un'entita' trovata

    def __init__(self, texts: List[str]):
        super().__init__()
        self.texts = texts

    def run(self):
        found = False
        if clin_llm.model():
            for t in self.texts:
                if self.isInterruptionRequested():
                    return
                found = bool(clin_llm.entities(t)) or found
        self.finished_signal.emit(clin_llm.status(), found)


class AnonymizeWorker(QThread):
    progress_signal = Signal(int, int, str)
    log_signal = Signal(str)
    file_done_signal = Signal(object)   # FileResult
    finished_signal = Signal(int, int)  # processati, oscuramenti
    batch_signal = Signal(object)       # BatchResult
    error_signal = Signal(str)

    def __init__(
        self,
        file_paths: List[Path],
        output_dir: Path,
        level: int,
        remove_images: bool,
        custom_text: str,
        whitelist_text: str,
        fill_color: Tuple[float, float, float] = (0, 0, 0),
        keep_labels: bool = False,
        sanitize_metadata: bool = True,
        verify_output: bool = True,
        overwrite: bool = True,
        table_settings=None,
    ):
        super().__init__()
        self.file_paths = file_paths
        self.output_dir = output_dir
        self.level = level
        self.remove_images = remove_images
        self.custom_text = custom_text
        self.whitelist_text = whitelist_text
        self.fill_color = fill_color
        self.keep_labels = keep_labels
        self.sanitize_metadata = sanitize_metadata
        self.verify_output = verify_output
        self.overwrite = overwrite
        self.table_settings = table_settings
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        try:
            batch = BatchResult()
            process_batch_files(
                file_list=self.file_paths,
                output_dir=self.output_dir,
                sensitivity_level=self.level,
                remove_images=self.remove_images,
                explicit_targets=parse_text_lines(self.custom_text),
                whitelist_words=parse_lines_exact(self.whitelist_text),
                fill_color=self.fill_color,
                progress_callback=lambda c, t, f: self.progress_signal.emit(c, t, f),
                keep_labels=self.keep_labels,
                sanitize_metadata=self.sanitize_metadata,
                verify_output=self.verify_output,
                overwrite=self.overwrite,
                suffix=OUTPUT_SUFFIX,
                should_cancel=self.is_cancelled,
                result_callback=lambda r: self.file_done_signal.emit(r),
                batch_result=batch,
                table_settings=self.table_settings,
            )
            self.batch_signal.emit(batch)
            self.finished_signal.emit(batch.processed, batch.total_redactions)
        except Exception as exc:  # il thread non deve morire in silenzio
            self.error_signal.emit(f"{type(exc).__name__}: {exc}")
            self.batch_signal.emit(BatchResult())
            self.finished_signal.emit(0, 0)


# --------------------------------------------------------------------------
# Dialoghi
# --------------------------------------------------------------------------
class CardDialog(QDialog):
    """Finestra modale a scheda, spostabile trascinandola."""

    def __init__(self, parent, title: str, subtitle: str = "", width: int = 480,
                 icon_name: str = "sparkle"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_offset: Optional[QPoint] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        self.card = QFrame()
        self.card.setObjectName("dlgCard")
        self.card.setStyleSheet(
            f"QFrame#dlgCard {{ background-color: {SURFACE}; border: 1px solid {BORDER};"
            f" border-radius: {R_LG + 2}px; }}"
        )
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(24, 22, 24, 22)
        self.card_layout.setSpacing(16)
        outer.addWidget(self.card)

        head = QHBoxLayout()
        head.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(icon(icon_name, ACCENT_INK, 18).pixmap(18, 18))
        mark.setFixedSize(34, 34)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(f"background-color: {SOFT}; border-radius: 17px;")
        titles = QVBoxLayout()
        titles.setSpacing(1)
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color: {INK}; font-size: 15px; font-weight: 600; letter-spacing: -0.2px;")
        titles.addWidget(lbl)
        if subtitle:
            titles.addWidget(caption(subtitle))
        head.addWidget(mark)
        head.addLayout(titles, 1)
        self.card_layout.addLayout(head)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class ConflictDialog(CardDialog):
    """Chiede dove collocare un termine presente in entrambi gli elenchi."""

    def __init__(self, parent, title: str, text: str, option1_text: str, option2_text: str):
        super().__init__(parent, "Termine in conflitto", width=460, icon_name="alert")
        self.choice = 0

        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.RichText)
        msg.setStyleSheet(f"color: {INK_SOFT}; font-size: 13px; line-height: 1.5;")
        self.card_layout.addWidget(msg)

        btn1 = make_button(option1_text, "check", "primary")
        btn2 = make_button(option2_text, None, "secondary")
        btn3 = make_button("Annulla", None, "ghost")
        btn1.clicked.connect(lambda: self.make_choice(1))
        btn2.clicked.connect(lambda: self.make_choice(2))
        btn3.clicked.connect(lambda: self.make_choice(0))

        col = QVBoxLayout()
        col.setSpacing(8)
        for b in (btn1, btn2, btn3):
            col.addWidget(b)
        self.card_layout.addLayout(col)

    def make_choice(self, val: int):
        self.choice = val
        self.accept()


class SettingsDialog(CardDialog):
    """Preferenze applicative."""

    def __init__(self, parent_main: "ClinMainWindow"):
        super().__init__(parent_main, "Impostazioni",
                         "Preferenze salvate automaticamente", 500, "settings")
        self.parent_main = parent_main

        self.cmb_color = QComboBox()
        for label, value in FILL_COLORS:
            self.cmb_color.addItem(label, value)
        self.cmb_color.setCurrentIndex(
            next((i for i, (_, v) in enumerate(FILL_COLORS) if v == parent_main.fill_color), 0)
        )
        self._field("Colore dei rettangoli di oscuramento", self.cmb_color,
                    "Il testo viene comunque rimosso: il colore e' solo estetico.")

        self.cmb_dpi = QComboBox()
        for label, value in DPI_CHOICES:
            self.cmb_dpi.addItem(label, value)
        self.cmb_dpi.setCurrentIndex(
            next((i for i, (_, v) in enumerate(DPI_CHOICES) if v == parent_main.render_dpi), 1)
        )
        self._field("Qualita' dell'anteprima", self.cmb_dpi,
                    "Piu' DPI significa immagine piu' nitida e rendering piu' lento.")

        self.cmb_overwrite = QComboBox()
        self.cmb_overwrite.addItem("Sovrascrivi i file esistenti", True)
        self.cmb_overwrite.addItem("Mantieni entrambi, numerando", False)
        self.cmb_overwrite.setCurrentIndex(0 if parent_main.overwrite else 1)
        self._field("Se il file di output esiste gia'", self.cmb_overwrite)

        self.cmb_verify = QComboBox()
        self.cmb_verify.addItem("Si', riapri e verifica ogni file", True)
        self.cmb_verify.addItem("No, elaborazione piu' rapida", False)
        self.cmb_verify.setCurrentIndex(0 if parent_main.verify_output else 1)
        self._field("Verifica finale dei termini personalizzati", self.cmb_verify)

        self.card_layout.addWidget(hairline())
        row = QHBoxLayout()
        row.setSpacing(8)
        btn_reset = make_button("Ripristina predefiniti", "eraser", "ghost")
        btn_reset.clicked.connect(self.reset_defaults)
        btn_cancel = make_button("Annulla", None, "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_save = make_button("Salva", "check", "primary")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.accept)
        row.addWidget(btn_reset)
        row.addStretch()
        row.addWidget(btn_cancel)
        row.addWidget(btn_save)
        self.card_layout.addLayout(row)

    def _field(self, label: str, widget: QWidget, hint: str = ""):
        box = QVBoxLayout()
        box.setSpacing(6)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {INK}; font-size: 12.5px; font-weight: 500;")
        box.addWidget(lbl)
        box.addWidget(widget)
        if hint:
            box.addWidget(caption(hint))
        self.card_layout.addLayout(box)

    def reset_defaults(self):
        for cmb, idx in ((self.cmb_color, 0), (self.cmb_dpi, 1),
                         (self.cmb_overwrite, 0), (self.cmb_verify, 0)):
            cmb.setCurrentIndex(idx)


class AgentsDialog(CardDialog):
    """Clin negli agenti IA: installazione e comportamento di /clin."""

    AGENT_NAMES = {"claude-code": "Claude Code", "codex": "Codex", "antigravity": "Google Antigravity"}

    def __init__(self, parent_main: "ClinMainWindow"):
        super().__init__(parent_main, "Agenti IA",
                         "Comportamento di /clin in Claude Code, Codex e Antigravity", 560, "shield")
        import clin
        import clin_settings
        self.parent_main = parent_main
        self.values = clin_settings.load()

        found = clin.detect_agents()
        status = QWidget()
        status.setObjectName("transparent")
        lines = QVBoxLayout(status)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(4)
        for key, name in self.AGENT_NAMES.items():
            if key not in found:
                state = "non trovato su questo computer"
            elif self._installed(key):
                state = "installato"
            else:
                state = "trovato, non ancora collegato"
            row = QLabel(f"<b>{name}</b> &nbsp;<span style='color:{MUTED}'>{state}</span>")
            row.setTextFormat(Qt.RichText)
            row.setStyleSheet(f"color: {INK}; font-size: 12.5px;")
            lines.addWidget(row)
        btn_install = make_button("Installa o aggiorna negli agenti trovati", "download", "secondary")
        btn_install.clicked.connect(self.install)
        self._field("Installazione", status,
                    "Dopo l'installazione, in una nuova sessione aperta sulla cartella dei dati si scrive /clin.")
        self.card_layout.addWidget(btn_install)
        self.card_layout.addWidget(hairline())

        self.combos = {}
        labels = {
            "ripristino_automatico": "Risultati con i dati reali",
            "blocca_messaggi": "Messaggi con dati personali",
            "ripulisci_output": "Output dei comandi",
            "modello_locale": "Modello linguistico locale",
            "ocr": "OCR di scansioni e immagini",
        }
        choices = {
            "ripristino_automatico": ("Automatico, a fine risposta", "Solo su richiesta"),
            "blocca_messaggi": ("Fermare prima dell'invio", "Inviare"),
            "ripulisci_output": ("Ripulire", "Lasciare invariato"),
            "modello_locale": ("Usare, se presente", "Non usare"),
            "ocr": ("Usare, se installato", "Non usare"),
        }
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        for i, (key, label) in enumerate(labels.items()):
            cmb = QComboBox()
            cmb.addItem(choices[key][0], True)
            cmb.addItem(choices[key][1], False)
            cmb.setCurrentIndex(0 if self.values[key] else 1)
            cmb.setToolTip(clin_settings.OPTIONS[key][1])
            self.combos[key] = cmb
            cell = QVBoxLayout()
            cell.setSpacing(6)
            lbl = QLabel(label)
            lbl.setToolTip(clin_settings.OPTIONS[key][1])
            lbl.setStyleSheet(f"color: {INK}; font-size: 12.5px; font-weight: 500;")
            cell.addWidget(lbl)
            cell.addWidget(cmb)
            grid.addLayout(cell, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.card_layout.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.txt_results = QLineEdit(str(self.values["cartella_risultati"]))
        self.txt_results.setPlaceholderText("Clin_risultati")
        btn = make_button("Sfoglia", "folder", "secondary")
        btn.clicked.connect(self.pick_results_dir)
        row.addWidget(self.txt_results, 1)
        row.addWidget(btn)
        box = QVBoxLayout()
        box.setSpacing(6)
        lbl = QLabel("Cartella dei risultati con i dati reali")
        lbl.setStyleSheet(f"color: {INK}; font-size: 12.5px; font-weight: 500;")
        box.addWidget(lbl)
        box.addLayout(row)
        box.addWidget(caption(clin_settings.OPTIONS["cartella_risultati"][1]))
        self.card_layout.addLayout(box)

        self.card_layout.addWidget(hairline())
        row = QHBoxLayout()
        row.setSpacing(8)
        btn_cancel = make_button("Annulla", None, "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_save = make_button("Salva", "check", "primary")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save)
        row.addStretch()
        row.addWidget(btn_cancel)
        row.addWidget(btn_save)
        self.card_layout.addLayout(row)

    _field = SettingsDialog._field

    @staticmethod
    def _installed(agent: str) -> bool:
        home = Path.home()
        path = {"claude-code": home / ".claude" / "settings.json", "codex": home / ".codex" / "hooks.json",
                "antigravity": home / ".gemini" / "config" / "hooks.json"}[agent]
        try:
            return "clin_guard.py" in path.read_text(encoding="utf-8")
        except OSError:
            return False

    def pick_results_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Cartella dei risultati con i dati reali")
        if folder:
            self.txt_results.setText(folder)

    def install(self):
        import clin
        msgs = []
        try:
            for agent in clin.detect_agents():
                if agent == "claude-code":
                    msgs.append(clin.connect_claude_code())
                msgs.append(clin.GUARD_FNS[agent](None))
        except Exception as exc:
            msgs.append(f"Errore: {exc}")
        for m in msgs or ["Nessun agente trovato (Claude Code, Codex, Antigravity)."]:
            self.parent_main.log(m, "error" if m.startswith("Errore") else "ok")
        self.parent_main.status.showMessage(msgs[-1] if msgs else "Nessun agente trovato.", 8000)

    def save(self):
        import clin_settings
        values = {k: bool(c.currentData()) for k, c in self.combos.items()}
        values["cartella_risultati"] = self.txt_results.text().strip() or "Clin_risultati"
        clin_settings.save(values)
        self.parent_main.log("Impostazioni per gli agenti IA salvate.", "ok")
        self.accept()


class CategoriesDialog(CardDialog):
    """Controllo manuale: quali categorie di dati rimuovere (tutte, per impostazione predefinita)."""

    def __init__(self, parent_main: "ClinMainWindow"):
        super().__init__(parent_main, "Cosa rimuovere",
                         "Vale per l'applicazione, /clin negli agenti e il server MCP", 600, "eraser")
        import clin_settings
        from anonymize_engine import CONTROL_CATEGORIES
        self.parent_main = parent_main
        values = clin_settings.load()
        excluded = set(values["categorie_escluse"])
        self.card_layout.addWidget(caption(
            "Per impostazione predefinita Clin rimuove tutto. Togliere la spunta solo per i dati che "
            "devono restare leggibili (per esempio le date degli esami in uno studio): restano in chiaro "
            "anche nelle copie per l'IA. La lista «Rimuovi sempre» resta comunque attiva."))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self.boxes = {}
        for i, (cat, desc) in enumerate(CONTROL_CATEGORIES.items()):
            box = QCheckBox(cat)
            box.setChecked(cat not in excluded)
            box.setToolTip(desc)
            box.setStyleSheet(f"color: {INK}; font-size: 12.5px;")
            self.boxes[cat] = box
            cell = QVBoxLayout()
            cell.setSpacing(1)
            cell.addWidget(box)
            note = caption(desc)
            note.setWordWrap(True)
            note.setContentsMargins(22, 0, 0, 0)
            cell.addWidget(note)
            grid.addLayout(cell, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.card_layout.addLayout(grid)
        self.card_layout.addWidget(hairline())
        self.chk_columns = QCheckBox("Riconoscere le colonne di nominativi anche dal contenuto")
        self.chk_columns.setChecked(bool(values["colonne_dal_contenuto"]))
        self.chk_columns.setToolTip(clin_settings.OPTIONS["colonne_dal_contenuto"][1])
        self.chk_columns.setStyleSheet(f"color: {INK}; font-size: 12.5px;")
        self.card_layout.addWidget(self.chk_columns)
        self.card_layout.addWidget(caption(
            "Fogli di calcolo: oltre alle intestazioni note (paziente, medico, familiare, codice fiscale, "
            "ricetta…), una colonna con nomi di persona viene pseudonimizzata se il modello locale "
            "(GLiNER o Ollama) li riconosce nella maggior parte delle celle."))
        row = QHBoxLayout()
        row.setSpacing(8)
        btn_all = make_button("Rimuovi tutto", None, "secondary")
        btn_all.clicked.connect(lambda: [b.setChecked(True) for b in self.boxes.values()])
        btn_cancel = make_button("Annulla", None, "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_save = make_button("Salva", "check", "primary")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save)
        row.addWidget(btn_all)
        row.addStretch()
        row.addWidget(btn_cancel)
        row.addWidget(btn_save)
        self.card_layout.addLayout(row)

    def save(self):
        import clin_settings
        excluded = [c for c, b in self.boxes.items() if not b.isChecked()]
        clin_settings.save({"categorie_escluse": excluded,
                            "colonne_dal_contenuto": self.chk_columns.isChecked()})
        self.parent_main.log("Lasciati in chiaro: " + ", ".join(excluded) if excluded
                             else "Categorie: si rimuove tutto.", "ok")
        try:
            self.parent_main.sync_preview_settings()
        except Exception:
            pass
        self.accept()


class HowItWorksDialog(CardDialog):
    """Guida all'uso."""

    SECTIONS = [
        ("folder", "Caricare i documenti",
         "Usa <b>Cartella</b> o <b>File</b>, oppure trascina i PDF sulla finestra. Ogni file ha "
         "una casella di spunta: vengono elaborati solo quelli spuntati. Il campo di ricerca "
         "filtra l'elenco per nome."),
        ("eye", "Anteprima degli oscuramenti",
         "Il pannello centrale evidenzia a colori tutto cio' che verra' oscurato, con "
         "aggiornamento immediato al variare del livello o degli elenchi. Un colore per "
         "categoria.<br>• <b>Clic su una parola</b>: la inserisce fra i termini da rimuovere o "
         "da mantenere.<br>• <b>Clic su un'evidenziazione</b>: propone l'intero termine "
         "rilevato.<br>• <b>Clic su un rettangolo nero</b> di un file gia' anonimizzato: risale "
         "al documento originale e recupera il testo coperto."),
        ("list", "Fogli di calcolo (CSV, TSV, Excel)",
         "I file tabellari si aprono in una vista a griglia che evidenzia le celle da "
         "anonimizzare.<br>• <b>Clic sull'intestazione di una colonna</b>: scegli come "
         "trattarla — <i>Automatico</i> (rileva solo i dati sensibili), <i>Oscura tutto</i> "
         "(rimuove l'intero contenuto), <i>Pseudonimo</i> (sostituisce con un codice stabile "
         "tipo COG-0001, cosi' le analisi restano possibili), <i>Non toccare</i>.<br>"
         "• <b>Seleziona delle righe</b> e usa <i>Solo selezionate</i> per limitare "
         "l'anonimizzazione a quelle.<br>• <b>Clic destro su una cella</b>: regola valida per "
         "quella sola cella.<br>• <b>Risultato</b> mostra il foglio gia' anonimizzato.<br>"
         "La riga di intestazione non viene mai modificata; nei file Excel formule, "
         "formattazione e fogli multipli sono preservati."),
        ("sparkle", "Cosa viene rimosso",
         "Sempre tutto: nomi di qualsiasi persona (anche senza etichetta e in qualsiasi lingua), "
         "codici fiscali, tessere, documenti d'identita', telefoni, indirizzi, email, date, eta', "
         "nosologici, numeri di cartella, referto e protocollo, firme digitali, IBAN e strutture. "
         "Restano visibili termini clinici, eponimi (\"manovra di Giordano\"), farmaci, dosi e "
         "valori di laboratorio."),
        ("list", "Elenchi e priorita'",
         "<b>Rimuovi sempre</b> viene scomposto anche nelle singole parole: \"MARIO ROSSI\" "
         "oscura pure \"MARIO\" e \"ROSSI\" da soli. <b>Mantieni invariate</b> usa le righe "
         "intere ed ha priorita' assoluta: le parole protette vengono sottratte "
         "dall'oscuramento, il resto della corrispondenza viene comunque rimosso."),
        ("shield", "Sicurezza dell'output",
         "Il testo non viene coperto ma <b>rimosso dal contenuto</b> del PDF. Con l'opzione "
         "attiva vengono ripuliti anche metadati, annotazioni, allegati, segnalibri e link. Al "
         "termine ogni file viene riaperto e verificato.<br><b>Attenzione:</b> le pagine "
         "scansionate non contengono testo analizzabile e vengono segnalate negli avvisi."),
    ]

    def __init__(self, parent_main):
        super().__init__(parent_main, "Come funziona Clin",
                         "Guida rapida alle funzioni principali", 640, "help")
        self.resize(660, 660)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("transparent")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 10, 0)
        lay.setSpacing(18)

        for idx, (icon_name, title, body) in enumerate(self.SECTIONS, start=1):
            block = QVBoxLayout()
            block.setSpacing(6)
            head = QHBoxLayout()
            head.setSpacing(8)
            glyph = QLabel()
            glyph.setPixmap(icon(icon_name, ACCENT_INK, 15).pixmap(15, 15))
            num = QLabel(f"{idx}. {title}")
            num.setStyleSheet(f"color: {INK}; font-size: 13px; font-weight: 600;")
            head.addWidget(glyph)
            head.addWidget(num)
            head.addStretch()
            block.addLayout(head)
            text = QLabel(body)
            text.setWordWrap(True)
            text.setTextFormat(Qt.RichText)
            text.setStyleSheet(f"color: {INK_SOFT}; font-size: 12.5px; line-height: 1.65;")
            block.addWidget(text)
            lay.addLayout(block)
        lay.addStretch()
        scroll.setWidget(content)
        self.card_layout.addWidget(scroll, 1)

        btn = make_button("Ho capito", "check", "primary")
        btn.clicked.connect(self.accept)
        self.card_layout.addWidget(btn, 0, Qt.AlignRight)


class ReportDialog(CardDialog):
    """Riepilogo dell'elaborazione con esportazione CSV."""

    def __init__(self, parent_main, batch: BatchResult, elapsed: float, output_dir: Path):
        super().__init__(parent_main, "Elaborazione completata",
                         "Riepilogo per documento", 680, "check")
        self.batch = batch
        self.output_dir = output_dir
        self.resize(700, 560)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        stats.addWidget(pill(f"{batch.processed} file elaborati", SUCCESS, "#eaf3ee", "#d5e7dc"))
        stats.addWidget(pill(f"{batch.total_redactions} oscuramenti"))
        stats.addWidget(pill(f"{elapsed:.1f}s", MUTED, SURFACE_SUNK, HAIRLINE))
        if batch.cancelled:
            stats.addWidget(pill("annullato", WARNING, WARNING_SOFT, "#f0e0c4"))
        if batch.failed:
            stats.addWidget(pill(f"{len(batch.failed)} errori", DANGER, DANGER_SOFT, "#f0d3ce"))
        stats.addStretch()
        self.card_layout.addLayout(stats)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Documento", "Oscuramenti", "Esito"])
        tree.setRootIsDecorated(True)
        tree.header().setStretchLastSection(False)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tree.setStyleSheet(
            f"QTreeWidget {{ background-color: {SURFACE_ALT}; border: 1px solid {HAIRLINE};"
            f" border-radius: {R_MD}px; padding: 6px; font-size: 12.5px; color: {INK_SOFT}; }}"
        )
        for res in batch.results:
            if res.error:
                status, color, ic = res.error, QColor(DANGER), "alert"
            elif res.warnings:
                status, color, ic = res.warnings[0], QColor(WARNING), "info"
            else:
                status, color, ic = "Completato", QColor(SUCCESS), "check"
            item = QTreeWidgetItem(tree, [res.input_path.name, str(res.redactions), status])
            item.setIcon(0, icon(ic, color.name(), 14))
            item.setForeground(2, color)
            for cat, n in sorted(res.per_category.items(), key=lambda kv: -kv[1]):
                QTreeWidgetItem(item, ["", str(n), cat])
            for w in res.warnings[1:]:
                QTreeWidgetItem(item, ["", "", w])
        self.card_layout.addWidget(tree, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        btn_csv = make_button("Esporta CSV", "download", "ghost")
        btn_csv.clicked.connect(self.export_csv)
        btn_open = make_button("Apri cartella", "external", "ghost")
        btn_open.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))
        )
        btn_ok = make_button("Chiudi", None, "primary")
        btn_ok.clicked.connect(self.accept)
        row.addWidget(btn_csv)
        row.addWidget(btn_open)
        row.addStretch()
        row.addWidget(btn_ok)
        self.card_layout.addLayout(row)

    def export_csv(self):
        default = str(self.output_dir / f"report_clin_{datetime.now():%Y%m%d_%H%M}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Esporta report", default, "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(
                    ["File", "Output", "Pagine", "Oscuramenti", "Categorie", "Avvisi", "Errore"]
                )
                for r in self.batch.results:
                    writer.writerow([
                        r.input_path.name,
                        r.output_path.name if r.output_path else "",
                        r.pages, r.redactions,
                        "; ".join(f"{k}={v}" for k, v in sorted(r.per_category.items())),
                        " | ".join(r.warnings), r.error or "",
                    ])
            QMessageBox.information(self, "Report esportato", f"Report salvato in:\n{path}")
        except OSError as exc:
            QMessageBox.warning(self, "Errore", f"Impossibile salvare il report:\n{exc}")


# --------------------------------------------------------------------------
# Widget di base
# --------------------------------------------------------------------------
class ListEditor(QTextEdit):
    """Editor di elenchi: una voce per riga, separate da linee sottili."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_stylesheet = (
            f"QTextEdit {{ background-color: {SURFACE_ALT}; border: 1px solid {HAIRLINE};"
            f" border-radius: {R_MD}px; color: {INK}; font-size: 12.5px; padding: 6px 10px; }}"
            f"QTextEdit:focus {{ border: 1px solid {ACCENT_INK}; background-color: {SURFACE}; }}"
        )
        self.setStyleSheet(self.base_stylesheet)
        self.setAcceptRichText(False)
        self.document().setDefaultStyleSheet(
            f"p {{ border-bottom: 1px solid {HAIRLINE}; margin-top: 1px; margin-bottom: 5px;"
            f" padding-bottom: 4px; color: {INK}; font-size: 12.5px; }}"
        )

    def set_lines(self, lines: List[str]) -> None:
        pos = self.textCursor().position()
        self.setHtml("".join(f"<p>{self._escape(l)}</p>" for l in lines))
        cursor = self.textCursor()
        cursor.setPosition(min(pos, len(self.toPlainText())))
        self.setTextCursor(cursor)

    def setText(self, text: str) -> None:  # compatibilita'
        self.set_lines(text.split("\n"))

    def lines(self) -> List[str]:
        return [l.strip() for l in self.toPlainText().split("\n") if l.strip()]

    @staticmethod
    def _escape(text: str) -> str:
        return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")) or "&nbsp;"


LinedTextEdit = ListEditor  # nome storico


class ClickableImageLabel(QLabel):
    """Etichetta immagine che riconosce parole ed evidenziazioni sotto il cursore."""

    word_clicked_signal = Signal(str, QPoint)

    def __init__(self, parent_preview):
        super().__init__()
        self.parent_preview = parent_preview
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            word = self.parent_preview.get_word_at_pos(event.position().toPoint())
            if word:
                self.word_clicked_signal.emit(word, event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        det = self.parent_preview.detection_at_pos(event.position().toPoint())
        if det:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip(f"{det.category} · {det.text}")
        else:
            self.setCursor(Qt.IBeamCursor if self.pixmap() else Qt.ArrowCursor)
            self.setToolTip("")
        super().mouseMoveEvent(event)


class ClickableTextEdit(QTextEdit):
    """Vista testuale con menu contestuale sulla parola selezionata."""

    word_clicked_signal = Signal(str, QPoint)

    def contextMenuEvent(self, event):
        cursor = self.textCursor()
        text = cursor.selectedText().strip(" .,;:()[]{}\"'«»<>!/?*")
        if not text:
            cursor.select(QTextCursor.WordUnderCursor)
            text = cursor.selectedText().strip(" .,;:()[]{}\"'«»<>!/?*")
        if text:
            self.word_clicked_signal.emit(text, event.globalPos())
            event.accept()
        else:
            super().contextMenuEvent(event)


class CustomScrollArea(QScrollArea):
    """Zoom con trackpad e Ctrl/Cmd + rotellina; scorrendo oltre il bordo cambia pagina."""

    # spinta oltre il bordo (unita' angleDelta: 120 = uno scatto di rotellina)
    PAGE_FLIP_PUSH = 240

    def __init__(self, parent_preview):
        super().__init__()
        self.parent_preview = parent_preview
        self._overscroll = 0
        self._flip_block = QElapsedTimer()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            delta = event.angleDelta().y()
            if delta > 0:
                self.parent_preview.zoom_in()
            elif delta < 0:
                self.parent_preview.zoom_out()
            event.accept()
            return
        delta = event.angleDelta().y()
        bar = self.verticalScrollBar()
        at_end = (delta < 0 and bar.value() >= bar.maximum()) or (delta > 0 and bar.value() <= bar.minimum())
        if not delta or not at_end:
            self._overscroll = 0
            super().wheelEvent(event)
            return
        # l'inerzia del trackpad continua a mandare eventi dopo il cambio pagina
        if self._flip_block.isValid() and self._flip_block.elapsed() < 450:
            event.accept()
            return
        if (self._overscroll < 0) != (delta < 0):
            self._overscroll = 0
        self._overscroll += delta
        if abs(self._overscroll) >= self.PAGE_FLIP_PUSH:
            forward = self._overscroll < 0
            self._overscroll = 0
            preview = self.parent_preview
            before = preview.current_page_idx
            preview.next_page() if forward else preview.prev_page()
            if preview.current_page_idx != before:
                # dopo il rendering il range della barra cambia: si posiziona al giro successivo
                QTimer.singleShot(0, lambda: bar.setValue(bar.minimum() if forward else bar.maximum()))
                self._flip_block.start()
        event.accept()

    def event(self, event: QEvent):
        if event.type() == QEvent.Type.NativeGesture and isinstance(event, QNativeGestureEvent):
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                new_zoom = self.parent_preview.zoom_factor + (event.value() * 1.5)
                if abs(new_zoom - self.parent_preview.zoom_factor) > 0.01:
                    self.parent_preview.set_zoom(new_zoom)
                return True
        return super().event(event)


# --------------------------------------------------------------------------
# Anteprima
# --------------------------------------------------------------------------
@dataclass
class PreviewSettings:
    level: int = MAX_LEVEL
    explicit: Tuple[str, ...] = ()
    whitelist: Tuple[str, ...] = ()
    keep_labels: bool = False
    dpi: int = 135


class PDFPreviewWidget(QWidget):
    """Anteprima grafica e testuale con evidenziazione degli oscuramenti."""

    add_to_blacklist_signal = Signal(str)
    add_to_whitelist_signal = Signal(str)
    status_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.current_doc: Optional[fitz.Document] = None
        self.current_file_path: Optional[Path] = None
        self.current_page_idx = 0
        self.zoom_factor = 1.0
        self.settings = PreviewSettings()
        self.detections: List[Detection] = []
        self.show_highlights = True
        self.search_dirs: List[Path] = []
        self._base_pixmap: Optional[QPixmap] = None

        self._analysis_timer = QTimer(self)
        self._analysis_timer.setSingleShot(True)
        self._analysis_timer.setInterval(170)
        self._analysis_timer.timeout.connect(self.refresh_detections)

        self.init_ui()

    # ---------------- costruzione ----------------
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addLayout(self.build_toolbar())

        self.stack = QStackedWidget()

        self.scroll_area = CustomScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {SURFACE_SUNK}; border: 1px solid {HAIRLINE};"
            f" border-radius: {R_MD}px; }}"
        )
        self.img_label = ClickableImageLabel(self)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setText(
            "Nessun documento aperto\n\nSeleziona un file dall'elenco a sinistra\n"
            "oppure trascina qui i tuoi PDF"
        )
        self.img_label.setStyleSheet(f"color: {FAINT}; font-size: 13px; line-height: 1.7;")
        self.img_label.word_clicked_signal.connect(self.show_word_context_menu)
        self.scroll_area.setWidget(self.img_label)
        self.stack.addWidget(self.scroll_area)

        text_page = QWidget()
        text_page.setObjectName("transparent")
        text_layout = QVBoxLayout(text_page)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Cerca nel testo della pagina")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.returnPressed.connect(self.find_next)
        text_layout.addWidget(self.txt_search)

        self.txt_selectable = ClickableTextEdit()
        self.txt_selectable.setReadOnly(True)
        self.txt_selectable.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.txt_selectable.setPlaceholderText("Testo del documento")
        self.txt_selectable.setStyleSheet(
            f"QTextEdit {{ background-color: {SURFACE_ALT}; border: 1px solid {HAIRLINE};"
            f" border-radius: {R_MD}px; font-family: {MONO_STACK}; font-size: 12px;"
            f" color: {INK_SOFT}; padding: 14px; line-height: 1.6; }}"
        )
        self.txt_selectable.word_clicked_signal.connect(self.show_word_context_menu)
        text_layout.addWidget(self.txt_selectable, 1)
        self.stack.addWidget(text_page)

        layout.addWidget(self.stack, 1)
        layout.addWidget(self.build_legend())

    def build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self.btn_prev = make_button("", "chevron-left", "icon", "Pagina precedente (←)")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = make_button("", "chevron-right", "icon", "Pagina successiva (→)")
        self.btn_next.clicked.connect(self.next_page)

        self.spin_page = QSpinBox()
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(1)
        self.spin_page.setAlignment(Qt.AlignCenter)
        self.spin_page.setFixedWidth(58)
        self.spin_page.setToolTip("Vai alla pagina")
        self.spin_page.valueChanged.connect(self.goto_page)

        self.lbl_page_num = QLabel("—")
        self.lbl_page_num.setStyleSheet(f"color: {FAINT}; font-size: 12px;")

        self.btn_zoom_out = make_button("", "zoom-out", "icon", "Riduci")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_in = make_button("", "zoom-in", "icon", "Ingrandisci")
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_fit = make_button("", "maximize", "icon", "Adatta alla larghezza")
        self.btn_zoom_fit.clicked.connect(self.zoom_fit_width)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        self.lbl_zoom.setFixedWidth(44)
        self.lbl_zoom.setStyleSheet(f"color: {MUTED}; font-size: 12px; font-weight: 500;")

        self.btn_highlight = make_button("", "eye", "icon",
                                        "Mostra o nascondi le evidenziazioni (Cmd/Ctrl+H)")
        self.btn_highlight.setCheckable(True)
        self.btn_highlight.setChecked(True)
        self.btn_highlight.toggled.connect(self.set_highlights_visible)

        self.seg_view = Segmented([("Pagina", "page"), ("Testo", "text")], 0)
        self.seg_view.changed.connect(lambda i: self.toggle_view_mode(i == 1))

        bar.addWidget(self.btn_prev)
        bar.addWidget(self.spin_page)
        bar.addWidget(self.lbl_page_num)
        bar.addWidget(self.btn_next)
        bar.addSpacing(10)
        bar.addWidget(self.btn_zoom_out)
        bar.addWidget(self.lbl_zoom)
        bar.addWidget(self.btn_zoom_in)
        bar.addWidget(self.btn_zoom_fit)
        bar.addStretch()
        bar.addWidget(self.btn_highlight)
        bar.addWidget(self.seg_view)
        return bar

    def build_legend(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("legend")
        wrap.setStyleSheet(
            f"QFrame#legend {{ background-color: {SURFACE_ALT}; border: 1px solid {HAIRLINE};"
            f" border-radius: {R_MD}px; }}"
        )
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(10)

        self.lbl_det_count = QLabel("—")
        self.lbl_det_count.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; font-weight: 500;"
        )
        self.lbl_det_chips = QLabel("")
        self.lbl_det_chips.setWordWrap(True)
        self.lbl_det_chips.setTextFormat(Qt.RichText)
        self.lbl_det_chips.setStyleSheet(f"color: {FAINT}; font-size: 11.5px;")

        lay.addWidget(self.lbl_det_count)
        lay.addWidget(self.lbl_det_chips, 1)
        return wrap

    # ---------------- documento ----------------
    def load_pdf(self, file_path: Path) -> bool:
        try:
            doc = fitz.open(str(file_path))
            if doc.is_encrypted and not doc.authenticate(""):
                doc.close()
                self.img_label.setPixmap(QPixmap())
                self.img_label.setText("PDF protetto da password:\nanteprima non disponibile.")
                self.status_signal.emit(f"PDF protetto: {file_path.name}")
                return False
        except Exception as exc:
            self.img_label.setPixmap(QPixmap())
            self.img_label.setText(f"Impossibile aprire il documento:\n{exc}")
            self.status_signal.emit(f"Errore apertura {file_path.name}")
            return False

        self.close_document()
        self.current_doc = doc
        self.current_file_path = file_path
        self.current_page_idx = 0
        self.spin_page.blockSignals(True)
        self.spin_page.setMaximum(max(1, len(doc)))
        self.spin_page.setValue(1)
        self.spin_page.blockSignals(False)
        self.render_current_page()
        self.start_context_analysis()
        return True

    def start_context_analysis(self):
        """Il modello locale lavora in background; l'anteprima si aggiorna alla fine."""
        if getattr(self, "_context_worker", None) is not None:
            self._context_worker.requestInterruption()
        try:
            texts = [_PageIndex(page).text for page in self.current_doc]
        except Exception:
            return
        worker = ContextAnalysisWorker(texts)
        worker.finished_signal.connect(self._on_context_ready)
        worker.finished.connect(worker.deleteLater)
        self._context_worker = worker
        worker.start()

    def _on_context_ready(self, status: str, found: bool):
        if self.sender() is not getattr(self, "_context_worker", None):
            return  # documento cambiato nel frattempo
        self._context_worker = None
        self.status_signal.emit(f"Riconoscimento contestuale: {status}")
        if found:
            self._names_key = None  # i nomi trovati dal modello entrano nella propagazione
            self.request_analysis()

    def close_document(self):
        if self.current_doc is not None:
            try:
                self.current_doc.close()
            except Exception:
                pass
        self.current_doc = None
        self.detections = []
        self._names_key = None

    def has_document(self) -> bool:
        return self.current_doc is not None and len(self.current_doc) > 0

    # ---------------- rendering ----------------
    def scale(self) -> float:
        return (self.settings.dpi * self.zoom_factor) / 72.0

    def render_current_page(self):
        if not self.has_document():
            self.lbl_page_num.setText("—")
            self.lbl_det_count.setText("—")
            self.lbl_det_chips.setText("")
            return

        page_count = len(self.current_doc)
        self.current_page_idx = max(0, min(self.current_page_idx, page_count - 1))
        self.lbl_page_num.setText(f"di {page_count}")
        self.btn_prev.setEnabled(self.current_page_idx > 0)
        self.btn_next.setEnabled(self.current_page_idx < page_count - 1)
        self.lbl_zoom.setText(f"{int(self.zoom_factor * 100)}%")
        self.spin_page.blockSignals(True)
        self.spin_page.setValue(self.current_page_idx + 1)
        self.spin_page.blockSignals(False)

        try:
            page = self.current_doc.load_page(self.current_page_idx)
            dpi = max(40, int(self.settings.dpi * self.zoom_factor))
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride,
                          QImage.Format_RGB888).copy()
            self._base_pixmap = QPixmap.fromImage(qimg)
            self.img_label.setPixmap(self._base_pixmap)
            self.img_label.setFixedSize(self._base_pixmap.size())
            self.txt_selectable.setPlainText(page.get_text())
            fade_in(self.img_label)
        except Exception as exc:
            self.img_label.setPixmap(QPixmap())
            self.img_label.setText(f"Errore nel rendering della pagina:\n{exc}")
            return

        self._analysis_timer.start()

    def request_analysis(self):
        if self.has_document():
            self._analysis_timer.start()

    def refresh_detections(self):
        if not self.has_document():
            return
        try:
            with clin_llm.cache_only():  # niente attese nell'interfaccia: il modello gira a parte
                self._refresh_detections_cached()
        except Exception:
            self.detections = []
        self.paint_overlay()

    def _refresh_detections_cached(self):
        key = (id(self.current_doc), self.settings.level, tuple(self.settings.whitelist))
        if getattr(self, "_names_key", None) != key:
            self._names_key = key
            self._doc_names = collect_document_names(
                self.current_doc, self.settings.level, list(self.settings.whitelist))
        page = self.current_doc.load_page(self.current_page_idx)
        self.detections = analyze_page(
            page,
            sensitivity_level=self.settings.level,
            explicit_targets=list(self.settings.explicit),
            whitelist_words=list(self.settings.whitelist),
            keep_labels=self.settings.keep_labels,
            derived_targets=self._doc_names,
        )

    def paint_overlay(self):
        if self._base_pixmap is None:
            return
        if not self.show_highlights or not self.detections:
            self.img_label.setPixmap(self._base_pixmap)
            self.update_detection_label()
            return

        pixmap = QPixmap(self._base_pixmap)
        painter = QPainter(pixmap)
        scale = self.scale()
        for det in self.detections:
            r, g, b = det.color
            painter.setPen(QPen(QColor(r, g, b, 210), 1.2))
            painter.setBrush(QColor(r, g, b, 58))
            for rect in det.rects:
                painter.drawRoundedRect(
                    int(rect.x0 * scale) - 1, int(rect.y0 * scale) - 1,
                    max(2, int((rect.x1 - rect.x0) * scale) + 2),
                    max(2, int((rect.y1 - rect.y0) * scale) + 2),
                    3, 3,
                )
        painter.end()
        self.img_label.setPixmap(pixmap)
        self.update_detection_label()

    def update_detection_label(self):
        if not self.has_document():
            self.lbl_det_count.setText("—")
            self.lbl_det_chips.setText("")
            return

        if not self.detections:
            page = self.current_doc.load_page(self.current_page_idx)
            if not page.get_text().strip():
                self.lbl_det_count.setText("Pagina scansionata")
                self.lbl_det_count.setStyleSheet(
                    f"color: {WARNING}; font-size: 12px; font-weight: 600;"
                )
                self.lbl_det_chips.setText(
                    "Nessun testo selezionabile: l'analisi automatica non puo' rilevare dati. "
                    "Verificare manualmente."
                )
            else:
                self.lbl_det_count.setText("Nessun rilevamento")
                self.lbl_det_count.setStyleSheet(
                    f"color: {MUTED}; font-size: 12px; font-weight: 500;"
                )
                self.lbl_det_chips.setText("In questa pagina non risultano dati da oscurare.")
            return

        by_cat: Dict[str, int] = {}
        for d in self.detections:
            by_cat[d.category] = by_cat.get(d.category, 0) + 1
        chips = " &nbsp; ".join(
            f"<span style='color:rgb{CATEGORY_COLORS.get(c, (201,100,66))}'>&#9679;</span>"
            f"&nbsp;{c} <span style='color:{FAINT}'>{n}</span>"
            for c, n in sorted(by_cat.items(), key=lambda kv: -kv[1])
        )
        self.lbl_det_count.setStyleSheet(f"color: {INK}; font-size: 12px; font-weight: 600;")
        self.lbl_det_count.setText(f"{len(self.detections)} da oscurare")
        self.lbl_det_chips.setText(chips)

    def set_highlights_visible(self, visible: bool):
        self.show_highlights = visible
        self.btn_highlight.setIcon(icon("eye" if visible else "eye-off",
                                        ACCENT_INK if visible else MUTED, 16))
        self.paint_overlay()

    def update_settings(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if hasattr(self.settings, key) and getattr(self.settings, key) != value:
                setattr(self.settings, key, value)
                changed = True
        if not changed:
            return
        if "dpi" in kwargs:
            self.render_current_page()
        else:
            self.request_analysis()

    # ---------------- interazione ----------------
    def _pixmap_offset(self) -> Tuple[int, int, int, int]:
        pixmap = self.img_label.pixmap()
        if not pixmap or pixmap.isNull():
            return (0, 0, 0, 0)
        off_x = max(0, (self.img_label.width() - pixmap.width()) // 2)
        off_y = max(0, (self.img_label.height() - pixmap.height()) // 2)
        return off_x, off_y, pixmap.width(), pixmap.height()

    def _to_pdf_coords(self, pos: QPoint) -> Optional[Tuple[float, float]]:
        off_x, off_y, pw, ph = self._pixmap_offset()
        if pw == 0:
            return None
        x, y = pos.x() - off_x, pos.y() - off_y
        if x < 0 or y < 0 or x > pw or y > ph:
            return None
        scale = self.scale()
        return x / scale, y / scale

    def detection_at_pos(self, pos: QPoint) -> Optional[Detection]:
        coords = self._to_pdf_coords(pos)
        if not coords or not self.detections:
            return None
        px, py = coords
        for det in self.detections:
            for rect in det.rects:
                if rect.x0 - 2 <= px <= rect.x1 + 2 and rect.y0 - 2 <= py <= rect.y1 + 2:
                    return det
        return None

    def get_word_at_pos(self, pos: QPoint) -> Optional[str]:
        if not self.has_document():
            return None
        coords = self._to_pdf_coords(pos)
        if not coords:
            return None
        pdf_x, pdf_y = coords

        det = self.detection_at_pos(pos)
        if det:
            return det.text

        page = self.current_doc.load_page(self.current_page_idx)
        for w in page.get_text("words"):
            x0, y0, x1, y1, word_text = w[0], w[1], w[2], w[3], w[4]
            if (x0 - 4) <= pdf_x <= (x1 + 4) and (y0 - 4) <= pdf_y <= (y1 + 4):
                clean = word_text.strip(" .,;:()[]{}\"'«»<>!/?*")
                if clean:
                    return clean

        return self._text_under_redaction(page, pdf_x, pdf_y)

    def _text_under_redaction(self, page, pdf_x: float, pdf_y: float) -> Optional[str]:
        """Su un file gia' anonimizzato recupera il testo coperto da un rettangolo."""
        target_rect = None
        try:
            drawings = page.get_drawings()
        except Exception:
            return None
        for d in drawings:
            rect, fill = d.get("rect"), d.get("fill")
            is_dark = fill is not None and isinstance(fill, (list, tuple)) and sum(fill) < 0.3
            if rect and is_dark:
                if (rect.x0 - 3) <= pdf_x <= (rect.x1 + 3) and (rect.y0 - 3) <= pdf_y <= (rect.y1 + 3):
                    target_rect = rect
                    break
        if target_rect is None or not self.current_file_path:
            return None

        orig_file = self._guess_original_file()
        if not orig_file:
            return None
        try:
            with fitz.open(str(orig_file)) as orig_doc:
                if self.current_page_idx >= len(orig_doc):
                    return None
                matched = []
                for w in orig_doc[self.current_page_idx].get_text("words"):
                    wx0, wy0, wx1, wy1, wtext = w[0], w[1], w[2], w[3], w[4]
                    inside = (
                        (target_rect.x0 - 4) <= wx0 and wx1 <= (target_rect.x1 + 4)
                        and (target_rect.y0 - 4) <= wy0 and wy1 <= (target_rect.y1 + 4)
                    )
                    if inside:
                        clean = wtext.strip(" .,;:()[]{}\"'«»<>!/?*")
                        if clean:
                            matched.append(clean)
                return " ".join(matched) if matched else None
        except Exception:
            return None

    def _guess_original_file(self) -> Optional[Path]:
        path = self.current_file_path
        if path is None:
            return None
        known = ORIGINS.get(path.resolve())
        if known and known.exists():
            return known
        stem = path.stem
        if stem.endswith(OUTPUT_SUFFIX):
            stem = stem[: -len(OUTPUT_SUFFIX)]
        candidates = [
            path.parent / f"{stem}.pdf",
            path.parent.parent / f"{stem}.pdf",
            Path(os.getcwd()) / f"{stem}.pdf",
        ]
        candidates.extend(Path(d) / f"{stem}.pdf" for d in (self.search_dirs or []))
        for c in candidates:
            if c.exists() and c.resolve() != path.resolve():
                return c
        return None

    def show_word_context_menu(self, word: str, global_pos: QPoint):
        menu = QMenu(self)
        shown = word if len(word) <= 48 else word[:45] + "..."
        header = menu.addAction(f'"{shown}"')
        header.setEnabled(False)
        menu.addSeparator()
        act_exclude = menu.addAction(icon("eraser", INK_SOFT, 15), "Rimuovi sempre")
        act_include = menu.addAction(icon("shield", INK_SOFT, 15), "Mantieni invariata")
        menu.addSeparator()
        act_copy = menu.addAction(icon("list", INK_SOFT, 15), "Copia negli appunti")

        chosen = menu.exec(global_pos)
        if chosen == act_exclude:
            self.add_to_blacklist_signal.emit(word)
        elif chosen == act_include:
            self.add_to_whitelist_signal.emit(word)
        elif chosen == act_copy:
            QApplication.clipboard().setText(word)

    # ---------------- navigazione ----------------
    def goto_page(self, page_number: int):
        if self.has_document():
            self.current_page_idx = page_number - 1
            self.render_current_page()

    def prev_page(self):
        if self.has_document() and self.current_page_idx > 0:
            self.current_page_idx -= 1
            self.render_current_page()

    def next_page(self):
        if self.has_document() and self.current_page_idx < len(self.current_doc) - 1:
            self.current_page_idx += 1
            self.render_current_page()

    def set_zoom(self, value: float):
        self.zoom_factor = max(0.3, min(value, 4.0))
        self.render_current_page()

    def zoom_in(self):
        self.set_zoom(self.zoom_factor + 0.2)

    def zoom_out(self):
        self.set_zoom(self.zoom_factor - 0.2)

    def zoom_reset(self):
        self.set_zoom(1.0)

    def zoom_fit_width(self):
        if not self.has_document():
            return
        page = self.current_doc.load_page(self.current_page_idx)
        available = self.scroll_area.viewport().width() - 28
        if available <= 0 or page.rect.width <= 0:
            return
        self.set_zoom((available * 72.0) / (page.rect.width * self.settings.dpi))

    def find_next(self):
        needle = self.txt_search.text().strip()
        if not needle:
            return
        if not self.txt_selectable.find(needle):
            cursor = self.txt_selectable.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.txt_selectable.setTextCursor(cursor)
            self.txt_selectable.find(needle)

    def toggle_view_mode(self, text_mode: bool):
        self.stack.setCurrentIndex(1 if text_mode else 0)
        self.seg_view.set_current(1 if text_mode else 0, emit=False)
        if text_mode:
            self.txt_search.setFocus()

    def copy_page_text(self):
        if self.has_document():
            QApplication.clipboard().setText(
                self.current_doc.load_page(self.current_page_idx).get_text()
            )


# --------------------------------------------------------------------------
# Finestra principale
# --------------------------------------------------------------------------
class ClinMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} · Clinical Data Anonymizer for AI")
        self.resize(1420, 900)
        self.setMinimumSize(1080, 700)
        self.setAcceptDrops(True)

        self.settings_store = QSettings(ORG_NAME, APP_NAME)
        self.input_folder: Path = Path(os.getcwd())
        self.output_folder: Path = Path(os.getcwd()) / "PDF_Anonimizzati"
        self.input_files: List[Path] = []
        self.worker: Optional[AnonymizeWorker] = None
        self._start_time = 0.0
        self._batch: Optional[BatchResult] = None
        self._unchecked_cache: set = set()
        self.table_settings = TableSettings()

        self.fill_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.render_dpi: int = 135
        self.overwrite: bool = True
        self.verify_output: bool = True

        self.setStyleSheet(app_stylesheet())
        self.init_ui()
        self.init_menu()
        self.load_preferences()
        self.refresh_worktrees()
        self.sync_preview_settings()

    # ---------------- costruzione ----------------
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(16)

        root.addLayout(self.build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)
        self.main_splitter = splitter
        root.addWidget(splitter, 1)

        splitter.addWidget(self.build_files_panel())
        splitter.addWidget(self.build_preview_panel())
        splitter.addWidget(self.build_settings_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([320, 760, 340])

        self.status = self.statusBar()
        self.status.showMessage("Pronto")

    def build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(12)

        mark = QLabel()
        mark.setPixmap(app_icon().pixmap(36, 36))
        mark.setFixedSize(36, 36)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setStyleSheet(
            f"color: {INK}; font-size: 19px; font-weight: 500; letter-spacing: -0.5px;"
        )
        sub = caption("Clinical Data Anonymizer for AI")
        sub.setWordWrap(False)
        titles.addWidget(name)
        titles.addWidget(sub)

        header.addWidget(mark)
        header.addLayout(titles)
        header.addStretch()

        self.btn_how_it_works = make_button("Guida", "help", "ghost", "Come funziona Clin")
        self.btn_how_it_works.clicked.connect(self.open_how_it_works)
        self.btn_settings = make_button("Impostazioni", "settings", "ghost")
        self.btn_settings.clicked.connect(self.open_settings)
        header.addWidget(self.btn_how_it_works)
        header.addWidget(self.btn_settings)
        return header

    def build_files_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("transparent")
        panel.setMinimumWidth(280)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # --- documenti di input ---
        card = Panel()
        card.add_header("Documenti", "folder")

        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_select_in_dir = make_button("Cartella", "folder", "secondary",
                                            "Carica tutti i PDF di una cartella (Cmd/Ctrl+O)")
        self.btn_select_in_files = make_button("File", "file-plus", "secondary",
                                              "Aggiungi singoli PDF (Cmd/Ctrl+Shift+O)")
        self.btn_clear_files = make_button("", "trash", "icon", "Svuota l'elenco")
        self.btn_select_in_dir.clicked.connect(self.select_input_folder)
        self.btn_select_in_files.clicked.connect(self.select_input_files)
        self.btn_clear_files.clicked.connect(self.clear_input_files)
        row.addWidget(self.btn_select_in_dir, 1)
        row.addWidget(self.btn_select_in_files, 1)
        row.addWidget(self.btn_clear_files)
        card.body.addLayout(row)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filtra per nome")
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.addAction(icon("search", FAINT, 15), QLineEdit.LeadingPosition)
        self.txt_filter.textChanged.connect(self.apply_file_filter)
        card.body.addWidget(self.txt_filter)

        self.input_tree = QTreeWidget()
        self.input_tree.setHeaderHidden(True)
        self.input_tree.setColumnCount(2)
        self.input_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.input_tree.header().setStretchLastSection(False)
        self.input_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.input_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.input_tree.itemClicked.connect(self.on_input_tree_item_clicked)
        self.input_tree.itemChanged.connect(self.on_input_item_changed)
        self.input_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.input_tree.customContextMenuRequested.connect(self.show_input_context_menu)
        card.body.addWidget(self.input_tree, 1)

        card.body.addWidget(hairline())
        foot = QHBoxLayout()
        foot.setSpacing(4)
        self.lbl_selection = QLabel("Nessun documento")
        self.lbl_selection.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.lbl_selection.setWordWrap(True)
        btn_all = make_button("Tutti", "check-all", "ghost", "Spunta i file visibili")
        btn_all.clicked.connect(lambda: self.set_all_checked(True))
        btn_none = make_button("Nessuno", "square", "ghost", "Togli tutte le spunte")
        btn_none.clicked.connect(lambda: self.set_all_checked(False))
        for b in (btn_all, btn_none):
            b.setMinimumWidth(b.sizeHint().width())
        foot.addWidget(self.lbl_selection, 1)
        foot.addWidget(btn_all)
        foot.addWidget(btn_none)
        card.body.addLayout(foot)
        layout.addWidget(card, 3)

        # --- output ---
        out = Panel()
        head = out.add_header("Risultati", "download")
        self.btn_select_out_dir = make_button("", "folder", "icon", "Scegli la cartella di output")
        self.btn_select_out_dir.clicked.connect(self.select_output_folder)
        self.btn_open_folder_small = make_button("", "external", "icon", "Apri nel Finder")
        self.btn_open_folder_small.clicked.connect(self.open_output_folder)
        head.addWidget(self.btn_select_out_dir)
        head.addWidget(self.btn_open_folder_small)

        self.lbl_output_path = QLabel(str(self.output_folder))
        self.lbl_output_path.setWordWrap(True)
        self.lbl_output_path.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-family: {MONO_STACK};"
            f" background-color: {SURFACE_ALT}; border: 1px solid {HAIRLINE};"
            f" border-radius: {R_SM}px; padding: 6px 8px;"
        )
        out.body.addWidget(self.lbl_output_path)

        self.output_tree = QTreeWidget()
        self.output_tree.setHeaderHidden(True)
        self.output_tree.setColumnCount(2)
        self.output_tree.header().setStretchLastSection(False)
        self.output_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.output_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.output_tree.itemClicked.connect(self.on_output_tree_item_clicked)
        out.body.addWidget(self.output_tree, 1)
        layout.addWidget(out, 2)
        return panel

    def build_preview_panel(self) -> QWidget:
        card = Panel(padding=14, spacing=12)
        head = card.add_header("Anteprima", "eye")
        self.lbl_preview_hint = caption("clic su una parola per aggiungerla agli elenchi")
        self.lbl_preview_hint.setWordWrap(False)
        head.insertWidget(2, self.lbl_preview_hint)

        self.preview_widget = PDFPreviewWidget()
        self.preview_widget.add_to_blacklist_signal.connect(self.add_to_blacklist)
        self.preview_widget.add_to_whitelist_signal.connect(self.add_to_whitelist)
        self.preview_widget.status_signal.connect(self.set_status)

        self.table_preview = TablePreviewWidget(self.table_settings)
        self.table_preview.add_to_blacklist_signal.connect(self.add_to_blacklist)
        self.table_preview.add_to_whitelist_signal.connect(self.add_to_whitelist)
        self.table_preview.status_signal.connect(self.set_status)

        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.preview_widget)
        self.preview_stack.addWidget(self.table_preview)
        card.body.addWidget(self.preview_stack, 1)
        return card

    def open_document(self, path: Path) -> bool:
        """Apre un documento nell'anteprima adatta al suo formato."""
        if is_table_file(path):
            self.preview_stack.setCurrentIndex(1)
            self.lbl_preview_hint.setText(
                "clic destro su intestazione o cella per scegliere come trattarla"
            )
            return self.table_preview.load_file(path)
        self.preview_stack.setCurrentIndex(0)
        self.lbl_preview_hint.setText("clic su una parola per aggiungerla agli elenchi")
        return self.preview_widget.load_pdf(path)

    def build_settings_panel(self) -> QWidget:
        container = QWidget()
        container.setObjectName("transparent")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(14)

        # --- elenchi ---
        lists = Panel()
        lists.add_header("Termini", "list")

        lbl_b = QLabel("Rimuovi sempre")
        lbl_b.setStyleSheet(f"color: {INK}; font-size: 12px; font-weight: 600;")
        lists.body.addWidget(lbl_b)
        lists.body.addWidget(caption("Una voce per riga. Le righe con piu' parole vengono "
                                     "scomposte anche nelle singole parole."))
        self.txt_custom = ListEditor()
        self.txt_custom.setMinimumHeight(82)
        self.txt_custom.setMaximumHeight(118)
        self.txt_custom.setPlaceholderText("COGNOME NOME\n04/05/2020\nRSSMRA80A01H501U")
        self.txt_custom.textChanged.connect(self.on_lists_changed)
        lists.body.addWidget(self.txt_custom)

        lists.body.addWidget(hairline())
        lbl_w = QLabel("Mantieni invariate")
        lbl_w.setStyleSheet(f"color: {INK}; font-size: 12px; font-weight: 600;")
        lists.body.addWidget(lbl_w)
        lists.body.addWidget(caption("Mai oscurate, nemmeno dentro una corrispondenza piu' ampia."))
        self.txt_whitelist = ListEditor()
        self.txt_whitelist.setMinimumHeight(70)
        self.txt_whitelist.setMaximumHeight(100)
        self.txt_whitelist.setPlaceholderText("Pediatria\nEmatologia\nMioglobina")
        self.txt_whitelist.textChanged.connect(self.on_lists_changed)
        lists.body.addWidget(self.txt_whitelist)
        layout.addWidget(lists)

        # --- opzioni ---
        opts = Panel()
        opts.add_header("Opzioni", "settings")
        self.chk_images = ToggleRow(
            "Rimuovi loghi ed immagini", True,
            "Oscura ogni immagine incorporata: loghi, timbri, firme scansionate.",
        )
        self.chk_keep_labels = ToggleRow(
            "Mantieni visibili le etichette", False,
            "Oscura solo il valore: \"Paziente: ███\" invece di \"███\".",
        )
        self.chk_keep_labels.toggled.connect(lambda _: self.sync_preview_settings())
        self.chk_sanitize = ToggleRow(
            "Pulisci metadati ed allegati", True,
            "Rimuove metadati, annotazioni, segnalibri, allegati e link.",
        )
        for i, w in enumerate((self.chk_images, self.chk_keep_labels, self.chk_sanitize)):
            if i:
                opts.body.addWidget(hairline())
            opts.body.addWidget(w)
        layout.addWidget(opts)

        # --- registro ---
        log = Panel()
        head = log.add_header("Registro", "list")
        self.btn_report = make_button("", "info", "icon", "Riapri l'ultimo report")
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self.show_last_report)
        btn_save_log = make_button("", "download", "icon", "Salva il registro")
        btn_save_log.clicked.connect(self.save_log)
        btn_clear_log = make_button("", "eraser", "icon", "Pulisci il registro")
        head.addWidget(self.btn_report)
        head.addWidget(btn_save_log)
        head.addWidget(btn_clear_log)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(120)
        self.log_console.setPlaceholderText("Nessuna attivita' registrata")
        self.log_console.setStyleSheet(
            f"QTextEdit {{ font-family: {MONO_STACK}; font-size: 11px;"
            f" background-color: {SURFACE_ALT}; border: 1px solid {HAIRLINE};"
            f" border-radius: {R_MD}px; color: {INK_SOFT}; padding: 10px; }}"
        )
        btn_clear_log.clicked.connect(self.log_console.clear)
        log.body.addWidget(self.log_console, 1)
        layout.addWidget(log, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(container)

        # --- barra d'azione, ancorata in basso e sempre visibile ---
        action = Panel(padding=14, spacing=10)
        self.btn_start = make_button("Avvia anonimizzazione", "play", "primary",
                                     "Elabora i file spuntati (Cmd/Ctrl+R)")
        self.btn_start.clicked.connect(self.start_anonymization)

        self.btn_cancel = make_button("Interrompi", "stop", "danger")
        self.btn_cancel.clicked.connect(self.cancel_anonymization)
        self.btn_cancel.setVisible(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self._progress_anim = QPropertyAnimation(self.progress_bar, b"value", self)
        self._progress_anim.setDuration(220)
        self._progress_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.lbl_progress = caption("", MUTED, 11.5)
        self.lbl_progress.setVisible(False)

        self.btn_open_folder = make_button("Apri cartella dei risultati", "external", "secondary")
        self.btn_open_folder.clicked.connect(self.open_output_folder)

        action.body.addWidget(self.btn_start)
        action.body.addWidget(self.btn_cancel)
        action.body.addWidget(self.progress_bar)
        action.body.addWidget(self.lbl_progress)
        action.body.addWidget(self.btn_open_folder)

        column = QWidget()
        column.setObjectName("transparent")
        column.setMinimumWidth(330)
        col_layout = QVBoxLayout(column)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(14)
        col_layout.addWidget(scroll, 1)
        col_layout.addWidget(action, 0)
        return column

    def init_menu(self):
        menubar = self.menuBar()

        m_file = menubar.addMenu("File")
        self._add_action(m_file, "Apri cartella...", QKeySequence.Open, self.select_input_folder)
        self._add_action(m_file, "Aggiungi file...", QKeySequence("Ctrl+Shift+O"),
                         self.select_input_files)
        self._add_action(m_file, "Scegli cartella dei risultati...", QKeySequence("Ctrl+Shift+S"),
                         self.select_output_folder)
        m_file.addSeparator()
        self._add_action(m_file, "Avvia anonimizzazione", QKeySequence("Ctrl+R"),
                         self.start_anonymization)
        self._add_action(m_file, "Interrompi", QKeySequence("Escape"), self.cancel_anonymization)
        m_file.addSeparator()
        self._add_action(m_file, "Apri cartella dei risultati", QKeySequence("Ctrl+Shift+F"),
                         self.open_output_folder)

        m_view = menubar.addMenu("Visualizza")
        self._add_action(m_view, "Pagina precedente", QKeySequence("Left"),
                         lambda: self.preview_widget.prev_page())
        self._add_action(m_view, "Pagina successiva", QKeySequence("Right"),
                         lambda: self.preview_widget.next_page())
        m_view.addSeparator()
        self._add_action(m_view, "Ingrandisci", QKeySequence.ZoomIn,
                         lambda: self.preview_widget.zoom_in())
        self._add_action(m_view, "Riduci", QKeySequence.ZoomOut,
                         lambda: self.preview_widget.zoom_out())
        self._add_action(m_view, "Zoom 100%", QKeySequence("Ctrl+0"),
                         lambda: self.preview_widget.zoom_reset())
        self._add_action(m_view, "Adatta alla larghezza", QKeySequence("Ctrl+1"),
                         lambda: self.preview_widget.zoom_fit_width())
        m_view.addSeparator()
        self._add_action(m_view, "Mostra o nascondi evidenziazioni", QKeySequence("Ctrl+H"),
                         lambda: self.preview_widget.btn_highlight.toggle())
        self._add_action(m_view, "Cerca nel testo", QKeySequence.Find, self.focus_search)

        m_ai = menubar.addMenu("IA")
        self._add_action(m_ai, "Anonimizza testo copiato (appunti)", QKeySequence("Ctrl+Shift+A"),
                         lambda: self.run_ai_action("appunti"))
        self._add_action(m_ai, "Ripristina risposta dell'IA (appunti)", QKeySequence("Ctrl+Shift+R"),
                         lambda: self.run_ai_action("ripristina"))
        self._add_action(m_ai, "Dimentica tabella segnaposto", None,
                         lambda: self.run_ai_action("dimentica"))
        m_ai.addSeparator()
        self._add_action(m_ai, "Collega a Claude Desktop", None,
                         lambda: self.run_ai_action("claude-desktop"))
        self._add_action(m_ai, "Collega a Claude Code", None,
                         lambda: self.run_ai_action("claude-code"))
        m_ai.addSeparator()
        self._add_action(m_ai, "Agenti IA: installazione e impostazioni di /clin…", None,
                         lambda: AgentsDialog(self).exec())

        m_help = menubar.addMenu("Aiuto")
        self._add_action(m_help, "Come funziona", QKeySequence.HelpContents, self.open_how_it_works)
        self._add_action(m_help, "Impostazioni", QKeySequence.Preferences, self.open_settings)
        self._add_action(m_help, "Cosa rimuovere…", None, lambda: CategoriesDialog(self).exec())

    def run_ai_action(self, action: str):
        """Strumenti per l'uso con le IA (vedi clin.py)."""
        import clin
        try:
            if action == "appunti":
                msg = clin.clip_anonymize()
            elif action == "ripristina":
                msg = clin.clip_restore()
            elif action == "dimentica":
                clin.MAP_FILE.unlink(missing_ok=True)
                msg = "Tabella segnaposto cancellata."
            elif action == "claude-desktop":
                msg = clin.connect_claude_desktop()
            else:
                msg = clin.connect_claude_code()
            self.log(msg, "ok")
            self.status.showMessage(msg, 6000)
        except Exception as exc:
            self.log(str(exc), "error")
            self.status.showMessage(str(exc), 8000)

    def _add_action(self, menu, text: str, shortcut, slot):
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(shortcut)
        act.triggered.connect(slot)
        menu.addAction(act)
        self.addAction(act)
        return act

    # ---------------- preferenze ----------------
    def load_preferences(self):
        s = self.settings_store
        geometry = s.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        splitter_state = s.value("window/splitter")
        if splitter_state:
            self.main_splitter.restoreState(splitter_state)

        self.fill_color = tuple(float(x) for x in s.value("engine/fill_color", [0.0, 0.0, 0.0]))
        self.render_dpi = int(s.value("preview/dpi", 135))
        self.overwrite = s.value("engine/overwrite", True, type=bool)
        self.verify_output = s.value("engine/verify", True, type=bool)

        self.txt_custom.setText(s.value("lists/blacklist", ""))
        self.txt_whitelist.setText(s.value("lists/whitelist", "Pediatria\nEmatologia\nMioglobina"))
        self.chk_images.set_checked(s.value("engine/remove_images", True, type=bool), emit=False)
        self.chk_keep_labels.set_checked(s.value("engine/keep_labels", False, type=bool), emit=False)
        self.chk_sanitize.set_checked(s.value("engine/sanitize", True, type=bool), emit=False)

        last_in = s.value("paths/input")
        if last_in and Path(last_in).is_dir():
            self.input_folder = Path(last_in)
        last_out = s.value("paths/output")
        self.output_folder = Path(last_out) if last_out else self.input_folder / "PDF_Anonimizzati"
        self.lbl_output_path.setText(str(self.output_folder))

    def save_preferences(self):
        s = self.settings_store
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/splitter", self.main_splitter.saveState())
        s.setValue("engine/fill_color", list(self.fill_color))
        s.setValue("preview/dpi", self.render_dpi)
        s.setValue("engine/overwrite", self.overwrite)
        s.setValue("engine/verify", self.verify_output)
        s.setValue("lists/blacklist", self.txt_custom.toPlainText())
        s.setValue("lists/whitelist", self.txt_whitelist.toPlainText())
        s.setValue("engine/remove_images", self.chk_images.isChecked())
        s.setValue("engine/keep_labels", self.chk_keep_labels.isChecked())
        s.setValue("engine/sanitize", self.chk_sanitize.isChecked())
        s.setValue("paths/input", str(self.input_folder))
        s.setValue("paths/output", str(self.output_folder))

    # ---------------- registro ----------------
    def log(self, message: str, level: str = "info"):
        colors = {"info": INK_SOFT, "ok": SUCCESS, "warn": WARNING, "error": DANGER}
        stamp = datetime.now().strftime("%H:%M:%S")
        safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log_console.append(
            f'<span style="color:{FAINT}">{stamp}</span>&nbsp;&nbsp;'
            f'<span style="color:{colors.get(level, INK_SOFT)}">{safe}</span>'
        )
        bar = self.log_console.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_status(self, message: str):
        self.status.showMessage(message, 8000)

    def save_log(self):
        default = str(self.output_folder / f"clin_log_{datetime.now():%Y%m%d_%H%M}.txt")
        path, _ = QFileDialog.getSaveFileName(self, "Salva registro", default, "Testo (*.txt)")
        if not path:
            return
        try:
            Path(path).write_text(self.log_console.toPlainText(), encoding="utf-8")
            self.log(f"Registro salvato in {path}", "ok")
        except OSError as exc:
            self.log(f"Impossibile salvare il registro: {exc}", "error")

    # ---------------- gestione file ----------------
    def add_files(self, paths: List[Path]) -> int:
        added = 0
        for p in paths:
            if p.suffix.lower() not in SUPPORTED_SUFFIXES or p.stem.endswith(OUTPUT_SUFFIX):
                continue
            if p not in self.input_files and p.exists():
                self.input_files.append(p)
                added += 1
        if added:
            self.refresh_worktrees()
        return added

    def select_input_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Seleziona la cartella con i documenti", str(self.input_folder)
        )
        if not folder:
            return
        self.input_folder = Path(folder)
        pdfs = sorted(
            p for p in self.input_folder.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
            and not p.stem.endswith(OUTPUT_SUFFIX)
        )
        self.input_files = pdfs
        self._unchecked_cache = set()
        if self.settings_store.value("paths/output") is None:
            self.output_folder = self.input_folder / "PDF_Anonimizzati"
            self.lbl_output_path.setText(str(self.output_folder))
        self.refresh_worktrees()
        self.log(f"Cartella caricata: {self.input_folder.name} · {len(pdfs)} documenti", "ok")

    def select_input_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Seleziona i documenti", str(self.input_folder), FILE_DIALOG_FILTER
        )
        if not files:
            return
        added = self.add_files([Path(f) for f in files])
        self.input_folder = Path(files[0]).parent
        self.log(f"{added} file aggiunti all'elenco.", "ok" if added else "warn")

    def clear_input_files(self):
        self.input_files = []
        self._unchecked_cache = set()
        self.refresh_worktrees()
        self.log("Elenco svuotato.")

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Seleziona la cartella dei risultati", str(self.output_folder)
        )
        if folder:
            self.output_folder = Path(folder)
            self.lbl_output_path.setText(str(self.output_folder))
            self.refresh_worktrees()
            self.log(f"Cartella dei risultati: {self.output_folder}")

    def refresh_worktrees(self):
        # Si memorizzano i file *deselezionati*: un file appena aggiunto arriva
        # sempre spuntato, mentre le deselezioni manuali sopravvivono.
        unchecked_before = self._unchecked_cache

        self.input_tree.blockSignals(True)
        self.input_tree.clear()
        if self.input_files:
            root = QTreeWidgetItem(self.input_tree, [f"{len(self.input_files)} documenti", ""])
            root.setFlags(root.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            root.setCheckState(0, Qt.Checked)
            root.setForeground(0, QColor(MUTED))
            for pdf in self.input_files:
                try:
                    size_str = human_size(pdf.stat().st_size)
                except OSError:
                    size_str = "n/d"
                child = QTreeWidgetItem(root, [pdf.name, size_str])
                child.setData(0, Qt.UserRole, str(pdf))
                child.setIcon(0, icon(FILE_ICONS.get(pdf.suffix.lower(), "page"), MUTED, 14))
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked if pdf in unchecked_before else Qt.Checked)
                child.setForeground(1, QColor(FAINT))
                child.setToolTip(0, str(pdf))
            root.setExpanded(True)
        self.input_tree.blockSignals(False)
        self.apply_file_filter(self.txt_filter.text())
        self.update_selection_label()

        self.output_tree.clear()
        if self.output_folder and self.output_folder.exists():
            out_files = sorted(
                p for p in self.output_folder.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
            )
            out_root = QTreeWidgetItem(
                self.output_tree, [f"{len(out_files)} file prodotti", ""]
            )
            out_root.setData(0, Qt.UserRole, str(self.output_folder))
            out_root.setForeground(0, QColor(MUTED))
            for out_pdf in out_files:
                try:
                    size_str = human_size(out_pdf.stat().st_size)
                except OSError:
                    size_str = "n/d"
                child = QTreeWidgetItem(out_root, [out_pdf.name, size_str])
                child.setData(0, Qt.UserRole, str(out_pdf))
                child.setIcon(0, icon(FILE_ICONS.get(out_pdf.suffix.lower(), "page"), MUTED, 14))
                child.setForeground(1, QColor(FAINT))
                child.setToolTip(0, str(out_pdf))
            out_root.setExpanded(True)

        self.preview_widget.search_dirs = [self.input_folder] + [
            p.parent for p in self.input_files
        ]

    def checked_files(self) -> List[Path]:
        files: List[Path] = []
        root = self.input_tree.topLevelItem(0)
        if root is None:
            return files
        for i in range(root.childCount()):
            child = root.child(i)
            if child.checkState(0) == Qt.Checked:
                data = child.data(0, Qt.UserRole)
                if data:
                    files.append(Path(data))
        return files

    def set_all_checked(self, checked: bool):
        root = self.input_tree.topLevelItem(0)
        if root is None:
            return
        state = Qt.Checked if checked else Qt.Unchecked
        self.input_tree.blockSignals(True)
        for i in range(root.childCount()):
            child = root.child(i)
            if not child.isHidden():
                child.setCheckState(0, state)
        self.input_tree.blockSignals(False)
        self.update_selection_label()

    def on_input_item_changed(self, item, column):
        if column == 0:
            self.update_selection_label()

    def update_selection_label(self):
        files = self.checked_files()
        self._unchecked_cache = set(self.input_files) - set(files)
        total = len(self.input_files)
        if total == 0:
            self.lbl_selection.setText("Nessun documento")
        else:
            self.lbl_selection.setText(f"{len(files)} di {total} selezionati")
        # Il pulsante resta sempre premibile: se manca la selezione lo spiega.
        self.btn_start.setEnabled(self.worker is None)
        self.btn_start.setText(
            f"Avvia su {len(files)} documenti" if len(files) > 1
            else ("Avvia su 1 documento" if files else "Avvia anonimizzazione")
        )

    def apply_file_filter(self, text: str):
        needle = (text or "").strip().lower()
        root = self.input_tree.topLevelItem(0)
        if root is None:
            return
        visible = 0
        for i in range(root.childCount()):
            child = root.child(i)
            match = needle in child.text(0).lower()
            child.setHidden(not match)
            visible += int(match)
        root.setText(0, f"{visible} di {len(self.input_files)} documenti" if needle
                     else f"{len(self.input_files)} documenti")

    def show_input_context_menu(self, pos: QPoint):
        item = self.input_tree.itemAt(pos)
        if item is None or item.data(0, Qt.UserRole) is None:
            return
        menu = QMenu(self)
        act_remove = menu.addAction(icon("trash", INK_SOFT, 15), "Rimuovi dall'elenco")
        act_reveal = menu.addAction(icon("external", INK_SOFT, 15), "Mostra nel Finder")
        chosen = menu.exec(self.input_tree.viewport().mapToGlobal(pos))
        if chosen == act_remove:
            selected = self.input_tree.selectedItems() or [item]
            paths = {Path(i.data(0, Qt.UserRole)) for i in selected if i.data(0, Qt.UserRole)}
            self.input_files = [p for p in self.input_files if p not in paths]
            self.refresh_worktrees()
            self.log(f"{len(paths)} file rimossi dall'elenco.")
        elif chosen == act_reveal:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(item.data(0, Qt.UserRole)).parent))
            )

    # ---------------- trascinamento ----------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths: List[Path] = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                paths.extend(sorted(
                    f for f in p.iterdir()
                    if f.is_file() and f.suffix.lower() in SUPPORTED_SUFFIXES
                ))
                self.input_folder = p
            elif p.suffix.lower() in SUPPORTED_SUFFIXES:
                paths.append(p)
        added = self.add_files(paths)
        self.log(f"{added} documenti aggiunti per trascinamento.", "ok" if added else "warn")
        event.acceptProposedAction()

    # ---------------- elenchi ed anteprima ----------------
    def on_lists_changed(self):
        self.sync_preview_settings()

    def sync_preview_settings(self):
        explicit = parse_text_lines(self.txt_custom.toPlainText())
        whitelist = parse_lines_exact(self.txt_whitelist.toPlainText())

        self.preview_widget.update_settings(
            level=MAX_LEVEL,
            explicit=tuple(explicit),
            whitelist=tuple(whitelist),
            keep_labels=self.chk_keep_labels.isChecked(),
            dpi=self.render_dpi,
        )

        # Le stesse impostazioni valgono per i fogli di calcolo; le regole per
        # colonna, riga e cella restano quelle scelte nell'anteprima tabellare.
        self.table_settings.level = MAX_LEVEL
        self.table_settings.explicit = explicit
        self.table_settings.whitelist = whitelist
        self.table_settings.keep_labels = self.chk_keep_labels.isChecked()
        self.table_preview.request_refresh()

    def add_to_blacklist(self, text: str):
        self._add_to_list(text, to_blacklist=True)

    def add_to_whitelist(self, text: str):
        self._add_to_list(text, to_blacklist=False)

    def _add_to_list(self, text: str, to_blacklist: bool):
        if not text:
            return
        text_clean = " ".join(text.split())
        candidate_words = set(text_clean.upper().split())

        blacklist_lines = self.txt_custom.lines()
        whitelist_lines = self.txt_whitelist.lines()
        target_lines = blacklist_lines if to_blacklist else whitelist_lines
        other_lines = whitelist_lines if to_blacklist else blacklist_lines
        target_name = "Rimuovi sempre" if to_blacklist else "Mantieni invariate"
        other_name = "Mantieni invariate" if to_blacklist else "Rimuovi sempre"

        conflicting = [l for l in other_lines if candidate_words & set(l.upper().split())]
        if conflicting:
            conf_str = ", ".join(f'"{c}"' for c in conflicting)
            dialog = ConflictDialog(
                self, "Termine in conflitto",
                f'Il termine <b>{text_clean}</b> condivide parole con voci gia\' presenti in '
                f"<b>{other_name}</b> ({conf_str}).<br><br>Dove vuoi inserirlo?",
                f"Sposta in {target_name}", f"Mantieni in {other_name}",
            )
            dialog.exec()
            if dialog.choice != 1:
                return
            other_lines = [l for l in other_lines if l not in conflicting]
            if to_blacklist:
                self.txt_whitelist.set_lines(other_lines)
            else:
                self.txt_custom.set_lines(other_lines)

        if text_clean in target_lines:
            self.set_status(f'"{text_clean}" e\' gia\' in {target_name}')
            return

        target_lines.append(text_clean)
        widget = self.txt_custom if to_blacklist else self.txt_whitelist
        widget.set_lines(target_lines)
        self.log(f"{target_name} · {text_clean}", "ok")
        animate_widget_flash(widget)
        self.sync_preview_settings()

    def focus_search(self):
        self.preview_widget.toggle_view_mode(True)
        self.preview_widget.txt_search.setFocus()
        self.preview_widget.txt_search.selectAll()

    def on_input_tree_item_clicked(self, item, col):
        path_str = item.data(0, Qt.UserRole)
        if path_str and Path(path_str).is_file():
            if self.open_document(Path(path_str)):
                self.set_status(f"Anteprima · {Path(path_str).name}")

    def on_output_tree_item_clicked(self, item, col):
        path_str = item.data(0, Qt.UserRole)
        if path_str and Path(path_str).is_file():
            if self.open_document(Path(path_str)):
                self.set_status(f"Risultato · {Path(path_str).name}")

    # ---------------- elaborazione ----------------
    def start_anonymization(self):
        if self.worker is not None:
            self.set_status("Elaborazione gia' in corso")
            return

        files = self.checked_files()
        if not files:
            if not self.input_files:
                msg = ("Nessun documento caricato.\n\nUsa i pulsanti Cartella o File in "
                       "alto a sinistra, oppure trascina PDF, CSV o Excel sulla finestra.")
            else:
                msg = ("Nessun documento spuntato.\n\nSpunta almeno un file nell'elenco a "
                       "sinistra oppure premi Tutti.")
            self.log(msg.replace("\n\n", " "), "error")
            self.set_status("Nessun documento da elaborare")
            QMessageBox.information(self, "Nessun documento da elaborare", msg)
            return

        try:
            self.output_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.log(f"Cartella dei risultati non utilizzabile: {exc}", "error")
            QMessageBox.warning(self, "Errore", f"Impossibile creare la cartella:\n{exc}")
            return

        self.btn_start.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.btn_report.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_progress.setVisible(True)
        self._start_time = time.time()
        self.log(
            f"Avvio · {len(files)} documenti", "ok"
        )

        self.worker = AnonymizeWorker(
            file_paths=files,
            output_dir=self.output_folder,
            level=MAX_LEVEL,
            remove_images=self.chk_images.isChecked(),
            custom_text=self.txt_custom.toPlainText(),
            whitelist_text=self.txt_whitelist.toPlainText(),
            fill_color=self.fill_color,
            keep_labels=self.chk_keep_labels.isChecked(),
            sanitize_metadata=self.chk_sanitize.isChecked(),
            verify_output=self.verify_output,
            overwrite=self.overwrite,
            table_settings=self.table_settings,
        )
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.file_done_signal.connect(self.on_file_done)
        self.worker.batch_signal.connect(self.on_batch_ready)
        self.worker.error_signal.connect(lambda m: self.log(f"Errore interno: {m}", "error"))
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def cancel_anonymization(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)
            self.log("Interruzione richiesta: attendo la fine del file corrente...", "warn")

    def on_progress(self, current: int, total: int, filename: str):
        pct = int((current / total) * 100) if total else 0
        self._progress_anim.stop()
        self._progress_anim.setStartValue(self.progress_bar.value())
        self._progress_anim.setEndValue(pct)
        self._progress_anim.start()
        self.lbl_progress.setText(f"{current} di {total} · {filename}")

    def on_file_done(self, res: FileResult):
        if res.error:
            self.log(f"{res.input_path.name} · {res.error}", "error")
            return
        if res.output_path:
            ORIGINS[res.output_path.resolve()] = res.input_path
        self.log(f"{res.input_path.name} · {res.redactions} oscuramenti", "ok")
        for w in res.warnings:
            self.log(f"   {res.input_path.name} · {w}", "warn")

    def on_batch_ready(self, batch: BatchResult):
        self._batch = batch

    def on_finished(self, processed: int, total_redactions: int):
        elapsed = time.time() - self._start_time
        self.progress_bar.setValue(100)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.worker = None
        self.update_selection_label()
        self.refresh_worktrees()

        batch = self._batch or BatchResult()
        msg = f"Completato · {processed} documenti · {total_redactions} oscuramenti · {elapsed:.1f}s"
        if batch.cancelled:
            msg = f"Interrotto dopo {processed} documenti ({total_redactions} oscuramenti)"
        self.log(msg, "warn" if batch.cancelled else "ok")
        if batch.failed:
            self.log(f"{len(batch.failed)} documenti non elaborati: vedi il report.", "error")
        self.set_status(msg)
        self.lbl_progress.setVisible(False)
        QTimer.singleShot(900, lambda: self.progress_bar.setVisible(False))

        if batch.results:
            self.btn_report.setEnabled(True)
            self.show_last_report(elapsed)

    def show_last_report(self, elapsed: Optional[float] = None):
        if not self._batch or not self._batch.results:
            return
        secs = elapsed if isinstance(elapsed, (int, float)) else 0.0
        ReportDialog(self, self._batch, secs, self.output_folder).exec()

    # ---------------- dialoghi ----------------
    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.fill_color = tuple(dlg.cmb_color.currentData())
            self.render_dpi = int(dlg.cmb_dpi.currentData())
            self.overwrite = bool(dlg.cmb_overwrite.currentData())
            self.verify_output = bool(dlg.cmb_verify.currentData())
            self.sync_preview_settings()
            self.save_preferences()
            self.log("Impostazioni aggiornate.", "ok")

    def open_how_it_works(self):
        HowItWorksDialog(self).exec()

    def open_output_folder(self):
        if not self.output_folder.exists():
            try:
                self.output_folder.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.log(f"Impossibile aprire la cartella: {exc}", "error")
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_folder)))

    # ---------------- chiusura ----------------
    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Elaborazione in corso",
                "Un'anonimizzazione e' ancora in corso. Vuoi interromperla ed uscire?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.wait(5000)

        self.save_preferences()
        self.preview_widget.close_document()
        event.accept()

    # ---------------- utilita' ----------------
    def on_table_settings_changed(self):
        self.log("Regole del foglio aggiornate.")


def main():
    app = QApplication(sys.argv)
    # Lo stile nativo di macOS ridisegna i controlli ignorando parte del foglio
    # di stile: Fusion garantisce lo stesso aspetto su tutte le piattaforme.
    app.setStyle("Fusion")
    load_brand_font()
    app.setFont(QFont("Albert Sans", 13))
    app.setWindowIcon(app_icon())
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    window = ClinMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
