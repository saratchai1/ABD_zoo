;;; ================================================================
;;; AUTOSHEET V12.10 - STRONG DRAWING-SCALE REBUILD
;;; 2026-09-11
;;;
;;; Visual bug found on another drawing:
;;; A3 and A1 scale rows can still overlap on the same baseline.
;;;
;;; Required visual result:
;;;   มาตราส่วน :                 1:500 A3
;;;                               1:250 A1
;;;
;;; This patch makes placement deterministic using visual bounding boxes,
;;; forces distinct A3/A1 objects, increases row spacing, and provides
;;; AUTOSHEETSCALEONLY for isolated testing without rerunning the full workflow.
;;; ================================================================

(setq *AS12:Version* "2026-09-11-V12.10-SCALE-REBUILD")
(setq *AS1210:GapInHeights* 25.0)
(setq *AS1210:RowPitchInHeights* 2.25)

(defun AS1210:ObjectHeight (obj / bh th)
  (setq bh (AS10:BBoxHeight obj)
        th (AS12:Height obj))
  (cond
    ((and (numberp th) (> th 1.0e-9)) (max bh th))
    ((numberp bh) bh)
    (T 1.0)))

(defun AS1210:DistinctNearestA1 (header a3 candidates / filtered)
  (setq filtered candidates)
  (if a3 (setq filtered (vl-remove a3 filtered)))
  (AS10:Nearest header filtered))

(defun AS1210:DistinctNearestA3 (header a1 candidates / filtered)
  (setq filtered candidates)
  (if a1 (setq filtered (vl-remove a1 filtered)))
  (AS10:Nearest header filtered))

(defun AS10:PlaceGroup
  (header a3obj a1obj /
          h gap headerRight headerBottom targetX targetA3Y targetA1Y
          ok3 ok1)

  (setq h
    (max
      (AS1210:ObjectHeight header)
      (AS1210:ObjectHeight a3obj)
      (AS1210:ObjectHeight a1obj)))

  (setq gap (* *AS1210:GapInHeights* h)
        headerRight (AS10:VisualRight header)
        headerBottom (AS10:VisualBottom header))

  (if (or (null headerRight) (null headerBottom))
    nil
    (progn
      (setq targetX (+ headerRight gap)
            targetA3Y headerBottom
            targetA1Y (- targetA3Y (* *AS1210:RowPitchInHeights* h)))

      (setq ok3 (AS10:MoveBBoxMinTo a3obj targetX targetA3Y)
            ok1 (AS10:MoveBBoxMinTo a1obj targetX targetA1Y))

      (and ok3 ok1))))

(defun AS10:NormalizeSpace
  (space ref /
         headers a3s a1s
         obj header a3 a1 prepared placed
         fixed skipped copiedA3 copiedA1)

  (setq headers nil
        a3s nil
        a1s nil
        fixed 0
        skipped 0
        copiedA3 0
        copiedA1 0)

  (vlax-for obj space
    (cond
      ((AS10:ThaiHeaderP obj ref)
       (setq headers (cons obj headers)))
      ((AS10:A3P obj ref)
       (setq a3s (cons obj a3s)))
      ((AS10:A1P obj ref)
       (setq a1s (cons obj a1s)))))

  (foreach header headers
    (setq a3 (AS10:Nearest header (vl-remove header a3s))
          a1 (AS1210:DistinctNearestA1 header a3 (vl-remove header a1s)))

    (if (and (null a3) a1)
      (setq a3
        (AS1210:DistinctNearestA3 header a1 (vl-remove header a3s))))

    (setq prepared (AS10:PrepareGroup header a3 a1))

    (if prepared
      (progn
        (if (eq (nth 0 prepared) (nth 1 prepared))
          (progn
            (setq obj (AS10:MakeCopy (nth 0 prepared)))
            (if obj
              (progn
                (AS10:Put obj (AS10:FormatA1 (nth 3 prepared)))
                (setq prepared
                  (list
                    (nth 0 prepared)
                    obj
                    (nth 2 prepared)
                    (nth 3 prepared)
                    (nth 4 prepared)
                    1))))))

        (setq placed
          (AS10:PlaceGroup
            header
            (nth 0 prepared)
            (nth 1 prepared)))

        (if placed
          (progn
            (setq fixed (1+ fixed)
                  copiedA3 (+ copiedA3 (nth 4 prepared))
                  copiedA1 (+ copiedA1 (nth 5 prepared)))
            (if a3 (setq a3s (vl-remove a3 a3s)))
            (if a1 (setq a1s (vl-remove a1 a1s))))
          (setq skipped (1+ skipped))))
      (setq skipped (1+ skipped))))

  (list fixed skipped copiedA3 copiedA1))

