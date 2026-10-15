from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from dashboard import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PQ-AI Provenance")
    app.setOrganizationName("PQ-AI")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
