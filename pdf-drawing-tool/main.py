import copy, json, os, sys, uuid
from pathlib import Path
import fitz
from PySide6.QtCore import Qt, QRectF, Signal, QSettings
from PySide6.QtGui import QColor, QFont, QImage, QPen, QPixmap, QBrush
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGraphicsRectItem, QGraphicsScene,
    QGraphicsSimpleTextItem, QGraphicsView, QGroupBox, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QSplitter,
    QTabWidget, QToolButton, QVBoxLayout, QWidget
)
from pdf_ops import detect_sheet_number_box, export_editor, merge_pdfs, page_count, split_pdf

APP_NAME = 'PDF Drawing Tool V2.3'
ORG_NAME = 'TEAMG'
THAI_SEQUENCE = list("กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")


def font_registry_map():
    fonts = {}
    if sys.platform != 'win32':
        return fonts
    try:
        import winreg
    except Exception:
        return fonts
    system = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
    local = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'Windows' / 'Fonts'
    def resolve(v):
        p = Path(str(v).strip().strip('"'))
        if p.is_absolute() and p.exists():
            return p
        for d in (local, system):
            q = d / p
            if q.exists():
                return q
    for hive, key in (
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'),
    ):
        try:
            with winreg.OpenKey(hive, key) as k:
                i = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(k, i); i += 1
                    except OSError:
                        break
                    p = resolve(val)
                    if p:
                        fonts[str(name).split(' (', 1)[0].strip()] = str(p)
        except OSError:
            pass
    for p in (local / 'cordia.ttf', system / 'cordia.ttf', system / 'cordia.ttc'):
        if p.exists():
            fonts['Cordia New'] = str(p)
            break
    return dict(sorted(fonts.items(), key=lambda kv: kv[0].lower()))


class PDFListWidget(QListWidget):
    filesDropped = Signal(list)
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragEnterEvent(e)
    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragMoveEvent(e)
    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile().lower().endswith('.pdf')]
            if paths:
                self.filesDropped.emit(paths); e.acceptProposedAction(); return
        super().dropEvent(e)
    def paths(self):
        return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]


class EditorView(QGraphicsView):
    rectCreated = Signal(str, QRectF)
    pointCreated = Signal(float, float)
    def __init__(self):
        super().__init__()
        self.mode = 'pan'; self.start = None; self.temp = None
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
    def set_mode(self, mode):
        self.mode = mode
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode in ('pan', 'select') else QGraphicsView.DragMode.NoDrag)
    def wheelEvent(self, e):
        self.scale(1.25, 1.25) if e.angleDelta().y() > 0 else self.scale(.8, .8)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            p = self.mapToScene(e.position().toPoint())
            if self.mode == 'text':
                self.pointCreated.emit(p.x(), p.y()); return
            if self.mode in ('sheet', 'image', 'rect', 'erase_sheet', 'erase_scale', 'erase_area'):
                self.start = p
                self.temp = QGraphicsRectItem(QRectF(p, p))
                self.temp.setPen(QPen(QColor(220, 40, 40), 2, Qt.PenStyle.DashLine))
                self.scene().addItem(self.temp); return
        super().mousePressEvent(e)
    def mouseMoveEvent(self, e):
        if self.start is not None and self.temp is not None:
            self.temp.setRect(QRectF(self.start, self.mapToScene(e.position().toPoint())).normalized()); return
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self, e):
        if self.start is not None and self.temp is not None:
            r = QRectF(self.start, self.mapToScene(e.position().toPoint())).normalized(); mode = self.mode
            self.scene().removeItem(self.temp); self.start = self.temp = None
            if r.width() > 3 and r.height() > 3:
                self.rectCreated.emit(mode, r)
            return
        super().mouseReleaseEvent(e)


