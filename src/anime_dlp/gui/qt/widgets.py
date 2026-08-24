"""Небольшой набор составных виджетов, приближенно повторяющих внешний вид
и поведение виджетов GTK4/libadwaita (Adw.ActionRow, Adw.PreferencesGroup,
Adw.StatusPage, Adw.ComboRow, Adw.SpinRow, Adw.ExpanderRow, Gtk.FlowBox,
Adw.ToastOverlay, Adw.ToolbarView/HeaderBar) на PyQt6, используемых страницами
в anime_dlp.gui.qt.*.
"""

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

APP_STYLESHEET = """
QWidget#headerBar {
    background: palette(alternate-base);
    border-bottom: 1px solid palette(mid);
}
QLabel#headerTitle {
    font-weight: 600;
    font-size: 11pt;
}
QPushButton#backButton {
    border: none;
    background: transparent;
    font-size: 14pt;
    font-weight: 600;
}
QPushButton#backButton:hover {
    background: palette(midlight);
    border-radius: 4px;
}
QFrame#card {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
}
QLabel#groupTitle {
    font-weight: 600;
    color: palette(dark);
    margin-left: 4px;
}
QFrame#actionRow {
    background: transparent;
}
QFrame#actionRow[activatable="true"]:hover {
    background: palette(alternate-base);
}
QFrame#rowSeparator {
    background: palette(mid);
    border: none;
}
QLabel#dimLabel {
    color: palette(placeholder-text);
}
QLabel#title1 {
    font-size: 18pt;
    font-weight: 700;
}
QLabel#heading {
    font-weight: 600;
}
QLabel#statusIcon {
    font-size: 40pt;
}
QPushButton#accentButton {
    background: palette(highlight);
    color: palette(highlighted-text);
    border: none;
    border-radius: 14px;
    padding: 6px 20px;
    font-weight: 600;
}
QPushButton#accentButton:hover {
    background: palette(highlight);
}
QLabel#toast {
    background: palette(shadow);
    color: palette(light);
    border-radius: 8px;
    padding: 8px 16px;
}
QTabBar::tab {
    padding: 6px 18px;
    border-radius: 14px;
    margin: 0 2px;
}
QTabBar::tab:selected {
    background: palette(highlight);
    color: palette(highlighted-text);
}
QTabBar::tab:!selected:hover {
    background: palette(midlight);
}
QFrame#coverCard:hover {
    background: palette(alternate-base);
    border-radius: 8px;
}
QLabel#pillBadge {
    background: palette(alternate-base);
    border-radius: 10px;
    padding: 4px 12px;
}
QPushButton#starButton {
    border: none;
    background: transparent;
    font-size: 16pt;
    padding: 0 4px;
}
QPushButton#starButton:hover {
    background: palette(midlight);
    border-radius: 4px;
}
QPushButton#iconButton {
    border: none;
    background: transparent;
    font-size: 13pt;
}
QPushButton#iconButton:hover {
    background: palette(midlight);
    border-radius: 4px;
}
"""


