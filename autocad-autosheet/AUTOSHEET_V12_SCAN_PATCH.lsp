;;; ================================================================
;;; AUTOSHEET V12 CLEAN CORE + READ-ONLY QA SCAN
;;; 2026-09-11
;;; ================================================================
(vl-load-com)

(setq *AS12:Version* "2026-09-11-V12-CLEAN-CORE")
(setq *AS12:TargetFont* "Cordia Shx")
(setq *AS12:TargetHeight* 0.0015)
(setq *AS12:TargetWidth* 1.0)
(setq *AS12:TargetCTB* "SIPHYA_LT_R1.ctb")
(setq *AS12:TargetPlotter* "DWG To PDF.pc3")

(defun AS12:Approx (a b tol)
  (and (numberp a) (numberp b) (<= (abs (- a b)) tol)))

(defun AS12:ObjName (obj / r)
  (setq r (vl-catch-all-apply 'vla-get-ObjectName (list obj)))
  (if (vl-catch-all-error-p r) "" (strcase r)))

(defun AS12:SafeGet (obj prop / r)
  (setq r (vl-catch-all-apply 'vlax-get-property (list obj prop)))
  (if (vl-catch-all-error-p r) nil r))

(defun AS12:SafeText (obj / r)
  (setq r (vl-catch-all-apply 'vla-get-TextString (list obj)))
  (if (vl-catch-all-error-p r) "" r))

(defun AS12:TextP (obj)
  (member (AS12:ObjName obj)
    '("ACDBTEXT" "ACDBMTEXT" "ACDBATTRIBUTEREFERENCE" "ACDBATTRIBUTEDEFINITION")))

(defun AS12:Height (obj / r)
  (cond
    ((vlax-property-available-p obj 'TextHeight)
     (setq r (vl-catch-all-apply 'vlax-get-property (list obj 'TextHeight))))
    ((vlax-property-available-p obj 'Height)
     (setq r (vl-catch-all-apply 'vlax-get-property (list obj 'Height))))
    (T (setq r nil)))
  (if (vl-catch-all-error-p r) nil r))

(defun AS12:FieldTypographyOKP (objects / ok obj style h w)
  (setq ok (> (length objects) 0))
  (foreach obj objects
    (setq style (AS12:SafeGet obj 'StyleName)
          h (AS12:Height obj))
    (if (or (null style)
            (/= (strcase style) (strcase *AS12:TargetFont*))
            (null h)
            (not (AS12:Approx h *AS12:TargetHeight* 1.0e-7)))
      (setq ok nil))
    (if (vlax-property-available-p obj 'ScaleFactor)
      (progn
        (setq w (AS12:SafeGet obj 'ScaleFactor))
        (if (or (null w) (not (AS12:Approx w *AS12:TargetWidth* 1.0e-6)))
          (setq ok nil)))))
  ok)

(defun AS12:CollectTitleFields (layout / ref block obj point local role titles codes scales sheets)
  (setq ref (A3V51:LayoutTitleReference layout)
        titles nil
        codes nil
        scales nil
        sheets nil)
  (if ref
    (progn
      (setq block (vla-get-Block layout))
      (vlax-for obj block
        (if (AS12:TextP obj)
          (progn
            (setq point (SA3:EntityPoint obj)
                  local (if point (A3V51:LocalPoint ref point) nil)
                  role (if local (A3V51:FieldRole local) nil))
            (cond
              ((eq role 'TITLE) (setq titles (cons obj titles)))
              ((eq role 'CODE)  (setq codes (cons obj codes)))
              ((eq role 'SCALE) (setq scales (cons obj scales)))
              ((eq role 'SHEET) (setq sheets (cons obj sheets)))))))))
  (list ref titles codes scales sheets))

(defun AS12:CodesOKP (codes / ok obj txt)
  (setq ok (> (length codes) 0))
  (foreach obj codes
    (setq txt (AS12:SafeText obj))
    (if (vl-string-search "_" txt) (setq ok nil)))
  ok)

(defun AS12:ScalesOKP (scales / obj txt up a3 a1)
  (setq a3 nil a1 nil)
  (foreach obj scales
    (setq txt (AS12:SafeText obj)
          up (strcase txt))
    (if (and (vl-string-search "1:" up) (vl-string-search "A3" up)) (setq a3 T))
    (if (and (vl-string-search "1:" up) (vl-string-search "A1" up)) (setq a1 T)))
  (and a3 a1))

(defun AS12:ViewportStatus (layout / obj n total bad layer)
  (setq total 0 bad 0)
  (vlax-for obj (vla-get-Block layout)
    (if (= (AS12:ObjName obj) "ACDBVIEWPORT")
      (progn
        (setq n (SA3:ViewportNumber obj))
        (if (and n (> n 1))
          (progn
            (setq total (1+ total)
                  layer (AS12:SafeGet obj 'Layer))
            (if (or (null layer) (/= (strcase layer) "DEFPOINTS"))
              (setq bad (1+ bad))))))))
  (list total bad))

(defun AS12:CountRed (doc layout / obj n)
  (setq n 0)
  (vlax-for obj (vla-get-Block layout)
    (if (and (AS6:RedGeometryP obj) (AS6:RedP doc obj))
      (setq n (1+ n))))
  n)

(defun AS12:CountPaths (layout / block obj name attrs a n)
  (setq block (vla-get-Block layout)
        n 0)
  (vlax-for obj block
    (setq name (AS12:ObjName obj))
    (cond
      ((and (member name '("ACDBTEXT" "ACDBMTEXT" "ACDBMLEADER"))
            (vlax-property-available-p obj 'TextString)
            (SA3:SourcePathTextP (AS12:SafeText obj)))
       (setq n (1+ n)))
      ((and (= name "ACDBBLOCKREFERENCE")
            (= (AS12:SafeGet obj 'HasAttributes) :vlax-true))
       (setq attrs (SA3:BlockAttributes obj))
       (foreach a attrs
         (if (SA3:SourcePathTextP (AS12:SafeText a))
           (setq n (1+ n)))))))
  n)

(defun AS12:BoolTrueP (v)
  (or (eq v T) (eq v :vlax-true) (and (numberp v) (/= v 0))))

(defun AS12:PaperOKP (layout / media p)
  (setq media (AS3:SafeGet layout 'CanonicalMediaName)
        p (AS3:GetPaperSize layout))
  (and media (vl-string-search "A3" (strcase media)) p (> (car p) (cadr p))))

(defun AS12:ScaleOKP (layout / pair)
  (setq pair (AS3:ScalePair layout))
  (and pair
       (AS12:Approx (car pair) 1.0 1.0e-9)
       (AS12:Approx (cadr pair) 0.001 1.0e-9)))

(defun AS12:CTBOKP (layout / ctb)
  (setq ctb (AS3:SafeGet layout 'StyleSheet))
  (and ctb (= (strcase ctb) (strcase *AS12:TargetCTB*))))

(defun AS12:PlotterOKP (layout / c)
  (setq c (AS3:SafeGet layout 'ConfigName))
  (and c (= (strcase c) (strcase *AS12:TargetPlotter*))))

(defun AS12:PrintCheck (ok label detail counts / pass warn fail)
  (setq pass (car counts)
        warn (cadr counts)
        fail (caddr counts))
  (princ (strcat "\n  " (if ok "PASS" "FAIL") "  " label
                 (if detail (strcat " = " detail) "")))
  (if ok
    (list (1+ pass) warn fail)
    (list pass warn (1+ fail))))

(defun AS12:ScanLayout (doc layout / fields ref titles codes scales vp red paths counts
                              plotType ctb media)
  (setq counts '(0 0 0)
        fields (AS12:CollectTitleFields layout)
        ref (nth 0 fields)
        titles (nth 1 fields)
        codes (nth 2 fields)
        scales (nth 3 fields))
  (princ (strcat "\n\n[LAYOUT] " (vla-get-Name layout)))
  (setq counts (AS12:PrintCheck (not (null ref)) "Title box"
                 (if ref "recognized" "not recognized") counts))
  (setq counts (AS12:PrintCheck (AS12:CodesOKP codes) "Drawing code"
                 (if (> (length codes) 0) "hyphen format" "missing") counts))
  (setq counts (AS12:PrintCheck (AS12:ScalesOKP scales) "Title scale"
                 (if (> (length scales) 0) "A3/A1" "missing") counts))
  (setq counts (AS12:PrintCheck (AS12:FieldTypographyOKP titles) "Title typography"
                 "Cordia Shx / H=0.0015 / W=1.0" counts))
  (setq counts (AS12:PrintCheck (AS12:FieldTypographyOKP codes) "Code typography"
                 "Cordia Shx / H=0.0015 / W=1.0" counts))
  (setq counts (AS12:PrintCheck (AS12:FieldTypographyOKP scales) "Scale typography"
                 "Cordia Shx / H=0.0015 / W=1.0" counts))
  (setq vp (AS12:ViewportStatus layout))
  (setq counts (AS12:PrintCheck (= (cadr vp) 0) "Viewport layer"
                 (strcat "floating=" (itoa (car vp)) ", non-Defpoints=" (itoa (cadr vp))) counts))
  (setq red (AS12:CountRed doc layout))
  (setq counts (AS12:PrintCheck (= red 0) "Red cleanup"
                 (strcat "remaining=" (itoa red)) counts))
  (setq paths (AS12:CountPaths layout))
  (setq counts (AS12:PrintCheck (= paths 0) "Source path cleanup"
                 (strcat "remaining=" (itoa paths)) counts))
  (setq counts (AS12:PrintCheck (AS12:PlotterOKP layout) "Plotter"
                 (or (AS3:SafeGet layout 'ConfigName) "<none>") counts))
  (setq media (AS3:SafeGet layout 'CanonicalMediaName))
  (setq counts (AS12:PrintCheck (AS12:PaperOKP layout) "Paper/orientation"
                 (if media media "<none>") counts))
  (setq plotType (AS3:SafeGet layout 'PlotType))
  (setq counts (AS12:PrintCheck (= plotType 4) "Plot area" "Window" counts))
  (setq counts (AS12:PrintCheck (AS12:BoolTrueP (AS3:SafeGet layout 'CenterPlot)) "Center plot" "On" counts))
  (setq counts (AS12:PrintCheck (AS12:ScaleOKP layout) "Plot scale" "1 mm = 0.001 unit" counts))
  (setq ctb (AS3:SafeGet layout 'StyleSheet))
  (setq counts (AS12:PrintCheck (AS12:CTBOKP layout) "Plot style"
                 (if ctb ctb "<none>") counts))
  (setq counts (AS12:PrintCheck (AS12:BoolTrueP (AS3:SafeGet layout 'PlotWithPlotStyles)) "Plot with styles" "On" counts))
  (setq counts (AS12:PrintCheck (AS12:BoolTrueP (AS3:SafeGet layout 'PlotWithLineweights)) "Lineweights" "On" counts))
  (setq counts (AS12:PrintCheck (AS12:BoolTrueP (AS3:SafeGet layout 'PlotViewportsFirst)) "Paper space last" "On" counts))
  (princ (strcat "\n  SUMMARY pass=" (itoa (car counts))
                 " warn=" (itoa (cadr counts))
                 " fail=" (itoa (caddr counts))))
  (list (vla-get-Name layout) (car counts) (cadr counts) (caddr counts)))

(defun AS12:ScanAll (doc label / layouts layout r pass warn fail checks compliance)
  (setq layouts (SA3:PaperLayouts doc)
        pass 0 warn 0 fail 0)
  (princ "\n================================================")
  (princ (strcat "\nAUTOSHEETSCAN V12 - " label))
  (princ "\nREAD ONLY QA / NO INTENTIONAL DRAWING CHANGES")
  (princ "\n================================================")
  (foreach layout layouts
    (setq r (AS12:ScanLayout doc layout)
          pass (+ pass (nth 1 r))
          warn (+ warn (nth 2 r))
          fail (+ fail (nth 3 r))))
  (setq checks (+ pass fail))
  (if (> checks 0)
    (setq compliance (* 100.0 (/ (float pass) (float checks))))
    (setq compliance 0.0))
  (princ "\n\n---------------- V12 QA TOTAL ----------------")
  (princ (strcat "\nLayouts     : " (itoa (length layouts))))
  (princ (strcat "\nPASS        : " (itoa pass)))
  (princ (strcat "\nWARN        : " (itoa warn)))
  (princ (strcat "\nFAIL        : " (itoa fail)))
  (princ (strcat "\nCompliance  : " (rtos compliance 2 1) "%"))
  (if (> fail 0)
    (princ "\nRESULT      : REVIEW / APPLY AUTOSHEET")
    (princ "\nRESULT      : READY TO PLOT"))
  (princ "\n================================================")
  (list (length layouts) pass warn fail compliance))

(defun AS12:RunApplyEngine (doc / result)
  (setq result (vl-catch-all-apply 'AS10:Run (list doc)))
  (if (vl-catch-all-error-p result)
    (progn
      (princ (strcat "\n[AUTOSHEET V12 ERROR] " (vl-catch-all-error-message result)))
      nil)
    result))

(defun c:AUTOSHEETSCAN (/ acad doc)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))
  (AS12:ScanAll doc "CURRENT STATE")
  (princ "\nNo intentional changes were made by AUTOSHEETSCAN.")
  (princ))

(defun c:AUTOSHEET (/ acad doc before apply after)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))
  (princ "\n================================================")
  (princ "\nAUTOSHEET V12 CLEAN CORE")
  (princ "\nSCAN -> APPLY PROVEN ENGINE -> RE-SCAN")
  (princ "\nNO AUTOMATIC SAVE")
  (princ "\n================================================")
  (setq before (AS12:ScanAll doc "BEFORE"))
  (princ "\n\n[AUTOSHEET V12 APPLY] Running frozen V11/V10 engine...")
  (setq apply (AS12:RunApplyEngine doc))
  (if apply
    (progn
      (vla-Regen doc acAllViewports)
      (SA3:ForcePaperSpace doc)
      (setq after (AS12:ScanAll doc "AFTER"))
      (princ "\n\n---------------- IMPROVEMENT ----------------")
      (princ (strcat "\nCompliance before : " (rtos (nth 4 before) 2 1) "%"))
      (princ (strcat "\nCompliance after  : " (rtos (nth 4 after) 2 1) "%"))
      (princ (strcat "\nChange            : "
                     (rtos (- (nth 4 after) (nth 4 before)) 2 1)
                     " percentage points"))
      (princ "\n------------------------------------------------")
      (princ "\nNO AUTOMATIC SAVE. Review the DWG before Ctrl+S."))
    (princ "\nApply failed. AFTER scan was not run."))
  (princ))

(defun c:AUTOSHEETVERSION ()
  (princ (strcat "\nAUTOSHEET version: " *AS12:Version*))
  (princ "\nArchitecture: V12 scan/validate shell over frozen V11/V10 apply engine.")
  (princ))

(princ "\nAUTOSHEET V12 CLEAN CORE loaded.")
(princ "\nRecommended: AUTOSHEETSCAN first, then AUTOSHEET on a backup DWG.")
(princ "\nCommands: AUTOSHEETSCAN, AUTOSHEET, AUTOSHEETCTB, AUTOSHEETVERSION")
(princ)
