"""
Clin - Sistema di design dell'interfaccia.

Raccoglie palette, tipografia, icone vettoriali e componenti riutilizzabili,
in modo che `clin_gui` si occupi solo della logica applicativa.

Impostazione visiva: superfici chiare su fondo caldo neutro, bordi a filo di
capello invece di ombre, angoli ampi, spaziature su griglia da 8 px, icone a
tratto e micro-animazioni brevi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

# --------------------------------------------------------------------------
# Palette (Gold Label, vedi STILE.md)
# --------------------------------------------------------------------------
CANVAS = "#ffffff"        # fondo di pagina
SURFACE = "#ffffff"       # controlli, menu, dialoghi
SOFT = "#f3f4f1"          # card e pannelli (superfici, non bordi)
SURFACE_ALT = "#ffffff"   # campi di testo sopra le card Soft
SURFACE_SUNK = "#e9ebe6"  # hover, tracce, aree incassate (Soft 2)

INK = "#101411"           # testo principale
INK_SOFT = "#101411"      # etichette dei controlli
MUTED = "#6a706b"         # testo secondario (Ink 2)
FAINT = "#9ba19c"         # testo terziario (Ink 3)

HAIRLINE = "#e4e6e1"      # filetti (Line)
BORDER = "#dcdfd8"        # bordi dei campi

ACCENT = "#d4f06b"        # Lime: un solo elemento in evidenza per schermata
ACCENT_HOVER = "#c6e555"  # Lime 2
ACCENT_PRESS = "#b8d84a"
ACCENT_SOFT = "#eef7cc"   # selezioni
ACCENT_LINE = "#d9ec95"
ACCENT_INK = "#3c7a4b"    # Forest 2: icone, link e fuochi in colore d'accento

FOREST = "#173d26"
FOREST_2 = "#3c7a4b"

SUCCESS = "#3c7a4b"
SUCCESS_SOFT = "#e7f0e8"
WARNING = "#b8640a"
WARNING_SOFT = "#f8ecdd"
DANGER = "#c8312f"
DANGER_SOFT = "#f9e7e6"

# Raggi e spaziature (STILE.md par. 4)
R_SM, R_MD, R_LG, R_PILL = 10, 14, 20, 999
FONT_FAMILY = "Albert Sans"
FONT_STACK = f'"{FONT_FAMILY}", -apple-system, "Helvetica Neue", Arial, sans-serif'
MONO_STACK = '"SF Mono", "JetBrains Mono", Menlo, Monaco, Consolas, monospace'

ASSETS = Path(__file__).resolve().parent / "assets"


def load_brand_font() -> None:
    """Registra Albert Sans dalla cartella assets (fallback: font di sistema)."""
    from PySide6.QtGui import QFontDatabase
    font_file = ASSETS / "AlbertSans.woff2"
    if font_file.exists():
        QFontDatabase.addApplicationFont(str(font_file))


def app_icon() -> QIcon:
    """Icona dell'applicazione, dal logo vettoriale."""
    svg = ASSETS / "logo.svg"
    if not svg.exists():
        return QIcon()
    renderer = QSvgRenderer(str(svg))
    out = QIcon()
    for size in (16, 32, 64, 128, 256, 512):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        out.addPixmap(pix)
    return out


