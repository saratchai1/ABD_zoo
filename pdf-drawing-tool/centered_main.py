import sys
import uuid

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget

import fast_main
import main as legacy
from dark_theme import install_dark_theme

APP_NAME = "PDF Drawing Tool V2.5 — Dark CAD"
SETTINGS_ORG = "TEAMG"


def centered_write_box(detected):
    """Return a narrow write box centered on the entire sheet-number cell.

    The erase box remains the conservative right-side number area. This
    separates two concerns:
      * erase safely without touching the printed 'แผ่นที่ :' label
      * place the replacement number at the true horizontal center of the cell
    """
    full = list(detected["box_norm"])
    erase = list(detected.get("number_box_norm") or full)

    fx1, fy1, fx2, fy2 = full
    ex1, ey1, ex2, ey2 = erase
    center_x = (fx1 + fx2) / 2.0

    full_width = max(0.0, fx2 - fx1)
    erase_width = max(0.0, ex2 - ex1)

    # Keep the preview / text box narrow so it does not cover the 'แผ่นที่ :'
    # label, but make its center exactly the center of the detected cell.
    write_width = min(erase_width * 0.68, full_width * 0.38)
    if write_width <= 0:
        write_width = full_width * 0.36

    half = write_width / 2.0
    x1 = max(fx1 + full_width * 0.03, center_x - half)
    x2 = min(fx2 - full_width * 0.03, center_x + half)

    # Re-center after clipping so the cell midpoint remains the target.
    clipped_width = max(0.0, x2 - x1)
    x1 = center_x - clipped_width / 2.0
    x2 = center_x + clipped_width / 2.0

    return [x1, ey1, x2, ey2]


class CenteredEditorTab(fast_main.FastEditorTab):
    def _on_detect_result(self, detected):
        silent = self._detect_silent
        self._detect_job = None
        self._detect_silent = True
        self.auto_detect_btn.setEnabled(True)

        if not detected:
            self.detect_status.setText(
                "Sheet No.: auto detect failed — use Sheet No. and drag around the number area manually."
            )
            if not silent:
                QMessageBox.warning(self, "Not detected", "Could not find the แผ่นที่ cell.")
            self._finish_detect_callbacks(False)
            return

        self.push_undo()
        erase_box = list(detected.get("number_box_norm") or detected["box_norm"])
        write_box = centered_write_box(detected)

        self.elements.append({
            "id": uuid.uuid4().hex,
            "type": "sheet_number",
            "box": write_box,
            "erase_box": erase_box,
            "erase_existing": True,
            "erase_mode": "text",
            "sequence_type": self.sequence_combo.currentData(),
            "sequence_start": self.sequence_start.text().strip() or "1",
            "font_name": self.font_name(),
            "font_path": self.font_path(),
            "font_size": self.font_size.value(),
            "scope": {"mode": "all"},
        })

        self.detect_status.setText(
            "Sheet No.: AUTO-DETECTED ✓ — replacement number centered on the full cell."
        )
        self.refresh_objects()
        self.draw_elements()
        self._finish_detect_callbacks(True)


class CenteredPDFDrawingTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1600, 920)
        self.setMinimumSize(1180, 720)

        tabs = QTabWidget()
        tabs.addTab(CenteredEditorTab(), "Editor")
        tabs.addTab(legacy.MergeTab(), "Merge")
        tabs.addTab(legacy.SplitTab(), "Split")
        self.setCentralWidget(tabs)

        self.statusBar().showMessage("Ready  •  Dark CAD Theme")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName(SETTINGS_ORG)
    app.setApplicationName(APP_NAME)
    window = CenteredPDFDrawingTool()
    install_dark_theme(app, window)
    window.show()
    sys.exit(app.exec())
