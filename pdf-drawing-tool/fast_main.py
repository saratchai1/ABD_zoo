import copy
import json
import os
import sys
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import fitz
from PySide6.QtCore import QSettings, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QListWidgetItem, QMainWindow, QMessageBox, QTabWidget

import main as legacy
from pdf_ops import detect_sheet_number_box, export_editor

APP_NAME = "PDF Drawing Tool V2.4.1"
SETTINGS_ORG = "TEAMG"
SETTINGS_CACHE_KEY = "performance/font_registry_cache_v24"
RENDER_SCALE = 1.20
RENDER_CACHE_PAGES = 6


# Font enumeration on Windows can be noticeable at every launch. Reuse the
# registry result for up to seven days, while preserving V2.3 preset storage.
_original_font_registry_map = legacy.font_registry_map


def cached_font_registry_map():
    settings = QSettings(SETTINGS_ORG, "PDF Drawing Tool V2.3")
    raw = settings.value(SETTINGS_CACHE_KEY, "")
    if raw:
        try:
            payload = json.loads(raw)
            age = time.time() - float(payload.get("saved_at", 0))
            fonts = payload.get("fonts", {})
            if age < 7 * 24 * 3600 and fonts and all(Path(p).exists() for p in fonts.values()):
                return fonts
        except Exception:
            pass
    fonts = _original_font_registry_map()
    try:
        settings.setValue(
            SETTINGS_CACHE_KEY,
            json.dumps({"saved_at": time.time(), "fonts": fonts}, ensure_ascii=False),
        )
    except Exception:
        pass
    return fonts


legacy.font_registry_map = cached_font_registry_map


def file_signature(path):
    try:
        stat = os.stat(path)
        return (int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        return None


class InventoryJob(QThread):
    """Open PDFs and count pages away from the GUI thread."""
    result = Signal(int, object, object)

    def __init__(self, generation, paths, parent=None):
        super().__init__(parent)
        self.generation = generation
        self.paths = list(paths)

    def run(self):
        counts = {}
        errors = {}
        for path in self.paths:
            try:
                with fitz.open(path) as doc:
                    count = int(doc.page_count)
                counts[path] = (file_signature(path), count)
            except Exception as exc:
                errors[path] = str(exc)
        self.result.emit(self.generation, counts, errors)


class RenderJob(QThread):
    result = Signal(int, object, object, object)
    error = Signal(int, object, str)

    def __init__(self, token, key, path, page_index, parent=None):
        super().__init__(parent)
        self.token = token
        self.key = key
        self.path = path
        self.page_index = page_index

    def run(self):
        try:
            with fitz.open(self.path) as doc:
                page = doc[self.page_index]
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE),
                    alpha=False,
                )
                image = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format.Format_RGB888,
                ).copy()
                page_pts = (float(page.rect.width), float(page.rect.height))
            self.result.emit(self.token, self.key, image, page_pts)
        except Exception as exc:
            self.error.emit(self.token, self.key, str(exc))


class DetectJob(QThread):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = list(files)

    def run(self):
        try:
            detected = None
            for path in self.files:
                detected = detect_sheet_number_box(path)
                if detected:
                    break
            self.result.emit(detected)
        except Exception as exc:
            self.error.emit(str(exc))