class PresetStore:
    def __init__(self):
        self.settings = QSettings(ORG_NAME, APP_NAME)
    def names(self):
        raw = self.settings.value('presets/names', '[]')
        try: return sorted(set(json.loads(raw)))
        except Exception: return []
    def save(self, name, elements):
        names = self.names()
        if name not in names: names.append(name)
        self.settings.setValue('presets/names', json.dumps(names, ensure_ascii=False))
        self.settings.setValue(f'presets/{name}', json.dumps(elements, ensure_ascii=False))
    def load(self, name):
        raw = self.settings.value(f'presets/{name}', '')
        return json.loads(raw) if raw else []


class EditorTab(QWidget):
    def __init__(self):
        super().__init__()
        self.fonts = font_registry_map(); self.presets = PresetStore()
        self.pages = []; self.render_size = None; self.page_pts = None
        self.elements = []; self.undo_stack = []; self.redo_stack = []
        self.pending_image = None
        self._build_ui(); self.refresh_presets()

    def _build_ui(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        for text, slot in [('Add PDFs', self.add_files_dialog), ('Remove selected', self.remove_selected_files), ('Clear', self.clear_files)]:
            b = QPushButton(text); b.clicked.connect(slot); top.addWidget(b)
        top.addStretch(); self.total_label = QLabel('0 files / 0 pages'); top.addWidget(self.total_label); root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal); root.addWidget(splitter, 1)
        left = QWidget(); ll = QVBoxLayout(left)
        ll.addWidget(QLabel('Files — drag PDFs here; drag rows to reorder'))
        self.file_list = PDFListWidget(); self.file_list.filesDropped.connect(self.add_files); ll.addWidget(self.file_list, 1)
        ll.addWidget(QLabel('Added objects'))
        self.element_list = QListWidget(); ll.addWidget(self.element_list, 1)
        self.delete_element_btn = QPushButton('Delete selected object'); self.delete_element_btn.clicked.connect(self.delete_element); ll.addWidget(self.delete_element_btn)
        splitter.addWidget(left)

        center = QWidget(); cl = QVBoxLayout(center)
        nav = QHBoxLayout(); self.prev_btn = QPushButton('◀'); self.next_btn = QPushButton('▶'); self.page_spin = QSpinBox(); self.page_spin.setMinimum(1); self.page_spin.setMaximum(1); self.page_label = QLabel('Page 0 / 0')
        self.prev_btn.clicked.connect(lambda: self.page_spin.setValue(max(1, self.page_spin.value()-1)))
        self.next_btn.clicked.connect(lambda: self.page_spin.setValue(min(self.page_spin.maximum(), self.page_spin.value()+1)))
        self.page_spin.valueChanged.connect(self.render_current_page)
        for w in (self.prev_btn, self.page_spin, self.next_btn, self.page_label): nav.addWidget(w)
        nav.addStretch(); cl.addLayout(nav)

        tools = QHBoxLayout()
        for txt, mode in [
            ('Select','select'), ('Add Text','text'), ('Sheet No.','sheet'), ('Erase Sheet No.','erase_sheet'),
            ('Erase Scale','erase_scale'), ('Image','image'), ('Rectangle','rect')
        ]:
            b = QToolButton(); b.setText(txt); b.clicked.connect(lambda _=False, m=mode: self.set_tool(m)); tools.addWidget(b)
        zoom_out = QPushButton('−'); zoom_100 = QPushButton('100%'); zoom_in = QPushButton('+'); fit_page = QPushButton('Fit Page'); fit_width = QPushButton('Fit Width')
        zoom_out.clicked.connect(lambda: self.view.scale(.8,.8)); zoom_in.clicked.connect(lambda: self.view.scale(1.25,1.25)); zoom_100.clicked.connect(self.reset_zoom); fit_page.clicked.connect(self.fit_page); fit_width.clicked.connect(self.fit_width)
        undo_btn = QPushButton('Undo'); redo_btn = QPushButton('Redo'); undo_btn.clicked.connect(self.undo); redo_btn.clicked.connect(self.redo)
        tools.addSpacing(8)
        for w in (zoom_out, zoom_100, zoom_in, fit_page, fit_width, undo_btn, redo_btn): tools.addWidget(w)
        tools.addStretch(); cl.addLayout(tools)

        self.scene = QGraphicsScene(self); self.view = EditorView(); self.view.setScene(self.scene); self.view.setBackgroundBrush(QColor(55,55,55)); self.view.rectCreated.connect(self.on_rect_created); self.view.pointCreated.connect(self.on_point_created); cl.addWidget(self.view,1)
        self.measure_label = QLabel('Sheet No. replaces the old number automatically. Erase Scale: drag tightly around the existing scale text/value.'); cl.addWidget(self.measure_label)
        splitter.addWidget(center)

        right = QWidget(); rl = QVBoxLayout(right)
        pg = QGroupBox('Preset'); pf = QFormLayout(pg); self.preset_combo = QComboBox(); self.save_preset_btn = QPushButton('Save current editor preset'); self.load_preset_btn = QPushButton('Apply preset'); self.save_preset_btn.clicked.connect(self.save_preset); self.load_preset_btn.clicked.connect(self.load_preset); pf.addRow(self.preset_combo); pf.addRow(self.save_preset_btn); pf.addRow(self.load_preset_btn); rl.addWidget(pg)

        g = QGroupBox('Properties'); f = QFormLayout(g)
        self.text_edit = QLineEdit(); self.text_edit.setPlaceholderText('Text to add')
        self.sequence_combo = QComboBox(); self.sequence_combo.addItem('1, 2, 3, ...','number'); self.sequence_combo.addItem('a, b, c, ...','lower'); self.sequence_combo.addItem('A, B, C, ...','upper'); self.sequence_combo.addItem('ก, ข, ฃ, ... ฮ','thai')
        self.sequence_start = QLineEdit('1'); self.sequence_start.setPlaceholderText('e.g. 1, a, ก')
        self.auto_detect_btn = QPushButton('Auto Detect Sheet No.'); self.auto_detect_btn.clicked.connect(lambda: self.auto_detect_sheet_number(False))
        self.auto_detect_on_load = QCheckBox('Auto-detect Sheet No. on PDF load'); self.auto_detect_on_load.setChecked(True)
        self.detect_status = QLabel('Sheet No.: not detected yet'); self.detect_status.setWordWrap(True)
        self.font_combo = QComboBox(); [self.font_combo.addItem(n,p) for n,p in self.fonts.items()]
        i = self.font_combo.findText('Cordia New'); self.font_combo.setCurrentIndex(i if i >= 0 else 0)
        self.font_browse_btn = QPushButton('Browse font'); self.font_browse_btn.clicked.connect(self.browse_font)
        fw = QWidget(); fwl = QHBoxLayout(fw); fwl.setContentsMargins(0,0,0,0); fwl.addWidget(self.font_combo,1); fwl.addWidget(self.font_browse_btn)
        self.font_size = QDoubleSpinBox(); self.font_size.setRange(3,100); self.font_size.setValue(12); self.font_size.setSingleStep(.5)
        self.scope_combo = QComboBox(); self.scope_combo.addItem('All pages','all'); self.scope_combo.addItem('Current page','current'); self.scope_combo.addItem('Page range','range')
        self.range_start = QSpinBox(); self.range_end = QSpinBox(); self.range_start.setRange(1,999999); self.range_end.setRange(1,999999)
        rr = QWidget(); rrl = QHBoxLayout(rr); rrl.setContentsMargins(0,0,0,0); rrl.addWidget(self.range_start); rrl.addWidget(QLabel('to')); rrl.addWidget(self.range_end)
        self.erase_mode = QComboBox(); self.erase_mode.addItem('Text only — preserve drawing lines','text'); self.erase_mode.addItem('Everything in selected box','all')
        self.cleanup_combo = QComboBox(); self.cleanup_combo.addItem('Keep annotations','keep'); self.cleanup_combo.addItem('Remove AutoCAD SHX annotations (recommended)','shx'); self.cleanup_combo.addItem('Remove AutoCAD SHX + all Text sticky notes','all_text'); self.cleanup_combo.setCurrentIndex(1)
        self.merge_after = QCheckBox('Merge all inputs into one edited PDF'); self.merge_after.setChecked(True)
        for label,w in [('Text',self.text_edit),('Sequence',self.sequence_combo),('Start value',self.sequence_start),('',self.auto_detect_btn),('',self.auto_detect_on_load),('',self.detect_status),('Font',fw),('Font size',self.font_size),('Apply to',self.scope_combo),('Range',rr),('Erase mode',self.erase_mode),('Cleanup',self.cleanup_combo),('',self.merge_after)]: f.addRow(label,w)
        rl.addWidget(g)
        self.export_btn = QPushButton('Export PDF'); self.export_btn.setMinimumHeight(44); self.export_btn.clicked.connect(self.export_pdf); rl.addWidget(self.export_btn)
        self.progress = QProgressBar(); rl.addWidget(self.progress); self.log = QPlainTextEdit(); self.log.setReadOnly(True); rl.addWidget(self.log,1)
        splitter.addWidget(right); splitter.setSizes([260,880,390])

        self.sequence_combo.currentIndexChanged.connect(self.sync_sheet_number); self.sequence_start.textChanged.connect(self.sync_sheet_number); self.font_size.valueChanged.connect(self.sync_sheet_number); self.font_combo.currentIndexChanged.connect(self.sync_sheet_number)

    def _snapshot(self): return copy.deepcopy(self.elements)
    def push_undo(self):
        self.undo_stack.append(self._snapshot()); self.undo_stack = self.undo_stack[-50:]; self.redo_stack.clear()
    def undo(self):
        if not self.undo_stack: return
        self.redo_stack.append(self._snapshot()); self.elements = self.undo_stack.pop(); self.refresh_objects(); self.draw_elements()
    def redo(self):
        if not self.redo_stack: return
        self.undo_stack.append(self._snapshot()); self.elements = self.redo_stack.pop(); self.refresh_objects(); self.draw_elements()

    def scope_value(self):
        m = self.scope_combo.currentData(); p = self.page_spin.value()
        if m == 'current': return {'mode':'current','page':p}
        if m == 'range': return {'mode':'range','start':self.range_start.value(),'end':self.range_end.value()}
        return {'mode':'all'}
    def font_path(self): return self.font_combo.currentData() if self.font_combo.count() else None
    def font_name(self): return self.font_combo.currentText() if self.font_combo.count() else 'Helvetica'
    def set_tool(self, mode):
        if mode == 'image':
            p,_ = QFileDialog.getOpenFileName(self,'Choose image','','Images (*.png *.jpg *.jpeg *.bmp)')
            if not p: return
            self.pending_image = p
        self.view.set_mode(mode)
    def browse_font(self):
        p,_ = QFileDialog.getOpenFileName(self,'Choose font','','Fonts (*.ttf *.otf *.ttc)')
        if not p: return
        name = Path(p).stem
        idx = self.font_combo.findData(p)
        if idx < 0: self.font_combo.addItem(name,p); idx = self.font_combo.count()-1
        self.font_combo.setCurrentIndex(idx)
    def add_files_dialog(self):
        ps,_ = QFileDialog.getOpenFileNames(self,'Add PDFs','','PDF Files (*.pdf)'); self.add_files(ps)
    def add_files(self, ps):
        existing = set(self.file_list.paths())
        for p in ps:
            if p in existing: continue
            try: n = page_count(p)
            except Exception as e: QMessageBox.warning(self,'PDF error',str(e)); continue
            it = QListWidgetItem(f'{Path(p).name} ({n} pages)'); it.setData(Qt.ItemDataRole.UserRole,p); self.file_list.addItem(it); existing.add(p)
        self.rebuild_pages()
    def remove_selected_files(self):
        for it in self.file_list.selectedItems(): self.file_list.takeItem(self.file_list.row(it))
        self.rebuild_pages()
    def clear_files(self):
        self.file_list.clear(); self.elements=[]; self.undo_stack=[]; self.redo_stack=[]; self.refresh_objects(); self.rebuild_pages()
    def rebuild_pages(self):
        self.pages=[]
        for p in self.file_list.paths(): self.pages += [(p,i) for i in range(page_count(p))]
        self.total_label.setText(f'{self.file_list.count()} files / {len(self.pages)} pages'); self.page_spin.setMaximum(max(1,len(self.pages))); self.page_spin.setValue(1); self.range_end.setValue(max(1,len(self.pages)))
        if self.pages:
            self.render_current_page()
            if self.auto_detect_on_load.isChecked() and not any(e['type']=='sheet_number' for e in self.elements): self.auto_detect_sheet_number(True)
        else:
            self.scene.clear(); self.page_label.setText('Page 0 / 0')
    def render_current_page(self):
        if not self.pages: return
        gi=min(self.page_spin.value()-1,len(self.pages)-1); path,pi=self.pages[gi]
        with fitz.open(path) as d:
            page=d[pi]; pix=page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False); img=QImage(pix.samples,pix.width,pix.height,pix.stride,QImage.Format.Format_RGB888).copy(); pm=QPixmap.fromImage(img)
            self.scene.clear(); self.scene.addPixmap(pm); self.scene.setSceneRect(QRectF(0,0,pm.width(),pm.height())); self.render_size=(pm.width(),pm.height()); self.page_pts=(page.rect.width,page.rect.height); self.page_label.setText(f'Page {gi+1}/{len(self.pages)} — {Path(path).name}'); self.draw_elements(); self.fit_page()
    def reset_zoom(self): self.view.resetTransform()
    def fit_page(self):
        if self.scene.sceneRect().width()>0: self.view.fitInView(self.scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
    def fit_width(self):
        if not self.render_size: return
        self.view.resetTransform(); width=self.scene.sceneRect().width(); vp=max(1,self.view.viewport().width()-12); self.view.scale(vp/max(1,width),vp/max(1,width))
    def norm_rect(self,r):
        w,h=self.render_size; r=r.normalized(); return [r.left()/w,r.top()/h,r.right()/w,r.bottom()/h]
    def norm_point(self,x,y): w,h=self.render_size; return x/w,y/h

    def auto_detect_sheet_number(self, silent=False):
        if not self.pages: return False
        existing = next((e for e in self.elements if e['type']=='sheet_number'),None)
        if existing:
            self.sync_sheet_number(); return True
        det=None
        for p in self.file_list.paths():
            det=detect_sheet_number_box(p)
            if det: break
        if not det:
            self.detect_status.setText('Sheet No.: auto detect failed — use Sheet No. and drag around the number area manually.')
            if not silent: QMessageBox.warning(self,'Not detected','Could not find the แผ่นที่ cell.')
            return False
        self.push_undo(); box=list(det.get('number_box_norm') or det['box_norm'])
        self.elements.append({'id':uuid.uuid4().hex,'type':'sheet_number','box':box,'erase_box':box,'erase_existing':True,'erase_mode':'text','sequence_type':self.sequence_combo.currentData(),'sequence_start':self.sequence_start.text().strip() or '1','font_name':self.font_name(),'font_path':self.font_path(),'font_size':self.font_size.value(),'scope':{'mode':'all'}})
        self.detect_status.setText('Sheet No.: AUTO-DETECTED ✓ — old number will be removed before the new sequence is written.'); self.refresh_objects(); self.draw_elements(); return True
    def sync_sheet_number(self,*_):
        for e in self.elements:
            if e['type']=='sheet_number':
                e.update(sequence_type=self.sequence_combo.currentData(),sequence_start=self.sequence_start.text().strip() or '1',font_name=self.font_name(),font_path=self.font_path(),font_size=self.font_size.value())
        self.draw_elements()
    def on_point_created(self,x,y):
        t=self.text_edit.text() or QInputDialog.getText(self,'Add Text','Text:')[0]
        if not t: return
        self.push_undo(); nx,ny=self.norm_point(x,y); self.elements.append({'id':uuid.uuid4().hex,'type':'text','text':t,'x':nx,'y':ny,'font_name':self.font_name(),'font_path':self.font_path(),'font_size':self.font_size.value(),'scope':self.scope_value()}); self.refresh_objects(); self.draw_elements(); self.view.set_mode('pan')
    def on_rect_created(self, mode, r):
        nr=self.norm_rect(r); self.push_undo()
        if mode=='sheet':
            self.elements.append({'id':uuid.uuid4().hex,'type':'sheet_number','box':nr,'erase_box':nr,'erase_existing':True,'erase_mode':self.erase_mode.currentData(),'sequence_type':self.sequence_combo.currentData(),'sequence_start':self.sequence_start.text().strip() or '1','font_name':self.font_name(),'font_path':self.font_path(),'font_size':self.font_size.value(),'scope':self.scope_value()})
        elif mode in ('erase_sheet','erase_scale','erase_area'):
            self.elements.append({'id':uuid.uuid4().hex,'type':mode,'rect':nr,'erase_mode':self.erase_mode.currentData(),'scope':self.scope_value()})
        elif mode=='image' and self.pending_image:
            self.elements.append({'id':uuid.uuid4().hex,'type':'image','rect':nr,'image_path':self.pending_image,'scope':self.scope_value()}); self.pending_image=None
        elif mode=='rect':
            self.elements.append({'id':uuid.uuid4().hex,'type':'rectangle','rect':nr,'color':[1,0,0],'line_width':1.0,'scope':self.scope_value()})
        self.refresh_objects(); self.draw_elements(); self.view.set_mode('pan')
    def refresh_objects(self):
        self.element_list.clear()
        labels={'sheet_number':'Sheet Number / Resequence','erase_sheet':'Erase Sheet No.','erase_scale':'Erase Scale','erase_area':'Erase Area','rectangle':'Rectangle'}
        for e in self.elements:
            label=labels.get(e['type']) or ('Text: '+e.get('text','') if e['type']=='text' else 'Image: '+Path(e.get('image_path','')).name if e['type']=='image' else e['type'])
            it=QListWidgetItem(label); it.setData(Qt.ItemDataRole.UserRole,e['id']); self.element_list.addItem(it)
    def delete_element(self):
        it=self.element_list.currentItem()
        if not it: return
        self.push_undo(); eid=it.data(Qt.ItemDataRole.UserRole); self.elements=[e for e in self.elements if e['id']!=eid]; self.refresh_objects(); self.draw_elements()
    def scope_ok(self,e):
        s=e.get('scope',{'mode':'all'}); p=self.page_spin.value(); m=s.get('mode','all')
        if m=='all': return True
        if m=='current': return p==int(s.get('page',p))
        a,b=int(s.get('start',1)),int(s.get('end',1)); return min(a,b)<=p<=max(a,b)
    def preview_sequence(self,e,gi):
        kind=e.get('sequence_type','number'); start=str(e.get('sequence_start','1')).strip()
        if kind=='number':
            try: return str(int(start)+gi)
            except Exception: return str(1+gi)
        chars=list('abcdefghijklmnopqrstuvwxyz') if kind=='lower' else list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') if kind=='upper' else THAI_SEQUENCE
        base=chars.index(start) if start in chars else 0; n=base+gi; out=''
        while True:
            out=chars[n%len(chars)]+out; n=n//len(chars)-1
            if n<0: break
        return out
    def draw_elements(self):
        if not self.render_size: return
        for it in list(self.scene.items()):
            if getattr(it,'overlay',False): self.scene.removeItem(it)
        w,h=self.render_size; gi=self.page_spin.value()-1
        for e in self.elements:
            if not self.scope_ok(e): continue
            if e['type']=='sheet_number':
                x1,y1,x2,y2=e['box']; rect=QRectF(x1*w,y1*h,(x2-x1)*w,(y2-y1)*h)
                blank=QGraphicsRectItem(rect); blank.overlay=True; blank.setBrush(QBrush(QColor(255,255,255,225))); blank.setPen(QPen(QColor(220,40,40),1,Qt.PenStyle.DashLine)); self.scene.addItem(blank)
                item=QGraphicsSimpleTextItem(self.preview_sequence(e,gi)); item.overlay=True; f=QFont(e.get('font_name','Arial')); f.setPixelSize(max(1,int(e.get('font_size',12)*(w/self.page_pts[0])))); item.setFont(f); br=item.boundingRect(); item.setPos(rect.center().x()-br.width()/2,rect.center().y()-br.height()/2); self.scene.addItem(item)
            elif e['type']=='text':
                item=QGraphicsSimpleTextItem(e['text']); item.overlay=True; f=QFont(e.get('font_name','Arial')); f.setPixelSize(max(1,int(e.get('font_size',12)*(w/self.page_pts[0])))); item.setFont(f); item.setPos(e['x']*w,e['y']*h); self.scene.addItem(item)
            elif e['type'] in ('erase_sheet','erase_scale','erase_area'):
                x1,y1,x2,y2=e['rect']; item=QGraphicsRectItem(QRectF(x1*w,y1*h,(x2-x1)*w,(y2-y1)*h)); item.overlay=True; item.setBrush(QBrush(QColor(255,255,255,120))); item.setPen(QPen(QColor(220,40,40),2,Qt.PenStyle.DashLine)); self.scene.addItem(item)
            elif e['type']=='rectangle':
                x1,y1,x2,y2=e['rect']; item=QGraphicsRectItem(QRectF(x1*w,y1*h,(x2-x1)*w,(y2-y1)*h)); item.overlay=True; item.setPen(QPen(QColor(255,0,0),2)); self.scene.addItem(item)
            elif e['type']=='image' and Path(e['image_path']).exists():
                x1,y1,x2,y2=e['rect']; pm=QPixmap(e['image_path']).scaled(max(1,int((x2-x1)*w)),max(1,int((y2-y1)*h)),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation); item=self.scene.addPixmap(pm); item.overlay=True; item.setPos(x1*w,y1*h)

    def refresh_presets(self):
        current=self.preset_combo.currentText(); self.preset_combo.clear(); self.preset_combo.addItems(self.presets.names()); idx=self.preset_combo.findText(current); self.preset_combo.setCurrentIndex(idx if idx>=0 else 0)
    def save_preset(self):
        name,ok=QInputDialog.getText(self,'Save preset','Preset name:')
        if not ok or not name.strip(): return
        self.presets.save(name.strip(),copy.deepcopy(self.elements)); self.refresh_presets(); self.preset_combo.setCurrentText(name.strip())
    def load_preset(self):
        name=self.preset_combo.currentText()
        if not name: return
        try:
            self.push_undo(); self.elements=self.presets.load(name); self.refresh_objects(); self.draw_elements()
        except Exception as e: QMessageBox.warning(self,'Preset error',str(e))

    def export_pdf(self):
        files=self.file_list.paths()
        if not files: return
        if self.auto_detect_on_load.isChecked() and not any(e['type']=='sheet_number' for e in self.elements): self.auto_detect_sheet_number(True)
        if not self.elements: QMessageBox.warning(self,'Nothing to export','Add an object, erase area, or Auto Detect Sheet No. first.'); return
        self.sync_sheet_number(); merge=self.merge_after.isChecked()
        if merge:
            out,_=QFileDialog.getSaveFileName(self,'Save PDF','Edited_Merged.pdf','PDF Files (*.pdf)')
            if not out:return
            if not out.lower().endswith('.pdf'): out+='.pdf'
        else:
            out=QFileDialog.getExistingDirectory(self,'Output folder')
            if not out:return
        self.log.clear(); self.progress.setValue(0)
        def pcb(done,total): self.progress.setValue(int(done*100/max(1,total))); QApplication.processEvents()
        try:
            result=export_editor(files,out,copy.deepcopy(self.elements),cleanup_mode=self.cleanup_combo.currentData(),merge=merge,progress_cb=pcb,log_cb=self.log.appendPlainText); self.progress.setValue(100)
            QMessageBox.information(self,'Finished',f"Exported {result['pages']} pages.\nAnnotations removed: {result['removed_annotations']}\nText annotations erased in selected areas: {result.get('erased_annotations',0)}")
        except Exception as e: QMessageBox.critical(self,'Export failed',str(e))


class MergeTab(QWidget):
    def __init__(self):
        super().__init__(); l=QVBoxLayout(self); b=QPushButton('Add PDFs'); b.clicked.connect(self.add); self.list=PDFListWidget(); self.list.filesDropped.connect(self.add_files); m=QPushButton('Merge'); m.clicked.connect(self.run); l.addWidget(b); l.addWidget(self.list,1); l.addWidget(m)
    def add(self): ps,_=QFileDialog.getOpenFileNames(self,'Add PDFs','','PDF Files (*.pdf)'); self.add_files(ps)
    def add_files(self,ps):
        for p in ps:
            it=QListWidgetItem(Path(p).name); it.setData(Qt.ItemDataRole.UserRole,p); self.list.addItem(it)
    def run(self):
        if not self.list.paths():return
        out,_=QFileDialog.getSaveFileName(self,'Save merged PDF','Merged.pdf','PDF Files (*.pdf)')
        if not out:return
        if not out.lower().endswith('.pdf'):out+='.pdf'
        try: n=merge_pdfs(self.list.paths(),out); QMessageBox.information(self,'Merged',f'{n} pages → {out}')
        except Exception as e: QMessageBox.critical(self,'Merge failed',str(e))


class SplitTab(QWidget):
    def __init__(self):
        super().__init__(); l=QFormLayout(self); self.path=QLineEdit(); self.path.setReadOnly(True); b=QPushButton('Choose PDF'); b.clicked.connect(self.choose); self.seq=QCheckBox('Use sequence filenames'); self.start=QSpinBox(); self.start.setValue(1); self.prefix=QLineEdit(); run=QPushButton('Split every page'); run.clicked.connect(self.run); l.addRow(self.path,b); l.addRow(self.seq); l.addRow('Sequence start',self.start); l.addRow('Prefix',self.prefix); l.addRow(run)
    def choose(self): p,_=QFileDialog.getOpenFileName(self,'Choose PDF','','PDF Files (*.pdf)'); self.path.setText(p)
    def run(self):
        if not self.path.text():return
        out=QFileDialog.getExistingDirectory(self,'Output folder')
        if not out:return
        try: ps=split_pdf(self.path.text(),out,self.seq.isChecked(),self.start.value(),self.prefix.text()); QMessageBox.information(self,'Split',f'Created {len(ps)} files.')
        except Exception as e: QMessageBox.critical(self,'Split failed',str(e))


class PDFDrawingTool(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(APP_NAME); self.resize(1600,920); tabs=QTabWidget(); tabs.addTab(EditorTab(),'Editor'); tabs.addTab(MergeTab(),'Merge'); tabs.addTab(SplitTab(),'Split'); self.setCentralWidget(tabs)


if __name__=='__main__':
    app=QApplication(sys.argv); app.setOrganizationName(ORG_NAME); app.setApplicationName(APP_NAME); w=PDFDrawingTool(); w.show(); sys.exit(app.exec())
