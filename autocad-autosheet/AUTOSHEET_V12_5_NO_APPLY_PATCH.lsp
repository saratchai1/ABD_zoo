;;; AUTOSHEET V12.5 - REMOVE UNSUPPORTED APPLY
(setq *AS12:Version* "2026-09-11-V12.5-NO-APPLY")

(defun AS125:ListMax (values / best x)
  (if values
    (progn
      (setq best (car values))
      (foreach x (cdr values)
        (if (> x best) (setq best x)))
      best)
    nil))

(defun AS125:ListMin (values / best x)
  (if values
    (progn
      (setq best (car values))
      (foreach x (cdr values)
        (if (< x best) (setq best x)))
      best)
    nil))

(defun AS5:HighLow (values / high low)
  (cond
    ((null values) nil)
    ((= (length values) 1)
     (setq high (car values)
           low (/ high 2.0))
     (list high low))
    (T
     (setq high (AS125:ListMax values)
           low  (AS125:ListMin values))
     (list high low))))

(defun AS10:PrepareGroup
  (header a3Candidate a1Candidate /
          headerVals a3Vals a1Vals combined high low
          a3obj a1obj copiedA3 copiedA1)
  (setq headerVals (AS10:ScaleVals header)
        a3Vals (if a3Candidate (AS10:ScaleVals a3Candidate) nil)
        a1Vals (if a1Candidate (AS10:ScaleVals a1Candidate) nil)
        high nil low nil
        a3obj a3Candidate a1obj a1Candidate
        copiedA3 0 copiedA1 0)
  (cond
    ((and a3Vals a1Vals)
     (setq combined (append a3Vals a1Vals)
           high (AS125:ListMax combined)
           low  (AS125:ListMin combined)))
    ((>= (length headerVals) 2)
     (setq high (AS125:ListMax headerVals)
           low  (AS125:ListMin headerVals)))
    ((and (AS10:HeaderContainsA3P header) headerVals a1Vals)
     (setq high (car headerVals) low (car a1Vals)))
    ((and (AS10:HeaderContainsA1P header) headerVals a3Vals)
     (setq high (car a3Vals) low (car headerVals)))
    ((and a3Vals (null a1Vals))
     (setq high (car a3Vals) low (/ high 2.0)))
    ((and a1Vals (null a3Vals))
     (setq low (car a1Vals) high (* low 2.0)))
    ((and (AS10:HeaderContainsA3P header) headerVals)
     (setq high (car headerVals) low (/ high 2.0)))
    ((and (AS10:HeaderContainsA1P header) headerVals)
     (setq low (car headerVals) high (* low 2.0))))
  (if (or (null high) (null low))
    nil
    (progn
      (if (or (AS10:HeaderContainsA3P header)
              (AS10:HeaderContainsA1P header)
              (>= (length headerVals) 1))
        (progn
          (if (null a3obj)
            (progn (setq a3obj (AS10:MakeCopy header)) (if a3obj (setq copiedA3 1))))
          (if (null a1obj)
            (progn (setq a1obj (AS10:MakeCopy header)) (if a1obj (setq copiedA1 1))))
          (AS10:Put header "มาตราส่วน :")))
      (if (and (null a3obj) a1obj)
        (progn (setq a3obj (AS10:MakeCopy a1obj)) (if a3obj (setq copiedA3 1))))
      (if (and (null a1obj) a3obj)
        (progn (setq a1obj (AS10:MakeCopy a3obj)) (if a1obj (setq copiedA1 1))))
      (if (and a3obj a1obj)
        (progn
          (AS10:Put a3obj (AS10:FormatA3 high))
          (AS10:Put a1obj (AS10:FormatA1 low))
          (list a3obj a1obj high low copiedA3 copiedA1))
        nil))))

(princ "\nAUTOSHEET V12.5 no-APPLY fix loaded.")
(princ "\nUse a FRESH BACKUP DWG for the next full end-to-end validation.")
(princ)