# --------------------------------------------------------------------------
# Icone vettoriali (tratto, 24x24, stile lineare)
# --------------------------------------------------------------------------
_ICONS: Dict[str, str] = {
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "file-plus": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
                 '<path d="M14 3v5h5"/><path d="M12 12v5"/><path d="M9.5 14.5h5"/>',
    "trash": '<path d="M4 7h16"/><path d="M18 7v12a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V7"/>'
             '<path d="M9.5 7V5.5A1.5 1.5 0 0 1 11 4h2a1.5 1.5 0 0 1 1.5 1.5V7"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/>',
    "play": '<path d="M7 5.5v13l11-6.5z"/>',
    "stop": '<rect x="7" y="7" width="10" height="10" rx="2"/>',
    "settings": '<path d="M4 20v-6"/><path d="M4 10V4"/><path d="M12 20v-9"/><path d="M12 7V4"/>'
                '<path d="M20 20v-4"/><path d="M20 12V4"/><path d="M2 14h4"/><path d="M10 7h4"/>'
                '<path d="M18 16h4"/>',
    "help": '<circle cx="12" cy="12" r="8.5"/><path d="M9.8 9.5a2.3 2.3 0 1 1 3 2.2c-.6.3-.9.8-.9 1.5v.4"/>'
            '<path d="M12 16.8h.01"/>',
    "shield": '<path d="M12 3.5l7 2.6v5.2c0 4.3-2.9 7.6-7 9.2-4.1-1.6-7-4.9-7-9.2V6.1z"/>'
              '<path d="M9 12.2l2.1 2.1 4-4.2"/>',
    "chevron-left": '<path d="M14.5 6.5L9 12l5.5 5.5"/>',
    "chevron-right": '<path d="M9.5 6.5L15 12l-5.5 5.5"/>',
    "zoom-in": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/><path d="M11 8.5v5"/><path d="M8.5 11h5"/>',
    "zoom-out": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/><path d="M8.5 11h5"/>',
    "maximize": '<path d="M4 9V5.5A1.5 1.5 0 0 1 5.5 4H9"/><path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5V9"/>'
                '<path d="M20 15v3.5a1.5 1.5 0 0 1-1.5 1.5H15"/><path d="M9 20H5.5A1.5 1.5 0 0 1 4 18.5V15"/>',
    "eye": '<path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12z"/>'
           '<circle cx="12" cy="12" r="2.8"/>',
    "eye-off": '<path d="M4 4l16 16"/><path d="M9.9 5.9A9.6 9.6 0 0 1 12 5.8c6 0 9.5 6.2 9.5 6.2a17 17 0 0 1-3.4 4"/>'
               '<path d="M6.4 7.9A16.8 16.8 0 0 0 2.5 12S6 18.2 12 18.2a9.7 9.7 0 0 0 3.7-.7"/>',
    "text": '<path d="M5 6h14"/><path d="M9 6v13"/><path d="M15 12h4"/><path d="M15 17h4"/>',
    "page": '<rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M8.5 8.5h7"/>'
            '<path d="M8.5 12h7"/><path d="M8.5 15.5h4"/>',
    "download": '<path d="M12 4v10"/><path d="M8 10.5l4 4 4-4"/><path d="M5 19h14"/>',
    "external": '<path d="M14 5h5v5"/><path d="M19 5l-7.5 7.5"/>'
                '<path d="M18 14v4.5A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "check-all": '<path d="M3 12.5l4 4 8-8"/><path d="M11 16.5l1.5 1.5 8.5-8.5"/>',
    "square": '<rect x="5" y="5" width="14" height="14" rx="3"/>',
    "alert": '<path d="M12 4.5l8.5 15h-17z"/><path d="M12 10v4"/><path d="M12 16.8h.01"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5"/><path d="M12 8.2h.01"/>',
    "sparkle": '<path d="M12 4l1.8 4.7L18.5 10l-4.7 1.8L12 16.5l-1.8-4.7L5.5 10l4.7-1.3z"/>',
    "eraser": '<path d="M8 20h11"/><path d="M15.5 4.5l4 4a1.6 1.6 0 0 1 0 2.3l-7.4 7.4a1.6 1.6 0 0 1-2.3 0l-4-4a1.6 1.6 0 0 1 0-2.3l7.4-7.4a1.6 1.6 0 0 1 2.3 0z"/>',
    "list": '<path d="M8 7h12"/><path d="M8 12h12"/><path d="M8 17h12"/><path d="M4 7h.01"/>'
            '<path d="M4 12h.01"/><path d="M4 17h.01"/>',
}

_icon_cache: Dict[Tuple[str, str, int], QIcon] = {}
_asset_cache: Dict[Tuple[str, str, int], str] = {}


def icon_asset(name: str, color: str = "#ffffff", size: int = 12) -> str:
    """
    Salva un'icona come PNG temporaneo e ne restituisce il percorso.

    Serve ai fogli di stile Qt, che accettano `image: url(...)` solo con un
    percorso su disco (per esempio per il segno di spunta delle caselle).
    """
    key = (name, color, size)
    if key in _asset_cache:
        return _asset_cache[key]
    import tempfile

    folder = Path(tempfile.gettempdir()) / "clin_ui"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}_{color.lstrip('#')}_{size}.png"
    if not path.exists():
        icon(name, color, size, width=2.4).pixmap(size, size).save(str(path))
    _asset_cache[key] = path.as_posix()
    return _asset_cache[key]


