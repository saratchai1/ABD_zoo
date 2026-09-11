;;; ================================================================
;;; AUTOSHEET V12.8 - NEW TITLEBOX OVERLAY PREVIEW
;;; 2026-09-11
;;;
;;; Purpose:
;;; - Do NOT delete the existing ABD Zoo strip yet.
;;; - Insert the embedded replacement titlebox on the CURRENT layout only.
;;; - Print the actual overlay bbox in Paper Space.
;;; - Compare it against the legacy strip target bbox.
;;; - Provide AUTOSHEETOVERLAYCLEAN to remove preview refs again.
;;;
;;; This is a controlled alignment test before any selective deletion.
;;; ================================================================

(setq *AS12:Version* "2026-09-11-V12.8-TITLEBOX-OVERLAY-PREVIEW")
(setq *AS128:OverlayHandles* nil)
(setq *AS128:PreviewLayer* "V12_TITLEBOX_PREVIEW")

(defun AS128:EnsurePreviewLayer (doc / layers layer r)
  (setq layers (vla-get-Layers doc)
        r (vl-catch-all-apply 'vla-Item (list layers *AS128:PreviewLayer*)))
  (if (vl-catch-all-error-p r)
    (setq layer (vla-Add layers *AS128:PreviewLayer*))
    (setq layer r))
  (if layer
    (vl-catch-all-apply 'vla-put-Color (list layer 6)))
  layer)

(defun AS128:CurrentPaperLayout (doc / tab lay found)
  (setq tab (getvar "CTAB")
        found nil)
  (if (/= (strcase tab) "MODEL")
    (vlax-for lay (vla-get-Layouts doc)
      (if (= (strcase (vla-get-Name lay)) (strcase tab))
        (setq found lay))))
  found)

(defun AS128:ExistingEmbeddedRefs (layout / obj refs)
  (setq refs nil)
  (vlax-for obj (vla-get-Block layout)
    (if (and
          (= (AS12:ObjName obj) "ACDBBLOCKREFERENCE")
          (AS6:EmbeddedTitleRefP obj))
      (setq refs (cons obj refs))))
  refs)

(defun AS128:LegacyStripPaperBBox ()
  ;; ABD Zoo source-space strip:
  ;; X 20.5..820.5, Y 20..90.707071
  ;; frame reference scale = 0.0005
  (list
    (list (* 20.5 0.0005) (* 20.0 0.0005) 0.0)
    (list (* 820.5 0.0005) (* 90.707071 0.0005) 0.0)))

(defun AS128:PrintBBoxCompare (overlayBBox / legacy)
  (setq legacy (AS128:LegacyStripPaperBBox))
  (princ "\n\n[BBOX COMPARISON]")
  (princ
    (strcat
      "\n  Legacy strip target = "
      (AS12:BBoxString legacy)))
  (princ
    (strcat
      "\n  New overlay bbox    = "
      (AS12:BBoxString overlayBBox)))
  (if (and overlayBBox legacy)
    (progn
      (princ
        (strcat
          "\n  Overlay min delta   = ("
          (rtos (- (car (car overlayBBox)) (car (car legacy))) 2 6)
          ","
          (rtos (- (cadr (car overlayBBox)) (cadr (car legacy))) 2 6)
          ")"))
      (princ
        (strcat
          "\n  Overlay max delta   = ("
          (rtos (- (car (cadr overlayBBox)) (car (cadr legacy))) 2 6)
          ","
          (rtos (- (cadr (cadr overlayBBox)) (cadr (cadr legacy))) 2 6)
          ")")))))

(defun AS128:InsertPreview
  (doc layout / existing tempPath block inserted insertedName bbox handle)

  (setq existing (AS128:ExistingEmbeddedRefs layout))

  (cond
    ((> (length existing) 0)
     (princ
       (strcat
         "\nABORT: This layout already contains "
         (itoa (length existing))
         " embedded/new titlebox reference(s)."))
     nil)

    (T
     (AS128:EnsurePreviewLayer doc)
     (setq tempPath
       (strcat
         (getvar "TEMPPREFIX")
         "SA3_AFRICA_TITLEBOX_EMBEDDED_PREVIEW.dwg"))

     (if (not (SA3:WriteEmbeddedTitleBox tempPath))
       (progn
         (princ "\nABORT: Failed to extract embedded titlebox DWG.")
         nil)
       (progn
         (setq block (vla-get-Block layout)
               inserted
                 (vl-catch-all-apply
                   'vla-InsertBlock
                   (list
                     block
                     (vlax-3d-point '(0.0 0.0 0.0))
                     tempPath
                     0.0005 0.0005 0.0005 0.0)))

         (if (vl-catch-all-error-p inserted)
           (progn
             (princ
               (strcat
                 "\nABORT: Insert preview failed: "
                 (vl-catch-all-error-message inserted)))
             (if (findfile tempPath) (vl-file-delete tempPath))
             nil)
           (progn
             (vl-catch-all-apply
               'vla-put-Layer
               (list inserted *AS128:PreviewLayer*))
             (vl-catch-all-apply 'vla-put-Color (list inserted 256))

             (setq insertedName (AS12:BlockNameSafe inserted)
                   bbox (AS12:GetBBoxSafe inserted)
                   handle (AS12:SafeGet inserted 'Handle))

             (if (= (type handle) 'STR)
               (setq *AS128:OverlayHandles*
                 (cons handle *AS128:OverlayHandles*)))

             (vla-Regen doc acAllViewports)

             (princ "\n================================================")
             (princ "\nAUTOSHEET TITLEBOX OVERLAY PREVIEW")
             (princ (strcat "\nLayout      : " (vla-get-Name layout)))
             (princ (strcat "\nInserted ref: " insertedName))
             (princ (strcat "\nHandle      : " (AS12:ValueString handle)))
             (princ (strcat "\nLayer       : " *AS128:PreviewLayer*))
             (princ "\nExisting ABD Zoo frame/strip was NOT deleted.")
             (AS128:PrintBBoxCompare bbox)
             (princ "\n================================================")
             (princ "\nInspect visually. Run AUTOSHEETOVERLAYCLEAN afterward.")
             (if (findfile tempPath) (vl-file-delete tempPath))
             inserted)))))))

(defun c:AUTOSHEETTITLEBOXOVERLAY (/ acad doc layout refs)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad)
        layout (AS128:CurrentPaperLayout doc))

  (cond
    ((null layout)
     (princ "\nSwitch to a Paper Space layout first."))

    (T
     (setq refs (AS123:RecognizedRefs layout))
     (cond
       ((/= (length refs) 1)
        (princ
          (strcat
            "\nABORT: expected exactly one recognized ABD Zoo frame, found "
            (itoa (length refs))
            ".")))
       ((not (AS123:ABDZooTitleBoxP (car refs)))
        (princ "\nABORT: current layout is not the ABD Zoo full-sheet profile."))
       (T
        (AS128:InsertPreview doc layout)))))

  (princ))

(defun AS128:DeleteHandle (doc h / en obj r)
  (setq en (handent h))
  (if en
    (progn
      (setq obj (vlax-ename->vla-object en)
            r (vl-catch-all-apply 'vla-Delete (list obj)))
      (not (vl-catch-all-error-p r)))
    nil))

(defun c:AUTOSHEETOVERLAYCLEAN (/ acad doc deleted failed h)
  (vl-load-com)
  (setq acad (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acad)
        deleted 0
        failed 0)

  (foreach h *AS128:OverlayHandles*
    (if (AS128:DeleteHandle doc h)
      (setq deleted (1+ deleted))
      (setq failed (1+ failed))))

  (setq *AS128:OverlayHandles* nil)
  (vla-Regen doc acAllViewports)

  (princ
    (strcat
      "\nPreview overlays deleted: " (itoa deleted)
      ", failed/not found: " (itoa failed)))
  (princ))

(princ "\nAUTOSHEET V12.8 titlebox overlay preview loaded.")
(princ "\nUse on ONE Paper Space layout: AUTOSHEETTITLEBOXOVERLAY")
(princ "\nAfter inspection: AUTOSHEETOVERLAYCLEAN")
(princ "\nDo NOT run destructive strip replacement yet.")
(princ)
