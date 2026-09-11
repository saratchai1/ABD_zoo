;;; ================================================================
;;; AUTOSHEET V12.9 - DRAWING SCALE GRID + GEOMETRY QA
;;; 2026-09-11
;;;
;;; Fix from visual validation:
;;; Desired:
;;;   มาตราส่วน :        1:50 A3
;;;                      1:25 A1
;;; A3/A1 must share the same left X. A3 stays on the header row.
;;; V12.5 preserve-frame path formatted scale text but did not run the
;;; V10 geometric grid pass, so A1 could remain under the Thai header.
;;; ================================================================

(setq *AS12:Version* "2026-09-11-V12.9-SCALE-GRID-QA")

(defun AS129:ScaleGroupAlignedP (header a3 a1 / h headerRight headerBottom x3 y3 x1 y1)
  (if (and header a3 a1)
    (progn
      (setq h
        (max
          (AS10:BBoxHeight header)
          (AS10:BBoxHeight a3)
          (AS10:BBoxHeight a1))
        headerRight (AS10:VisualRight header)
        headerBottom (AS10:VisualBottom header)
        x3 (AS10:VisualLeft a3)
        y3 (AS10:VisualBottom a3)
        x1 (AS10:VisualLeft a1)
        y1 (AS10:VisualBottom a1))
      (and
        headerRight headerBottom x3 y3 x1 y1
        (<= (abs (- x3 x1)) (* h 0.35))
        (<= (abs (- y3 headerBottom)) (* h 0.75))
        (> x3 (+ headerRight (* h 3.0)))
        (< y1 (- y3 (* h 0.50)))
        (> y1 (- y3 (* h 2.50)))))
    nil))

(defun AS129:ScaleAlignmentStatus (layout / ref space headers a3s a1s obj header a3 a1
                                          groups bad)
  (setq ref (A3V51:LayoutTitleReference layout)
        space (vla-get-Block layout)
        headers nil
        a3s nil
        a1s nil
        groups 0
        bad 0)

  (vlax-for obj space
    (cond
      ((AS10:ThaiHeaderP obj ref)
       (setq headers (cons obj headers)))
      ((AS10:A3P obj ref)
       (setq a3s (cons obj a3s)))
      ((AS10:A1P obj ref)
       (setq a1s (cons obj a1s)))))

  (foreach header headers
    (setq a3 (AS10:Nearest header a3s)
          a1 (AS10:Nearest header a1s))
    (setq groups (1+ groups))
    (if (not (AS129:ScaleGroupAlignedP header a3 a1))
      (setq bad (1+ bad)))
    (if a3 (setq a3s (vl-remove a3 a3s)))
    (if a1 (setq a1s (vl-remove a1 a1s))))

  (list groups bad))

(defun AS124:RunABDZoo
  (doc / redResult scaleResult scaleGridResult fieldResult layout
         titleTotal codeTotal scaleTotal scaleChangedTotal)

  (setq titleTotal 0
        codeTotal 0
        scaleTotal 0
        scaleChangedTotal 0)

  (princ "\n\n[STEP 1/7] Delete red Paper-space line/polyline geometry...")
  (setq redResult (AS6:DeleteRedPaperGeometry doc))
  (princ
    (strcat
      "\n  Red geometry deleted: " (itoa (car redResult))
      ", failed: " (itoa (cadr redResult))))

  (princ "\n\n[STEP 2/7] Move MV / floating Viewports / VPCLIP to Defpoints...")
  (c:A3MVVPDEFPOINTS)

  (princ "\n\n[STEP 3/7] Preserve ABD Zoo full-sheet frame...")
  (princ "\n  NO titlebox replacement.")
  (princ "\n  NO residual block deletion.")
  (princ "\n  Existing NTT ABD_Zoo I sheet/frame remains untouched.")

  (princ "\n\n[STEP 4/7] Normalize drawing-area scale content...")
  (setq scaleResult (AS6:FormatDrawingScales doc))
  (AS6:PrintScaleResult (car scaleResult))
  (AS6:PrintScaleResult (cadr scaleResult))
  (princ
    (strcat
      "\n  Thai scale-header gaps adjusted: "
      (itoa (caddr scaleResult))))

  (princ "\n\n[STEP 5/7] Apply FINAL geometric drawing-scale grid...")
  (setq scaleGridResult (AS10:NormalizeAllDrawingScales doc))
  (princ
    (strcat
      "\n  Scale groups standardized : " (itoa (nth 0 scaleGridResult))
      "\n  Scale groups skipped      : " (itoa (nth 1 scaleGridResult))
      "\n  A3 rows created           : " (itoa (nth 2 scaleGridResult))
      "\n  A1 rows created           : " (itoa (nth 3 scaleGridResult))))

  (princ "\n\n[STEP 6/7] Format ONLY TITLE / CODE / SCALE Paper-space fields...")
  (A3V51:EnsureCordiaStyle doc)
  (foreach layout (SA3:PaperLayouts doc)
    (setq fieldResult (AS6:NormalizeTitleFieldsOne layout)
          titleTotal (+ titleTotal (nth 0 fieldResult))
          codeTotal (+ codeTotal (nth 1 fieldResult))
          scaleTotal (+ scaleTotal (nth 2 fieldResult))
          scaleChangedTotal (+ scaleChangedTotal (nth 3 fieldResult))))

  (princ
    (strcat
      "\n  TITLE fields -> Cordia Shx / H=0.0015 / W=1.0 : "
      (itoa titleTotal)))
  (princ
    (strcat
      "\n  CODE fields  -> Cordia Shx / H=0.0015 / W=1.0 : "
      (itoa codeTotal)))
  (princ
    (strcat
      "\n  SCALE fields -> Cordia Shx / H=0.0015 / W=1.0 : "
      (itoa scaleTotal)))

  (princ "\n\n[STEP 7/7] Apply verified A3 PDF plot settings...")
  (foreach layout (SA3:PaperLayouts doc)
    (AS3:StandardizePlotOne layout))

  (vla-Regen doc acAllViewports)

  (list
    redResult
    scaleResult
    scaleGridResult
    titleTotal
    codeTotal
    scaleTotal
    scaleChangedTotal))

(setq AS129:ScanLayoutBase AS12:ScanLayout)

(defun AS12:ScanLayout (doc layout / base align counts)
  (setq base (AS129:ScanLayoutBase doc layout)
        align (AS129:ScaleAlignmentStatus layout)
        counts (list (nth 1 base) (nth 2 base) (nth 3 base)))

  (setq counts
    (AS12:PrintStatus
      (if (and (> (car align) 0) (= (cadr align) 0)) 'PASS 'FAIL)
      "Drawing scale alignment"
      (strcat
        "groups=" (itoa (car align))
        ", misaligned=" (itoa (cadr align))
        " | A3/A1 same X")
      counts))

  (list
    (car base)
    (car counts)
    (cadr counts)
    (caddr counts)))

(princ "\nAUTOSHEET V12.9 scale-grid QA loaded.")
(princ "\nVisual rule: Thai header + A3 on first row; A1 directly below A3 at same X.")
(princ "\nUse a FRESH backup DWG for the next apply validation.")
(princ)