def icon(name: str, color: str = INK_SOFT, size: int = 18, width: float = 1.6) -> QIcon:
    """Restituisce un'icona a tratto, generata da SVG e memorizzata in cache."""
    key = (name, color, size)
    if key in _icon_cache:
        return _icon_cache[key]
    body = _ICONS.get(name, _ICONS["square"])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    ).encode("utf-8")

    renderer = QSvgRenderer(svg)
    ratio = 2  # nitidezza su schermi ad alta densita'
    pix = QPixmap(size * ratio, size * ratio)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * ratio, size * ratio))
    painter.end()
    pix.setDevicePixelRatio(ratio)
    result = QIcon(pix)
    _icon_cache[key] = result
    return result


# --------------------------------------------------------------------------
# Stili dei pulsanti
# --------------------------------------------------------------------------
# Nota: i pulsanti colorati ricevono il foglio di stile direttamente, perche'
# le regole ereditate dalla finestra non riescono a dipingerne lo sfondo.
BTN_PRIMARY = f"""
    QPushButton {{
        background-color: {ACCENT}; color: {INK}; border: none;
        border-radius: 21px; padding: 0 22px; min-height: 42px;
        font-size: 14px; font-weight: 500; text-align: center;
    }}
    QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
    QPushButton:pressed {{ background-color: {ACCENT_PRESS}; }}
    QPushButton:disabled {{ background-color: {SURFACE_SUNK}; color: {FAINT}; }}
"""

BTN_SECONDARY = f"""
    QPushButton {{
        background-color: {SURFACE}; color: {INK}; border: 1px solid {HAIRLINE};
        border-radius: 16px; padding: 7px 15px; font-size: 13px; font-weight: 500;
    }}
    QPushButton:hover {{ background-color: {SURFACE_SUNK}; border-color: {SURFACE_SUNK}; }}
    QPushButton:pressed {{ background-color: {BORDER}; }}
    QPushButton:disabled {{ color: {FAINT}; background-color: {SOFT}; }}
"""

BTN_DARK = f"""
    QPushButton {{
        background-color: {INK}; color: #ffffff; border: none;
        border-radius: 16px; padding: 7px 16px; font-size: 13px; font-weight: 500;
    }}
    QPushButton:hover {{ background-color: #2a302b; }}
    QPushButton:disabled {{ background-color: {SURFACE_SUNK}; color: {FAINT}; }}
"""

BTN_GHOST = f"""
    QPushButton {{
        background-color: transparent; color: {MUTED}; border: none;
        border-radius: 15px; padding: 6px 13px; font-size: 13px; font-weight: 500;
    }}
    QPushButton:hover {{ background-color: {SOFT}; color: {INK}; }}
    QPushButton:pressed {{ background-color: {SURFACE_SUNK}; }}
    QPushButton:disabled {{ color: {FAINT}; }}
"""

BTN_DANGER = f"""
    QPushButton {{
        background-color: {DANGER_SOFT}; color: {DANGER}; border: none;
        border-radius: 16px; padding: 7px 15px; font-size: 13px; font-weight: 500;
    }}
    QPushButton:hover {{ background-color: #f3d6d4; }}
"""

BTN_ICON = f"""
    QPushButton {{
        background-color: transparent; border: none;
        border-radius: 14px; padding: 5px;
    }}
    QPushButton:hover {{ background-color: {SURFACE_SUNK}; }}
    QPushButton:pressed {{ background-color: {BORDER}; }}
    QPushButton:checked {{ background-color: {ACCENT_SOFT}; }}
    QPushButton:disabled {{ background-color: transparent; }}
"""


