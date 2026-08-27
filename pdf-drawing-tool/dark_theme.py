from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsView,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollBar,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QToolButton,
    QWidget,
)


DARK_STYLESHEET = r"""
/* ===== PDF Drawing Tool — Dark CAD Theme ===== */

QWidget {
    background-color: #11161d;
    color: #e7ebf0;
    font-family: "Segoe UI";
    font-size: 13px;
    selection-background-color: #245da8;
    selection-color: #ffffff;
}

QMainWindow,
QDialog {
    background-color: #0f141a;
}

QLabel {
    background: transparent;
    color: #d9dee6;
}

QLabel[kind="section"] {
    color: #f3f6fa;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 0px 5px 2px;
}

QLabel[kind="muted"] {
    color: #8d97a5;
}

QLabel[kind="hint"] {
    color: #929dab;
    font-size: 12px;
    padding: 5px 8px;
}

/* ===== Tabs ===== */
QTabWidget::pane {
    border: 0px;
    border-top: 1px solid #202833;
    background: #11161d;
}

QTabBar {
    background: #0f141a;
}

QTabBar::tab {
    background: transparent;
    color: #919ba8;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 12px 23px 10px 23px;
    min-width: 68px;
    font-size: 13px;
}

QTabBar::tab:hover {
    color: #e4e9ef;
    background: #151b23;
}

QTabBar::tab:selected {
    color: #ffffff;
    border-bottom: 2px solid #3b82f6;
    background: #151b23;
    font-weight: 600;
}

/* ===== Panels / group boxes ===== */
QGroupBox {
    background: #171d25;
    border: 1px solid #252e39;
    border-radius: 9px;
    margin-top: 16px;
    padding: 14px 10px 10px 10px;
    color: #f0f3f7;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 0 6px;
    color: #dce2e9;
    background: #171d25;
}

/* ===== Buttons ===== */
QPushButton,
QToolButton {
    background: #202731;
    color: #e5eaf0;
    border: 1px solid #313b48;
    border-radius: 7px;
    padding: 7px 12px;
    min-height: 22px;
    font-weight: 500;
}

QPushButton:hover,
QToolButton:hover {
    background: #29323e;
    border-color: #465466;
    color: #ffffff;
}

QPushButton:pressed,
QToolButton:pressed,
QToolButton:checked {
    background: #1c4f91;
    border-color: #3b82f6;
    color: #ffffff;
}

QPushButton:disabled,
QToolButton:disabled {
    background: #181e26;
    border-color: #252d37;
    color: #606a78;
}

QPushButton[role="primary"] {
    background: #2563c7;
    border: 1px solid #3478e5;
    color: #ffffff;
    font-size: 14px;
    font-weight: 650;
    min-height: 31px;
    padding: 8px 18px;
}

QPushButton[role="primary"]:hover {
    background: #2f72df;
    border-color: #5b96ef;
}

QPushButton[role="primary"]:pressed {
    background: #1f57b0;
}

QPushButton[role="danger"] {
    background: transparent;
    color: #f08a8a;
    border: 1px solid #56343a;
}

QPushButton[role="danger"]:hover {
    background: #3a2025;
    color: #ffb0b0;
    border-color: #8d474f;
}

QPushButton[role="ghost"] {
    background: transparent;
    border-color: transparent;
    color: #aab3bf;
    padding-left: 9px;
    padding-right: 9px;
}

QPushButton[role="ghost"]:hover {
    background: #202731;
    border-color: #2d3743;
    color: #ffffff;
}

QToolButton[toolbar="true"] {
    background: #1a2028;
    border: 1px solid #2b3440;
    padding: 7px 11px;
    min-height: 25px;
}

QToolButton[toolbar="true"]:hover {
    background: #252e39;
    border-color: #465466;
}

/* ===== Inputs ===== */
QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QPlainTextEdit {
    background: #131920;
    color: #eef2f6;
    border: 1px solid #303a47;
    border-radius: 6px;
    padding: 6px 9px;
    min-height: 23px;
}

QLineEdit:hover,
QComboBox:hover,
QSpinBox:hover,
QDoubleSpinBox:hover {
    border-color: #475566;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QPlainTextEdit:focus {
    border: 1px solid #3b82f6;
    background: #151c24;
}

QLineEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {
    background: #151a20;
    color: #606a77;
    border-color: #252d36;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
    background: transparent;
}

QComboBox QAbstractItemView {
    background: #171d25;
    color: #e6ebf1;
    border: 1px solid #364150;
    border-radius: 6px;
    selection-background-color: #214e85;
    selection-color: #ffffff;
    padding: 4px;
    outline: 0;
}

/* ===== Lists ===== */
QListWidget {
    background: #131920;
    color: #dce2e9;
    border: 1px solid #252e39;
    border-radius: 8px;
    padding: 5px;
    outline: 0;
}

QListWidget::item {
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 8px 8px;
    margin: 1px;
}

QListWidget::item:hover {
    background: #1d2530;
    border-color: #2a3441;
}

QListWidget::item:selected {
    background: #1e4779;
    border-color: #3269a9;
    color: #ffffff;
}

/* ===== Checkboxes ===== */
QCheckBox {
    background: transparent;
    color: #cbd2db;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #4a5665;
    background: #131920;
}

QCheckBox::indicator:hover {
    border-color: #3b82f6;
}

QCheckBox::indicator:checked {
    background: #2d6fd0;
    border-color: #4c8dea;
}

/* ===== Progress ===== */
QProgressBar {
    background: #151b22;
    border: 1px solid #2b3440;
    border-radius: 5px;
    color: #cbd2db;
    min-height: 9px;
    max-height: 9px;
    text-align: center;
}

QProgressBar::chunk {
    background: #3478df;
    border-radius: 4px;
}

/* ===== Splitters ===== */
QSplitter::handle {
    background: #202833;
}

QSplitter::handle:hover {
    background: #3b82f6;
}

/* ===== Scroll bars ===== */
QScrollBar:vertical {
    background: transparent;
    width: 11px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #3a4553;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: #526174;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 11px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background: #3a4553;
    border-radius: 5px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background: #526174;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
    width: 0px;
}

/* ===== Status / tooltips ===== */
QStatusBar {
    background: #10151b;
    color: #8893a1;
    border-top: 1px solid #242d38;
}

QToolTip {
    background: #222a34;
    color: #f4f7fa;
    border: 1px solid #445164;
    padding: 6px 8px;
}

QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #29333f;
}
"""


