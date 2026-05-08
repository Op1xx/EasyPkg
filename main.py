import sys
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.uic import loadUi

from core.distro_detector import get_distro_info
from core.pkg_manager import Package, get_install_cmd, list_installed, search_packages
from core.command_runner import InstallWorker


DISTRO_MANAGERS: dict[str, str] = {
    "Arch Linux (pacman)": "pacman",
    "Fedora (dnf)":        "dnf",
    "Debian / Ubuntu (apt)": "apt",
    "Astra Linux (SE)":    "apt",
    "РЕД ОС":              "dnf",
    "ALT Linux / МОС":     "apt",
}


class SearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, manager: str, query: str):
        super().__init__()
        self.manager = manager
        self.query = query

    def run(self):
        try:
            self.results_ready.emit(search_packages(self.manager, self.query))
        except Exception as e:
            self.error.emit(str(e))


class InstalledWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, manager: str):
        super().__init__()
        self.manager = manager

    def run(self):
        try:
            self.results_ready.emit(list_installed(self.manager))
        except Exception as e:
            self.error.emit(str(e))


class InstallDialog(QDialog):
    def __init__(self, package: str, manager: str, password: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Установка: {package}")
        self.setMinimumSize(540, 380)
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("install_output")
        layout.addWidget(self.output)

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        cmd = get_install_cmd(manager, package)
        if not cmd:
            self.output.append(f"Неизвестный менеджер пакетов: {manager}")
            self.close_btn.setEnabled(True)
            return

        self.output.append(f"$ sudo {' '.join(cmd)}\n")
        self.worker = InstallWorker(cmd, password, self)
        self.worker.line_received.connect(self.output.append)
        self.worker.finished.connect(self._on_done)
        self.worker.start()

    def _on_done(self, success: bool):
        self.output.append("\n✅ Установка завершена" if success else "\n❌ Ошибка установки")
        self.close_btn.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    window = loadUi("ui/main_window.ui")

    with open("assets/main_window.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    window.menuBar().setVisible(False)
    window.statusBar().setVisible(False)

    info = get_distro_info()
    window.setWindowTitle(f"EasyPkg — {info['name']}")

    state: dict = {
        "manager": info["manager"] or "apt",
        "worker": None,
    }

    window.ManagersLabel.setText("Дистрибутив")
    window.SearchbarLineEdit.setPlaceholderText("Поиск пакетов...")

    distros = list(DISTRO_MANAGERS.keys())
    window.ManagersListWidget.addItems(distros)

    # Скролл-область для карточек пакетов (PkgsLayout — QGridLayout из .ui)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setObjectName("PkgsScrollArea")

    pkg_container = QWidget()
    pkg_container.setObjectName("PkgsContainer")
    pkg_layout = QVBoxLayout(pkg_container)
    pkg_layout.setContentsMargins(8, 8, 8, 8)
    pkg_layout.setSpacing(6)
    pkg_layout.addStretch()
    scroll.setWidget(pkg_container)

    window.PkgsLayout.addWidget(scroll, 0, 0)

    def clear_cards():
        # Удаляем все кроме последнего stretch
        while pkg_layout.count() > 1:
            item = pkg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_status(text: str):
        clear_cards()
        lbl = QLabel(text)
        lbl.setObjectName("StatusLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pkg_layout.insertWidget(0, lbl)

    def make_card(pkg: Package) -> QFrame:
        card = QFrame()
        card.setObjectName("package_card")

        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(4)

        top = QHBoxLayout()
        name_lbl = QLabel(pkg.name)
        name_lbl.setObjectName("pkg_name")
        top.addWidget(name_lbl)
        if pkg.version:
            ver_lbl = QLabel(pkg.version)
            ver_lbl.setObjectName("pkg_version")
            top.addWidget(ver_lbl)
        top.addStretch()
        v.addLayout(top)

        if pkg.description:
            desc_lbl = QLabel(pkg.description)
            desc_lbl.setObjectName("pkg_desc")
            desc_lbl.setWordWrap(True)
            v.addWidget(desc_lbl)

        bottom = QHBoxLayout()
        bottom.addStretch()
        if pkg.installed:
            badge = QLabel("Установлен")
            badge.setObjectName("InstalledBadge")
            bottom.addWidget(badge)
        else:
            btn = QPushButton("Установить")
            btn.setObjectName("install_btn")
            btn.clicked.connect(lambda checked=False, p=pkg: do_install(p.name))
            bottom.addWidget(btn)
        v.addLayout(bottom)

        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        return card

    def show_packages(packages: list[Package]):
        clear_cards()
        if not packages:
            show_status("Ничего не найдено")
            return
        for i, pkg in enumerate(packages):
            pkg_layout.insertWidget(i, make_card(pkg))

    def do_install(package_name: str):
        password, ok = QInputDialog.getText(
            window,
            "Авторизация",
            f"Пароль sudo для установки '{package_name}':",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        dlg = InstallDialog(package_name, state["manager"], password, window)
        dlg.exec()

    def do_search():
        query = window.SearchbarLineEdit.text().strip()
        if not query:
            return
        show_status("Поиск...")
        _stop_worker()
        w = SearchWorker(state["manager"], query)
        w.results_ready.connect(show_packages)
        w.error.connect(lambda msg: show_status(f"Ошибка: {msg}"))
        w.start()
        state["worker"] = w

    def on_installed_click():
        window.ManagersListWidget.clearSelection()
        show_status("Загрузка установленных пакетов...")
        _stop_worker()
        w = InstalledWorker(state["manager"])
        w.results_ready.connect(show_packages)
        w.error.connect(lambda msg: show_status(f"Ошибка: {msg}"))
        w.start()
        state["worker"] = w

    def on_distro_click(item):
        state["manager"] = DISTRO_MANAGERS.get(item.text(), "apt")
        show_status(f"Выбран: {item.text()}. Введите запрос для поиска.")

    def _stop_worker():
        w = state.get("worker")
        if w and w.isRunning():
            w.terminate()
            w.wait()

    window.ManagersListWidget.itemClicked.connect(on_distro_click)
    window.InstalledButton.clicked.connect(on_installed_click)
    window.SearchButton.clicked.connect(do_search)
    window.SearchbarLineEdit.returnPressed.connect(do_search)

    detected = info["manager"]
    if detected:
        for i, (distro, mgr) in enumerate(DISTRO_MANAGERS.items()):
            if mgr == detected:
                window.ManagersListWidget.setCurrentRow(i)
                break

    show_status("Введите запрос и нажмите Поиск")

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
