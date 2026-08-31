import copy
import sys
import uuid

import fitz
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget

import centered_main
import fast_main
import main as legacy
import pdf_ops
import v255_main
from dark_theme import install_dark_theme
from sheet_detector_v260 import (
    robust_detect_sheet_number_box,
    robust_detect_sheet_number_box_on_page,
)

APP_NAME = "PDF Drawing Tool V2.6.0 — Verified Cell Center"
SETTINGS_ORG = "TEAMG"


# Keep original detectors only as validated last-resort fallbacks.
_ORIGINAL_PAGE_DETECTOR = pdf_ops.detect_sheet_number_box_on_page
_ORIGINAL_FILE_DETECTOR = pdf_ops.detect_sheet_number_box
_ORIGINAL_PREPARE_ERASURE = pdf_ops.prepare_erasure
_ORIGINAL_APPLY_ELEMENT = pdf_ops.apply_editor_element


def precise_centered_write_box(detected):
    """Create a narrow write box whose center is exactly the detected cell center.

    V2.6.0 no longer derives vertical placement from a previous-page erase box.
    Both X and Y are calculated from the full title-block cell detected on the
    current page, with symmetric margins around its true center.
    """
    full = [float(v) for v in detected["box_norm"]]
    x1, y1, x2, y2 = full
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0

    # Keep the number narrow enough not to cover the printed "แผ่นที่ :" label,
    # but center the write rectangle on the entire physical cell.
    write_w = width * 0.34
    write_h = height * 0.78
    if write_w <= 0:
        write_w = width
    if write_h <= 0:
        write_h = height

    return [
        cx - write_w / 2.0,
        cy - write_h / 2.0,
        cx + write_w / 2.0,
        cy + write_h / 2.0,
    ]


def _detect_page(page, reference_box=None):
    return robust_detect_sheet_number_box_on_page(
        page,
        reference_box=reference_box,
        original_detector=_ORIGINAL_PAGE_DETECTOR,
    )


def _detect_file(path, max_pages=20):
    return robust_detect_sheet_number_box(
        path,
        max_pages=max_pages,
        original_detector=_ORIGINAL_PAGE_DETECTOR,
    )


# Use the V2.6 detector everywhere the old program resolves detection dynamically.
pdf_ops.detect_sheet_number_box_on_page = _detect_page
pdf_ops.detect_sheet_number_box = _detect_file
fast_main.detect_sheet_number_box = _detect_file
centered_main.detect_sheet_number_box_on_page = _detect_page
centered_main.centered_write_box = precise_centered_write_box
pdf_ops._centered_write_box = precise_centered_write_box


def _reference_box_from_elements(elements):
    for element in elements:
        if element.get("type") == "sheet_number" and element.get("follow_detected_cell", False):
            ref = element.get("reference_cell_norm")
            if ref and len(ref) == 4:
                return list(ref)
    return None


def v260_page_local_elements(page, elements, global_page_index, log_cb=None):
    """Resolve an auto sheet-number element from the current page only.

    The old code reused its stored position when a page detector failed. That is
    exactly how a number could appear one row above the real แผ่นที่ cell. V2.6.0
    never does that. It first performs anchor + local grid detection, then a
    reference-grid match. If both fail, the number is skipped on that page rather
    than written in a known-wrong location.
    """
    followers = [
        e for e in elements
        if e.get("type") == "sheet_number" and e.get("follow_detected_cell", False)
    ]
    if not followers:
        return elements, False, False

    reference_box = _reference_box_from_elements(elements)
    detected = _detect_page(page, reference_box=reference_box)

    effective = []
    if detected:
        write_box = precise_centered_write_box(detected)
        erase_box = list(detected.get("number_box_norm") or detected["box_norm"])
        for element in elements:
            if element.get("type") == "sheet_number" and element.get("follow_detected_cell", False):
                local = dict(element)
                local["box"] = list(write_box)
                local["erase_box"] = list(erase_box)
                local["detected_cell_norm"] = list(detected["box_norm"])
                local["detection_method"] = detected.get("method", "v260")
                local.pop("_skip_sheet_number", None)
                effective.append(local)
            else:
                effective.append(element)
        return effective, True, False

    # Never write / erase at the stale coordinates from another page.
    for element in elements:
        if element.get("type") == "sheet_number" and element.get("follow_detected_cell", False):
            local = dict(element)
            local["_skip_sheet_number"] = True
            effective.append(local)
        else:
            effective.append(element)

    if log_cb:
        log_cb(
            f"  Page {global_page_index + 1}: could not verify the แผ่นที่ cell; "
            "sheet number skipped to prevent wrong placement."
        )
    return effective, False, True


pdf_ops._page_local_elements = v260_page_local_elements


