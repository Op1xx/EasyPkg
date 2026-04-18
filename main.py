import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.uic import loadUi
from core.distro_detector import get_distro_info

def main():
    app = QApplication(sys.argv)

    window = loadUi("ui/main_window.ui")

    with open("assets/main_window.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    window.menuBar().setVisible(False)
    window.statusBar().setVisible(False)

    info = get_distro_info()
    print(f"Система: {info['name']}")
    print(f"Менеджер: {info['manager']}")

    window.setWindowTitle(f"EasyPkg — {info['name']}")

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()