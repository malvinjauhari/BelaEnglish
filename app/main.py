"""Entry point aplikasi: Qt + asyncio lewat qasync."""

from __future__ import annotations

import asyncio
import sys

import qasync
from PyQt6.QtWidgets import QApplication

from .config import Config
from .core.bus import EventBus
from .ui import theme
from .ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("BelaEnglish")
    app.setApplicationDisplayName("BelaEnglish")
    app.setOrganizationName("BelaEnglish")
    app.setStyleSheet(theme.stylesheet())

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    config = Config()
    bus = EventBus()
    window = MainWindow(config, bus)

    screen = app.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        frame = window.frameGeometry()
        frame.moveCenter(geometry.center())
        window.move(frame.topLeft())

    window.show()
    with loop:
        loop.run_forever()
    return 0
