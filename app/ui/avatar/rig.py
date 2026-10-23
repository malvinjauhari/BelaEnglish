"""Rig karakter 2.5D — blockout semi-realistis, digambar penuh dengan QPainter.

Kontrak penting (dipakai M3):
- Semua koordinat di kanvas virtual 1000×1000.
- Anchor ada di ``assets/rig.json``.
- Mengganti blockout dengan layer PNG tidak boleh mengubah tanda tangan
  ``paint()`` / ``update()``.

M1 sengaja belum memuat file gambar: tujuannya membuktikan rig, timing, dan
state karakter jalan di 60 fps sebelum art final ada.
"""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from .visemes import VisemeDriver

# ── palet karakter ───────────────────────────────────────────────────────────
SKIN_LIGHT = QColor("#F7D6BF")
SKIN_BASE = QColor("#EDBE9E")
SKIN_SHADE = QColor("#D79B80")
SKIN_DEEP = QColor("#B97A63")
HAIR_DARK = QColor("#241C2E")
HAIR_MID = QColor("#3A2C46")
HAIR_LIGHT = QColor("#55405F")
EYE_WHITE = QColor("#F8F3EF")
IRIS = QColor("#7A5540")
IRIS_DARK = QColor("#4A3026")
PUPIL = QColor("#1A1218")
LIP = QColor("#C06E72")
LIP_DARK = QColor("#8E4A52")
MOUTH_INNER = QColor("#4A2128")
TEETH = QColor("#F5EDE6")
TONGUE = QColor("#A85A63")
BLOUSE = QColor("#232C4C")
BLOUSE_DARK = QColor("#161D34")
ACCENT = QColor("#7C5CFF")

EMOTIONS: dict[str, dict[str, float]] = {
    "neutral": {"brow": 0.0, "brow_tilt": 0.0, "eye": 1.0, "smile": 0.12, "tilt": 0.0},
    "happy": {"brow": -5.0, "brow_tilt": -2.0, "eye": 0.92, "smile": 1.0, "tilt": -1.0},
    "thinking": {"brow": -2.0, "brow_tilt": 6.0, "eye": 0.84, "smile": -0.10, "tilt": 3.0},
    "confused": {"brow": 2.0, "brow_tilt": -8.0, "eye": 0.98, "smile": -0.45, "tilt": 5.0},
    "encouraging": {"brow": -4.0, "brow_tilt": -3.0, "eye": 1.0, "smile": 0.78, "tilt": -2.0},
    "surprised": {"brow": -11.0, "brow_tilt": 0.0, "eye": 1.12, "smile": 0.05, "tilt": 0.0},
}

HEAD_CENTER = QPointF(500.0, 360.0)


