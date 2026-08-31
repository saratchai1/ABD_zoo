import copy
import sys
import uuid

import fitz
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import fast_main
import main as legacy
import pdf_ops
from dark_theme import install_dark_theme
from pdf_ops import detect_sheet_number_box_on_page

APP_NAME = "PDF Drawing Tool V2.5.4 — Dark CAD Responsive"
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
    _, ey1, _, ey2 = erase
    center_x = (fx1 + fx2) / 2.0

    full_width = max(0.0, fx2 - fx1)
    erase_width = max(0.0, erase[2] - erase[0])

    write_width = min(erase_width * 0.68, full_width * 0.38)
    if write_width <= 0:
        write_width = full_width * 0.36

    half = write_width / 2.0
    x1 = max(fx1 + full_width * 0.03, center_x - half)
    x2 = min(fx2 - full_width * 0.03, center_x + half)

    clipped_width = max(0.0, x2 - x1)
    x1 = center_x - clipped_width / 2.0
    x2 = center_x + clipped_width / 2.0

    return [x1, ey1, x2, ey2]


def preview_effective_elements(elements, detected):
    """Return preview-only elements resolved against the current page.

    V2.5.2 re-detected the cell only during export, so the red dashed preview
    could still show the stored position from the first detected page. V2.5.3+
    applies the same page-local geometry to the on-screen preview.
    """
    if not detected:
        return elements

    write_box = centered_write_box(detected)
    erase_box = list(detected.get("number_box_norm") or detected["box_norm"])
    effective = []
    for element in elements:
        if element.get("type") == "sheet_number" and element.get("follow_detected_cell", False):
            local = copy.deepcopy(element)
            local["box"] = list(write_box)
            local["erase_box"] = list(erase_box)
            effective.append(local)
        else:
            effective.append(element)
    return effective


def remove_cad_comment_annotations(page, mode: str) -> int:
    """Remove CAD comment / sticky-note annotations robustly.

    AutoCAD SHX exports are not consistent: many pages identify the yellow
    sticky notes as "AutoCAD SHX Text", while other pages expose the exact same
    visible yellow icon only as a generic PDF Text annotation. Older builds only
    removed the first form, which is why some pages still showed yellow notes.

    In the recommended ``shx`` mode we now remove BOTH:
      * annotations explicitly identified as AutoCAD SHX text
      * generic PDF Text / sticky-note annotations (the yellow speech bubbles)

    ``all_text`` additionally removes FreeText annotations. ``keep`` leaves all
    annotations untouched.
    """
    if mode == "keep":
        return 0

    removed = 0
    for annot in list(page.annots() or []):
        try:
            type_name = str(annot.type[1]).strip().lower()
        except Exception:
            type_name = ""

        info = annot.info or {}
        metadata = " ".join(
            str(info.get(key, ""))
            for key in ("title", "subject", "content", "name")
        ).lower()

        is_shx = (
            "autocad shx" in metadata
            or "shx text" in metadata
            or "autocadshx" in metadata.replace(" ", "")
        )
        is_sticky_note = type_name in {"text", "popup"}
        is_free_text = type_name in {"freetext", "free text"}

        if mode == "shx":
            should_remove = is_shx or is_sticky_note
        elif mode == "all_text":
            should_remove = is_shx or is_sticky_note or is_free_text
        else:
            should_remove = is_shx

        if should_remove:
            try:
                page.delete_annot(annot)
                removed += 1
            except Exception:
                pass

    return removed


# export_editor() was imported by fast_main earlier, but its global function
# lookup still resolves through the pdf_ops module. Replacing the function here
# upgrades annotation cleanup without changing the stable numbering/export flow.
pdf_ops.delete_annotations = remove_cad_comment_annotations


class AnnotationAwareRenderJob(fast_main.RenderJob):
    """Render preview without yellow comments when cleanup is enabled."""

    def __init__(self, token, key, path, page_index, parent=None):
        super().__init__(token, key, path, page_index, parent)
        cleanup_mode = "shx"
        try:
            cleanup_mode = str(parent.cleanup_combo.currentData() or "shx")
        except Exception:
            pass
        self.show_annotations = cleanup_mode == "keep"

    def run(self):
        try:
            with fitz.open(self.path) as doc:
                page = doc[self.page_index]
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(fast_main.RENDER_SCALE, fast_main.RENDER_SCALE),
                    alpha=False,
                    annots=self.show_annotations,
                )
                image = fast_main.QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    fast_main.QImage.Format.Format_RGB888,
                ).copy()
                page_pts = (float(page.rect.width), float(page.rect.height))
            self.result.emit(self.token, self.key, image, page_pts)
        except Exception as exc:
            self.error.emit(self.token, self.key, str(exc))


