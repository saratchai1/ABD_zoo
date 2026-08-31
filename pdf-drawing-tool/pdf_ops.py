from pathlib import Path
import fitz

THAI_SEQUENCE = list("กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
LOWER_SEQUENCE = list("abcdefghijklmnopqrstuvwxyz")
UPPER_SEQUENCE = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def page_count(path: str) -> int:
    with fitz.open(path) as doc:
        return doc.page_count


def _sequence_value(kind: str, start, offset: int) -> str:
    kind = (kind or "number").lower()
    if kind == "number":
        try:
            base = int(str(start).strip())
        except Exception:
            base = 1
        return str(base + offset)

    chars = LOWER_SEQUENCE if kind == "lower" else UPPER_SEQUENCE if kind == "upper" else THAI_SEQUENCE
    raw = str(start or "").strip()
    if raw in chars:
        base = chars.index(raw)
    else:
        base = 0
    idx = base + offset
    # Continue naturally past Z / ฮ by using spreadsheet-like groups: z -> aa, ฮ -> กก.
    if kind in ("lower", "upper"):
        out = ""
        n = idx
        while True:
            out = chars[n % len(chars)] + out
            n = n // len(chars) - 1
            if n < 0:
                break
        return out
    # Thai drawings normally use one-letter series. If pages exceed the alphabet,
    # continue as กก, กข, ... rather than wrapping silently.
    out = ""
    n = idx
    while True:
        out = chars[n % len(chars)] + out
        n = n // len(chars) - 1
        if n < 0:
            break
    return out


def _longest_true_run(values):
    best = current = 0
    for value in values:
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _dedupe_sorted(values, tolerance=1.0):
    result = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result


def detect_sheet_number_box_on_page(page):
    """Detect the แผ่นที่ title-block cell on one specific page.

    This is intentionally page-local. Engineering drawing PDFs sometimes use
    slightly shifted title blocks from page to page, so one normalized box must
    not be reused blindly for the whole document.
    """
    for annot in list(page.annots() or []):
        info = annot.info or {}
        content = str(info.get("content", ""))
        normalized = content.replace(" ", "").replace(".", "").replace(":", "").replace("：", "")
        if "แผ่นที่" not in normalized:
            continue

        label_rect = annot.rect * page.rotation_matrix
        clip = fitz.Rect(
            max(0.0, label_rect.x0 - 30.0),
            max(0.0, label_rect.y0 - 50.0),
            min(page.rect.width, label_rect.x1 + 100.0),
            min(page.rect.height, label_rect.y1 + 40.0),
        )
        scale = 3.0
        pix = page.get_pixmap(
            matrix=fitz.Matrix(scale, scale),
            clip=clip,
            colorspace=fitz.csGRAY,
            alpha=False,
        )
        width, height, stride, samples = pix.width, pix.height, pix.stride, pix.samples
        threshold = 200
        dark = []
        for row in range(height):
            base = row * stride
            dark.append([samples[base + col] < threshold for col in range(width)])

        horizontal = []
        min_run = max(20, int(width * 0.35))
        for row_index in range(height):
            if _longest_true_run(dark[row_index]) >= min_run:
                horizontal.append(clip.y0 + row_index / scale)
        horizontal = _dedupe_sorted(horizontal, 1.0)
        if len(horizontal) < 2:
            continue

        tops = [y for y in horizontal if label_rect.y0 - 8 <= y <= label_rect.y0 + 8]
        if not tops:
            continue
        top = min(tops, key=lambda y: abs(y - label_rect.y0))

        bottoms = [y for y in horizontal if y > label_rect.y1 + 2]
        if not bottoms:
            continue
        bottom = min(bottoms)
        if bottom - top < 8:
            continue

        row0 = max(0, int((top - clip.y0) * scale))
        row1 = min(height, int((bottom - clip.y0) * scale) + 1)
        vertical = []
        for col in range(width):
            vals = [dark[row][col] for row in range(row0, row1)]
            if sum(vals) / max(1, len(vals)) >= 0.65:
                vertical.append(clip.x0 + col / scale)
        vertical = _dedupe_sorted(vertical, 1.0)

        lefts = [x for x in vertical if x <= label_rect.x0 + 2]
        rights = [x for x in vertical if x >= label_rect.x1 + 5]
        if not lefts or not rights:
            continue
        left, right = max(lefts), min(rights)
        if right - left < 15:
            continue

        # Preserve the printed label "แผ่นที่ :". Only erase in the area to its
        # right. Writing uses a separate box centered on the whole detected cell.
        margin_x = min(2.0, (right - left) * 0.03)
        margin_y = min(1.5, (bottom - top) * 0.12)
        number_left = max(label_rect.x1 + 1.5, left + (right - left) * 0.42)
        number_left = min(number_left, right - 6.0)
        number_box = [
            (number_left + margin_x) / page.rect.width,
            (top + margin_y) / page.rect.height,
            (right - margin_x) / page.rect.width,
            (bottom - margin_y) / page.rect.height,
        ]
        return {
            "box_norm": [
                left / page.rect.width,
                top / page.rect.height,
                right / page.rect.width,
                bottom / page.rect.height,
            ],
            "number_box_norm": number_box,
            "label_rect": [label_rect.x0, label_rect.y0, label_rect.x1, label_rect.y1],
            "label": content,
            "method": "titleblock_borders_number_area_page_local",
        }
    return None


def detect_sheet_number_box(path: str, max_pages: int = 8):
    """Detect the first usable แผ่นที่ title-block cell in a PDF.

    This remains the UI's initial detection entry point. Export uses
    detect_sheet_number_box_on_page() again for every page when the element was
    auto-detected, so shifted title blocks are followed page by page.
    """
    with fitz.open(path) as doc:
        limit = min(doc.page_count, max(1, int(max_pages)))
        for page_index in range(limit):
            detected = detect_sheet_number_box_on_page(doc[page_index])
            if detected:
                detected["page_index"] = page_index
                return detected
    return None


def _centered_write_box(detected):
    """Return a write box centered on the full detected sheet-number cell."""
    full = list(detected["box_norm"])
    erase = list(detected.get("number_box_norm") or full)

    fx1, _, fx2, _ = full
    _, ey1, _, ey2 = erase
    center_x = (fx1 + fx2) / 2.0

    full_width = max(0.0, fx2 - fx1)
    erase_width = max(0.0, erase[2] - erase[0])

    write_width = min(erase_width * 0.68, full_width * 0.38)
    if write_width <= 0:
        write_width = full_width * 0.36

    half = write_width / 2.0
    x1 = max(fx1 + full_width * 0.03, center_x - half)
    x2 = min(fx2 - full_width * 0.03, center_x + half)

    clipped_width = max(0.0, x2 - x1)
    x1 = center_x - clipped_width / 2.0
    x2 = center_x + clipped_width / 2.0

    return [x1, ey1, x2, ey2]


def _page_local_elements(page, elements, global_page_index, log_cb=None):
    """Resolve auto-detected sheet-number elements against the current page.

    Manual sheet-number rectangles are left untouched. Auto-detected elements
    carry follow_detected_cell=True and get fresh erase/write boxes on each
    page. If a page cannot be detected, the stored box is used as a fallback.
    """
    followers = [
        e for e in elements
        if e.get("type") == "sheet_number" and e.get("follow_detected_cell", False)
    ]
    if not followers:
        return elements, False, False

    detected = detect_sheet_number_box_on_page(page)
    if not detected:
        if log_cb:
            log_cb(
                f"  Page {global_page_index + 1}: แผ่นที่ cell not detected; "
                "using stored fallback position."
            )
        return elements, False, True

    write_box = _centered_write_box(detected)
    erase_box = list(detected.get("number_box_norm") or detected["box_norm"])
    effective = []
    for element in elements:
        if element.get("type") == "sheet_number" and element.get("follow_detected_cell", False):
            local = dict(element)
            local["box"] = list(write_box)
            local["erase_box"] = list(erase_box)
            effective.append(local)
        else:
            effective.append(element)
    return effective, True, False


def delete_annotations(page, mode: str) -> int:
    if mode == "keep":
        return 0
    removed = 0
    for annot in list(page.annots() or []):
        try:
            type_name = str(annot.type[1]).lower()
        except Exception:
            type_name = ""
        info = annot.info or {}
        metadata = f"{info.get('title','')} {info.get('subject','')} {info.get('content','')}".lower()
        is_text = type_name == "text"
        is_shx = (
            "autocad shx" in metadata
            or "shx text" in metadata
            or str(info.get("title", "")).strip().lower() == "autocad shx text"
        )
        should = (mode == "shx" and is_shx) or (mode == "all_text" and (is_shx or is_text))
        if should:
            try:
                page.delete_annot(annot)
                removed += 1
            except Exception:
                pass
    return removed


def _load_font(page, font_path, alias="editor_font"):
    if font_path and Path(font_path).exists():
        pdf_font = fitz.Font(fontfile=str(font_path))
        page.insert_font(fontname=alias, fontfile=str(font_path))
        return alias, pdf_font
    return "helv", fitz.Font("helv")


def _scope_applies(scope, global_page_index):
    mode = scope.get("mode", "all")
    page_no = global_page_index + 1
    if mode == "all":
        return True
    if mode == "current":
        return page_no == int(scope.get("page", page_no))
    if mode == "range":
        a, b = int(scope.get("start", 1)), int(scope.get("end", 1))
        if a > b:
            a, b = b, a
        return a <= page_no <= b
    return True


def _norm_to_rect(page, values):
    x1, y1, x2, y2 = values
    pr = page.rect
    return fitz.Rect(x1 * pr.width, y1 * pr.height, x2 * pr.width, y2 * pr.height)


def _delete_text_annotations_in_rect(page, rect) -> int:
    removed = 0
    for annot in list(page.annots() or []):
        try:
            if not (annot.rect & rect).is_empty:
                info = annot.info or {}
                metadata = f"{info.get('title','')} {info.get('subject','')} {info.get('content','')}".lower()
                type_name = str(annot.type[1]).lower()
                if type_name == "text" or "shx" in metadata:
                    page.delete_annot(annot)
                    removed += 1
        except Exception:
            pass
    return removed


def prepare_erasure(page, element, global_page_index):
    """Create redactions before drawing new elements. Returns (did_redact, aggressive, annotations_removed)."""
    if not _scope_applies(element.get("scope", {"mode": "all"}), global_page_index):
        return False, False, 0
    kind = element.get("type")
    values = None
    if kind in ("erase_sheet", "erase_scale", "erase_area"):
        values = element.get("rect")
    elif kind == "sheet_number" and element.get("erase_existing", True):
        values = element.get("erase_box") or element.get("box")
    if not values:
        return False, False, 0

    rect = _norm_to_rect(page, values)
    removed = _delete_text_annotations_in_rect(page, rect)
    # fill=None avoids painting over title-block / scale border lines.
    page.add_redact_annot(rect, fill=None, cross_out=False)
    aggressive = str(element.get("erase_mode", "text")).lower() == "all"
    return True, aggressive, removed


def apply_editor_element(page, element, global_page_index):
    if not _scope_applies(element.get("scope", {"mode": "all"}), global_page_index):
        return
    kind = element.get("type")
    if kind in ("erase_sheet", "erase_scale", "erase_area"):
        return
    pr = page.rect

    if kind == "text":
        x, y = float(element["x"]) * pr.width, float(element["y"]) * pr.height
        text = str(element.get("text", ""))
        size = float(element.get("font_size", 12))
        alias, _ = _load_font(page, element.get("font_path"), "editor_text_font")
        page.insert_text(
            (x, y),
            text,
            fontsize=size,
            fontname=alias,
            color=tuple(element.get("color", [0, 0, 0])),
            overlay=True,
        )

    elif kind == "sheet_number":
        box = _norm_to_rect(page, element["box"])
        text = _sequence_value(
            element.get("sequence_type", "number"),
            element.get("sequence_start", element.get("start_number", 1)),
            global_page_index,
        )
        size = float(element.get("font_size", 12))
        alias, pdf_font = _load_font(page, element.get("font_path"), "sheet_number_font")
        text_width = pdf_font.text_length(text, fontsize=size)
        x = box.x0 + (box.width - text_width) / 2.0
        asc, desc = pdf_font.ascender * size, pdf_font.descender * size
        baseline_y = box.y0 + (box.height - (asc - desc)) / 2.0 + asc
        page.insert_text(
            (x, baseline_y),
            text,
            fontsize=size,
            fontname=alias,
            color=(0, 0, 0),
            overlay=True,
        )

    elif kind == "image":
        rect = _norm_to_rect(page, element["rect"])
        image_path = element.get("image_path")
        if image_path and Path(image_path).exists():
            page.insert_image(rect, filename=str(image_path), keep_proportion=True, overlay=True)

    elif kind == "rectangle":
        rect = _norm_to_rect(page, element["rect"])
        page.draw_rect(
            rect,
            color=tuple(element.get("color", [1, 0, 0])),
            width=float(element.get("line_width", 1)),
            overlay=True,
        )


def export_editor(
    files,
    output,
    elements,
    cleanup_mode="shx",
    merge=True,
    progress_cb=None,
    log_cb=None,
):
    total_pages = sum(page_count(p) for p in files)
    global_index = 0
    removed_total = 0
    erased_annotations = 0
    sheet_pages_redetected = 0
    sheet_pages_fallback = 0
    merged = fitz.open() if merge else None
    try:
        for file_idx, path in enumerate(files, start=1):
            if log_cb:
                log_cb(f"[{file_idx}/{len(files)}] {Path(path).name}")
            doc = fitz.open(path)
            for page in doc:
                try:
                    page.remove_rotation()
                except Exception:
                    pass

                # Detect before cleanup: the แผ่นที่ SHX annotation is one of the
                # strongest anchors and may be deleted by cleanup below.
                effective_elements, redetected, fallback = _page_local_elements(
                    page, elements, global_index, log_cb=log_cb
                )
                if redetected:
                    sheet_pages_redetected += 1
                if fallback:
                    sheet_pages_fallback += 1

                removed_total += delete_annotations(page, cleanup_mode)

                did_redact = False
                aggressive = False
                for element in effective_elements:
                    yes, hard, ann = prepare_erasure(page, element, global_index)
                    did_redact = did_redact or yes
                    aggressive = aggressive or hard
                    erased_annotations += ann
                if did_redact:
                    page.apply_redactions(
                        images=2 if aggressive else 0,
                        graphics=2 if aggressive else 0,
                        text=0,
                    )

                for element in effective_elements:
                    apply_editor_element(page, element, global_index)

                global_index += 1
                if progress_cb:
                    progress_cb(global_index, total_pages)

            if merge:
                merged.insert_pdf(doc)
            else:
                target = Path(output) / f"{Path(path).stem}_edited.pdf"
                doc.save(str(target), garbage=4, deflate=True)
                if log_cb:
                    log_cb(f"  -> {target}")
            doc.close()

        if merge:
            merged.save(str(output), garbage=4, deflate=True)
            merged.close()
        return {
            "pages": global_index,
            "removed_annotations": removed_total,
            "erased_annotations": erased_annotations,
            "sheet_pages_redetected": sheet_pages_redetected,
            "sheet_pages_fallback": sheet_pages_fallback,
            "output": str(output),
        }
    except Exception:
        if merged is not None:
            try:
                merged.close()
            except Exception:
                pass
        raise


def merge_pdfs(files, target):
    out = fitz.open()
    total = 0
    try:
        for path in files:
            src = fitz.open(path)
            total += src.page_count
            out.insert_pdf(src)
            src.close()
        out.save(str(target), garbage=4, deflate=True)
    finally:
        out.close()
    return total


def split_pdf(path, output_dir, sequence_names=False, start=1, prefix="", progress_cb=None):
    doc = fitz.open(path)
    outputs = []
    try:
        total = doc.page_count
        for i in range(total):
            single = fitz.open()
            single.insert_pdf(doc, from_page=i, to_page=i)
            name = (
                f"{prefix}{start+i}.pdf"
                if sequence_names
                else f"{prefix}{Path(path).stem}_page_{i+1:03d}.pdf"
            )
            target = Path(output_dir) / name
            single.save(str(target), garbage=4, deflate=True)
            single.close()
            outputs.append(str(target))
            if progress_cb:
                progress_cb(i + 1, total)
        return outputs
    finally:
        doc.close()
