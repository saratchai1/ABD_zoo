;;; AUTOSHEET V12.11 drawing-scale style patch
;;; Fixes drawing-area scale header/A3/A1 remaining in A Century Gothic.
;;; The patch changes style/font and width only; existing text height is preserved.

(setq *AS12:Version* "2026-09-11-V12.11-SCALE-STYLE-FIX")
(setq *AS1211:TargetStyle* "Cordia Shx")
(setq *AS1211:TargetWidth* 1.0)

(defun AS1211:StyleOKP (obj / style width)
  (setq style (AS12:SafeGet obj 'StyleName))
  (and
    (= (type style) 'STR)
    (= (strcase style) (strcase *AS1211:TargetStyle*))
    (if (vlax-property-available-p obj 'ScaleFactor)
      (progn
        (setq width (AS12:SafeGet obj 'ScaleFactor))
        (and (numberp width)
             (<= (abs (- width *AS1211:TargetWidth*)) 1.0e-6)))
      T)))

(defun AS1211:SetScaleStyleOnly (obj / styleResult cleanResult widthResult)
  (setq styleResult
    (vl-catch-all-apply 'vla-put-StyleName (list obj *AS1211:TargetStyle*)))
  (setq cleanResult
    (if (= (AS12:ObjName obj) "ACDBMTEXT")
      (A3V51:CleanMTextOverrides obj)
      T))
  (setq widthResult T)
  (if (vlax-property-available-p obj 'ScaleFactor T)
    (setq widthResult
      (not
        (vl-catch-all-error-p
          (vl-catch-all-apply
            'vlax-put-property
            (list obj 'ScaleFactor *AS1211:TargetWidth*))))))
  (vl-catch-all-apply 'vla-Update (list obj))
  (and (not (vl-catch-all-error-p styleResult)) cleanResult widthResult))

(defun AS1211:StyleScaleSpace (space ref / obj changed failed)
  (setq changed 0 failed 0)
  (vlax-for obj space
    (if (or (AS10:ThaiHeaderP obj ref) (AS10:A3P obj ref) (AS10:A1P obj ref))
      (if (AS1211:SetScaleStyleOnly obj)
        (setq changed (1+ changed))
        (setq failed (1+ failed)))))
  (list changed failed))

(defun AS1211:StyleAllDrawingScales (doc / totalChanged totalFailed part layout ref)
  (setq totalChanged 0 totalFailed 0)
  (setq part (AS1211:StyleScaleSpace (vla-get-ModelSpace doc) nil)
        totalChanged (+ totalChanged (car part))
        totalFailed (+ totalFailed (cadr part)))
  (foreach layout (SA3:PaperLayouts doc)
    (setq ref (A3V51:LayoutTitleReference layout)
          part (AS1211:StyleScaleSpace (vla-get-Block layout) ref)
          totalChanged (+ totalChanged (car part))
          totalFailed (+ totalFailed (cadr part))))
  (list totalChanged totalFailed))

(defun AS1211:ScaleStyleStatus (layout / ref space objs obj bad)
  (setq ref (A3V51:LayoutTitleReference layout)
        space (vla-get-Block layout)
        objs nil bad 0)
  (vlax-for obj space
    (if (or (AS10:ThaiHeaderP obj ref) (AS10:A3P obj ref) (AS10:A1P obj ref))
      (setq objs (cons obj objs))))
  (foreach obj objs
    (if (not (AS1211:StyleOKP obj)) (setq bad (1+ bad))))
  (list (length objs) bad))

(princ "\nAUTOSHEET V12.11 scale-style patch loaded.")
(princ "\nDrawing scale header/A3/A1 -> Cordia Shx, width 1.0, height preserved.")
(princ)
