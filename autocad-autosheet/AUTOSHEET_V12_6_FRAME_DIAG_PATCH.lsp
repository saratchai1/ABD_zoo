;;; ================================================================
;;; AUTOSHEET V12.6 - FRAME STRUCTURE DIAGNOSTIC
;;; 2026-09-11
;;; ================================================================

(setq *AS12:Version* "2026-09-11-V12.6-FRAME-DIAG")

(defun AS126:ObjLayer (obj / r)
  (setq r (vl-catch-all-apply 'vla-get-Layer (list obj)))
  (if (vl-catch-all-error-p r) "<none>" (AS12:ValueString r)))

(defun AS126:KeywordFrameTextP (txt / up)
  (setq up (strcase (if (= (type txt) 'STR) txt "")))
  (or
    (vl-string-search "DRAWING" up)
    (vl-string-search "TITLE" up)
    (vl-string-search "SCALE" up)
    (vl-string-search "SHEET" up)
    (vl-string-search "PROJECT" up)
    (vl-string-search "AS-BUILT" up)
    (vl-string-search "DESIGN" up)
    (vl-string-search "CHECK" up)
    (vl-string-search "APPROV" up)
    (vl-string-search "REV" up)
    (vl-string-search "RSDT" up)
    (vl-string-search "ABD" up)
    (vl-string-search "มาตราส่วน" txt)))

(defun AS126:PrintNestedBlock (obj idx / name bbox ip sx sy rot)
  (setq name (AS12:BlockNameSafe obj)
        bbox (AS12:GetBBoxSafe obj)
        ip (AS12:GetInsertionPoint obj)
        sx (AS12:SafeGet obj 'XScaleFactor)
        sy (AS12:SafeGet obj 'YScaleFactor)
        rot (AS12:SafeGet obj 'Rotation))
  (princ
    (strcat
      "\n  [NESTED BLOCK " (itoa idx) "]"
      " name=" name
      " | layer=" (AS126:ObjLayer obj)
      " | ins=" (AS12:PointString ip)
      " | bbox=" (AS12:BBoxString bbox)
      " | sx=" (AS12:ValueString sx)
      " | sy=" (AS12:ValueString sy)
      " | rot=" (AS12:ValueString rot))))

(defun AS126:PrintNestedText (obj idx / txt bbox p)
  (setq txt (AS12:SafeText obj)
        bbox (AS12:GetBBoxSafe obj)
        p (SA3:EntityPoint obj))
  (princ
    (strcat
      "\n  [NESTED TEXT " (itoa idx) "]"
      " \"" txt "\""
      " | layer=" (AS126:ObjLayer obj)
      " | pos=" (AS12:PointString p)
      " | bbox=" (AS12:BBoxString bbox))))

(defun AS126:DiagFrame
  (doc / tab layout refs frame objects obj objName
         blockCount textCount typeCounts pair)

  (setq tab (getvar "CTAB")
        layout (AS12:FindLayoutByName doc tab))

  (cond
    ((or (null layout) (= (strcase tab) "MODEL"))
     (princ "\nAUTOSHEETDIAGFRAME: switch to a Paper Space layout first."))

    ((/= (length (AS123:RecognizedRefs layout)) 1)
     (princ
       (strcat
         "\nAUTOSHEETDIAGFRAME: expected exactly 1 recognized frame, found "
         (itoa (length (AS123:RecognizedRefs layout)))
         ".")))

    (T
     (setq refs (AS123:RecognizedRefs layout)
           frame (car refs)
           *A3V27:Visited* nil
           objects (A3V27:CollectReferenceTree doc frame)
           blockCount 0
           textCount 0
           typeCounts nil)

     (princ "\n================================================")
     (princ "\nAUTOSHEETDIAGFRAME V12.6 - READ ONLY")
     (princ (strcat "\nLayout: " tab))
     (princ (strcat "\nFrame: " (AS12:BlockNameSafe frame)))
     (princ "\nGoal: identify old titlebox sub-assembly inside preserved full-sheet frame")
     (princ "\n================================================")

     (princ "\n\n[NESTED BLOCK REFERENCES]")
     (foreach obj objects
       (setq objName (AS12:ObjName obj))
       (if (= objName "ACDBBLOCKREFERENCE")
         (progn
           (setq blockCount (1+ blockCount))
           (AS126:PrintNestedBlock obj blockCount))))
     (if (= blockCount 0)
       (princ "\n  <none>"))

     (princ "\n\n[TITLEBLOCK-RELATED NESTED TEXT]")
     (foreach obj objects
       (if (and (AS12:TextP obj)
                (AS126:KeywordFrameTextP (AS12:SafeText obj)))
         (progn
           (setq textCount (1+ textCount))
           (AS126:PrintNestedText obj textCount))))
     (if (= textCount 0)
       (princ "\n  <none>"))

     (princ "\n\n[OBJECT TYPE COUNTS]")
     (foreach obj objects
       (setq objName (AS12:ObjName obj)
             pair (assoc objName typeCounts))
       (if pair
         (setq typeCounts
           (subst (cons objName (1+ (cdr pair))) pair typeCounts))
         (setq typeCounts
           (cons (cons objName 1) typeCounts))))
     (foreach pair typeCounts
       (princ
         (strcat
           "\n  " (car pair) " = " (itoa (cdr pair)))))

     (princ "\n================================================")
     (princ "\nCopy this entire output back before changing frame/titlebox geometry.")))

  (setq *A3V27:Visited* nil)
  (princ))

(defun c:AUTOSHEETDIAGFRAME (/ acad doc)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))
  (AS126:DiagFrame doc)
  (princ))

(princ "\nAUTOSHEET V12.6 frame diagnostic loaded.")
(princ "\nCurrent behavior: fields/plot are standardized, but the old full-sheet frame is preserved.")
(princ "\nSwitch to D100.10 and run AUTOSHEETDIAGFRAME.")
(princ)