def _face_path() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(500.0, 182.0)
    path.cubicTo(602.0, 182.0, 652.0, 252.0, 650.0, 352.0)
    path.cubicTo(648.0, 444.0, 598.0, 512.0, 500.0, 540.0)
    path.cubicTo(402.0, 512.0, 352.0, 444.0, 350.0, 352.0)
    path.cubicTo(348.0, 252.0, 398.0, 182.0, 500.0, 182.0)
    return path


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class Rig:
    def __init__(self) -> None:
        self.time = 0.0
        self.breath = 0.0
        self.tilt = 0.0
        self.blink = 0.0
        self.look = QPointF(0.0, 0.0)
        self._look_target = QPointF(0.0, 0.0)
        self.emotion = "neutral"
        self.state = "idle"

        self._blink_clock = random.uniform(1.5, 4.0)
        self._blink_elapsed: float | None = None

        self.visemes = VisemeDriver()
        self.mouth_shape = "M"
        self.mouth_level = 0.0
        self._audio_level = 0.0
        self._audio_shape = "M"

    # ── input eksternal ───────────────────────────────────────────────────
    def set_emotion(self, name: str) -> None:
        if name in EMOTIONS:
            self.emotion = name

    def set_state(self, state: str) -> None:
        self.state = state

    def set_audio(self, shape: str, level: float) -> None:
        self._audio_shape = shape
        self._audio_level = max(0.0, min(1.0, level))

    def set_look(self, dx: float, dy: float) -> None:
        """dx/dy dalam -1..1 relatif terhadap tengah widget."""
        self._look_target = QPointF(
            max(-1.0, min(1.0, dx)) * 10.0,
            max(-1.0, min(1.0, dy)) * 6.0,
        )

    # ── animasi ───────────────────────────────────────────────────────────
    def update(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1))
        self.time += dt

        target_breath = math.sin(self.time * 2.0 * math.pi * 0.25) * 2.4
        self.breath = _lerp(self.breath, target_breath, 1.0 - math.exp(-dt / 0.35))

        base_tilt = math.sin(self.time * 2.0 * math.pi * 0.12) * 1.4
        state_tilt = {
            "listening": 3.2,
            "thinking": 4.0,
            "interrupted": -2.5,
            "speaking": 0.6,
        }.get(self.state, 0.0)
        emotion_tilt = EMOTIONS[self.emotion]["tilt"]
        target_tilt = base_tilt + state_tilt + emotion_tilt
        self.tilt = _lerp(self.tilt, target_tilt, 1.0 - math.exp(-dt / 0.35))

        self._update_blink(dt)

        look_alpha = 1.0 - math.exp(-dt / 0.18)
        self.look = QPointF(
            _lerp(self.look.x(), self._look_target.x(), look_alpha),
            _lerp(self.look.y(), self._look_target.y(), look_alpha),
        )

        self.mouth_shape, self.mouth_level = self.visemes.update(
            self._audio_level, self._audio_shape, dt
        )

    def _update_blink(self, dt: float) -> None:
        if self._blink_elapsed is None:
            self._blink_clock -= dt
            if self._blink_clock <= 0.0:
                self._blink_elapsed = 0.0
                self._blink_clock = random.uniform(2.4, 6.2)

        if self._blink_elapsed is None:
            self.blink = 0.0
            return

        self._blink_elapsed += dt
        duration = 0.19
        p = self._blink_elapsed / duration
        if p >= 1.0:
            self._blink_elapsed = None
            self.blink = 0.0
            return
        self.blink = p / 0.32 if p < 0.32 else (1.0 - p) / 0.68

    def force_blink(self) -> None:
        if self._blink_elapsed is None:
            self._blink_elapsed = 0.0

    # ── render ────────────────────────────────────────────────────────────
    def paint(self, painter: QPainter, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale = min(width / 620.0, height / 840.0)
        painter.save()
        painter.translate(width / 2.0, height / 2.0 + 40.0)
        painter.scale(scale, scale)
        painter.translate(-500.0, -560.0)

        self._paint_glow(painter)

        painter.save()
        painter.translate(0.0, self.breath)
        self._paint_body(painter)
        painter.restore()

        painter.save()
        painter.translate(0.0, self.breath)
        painter.translate(HEAD_CENTER.x(), HEAD_CENTER.y())
        painter.rotate(self.tilt)
        painter.translate(-HEAD_CENTER.x(), -HEAD_CENTER.y())

        self._paint_hair_back(painter)
        self._paint_ears(painter)
        self._paint_neck(painter)
        self._paint_face(painter)
        self._paint_face_shading(painter)
        self._paint_eyes(painter)
        self._paint_brows(painter)
        self._paint_nose(painter)
        self._paint_mouth(painter)
        self._paint_blush(painter)
        self._paint_hair_front(painter)
        self._paint_rim_light(painter)
        painter.restore()

        painter.restore()

    # ── bagian tubuh ──────────────────────────────────────────────────────
    def _paint_glow(self, p: QPainter) -> None:
        grad = QRadialGradient(500.0, 480.0, 430.0)
        grad.setColorAt(0.0, QColor(124, 92, 255, 46))
        grad.setColorAt(0.55, QColor(34, 211, 238, 16))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QRectF(80.0, 60.0, 840.0, 840.0))

    def _paint_body(self, p: QPainter) -> None:
        path = QPainterPath()
        path.moveTo(170.0, 1010.0)
        path.cubicTo(196.0, 830.0, 300.0, 700.0, 436.0, 654.0)
        path.cubicTo(470.0, 642.0, 530.0, 642.0, 564.0, 654.0)
        path.cubicTo(700.0, 700.0, 804.0, 830.0, 830.0, 1010.0)
        path.closeSubpath()

        grad = QLinearGradient(500.0, 640.0, 500.0, 1010.0)
        grad.setColorAt(0.0, QColor("#38456F"))
        grad.setColorAt(0.55, QColor("#28324F"))
        grad.setColorAt(1.0, BLOUSE_DARK)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(path)

        # rim light di bahu kiri supaya siluet terpisah dari background gelap
        rim = QPainterPath()
        rim.moveTo(196.0, 900.0)
        rim.cubicTo(224.0, 806.0, 316.0, 704.0, 436.0, 656.0)
        pen = QPen(QColor(124, 92, 255, 95), 3.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(rim)

        collar = QPainterPath()
        collar.moveTo(436.0, 654.0)
        collar.cubicTo(470.0, 700.0, 530.0, 700.0, 564.0, 654.0)
        collar.cubicTo(530.0, 730.0, 470.0, 730.0, 436.0, 654.0)
        p.setBrush(QColor("#10162A"))
        p.drawPath(collar)

        p.setPen(QPen(QColor(124, 92, 255, 110), 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(collar)

    def _paint_neck(self, p: QPainter) -> None:
        path = QPainterPath()
        path.moveTo(462.0, 500.0)
        path.lineTo(538.0, 500.0)
        path.lineTo(548.0, 648.0)
        path.cubicTo(520.0, 668.0, 480.0, 668.0, 452.0, 648.0)
        path.closeSubpath()

        grad = QLinearGradient(452.0, 500.0, 548.0, 660.0)
        grad.setColorAt(0.0, SKIN_SHADE)
        grad.setColorAt(0.55, SKIN_BASE)
        grad.setColorAt(1.0, SKIN_DEEP)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(path)

    def _paint_ears(self, p: QPainter) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        for rect in (QRectF(342.0, 350.0, 34.0, 62.0), QRectF(624.0, 350.0, 34.0, 62.0)):
            grad = QRadialGradient(rect.center(), rect.width())
            grad.setColorAt(0.0, SKIN_BASE)
            grad.setColorAt(1.0, SKIN_SHADE)
            p.setBrush(QBrush(grad))
            p.drawEllipse(rect)

    def _paint_hair_back(self, p: QPainter) -> None:
        path = QPainterPath()
        path.moveTo(500.0, 104.0)
        path.cubicTo(330.0, 104.0, 286.0, 262.0, 304.0, 424.0)
        path.cubicTo(318.0, 548.0, 344.0, 622.0, 386.0, 664.0)
        path.cubicTo(428.0, 612.0, 442.0, 566.0, 450.0, 522.0)
        path.lineTo(550.0, 522.0)
        path.cubicTo(558.0, 570.0, 572.0, 614.0, 614.0, 664.0)
        path.cubicTo(660.0, 616.0, 684.0, 540.0, 696.0, 424.0)
        path.cubicTo(714.0, 262.0, 670.0, 104.0, 500.0, 104.0)
        path.closeSubpath()

        grad = QLinearGradient(330.0, 120.0, 690.0, 640.0)
        grad.setColorAt(0.0, HAIR_LIGHT)
        grad.setColorAt(0.35, HAIR_MID)
        grad.setColorAt(1.0, HAIR_DARK)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(path)

    def _paint_face(self, p: QPainter) -> None:
        face = _face_path()
        grad = QRadialGradient(468.0, 302.0, 330.0)
        grad.setColorAt(0.0, SKIN_LIGHT)
        grad.setColorAt(0.62, SKIN_BASE)
        grad.setColorAt(1.0, SKIN_SHADE)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(face)

    def _paint_face_shading(self, p: QPainter) -> None:
        face = _face_path()
        p.save()
        p.setClipPath(face)

        # bayangan rahang
        jaw = QLinearGradient(0.0, 430.0, 0.0, 545.0)
        jaw.setColorAt(0.0, QColor(180, 110, 92, 0))
        jaw.setColorAt(1.0, QColor(180, 110, 92, 80))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(jaw))
        p.drawRect(QRectF(330.0, 420.0, 340.0, 130.0))

        # bayangan sisi kiri (arah cahaya dari kanan)
        side = QLinearGradient(350.0, 0.0, 470.0, 0.0)
        side.setColorAt(0.0, QColor(160, 96, 82, 55))
        side.setColorAt(1.0, QColor(160, 96, 82, 0))
        p.setBrush(QBrush(side))
        p.drawRect(QRectF(340.0, 170.0, 140.0, 380.0))

        # kilau dahi
        shine = QRadialGradient(560.0, 250.0, 120.0)
        shine.setColorAt(0.0, QColor(255, 236, 224, 90))
        shine.setColorAt(1.0, QColor(255, 236, 224, 0))
        p.setBrush(QBrush(shine))
        p.drawEllipse(QRectF(470.0, 180.0, 160.0, 130.0))
        p.restore()

    def _paint_eyes(self, p: QPainter) -> None:
        open_factor = max(0.06, 1.0 - self.blink * 0.94)
        eye_scale = EMOTIONS[self.emotion]["eye"]
        if self.state == "thinking":
            eye_scale *= 0.9

        for cx, side in ((432.0, -1.0), (568.0, 1.0)):
            cy = 380.0
            p.save()
            p.translate(cx, cy)
            p.scale(1.0, open_factor * eye_scale)
            p.translate(-cx, -cy)

            eye_rect = QRectF(cx - 35.0, cy - 23.0, 70.0, 46.0)
            eye_path = QPainterPath()
            eye_path.addEllipse(eye_rect)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(EYE_WHITE)
            p.drawPath(eye_path)

            p.save()
            p.setClipPath(eye_path)

            iris = QRadialGradient(cx + self.look.x() - 4.0, cy + self.look.y() - 3.0, 20.0)
            iris.setColorAt(0.0, QColor("#9A6E52"))
            iris.setColorAt(0.55, IRIS)
            iris.setColorAt(1.0, IRIS_DARK)
            p.setBrush(QBrush(iris))
            p.drawEllipse(
                QRectF(
                    cx - 19.0 + self.look.x() * 0.55,
                    cy - 19.0 + self.look.y() * 0.55,
                    38.0,
                    38.0,
                )
            )

            p.setBrush(PUPIL)
            p.drawEllipse(
                QRectF(
                    cx - 8.0 + self.look.x() * 0.6,
                    cy - 8.0 + self.look.y() * 0.6,
                    16.0,
                    16.0,
                )
            )

            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(
                QPointF(cx - 7.0 + self.look.x() * 0.7, cy - 7.0 + self.look.y() * 0.7),
                4.6,
                4.6,
            )
            p.setBrush(QColor(255, 255, 255, 90))
            p.drawEllipse(
                QPointF(cx + 7.0 + self.look.x() * 0.6, cy + 8.0 + self.look.y() * 0.6),
                2.4,
                2.4,
            )
            p.restore()

            # garis kelopak atas
            lid = QPainterPath()
            lid.moveTo(cx - 35.0, cy + 1.0)
            lid.cubicTo(cx - 22.0, cy - 30.0, cx + 22.0, cy - 30.0, cx + 35.0, cy + 1.0)
            pen = QPen(QColor("#2A1E28"), 4.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(lid)

            # bulu mata
            pen.setWidthF(2.0)
            p.setPen(pen)
            p.drawLine(
                QPointF(cx + 30.0 * side, cy - 7.0 * side),
                QPointF(cx + 44.0 * side, cy - 14.0 * side),
            )

            # garis kelopak bawah
            lower = QPainterPath()
            lower.moveTo(cx - 30.0, cy + 9.0)
            lower.cubicTo(cx - 14.0, cy + 24.0, cx + 14.0, cy + 24.0, cx + 30.0, cy + 9.0)
            p.setPen(QPen(QColor(150, 96, 84, 150), 1.6))
            p.drawPath(lower)

            if self.blink > 0.55:
                p.setPen(QPen(QColor("#3A2A32"), 3.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawLine(QPointF(cx - 30.0, cy), QPointF(cx + 30.0, cy))

            p.restore()

    def _paint_brows(self, p: QPainter) -> None:
        emo = EMOTIONS[self.emotion]
        lift = emo["brow"] + (2.0 if self.state == "listening" else 0.0)
        tilt = emo["brow_tilt"]

        for cx, side in ((432.0, -1.0), (568.0, 1.0)):
            base_y = 330.0 + lift
            inner = QPointF(cx - 32.0 * side, base_y + tilt)
            outer = QPointF(cx + 32.0 * side, base_y - tilt * 0.35 - 4.0)
            control = QPointF(cx + 2.0 * side, base_y - 12.0)

            path = QPainterPath(inner)
            path.quadTo(control, outer)

            pen = QPen(QColor("#332231"), 6.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

    def _paint_nose(self, p: QPainter) -> None:
        p.setPen(QPen(QColor(180, 112, 96, 150), 2.4))
        path = QPainterPath(QPointF(506.0, 408.0))
        path.cubicTo(516.0, 438.0, 512.0, 456.0, 498.0, 462.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        shadow = QRadialGradient(500.0, 470.0, 34.0)
        shadow.setColorAt(0.0, QColor(170, 100, 86, 70))
        shadow.setColorAt(1.0, QColor(170, 100, 86, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(shadow))
        p.drawEllipse(QRectF(466.0, 452.0, 68.0, 30.0))

        p.setBrush(QColor(255, 240, 230, 60))
        p.drawEllipse(QRectF(494.0, 420.0, 8.0, 22.0))

    def _paint_mouth(self, p: QPainter) -> None:
        cx, cy = 500.0, 505.0
        smile = EMOTIONS[self.emotion]["smile"]
        shape = self.mouth_shape
        level = self.mouth_level

        if shape == "M" or level < 0.05:
            corner = smile * 7.0
            line = QPainterPath(QPointF(cx - 35.0, cy + corner))
            line.quadTo(cx, cy + 5.0 + corner, cx + 35.0, cy + corner)
            pen = QPen(LIP_DARK, 4.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(line)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(232, 160, 158, 80))
            p.drawRoundedRect(QRectF(cx - 30.0, cy + 3.0 + corner, 60.0, 7.0), 3.0, 3.0)
            return

        dims = {
            "A": (34.0, 30.0),
            "E": (42.0, 20.0),
            "O": (27.0, 33.0),
            "U": (21.0, 24.0),
            "F": (36.0, 14.0),
        }
        half_w, height = dims.get(shape, (32.0, 24.0))
        open_h = max(6.0, height * (0.35 + level * 0.85))
        corner = smile * 8.0

        inner = QPainterPath()
        inner.moveTo(cx - half_w, cy + corner * 0.5)
        inner.cubicTo(
            cx - half_w * 0.55,
            cy - open_h * 0.55 - corner * 0.2,
            cx + half_w * 0.55,
            cy - open_h * 0.55 - corner * 0.2,
            cx + half_w,
            cy + corner * 0.5,
        )
        inner.cubicTo(
            cx + half_w * 0.55,
            cy + open_h * 0.55,
            cx - half_w * 0.55,
            cy + open_h * 0.55,
            cx - half_w,
            cy + corner * 0.5,
        )
        inner.closeSubpath()

        lips = QPainterPath()
        lips.addRoundedRect(
            QRectF(cx - half_w - 5.0, cy - open_h / 2.0 - 4.0, (half_w + 5.0) * 2.0, open_h + 9.0),
            (open_h + 9.0) / 2.0,
            (open_h + 9.0) / 2.0,
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(LIP)
        p.drawPath(lips)

        p.setBrush(MOUTH_INNER)
        p.drawPath(inner)

        p.save()
        p.setClipPath(inner)
        p.setBrush(TEETH)
        p.drawRect(QRectF(cx - half_w, cy - open_h, half_w * 2.0, open_h * 0.42))
        p.setBrush(TONGUE)
        p.drawEllipse(
            QRectF(cx - half_w * 0.55, cy + open_h * 0.12, half_w * 1.1, open_h * 0.55)
        )
        p.restore()

        if shape == "F":
            p.setPen(QPen(QColor(255, 255, 255, 220), 2.0))
            p.drawLine(
                QPointF(cx - half_w * 0.7, cy + open_h * 0.18),
                QPointF(cx + half_w * 0.7, cy + open_h * 0.18),
            )

        highlight = QLinearGradient(0.0, cy + open_h / 2.0, 0.0, cy + open_h / 2.0 + 6.0)
        highlight.setColorAt(0.0, QColor(255, 210, 205, 110))
        highlight.setColorAt(1.0, QColor(255, 210, 205, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(highlight))
        p.drawRoundedRect(
            QRectF(cx - half_w * 0.7, cy + open_h / 2.0 - 1.0, half_w * 1.4, 7.0),
            3.0,
            3.0,
        )

    def _paint_blush(self, p: QPainter) -> None:
        for cx in (392.0, 608.0):
            grad = QRadialGradient(cx, 458.0, 48.0)
            grad.setColorAt(0.0, QColor(224, 120, 112, 62))
            grad.setColorAt(1.0, QColor(224, 120, 112, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(QRectF(cx - 48.0, 410.0, 96.0, 96.0))

    def _paint_hair_front(self, p: QPainter) -> None:
        fringe = QPainterPath()
        fringe.moveTo(336.0, 338.0)
        fringe.cubicTo(318.0, 196.0, 414.0, 126.0, 512.0, 132.0)
        fringe.cubicTo(628.0, 138.0, 696.0, 222.0, 676.0, 350.0)
        fringe.cubicTo(660.0, 312.0, 636.0, 278.0, 604.0, 254.0)
        fringe.cubicTo(588.0, 306.0, 556.0, 330.0, 534.0, 338.0)
        fringe.cubicTo(518.0, 286.0, 486.0, 254.0, 452.0, 246.0)
        fringe.cubicTo(424.0, 300.0, 382.0, 320.0, 336.0, 338.0)
        fringe.closeSubpath()

        grad = QLinearGradient(360.0, 140.0, 640.0, 360.0)
        grad.setColorAt(0.0, HAIR_LIGHT)
        grad.setColorAt(0.45, HAIR_MID)
        grad.setColorAt(1.0, HAIR_DARK)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fringe)

        # helai rambut
        p.setBrush(Qt.BrushStyle.NoBrush)
        for start, control, end, width, alpha in (
            ((470.0, 168.0), (520.0, 210.0), (556.0, 300.0), 5.0, 90),
            ((430.0, 180.0), (452.0, 232.0), (470.0, 300.0), 3.5, 70),
            ((600.0, 210.0), (626.0, 252.0), (630.0, 316.0), 3.0, 60),
        ):
            path = QPainterPath(QPointF(*start))
            path.quadTo(QPointF(*control), QPointF(*end))
            pen = QPen(QColor(255, 235, 255, alpha), width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawPath(path)

    def _paint_rim_light(self, p: QPainter) -> None:
        p.save()
        p.setClipPath(_face_path())
        grad = QLinearGradient(640.0, 0.0, 500.0, 0.0)
        grad.setColorAt(0.0, QColor(124, 92, 255, 120))
        grad.setColorAt(0.35, QColor(124, 92, 255, 0))
        p.setPen(QPen(QBrush(grad), 6.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(_face_path())
        p.restore()