def make_button(
    text: str = "",
    icon_name: Optional[str] = None,
    kind: str = "secondary",
    tooltip: str = "",
    icon_color: Optional[str] = None,
    icon_size: int = 16,
) -> QPushButton:
    """Costruisce un pulsante coerente con il sistema di design."""
    styles = {
        "primary": BTN_PRIMARY, "secondary": BTN_SECONDARY, "dark": BTN_DARK,
        "ghost": BTN_GHOST, "danger": BTN_DANGER, "icon": BTN_ICON,
    }
    btn = QPushButton(text)
    btn.setStyleSheet(styles.get(kind, BTN_SECONDARY))
    btn.setCursor(Qt.PointingHandCursor)
    if tooltip:
        btn.setToolTip(tooltip)
    if icon_name:
        default_color = {
            "primary": INK, "dark": "#ffffff", "danger": DANGER, "icon": MUTED,
        }.get(kind, INK_SOFT)
        btn.setIcon(icon(icon_name, icon_color or default_color, icon_size))
        btn.setIconSize(QSize(icon_size, icon_size))
    if kind == "icon":
        btn.setFixedSize(30, 28)
    if kind == "primary":
        btn.setMinimumHeight(42)
    return btn


# --------------------------------------------------------------------------
# Contenitori
# --------------------------------------------------------------------------
class Panel(QFrame):
    """Card Soft senza bordo, raggio 20 (STILE.md: superfici, non bordi)."""

    def __init__(self, padding: int = 22, spacing: int = 12):
        super().__init__()
        self.setObjectName("panel")
        self.setStyleSheet(
            f"QFrame#panel {{ background-color: {SOFT}; border: none;"
            f" border-radius: {R_LG}px; }}"
        )
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)

    def add_header(self, title: str, icon_name: Optional[str] = None, hint: str = "") -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        # Etichetta di sezione: "// TITOLO", senza icone decorative (STILE.md par. 3 e 9).
        label = QLabel(f'<span style="color:{FAINT}">//</span> {title.upper()}')
        label.setTextFormat(Qt.RichText)
        label.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; font-weight: 500; letter-spacing: 0.8px;"
        )
        row.addWidget(label)
        if hint:
            tip = QLabel(hint)
            tip.setStyleSheet(f"color: {FAINT}; font-size: 12px;")
            row.addWidget(tip)
        row.addStretch()
        self.body.addLayout(row)
        return row


def hairline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {HAIRLINE}; border: none;")
    return line


def caption(text: str, color: str = FAINT, size: float = 11.5) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color: {color}; font-size: {size}px;")
    return lbl


def pill(text: str, fg: str = INK, bg: str = SOFT, border: str = "transparent") -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {fg}; background-color: {bg}; border: none;"
        f" border-radius: 11px; padding: 4px 11px; font-size: 12px; font-weight: 500;"
    )
    return lbl


