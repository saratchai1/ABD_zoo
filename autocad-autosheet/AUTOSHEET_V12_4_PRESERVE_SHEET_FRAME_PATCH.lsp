;;; ================================================================
;;; AUTOSHEET V12.4 - PRESERVE ABD ZOO FULL-SHEET FRAME
;;; 2026-09-11
;;;
;;; Critical correction from first V12.3 apply:
;;; `NTT ABD_Zoo I` is NOT a disposable titlebox-only block.
;;; Diagnostic bbox ≈ 0.4205 x 0.297 m, so it is the full A3 sheet/frame
;;; container. Deleting/replacing it removes the attached border/titlebox
;;; graphics. For the ABD Zoo profile we therefore PRESERVE the block and
;;; standardize only its direct Paper-space data fields + viewport/plot/cleanup.
;;;
;;; V12.4:
;;; - never classifies ABD Zoo full-sheet block as "old titlebox to delete"
;;; - still uses it as the local-coordinate reference for TITLE/CODE/SCALE
;;; - skips titlebox replacement and residual-block cleanup on ABD Zoo layouts
;;; - preserves all existing sheet-frame geometry
;;; - keeps the V12 scan / profile safety / before-after QA workflow
;;; ================================================================

(setq *AS12:Version* "2026-09-11-V12.4-PRESERVE-SHEET-FRAME")

(defun AS124:ABDZooLayoutP (layout / refs)
  (setq refs (AS123:RecognizedRefs layout))
  (and (= (length refs) 1)
       (AS123:ABDZooTitleBoxP (car refs))))

(defun AS124:AllLayoutsABDZooP (doc / ok layout)
  (setq ok T)
  (foreach layout (SA3:PaperLayouts doc)
    (if (not (AS124:ABDZooLayoutP layout))
      (setq ok nil)))
  ok)

;;; IMPORTANT:
;;; Restore deletion semantics: ABD Zoo full-sheet frames must NOT be deleted.
;;; Historical disposable titleboxes remain eligible.
(defun SA3:OldOrEmbeddedTitleBoxP (entity / upper point)
  (if (= (AS12:ObjName entity) "ACDBBLOCKREFERENCE")
    (progn
      (setq upper (strcase (AS12:BlockNameSafe entity))
            point (AS12:GetInsertionPoint entity))
      (and
        (not (AS123:ABDZooTitleBoxP entity))
        (or
          (= upper "TITLE BLOCK A3")
          (and point
               (< (abs (car point)) 1.0e-8)
               (< (abs (cadr point)) 1.0e-8)
               (or
                 (= upper "NTT ABD")
                 (vl-string-search "TITLEBLOCK_A3_TYPICAL" upper)
                 (vl-string-search "G$CDDD1724B" upper)
                 (vl-string-search "TITLEBOX_G_CDDD1724B" upper)
                 (vl-string-search "SA3_AFRICA_TITLEBOX" upper))))))
    nil))

;;; Keep ABD Zoo recognized as the reference frame for local-coordinate
;;; TITLE/CODE/SCALE detection.
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

(defun AS124:RunABDZoo
  (doc / redResult scaleResult fieldResult layout
         titleTotal codeTotal scaleTotal scaleChangedTotal)

  (setq titleTotal 0 codeTotal 0 scaleTotal 0 scaleChangedTotal 0)

  (princ "\n\n[STEP 1/6] Delete red Paper-space line/polyline geometry...")
  (setq redResult (AS6:DeleteRedPaperGeometry doc))
  (princ
    (strcat
      "\n  Red geometry deleted: " (itoa (car redResult))
      ", failed: " (itoa (cadr redResult))))

  (princ "\n\n[STEP 2/6] Move MV / floating Viewports / VPCLIP to Defpoints...")
  (c:A3MVVPDEFPOINTS)

  (princ "\n\n[STEP 3/6] Preserve ABD Zoo full-sheet frame...")
  (princ "\n  NO titlebox replacement.")
  (princ "\n  NO residual block deletion.")
  (princ "\n  Existing NTT ABD_Zoo I sheet/frame remains untouched.")

  (princ "\n\n[STEP 4/6] Reformat drawing-area scale...")
  (setq scaleResult (AS6:FormatDrawingScales doc))
  (AS6:PrintScaleResult (car scaleResult))
  (AS6:PrintScaleResult (cadr scaleResult))
  (princ
    (strcat
      "\n  Thai scale-header gaps adjusted: "
      (itoa (caddr scaleResult))))

  (princ "\n\n[STEP 5/6] Format ONLY TITLE / CODE / SCALE Paper-space fields...")
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

  (princ "\n\n[STEP 6/6] Apply verified A3 PDF plot settings...")
  (foreach layout (SA3:PaperLayouts doc)
    (AS3:StandardizePlotOne layout))

  ;; Do NOT call SA3:SendTitleBoxesToBack for ABD Zoo full-sheet frames.
  ;; Their draw order is part of the original sheet composition.
  (vla-Regen doc acAllViewports)

  (list
    redResult
    scaleResult
    titleTotal
    codeTotal
    scaleTotal
    scaleChangedTotal))

(defun AS12:RunApplyEngine (doc / result)
  (if (AS124:AllLayoutsABDZooP doc)
    (progn
      (princ "\n[V12.4] ABD Zoo full-sheet profile detected on all layouts.")
      (princ "\n[V12.4] Using PRESERVE-SHEET-FRAME apply engine.")
      (setq result
        (vl-catch-all-apply 'AS124:RunABDZoo (list doc))))
    (progn
      (princ "\n[V12.4] Non-ABD-Zoo layout detected.")
      (princ "\n[V12.4] Falling back to frozen V11/V10 engine.")
      (setq result
        (vl-catch-all-apply 'AS10:Run (list doc)))))

  (if (vl-catch-all-error-p result)
    (progn
      (princ
        (strcat
          "\n[AUTOSHEET V12.4 ERROR] "
          (vl-catch-all-error-message result)))
      nil)
    result))

(defun c:AUTOSHEETFRAMECHECK (/ acad doc layout refs)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))
  (princ "\n---------------- SHEET FRAME CHECK ----------------")
  (foreach layout (SA3:PaperLayouts doc)
    (setq refs (AS123:RecognizedRefs layout))
    (princ
      (strcat
        "\n  " (vla-get-Name layout)
        " | refs=" (itoa (length refs))
        " | ABD-Zoo-frame="
        (if (and (= (length refs) 1)
                 (AS123:ABDZooTitleBoxP (car refs)))
          "YES"
          "NO"))))
  (princ "\n---------------------------------------------------")
  (princ))

(princ "\nAUTOSHEET V12.4 preserve-sheet-frame fix loaded.")
(princ "\nIMPORTANT: reopen the untouched backup DWG before testing V12.4.")
(princ "\nRun AUTOSHEETFRAMECHECK, AUTOSHEETSCAN, then AUTOSHEET.")
(princ)
