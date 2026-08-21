import copy, json, os, sys, uuid
from pathlib import Path
import fitz
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPen, QPixmap
from PySide6.QtWidgets import (QApplication,QCheckBox,QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QGraphicsRectItem,QGraphicsScene,QGraphicsSimpleTextItem,QGraphicsView,QGroupBox,QHBoxLayout,QInputDialog,QLabel,QLineEdit,QListWidget,QListWidgetItem,QMainWindow,QMessageBox,QPlainTextEdit,QProgressBar,QPushButton,QSpinBox,QSplitter,QTabWidget,QToolButton,QVBoxLayout,QWidget,QAbstractItemView)
from pdf_ops import detect_sheet_number_box, export_editor, merge_pdfs, page_count, split_pdf

APP_NAME='PDF Drawing Tool'


def font_registry_map():
    fonts={}
    if sys.platform!='win32': return fonts
    try: import winreg
    except Exception: return fonts
    system=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'
    local=Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft'/'Windows'/'Fonts'
    def resolve(v):
        p=Path(str(v).strip().strip('"'))
        if p.is_absolute() and p.exists(): return p
        for d in (local,system):
            q=d/p
            if q.exists(): return q
    for hive,key in ((winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'),(winreg.HKEY_CURRENT_USER,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')):
        try:
            with winreg.OpenKey(hive,key) as k:
                i=0
                while True:
                    try: name,val,_=winreg.EnumValue(k,i); i+=1
                    except OSError: break
                    p=resolve(val)
                    if p: fonts[str(name).split(' (',1)[0].strip()]=str(p)
        except OSError: pass
    for p in (local/'cordia.ttf',system/'cordia.ttf',system/'cordia.ttc'):
        if p.exists(): fonts['Cordia New']=str(p); break
    return dict(sorted(fonts.items(),key=lambda kv:kv[0].lower()))


class PDFList(QListWidget):
    filesDropped=Signal(list)
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove); self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragEnterEvent(e)
    def dragMoveEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragMoveEvent(e)
    def dropEvent(self,e):
        if e.mimeData().hasUrls():
            ps=[u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile().lower().endswith('.pdf')]
            if ps: self.filesDropped.emit(ps); e.acceptProposedAction(); return
        super().dropEvent(e)
    def paths(self): return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]


class Preview(QGraphicsView):
    rectCreated=Signal(str,QRectF); pointCreated=Signal(float,float)
    def __init__(self):
        super().__init__(); self.mode='pan'; self.start=None; self.temp=None; self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse); self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
    def set_mode(self,m):
        self.mode=m; self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if m=='pan' else QGraphicsView.DragMode.NoDrag)
    def wheelEvent(self,e): self.scale(1.25,1.25) if e.angleDelta().y()>0 else self.scale(.8,.8)
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:
            p=self.mapToScene(e.position().toPoint())
            if self.mode=='text': self.pointCreated.emit(p.x(),p.y()); return
            if self.mode in ('sheet','image','rect'):
                self.start=p; self.temp=QGraphicsRectItem(QRectF(p,p)); self.temp.setPen(QPen(QColor(220,40,40),2)); self.scene().addItem(self.temp); return
        super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        if self.start is not None and self.temp is not None:
            self.temp.setRect(QRectF(self.start,self.mapToScene(e.position().toPoint())).normalized()); return
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self,e):
        if self.start is not None and self.temp is not None:
            r=QRectF(self.start,self.mapToScene(e.position().toPoint())).normalized(); m=self.mode; self.scene().removeItem(self.temp); self.start=self.temp=None
            if r.width()>3 and r.height()>3: self.rectCreated.emit(m,r)
            return
        super().mouseReleaseEvent(e)


