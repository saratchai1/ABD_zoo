import os,sys,copy
from pathlib import Path
import fitz
from PySide6.QtCore import Qt,QRectF,Signal
from PySide6.QtGui import QColor,QFont,QImage,QPen,QPixmap
from PySide6.QtWidgets import (QApplication,QCheckBox,QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QGraphicsRectItem,QGraphicsScene,QGraphicsSimpleTextItem,QGraphicsView,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,QMainWindow,QMessageBox,QProgressBar,QPushButton,QSpinBox,QSplitter,QTabWidget,QVBoxLayout,QWidget,QAbstractItemView,QLineEdit)
from pdf_ops import detect_sheet_number_box,export_editor,merge_pdfs,page_count,split_pdf
APP='PDF Drawing Tool'

def fonts():
    out={}
    if sys.platform!='win32': return out
    try: import winreg
    except: return out
    sysf=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'; loc=Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft'/'Windows'/'Fonts'
    def resolve(v):
        p=Path(str(v).strip().strip('"'))
        if p.is_absolute() and p.exists(): return p
        for d in (loc,sysf):
            q=d/p
            if q.exists(): return q
    for hive,key in ((winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'),(winreg.HKEY_CURRENT_USER,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')):
        try:
            with winreg.OpenKey(hive,key) as k:
                i=0
                while 1:
                    try:n,v,_=winreg.EnumValue(k,i);i+=1
                    except OSError:break
                    p=resolve(v)
                    if p: out[str(n).split(' (',1)[0]]=str(p)
        except OSError:pass
    for p in (loc/'cordia.ttf',sysf/'cordia.ttf',sysf/'cordia.ttc'):
        if p.exists():out['Cordia New']=str(p);break
    return dict(sorted(out.items()))

class PDFList(QListWidget):
    dropped=Signal(list)
    def __init__(self):
        super().__init__();self.setAcceptDrops(True);self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
    def dragEnterEvent(self,e): e.acceptProposedAction() if e.mimeData().hasUrls() else super().dragEnterEvent(e)
    def dragMoveEvent(self,e): e.acceptProposedAction() if e.mimeData().hasUrls() else super().dragMoveEvent(e)
    def dropEvent(self,e):
        if e.mimeData().hasUrls():
            p=[u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile().lower().endswith('.pdf')]
            if p:self.dropped.emit(p);e.acceptProposedAction();return
        super().dropEvent(e)
    def paths(self):return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]

class View(QGraphicsView):
    box=Signal(QRectF)
    def __init__(self):
        super().__init__();self.start=None;self.tmp=None;self.draw=False;self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse);self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
    def wheelEvent(self,e):self.scale(1.25,1.25) if e.angleDelta().y()>0 else self.scale(.8,.8)
    def select_box(self):self.draw=True;self.setDragMode(QGraphicsView.DragMode.NoDrag)
    def mousePressEvent(self,e):
        if self.draw and e.button()==Qt.MouseButton.LeftButton:
            self.start=self.mapToScene(e.position().toPoint());self.tmp=QGraphicsRectItem(QRectF(self.start,self.start));self.tmp.setPen(QPen(QColor(220,40,40),2));self.scene().addItem(self.tmp);return
        super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        if self.tmp:self.tmp.setRect(QRectF(self.start,self.mapToScene(e.position().toPoint())).normalized());return
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self,e):
        if self.tmp:
            r=QRectF(self.start,self.mapToScene(e.position().toPoint())).normalized();self.scene().removeItem(self.tmp);self.tmp=self.start=None;self.draw=False;self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag);self.box.emit(r);return
        super().mouseReleaseEvent(e)