# --------------------------------------------------------------------------
# Interruttore animato
# --------------------------------------------------------------------------
class Switch(QWidget):
    """Interruttore con pallino scorrevole, animato."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False):
        super().__init__()
        self._checked = checked
        self._offset = 1.0 if checked else 0.0
        self.setFixedSize(40, 23)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(190)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float):
        self._offset = value
        self.update()

    offset = Property(float, get_offset, set_offset)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True, emit: bool = True):
        changed = checked != self._checked
        self._checked = checked
        target = 1.0 if checked else 0.0
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._offset)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self.set_offset(target)
        if changed and emit:
            self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track_off, track_on = QColor(BORDER), QColor(FOREST_2)
        t = self._offset
        track = QColor(
            int(track_off.red() + (track_on.red() - track_off.red()) * t),
            int(track_off.green() + (track_on.green() - track_off.green()) * t),
            int(track_off.blue() + (track_on.blue() - track_off.blue()) * t),
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()),
                                self.height() / 2, self.height() / 2)
        knob_d = self.height() - 6
        x = 3 + t * (self.width() - knob_d - 6)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(x, 3, knob_d, knob_d))
        painter.end()


class ToggleRow(QWidget):
    """Riga con etichetta, descrizione opzionale ed interruttore."""

    toggled = Signal(bool)

    def __init__(self, label_text: str, default_state: bool = True,
                 description: str = "", tooltip: str = ""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(12)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.lbl = QLabel(label_text)
        self.lbl.setWordWrap(True)
        self.lbl.setStyleSheet(f"color: {INK}; font-size: 13px; font-weight: 500;")
        texts.addWidget(self.lbl)
        if description:
            texts.addWidget(caption(description, MUTED, 12))

        self.switch = Switch(default_state)
        self.switch.toggled.connect(self.toggled.emit)

        layout.addLayout(texts, 1)
        layout.addWidget(self.switch, 0, Qt.AlignVCenter)
        if tooltip:
            self.setToolTip(tooltip)

    # API compatibile con il vecchio ToggleSwitch
    def isChecked(self) -> bool:
        return self.switch.isChecked()

    def set_checked(self, checked: bool, emit: bool = True):
        self.switch.setChecked(checked, animate=False, emit=emit)

    setChecked = set_checked


# --------------------------------------------------------------------------
# Controllo segmentato
# --------------------------------------------------------------------------
class Segmented(QWidget):
    """Selettore a segmenti, in stile barra di controllo moderna."""

    changed = Signal(int)

    def __init__(self, options: List[Tuple[str, Optional[str]]], current: int = 0):
        super().__init__()
        self._buttons: List[QPushButton] = []
        self._icons: List[Optional[str]] = [ic for _, ic in options]
        self._current = current

        frame = QFrame()
        frame.setObjectName("segFrame")
        frame.setStyleSheet(
            f"QFrame#segFrame {{ background-color: {SURFACE_SUNK}; border: none;"
            f" border-radius: 17px; }}"
        )
        inner = QHBoxLayout(frame)
        inner.setContentsMargins(3, 3, 3, 3)
        inner.setSpacing(3)

        for idx, (label, icon_name) in enumerate(options):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            if icon_name:
                btn.setIcon(icon(icon_name, MUTED, 14))
                btn.setIconSize(QSize(14, 14))
            btn.clicked.connect(lambda _=False, i=idx: self.set_current(i))
            self._buttons.append(btn)
            inner.addWidget(btn)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        self._refresh()

    def current(self) -> int:
        return self._current

    def set_current(self, index: int, emit: bool = True):
        if index == self._current:
            self._refresh()
            return
        self._current = index
        self._refresh()
        if emit:
            self.changed.emit(index)

    def _refresh(self):
        for i, btn in enumerate(self._buttons):
            active = i == self._current
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {SURFACE}; color: {INK};"
                    f" border: none; border-radius: 14px;"
                    f" padding: 6px 13px; font-size: 12.5px; font-weight: 500; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: transparent; color: {MUTED};"
                    f" border: none; border-radius: 14px;"
                    f" padding: 6px 13px; font-size: 12.5px; font-weight: 500; }}"
                    f"QPushButton:hover {{ color: {INK}; }}"
                )
            name = self._icons[i]
            if name:
                btn.setIcon(icon(name, INK if active else MUTED, 14))


# --------------------------------------------------------------------------
# Animazioni
# --------------------------------------------------------------------------
def fade_in(widget: QWidget, duration: int = 170, start: float = 0.25) -> None:
    """Breve dissolvenza in entrata, usata al cambio pagina dell'anteprima."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    widget._fade_anim = anim


