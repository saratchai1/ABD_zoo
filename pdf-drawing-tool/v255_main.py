import sys

import fitz
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

import centered_main
import fast_main
import main as legacy
import pdf_ops
from dark_theme import install_dark_theme

APP_NAME = "PDF Drawing Tool V2.5.5 — Dark CAD Responsive"
SETTINGS_ORG = "TEAMG"


def strip_all_pdf_comments(page, mode: str) -> int:
    """Remove every normal PDF annotation when cleanup is enabled.

    Previous versions tried to classify yellow AutoCAD comment bubbles by
    subtype / metadata. Real exported drawings are inconsistent and some of the
    same yellow bubbles use other annotation subtypes. V2.5.5 deliberately does
    not classify them: recommended cleanup removes every annotation returned by
    PyMuPDF's page.annots() API. Links and form widgets use separate APIs and are
    therefore not touched here.

    A repeated pass is used because deleting a parent annotation may expose or
    invalidate related popup annotations depending on the source PDF.
    """
    if str(mode or "").lower() == "keep":
        return 0

    removed = 0
    for _ in range(8):
        annotations = list(page.annots() or [])
        if not annotations:
            break

        pass_removed = 0
        for annot in annotations:
            try:
                page.delete_annot(annot)
                removed += 1
                pass_removed += 1
            except Exception:
                pass

        if pass_removed == 0:
            # Fallback for unusual annotation trees. Newer PyMuPDF exposes
            # annotation xrefs directly; try those without making export fail.
            try:
                xrefs = list(page.annot_xrefs())
            except Exception:
                xrefs = []
            for item in xrefs:
                try:
                    xref = item[0] if isinstance(item, (tuple, list)) else item
                    annot = page.load_annot(int(xref))
                    if annot is not None:
                        page.delete_annot(annot)
                        removed += 1
                        pass_removed += 1
                except Exception:
                    pass

        if pass_removed == 0:
            break

    return removed


# export_editor() looks up delete_annotations through pdf_ops at runtime, so
# this replaces only annotation cleanup. Sheet detection, numbering, erasure,
# sequencing and page-local placement remain exactly as in V2.5.4.
pdf_ops.delete_annotations = strip_all_pdf_comments


class GuaranteedCleanRenderJob(fast_main.RenderJob):
    """Never paint PDF annotations in preview unless user explicitly keeps them."""

    def __init__(self, token, key, path, page_index, parent=None):
        super().__init__(token, key, path, page_index, parent)
        cleanup_mode = "shx"
        try:
            cleanup_mode = str(parent.cleanup_combo.currentData() or "shx").lower()
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


# FastEditorTab resolves this module-level class dynamically when rendering.
fast_main.RenderJob = GuaranteedCleanRenderJob


class V255EditorTab(centered_main.CenteredEditorTab):
    """Keep V2.5.4 numbering behavior; make annotation cleanup unconditional."""

    def _install_annotation_cleanup_ui(self):
        idx = self.cleanup_combo.findData("shx")
        if idx >= 0:
            self.cleanup_combo.setItemText(
                idx,
                "Remove ALL PDF comments / yellow annotations (recommended)",
            )
            self.cleanup_combo.setCurrentIndex(idx)

        idx = self.cleanup_combo.findData("all_text")
        if idx >= 0:
            self.cleanup_combo.setItemText(
                idx,
                "Remove ALL PDF comments / annotations",
            )

        self.cleanup_combo.currentIndexChanged.connect(self._on_cleanup_preview_changed)

    def _on_cleanup_preview_changed(self, *_):
        # Render-cache pixels include annotation visibility. Force a clean
        # re-render whenever cleanup policy changes.
        self._render_cache.clear()
        self._render_inflight.clear()
        if self.pages:
            self.render_current_page()


class PDFDrawingToolV255(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1500, 900)
        self.setMinimumSize(1020, 700)

        tabs = QTabWidget()
        tabs.addTab(V255EditorTab(), "Editor")
        tabs.addTab(legacy.MergeTab(), "Merge")
        tabs.addTab(legacy.SplitTab(), "Split")
        self.setCentralWidget(tabs)

        self.statusBar().showMessage(
            "Ready  •  Per-page sheet numbering preserved  •  All PDF comments removed"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName(SETTINGS_ORG)
    app.setApplicationName(APP_NAME)
    window = PDFDrawingToolV255()
    install_dark_theme(app, window)
    window.show()
    sys.exit(app.exec())