# FastEditorTab resolves RenderJob from the fast_main module at runtime, so this
# keeps all async/cache behavior unchanged while only changing annotation paint.
fast_main.RenderJob = AnnotationAwareRenderJob


def _separator(parent=None):
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setFixedWidth(1)
    line.setMinimumHeight(24)
    return line


class CenteredEditorTab(fast_main.FastEditorTab):
    """V2.5.4 follows sheet cells per page and removes yellow CAD comments."""

    def __init__(self):
        self._preview_sheet_detection_cache = {}
        super().__init__()
        self._install_responsive_toolbar()
        self._install_annotation_cleanup_ui()

    def _install_annotation_cleanup_ui(self):
        idx = self.cleanup_combo.findData("shx")
        if idx >= 0:
            self.cleanup_combo.setItemText(
                idx,
                "Remove yellow CAD comments + AutoCAD SHX (recommended)",
            )
        idx = self.cleanup_combo.findData("all_text")
        if idx >= 0:
            self.cleanup_combo.setItemText(
                idx,
                "Remove yellow comments + SHX + FreeText",
            )
        self.cleanup_combo.currentIndexChanged.connect(self._on_cleanup_preview_changed)

    def _on_cleanup_preview_changed(self, *_):
        # Preview cache contains rendered page pixels, including annotation
        # visibility. Re-render when the cleanup policy changes.
        self._render_cache.clear()
        if self.pages:
            self.render_current_page()

    def _install_responsive_toolbar(self):
        center = self.view.parentWidget()
        if center is None or center.layout() is None:
            return

        center_layout = center.layout()

        # The legacy UI puts navigation and every editor/view control in two
        # dense rows. Detach those two layouts while keeping their widgets.
        detached = []
        for _ in range(2):
            if center_layout.count() <= 0:
                break
            item = center_layout.itemAt(0)
            if item is None or item.layout() is None:
                break
            detached_item = center_layout.takeAt(0)
            if detached_item and detached_item.layout():
                detached.append(detached_item.layout())

        toolbar_shell = QWidget(center)
        toolbar_shell.setObjectName("responsiveToolbarShell")
        shell_layout = QVBoxLayout(toolbar_shell)
        shell_layout.setContentsMargins(0, 0, 0, 2)
        shell_layout.setSpacing(6)

        # --- Row 1: editing tools only -------------------------------------
        edit_row = QWidget(toolbar_shell)
        edit_row.setObjectName("responsiveEditToolbar")
        edit_layout = QHBoxLayout(edit_row)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(5)

        tools = {b.text().strip(): b for b in center.findChildren(QToolButton)}
        edit_specs = [
            ("Select", "↖ Select", 70),
            ("Add Text", "T Text", 62),
            ("Sheet No.", "# Sheet", 68),
            ("Erase Sheet No.", "⌫ Sheet", 76),
            ("Erase Scale", "⌫ Scale", 76),
            ("Image", "▧ Image", 70),
            ("Rectangle", "▭ Rect", 66),
        ]

        for original, label, width in edit_specs:
            button = tools.get(original)
            if button is None:
                continue
            button.setText(label)
            button.setToolTip(original)
            button.setProperty("toolbar", True)
            button.setFixedWidth(width)
            button.setMinimumHeight(38)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            edit_layout.addWidget(button)

        edit_layout.addStretch(1)
        shell_layout.addWidget(edit_row)

        # --- Row 2: page navigation + history + viewport -------------------
        view_row = QWidget(toolbar_shell)
        view_row.setObjectName("responsiveViewToolbar")
        view_layout = QHBoxLayout(view_row)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(5)

        buttons = {b.text().strip(): b for b in center.findChildren(QPushButton)}
        undo = buttons.get("Undo")
        redo = buttons.get("Redo")
        zoom_out = buttons.get("−")
        zoom_100 = buttons.get("100%")
        zoom_in = buttons.get("+")
        fit_page = buttons.get("Fit Page")
        fit_width = buttons.get("Fit Width")

        if undo:
            undo.setText("↶")
            undo.setToolTip("Undo")
            undo.setFixedWidth(38)
            view_layout.addWidget(undo)
        if redo:
            redo.setText("↷")
            redo.setToolTip("Redo")
            redo.setFixedWidth(38)
            view_layout.addWidget(redo)

        view_layout.addWidget(_separator(view_row))

        self.prev_btn.setText("◀")
        self.next_btn.setText("▶")
        self.prev_btn.setToolTip("Previous page")
        self.next_btn.setToolTip("Next page")
        self.prev_btn.setFixedWidth(34)
        self.next_btn.setFixedWidth(34)
        self.page_spin.setFixedWidth(54)
        self.page_spin.setMinimumHeight(34)
        self.page_label.setMinimumWidth(72)
        self.page_label.setMaximumWidth(150)
        self.page_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        view_layout.addWidget(self.prev_btn)
        view_layout.addWidget(self.page_spin)
        view_layout.addWidget(self.next_btn)
        view_layout.addWidget(self.page_label)

        view_layout.addWidget(_separator(view_row))

        for button, label, tip, width in [
            (zoom_out, "−", "Zoom out", 34),
            (zoom_100, "100%", "Reset zoom", 54),
            (zoom_in, "+", "Zoom in", 34),
            (fit_page, "Fit", "Fit Page", 48),
            (fit_width, "Width", "Fit Width", 58),
        ]:
            if button is None:
                continue
            button.setText(label)
            button.setToolTip(tip)
            button.setFixedWidth(width)
            button.setMinimumHeight(34)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            view_layout.addWidget(button)

        view_layout.addStretch(1)
        shell_layout.addWidget(view_row)

        center_layout.insertWidget(0, toolbar_shell)

        # Keep the preview as the dominant pane. The sidebars can shrink, but
        # not enough to crush the toolbar labels into one another.
        splitter = center.parentWidget()
        if splitter is not None and hasattr(splitter, "indexOf"):
            center_index = splitter.indexOf(center)
            if center_index >= 0:
                splitter.setChildrenCollapsible(False)
                splitter.setStretchFactor(center_index, 1)
                center.setMinimumWidth(560)

                if splitter.count() >= 3:
                    left = splitter.widget(0)
                    right = splitter.widget(2)
                    if left is not None:
                        left.setMinimumWidth(190)
                        left.setMaximumWidth(300)
                        splitter.setStretchFactor(0, 0)
                    if right is not None:
                        right.setMinimumWidth(250)
                        right.setMaximumWidth(390)
                        splitter.setStretchFactor(2, 0)
                    splitter.setSizes([220, 640, 300])

        self.measure_label.setWordWrap(True)
        self.measure_label.setMaximumHeight(48)
        self.measure_label.setText(
            "V2.5.4: sheet numbering still follows each page independently. "
            "Recommended Cleanup now removes generic yellow PDF comment bubbles as well as AutoCAD SHX notes."
        )

    def _current_page_sheet_detection(self):
        if not self.pages:
            return None
        if not any(
            e.get("type") == "sheet_number" and e.get("follow_detected_cell", False)
            for e in self.elements
        ):
            return None

        gi = min(self.page_spin.value() - 1, len(self.pages) - 1)
        path, page_index = self.pages[gi]
        key = (path, page_index, self._file_signature(path))
        if key in self._preview_sheet_detection_cache:
            return self._preview_sheet_detection_cache[key]

        detected = None
        try:
            with fitz.open(path) as doc:
                if 0 <= page_index < doc.page_count:
                    detected = detect_sheet_number_box_on_page(doc[page_index])
        except Exception:
            detected = None
        self._preview_sheet_detection_cache[key] = detected
        return detected

    def draw_elements(self):
        """Draw the current page using its own detected แผ่นที่ geometry."""
        if not self.render_size:
            return

        detected = self._current_page_sheet_detection()
        effective = preview_effective_elements(self.elements, detected)
        if effective is self.elements:
            return super().draw_elements()

        original = self.elements
        self.elements = effective
        try:
            super().draw_elements()
        finally:
            self.elements = original

    def clear_files(self):
        self._preview_sheet_detection_cache.clear()
        super().clear_files()

    def remove_selected_files(self):
        self._preview_sheet_detection_cache.clear()
        super().remove_selected_files()

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
            "follow_detected_cell": True,
            "sequence_type": self.sequence_combo.currentData(),
            "sequence_start": self.sequence_start.text().strip() or "1",
            "font_name": self.font_name(),
            "font_path": self.font_path(),
            "font_size": self.font_size.value(),
            "scope": {"mode": "all"},
        })

        self.detect_status.setText(
            "Sheet No.: AUTO-DETECTED ✓ — preview + export follow each page; yellow CAD comments are cleaned separately."
        )
        self.refresh_objects()
        self.draw_elements()
        self._finish_detect_callbacks(True)


class CenteredPDFDrawingTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1500, 900)
        # Fits a 1080-wide desktop without forcing the center toolbar to crush.
        self.setMinimumSize(1020, 700)

        tabs = QTabWidget()
        tabs.addTab(CenteredEditorTab(), "Editor")
        tabs.addTab(legacy.MergeTab(), "Merge")
        tabs.addTab(legacy.SplitTab(), "Split")
        self.setCentralWidget(tabs)

        self.statusBar().showMessage(
            "Ready  •  Per-page sheet tracking  •  Yellow CAD comment cleanup"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName(SETTINGS_ORG)
    app.setApplicationName(APP_NAME)
    window = CenteredPDFDrawingTool()
    install_dark_theme(app, window)
    window.show()
    sys.exit(app.exec())
