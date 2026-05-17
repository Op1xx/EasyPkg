import os
import sys
from PyQt6 import sip
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QSizePolicy, QMessageBox,
    QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent
from PyQt6.uic import loadUi
from core.distro_detector import get_distro_info
from core.pkg_manager import PackageManager
from core.worker import SearchWorker, InstalledWorker, InstallWorker, RemoveWorker
from ui.password_dialog import PasswordDialog
from ui.title_bar import TitleBar
from ui.resize_filter import ResizeFilter
from ui.setup_dialog import SetupDialog, is_setup_done

DISTRO_ITEM_MAP = {
    "arch": "Arch Linux (pacman)",
    "manjaro": "Arch Linux (pacman)",
    "endeavouros": "Arch Linux (pacman)",
    "fedora": "Fedora (dnf)",
    "rhel": "Fedora (dnf)",
    "centos": "Fedora (dnf)",
    "rocky": "Fedora (dnf)",
    "almalinux": "Fedora (dnf)",
    "redos": "РЕД ОС",
    "debian": "Debian / Ubuntu (apt)",
    "ubuntu": "Debian / Ubuntu (apt)",
    "mint": "Debian / Ubuntu (apt)",
    "kali": "Debian / Ubuntu (apt)",
    "astra": "Astra Linux (SE)",
    "alt": "ALT Linux / МОС",
    "rosa": "ALT Linux / МОС",
    "mos": "ALT Linux / МОС",
}

SIDEBAR_MANAGER_MAP = {
    "Arch Linux (pacman)": "pacman",
    "Fedora (dnf)": "dnf",
    "Debian / Ubuntu (apt)": "apt",
    "Astra Linux (SE)": "apt",
    "РЕД ОС": "dnf",
    "ALT Linux / МОС": "apt-get",
}

_active_workers = []
_installed_names: set[str] = set()
_sudo_password: str | None = None
_last_query: str = ""
_system_manager: str | None = None
_selected_manager: str | None = None
_last_view: str = "search"

_SPINNER = ["▰▱▱▱", "▱▰▱▱", "▱▱▰▱", "▱▱▱▰", "▱▱▰▱", "▱▰▱▱"]


class _InstalledBtnFilter(QObject):
    """Меняет текст кнопки на «УДАЛИТЬ» при наведении и обратно при уходе."""
    def eventFilter(self, obj, event):
        if obj.isEnabled():
            if event.type() == QEvent.Type.Enter:
                obj.setText("УДАЛИТЬ")
            elif event.type() == QEvent.Type.Leave:
                obj.setText("УСТАНОВЛЕН")
        return False


class ButtonSpinner:
    """Анимирует кнопку пока идёт фоновая операция."""
    def __init__(self, btn: QPushButton, label: str):
        self._btn = btn
        self._label = label
        self._idx = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(120)

    def _tick(self):
        if sip.isdeleted(self._btn):
            self.stop()
            return
        frame = _SPINNER[self._idx % len(_SPINNER)]
        self._btn.setText(f"{frame}  {self._label}")
        self._idx += 1

    def stop(self):
        self._timer.stop()