class Editor(QWidget):
    def __init__(self):
        super().__init__();self.pages=[];self.render_size=None;self.page_pts=None;self.sheet=None;self.fmap=fonts();self.ui()
    def ui(self):
        root=QVBoxLayout(self);top=QHBoxLayout();add=QPushButton('Add PDFs');add.clicked.connect(self.pick);rm=QPushButton('Remove');rm.clicked.connect(self.remove);top.addWidget(add);top.addWidget(rm);top.addStretch();self.info=QLabel();top.addWidget(self.info);root.addLayout(top)
        sp=QSplitter(Qt.Orientation.Horizontal);root.addWidget(sp,1);self.list=PDFList();self.list.dropped.connect(self.add);sp.addWidget(self.list)
        c=QWidget();cl=QVBoxLayout(c);nav=QHBoxLayout();self.pg=QSpinBox();self.pg.setMinimum(1);self.pg.valueChanged.connect(self.render);pr=QPushButton('◀');nx=QPushButton('▶');pr.clicked.connect(lambda:self.pg.setValue(max(1,self.pg.value()-1)));nx.clicked.connect(lambda:self.pg.setValue(min(self.pg.maximum(),self.pg.value()+1)));self.pl=QLabel();nav.addWidget(pr);nav.addWidget(self.pg);nav.addWidget(nx);nav.addWidget(self.pl);nav.addStretch();cl.addLayout(nav)
        tools=QHBoxLayout();zin=QPushButton('+');zout=QPushButton('−');fit=QPushButton('Fit');manual=QPushButton('Manual Sheet Box');zin.clicked.connect(lambda:self.view.scale(1.25,1.25));zout.clicked.connect(lambda:self.view.scale(.8,.8));fit.clicked.connect(self.fit);manual.clicked.connect(self.manual);[tools.addWidget(w) for w in (zout,zin,fit,manual)];tools.addStretch();cl.addLayout(tools)
        self.scene=QGraphicsScene();self.view=View();self.view.setScene(self.scene);self.view.setBackgroundBrush(QColor(50,50,50));self.view.box.connect(self.boxmade);cl.addWidget(self.view,1);self.status=QLabel('Add PDF — auto detect will find the แผ่นที่ cell.');cl.addWidget(self.status);sp.addWidget(c)
        r=QWidget();f=QFormLayout(r);self.start=QSpinBox();self.start.setRange(-999999,999999);self.start.setValue(4);self.detect=QPushButton('Auto Detect Sheet No.');self.detect.clicked.connect(lambda:self.autodetect(False));self.autoload=QCheckBox('Auto detect on load');self.autoload.setChecked(True);self.font=QComboBox();[self.font.addItem(n,p) for n,p in self.fmap.items()];i=self.font.findText('Cordia New');self.font.setCurrentIndex(i if i>=0 else 0);self.size=QDoubleSpinBox();self.size.setRange(3,100);self.size.setValue(12);self.cleanup=QComboBox();self.cleanup.addItem('Keep annotations','keep');self.cleanup.addItem('Remove AutoCAD SHX annotations','shx');self.cleanup.addItem('Remove SHX + Text notes','all_text');self.cleanup.setCurrentIndex(1);self.merge=QCheckBox('Merge inputs into one PDF');self.merge.setChecked(True);self.export=QPushButton('Export PDF');self.export.clicked.connect(self.save);self.progress=QProgressBar()
        for a,b in [('Start sheet',self.start),('',self.detect),('',self.autoload),('Font',self.font),('Font size',self.size),('Cleanup',self.cleanup),('',self.merge),('',self.export),('',self.progress)]:f.addRow(a,b)
        self.start.valueChanged.connect(self.sync);self.size.valueChanged.connect(self.sync);self.font.currentIndexChanged.connect(self.sync);sp.addWidget(r);sp.setSizes([250,900,330])
    def pick(self):p,_=QFileDialog.getOpenFileNames(self,'Add PDFs','','PDF Files (*.pdf)');self.add(p)
    def add(self,ps):
        ex=set(self.list.paths())
        for p in ps:
            if p in ex:continue
            try:n=page_count(p)
            except Exception as e:QMessageBox.warning(self,'PDF error',str(e));continue
            it=QListWidgetItem(f'{Path(p).name} ({n} pages)');it.setData(Qt.ItemDataRole.UserRole,p);self.list.addItem(it);ex.add(p)
        self.rebuild()
    def remove(self):
        for x in self.list.selectedItems():self.list.takeItem(self.list.row(x))
        self.rebuild()
    def rebuild(self):
        self.pages=[]
        for p in self.list.paths():self.pages += [(p,i) for i in range(page_count(p))]
        self.info.setText(f'{self.list.count()} files / {len(self.pages)} pages');self.pg.setMaximum(max(1,len(self.pages)));self.pg.setValue(1)
        if self.pages:
            self.render()
            if self.autoload.isChecked() and self.sheet is None:self.autodetect(True)
    def render(self):
        if not self.pages:return
        gi=min(self.pg.value()-1,len(self.pages)-1);p,i=self.pages[gi]
        with fitz.open(p) as d:
            page=d[i];pix=page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False);im=QImage(pix.samples,pix.width,pix.height,pix.stride,QImage.Format.Format_RGB888).copy();pm=QPixmap.fromImage(im);self.scene.clear();self.scene.addPixmap(pm);self.scene.setSceneRect(QRectF(0,0,pm.width(),pm.height()));self.render_size=(pm.width(),pm.height());self.page_pts=(page.rect.width,page.rect.height);self.pl.setText(f'Page {gi+1}/{len(self.pages)} — {Path(p).name}');self.draw();self.fit()
    def fit(self):
        if self.scene.sceneRect().width():self.view.fitInView(self.scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
    def fpath(self):return self.font.currentData() if self.font.count() else None
    def fname(self):return self.font.currentText() if self.font.count() else 'Helvetica'
    def manual(self):self.view.select_box();self.status.setText('Drag the exact แผ่นที่ cell.')
    def boxmade(self,r):
        w,h=self.render_size;self.sheet={'type':'sheet_number','box':[r.left()/w,r.top()/h,r.right()/w,r.bottom()/h],'start_number':self.start.value(),'font_name':self.fname(),'font_path':self.fpath(),'font_size':self.size.value(),'scope':{'mode':'all'}};self.status.setText('Sheet No.: manual box ✓');self.draw()
    def autodetect(self,silent=False):
        if not self.pages:return False
        d=None
        for p in self.list.paths():
            d=detect_sheet_number_box(p)
            if d:break
        if not d:
            self.status.setText('Auto detect failed — use Manual Sheet Box.')
            if not silent:QMessageBox.warning(self,'Not detected','Could not find แผ่นที่ cell.')
            return False
        self.sheet={'type':'sheet_number','box':list(d['box_norm']),'start_number':self.start.value(),'font_name':self.fname(),'font_path':self.fpath(),'font_size':self.size.value(),'scope':{'mode':'all'}};self.status.setText('Sheet No.: AUTO-DETECTED ✓');self.draw();return True
    def sync(self,*_):
        if self.sheet:self.sheet.update(start_number=self.start.value(),font_name=self.fname(),font_path=self.fpath(),font_size=self.size.value());self.draw()
    def draw(self):
        if not self.sheet or not self.render_size:return
        w,h=self.render_size;x1,y1,x2,y2=self.sheet['box'];r=QRectF(x1*w,y1*h,(x2-x1)*w,(y2-y1)*h);g=QGraphicsRectItem(r);g.setPen(QPen(QColor(220,40,40),1));self.scene.addItem(g);n=self.start.value()+self.pg.value()-1;t=QGraphicsSimpleTextItem(str(n));f=QFont(self.fname());f.setPixelSize(max(1,int(self.size.value()*(w/self.page_pts[0]))));t.setFont(f);b=t.boundingRect();t.setPos(r.center().x()-b.width()/2,r.center().y()-b.height()/2);self.scene.addItem(t)
    def save(self):
        files=self.list.paths()
        if not files:return
        if self.sheet is None and self.autoload.isChecked():self.autodetect(True)
        if self.sheet is None:QMessageBox.warning(self,'No sheet box','Auto Detect or define Manual Sheet Box first.');return
        self.sync();merge=self.merge.isChecked()
        if merge:
            out,_=QFileDialog.getSaveFileName(self,'Save PDF','Edited_Merged.pdf','PDF Files (*.pdf)')
            if not out:return
            if not out.lower().endswith('.pdf'):out+='.pdf'
        else:
            out=QFileDialog.getExistingDirectory(self,'Output folder')
            if not out:return
        def prog(a,b):self.progress.setValue(int(a*100/max(1,b)));QApplication.processEvents()
        try:r=export_editor(files,out,[copy.deepcopy(self.sheet)],cleanup_mode=self.cleanup.currentData(),merge=merge,progress_cb=prog);self.progress.setValue(100);QMessageBox.information(self,'Finished',f"Exported {r['pages']} pages.\nRemoved annotations: {r['removed_annotations']}")
        except Exception as e:QMessageBox.critical(self,'Export failed',str(e))

class Merge(QWidget):
    def __init__(self):
        super().__init__();l=QVBoxLayout(self);self.list=PDFList();self.list.dropped.connect(self.add);b=QPushButton('Add PDFs');b.clicked.connect(self.pick);m=QPushButton('Merge');m.clicked.connect(self.run);l.addWidget(b);l.addWidget(self.list,1);l.addWidget(m)
    def pick(self):p,_=QFileDialog.getOpenFileNames(self,'Add','','PDF Files (*.pdf)');self.add(p)
    def add(self,ps):
        for p in ps:it=QListWidgetItem(Path(p).name);it.setData(Qt.ItemDataRole.UserRole,p);self.list.addItem(it)
    def run(self):
        if not self.list.paths():return
        out,_=QFileDialog.getSaveFileName(self,'Save','Merged.pdf','PDF Files (*.pdf)')
        if not out:return
        if not out.lower().endswith('.pdf'):out+='.pdf'
        try:n=merge_pdfs(self.list.paths(),out);QMessageBox.information(self,'Done',f'{n} pages merged.')
        except Exception as e:QMessageBox.critical(self,'Error',str(e))

class Split(QWidget):
    def __init__(self):
        super().__init__();f=QFormLayout(self);self.path=QLineEdit();self.path.setReadOnly(True);b=QPushButton('Choose PDF');b.clicked.connect(self.pick);self.seq=QCheckBox('Sequence filenames');self.start=QSpinBox();self.start.setValue(1);run=QPushButton('Split');run.clicked.connect(self.run);f.addRow(self.path,b);f.addRow(self.seq);f.addRow('Start',self.start);f.addRow(run)
    def pick(self):p,_=QFileDialog.getOpenFileName(self,'Choose','','PDF Files (*.pdf)');self.path.setText(p)
    def run(self):
        if not self.path.text():return
        out=QFileDialog.getExistingDirectory(self,'Output folder')
        if not out:return
        try:p=split_pdf(self.path.text(),out,self.seq.isChecked(),self.start.value());QMessageBox.information(self,'Done',f'Created {len(p)} files.')
        except Exception as e:QMessageBox.critical(self,'Error',str(e))

class Main(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle(APP);self.resize(1500,900);t=QTabWidget();t.addTab(Editor(),'Editor');t.addTab(Merge(),'Merge');t.addTab(Split(),'Split');self.setCentralWidget(t)
if __name__=='__main__':
    a=QApplication(sys.argv);a.setApplicationName(APP);w=Main();w.show();sys.exit(a.exec())
