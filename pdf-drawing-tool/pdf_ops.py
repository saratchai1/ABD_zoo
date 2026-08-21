from pathlib import Path
import fitz

MM_PER_PT = 25.4 / 72.0


def page_count(path: str) -> int:
    with fitz.open(path) as doc:
        return doc.page_count


def detect_sheet_number_box(path: str, max_pages: int = 8):
    """
    Auto-detect the ACTUAL title-block cell containing "แผ่นที่ :".

    V2.1 used the SHX label itself and guessed a rectangle around it.
    That could extend upward into the drawing-number row.

    V2.2 does this instead:
      1) Find the AutoCAD SHX annotation whose content contains "แผ่นที่".
      2) Render a small grayscale area around that label.
      3) Detect the real horizontal and vertical table-border lines.
      4) Return the exact title-block cell bounded by those lines.

    This is designed for engineering drawing PDFs where title-block borders
    are printed as straight vector/rasterized black lines.

    Returns:
        {
            "box_norm": [x1, y1, x2, y2],
            "page_index": int,
            "label_rect": [x0, y0, x1, y1],
            "label": str,
            "method": "titleblock_borders",
        }
        or None.
    """

    def longest_true_run(values):
        best = 0
        current = 0
        for value in values:
            if value:
                current += 1
                if current > best:
                    best = current
            else:
                current = 0
        return best

    def dedupe_sorted(values, tolerance=1.0):
        result = []
        for value in sorted(values):
            if not result or abs(value - result[-1]) > tolerance:
                result.append(value)
        return result

    with fitz.open(path) as doc:
        limit = min(doc.page_count, max(1, int(max_pages)))

        for page_index in range(limit):
            page = doc[page_index]

            for annot in list(page.annots() or []):
                info = annot.info or {}
                content = str(info.get("content", ""))

                normalized = (
                    content.replace(" ", "")
                    .replace(".", "")
                    .replace(":", "")
                    .replace("：", "")
                )

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

                width = pix.width
                height = pix.height
                stride = pix.stride
                samples = pix.samples

                dark = []
                threshold = 200
                for row in range(height):
                    base = row * stride
                    dark.append([
                        samples[base + col] < threshold
                        for col in range(width)
                    ])

                row_runs = [
                    longest_true_run(dark[row])
                    for row in range(height)
                ]

                horizontal = []
                min_horizontal_run = max(20, int(width * 0.35))

                for row_index, run in enumerate(row_runs):
                    if run >= min_horizontal_run:
                        y = clip.y0 + row_index / scale
                        horizontal.append(y)

                horizontal = dedupe_sorted(horizontal, tolerance=1.0)

                if len(horizontal) < 2:
                    continue

                top_candidates = [
                    y for y in horizontal
                    if label_rect.y0 - 8.0 <= y <= label_rect.y0 + 8.0
                ]

                if not top_candidates:
                    continue

                top = min(top_candidates, key=lambda y: abs(y - label_rect.y0))

                bottom_candidates = [
                    y for y in horizontal
                    if y > label_rect.y1 + 2.0
                ]

                if not bottom_candidates:
                    continue

                bottom = min(bottom_candidates)

                if bottom - top < 8.0:
                    continue

                row0 = max(0, int((top - clip.y0) * scale))
                row1 = min(height, int((bottom - clip.y0) * scale) + 1)

                if row1 <= row0:
                    continue

                vertical_candidates = []

                for col in range(width):
                    column_values = [dark[row][col] for row in range(row0, row1)]
                    dark_fraction = (
                        sum(1 for value in column_values if value)
                        / max(1, len(column_values))
                    )

                    if dark_fraction >= 0.65:
                        x = clip.x0 + col / scale
                        vertical_candidates.append(x)

                vertical_candidates = dedupe_sorted(
                    vertical_candidates,
                    tolerance=1.0,
                )

                if len(vertical_candidates) < 2:
                    continue

                left_candidates = [
                    x for x in vertical_candidates
                    if x <= label_rect.x0 + 2.0
                ]
                right_candidates = [
                    x for x in vertical_candidates
                    if x >= label_rect.x1 + 5.0
                ]

                if not left_candidates or not right_candidates:
                    continue

                left = max(left_candidates)
                right = min(right_candidates)

                if right - left < 15.0:
                    continue

                return {
                    "box_norm": [
                        left / page.rect.width,
                        top / page.rect.height,
                        right / page.rect.width,
                        bottom / page.rect.height,
                    ],
                    "page_index": page_index,
                    "label_rect": [
                        label_rect.x0,
                        label_rect.y0,
                        label_rect.x1,
                        label_rect.y1,
                    ],
                    "label": content,
                    "method": "titleblock_borders",
                }

    return None