(defun AS129:ScaleGroupAlignedP (header a3 a1 / h headerRight headerBottom x3 y3 x1 y1)
  (if (and header a3 a1)
    (progn
      (setq h
        (max
          (AS1210:ObjectHeight header)
          (AS1210:ObjectHeight a3)
          (AS1210:ObjectHeight a1))
        headerRight (AS10:VisualRight header)
        headerBottom (AS10:VisualBottom header)
        x3 (AS10:VisualLeft a3)
        y3 (AS10:VisualBottom a3)
        x1 (AS10:VisualLeft a1)
        y1 (AS10:VisualBottom a1))
      (and
        headerRight headerBottom x3 y3 x1 y1
        (<= (abs (- x3 x1)) (* h 0.30))
        (<= (abs (- y3 headerBottom)) (* h 0.65))
        (> x3 (+ headerRight (* h 3.0)))
        (< y1 (- y3 (* h 1.35)))
        (> y1 (- y3 (* h 3.20)))))
    nil))

(defun AS1210:PrintScaleQAAll (doc / layout status total bad)
  (setq total 0 bad 0)
  (princ "\n---------------- DRAWING SCALE GEOMETRY QA ----------------")
  (foreach layout (SA3:PaperLayouts doc)
    (setq status (AS129:ScaleAlignmentStatus layout)
          total (+ total (car status))
          bad (+ bad (cadr status)))
    (princ
      (strcat
        "\n  " (vla-get-Name layout)
        " | groups=" (itoa (car status))
        " | misaligned=" (itoa (cadr status))
        " | " (if (= (cadr status) 0) "PASS" "FAIL"))))
  (princ "\n-----------------------------------------------------------")
  (list total bad))

(defun c:AUTOSHEETSCALEONLY (/ acad doc contentResult gridResult qa)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))

  (princ "\n================================================")
  (princ "\nAUTOSHEETSCALEONLY V12.10")
  (princ "\nDRAWING SCALE CONTENT + GEOMETRY ONLY / NO SAVE")
  (princ "\n================================================")

  (setq contentResult (AS6:FormatDrawingScales doc))
  (setq gridResult (AS10:NormalizeAllDrawingScales doc))

  (vla-Regen doc acAllViewports)
  (SA3:ForcePaperSpace doc)

  (princ
    (strcat
      "\nScale groups standardized : " (itoa (nth 0 gridResult))
      "\nScale groups skipped      : " (itoa (nth 1 gridResult))
      "\nA3 rows created           : " (itoa (nth 2 gridResult))
      "\nA1 rows created           : " (itoa (nth 3 gridResult))))

  (setq qa (AS1210:PrintScaleQAAll doc))
  (princ
    (strcat
      "\nTOTAL scale groups=" (itoa (car qa))
      " | misaligned=" (itoa (cadr qa))))
  (princ "\nNO AUTOMATIC SAVE.")
  (princ))

(defun c:AUTOSHEETSCALECHECK (/ acad doc)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad))
  (AS1210:PrintScaleQAAll doc)
  (princ))

(princ "\nAUTOSHEET V12.10 strong scale rebuild loaded.")
(princ "\nRecommended test: AUTOSHEETSCALECHECK -> AUTOSHEETSCALEONLY -> inspect -> AUTOSHEETSCALECHECK")
(princ)