def main():
    app = QApplication(sys.argv)
    window = loadUi("ui/main_window.ui")

    with open("assets/main_window.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    window.menuBar().setVisible(False)
    window.statusBar().setVisible(False)

    # ── Убираем стандартный фрейм, добавляем кастомный тайтлбар ──
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    titlebar = TitleBar()
    central = window.centralWidget()
    wrapper = QWidget()
    wrapper.setObjectName("AppWrapper")
    wrapper_layout = QVBoxLayout(wrapper)
    wrapper_layout.setSpacing(0)
    wrapper_layout.setContentsMargins(0, 0, 0, 0)
    wrapper_layout.addWidget(titlebar)
    wrapper_layout.addWidget(central)
    window.setCentralWidget(wrapper)
    ResizeFilter(window)

    # ── Перестраиваем PkgsFrame: section title + scroll area ──
    pkg_frame_layout = window.PkgsFrame.layout()
    while pkg_frame_layout.count():
        item = pkg_frame_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            # очищаем вложенные layout
            pass

    section_title = QLabel("// ПОПУЛЯРНЫЕ ПАКЕТЫ")
    section_title.setObjectName("section_title")
    section_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    scroll_content = QWidget()
    scroll_content.setStyleSheet("background-color: #0c0c0c;")
    pkg_list_layout = QVBoxLayout(scroll_content)
    pkg_list_layout.setSpacing(0)
    pkg_list_layout.setContentsMargins(0, 0, 0, 0)
    pkg_list_layout.addStretch()

    scroll.setWidget(scroll_content)

    pkg_frame_layout.addWidget(section_title, 0, 0)
    pkg_frame_layout.addWidget(scroll, 1, 0)
    pkg_frame_layout.setSpacing(0)
    pkg_frame_layout.setContentsMargins(0, 0, 0, 0)
    pkg_frame_layout.setColumnStretch(0, 1)
    pkg_frame_layout.setRowStretch(1, 1)

    # ── Инфо о системе ──
    info = get_distro_info()
    print(f"🐧 Система: {info['name']} | Менеджер: {info['manager']}")

    pkg = PackageManager.from_manager(info["manager"]) if info["manager"] else None
    global _system_manager, _selected_manager
    _system_manager = info["manager"]
    _selected_manager = info["manager"]

    # ── Сайдбар ──
    window.ManagersLabel.setText("// ДИСТРИБУТИВ")
    window.InstalledButton.setText("▼ СКАЧАННЫЕ ПАКЕТЫ")

    window.ManagersListWidget.clear()
    distros = [
        "Arch Linux (pacman)",
        "Fedora (dnf)",
        "Debian / Ubuntu (apt)",
        "Astra Linux (SE)",
        "РЕД ОС / МОС (dnf)",
        "ALT Linux (apt)",
    ]
    window.ManagersListWidget.addItems(distros)

    # ── Вспомогательные функции ──

    # Если sudoers уже настроен — пароль не нужен
    global _sudo_password
    mgr_name = info["manager"] or ""
    if is_setup_done(mgr_name):
        _sudo_password = ""

    base_title = f"◈ EasyPkg — {info['name']}"
    titlebar.set_title(base_title)

    def open_setup():
        global _sudo_password
        dlg = SetupDialog(mgr_name, window)
        dlg.exec()
        if is_setup_done(mgr_name):
            _sudo_password = ""

    # Кнопка настройки sudo в сайдбаре (над "Скачанные пакеты")
    setup_btn = QPushButton("⚙ НАСТРОЙКА SUDO")
    setup_btn.setObjectName("InstalledButton")
    setup_btn.setMinimumHeight(45)
    setup_btn.clicked.connect(open_setup)
    sidebar_layout = window.SidebarFrame.layout().itemAt(0).layout()
    # Вставляем перед InstalledButton (последний элемент, индекс 3)
    sidebar_layout.insertWidget(sidebar_layout.count() - 1, setup_btn)

    def set_status(text: str):
        titlebar.set_title(f"◈ EasyPkg — {info['name']}  |  {text}")

    def reset_status():
        titlebar.set_title(base_title)

    def set_section_title(text: str):
        section_title.setText(f"// {text.upper()}")

    def clear_list():
        while pkg_list_layout.count() > 1:  # оставляем stretch в конце
            item = pkg_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_error(msg: str):
        dlg = QMessageBox(window)
        dlg.setIcon(QMessageBox.Icon.Critical)
        dlg.setWindowTitle("Ошибка")
        dlg.setText(msg)
        dlg.setStyleSheet("""
            * { font-family: "JetBrains Mono","Courier New",monospace; border-radius: 0; }
            QMessageBox { background: #0c0c0c; border: 3px solid #7c4dff; }
            QLabel { color: #d0d0d0; font-size: 12px; padding: 16px; background: transparent; }
            QPushButton {
                background: #0e0b1a; border: 2px solid #2a1e3d;
                padding: 8px 24px; color: #b0a0d0; font-size: 11px; font-weight: 800;
                min-width: 80px; min-height: 20px;
            }
            QPushButton:hover { background: #7c4dff; border-color: #7c4dff; color: #fff; }
        """)
        dlg.exec()

    def _is_auth_error(msg: str) -> bool:
        keywords = ("incorrect password", "try again", "authentication failure",
                    "Sorry", "пароль", "password")
        return any(k.lower() in msg.lower() for k in keywords)

    def get_sudo_password(prompt: str) -> str | None:
        global _sudo_password
        if _sudo_password is not None:
            return _sudo_password
        pwd = PasswordDialog(window, prompt).get_password()
        if pwd is not None:
            _sudo_password = pwd
        return pwd

    def make_row(name: str, desc: str, is_installed: bool = False):
        row = QFrame()
        row.setObjectName("package_row")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        h = QHBoxLayout(row)
        h.setContentsMargins(16, 14, 16, 14)
        h.setSpacing(12)

        # Левая часть: имя + описание
        info_widget = QWidget()
        info_widget.setStyleSheet("background: transparent;")
        v = QVBoxLayout(info_widget)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        lbl_name = QLabel(name)
        lbl_name.setObjectName("pkg_name")
        lbl_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        lbl_desc = QLabel(desc or "")
        lbl_desc.setObjectName("pkg_desc")
        lbl_desc.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        v.addWidget(lbl_name)
        if desc:
            v.addWidget(lbl_desc)

        info_widget.setMinimumWidth(0)
        h.addWidget(info_widget, stretch=1)

        # Правая часть: badge + кнопка
        actions = QWidget()
        actions.setStyleSheet("background: transparent;")
        a = QHBoxLayout(actions)
        a.setContentsMargins(0, 0, 0, 0)
        a.setSpacing(8)

        if is_installed:
            btn = QPushButton("УСТАНОВЛЕН")
            btn.setObjectName("installed_btn")
            _f = _InstalledBtnFilter(btn)
            btn.installEventFilter(_f)
        else:
            btn = QPushButton("УСТАНОВИТЬ")
            btn.setObjectName("install_btn")

        a.addWidget(btn)
        h.addWidget(actions)

        # Логика кнопок
        if is_installed:
            def on_remove(checked=False, _name=name, _btn=btn):
                password = get_sudo_password(f"Пароль sudo для удаления «{_name}»:")
                if password is None:
                    return
                _btn.setEnabled(False)
                set_status(f"Удаляем {_name}…")
                spinner = ButtonSpinner(_btn, "УДАЛЕНИЕ")
                worker = RemoveWorker(pkg, _name, password)
                _active_workers.append(worker)

                def on_done(success: bool, msg: str, _w=worker, _b=_btn, _n=_name, _s=spinner):
                    global _sudo_password
                    _s.stop()
                    reset_status()
                    if not sip.isdeleted(_b):
                        if success:
                            refresh_after_operation()
                        else:
                            if _is_auth_error(msg):
                                _sudo_password = None
                            _b.setEnabled(True)
                            _b.setText("УСТАНОВЛЕН")
                            show_error(f"Не удалось удалить {_n}:\n{msg}")
                    if _w in _active_workers:
                        _active_workers.remove(_w)

                worker.finished.connect(on_done)
                worker.start()

            btn.clicked.connect(on_remove)
        else:
            def on_install(checked=False, _name=name, _btn=btn):
                password = get_sudo_password(f"Пароль sudo для установки «{_name}»:")
                if password is None:
                    return
                _btn.setEnabled(False)
                set_status(f"Устанавливаем {_name}…")
                spinner = ButtonSpinner(_btn, "УСТАНОВКА")
                worker = InstallWorker(pkg, _name, password)
                _active_workers.append(worker)

                def on_done(success: bool, msg: str, _w=worker, _b=_btn, _n=_name, _s=spinner):
                    global _sudo_password
                    _s.stop()
                    reset_status()
                    if not sip.isdeleted(_b):
                        if success:
                            refresh_after_operation()
                        else:
                            if _is_auth_error(msg):
                                _sudo_password = None
                            _b.setEnabled(True)
                            _b.setText("УСТАНОВИТЬ")
                            show_error(f"Не удалось установить {_n}:\n{msg}")
                    if _w in _active_workers:
                        _active_workers.remove(_w)

                worker.finished.connect(on_done)
                worker.start()

            btn.clicked.connect(on_install)

        return row

    def show_results(results: list[dict], title: str = "РЕЗУЛЬТАТЫ", force_installed: bool = False):
        clear_list()
        set_section_title(title)
        if not results:
            placeholder = QLabel("Ничего не найдено")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #4a4a4a; padding: 32px;")
            pkg_list_layout.insertWidget(0, placeholder)
            return
        for i, pkg_info in enumerate(results):
            name = pkg_info["name"]
            installed = force_installed or (name in _installed_names)
            row = make_row(name, pkg_info.get("description", ""), installed)
            pkg_list_layout.insertWidget(i, row)

    def show_search_error(msg: str):
        reset_status()
        show_error(f"Ошибка поиска:\n{msg}")

    def do_search(query: str):
        global _last_query, _last_view
        _last_query = query
        _last_view = "search"
        if not pkg:
            show_error("Пакетный менеджер не определён для этого дистрибутива.")
            return
        set_status(f"Поиск «{query}»…")
        worker = SearchWorker(pkg, query)
        _active_workers.append(worker)

        def on_results(results: list, _w=worker, _q=query):
            reset_status()
            show_results(results, title=f"ПОИСК: {_q.upper()}", force_installed=False)
            if _w in _active_workers:
                _active_workers.remove(_w)

        def on_error(msg: str, _w=worker):
            show_search_error(msg)
            if _w in _active_workers:
                _active_workers.remove(_w)

        worker.results_ready.connect(on_results)
        worker.error.connect(on_error)
        worker.start()

    # ── Обработчики событий ──

    def refresh_after_operation():
        if not pkg:
            return
        cache_worker = InstalledWorker(pkg)
        _active_workers.append(cache_worker)

        def on_cache_ready(results: list, _w=cache_worker):
            _installed_names.clear()
            for r in results:
                _installed_names.add(r["name"])
            if _w in _active_workers:
                _active_workers.remove(_w)
            if _last_view == "search":
                do_search(_last_query or "git")
            else:
                on_installed_click()

        cache_worker.results_ready.connect(on_cache_ready)
        cache_worker.start()

    def select_system_distro():
        for text, mgr in SIDEBAR_MANAGER_MAP.items():
            if mgr == _system_manager:
                for i, d in enumerate(distros):
                    if d == text:
                        window.ManagersListWidget.setCurrentRow(i)
                        break
                break

    def on_distro_click(_item):
        global _selected_manager
        text = _item.text()
        _selected_manager = SIDEBAR_MANAGER_MAP.get(text)
        if _selected_manager != _system_manager:
            show_error("У вас нет этого пакетного менеджера")
            select_system_distro()
            _selected_manager = _system_manager
            return
        query = window.SearchbarLineEdit.text().strip() or "git"
        do_search(query)

    def on_installed_click():
        global _last_view, _selected_manager
        if _selected_manager != _system_manager:
            show_error("У вас нет этого пакетного менеджера")
            select_system_distro()
            _selected_manager = _system_manager
            return
        if not pkg:
            show_error("Пакетный менеджер не определён для этого дистрибутива.")
            return
        window.ManagersListWidget.clearSelection()
        set_status("Загружаем список установленных…")
        worker = InstalledWorker(pkg)
        _active_workers.append(worker)

        def on_results(results: list, _w=worker):
            global _last_view
            _last_view = "installed"
            reset_status()
            show_results(results, title="УСТАНОВЛЕННЫЕ ПАКЕТЫ", force_installed=True)
            if _w in _active_workers:
                _active_workers.remove(_w)

        def on_error(msg: str, _w=worker):
            show_search_error(msg)
            if _w in _active_workers:
                _active_workers.remove(_w)

        worker.results_ready.connect(on_results)
        worker.error.connect(on_error)
        worker.start()

    def on_search():
        global _selected_manager
        query = window.SearchbarLineEdit.text().strip()
        if query:
            if _selected_manager != _system_manager:
                show_error("У вас нет этого пакетного менеджера")
                select_system_distro()
                _selected_manager = _system_manager
                return
            do_search(query)

    window.ManagersListWidget.itemClicked.connect(on_distro_click)
    window.InstalledButton.clicked.connect(on_installed_click)
    window.SearchButton.clicked.connect(on_search)
    window.SearchbarLineEdit.returnPressed.connect(on_search)

    # Автовыбор дистрибутива в сайдбаре
    dist_id = ""
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    dist_id = line.split("=", 1)[1].strip().strip('"\'').lower()
                    break

    target_item = DISTRO_ITEM_MAP.get(dist_id, distros[0])
    for i, d in enumerate(distros):
        if d == target_item:
            window.ManagersListWidget.setCurrentRow(i)
            break

    # Сначала загружаем кеш установленных, потом запускаем поиск —
    # иначе уже установленные пакеты показываются с кнопкой «УСТАНОВИТЬ»
    if pkg:
        cache_worker = InstalledWorker(pkg)
        _active_workers.append(cache_worker)

        def on_cache_ready(results: list, _w=cache_worker):
            for r in results:
                _installed_names.add(r["name"])
            if _w in _active_workers:
                _active_workers.remove(_w)
            do_search("git")

        cache_worker.results_ready.connect(on_cache_ready)
        cache_worker.start()
    else:
        do_search("git")

    window.show()

    # Первый запуск — показываем настройку sudoers автоматически
    if pkg and not is_setup_done(mgr_name):
        QTimer.singleShot(300, open_setup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
