"""Dialog pengaturan M1 — hanya preferensi yang sudah dipakai."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..config import Config

LEVELS = ["A2", "B1", "B2", "C1"]


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pengaturan")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        title = QLabel("Pengaturan")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.name_edit = QLineEdit(config.get("persona", "user_name", default=""))
        self.name_edit.setObjectName("FormField")
        self.name_edit.setPlaceholderText("Nama panggilan kamu")
        form.addRow("Nama", self.name_edit)

        self.level_combo = QComboBox()
        self.level_combo.addItems(LEVELS)
        level = config.get("persona", "cefr_level", default="B1")
        if level in LEVELS:
            self.level_combo.setCurrentText(level)
        form.addRow("Level Inggris", self.level_combo)

        self.spice_slider, self.spice_value = self._slider_row(
            config.get("persona", "spice_level", default=1), self._spice_label
        )
        form.addRow("Kasual / spice", self.spice_slider)
        form.addRow("", self.spice_value)

        self.correction_slider, self.correction_value = self._slider_row(
            config.get("persona", "correction_level", default=2),
            lambda v: f"Level {v}",
        )
        form.addRow("Intensitas koreksi", self.correction_slider)
        form.addRow("", self.correction_value)

        self.indo_check = QCheckBox("Boleh klarifikasi singkat bahasa Indonesia")
        self.indo_check.setChecked(
            bool(config.get("persona", "indonesian_help", default=True))
        )
        form.addRow("", self.indo_check)

        self.top_check = QCheckBox("Selalu di atas jendela lain")
        self.top_check.setChecked(bool(config.get("ui", "always_on_top", default=False)))
        form.addRow("", self.top_check)

        root.addLayout(form)

        hint = QLabel("Voice, model, dan perangkat audio diatur di config.json.")
        hint.setObjectName("DialogHint")
        root.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Batal")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Simpan")
        save.setObjectName("Primary")
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _slider_row(self, value: int, formatter) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 3)
        slider.setValue(int(value))
        slider.setPageStep(1)
        label = QLabel(formatter(int(value)))
        label.setObjectName("DialogHint")
        slider.valueChanged.connect(lambda v: label.setText(formatter(v)))
        return slider, label

    @staticmethod
    def _spice_label(value: int) -> str:
        return {
            0: "0 · bersih",
            1: "1 · ringan (damn, hell)",
            2: "2 · kasual (anjir, gila)",
            3: "3 · spicy (goblok, shit — ekspresi saja)",
        }.get(value, str(value))

    def values(self) -> dict:
        return {
            "user_name": self.name_edit.text().strip(),
            "cefr_level": self.level_combo.currentText(),
            "spice_level": self.spice_slider.value(),
            "correction_level": self.correction_slider.value(),
            "indonesian_help": self.indo_check.isChecked(),
            "always_on_top": self.top_check.isChecked(),
        }
