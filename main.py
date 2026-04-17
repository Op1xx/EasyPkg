#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EasyPkg - Визуальный менеджер пакетов для Linux
Основной файл запуска приложения

Загружает UI из Qt Designer, применяет стили и инициализирует логику.
"""

import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QFrame, QLabel, QPushButton, QVBoxLayout, QScrollArea, QWidget
from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSignal


class PackageCard(QFrame):
    """
    Карточка пакета - динамически создаваемый виджет
    Отображает имя, описание и кнопку установки пакета
    """
    
    # Сигнал для запроса установки пакета
    install_requested = pyqtSignal(str)  # передаёт имя пакета
    
    def __init__(self, name: str, description: str, version: str = "", parent=None):
        super().__init__(parent)
        
        # Устанавливаем класс для стилизации через QSS
        self.setObjectName("PackageCard")
        self.setProperty("class", "PackageCard")
        
        # Основной layout карточки
        card_layout = QVBoxLayout(self)
        card_layout.setSpacing(6)
        card_layout.setContentsMargins(12, 12, 12, 12)
        
        # Название пакета (жирный текст)
        self.name_label = QLabel(name, self)
        self.name_label.setObjectName("PackageCardName")
        self.name_label.setProperty("class", "PackageCardName")
        self.name_label.setWordWrap(True)
        card_layout.addWidget(self.name_label)
        
        # Описание пакета (серый текст)
        self.desc_label = QLabel(description, self)
        self.desc_label.setObjectName("PackageCardDesc")
        self.desc_label.setProperty("class", "PackageCardDesc")
        self.desc_label.setWordWrap(True)
        card_layout.addWidget(self.desc_label)
        
        # Версия (опционально, серый мелкий текст)
        if version:
            self.version_label = QLabel(f"Версия: {version}", self)
            self.version_label.setObjectName("PackageCardVersion")
            self.version_label.setProperty("class", "PackageCardVersion")
            card_layout.addWidget(self.version_label)
        
        # Кнопка установки
        self.install_btn = QPushButton("Установить", self)
        self.install_btn.setObjectName("PackageCardInstallBtn")
        self.install_btn.setProperty("class", "PackageCardInstallBtn")
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.clicked.connect(lambda: self.install_requested.emit(name))
        card_layout.addWidget(self.install_btn)
        
        # Фиксированная минимальная высота для единообразия
        self.setMinimumHeight(140)


class EasyPkgMainWindow(QMainWindow):
    """
    Главное окно приложения EasyPkg
    Загружает UI, применяет стили, управляет логикой отображения пакетов
    """
    
    def __init__(self):
        super().__init__()
        
        # Определяем путь к текущему файлу для относительных путей
        self.base_path = Path(__file__).parent
        
        # Загружаем UI из файла .ui
        ui_path = self.base_path / "ui" / "main_window.ui"
        uic.loadUi(str(ui_path), self)
        
        # Применяем глобальные стили
        self._load_styles()
        
        # Инициализация компонентов интерфейса
        self._init_components()
        
        # Подключение сигналов
        self._connect_signals()
        
        # Пример данных для демонстрации (будет заменено на реальную логику)
        self._populate_demo_packages()
    
    def _load_styles(self) -> None:
        """Загружает и применяет QSS стили из assets/styles.qss"""
        styles_path = self.base_path / "assets" / "styles.qss"
        
        if styles_path.exists():
            with open(styles_path, "r", encoding="utf-8") as f:
                styles = f.read()
            self.setStyleSheet(styles)
            print(f"[OK] Стили загружены из {styles_path}")
        else:
            print(f"[WARN] Файл стилей не найден: {styles_path}")
    
    def _init_components(self) -> None:
        """Инициализация компонентов после загрузки UI"""
        # Получаем ссылки на ключевые элементы
        self.managers_list = self.findChild(QWidget, "ManagersListWidget")
        self.installed_btn = self.findChild(QPushButton, "InstalledButton")
        self.pkgs_frame = self.findChild(QFrame, "PkgsFrame")
        self.pkgs_layout = self.findChild(QWidget, "PkgsLayout")
        self.search_input = self.findChild(QWidget, "SearchbarLineEdit")
        self.search_btn = self.findChild(QPushButton, "SearchButton")
        
        # Добавляем элементы в список менеджеров (дистрибутивы)
        distros = [
            "Arch Linux (pacman/yay)",
            "Fedora (dnf)",
            "Debian/Ubuntu (apt)",
            "Astra Linux",
            "РЕД ОС",
            "МОС / ALT Linux"
        ]
        
        if self.managers_list:
            from PyQt6.QtWidgets import QListWidgetItem
            for distro in distros:
                item = QListWidgetItem(distro)
                self.managers_list.addItem(item)
    
    def _connect_signals(self) -> None:
        """Подключение сигналов и слотов"""
        # Клик по элементу списка менеджеров
        if self.managers_list:
            self.managers_list.itemClicked.connect(self._on_distro_selected)
        
        # Кнопка "Скачанные пакеты"
        if self.installed_btn:
            self.installed_btn.clicked.connect(self._on_installed_clicked)
        
        # Кнопка поиска
        if self.search_btn:
            self.search_btn.clicked.connect(self._on_search_clicked)
        
        # Enter в поле поиска
        if self.search_input:
            self.search_input.returnPressed.connect(self._on_search_clicked)
    
    def _clear_packages_layout(self) -> None:
        """Очищает PkgsLayout от всех карточек пакетов"""
        if not self.pkgs_layout:
            return
        
        # Удаляем все виджеты из layout
        while self.pkgs_layout.count():
            item = self.pkgs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _add_package_card(self, name: str, desc: str, version: str = "") -> None:
        """
        Добавляет карточку пакета в PkgsLayout
        
        Args:
            name: Название пакета
            desc: Описание пакета
            version: Версия пакета (опционально)
        """
        if not self.pkgs_layout:
            return
        
        # Создаём карточку
        card = PackageCard(name, desc, version)
        card.install_requested.connect(self._on_package_install_requested)
        
        # Добавляем в grid layout
        # Получаем текущее количество строк/колонок
        row_count = self.pkgs_layout.rowCount() if hasattr(self.pkgs_layout, 'rowCount') else 0
        
        # Для QGridLayout добавляем по порядку
        # Находим первую свободную позицию
        added = False
        for row in range(10):  # Максимум 10 строк
            for col in range(3):  # 3 колонки
                if self.pkgs_layout.itemAtPosition(row, col) is None:
                    self.pkgs_layout.addWidget(card, row, col)
                    added = True
                    break
            if added:
                break
        
        # Если не удалось добавить в сетку, просто добавляем как следующий элемент
        if not added:
            self.pkgs_layout.addWidget(card)
    
    def _populate_demo_packages(self) -> None:
        """Заполняет демонстрационными данными (для тестирования)"""
        demo_packages = [
            ("firefox", "Веб-браузер Mozilla Firefox", "120.0"),
            ("vlc", "Видеоплеер VLC media player", "3.0.20"),
            ("gimp", "Графический редактор GIMP", "2.10.36"),
            ("vscode", "Редактор кода Visual Studio Code", "1.85.0"),
            ("python3", "Язык программирования Python 3", "3.11.7"),
            ("git", "Система контроля версий Git", "2.43.0"),
        ]
        
        for name, desc, version in demo_packages:
            self._add_package_card(name, desc, version)
    
    # === Обработчики событий ===
    
    def _on_distro_selected(self, item) -> None:
        """Обработчик выбора дистрибутива из списка"""
        distro_name = item.text()
        print(f"[INFO] Выбран дистрибутив: {distro_name}")
        
        # Очищаем текущие пакеты
        self._clear_packages_layout()
        
        # Здесь будет логика загрузки пакетов для конкретного дистрибутива
        # Пока показываем демо-данные
        self.statusBar().showMessage(f"Пакеты для: {distro_name}", 3000)
        self._populate_demo_packages()
    
    def _on_installed_clicked(self) -> None:
        """Обработчик кнопки 'Скачанные пакеты'"""
        print("[INFO] Показ установленных пакетов")
        
        self._clear_packages_layout()
        self.statusBar().showMessage("Показ установленных пакетов...", 2000)
        
        # Демо: показываем "установленные" пакеты
        installed_demo = [
            ("bash", "Bourne Again SHell", "5.2.21"),
            ("coreutils", "Основные утилиты GNU", "9.4"),
        ]
        
        for name, desc, version in installed_demo:
            self._add_package_card(name, desc, version)
    
    def _on_search_clicked(self) -> None:
        """Обработчик кнопки поиска"""
        if not self.search_input:
            return
        
        query = self.search_input.text().strip()
        if not query:
            self.statusBar().showMessage("Введите поисковый запрос", 2000)
            return
        
        print(f"[INFO] Поиск: {query}")
        self.statusBar().showMessage(f"Поиск: {query}...", 2000)
        
        # Очищаем и показываем результаты (демо)
        self._clear_packages_layout()
        
        # Фильтруем демо-пакеты по запросу
        demo_packages = [
            ("firefox", "Веб-браузер Mozilla Firefox", "120.0"),
            ("firefox-dev", "Firefox Developer Edition", "121.0b5"),
            ("thunderbird", "Почтовый клиент Thunderbird", "115.6.0"),
        ]
        
        for name, desc, version in demo_packages:
            if query.lower() in name.lower() or query.lower() in desc.lower():
                self._add_package_card(name, desc, version)
    
    def _on_package_install_requested(self, package_name: str) -> None:
        """
        Обработчик запроса на установку пакета
        
        Args:
            package_name: Имя пакета для установки
        """
        print(f"[INFO] Запрошена установка пакета: {package_name}")
        self.statusBar().showMessage(f"Установка: {package_name}...", 3000)
        
        # Здесь будет вызов core/runner.py для выполнения команды установки
        # TODO: Интеграция с бэкендом


def main():
    """Точка входа в приложение"""
    
    # Создаём приложение
    app = QApplication(sys.argv)
    app.setApplicationName("EasyPkg")
    app.setOrganizationName("EasyPkg Project")
    
    # Устанавливаем стиль шрифта для всего приложения
    font = app.font()
    font.setPointSize(13)
    app.setFont(font)
    
    # Создаём и показываем главное окно
    window = EasyPkgMainWindow()
    window.show()
    
    # Запускаем цикл событий
    sys.exit(app.exec())


if __name__ == "__main__":
    main()