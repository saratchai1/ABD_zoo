;;; ================================================================
;;; AUTOSHEET V12.3 - ABD ZOO TITLEBOX PROFILE + SAFE APPLY GUARD
;;; 2026-09-11
;;;
;;; Real DWG diagnostic:
;;;   block name = NTT ABD_Zoo I
;;;   insertion  = (0,0,0)
;;;   bbox       = (0,0,-0.0004) -> (0.4205,0.297,0)
;;;   scale      = 0.0005 x 0.0005
;;;   attributes = NO
;;;
;;; This patch:
;;; - recognizes the ABD Zoo titlebox by name + origin + scale + sheet geometry
;;; - lets the existing local-coordinate field rules read direct Paper-space text
;;; - lets titlebox replacement delete the correct legacy block before insertion
;;; - aborts AUTOSHEET if any layout has zero or multiple recognized titlebox refs
;;; - tightens A3 QA to ISO full bleed A3 + effective landscape
;;; ================================================================

(setq *AS12:Version* "2026-09-11-V12.3-ABD-ZOO-PROFILE")
(setq *AS123:ProfileName* "ABD_ZOO_NTT_A3_V1")

(defun AS123:Near (a b tol)
  (and (numberp a) (numberp b) (<= (abs (- a b)) tol)))

(defun AS123:ABDZooNameP (name / upper)
  (and
    (= (type name) 'STR)
    (setq upper (strcase name))
    (or
      (= upper "NTT ABD_ZOO I")
      (= upper "NTT ABD_ZOO")
      (= upper "NTT ABD")
      (= (vl-string-search "NTT ABD_ZOO" upper) 0))))

(defun AS123:ABDZooTitleBoxP
  (entity / objName blockName ip sx sy bbox mn mx width height)
  (setq objName (AS12:ObjName entity))
  (if (/= objName "ACDBBLOCKREFERENCE")
    nil
    (progn
      (setq blockName (AS12:BlockNameSafe entity)
            ip (AS12:GetInsertionPoint entity)
            sx (AS12:SafeGet entity 'XScaleFactor)
            sy (AS12:SafeGet entity 'YScaleFactor)
            bbox (AS12:GetBBoxSafe entity))
      (if bbox
        (setq mn (car bbox)
              mx (cadr bbox)
              width (abs (- (car mx) (car mn)))
              height (abs (- (cadr mx) (cadr mn)))))
      (and
        (AS123:ABDZooNameP blockName)
        ip
        (AS123:Near (car ip) 0.0 1.0e-7)
        (AS123:Near (cadr ip) 0.0 1.0e-7)
        (AS123:Near sx 0.0005 0.00005)
        (AS123:Near sy 0.0005 0.00005)
        bbox
        (>= width 0.400)
        (<= width 0.440)
        (>= height 0.280)
        (<= height 0.310)))))

(defun SA3:OldOrEmbeddedTitleBoxP (entity / upper point)
  (if (= (AS12:ObjName entity) "ACDBBLOCKREFERENCE")
    (progn
      (setq upper (strcase (AS12:BlockNameSafe entity))
            point (AS12:GetInsertionPoint entity))
      (or
        (AS123:ABDZooTitleBoxP entity)
        (= upper "TITLE BLOCK A3")
        (and point
             (< (abs (car point)) 1.0e-8)
             (< (abs (cadr point)) 1.0e-8)
             (or
               (= upper "NTT ABD")
               (vl-string-search "TITLEBLOCK_A3_TYPICAL" upper)
               (vl-string-search "G$CDDD1724B" upper)
               (vl-string-search "TITLEBOX_G_CDDD1724B" upper)
               (vl-string-search "SA3_AFRICA_TITLEBOX" upper)))))
    nil))

(defun SA3:TitleBoxReferenceP (entity / name upper)
  (if (= (AS12:ObjName entity) "ACDBBLOCKREFERENCE")
    (progn
      (setq name (AS12:BlockNameSafe entity)
            upper (strcase name))
      (or
        (AS123:ABDZooTitleBoxP entity)
        (vl-string-search "G$CDDD1724B" upper)
        (vl-string-search "TITLE BLOCK A3" upper)
        (vl-string-search "TITLEBOX_G_CDDD1724B" upper)
        (vl-string-search "SA3_AFRICA_TITLEBOX" upper)))
    nil))

(defun AS123:RecognizedRefs (layout / obj refs)
  (setq refs nil)
  (vlax-for obj (vla-get-Block layout)
    (if (and
          (= (AS12:ObjName obj) "ACDBBLOCKREFERENCE")
          (SA3:TitleBoxReferenceP obj))
      (setq refs (cons obj refs))))
  refs)

(defun AS123:TitleboxSafetyCheck (doc / ok layout refs count)
  (setq ok T)
  (princ "\n---------------- TITLEBOX SAFETY CHECK ----------------")
  (foreach layout (SA3:PaperLayouts doc)
    (setq refs (AS123:RecognizedRefs layout)
          count (length refs))
    (cond
      ((= count 1)
       (princ
         (strcat
           "\n  PASS " (vla-get-Name layout)
           " | recognized refs=1"
           (if (AS123:ABDZooTitleBoxP (car refs))
             (strcat " | profile=" *AS123:ProfileName*)
             " | profile=embedded/legacy"))))
      ((= count 0)
       (setq ok nil)
       (princ
         (strcat
           "\n  FAIL " (vla-get-Name layout)
           " | recognized refs=0 | AUTOSHEET WILL ABORT")))
      (T
       (setq ok nil)
       (princ
         (strcat
           "\n  FAIL " (vla-get-Name layout)
           " | recognized refs=" (itoa count)
           " | ambiguous | AUTOSHEET WILL ABORT")))))
  (princ "\n-------------------------------------------------------")
  ok)

(defun AS123:FullBleedA3MediaP (media / upper)
  (and
    (= (type media) 'STR)
    (setq upper (strcase media))
    (vl-string-search "A3" upper)
    (vl-string-search "FULL" upper)
    (vl-string-search "BLEED" upper)))

(defun AS12:PaperOKP (layout / media p)
  (setq media (AS12:GetMediaName layout)
        p (AS3:GetPaperSize layout))
  (and
    (AS123:FullBleedA3MediaP media)
    p
    (> (car p) (cadr p))))

(defun c:AUTOSHEET (/ acad doc before apply after)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))

  (princ "\n================================================")
  (princ "\nAUTOSHEET V12.3 ABD ZOO PROFILE")
  (princ "\nSCAN -> SAFETY CHECK -> APPLY -> RE-SCAN")
  (princ "\nNO AUTOMATIC SAVE")
  (princ "\n================================================")

  (setq before (AS12:ScanAll doc "BEFORE"))

  (if (not (AS123:TitleboxSafetyCheck doc))
    (progn
      (princ "\n\nABORT: Titlebox safety check failed.")
      (princ "\nNo AUTOSHEET apply actions were run.")
      (princ "\nUse AUTOSHEETDIAGTITLE on the failing layout."))
    (progn
      (princ "\n\n[AUTOSHEET V12.3 APPLY] Running frozen V11/V10 engine...")
      (setq apply (AS12:RunApplyEngine doc))
      (if apply
        (progn
          (vla-Regen doc acAllViewports)
          (SA3:ForcePaperSpace doc)
          (setq after (AS12:ScanAll doc "AFTER"))

          (princ "\n\n---------------- IMPROVEMENT ----------------")
          (princ
            (strcat
              "\nCompliance before : "
              (rtos (nth 4 before) 2 1) "%"))
          (princ
            (strcat
              "\nCompliance after  : "
              (rtos (nth 4 after) 2 1) "%"))
          (princ
            (strcat
              "\nChange            : "
              (rtos (- (nth 4 after) (nth 4 before)) 2 1)
              " percentage points"))
          (princ "\n------------------------------------------------")
          (princ "\nNO AUTOMATIC SAVE. Review 2-3 layouts and Plot Preview before Ctrl+S."))
        (princ "\nApply failed. AFTER scan was not run."))))

  (princ))

(defun c:AUTOSHEETPROFILECHECK (/ acad doc)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))
  (AS123:TitleboxSafetyCheck doc)
  (princ))

(princ "\nAUTOSHEET V12.3 ABD Zoo profile loaded.")
(princ "\nRun AUTOSHEETSCAN first. Then AUTOSHEETPROFILECHECK.")
(princ "\nOnly run AUTOSHEET if all titlebox safety rows PASS.")
(princ)
