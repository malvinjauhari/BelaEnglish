"""Token warna, font, dan stylesheet Qt.

Semua warna UI diambil dari sini supaya tema bisa diganti di satu tempat.
"""

from __future__ import annotations

COLORS = {
    "bg": "#0B1020",
    "surface": "#141A2E",
    "surface_high": "#1B2340",
    "line": "#283252",
    "text": "#E8ECF8",
    "text_dim": "#98A2C0",
    "text_faint": "#6C7796",
    "accent": "#7C5CFF",
    "accent_soft": "#9B85FF",
    "cyan": "#22D3EE",
    "coral": "#FF8A65",
    "success": "#4ADE80",
    "danger": "#FF6B6B",
}

FONT_FAMILY = '"Inter", "Segoe UI", "Noto Sans", sans-serif'
MONO_FAMILY = '"JetBrains Mono", "DejaVu Sans Mono", monospace'

RADIUS = 18


def stylesheet() -> str:
    c = COLORS
    return f"""
    QWidget {{
        color: {c['text']};
        font-family: {FONT_FAMILY};
        font-size: 13px;
    }}
    #Root {{
        background: {c['bg']};
        border: 1px solid {c['line']};
        border-radius: {RADIUS}px;
    }}
    #Root[maximized="true"] {{
        border-radius: 0px;
        border: none;
    }}
    #TitleBar {{
        background: transparent;
    }}
    #AppName {{
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}
    #StatusPill {{
        background: {c['surface_high']};
        color: {c['text_dim']};
        border: 1px solid {c['line']};
        border-radius: 10px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.6px;
    }}
    #StatusPill[state="listening"] {{
        color: {c['cyan']};
        border-color: {c['cyan']};
    }}
    #StatusPill[state="speaking"] {{
        color: {c['accent_soft']};
        border-color: {c['accent']};
    }}
    #StatusPill[state="thinking"] {{
        color: {c['coral']};
        border-color: {c['coral']};
    }}
    #StatusPill[state="error"] {{
        color: {c['danger']};
        border-color: {c['danger']};
    }}
    #WinButton {{
        background: transparent;
        border: none;
        border-radius: 7px;
        color: {c['text_dim']};
        font-size: 13px;
        padding: 5px 10px;
    }}
    #WinButton:hover {{
        background: {c['surface_high']};
        color: {c['text']};
    }}
    #WinButtonClose:hover {{
        background: {c['danger']};
        color: white;
    }}
    #WinButton[danger="true"]:hover {{
        background: {c['danger']};
        color: white;
    }}
    #Panel {{
        background: {c['surface']};
        border: 1px solid {c['line']};
        border-radius: 14px;
    }}
    #SectionLabel {{
        color: {c['text_faint']};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.4px;
    }}
    #ScenarioTitle {{
        font-size: 15px;
        font-weight: 700;
    }}
    #ScenarioMeta {{
        color: {c['text_dim']};
        font-size: 12px;
    }}
    #ModeChip {{
        background: transparent;
        border: 1px solid {c['line']};
        border-radius: 10px;
        padding: 8px 6px;
        color: {c['text_dim']};
        font-size: 12px;
        font-weight: 600;
    }}
    #ModeChip:hover {{
        border-color: {c['accent_soft']};
        color: {c['text']};
    }}
    #ModeChip:checked {{
        background: {c['accent']};
        border-color: {c['accent']};
        color: white;
    }}
    #StatValue {{
        font-family: {MONO_FAMILY};
        font-size: 16px;
        font-weight: 700;
        color: {c['text']};
    }}
    #StatName {{
        color: {c['text_faint']};
        font-size: 10px;
        letter-spacing: 0.8px;
    }}
    #BubbleYou {{
        background: {c['surface_high']};
        border: 1px solid {c['line']};
        border-radius: 14px;
        padding: 10px 14px;
    }}
    #BubbleRey {{
        background: rgba(124, 92, 255, 0.14);
        border: 1px solid rgba(124, 92, 255, 0.42);
        border-radius: 14px;
        padding: 10px 14px;
    }}
    #SpeakerName {{
        color: {c['text_faint']};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    #CorrectionCard {{
        background: rgba(255, 138, 101, 0.10);
        border: 1px solid rgba(255, 138, 101, 0.42);
        border-left: 3px solid {c['coral']};
        border-radius: 10px;
        padding: 9px 12px;
    }}
    #CorrectionFix {{
        color: {c['coral']};
        font-weight: 700;
    }}
    #CorrectionNote {{
        color: {c['text_dim']};
        font-size: 11px;
    }}
    #EmptyHint {{
        color: {c['text_faint']};
        font-size: 12px;
    }}
    #InputBar {{
        background: {c['surface_high']};
        border: 1px solid {c['line']};
        border-radius: 12px;
        padding: 10px 14px;
        color: {c['text']};
        selection-background-color: {c['accent']};
    }}
    #InputBar:focus {{
        border-color: {c['accent']};
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['line']};
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['text_faint']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QComboBox, QSpinBox {{
        background: {c['surface_high']};
        border: 1px solid {c['line']};
        border-radius: 8px;
        padding: 6px 10px;
        color: {c['text']};
    }}
    QComboBox QAbstractItemView {{
        background: {c['surface_high']};
        border: 1px solid {c['line']};
        selection-background-color: {c['accent']};
    }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: {c['line']};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {c['accent']};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {c['text']};
        width: 14px;
        margin: -6px 0;
        border-radius: 7px;
    }}
    QCheckBox {{
        color: {c['text_dim']};
        spacing: 8px;
    }}
    QDialog {{
        background: {c['surface']};
        border: 1px solid {c['line']};
    }}
    QLabel#DialogTitle {{
        font-size: 16px;
        font-weight: 700;
    }}
    QLabel#DialogHint {{
        color: {c['text_faint']};
        font-size: 11px;
    }}
    QPushButton#Primary {{
        background: {c['accent']};
        border: none;
        border-radius: 9px;
        padding: 9px 18px;
        color: white;
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{
        background: {c['accent_soft']};
    }}
    QPushButton#Ghost {{
        background: transparent;
        border: 1px solid {c['line']};
        border-radius: 9px;
        padding: 9px 16px;
        color: {c['text_dim']};
    }}
    QPushButton#Ghost:hover {{
        color: {c['text']};
        border-color: {c['text_faint']};
    }}
    QLineEdit#FormField {{
        background: {c['surface_high']};
        border: 1px solid {c['line']};
        border-radius: 8px;
        padding: 7px 10px;
        color: {c['text']};
    }}
    QLineEdit#FormField:focus {{
        border-color: {c['accent']};
    }}
    """
