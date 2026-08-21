"""Entry point for NeoTranscribe."""

import sys

from PyQt6.QtWidgets import QApplication

from src.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NeoTranscribe")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
