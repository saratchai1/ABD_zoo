;;; ================================================================
;;; AUTOSHEET V12.1 SCAN ROBUSTNESS FIX
;;; 2026-09-11
;;; ================================================================
(setq *AS12:Version* "2026-09-11-V12.1-SCAN-FIX")

(defun AS12:ValueString (v)
  (cond
    ((null v) "<none>")
    ((= (type v) 'STR) v)
    (T (vl-princ-to-string v))))

(defun AS12:GetConfigName (layout / r)
  (setq r (vl-catch-all-apply 'vla-get-ConfigName (list layout)))
  (if (vl-catch-all-error-p r) nil r))

(defun AS12:GetMediaName (layout / r)
  (setq r (vl-catch-all-apply 'vla-get-CanonicalMediaName (list layout)))
  (if (vl-catch-all-error-p r) nil r))

(defun AS12:GetStyleSheet (layout / r)
  (setq r (vl-catch-all-apply 'vla-get-StyleSheet (list layout)))
  (if (vl-catch-all-error-p r) nil r))

(defun AS12:CandidateTitleBoxes (layout / obj name candidates result)
  (setq candidates nil)
  (vlax-for obj (vla-get-Block layout)
    (setq name (AS12:ObjName obj))
    (if (= name "ACDBBLOCKREFERENCE")
      (progn
        (setq result
          (vl-catch-all-apply 'A3V38:TitleBoxCandidateP (list obj)))
        (if (and (not (vl-catch-all-error-p result)) result)
          (setq candidates (cons obj candidates))))))
  candidates)

(defun AS12:TitleDetection (layout / ref candidates)
  (setq ref (A3V51:LayoutTitleReference layout))
  (if ref
    (list 'PROFILED ref 1)
    (progn
      (setq candidates (AS12:CandidateTitleBoxes layout))
      (if candidates
        (list 'UNPROFILED nil (length candidates))
        (list 'NONE nil 0)))))

(defun AS12:PrintStatus (status label detail counts / pass warn fail prefix)
  (setq pass (car counts)
        warn (cadr counts)
        fail (caddr counts)
        prefix
          (cond
            ((eq status 'PASS) "PASS")
            ((eq status 'WARN) "WARN")
            (T "FAIL")))
  (princ
    (strcat
      "\n  " prefix "  " label
      (if detail (strcat " = " (AS12:ValueString detail)) "")))
  (cond
    ((eq status 'PASS) (list (1+ pass) warn fail))
    ((eq status 'WARN) (list pass (1+ warn) fail))
    (T (list pass warn (1+ fail)))))

(defun AS12:PlotterOKP (layout / c)
  (setq c (AS12:GetConfigName layout))
  (and (= (type c) 'STR)
       (= (strcase c) (strcase *AS12:TargetPlotter*))))

(defun AS12:PaperOKP (layout / media p)
  (setq media (AS12:GetMediaName layout)
        p (AS3:GetPaperSize layout))
  (and (= (type media) 'STR)
       (vl-string-search "A3" (strcase media))
       p
       (> (car p) (cadr p))))

(defun AS12:CTBOKP (layout / ctb)
  (setq ctb (AS12:GetStyleSheet layout))
  (and (= (type ctb) 'STR)
       (= (strcase ctb) (strcase *AS12:TargetCTB*))))

(defun AS12:CountPaths (layout / block obj name attrs a n)
  (setq block (vla-get-Block layout)
        n 0)
  (vlax-for obj block
    (setq name (AS12:ObjName obj))
    (cond
      ((and
         (member name '("ACDBTEXT" "ACDBMTEXT" "ACDBMLEADER"))
         (vlax-property-available-p obj 'TextString)
         (SA3:SourcePathTextP (AS12:SafeText obj)))
       (setq n (1+ n)))
      ((and
         (= name "ACDBBLOCKREFERENCE")
         (AS12:BoolTrueP (AS12:SafeGet obj 'HasAttributes)))
       (setq attrs (SA3:BlockAttributes obj))
       (foreach a attrs
         (if (SA3:SourcePathTextP (AS12:SafeText a))
           (setq n (1+ n)))))))
  n)

(defun AS12:ScanLayout
  (doc layout /
       detect mode candidateCount
       fields titles codes scales
       vp red paths counts
       plotType ctb media config)

  (setq counts '(0 0 0)
        detect (AS12:TitleDetection layout)
        mode (car detect)
        candidateCount (caddr detect))

  (princ (strcat "\n\n[LAYOUT] " (vla-get-Name layout)))

  (cond
    ((eq mode 'PROFILED)
     (setq counts
       (AS12:PrintStatus 'PASS "Title box" "recognized profile" counts)))
    ((eq mode 'UNPROFILED)
     (setq counts
       (AS12:PrintStatus
         'WARN
         "Title box"
         (strcat "candidate block(s)=" (itoa candidateCount)
                 "; profile unknown -> field QA skipped")
         counts)))
    (T
     (setq counts
       (AS12:PrintStatus 'FAIL "Title box" "no candidate detected" counts))))

  (if (eq mode 'PROFILED)
    (progn
      (setq fields (AS12:CollectTitleFields layout)
            titles (nth 1 fields)
            codes (nth 2 fields)
            scales (nth 3 fields))
      (setq counts
        (AS12:PrintStatus
          (if (AS12:CodesOKP codes) 'PASS 'FAIL)
          "Drawing code"
          (if (> (length codes) 0) "hyphen format" "missing")
          counts))
      (setq counts
        (AS12:PrintStatus
          (if (AS12:ScalesOKP scales) 'PASS 'FAIL)
          "Title scale"
          (if (> (length scales) 0) "A3/A1" "missing")
          counts))
      (setq counts
        (AS12:PrintStatus
          (if (AS12:FieldTypographyOKP titles) 'PASS 'FAIL)
          "Title typography"
          "Cordia Shx / H=0.0015 / W=1.0"
          counts))
      (setq counts
        (AS12:PrintStatus
          (if (AS12:FieldTypographyOKP codes) 'PASS 'FAIL)
          "Code typography"
          "Cordia Shx / H=0.0015 / W=1.0"
          counts))
      (setq counts
        (AS12:PrintStatus
          (if (AS12:FieldTypographyOKP scales) 'PASS 'FAIL)
          "Scale typography"
          "Cordia Shx / H=0.0015 / W=1.0"
          counts)))
    (progn
      (setq counts
        (AS12:PrintStatus 'WARN "Drawing code" "skipped - titlebox profile unknown" counts))
      (setq counts
        (AS12:PrintStatus 'WARN "Title scale" "skipped - titlebox profile unknown" counts))
      (setq counts
        (AS12:PrintStatus 'WARN "Title typography" "skipped - titlebox profile unknown" counts))
      (setq counts
        (AS12:PrintStatus 'WARN "Code typography" "skipped - titlebox profile unknown" counts))
      (setq counts
        (AS12:PrintStatus 'WARN "Scale typography" "skipped - titlebox profile unknown" counts))))

  (setq vp (AS12:ViewportStatus layout))
  (setq counts
    (AS12:PrintStatus
      (if (= (cadr vp) 0) 'PASS 'FAIL)
      "Viewport layer"
      (strcat "floating=" (itoa (car vp))
              ", non-Defpoints=" (itoa (cadr vp)))
      counts))

  (setq red (AS12:CountRed doc layout))
  (setq counts
    (AS12:PrintStatus
      (if (= red 0) 'PASS 'FAIL)
      "Red cleanup"
      (strcat "remaining=" (itoa red))
      counts))

  (setq paths (AS12:CountPaths layout))
  (setq counts
    (AS12:PrintStatus
      (if (= paths 0) 'PASS 'FAIL)
      "Source path cleanup"
      (strcat "remaining=" (itoa paths))
      counts))

  (setq config (AS12:GetConfigName layout))
  (setq counts
    (AS12:PrintStatus
      (if (AS12:PlotterOKP layout) 'PASS 'FAIL)
      "Plotter"
      (AS12:ValueString config)
      counts))

  (setq media (AS12:GetMediaName layout))
  (setq counts
    (AS12:PrintStatus
      (if (AS12:PaperOKP layout) 'PASS 'FAIL)
      "Paper/orientation"
      (AS12:ValueString media)
      counts))

  (setq plotType (AS12:SafeGet layout 'PlotType))
  (setq counts
    (AS12:PrintStatus
      (if (= plotType 4) 'PASS 'FAIL)
      "Plot area"
      (if (= plotType 4) "Window" (AS12:ValueString plotType))
      counts))

  (setq counts
    (AS12:PrintStatus
      (if (AS12:BoolTrueP (AS12:SafeGet layout 'CenterPlot)) 'PASS 'FAIL)
      "Center plot"
      "On"
      counts))

  (setq counts
    (AS12:PrintStatus
      (if (AS12:ScaleOKP layout) 'PASS 'FAIL)
      "Plot scale"
      "1 mm = 0.001 unit"
      counts))

  (setq ctb (AS12:GetStyleSheet layout))
  (setq counts
    (AS12:PrintStatus
      (if (AS12:CTBOKP layout) 'PASS 'FAIL)
      "Plot style"
      (AS12:ValueString ctb)
      counts))

  (setq counts
    (AS12:PrintStatus
      (if (AS12:BoolTrueP (AS12:SafeGet layout 'PlotWithPlotStyles)) 'PASS 'FAIL)
      "Plot with styles"
      "On"
      counts))

  (setq counts
    (AS12:PrintStatus
      (if (AS12:BoolTrueP (AS12:SafeGet layout 'PlotWithLineweights)) 'PASS 'FAIL)
      "Lineweights"
      "On"
      counts))

  (setq counts
    (AS12:PrintStatus
      (if (AS12:BoolTrueP (AS12:SafeGet layout 'PlotViewportsFirst)) 'PASS 'FAIL)
      "Paper space last"
      "On"
      counts))

  (princ
    (strcat "\n  SUMMARY pass=" (itoa (car counts))
            " warn=" (itoa (cadr counts))
            " fail=" (itoa (caddr counts))))

  (list
    (vla-get-Name layout)
    (car counts)
    (cadr counts)
    (caddr counts)))

(princ "\nAUTOSHEET V12.1 scan-fix loaded.")
(princ "\nRun AUTOSHEETSCAN again before running AUTOSHEET.")
(princ)