def v260_prepare_erasure(page, element, global_page_index):
    if element.get("_skip_sheet_number"):
        return False, False, 0
    return _ORIGINAL_PREPARE_ERASURE(page, element, global_page_index)


def v260_apply_editor_element(page, element, global_page_index):
    if element.get("_skip_sheet_number"):
        return
    return _ORIGINAL_APPLY_ELEMENT(page, element, global_page_index)


pdf_ops.prepare_erasure = v260_prepare_erasure
pdf_ops.apply_editor_element = v260_apply_editor_element


class V260EditorTab(v255_main.V255EditorTab):
    """V2.5.5 cleanup + V2.6.0 verified per-page sheet-cell centering."""

    def __init__(self):
        super().__init__()
        self.measure_label.setText(
            "V2.6.0 VERIFIED CELL CENTER: every auto sheet number is re-detected from the current "
            "page's actual title-block grid. Stored coordinates are never reused after a failed detection."
        )

    def _reference_cell_norm(self):
        return _reference_box_from_elements(self.elements)

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
        reference = self._reference_cell_norm()
        ref_key = tuple(round(float(v), 7) for v in reference) if reference else None
        key = (path, page_index, self._file_signature(path), ref_key)
        if key in self._preview_sheet_detection_cache:
            return self._preview_sheet_detection_cache[key]

        detected = None
        try:
            with fitz.open(path) as doc:
                if 0 <= page_index < doc.page_count:
                    detected = _detect_page(doc[page_index], reference_box=reference)
        except Exception:
            detected = None
        self._preview_sheet_detection_cache[key] = detected
        return detected

    def draw_elements(self):
        if not self.render_size:
            return

        detected = self._current_page_sheet_detection()
        if detected:
            effective = centered_main.preview_effective_elements(self.elements, detected)
        else:
            # If current page cannot be verified, do not show a stale red box / number
            # from another page. The original PDF underneath remains visible.
            effective = [
                e for e in self.elements
                if not (e.get("type") == "sheet_number" and e.get("follow_detected_cell", False))
            ]

        original = self.elements
        self.elements = effective
        try:
            # Call the original editor draw implementation directly so the V2.5.x
            # preview wrapper cannot substitute an old box after detection failure.
            legacy.EditorTab.draw_elements(self)
        finally:
            self.elements = original

    def _on_detect_result(self, detected):
        silent = self._detect_silent
        self._detect_job = None
        self._detect_silent = True
        self.auto_detect_btn.setEnabled(True)

        if not detected:
            self.detect_status.setText(
                "Sheet No.: V2.6.0 could not verify a title-block cell. No guessed position was created."
            )
            if not silent:
                QMessageBox.warning(
                    self,
                    "Sheet cell not verified",
                    "Could not verify the แผ่นที่ cell from the actual title-block borders.",
                )
            self._finish_detect_callbacks(False)
            return

        self.push_undo()
        erase_box = list(detected.get("number_box_norm") or detected["box_norm"])
        write_box = precise_centered_write_box(detected)
        self.elements.append({
            "id": uuid.uuid4().hex,
            "type": "sheet_number",
            "box": write_box,
            "erase_box": erase_box,
            "erase_existing": True,
            "erase_mode": "text",
            "follow_detected_cell": True,
            "reference_cell_norm": list(detected["box_norm"]),
            "detector_version": "v260",
            "sequence_type": self.sequence_combo.currentData(),
            "sequence_start": self.sequence_start.text().strip() or "1",
            "font_name": self.font_name(),
            "font_path": self.font_path(),
            "font_size": self.font_size.value(),
            "scope": {"mode": "all"},
        })

        self._preview_sheet_detection_cache.clear()
        self.detect_status.setText(
            "Sheet No.: V2.6.0 VERIFIED ✓ — actual cell borders + page-local center; no stale-position fallback."
        )
        self.refresh_objects()
        self.draw_elements()
        self._finish_detect_callbacks(True)


class PDFDrawingToolV260(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1500, 900)
        self.setMinimumSize(1020, 700)

        tabs = QTabWidget()
        tabs.addTab(V260EditorTab(), "Editor")
        tabs.addTab(legacy.MergeTab(), "Merge")
        tabs.addTab(legacy.SplitTab(), "Split")
        self.setCentralWidget(tabs)

        self.statusBar().showMessage(
            "V2.6.0  •  VERIFIED CELL CENTER  •  Per-page grid detection  •  V2.5.5 annotation cleanup"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName(SETTINGS_ORG)
    app.setApplicationName(APP_NAME)
    window = PDFDrawingToolV260()
    install_dark_theme(app, window)
    window.show()
    sys.exit(app.exec())
