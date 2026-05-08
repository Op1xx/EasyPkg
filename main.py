import sys
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.uic import loadUi
from core.distro_detector import get_distro_info

def main():
    app = QApplication(sys.argv)
    window = loadUi("ui/main_window.ui")
    
    # Применяем стили
    with open("assets/main_window.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    # Скрываем меню и статус-бар
    window.menuBar().setVisible(False)
    window.statusBar().setVisible(False)

    # Автодетект системы (для заголовка окна)
    info = get_distro_info()
    print(f"🐧 Система: {info['name']} | Менеджер: {info['manager']}")
    window.setWindowTitle(f"EasyPkg — {info['name']}")

    # === НАСТРОЙКА ИНТЕРФЕЙСА ===
    
    # Меняем текст заголовка на "Выберите дистрибутив"
    window.ManagersLabel.setText("Выберите дистрибутив")

    # Заполняем список дистрибутивов
    window.ManagersListWidget.clear()
    distros = [
        "Arch Linux (pacman)",
        "Fedora (dnf)",
        "Debian / Ubuntu (apt)",
        "Astra Linux (SE)",
        "РЕД ОС",
        "ALT Linux / МОС"
    ]
    window.ManagersListWidget.addItems(distros)

    # === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

    # Очистка сетки с пакетами
    def clear_grid():
        layout = window.PkgsLayout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # Создание карточки пакета
    def make_card(name, desc, is_installed=False):
        card = QFrame()
        card.setObjectName("package_card")  # Для стилей
        
        v_layout = QVBoxLayout(card)
        v_layout.setContentsMargins(10, 10, 10, 10)
        v_layout.setSpacing(4)

        lbl_name = QLabel(name)
        lbl_name.setObjectName("pkg_name")
        
        lbl_desc = QLabel(desc)
        lbl_desc.setObjectName("pkg_desc")
        lbl_desc.setWordWrap(True)

        # Кнопка установки (или галочка если установлено)
        btn_text = "✅" if is_installed else "⬇️"
        btn = QPushButton(btn_text)
        btn.setObjectName("install_btn")
        btn.setFixedSize(30, 30)
        
        if is_installed:
            btn.setEnabled(False)
            btn.setStyleSheet("color: #34d399;") # Зеленый цвет

        v_layout.addWidget(lbl_name)
        v_layout.addWidget(lbl_desc)
        v_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

        # Растягиваем карточку по ширине
        from PyQt6.QtWidgets import QSizePolicy
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        # Логика кнопки установки
        def on_install():
            print(f"🚀 Ставим: {name}")
            btn.setEnabled(False)
            btn.setText("✅")
            btn.setStyleSheet("color: #34d399;")

        if not is_installed:
            btn.clicked.connect(on_install)

        return card

    # === ОБРАБОТЧИКИ СОБЫТИЙ ===

    # Клик по дистрибутиву в списке
    def on_distro_click(item):
        distro = item.text()
        print(f"📂 Выбран: {distro}")
        clear_grid()
        
        # Фейковые данные для примера
        make_card("git", "Система контроля версий")
        make_card("curl", "Утилита для HTTP-запросов")
        make_card("neovim", "Продвинутый текстовый редактор")
        make_card("htop", "Монитор процессов")
        make_card("python-pip", "Менеджер пакетов Python")

    # Клик по кнопке "Скачанные пакеты" внизу
    def on_installed_click():
        print("📦 Показываем установленные пакеты")
        # Снимаем выделение со списка дистрибутивов, чтобы было понятно, что мы в другом разделе
        window.ManagersListWidget.clearSelection() 
        clear_grid()
        
        make_card("bash", "Системная оболочка", is_installed=True)
        make_card("coreutils", "Базовые утилиты Linux", is_installed=True)
        make_card("nano", "Текстовый редактор", is_installed=True)

    # Привязываем события
    window.ManagersListWidget.itemClicked.connect(on_distro_click)
    window.InstalledButton.clicked.connect(on_installed_click)

    # Выбираем первый дистрибутив по умолчанию при запуске
    window.ManagersListWidget.setCurrentRow(0)
    on_distro_click(window.ManagersListWidget.item(0))

    # Запуск
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()