def build_dark_palette():
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#11161d"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e7ebf0"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#131920"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#171d25"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#222a34"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f4f7fa"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e7ebf0"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#202731"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e5eaf0"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#60a5fa"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#245da8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#6f7987"))
    return palette


def _refresh_style(widget):
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def polish_dark_ui(root):
    """Apply presentation-only refinements without changing PDF/editor logic."""

    # Tabs: compact CAD-style navigation.
    for tabs in root.findChildren(QTabWidget):
        tabs.setDocumentMode(True)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)

    # Splitter handles should be easy to grab but visually quiet.
    for splitter in root.findChildren(QSplitter):
        splitter.setHandleWidth(3)

    # Preview remains dark while the PDF page itself stays white.
    for view in root.findChildren(QGraphicsView):
        view.setBackgroundBrush(QColor("#0b1016"))
        view.setFrameShape(QFrame.Shape.NoFrame)

    for list_widget in root.findChildren(QListWidget):
        list_widget.setSpacing(2)
        list_widget.setUniformItemSizes(False)

    # Make form controls consistent and slightly less cramped.
    controls = []
    controls += root.findChildren(QLineEdit)
    controls += root.findChildren(QComboBox)
    controls += root.findChildren(QSpinBox)
    controls += root.findChildren(QDoubleSpinBox)
    for control in controls:
        control.setMinimumHeight(34)

    for edit in root.findChildren(QPlainTextEdit):
        edit.setFrameShape(QFrame.Shape.NoFrame)

    for group in root.findChildren(QGroupBox):
        if group.layout():
            group.layout().setSpacing(9)

    # Section labels on the left column and helper/status copy.
    for label in root.findChildren(QLabel):
        text = label.text().strip().lower()
        if text.startswith("files") or text == "added objects" or text == "objects":
            label.setProperty("kind", "section")
        elif "files /" in text or text.startswith("page "):
            label.setProperty("kind", "muted")
        elif "v2.4" in text or "sheet no." in text:
            label.setProperty("kind", "hint")
        _refresh_style(label)

    tool_text = {
        "Select": "↖  Select",
        "Add Text": "T  Text",
        "Sheet No.": "#  Sheet",
        "Erase Sheet No.": "⌫  Sheet",
        "Erase Scale": "⌫  Scale",
        "Image": "▧  Image",
        "Rectangle": "□  Rectangle",
    }

    for button in root.findChildren(QAbstractButton):
        original = button.text().strip()
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        if isinstance(button, QToolButton):
            button.setProperty("toolbar", True)
            if original in tool_text:
                button.setToolTip(original)
                button.setText(tool_text[original])
                button.setMinimumHeight(40)
                button.setMinimumWidth(76)

        if isinstance(button, QPushButton):
            low = original.lower()
            if original == "Export PDF" or low.startswith("exporting"):
                button.setProperty("role", "primary")
                button.setMinimumHeight(48)
            elif any(token in low for token in ("delete", "clear")):
                button.setProperty("role", "danger")
            elif original in {"Undo", "Redo", "Fit Page", "Fit Width", "100%", "+", "−", "◀", "▶"}:
                button.setProperty("role", "ghost")
            else:
                button.setProperty("role", "secondary")
                button.setMinimumHeight(max(button.minimumHeight(), 34))

            if original == "Remove selected":
                button.setText("Remove")
            elif original == "Delete selected object":
                button.setText("Delete object")
            elif original == "Save current editor preset":
                button.setText("Save preset")
            elif original == "Auto Detect Sheet No.":
                button.setText("Auto Detect")
                button.setToolTip("Auto Detect Sheet Number")

        _refresh_style(button)


def install_dark_theme(app, root):
    app.setStyle("Fusion")
    app.setPalette(build_dark_palette())
    app.setStyleSheet(DARK_STYLESHEET)
    polish_dark_ui(root)