def app_stylesheet() -> str:
    """Foglio di stile globale dell'applicazione."""
    return f"""
        * {{ font-family: {FONT_STACK}; }}
        QMainWindow, QDialog {{ background-color: {CANVAS}; }}
        QWidget#transparent {{ background-color: transparent; }}

        QLabel {{ color: {INK}; font-size: 13px; }}

        QLineEdit {{
            background-color: {SURFACE_ALT}; border: 1px solid {BORDER};
            border-radius: {R_SM}px; padding: 8px 12px; font-size: 13px; color: {INK};
            selection-background-color: {ACCENT_SOFT}; selection-color: {INK};
        }}
        QLineEdit:focus {{ border: 1px solid {ACCENT_INK}; background-color: {SURFACE}; }}
        QLineEdit::placeholder {{ color: {FAINT}; }}

        QTextEdit {{
            background-color: {SURFACE_ALT}; border: 1px solid {BORDER};
            border-radius: {R_SM + 2}px; padding: 8px 10px; font-size: 13px; color: {INK};
            selection-background-color: {ACCENT_SOFT}; selection-color: {INK};
        }}
        QTextEdit:focus {{ border: 1px solid {ACCENT_INK}; background-color: {SURFACE}; }}

        QTreeWidget {{
            background-color: transparent; border: none; outline: none;
            font-size: 12.5px; color: {INK_SOFT};
            alternate-background-color: transparent; show-decoration-selected: 0;
        }}
        QTreeWidget::item {{
            padding: 6px 4px; border-radius: 0; min-height: 22px;
        }}
        QTreeWidget::item:hover {{ background-color: {SURFACE_ALT}; }}
        QTreeWidget::item:selected {{
            background-color: {ACCENT_SOFT}; color: {INK}; font-weight: 500;
        }}
        QTreeWidget::indicator {{
            width: 15px; height: 15px; border: 1.4px solid {BORDER};
            border-radius: 5px; background-color: {SURFACE};
        }}
        QTreeWidget::indicator:hover {{ border-color: {INK}; }}
        QTreeWidget::indicator:checked {{
            background-color: {ACCENT}; border-color: {ACCENT_HOVER};
            image: url("{icon_asset('check', INK, 11)}");
        }}
        QTreeWidget::indicator:indeterminate {{
            background-color: {ACCENT_SOFT}; border-color: {ACCENT_HOVER};
            image: url("{icon_asset('check', FOREST_2, 11)}");
        }}
        QTreeWidget::branch {{ background: transparent; }}
        QTreeWidget::branch:selected {{ background: transparent; }}
        QHeaderView::section {{
            background-color: transparent; color: {FAINT}; border: none;
            border-bottom: 1px solid {HAIRLINE}; padding: 4px 6px;
            font-size: 11px; font-weight: 500; letter-spacing: 0.6px;
        }}

        QComboBox {{
            background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: {R_SM}px;
            padding: 8px 12px; font-size: 12.5px; color: {INK}; min-height: 20px;
        }}
        QComboBox:hover {{ border-color: {FAINT}; }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
        QComboBox QAbstractItemView {{
            background-color: {SURFACE}; border: 1px solid {BORDER};
            border-radius: {R_MD}px; padding: 4px; outline: none;
            selection-background-color: {ACCENT_SOFT}; selection-color: {INK};
        }}

        QSpinBox {{
            background-color: {SURFACE}; border: 1px solid {BORDER};
            border-radius: {R_SM}px; padding: 3px 6px; font-size: 12px; color: {INK};
        }}
        QSpinBox:focus {{ border-color: {ACCENT_INK}; }}

        QSlider {{ min-height: 26px; background: transparent; }}
        QSlider::groove:horizontal {{
            height: 5px; background: {SURFACE_SUNK}; border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{ background: {ACCENT_HOVER}; border-radius: 3px; }}
        QSlider::handle:horizontal {{
            background: {SURFACE}; width: 16px; height: 16px;
            margin: -6px 0; border-radius: 8px;
            border: 1.5px solid {INK};
        }}
        QSlider::handle:horizontal:hover {{ background: {ACCENT}; }}

        QProgressBar {{
            border: none; background-color: {SURFACE_SUNK}; border-radius: 3px;
            color: transparent; min-height: 5px; max-height: 5px;
        }}
        QProgressBar::chunk {{ background-color: {FOREST_2}; border-radius: 3px; }}

        QScrollArea {{ background-color: transparent; border: none; }}
        QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
        QScrollBar::handle:vertical {{
            background: {BORDER}; border-radius: 4px; min-height: 32px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {FAINT}; }}
        QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
        QScrollBar::handle:horizontal {{
            background: {BORDER}; border-radius: 4px; min-width: 32px;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

        QSplitter::handle {{ background-color: transparent; }}
        QSplitter::handle:horizontal {{ width: 12px; }}

        QStatusBar {{
            background-color: transparent; color: {MUTED}; font-size: 12px;
            border-top: 1px solid {HAIRLINE};
        }}
        QStatusBar::item {{ border: none; }}

        QMenu {{
            background-color: {SURFACE}; border: 1px solid {BORDER};
            border-radius: {R_MD}px; padding: 5px;
        }}
        QMenu::item {{
            padding: 7px 14px; font-size: 12.5px; color: {INK}; border-radius: {R_SM}px;
        }}
        QMenu::item:selected {{ background-color: {SURFACE_SUNK}; }}
        QMenu::item:disabled {{ color: {FAINT}; }}
        QMenu::separator {{ height: 1px; background: {HAIRLINE}; margin: 5px 8px; }}

        QToolTip {{
            background-color: {INK}; color: #ffffff; border: none;
            padding: 7px 10px; border-radius: 8px; font-size: 12px;
        }}
    """