class ExportJob(QThread):
    progress = Signal(int, int)
    log = Signal(str)
    result = Signal(object)
    error = Signal(str)

    def __init__(self, files, output, elements, cleanup_mode, merge, parent=None):
        super().__init__(parent)
        self.files = list(files)
        self.output = output
        self.elements = copy.deepcopy(elements)
        self.cleanup_mode = cleanup_mode
        self.merge = merge

    def run(self):
        try:
            result = export_editor(
                self.files,
                self.output,
                self.elements,
                cleanup_mode=self.cleanup_mode,
                merge=self.merge,
                progress_cb=lambda done, total: self.progress.emit(done, total),
                log_cb=lambda text: self.log.emit(str(text)),
            )
            self.result.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class FastEditorTab(legacy.EditorTab):
    def __init__(self):
        self._page_count_cache = {}
        self._inventory_generation = 0
        self._inventory_queue = []
        self._inventory_job = None
        self._render_cache = OrderedDict()
        self._render_inflight = set()
        self._render_token = 0
        self._pending_render = None
        self._jobs = []
        self._detect_job = None
        self._detect_silent = True
        self._detect_callbacks = []
        self._export_job = None
        super().__init__()

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(35)
        self._render_timer.timeout.connect(self._launch_pending_render)

        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(140)
        self._redraw_timer.timeout.connect(self.draw_elements)

        self._auto_detect_timer = QTimer(self)
        self._auto_detect_timer.setSingleShot(True)
        self._auto_detect_timer.setInterval(600)
        self._auto_detect_timer.timeout.connect(self._launch_idle_auto_detect)

        self.measure_label.setText(
            "V2.4.1: loading, page count, preview, Auto Detect and Export all run outside the UI thread. "
            "The window should stay responsive while a PDF is being opened."
        )

    def _track_job(self, job):
        self._jobs.append(job)

        def cleanup():
            try:
                self._jobs.remove(job)
            except ValueError:
                pass
            job.deleteLater()

        job.finished.connect(cleanup)
        job.start()
        return job

    def _file_signature(self, path):
        return file_signature(path)

    def _cached_page_count(self, path):
        """Never opens the PDF. Only returns metadata already produced by InventoryJob."""
        signature = self._file_signature(path)
        cached = self._page_count_cache.get(path)
        if cached and cached[0] == signature:
            return cached[1]
        return None

    def add_files(self, paths):
        existing = set(self.file_list.paths())
        new_paths = []
        for path in paths:
            if path in existing:
                continue
            item = QListWidgetItem(f"{Path(path).name} (loading…)")
            item.setData(legacy.Qt.ItemDataRole.UserRole, path)
            self.file_list.addItem(item)
            existing.add(path)
            new_paths.append(path)

        if not new_paths:
            return

        self._render_cache.clear()
        self.total_label.setText(f"Reading PDF metadata… {len(new_paths)} file(s)")
        self.page_label.setText("Opening PDF in background…")
        self._inventory_queue.extend(new_paths)
        self._start_inventory_if_needed()

    def _start_inventory_if_needed(self):
        if self._inventory_job and self._inventory_job.isRunning():
            return
        if not self._inventory_queue:
            return

        batch = self._inventory_queue[:]
        self._inventory_queue.clear()
        generation = self._inventory_generation
        job = InventoryJob(generation, batch, self)
        self._inventory_job = job
        job.result.connect(self._on_inventory_result)
        self._track_job(job)

    def _on_inventory_result(self, generation, counts, errors):
        self._inventory_job = None
        if generation != self._inventory_generation:
            self._start_inventory_if_needed()
            return

        for path, cache_value in counts.items():
            self._page_count_cache[path] = cache_value

        # Update list labels without touching the PDF again.
        for row in range(self.file_list.count() - 1, -1, -1):
            item = self.file_list.item(row)
            path = item.data(legacy.Qt.ItemDataRole.UserRole)
            if path in counts:
                count = counts[path][1]
                item.setText(f"{Path(path).name} ({count} pages)")
            elif path in errors:
                item.setText(f"{Path(path).name} (ERROR)")
                self.file_list.takeItem(row)

        if errors:
            first_path = next(iter(errors))
            QMessageBox.warning(
                self,
                "PDF error",
                f"Could not open {Path(first_path).name}:\n{errors[first_path]}",
            )

        self.rebuild_pages()
        self._start_inventory_if_needed()

    def remove_selected_files(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self._render_cache.clear()
        self.rebuild_pages()

    def clear_files(self):
        self._inventory_generation += 1
        self._inventory_queue.clear()
        self._render_cache.clear()
        self._page_count_cache.clear()
        self._auto_detect_timer.stop()
        super().clear_files()

    def rebuild_pages(self):
        self.pages = []
        waiting = 0
        for path in self.file_list.paths():
            count = self._cached_page_count(path)
            if count is None:
                waiting += 1
                continue
            self.pages.extend((path, i) for i in range(count))

        if waiting:
            self.total_label.setText(
                f"{self.file_list.count()} files / {len(self.pages)} pages ready — {waiting} loading"
            )
        else:
            self.total_label.setText(f"{self.file_list.count()} files / {len(self.pages)} pages")

        self.page_spin.setMaximum(max(1, len(self.pages)))
        self.page_spin.setValue(1)
        self.range_end.setValue(max(1, len(self.pages)))

        if self.pages:
            self.render_current_page()
            # Delay auto-detect until the first preview has had a chance to appear.
            if (
                not waiting
                and self.auto_detect_on_load.isChecked()
                and not any(e["type"] == "sheet_number" for e in self.elements)
            ):
                self._auto_detect_timer.start()
        elif waiting:
            self.scene.clear()
            self.page_label.setText("Opening PDF in background…")
        else:
            self.scene.clear()
            self.page_label.setText("Page 0 / 0")

    def _launch_idle_auto_detect(self):
        if self._inventory_job or self._inventory_queue:
            self._auto_detect_timer.start()
            return
        if self.pages and self.auto_detect_on_load.isChecked() and not any(
            e["type"] == "sheet_number" for e in self.elements
        ):
            self.auto_detect_sheet_number(True)

    def _cache_render(self, key, image, page_pts):
        if key in self._render_cache:
            self._render_cache.pop(key, None)
        self._render_cache[key] = (image, page_pts)
        while len(self._render_cache) > RENDER_CACHE_PAGES:
            self._render_cache.popitem(last=False)

    def render_current_page(self):
        if not self.pages:
            return
        gi = min(self.page_spin.value() - 1, len(self.pages) - 1)
        path, page_index = self.pages[gi]
        key = (path, page_index, self._file_signature(path))
        self._render_token += 1
        token = self._render_token
        self._pending_render = (token, key, path, page_index)

        cached = self._render_cache.get(key)
        if cached:
            self._render_cache.move_to_end(key)
            self._display_render(token, key, cached[0], cached[1])
            return

        self.page_label.setText(
            f"Page {gi + 1}/{len(self.pages)} — rendering {Path(path).name} in background…"
        )
        if hasattr(self, "_render_timer"):
            self._render_timer.start()
        else:
            self._launch_pending_render()

    def _launch_pending_render(self):
        pending = self._pending_render
        if not pending:
            return
        token, key, path, page_index = pending
        if key in self._render_cache:
            image, page_pts = self._render_cache[key]
            self._display_render(token, key, image, page_pts)
            return
        if key in self._render_inflight:
            return
        self._render_inflight.add(key)
        job = RenderJob(token, key, path, page_index, self)
        job.result.connect(self._on_render_result)
        job.error.connect(self._on_render_error)
        self._track_job(job)

    def _on_render_result(self, token, key, image, page_pts):
        self._render_inflight.discard(key)
        self._cache_render(key, image, page_pts)
        if token == self._render_token:
            self._display_render(token, key, image, page_pts)

    def _on_render_error(self, token, key, message):
        self._render_inflight.discard(key)
        if token == self._render_token:
            self.page_label.setText(f"Preview error: {message}")

    def _display_render(self, token, key, image, page_pts):
        if token != self._render_token or not self.pages:
            return
        gi = min(self.page_spin.value() - 1, len(self.pages) - 1)
        path, page_index = self.pages[gi]
        current_key = (path, page_index, self._file_signature(path))
        if current_key != key:
            return

        pixmap = QPixmap.fromImage(image)
        self.scene.clear()
        self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.render_size = (pixmap.width(), pixmap.height())
        self.page_pts = page_pts
        self.page_label.setText(f"Page {gi + 1}/{len(self.pages)} — {Path(path).name}")
        self.draw_elements()
        self.fit_page()
        self._prefetch_next(gi)

    def _prefetch_next(self, gi):
        next_gi = gi + 1
        if next_gi >= len(self.pages):
            return
        path, page_index = self.pages[next_gi]
        key = (path, page_index, self._file_signature(path))
        if key in self._render_cache or key in self._render_inflight:
            return
        self._render_inflight.add(key)
        job = RenderJob(-1, key, path, page_index, self)
        job.result.connect(self._on_prefetch_result)
        job.error.connect(self._on_render_error)
        self._track_job(job)

    def _on_prefetch_result(self, token, key, image, page_pts):
        self._render_inflight.discard(key)
        self._cache_render(key, image, page_pts)

    def auto_detect_sheet_number(self, silent=False, after=None):
        if not self.pages:
            if after:
                after(False)
            return False
        existing = next((e for e in self.elements if e["type"] == "sheet_number"), None)
        if existing:
            self.sync_sheet_number()
            if after:
                after(True)
            return True

        if after:
            self._detect_callbacks.append(after)
        self._detect_silent = self._detect_silent and silent if self._detect_job else silent

        if self._detect_job and self._detect_job.isRunning():
            return False

        self.auto_detect_btn.setEnabled(False)
        self.detect_status.setText("Sheet No.: detecting in background…")
        job = DetectJob(self.file_list.paths(), self)
        self._detect_job = job
        job.result.connect(self._on_detect_result)
        job.error.connect(self._on_detect_error)
        self._track_job(job)
        return False

    def _finish_detect_callbacks(self, success):
        callbacks = self._detect_callbacks[:]
        self._detect_callbacks.clear()
        for callback in callbacks:
            try:
                callback(success)
            except Exception:
                pass

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
        box = list(detected.get("number_box_norm") or detected["box_norm"])
        self.elements.append({
            "id": uuid.uuid4().hex,
            "type": "sheet_number",
            "box": box,
            "erase_box": box,
            "erase_existing": True,
            "erase_mode": "text",
            "sequence_type": self.sequence_combo.currentData(),
            "sequence_start": self.sequence_start.text().strip() or "1",
            "font_name": self.font_name(),
            "font_path": self.font_path(),
            "font_size": self.font_size.value(),
            "scope": {"mode": "all"},
        })
        self.detect_status.setText("Sheet No.: AUTO-DETECTED ✓ — background detection complete.")
        self.refresh_objects()
        self.draw_elements()
        self._finish_detect_callbacks(True)

    def _on_detect_error(self, message):
        silent = self._detect_silent
        self._detect_job = None
        self._detect_silent = True
        self.auto_detect_btn.setEnabled(True)
        self.detect_status.setText(f"Sheet No.: detection error — {message}")
        if not silent:
            QMessageBox.warning(self, "Auto Detect error", message)
        self._finish_detect_callbacks(False)

    def sync_sheet_number(self, *_):
        for element in self.elements:
            if element["type"] == "sheet_number":
                element.update(
                    sequence_type=self.sequence_combo.currentData(),
                    sequence_start=self.sequence_start.text().strip() or "1",
                    font_name=self.font_name(),
                    font_path=self.font_path(),
                    font_size=self.font_size.value(),
                )
        if hasattr(self, "_redraw_timer"):
            self._redraw_timer.start()
        elif self.render_size:
            self.draw_elements()

    def export_pdf(self):
        files = self.file_list.paths()
        if not files or (self._export_job and self._export_job.isRunning()):
            return
        if self._inventory_job or self._inventory_queue:
            QMessageBox.information(self, "Please wait", "PDF metadata is still loading in the background.")
            return

        if self.auto_detect_on_load.isChecked() and not any(e["type"] == "sheet_number" for e in self.elements):
            self.auto_detect_sheet_number(True, after=lambda _ok: self._begin_export())
            return
        self._begin_export()

    def _begin_export(self):
        files = self.file_list.paths()
        if not files:
            return
        if not self.elements:
            QMessageBox.warning(
                self,
                "Nothing to export",
                "Add an object, erase area, or Auto Detect Sheet No. first.",
            )
            return

        self.sync_sheet_number()
        merge = self.merge_after.isChecked()
        if merge:
            output, _ = legacy.QFileDialog.getSaveFileName(
                self,
                "Save PDF",
                "Edited_Merged.pdf",
                "PDF Files (*.pdf)",
            )
            if not output:
                return
            if not output.lower().endswith(".pdf"):
                output += ".pdf"
        else:
            output = legacy.QFileDialog.getExistingDirectory(self, "Output folder")
            if not output:
                return

        self.log.clear()
        self.progress.setValue(0)
        self.export_btn.setEnabled(False)
        self.export_btn.setText("Exporting in background…")

        job = ExportJob(
            files,
            output,
            copy.deepcopy(self.elements),
            self.cleanup_combo.currentData(),
            merge,
            self,
        )
        self._export_job = job
        job.progress.connect(self._on_export_progress)
        job.log.connect(self.log.appendPlainText)
        job.result.connect(self._on_export_result)
        job.error.connect(self._on_export_error)
        self._track_job(job)

    def _on_export_progress(self, done, total):
        self.progress.setValue(int(done * 100 / max(1, total)))

    def _restore_export_button(self):
        self._export_job = None
        self.export_btn.setEnabled(True)
        self.export_btn.setText("Export PDF")

    def _on_export_result(self, result):
        self.progress.setValue(100)
        self._restore_export_button()
        QMessageBox.information(
            self,
            "Finished",
            f"Exported {result['pages']} pages.\n"
            f"Annotations removed: {result['removed_annotations']}\n"
            f"Text annotations erased in selected areas: {result.get('erased_annotations', 0)}",
        )

    def _on_export_error(self, message):
        self._restore_export_button()
        QMessageBox.critical(self, "Export failed", message)


class FastPDFDrawingTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1600, 920)
        tabs = QTabWidget()
        tabs.addTab(FastEditorTab(), "Editor")
        tabs.addTab(legacy.MergeTab(), "Merge")
        tabs.addTab(legacy.SplitTab(), "Split")
        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName(SETTINGS_ORG)
    app.setApplicationName(APP_NAME)
    window = FastPDFDrawingTool()
    window.show()
    sys.exit(app.exec())
