from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from anime_dlp import about


class AboutDialog(QDialog):
    """Аналог Adw.AboutDialog из GTK-бэкенда: версия, ссылки, лицензия и
    список используемых библиотек."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)

        name_label = QLabel(about.APP_NAME)
        name_label.setObjectName("title1")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        version_label = QLabel(f"Версия {about.VERSION}")
        version_label.setObjectName("dimLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        summary_label = QLabel(about.SUMMARY)
        summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        layout.addWidget(self._link_block())
        layout.addWidget(self._libraries_block())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _link_block(self) -> QLabel:
        html = (
            f'Автор: {about.DEVELOPER}<br>'
            f'Исходный код: <a href="{about.WEBSITE}">{about.WEBSITE}</a><br>'
            f'Сообщить об ошибке: <a href="{about.ISSUE_URL}">{about.ISSUE_URL}</a><br>'
            f'Лицензия: <a href="{about.LICENSE_URL}">{about.LICENSE_NAME}</a>'
        )
        return self._rich_label(html)

    def _libraries_block(self) -> QLabel:
        rows = "<br>".join(
            f'<a href="{url}">{name}</a> — {description}'
            for name, url, description in about.LIBRARIES
        )
        return self._rich_label(f"<b>Библиотеки</b><br>{rows}")

    @staticmethod
    def _rich_label(html: str) -> QLabel:
        label = QLabel(html)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        return label


def show_about_dialog(window):
    AboutDialog(parent=window).exec()
