"""
Clin - Anteprima interattiva dei fogli di calcolo.

Mostra il contenuto di un CSV/XLSX evidenziando le celle che verranno
anonimizzate e permette di decidere il trattamento per colonna, per riga o per
singola cella. La vista "Risultato" mostra il file gia' anonimizzato.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMenu, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from anonymize_engine import CATEGORY_COLORS
from tabular_engine import (
    MODE_ALL, MODE_AUTO, MODE_KEEP, MODE_LABELS, MODE_PSEUDO, CellPlan, Sheet,
    TableDoc, TableSettings, load_table, plan_sheet,
)
from ui_kit import (
    ACCENT, ACCENT_LINE, ACCENT_SOFT, BORDER, FAINT, HAIRLINE, INK, INK_SOFT,
    MUTED, R_MD, R_SM, SURFACE, SURFACE_ALT, SURFACE_SUNK, WARNING,
    Segmented, icon, make_button,
)

PREVIEW_ROWS = 400          # righe caricate per l'anteprima
MODE_BADGE = {
    MODE_AUTO: "",
    MODE_ALL: "oscura tutto",
    MODE_PSEUDO: "pseudonimo",
    MODE_KEEP: "non toccare",
}


def _tint(rgb: Tuple[int, int, int], amount: float = 0.20) -> QColor:
    """Versione chiara del colore di categoria, adatta come sfondo di cella."""
    r, g, b = rgb
    return QColor(
        int(255 + (r - 255) * amount),
        int(255 + (g - 255) * amount),
        int(255 + (b - 255) * amount),
    )


class TablePreviewWidget(QWidget):
    """Tabella con evidenziazione delle celle da anonimizzare."""

    add_to_blacklist_signal = Signal(str)
    add_to_whitelist_signal = Signal(str)
    status_signal = Signal(str)
    settings_changed = Signal()

    def __init__(self, settings: TableSettings):
        super().__init__()
        self.settings = settings
        self.doc: Optional[TableDoc] = None
        self.sheet: Optional[Sheet] = None
        self.plans: Dict[Tuple[int, int], CellPlan] = {}
        self.show_result = False

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(160)
        self._refresh_timer.timeout.connect(self.recompute)

        self.init_ui()

    # ---------------- costruzione ----------------
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.cmb_sheet = QComboBox()
        self.cmb_sheet.setMinimumWidth(150)
        self.cmb_sheet.currentTextChanged.connect(self.on_sheet_changed)
        self.cmb_sheet.setVisible(False)

        self.lbl_dims = QLabel("—")
        self.lbl_dims.setStyleSheet(f"color: {FAINT}; font-size: 12px;")

        self.seg_rows = Segmented([("Tutte le righe", None), ("Solo selezionate", None)], 0)
        self.seg_rows.changed.connect(self.on_row_scope_changed)

        self.btn_reset = make_button("", "eraser", "icon", "Azzera le regole di questo foglio")
        self.btn_reset.clicked.connect(self.reset_rules)

        self.seg_mode = Segmented([("Originale", None), ("Risultato", "eye")], 0)
        self.seg_mode.changed.connect(self.on_view_changed)

        bar.addWidget(self.cmb_sheet)
        bar.addWidget(self.lbl_dims)
        bar.addStretch()
        bar.addWidget(self.seg_rows)
        bar.addWidget(self.btn_reset)
        bar.addWidget(self.seg_mode)
        layout.addLayout(bar)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_cell_menu)
        self.table.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self.show_column_menu)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {SURFACE}; border: 1px solid {HAIRLINE};
                border-radius: {R_MD}px; gridline-color: {HAIRLINE};
                font-size: 12px; color: {INK_SOFT};
                selection-background-color: {ACCENT_SOFT}; selection-color: {INK};
            }}
            QTableWidget::item {{ padding: 3px 6px; }}
            QHeaderView::section {{
                background-color: {SURFACE_ALT}; color: {MUTED};
                border: none; border-right: 1px solid {HAIRLINE};
                border-bottom: 1px solid {HAIRLINE};
                padding: 6px 8px; font-size: 11px; font-weight: 600;
            }}
            QHeaderView::section:hover {{ background-color: {SURFACE_SUNK}; color: {INK}; }}
            QTableCornerButton::section {{
                background-color: {SURFACE_ALT}; border: none;
                border-bottom: 1px solid {HAIRLINE};
            }}
        """)
        layout.addWidget(self.table, 1)

        legend = QFrame()
        legend.setObjectName("tlegend")
        legend.setStyleSheet(
            f"QFrame#tlegend {{ background-color: {SURFACE_ALT}; border: 1px solid {HAIRLINE};"
            f" border-radius: {R_MD}px; }}"
        )
        legend_layout = QHBoxLayout(legend)
        legend_layout.setContentsMargins(12, 9, 12, 9)
        legend_layout.setSpacing(10)
        self.lbl_count = QLabel("—")
        self.lbl_count.setStyleSheet(f"color: {MUTED}; font-size: 12px; font-weight: 500;")
        self.lbl_chips = QLabel("")
        self.lbl_chips.setWordWrap(True)
        self.lbl_chips.setTextFormat(Qt.RichText)
        self.lbl_chips.setStyleSheet(f"color: {FAINT}; font-size: 11.5px;")
        legend_layout.addWidget(self.lbl_count)
        legend_layout.addWidget(self.lbl_chips, 1)
        layout.addWidget(legend)

    # ---------------- caricamento ----------------
    def load_file(self, path: Path) -> bool:
        try:
            self.doc = load_table(path, max_rows=PREVIEW_ROWS)
        except Exception as exc:
            self.doc = None
            self.sheet = None
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.lbl_dims.setText("Impossibile leggere il file")
            self.status_signal.emit(f"Errore lettura {path.name}: {exc}")
            return False

        self.cmb_sheet.blockSignals(True)
        self.cmb_sheet.clear()
        self.cmb_sheet.addItems([s.name for s in self.doc.sheets])
        self.cmb_sheet.setVisible(len(self.doc.sheets) > 1)
        self.cmb_sheet.blockSignals(False)

        self.sheet = self.doc.sheets[0] if self.doc.sheets else None
        self.sync_row_scope()
        self.recompute()
        return True

    def has_document(self) -> bool:
        return self.sheet is not None

    def on_sheet_changed(self, name: str):
        if self.doc:
            self.sheet = self.doc.sheet(name)
            self.sync_row_scope()
            self.recompute()

    def request_refresh(self):
        if self.sheet is not None:
            self._refresh_timer.start()

    # ---------------- calcolo e disegno ----------------
    def recompute(self):
        if self.sheet is None:
            return
        try:
            self.plans = plan_sheet(self.sheet, self.settings, max_rows=PREVIEW_ROWS)
        except Exception:
            self.plans = {}
        self.populate()
        self.update_legend()

    def populate(self):
        sheet = self.sheet
        if sheet is None:
            return
        header = sheet.header(self.settings.has_header)
        first_row = 1 if self.settings.has_header else 0
        data_rows = sheet.rows[first_row:]

        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(max(len(header), sheet.column_count))
        self.table.setRowCount(len(data_rows))
        self.table.setHorizontalHeaderLabels(
            [self._header_label(i, header) for i in range(self.table.columnCount())]
        )
        self.table.setVerticalHeaderLabels(
            [str(first_row + i + 1) for i in range(len(data_rows))]
        )

        selected_rows = self.settings.rows_for(sheet.name)
        for view_row, row in enumerate(data_rows):
            model_row = view_row + first_row
            row_active = selected_rows is None or model_row in selected_rows
            for col in range(self.table.columnCount()):
                value = row[col] if col < len(row) else ""
                plan = self.plans.get((model_row, col))
                text = plan.new_value if (plan and self.show_result) else value
                item = QTableWidgetItem(text)
                item.setToolTip(self._cell_tooltip(value, plan))
                if plan:
                    color = CATEGORY_COLORS.get(plan.category, (201, 100, 66))
                    item.setBackground(QBrush(_tint(color)))
                    item.setForeground(QBrush(QColor(INK)))
                elif not row_active:
                    item.setForeground(QBrush(QColor(FAINT)))
                self.table.setItem(view_row, col, item)

        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        for col in range(self.table.columnCount()):
            if self.table.columnWidth(col) > 260:
                self.table.setColumnWidth(col, 260)

        note = f"{sheet.total_rows} righe · {sheet.column_count} colonne"
        if sheet.truncated:
            note += f" · anteprima delle prime {PREVIEW_ROWS}"
        self.lbl_dims.setText(note)

    def _header_label(self, col: int, header: List[str]) -> str:
        name = header[col] if col < len(header) and header[col] else f"Colonna {col + 1}"
        mode = self.settings.column_mode(self.sheet.name, col) if self.sheet else MODE_AUTO
        badge = MODE_BADGE.get(mode, "")
        return f"{name}\n{badge}" if badge else name

    def _cell_tooltip(self, value: str, plan: Optional[CellPlan]) -> str:
        if plan is None:
            return value
        if self.show_result:
            return f"Originale: {value}\nCategoria: {plan.category}"
        return f"Diventera': {plan.new_value}\nCategoria: {plan.category}"

    def update_legend(self):
        if self.sheet is None:
            self.lbl_count.setText("—")
            self.lbl_chips.setText("")
            return
        if not self.plans:
            self.lbl_count.setText("Nessun rilevamento")
            self.lbl_count.setStyleSheet(f"color: {MUTED}; font-size: 12px; font-weight: 500;")
            self.lbl_chips.setText(
                "Nessuna cella verra' modificata. Alza la sensibilita' oppure imposta una "
                "regola sulle colonne (clic sull'intestazione)."
            )
            return

        by_cat: Dict[str, int] = {}
        for plan in self.plans.values():
            by_cat[plan.category] = by_cat.get(plan.category, 0) + 1
        chips = " &nbsp; ".join(
            f"<span style='color:rgb{CATEGORY_COLORS.get(c, (201, 100, 66))}'>&#9679;</span>"
            f"&nbsp;{c} <span style='color:{FAINT}'>{n}</span>"
            for c, n in sorted(by_cat.items(), key=lambda kv: -kv[1])
        )
        self.lbl_count.setStyleSheet(f"color: {INK}; font-size: 12px; font-weight: 600;")
        self.lbl_count.setText(f"{len(self.plans)} celle da anonimizzare")
        self.lbl_chips.setText(chips)

    # ---------------- interazione ----------------
    def _model_row(self, view_row: int) -> int:
        return view_row + (1 if self.settings.has_header else 0)

    def on_view_changed(self, index: int):
        self.show_result = index == 1
        self.populate()

    def on_row_scope_changed(self, index: int):
        if self.sheet is None:
            return
        if index == 0:
            self.settings.set_rows(self.sheet.name, None)
            self.status_signal.emit("Anonimizzazione su tutte le righe")
        else:
            rows = {self._model_row(i.row()) for i in self.table.selectedIndexes()}
            if not rows:
                self.seg_rows.set_current(0, emit=False)
                self.status_signal.emit(
                    "Seleziona prima le righe nella tabella, poi scegli 'Solo selezionate'"
                )
                return
            self.settings.set_rows(self.sheet.name, rows)
            self.status_signal.emit(f"Anonimizzazione limitata a {len(rows)} righe")
        self.recompute()
        self.settings_changed.emit()

    def sync_row_scope(self):
        if self.sheet is None:
            return
        active = self.settings.rows_for(self.sheet.name) is not None
        self.seg_rows.set_current(1 if active else 0, emit=False)

    def reset_rules(self):
        if self.sheet is None:
            return
        self.settings.reset_sheet(self.sheet.name)
        self.sync_row_scope()
        self.recompute()
        self.settings_changed.emit()
        self.status_signal.emit("Regole del foglio azzerate")

    def on_header_clicked(self, col: int):
        header = self.table.horizontalHeader()
        pos = QPoint(header.sectionViewportPosition(col) + 12, header.height())
        self.show_column_menu(pos, col)

    def show_column_menu(self, pos: QPoint, col: Optional[int] = None):
        if self.sheet is None:
            return
        header = self.table.horizontalHeader()
        if col is None:
            col = header.logicalIndexAt(pos)
        if col < 0:
            return

        names = self.sheet.header(self.settings.has_header)
        title = names[col] if col < len(names) else f"Colonna {col + 1}"
        current = self.settings.column_mode(self.sheet.name, col)

        menu = QMenu(self)
        head = menu.addAction(f"Colonna: {title}")
        head.setEnabled(False)
        menu.addSeparator()
        actions = {}
        for mode in (MODE_AUTO, MODE_ALL, MODE_PSEUDO, MODE_KEEP):
            act = menu.addAction(MODE_LABELS[mode])
            act.setCheckable(True)
            act.setChecked(mode == current)
            actions[act] = mode
        menu.addSeparator()
        act_all_auto = menu.addAction("Reimposta tutte le colonne su Automatico")

        chosen = menu.exec(header.mapToGlobal(pos))
        if chosen in actions:
            self.settings.set_column_mode(self.sheet.name, col, actions[chosen])
            self.status_signal.emit(f"{title} · {MODE_LABELS[actions[chosen]]}")
        elif chosen == act_all_auto:
            self.settings.column_modes.pop(self.sheet.name, None)
            self.status_signal.emit("Tutte le colonne su Automatico")
        else:
            return
        self.recompute()
        self.settings_changed.emit()

    def show_cell_menu(self, pos: QPoint):
        if self.sheet is None:
            return
        item = self.table.itemAt(pos)
        if item is None:
            return
        view_row, col = item.row(), item.column()
        model_row = self._model_row(view_row)
        raw = self.sheet.rows[model_row][col] if col < len(self.sheet.rows[model_row]) else ""
        selected_rows = {self._model_row(i.row()) for i in self.table.selectedIndexes()}

        menu = QMenu(self)
        shown = raw if len(raw) <= 44 else raw[:41] + "..."
        head = menu.addAction(f'"{shown}"')
        head.setEnabled(False)
        menu.addSeparator()

        act_black = menu.addAction(icon("eraser", INK_SOFT, 15), "Rimuovi sempre questo valore")
        act_white = menu.addAction(icon("shield", INK_SOFT, 15), "Mantieni invariato")
        menu.addSeparator()

        cell_actions = {}
        current_cell = self.settings.cell_mode(self.sheet.name, model_row, col)
        for mode in (MODE_ALL, MODE_PSEUDO, MODE_KEEP):
            act = menu.addAction(f"Questa cella · {MODE_LABELS[mode]}")
            act.setCheckable(True)
            act.setChecked(current_cell == mode)
            cell_actions[act] = mode
        act_cell_reset = menu.addAction("Questa cella · segui la colonna")
        menu.addSeparator()

        act_rows = menu.addAction(f"Limita alle {len(selected_rows)} righe selezionate")
        act_rows.setEnabled(bool(selected_rows))
        act_rows_all = menu.addAction("Estendi a tutte le righe")
        menu.addSeparator()
        act_copy = menu.addAction("Copia valore")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == act_black:
            self.add_to_blacklist_signal.emit(raw)
            return
        if chosen == act_white:
            self.add_to_whitelist_signal.emit(raw)
            return
        if chosen == act_copy:
            QApplication.clipboard().setText(raw)
            return
        if chosen in cell_actions:
            self.settings.set_cell_mode(self.sheet.name, model_row, col, cell_actions[chosen])
        elif chosen == act_cell_reset:
            self.settings.set_cell_mode(self.sheet.name, model_row, col, None)
        elif chosen == act_rows:
            self.settings.set_rows(self.sheet.name, selected_rows)
            self.sync_row_scope()
        elif chosen == act_rows_all:
            self.settings.set_rows(self.sheet.name, None)
            self.sync_row_scope()
        else:
            return

        self.recompute()
        self.settings_changed.emit()
