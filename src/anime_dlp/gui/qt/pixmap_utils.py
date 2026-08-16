from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPainterPath, QPixmap


def round_pixmap(pixmap: QPixmap, radius: int = 8) -> QPixmap:
    """Обрезает пиксмап по скруглённому прямоугольнику. QLabel'овский
    border-radius в стилях скругляет только фон/рамку виджета, а не
    содержимое самого pixmap — для реального скругления картинки нужна
    ручная отрисовка через QPainterPath."""
    if pixmap.isNull():
        return pixmap

    rounded = QPixmap(pixmap.size())
    rounded.fill(Qt.GlobalColor.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()

    return rounded