class Editor(QWidget):
    def __init__(self):
        super().__init__(); self.fonts=font_registry_map(); self.pages=[]; self.render_size=None; self.page_pts=None; self.elements=[]; self.pending_image=None; self._ui()
    def _ui(self):
        root=QVBoxLayout(self); top=QHBoxLayout();
        for text,slot in [('Add PDFs',self.add_dialog),('Remove',self.remove),('Clear',self.clear)]: b=QPushButton(text); b.clicked.connect(slot); top.addWidget(b)
        top.addStretch(); self.count=QLabel('0 files / 0 pages'); top.addWidget(self.count); root.addLayout(top)
        sp=QSplitter(Qt.Orientation.Horizontal); root.addWidget(sp,1)
        left=QWidget(); ll=QVBoxLayout(left); ll.addWidget(QLabel('Files')); self.files=PDFList(); self.files.filesDropped.connect(self.add_files); ll.addWidget(self.files,1); ll.addWidget(QLabel('Objects')); self.objects=QListWidget(); ll.addWidget(self.objects,1); self.delobj=QPushButton('Delete selected object'); self.delobj.clicked.connect(self.delete_obj); ll.addWidget(self.delobj); sp.addWidget(left)
        center=QWidget(); cl=QVBoxLayout(center); nav=QHBoxLayout(); self.prev=QPushButton('◀'); self.next=QPushButton('▶'); self.pg=QSpinBox(); self.pg.setMinimum(1); self.pg.setMaximum(1); self.pgl=QLabel('Page 0 / 0'); self.prev.clicked.connect(lambda:self.pg.setValue(max(1,self.pg.value()-1))); self.next.clicked.connect(lambda:self.pg.setValue(min(self.pg.maximum(),self.pg.value()+1))); self.pg.valueChanged.connect(self.render); [nav.addWidget(w) for w in (self.prev,self.pg,self.next,self.pgl)]; nav.addStretch(); cl.addLayout(nav)
        tools=QHBoxLayout();
        for txt,mode in [('Pan','pan'),('Add Text','text'),('Sheet No.','sheet'),('Image','image'),('Rectangle','rect')]: b=QToolButton(); b.setText(txt); b.clicked.connect(lambda _=False,m=mode:self.tool(m)); tools.addWidget(b)
        zin=QPushButton('+'); zout=QPushButton('−'); fit=QPushButton('Fit Page'); zin.clicked.connect(lambda:self.view.scale(1.25,1.25)); zout.clicked.connect(lambda:self.view.scale(.8,.8)); fit.clicked.connect(self.fit); tools.addSpacing(10); [tools.addWidget(w) for w in (zout,zin,fit)]; tools.addStretch(); cl.addLayout(tools)
        self.scene=QGraphicsScene(self); self.view=Preview(); self.view.setScene(self.scene); self.view.setBackgroundBrush(QColor(55,55,55)); self.view.rectCreated.connect(self.rect_created); self.view.pointCreated.connect(self.text_created); cl.addWidget(self.view,1); self.status=QLabel('Add a PDF. Auto Detect will find the แผ่นที่ cell.'); cl.addWidget(self.status); sp.addWidget(center)
        right=QWidget(); rl=QVBoxLayout(right); g=QGroupBox('Properties'); f=QFormLayout(g); self.text=QLineEdit(); self.start=QSpinBox(); self.start.setRange(-999999,999999); self.start.setValue(4); self.autoload=QCheckBox('Auto-detect Sheet No. on PDF load'); self.autoload.setChecked(True); self.detect=QPushButton('Auto Detect Sheet No.'); self.detect.clicked.connect(lambda:self.auto_detect(False)); self.font=QComboBox(); [self.font.addItem(n,p) for n,p in self.fonts.items()]; i=self.font.findText('Cordia New'); self.font.setCurrentIndex(i if i>=0 else 0); self.size=QDoubleSpinBox(); self.size.setRange(3,100); self.size.setValue(12); self.scope=QComboBox(); self.scope.addItem('All pages','all'); self.scope.addItem('Current page','current'); self.scope.addItem('Page range','range'); self.r1=QSpinBox(); self.r2=QSpinBox(); self.r1.setRange(1,999999); self.r2.setRange(1,999999); rr=QWidget(); rrl=QHBoxLayout(rr); rrl.setContentsMargins(0,0,0,0); rrl.addWidget(self.r1); rrl.addWidget(QLabel('to')); rrl.addWidget(self.r2); self.cleanup=QComboBox(); self.cleanup.addItem('Keep annotations','keep'); self.cleanup.addItem('Remove AutoCAD SHX annotations','shx'); self.cleanup.addItem('Remove SHX + Text sticky notes','all_text'); self.cleanup.setCurrentIndex(1); self.merge=QCheckBox('Merge all inputs into one PDF'); self.merge.setChecked(True)
        for label,w in [('Text',self.text),('Sheet start',self.start),('',self.detect),('',self.autoload),('Font',self.font),('Font size',self.size),('Apply to',self.scope),('Range',rr),('Cleanup',self.cleanup),('',self.merge)]: f.addRow(label,w)
        rl.addWidget(g); self.export=QPushButton('Export PDF'); self.export.setMinimumHeight(44); self.export.clicked.connect(self.do_export); rl.addWidget(self.export); self.progress=QProgressBar(); rl.addWidget(self.progress); self.log=QPlainTextEdit(); self.log.setReadOnly(True); rl.addWidget(self.log,1); sp.addWidget(right); sp.setSizes([250,850,350])
        self.start.valueChanged.connect(self.sync_sheet); self.size.valueChanged.connect(self.sync_sheet); self.font.currentIndexChanged.connect(self.sync_sheet)
    def scope_val(self):
        m=self.scope.currentData(); p=self.pg.value(); return {'mode':'current','page':p} if m=='current' else ({'mode':'range','start':self.r1.value(),'end':self.r2.value()} if m=='range' else {'mode':'all'})
    def tool(self,m):
        if m=='image':
            p,_=QFileDialog.getOpenFileName(self,'Choose image','','Images (*.png *.jpg *.jpeg *.bmp)')
            if not p:return
            self.pending_image=p
        self.view.set_mode(m)
    def add_dialog(self):
        ps,_=QFileDialog.getOpenFileNames(self,'Add PDFs','','PDF Files (*.pdf)'); self.add_files(ps)
    def add_files(self,ps):
        existing=set(self.files.paths())
        for p in ps:
            if p in existing: continue
            try:n=page_count(p)
            except Exception as e: QMessageBox.warning(self,'PDF error',str(e)); continue
            it=QListWidgetItem(f'{Path(p).name} ({n} pages)'); it.setData(Qt.ItemDataRole.UserRole,p); self.files.addItem(it); existing.add(p)
        self.rebuild()
    def remove(self):
        for it in self.files.selectedItems(): self.files.takeItem(self.files.row(it))
        self.rebuild()
    def clear(self): self.files.clear(); self.elements=[]; self.objects.clear(); self.rebuild()
    def rebuild(self):
        self.pages=[]
        for p in self.files.paths(): self.pages += [(p,i) for i in range(page_count(p))]
        self.count.setText(f'{self.files.count()} files / {len(self.pages)} pages'); self.pg.setMaximum(max(1,len(self.pages))); self.pg.setValue(1); self.r2.setValue(max(1,len(self.pages)))
        if self.pages:
            self.render()
            if self.autoload.isChecked() and not any(e['type']=='sheet_number' for e in self.elements): self.auto_detect(True)
        else: self.scene.clear(); self.pgl.setText('Page 0 / 0')
    def render(self):
        if not self.pages:return
        gi=min(self.pg.value()-1,len(self.pages)-1); path,pi=self.pages[gi]
        with fitz.open(path) as d:
            page=d[pi]; pix=page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False); img=QImage(pix.samples,pix.width,pix.height,pix.stride,QImage.Format.Format_RGB888).copy(); pm=QPixmap.fromImage(img); self.scene.clear(); self.scene.addPixmap(pm); self.scene.setSceneRect(QRectF(0,0,pm.width(),pm.height())); self.render_size=(pm.width(),pm.height()); self.page_pts=(page.rect.width,page.rect.height); self.pgl.setText(f'Page {gi+1}/{len(self.pages)} — {Path(path).name}'); self.draw_elements(); self.fit()
    def fit(self):
        if self.scene.sceneRect().width()>0:self.view.fitInView(self.scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
    def norm_rect(self,r):
        w,h=self.render_size; r=r.normalized(); return [r.left()/w,r.top()/h,r.right()/w,r.bottom()/h]
    def norm_point(self,x,y): w,h=self.render_size; return x/w,y/h
    def font_path(self): return self.font.currentData() if self.font.count() else None
    def font_name(self): return self.font.currentText() if self.font.count() else 'Helvetica'
    def auto_detect(self,silent=False):
        if not self.pages:return False
        if any(e['type']=='sheet_number' for e in self.elements): self.sync_sheet(); return True
        det=None
        for p in self.files.paths():
            det=detect_sheet_number_box(p)
            if det: break
        if not det:
            self.status.setText('Auto detect failed — use Sheet No. and drag the cell manually.')
            if not silent: QMessageBox.warning(self,'Not detected','Could not find the แผ่นที่ cell.')
            return False
        self.elements.append({'id':uuid.uuid4().hex,'type':'sheet_number','box':list(det['box_norm']),'start_number':self.start.value(),'font_name':self.font_name(),'font_path':self.font_path(),'font_size':self.size.value(),'scope':{'mode':'all'}}); self.status.setText('Sheet No.: AUTO-DETECTED ✓'); self.refresh_objects(); self.draw_elements(); return True
    def sync_sheet(self,*_):
        for e in self.elements:
            if e['type']=='sheet_number': e.update(start_number=self.start.value(),font_name=self.font_name(),font_path=self.font_path(),font_size=self.size.value())
        self.draw_elements()
    def text_created(self,x,y):
        t=self.text.text() or QInputDialog.getText(self,'Add Text','Text:')[0]
        if not t:return
        nx,ny=self.norm_point(x,y); self.elements.append({'id':uuid.uuid4().hex,'type':'text','text':t,'x':nx,'y':ny,'font_name':self.font_name(),'font_path':self.font_path(),'font_size':self.size.value(),'scope':self.scope_val()}); self.refresh_objects(); self.draw_elements(); self.view.set_mode('pan')
    def rect_created(self,m,r):
        nr=self.norm_rect(r)
        if m=='sheet': self.elements.append({'id':uuid.uuid4().hex,'type':'sheet_number','box':nr,'start_number':self.start.value(),'font_name':self.font_name(),'font_path':self.font_path(),'font_size':self.size.value(),'scope':self.scope_val()})
        elif m=='image' and self.pending_image: self.elements.append({'id':uuid.uuid4().hex,'type':'image','rect':nr,'image_path':self.pending_image,'scope':self.scope_val()}); self.pending_image=None
        elif m=='rect': self.elements.append({'id':uuid.uuid4().hex,'type':'rectangle','rect':nr,'color':[1,0,0],'line_width':1.0,'scope':self.scope_val()})
        self.refresh_objects(); self.draw_elements(); self.view.set_mode('pan')
    def refresh_objects(self):
        self.objects.clear()
        for e in self.elements:
            label={'sheet_number':'Sheet Number','text':'Text: '+e.get('text',''),'image':'Image: '+Path(e.get('image_path','')).name,'rectangle':'Rectangle'}.get(e['type'],e['type']); it=QListWidgetItem(label); it.setData(Qt.ItemDataRole.UserRole,e['id']); self.objects.addItem(it)
    def delete_obj(self):
        it=self.objects.currentItem()
        if not it:return
        eid=it.data(Qt.ItemDataRole.UserRole); self.elements=[e for e in self.elements if e['id']!=eid]; self.refresh_objects(); self.draw_elements()
    def scope_ok(self,e):
        s=e.get('scope',{'mode':'all'}); p=self.pg.value(); m=s.get('mode','all')
        if m=='all': return True
        if m=='current': return p==int(s.get('page',p))
        a,b=int(s.get('start',1)),int(s.get('end',1)); return min(a,b)<=p<=max(a,b)
    def draw_elements(self):
        if not self.render_size:return
        for it in list(self.scene.items()):
            if getattr(it,'overlay',False): self.scene.removeItem(it)
        w,h=self.render_size; gi=self.pg.value()-1
        for e in self.elements:
            if not self.scope_ok(e):continue
            if e['type']=='sheet_number':
                x1,y1,x2,y2=e['box']; rect=QRectF(x1*w,y1*h,(x2-x1)*w,(y2-y1)*h); guide=QGraphicsRectItem(rect); guide.overlay=True; guide.setPen(QPen(QColor(220,40,40),1)); self.scene.addItem(guide); item=QGraphicsSimpleTextItem(str(int(e['start_number'])+gi)); item.overlay=True; f=QFont(e.get('font_name','Arial')); f.setPixelSize(max(1,int(e.get('font_size',12)*(w/self.page_pts[0])))); item.setFont(f); br=item.boundingRect(); item.setPos(rect.center().x()-br.width()/2,rect.center().y()-br.height()/2); self.scene.addItem(item)
            elif e['type']=='text':
                item=QGraphicsSimpleTextItem(e['text']); item.overlay=True; f=QFont(e.get('font_name','Arial')); f.setPixelSize(max(1,int(e.get('font_size',12)*(w/self.page_pts[0])))); item.setFont(f); item.setPos(e['x']*w,e['y']*h); self.scene.addItem(item)
            elif e['type']=='rectangle':
                x1,y1,x2,y2=e['rect']; item=QGraphicsRectItem(QRectF(x1*w,y1*h,(x2-x1)*w,(y2-y1)*h)); item.overlay=True; item.setPen(QPen(QColor(255,0,0),2)); self.scene.addItem(item)
            elif e['type']=='image' and Path(e['image_path']).exists():
                x1,y1,x2,y2=e['rect']; pm=QPixmap(e['image_path']).scaled(max(1,int((x2-x1)*w)),max(1,int((y2-y1)*h)),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation); item=self.scene.addPixmap(pm); item.overlay=True; item.setPos(x1*w,y1*h)
    def do_export(self):
        files=self.files.paths()
        if not files:return
        if self.autoload.isChecked() and not any(e['type']=='sheet_number' for e in self.elements): self.auto_detect(True)
        if not self.elements: QMessageBox.warning(self,'Nothing to export','Add an object or Auto Detect Sheet No. first.'); return
        self.sync_sheet(); merge=self.merge.isChecked()
        if merge:
            out,_=QFileDialog.getSaveFileName(self,'Save PDF','Edited_Merged.pdf','PDF Files (*.pdf)');
            if not out:return
            if not out.lower().endswith('.pdf'):out+='.pdf'
        else:
            out=QFileDialog.getExistingDirectory(self,'Output folder');
            if not out:return
        self.log.clear(); self.progress.setValue(0)
        def pcb(d,t): self.progress.setValue(int(d*100/max(1,t))); QApplication.processEvents()
        try:
            r=export_editor(files,out,copy.deepcopy(self.elements),cleanup_mode=self.cleanup.currentData(),merge=merge,progress_cb=pcb,log_cb=self.log.appendPlainText); self.progress.setValue(100); QMessageBox.information(self,'Finished',f"Exported {r['pages']} pages.\nAnnotations removed: {r['removed_annotations']}")
        except Exception as e: QMessageBox.critical(self,'Export failed',str(e))


class Merge(QWidget):
    def __init__(self):
        super().__init__(); l=QVBoxLayout(self); b=QPushButton('Add PDFs'); b.clicked.connect(self.add); self.list=PDFList(); self.list.filesDropped.connect(self.add_files); m=QPushButton('Merge'); m.clicked.connect(self.run); l.addWidget(b); l.addWidget(self.list,1); l.addWidget(m)
    def add(self): ps,_=QFileDialog.getOpenFileNames(self,'Add PDFs','','PDF Files (*.pdf)'); self.add_files(ps)
    def add_files(self,ps):
        for p in ps:
            it=QListWidgetItem(Path(p).name); it.setData(Qt.ItemDataRole.UserRole,p); self.list.addItem(it)
    def run(self):
        if not self.list.paths():return
        out,_=QFileDialog.getSaveFileName(self,'Save merged PDF','Merged.pdf','PDF Files (*.pdf)');
        if not out:return
        if not out.lower().endswith('.pdf'):out+='.pdf'
        try: n=merge_pdfs(self.list.paths(),out); QMessageBox.information(self,'Merged',f'{n} pages → {out}')
        except Exception as e: QMessageBox.critical(self,'Merge failed',str(e))


class Split(QWidget):
    def __init__(self):
        super().__init__(); l=QFormLayout(self); self.path=QLineEdit(); self.path.setReadOnly(True); b=QPushButton('Choose PDF'); b.clicked.connect(self.choose); self.seq=QCheckBox('Use sequence filenames'); self.start=QSpinBox(); self.start.setValue(1); self.prefix=QLineEdit(); run=QPushButton('Split every page'); run.clicked.connect(self.run); l.addRow(self.path,b); l.addRow(self.seq); l.addRow('Sequence start',self.start); l.addRow('Prefix',self.prefix); l.addRow(run)
    def choose(self): p,_=QFileDialog.getOpenFileName(self,'Choose PDF','','PDF Files (*.pdf)'); self.path.setText(p)
    def run(self):
        if not self.path.text():return
        out=QFileDialog.getExistingDirectory(self,'Output folder');
        if not out:return
        try: ps=split_pdf(self.path.text(),out,self.seq.isChecked(),self.start.value(),self.prefix.text()); QMessageBox.information(self,'Split',f'Created {len(ps)} files.')
        except Exception as e: QMessageBox.critical(self,'Split failed',str(e))


class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(APP_NAME); self.resize(1550,900); tabs=QTabWidget(); tabs.addTab(Editor(),'Editor'); tabs.addTab(Merge(),'Merge'); tabs.addTab(Split(),'Split'); self.setCentralWidget(tabs)

if __name__=='__main__':
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME); w=Main(); w.show(); sys.exit(app.exec())
