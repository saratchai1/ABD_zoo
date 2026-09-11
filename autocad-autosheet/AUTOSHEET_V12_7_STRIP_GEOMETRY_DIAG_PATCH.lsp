;;; ================================================================
;;; AUTOSHEET V12.7 - LEGACY TITLE-STRIP GEOMETRY DIAGNOSTIC
;;; 2026-09-11
;;;
;;; V12.6 proved that NTT ABD_Zoo I has no nested block references;
;;; its legacy frame/titlebox is flattened into the block definition.
;;; This command reads the actual block definition and reports geometry
;;; intersecting the lower title-strip region so we can separate:
;;;   KEEP  = outer sheet border / drawing frame
;;;   REPLACE = legacy titlebox graphics
;;; before making any destructive edit.
;;; ================================================================

(setq *AS12:Version* "2026-09-11-V12.7-STRIP-GEOM-DIAG")
(setq *AS127:StripMaxY* 120.0)

(defun AS127:GetBlockDef (doc ref / blocks n r)
  (setq blocks (vla-get-Blocks doc)
        n (vl-catch-all-apply 'vla-get-Name (list ref)))
  (if (vl-catch-all-error-p n)
    nil
    (progn
      (setq r (vl-catch-all-apply 'vla-Item (list blocks n)))
      (if (vl-catch-all-error-p r) nil r))))

(defun AS127:BBoxIntersectsStripP (bbox / mn mx)
  (if bbox
    (progn
      (setq mn (car bbox)
            mx (cadr bbox))
      (and (<= (cadr mn) *AS127:StripMaxY*)
           (>= (cadr mx) -20.0)))
    nil))

(defun AS127:BBoxContainedInStripP (bbox / mn mx)
  (if bbox
    (progn
      (setq mn (car bbox)
            mx (cadr bbox))
      (and (>= (cadr mn) -20.0)
           (<= (cadr mx) *AS127:StripMaxY*)))
    nil))

(defun AS127:GeomP (obj / n)
  (setq n (AS12:ObjName obj))
  (member n
    '("ACDBLINE"
      "ACDBPOLYLINE"
      "ACDB2DPOLYLINE"
      "ACDB3DPOLYLINE"
      "ACDBLWPOLYLINE"
      "ACDBARC"
      "ACDBCIRCLE"
      "ACDBHATCH"
      "ACDBSPLINE"
      "ACDBELLIPSE"
      "ACDBSOLID")))

(defun AS127:PrintObject (obj idx class / n bbox)
  (setq n (AS12:ObjName obj)
        bbox (AS12:GetBBoxSafe obj))
  (princ
    (strcat
      "\n  [" class " " (itoa idx) "] "
      n
      " | layer=" (AS126:ObjLayer obj)
      " | bbox=" (AS12:BBoxString bbox))))

(defun AS127:PrintAllStripText (obj idx / txt bbox)
  (setq txt (AS12:SafeText obj)
        bbox (AS12:GetBBoxSafe obj))
  (princ
    (strcat
      "\n  [TEXT " (itoa idx) "] "
      "\"" txt "\""
      " | layer=" (AS126:ObjLayer obj)
      " | bbox=" (AS12:BBoxString bbox))))

(defun AS127:DiagStrip
  (doc / tab layout refs frame def obj bbox
         contained crossing textCount containedCount crossingCount otherCount)

  (setq tab (getvar "CTAB")
        layout (AS12:FindLayoutByName doc tab))

  (cond
    ((or (null layout) (= (strcase tab) "MODEL"))
     (princ "\nAUTOSHEETDIAGSTRIP: switch to a Paper Space layout first."))

    ((/= (length (AS123:RecognizedRefs layout)) 1)
     (princ
       (strcat
         "\nAUTOSHEETDIAGSTRIP: expected 1 ABD Zoo frame, found "
         (itoa (length (AS123:RecognizedRefs layout))) ".")))

    (T
     (setq refs (AS123:RecognizedRefs layout)
           frame (car refs)
           def (AS127:GetBlockDef doc frame))

     (if (null def)
       (princ "\nAUTOSHEETDIAGSTRIP: cannot open the frame block definition.")
       (progn
         (setq textCount 0
               containedCount 0
               crossingCount 0
               otherCount 0)

         (princ "\n================================================")
         (princ "\nAUTOSHEETDIAGSTRIP V12.7 - READ ONLY")
         (princ (strcat "\nLayout: " tab))
         (princ (strcat "\nFrame block: " (AS12:BlockNameSafe frame)))
         (princ (strcat "\nDiagnostic title-strip Y range: -20 .. "
                        (rtos *AS127:StripMaxY* 2 1)))
         (princ "\n================================================")

         (princ "\n\n[ALL TEXT INSIDE/INTERSECTING LOWER STRIP]")
         (vlax-for obj def
           (setq bbox (AS12:GetBBoxSafe obj))
           (if (and (AS12:TextP obj)
                    (AS127:BBoxIntersectsStripP bbox))
             (progn
               (setq textCount (1+ textCount))
               (AS127:PrintAllStripText obj textCount))))
         (if (= textCount 0)
           (princ "\n  <none>"))

         (princ "\n\n[GEOMETRY FULLY CONTAINED IN LOWER STRIP]")
         (vlax-for obj def
           (setq bbox (AS12:GetBBoxSafe obj))
           (if (and (AS127:GeomP obj)
                    (AS127:BBoxContainedInStripP bbox))
             (progn
               (setq containedCount (1+ containedCount))
               (AS127:PrintObject obj containedCount "CONTAINED"))))
         (if (= containedCount 0)
           (princ "\n  <none>"))

         (princ "\n\n[GEOMETRY CROSSING STRIP BOUNDARY]")
         (vlax-for obj def
           (setq bbox (AS12:GetBBoxSafe obj))
           (if (and (AS127:GeomP obj)
                    (AS127:BBoxIntersectsStripP bbox)
                    (not (AS127:BBoxContainedInStripP bbox)))
             (progn
               (setq crossingCount (1+ crossingCount))
               (AS127:PrintObject obj crossingCount "CROSSING"))))
         (if (= crossingCount 0)
           (princ "\n  <none>"))

         (princ "\n\n[SUMMARY]")
         (princ (strcat "\n  lower-strip text objects        = " (itoa textCount)))
         (princ (strcat "\n  contained geometry candidates   = " (itoa containedCount)))
         (princ (strcat "\n  crossing geometry (protect/clip)= " (itoa crossingCount)))
         (princ "\n================================================")
         (princ "\nCopy this entire output back. Do not modify the frame yet.")))))

  (princ))

(defun c:AUTOSHEETDIAGSTRIP (/ acad doc)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))
  (AS127:DiagStrip doc)
  (princ))

(princ "\nAUTOSHEET V12.7 strip-geometry diagnostic loaded.")
(princ "\nRun AUTOSHEETDIAGSTRIP on D100.10 or D100.14.")
(princ)
