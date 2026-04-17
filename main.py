import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.uic import loadUi

def main():
    app = QApplication(sys.argv)

    window = loadUi("ui/main_window.ui")

    with open("assets/main_window.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    window.menuBar().setVisible(False)
    window.statusBar().setVisible(False)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()