class ActionRow(QFrame):
    """Строка с заголовком/подзаголовком слева и суффиксом справа."""

    clicked = pyqtSignal()

    def __init__(self, title: str = "", subtitle: str | None = None, activatable: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("actionRow")
        self._activatable = activatable
        self.setProperty("activatable", "true" if activatable else "false")
        if activatable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.prefix_layout = QHBoxLayout()
        self.prefix_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.prefix_layout)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QLabel(title)
        title_box.addWidget(self.title_label)
        self.subtitle_label: QLabel | None = None
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("dimLabel")
            title_box.addWidget(self.subtitle_label)
        layout.addLayout(title_box, 1)

        self.suffix_layout = QHBoxLayout()
        self.suffix_layout.setContentsMargins(0, 0, 0, 0)
        self.suffix_layout.setSpacing(6)
        layout.addLayout(self.suffix_layout)

    def add_prefix(self, widget: QWidget):
        self.prefix_layout.addWidget(widget)

    def add_suffix(self, widget: QWidget):
        self.suffix_layout.addWidget(widget)

    def set_title(self, text: str):
        self.title_label.setText(text)

    def set_subtitle(self, text: str):
        if self.subtitle_label is None:
            self.subtitle_label = QLabel(text)
            self.subtitle_label.setObjectName("dimLabel")
            self.title_label.parentWidget().layout().addWidget(self.subtitle_label)
        else:
            self.subtitle_label.setText(text)

    def mousePressEvent(self, event):
        if self._activatable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PreferencesGroup(QFrame):
    """Заголовок группы + карточка со списком строк, разделённых линиями."""

    def __init__(self, title: str | None = None, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        if title:
            header = QLabel(title)
            header.setObjectName("groupTitle")
            outer.addWidget(header)

        self.card = QFrame()
        self.card.setObjectName("card")
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(0)
        outer.addWidget(self.card)

        self._rows: list[QWidget] = []

    def add(self, widget: QWidget):
        if self._rows:
            separator = QFrame()
            separator.setObjectName("rowSeparator")
            separator.setFixedHeight(1)
            self.card_layout.addWidget(separator)
        self.card_layout.addWidget(widget)
        self._rows.append(widget)


class StatusPage(QWidget):
    """Крупная центрированная иконка + заголовок + описание (+ доп. виджет)."""

    def __init__(self, icon_text: str = "", title: str = "", description: str = "", parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.setSpacing(6)

        self.icon_label = QLabel(icon_text)
        self.icon_label.setObjectName("statusIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.icon_label)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("title1")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.title_label)

        self.description_label = QLabel(description)
        self.description_label.setObjectName("dimLabel")
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        self._layout.addWidget(self.description_label)

        self._child: QWidget | None = None

    def set_description(self, text: str):
        self.description_label.setText(text)
        self.description_label.setVisible(bool(text))

    def set_child(self, widget: QWidget):
        if self._child is not None:
            self._layout.removeWidget(self._child)
            self._child.deleteLater()
        self._child = widget
        self._layout.addWidget(widget)


class ComboRow(ActionRow):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent=parent)
        self.combo = QComboBox()
        self.combo.setMinimumWidth(180)
        self.add_suffix(self.combo)

    def set_items(self, items: list[str]):
        self.combo.clear()
        self.combo.addItems(items)
        if items:
            # QComboBox по умолчанию не расширяет свой выпадающий список
            # шире закрытого поля — длинные названия студий/озвучек
            # обрезались. Меряем самую длинную строку и явно задаём
            # ширину и полю, и его попапу (view()).
            metrics = self.combo.fontMetrics()
            widest = max(metrics.horizontalAdvance(text) for text in items)
            padding = 48
            self.combo.view().setMinimumWidth(widest + padding)
            self.combo.setMinimumWidth(min(widest + padding, 480))

    def current_index(self) -> int:
        return self.combo.currentIndex()


class SpinRow(ActionRow):
    def __init__(self, title: str, minimum: int, maximum: int, value: int | None = None, parent=None):
        super().__init__(title, parent=parent)
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(value if value is not None else minimum)
        self.add_suffix(self.spin)

    def value(self) -> int:
        return self.spin.value()

    def set_value(self, value: int):
        self.spin.setValue(value)


class ExpanderRow(QFrame):
    """Кликабельный заголовок, разворачивающий/сворачивающий содержимое."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = ActionRow(title, activatable=True)
        self._chevron = QLabel("▸")
        self.header.add_suffix(self._chevron)
        self.header.clicked.connect(self.toggle)
        outer.addWidget(self.header)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 6, 12, 12)
        self.content.setVisible(False)
        outer.addWidget(self.content)

        self._expanded = False

    def add_row(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self.content.setVisible(expanded)
        self._chevron.setText("▾" if expanded else "▸")

    def toggle(self):
        self.set_expanded(not self._expanded)


class FlowLayout(QLayout):
    """Реализация flow-layout (по мотивам примера Qt "Flow Layout"),
    заполняющая строку по ширине; max_columns дополнительно ограничивает
    число элементов в строке (None — без ограничения, только по ширине)."""

    def __init__(
        self,
        parent=None,
        margin: int = 0,
        spacing: int = 18,
        max_columns: int | None = None,
    ):
        super().__init__(parent)
        self._spacing = spacing
        self._max_columns = max_columns
        self._items: list = []
        if margin >= 0:
            self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def clear(self):
        """Удаляет все виджеты из лэйаута (перезагрузка сетки)."""
        while self._items:
            item = self._items.pop()
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        items_in_line = 0

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + self._spacing
            wrap = (
                self._max_columns is not None and items_in_line >= self._max_columns
            ) or (next_x - self._spacing > effective_rect.right() and line_height > 0)
            if wrap:
                x = effective_rect.x()
                y += line_height + self._spacing
                next_x = x + item_size.width() + self._spacing
                line_height = 0
                items_in_line = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())
            items_in_line += 1

        return y + line_height - rect.y() + margins.bottom()


class ToastOverlay(QWidget):
    """Оборачивает основной контент и показывает всплывающие сообщения
    внизу окна (аналог Adw.ToastOverlay/Adw.Toast)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._content: QWidget | None = None

        self._toast_label = QLabel(self)
        self._toast_label.setObjectName("toast")
        self._toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast_label.hide()

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast_label.hide)

    def set_content(self, widget: QWidget):
        if self._content is not None:
            self._layout.removeWidget(self._content)
        self._content = widget
        self._layout.addWidget(widget)

    def show_toast(self, message: str, duration_ms: int = 3000):
        self._toast_label.setText(message)
        self._toast_label.adjustSize()
        self._reposition_toast()
        self._toast_label.show()
        self._toast_label.raise_()
        self._toast_timer.start(duration_ms)

    def _reposition_toast(self):
        x = (self.width() - self._toast_label.width()) // 2
        y = self.height() - self._toast_label.height() - 24
        self._toast_label.move(max(0, x), max(0, y))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._toast_label.isVisible():
            self._reposition_toast()


class NavHeaderBar(QWidget):
    """Заголовок страницы с опциональной кнопкой «назад» (аналог
    Adw.ToolbarView + Adw.HeaderBar внутри Adw.NavigationView)."""

    back_clicked = pyqtSignal()

    def __init__(self, title: str, show_back: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("headerBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self._layout = layout

        self.back_button = QPushButton("‹")
        self.back_button.setObjectName("backButton")
        self.back_button.setFixedWidth(32)
        self.back_button.setVisible(show_back)
        self.back_button.clicked.connect(self.back_clicked.emit)
        layout.addWidget(self.back_button)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("headerTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label, 1)

        self.end_layout = QHBoxLayout()
        self.end_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.end_layout)

        # Симметричный отступ справа, чтобы заголовок оставался по центру,
        # когда слева видна кнопка «назад» или иконка «О программе».
        self._spacer = QWidget()
        self._spacer.setFixedWidth(32)
        layout.addWidget(self._spacer)

    def add_start_widget(self, widget: QWidget):
        """Добавляет виджет слева, сразу после кнопки «назад»."""
        self._layout.insertWidget(1, widget)

    def add_end_widget(self, widget: QWidget):
        self.end_layout.addWidget(widget)

    def set_title(self, text: str):
        self.title_label.setText(text)