def delete_annotations(page, mode: str) -> int:
    """
    keep      : preserve annotations
    shx       : remove AutoCAD SHX annotations regardless of subtype
    all_text  : remove SHX + ordinary Text sticky notes
    """
    if mode == "keep":
        return 0

    removed = 0
    for annot in list(page.annots() or []):
        try:
            type_name = str(annot.type[1]).lower()
        except Exception:
            type_name = ""

        info = annot.info or {}
        title = str(info.get("title", ""))
        subject = str(info.get("subject", ""))
        content = str(info.get("content", ""))
        metadata = f"{title} {subject} {content}".lower()

        is_text = type_name == "text"
        is_shx = (
            "autocad shx" in metadata
            or "shx text" in metadata
            or title.strip().lower() == "autocad shx text"
        )

        should_delete = (
            (mode == "shx" and is_shx)
            or (mode == "all_text" and (is_shx or is_text))
        )

        if should_delete:
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
        a = int(scope.get("start", 1))
        b = int(scope.get("end", a))
        if a > b:
            a, b = b, a
        return a <= page_no <= b
    return True


def apply_editor_element(page, element, global_page_index):
    if not _scope_applies(element.get("scope", {"mode": "all"}), global_page_index):
        return

    kind = element.get("type")
    pr = page.rect

    if kind == "text":
        x = float(element["x"]) * pr.width
        y = float(element["y"]) * pr.height
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
        x1, y1, x2, y2 = element["box"]
        box = fitz.Rect(
            x1 * pr.width,
            y1 * pr.height,
            x2 * pr.width,
            y2 * pr.height,
        )
        number = int(element.get("start_number", 1)) + global_page_index
        text = str(number)

        size = float(element.get("font_size", 12))
        alias, pdf_font = _load_font(page, element.get("font_path"), "sheet_number_font")

        text_width = pdf_font.text_length(text, fontsize=size)
        x = box.x0 + (box.width - text_width) / 2.0
        asc = pdf_font.ascender * size
        desc = pdf_font.descender * size
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
        x1, y1, x2, y2 = element["rect"]
        rect = fitz.Rect(
            x1 * pr.width,
            y1 * pr.height,
            x2 * pr.width,
            y2 * pr.height,
        )
        image_path = element.get("image_path")
        if image_path and Path(image_path).exists():
            page.insert_image(rect, filename=str(image_path), keep_proportion=True, overlay=True)

    elif kind == "rectangle":
        x1, y1, x2, y2 = element["rect"]
        rect = fitz.Rect(
            x1 * pr.width,
            y1 * pr.height,
            x2 * pr.width,
            y2 * pr.height,
        )
        width = float(element.get("line_width", 1))
        page.draw_rect(
            rect,
            color=tuple(element.get("color", [1, 0, 0])),
            width=width,
            overlay=True,
        )


def export_editor(files, output, elements, cleanup_mode="shx", merge=True,
                  progress_cb=None, log_cb=None):
    total_pages = sum(page_count(p) for p in files)
    global_index = 0
    removed_total = 0
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

                removed_total += delete_annotations(page, cleanup_mode)

                for element in elements:
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

            if sequence_names:
                name = f"{prefix}{start + i}.pdf"
            else:
                name = f"{prefix}{Path(path).stem}_page_{i + 1:03d}.pdf"

            target = Path(output_dir) / name
            single.save(str(target), garbage=4, deflate=True)
            single.close()
            outputs.append(str(target))

            if progress_cb:
                progress_cb(i + 1, total)

        return outputs
    finally:
        doc.close()
