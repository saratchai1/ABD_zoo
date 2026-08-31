import re

import fitz


def _norm_text(value) -> str:
    text = str(value or "")
    text = text.replace("：", ":")
    text = re.sub(r"[\s\.:_\-]+", "", text)
    return text.lower()


def _to_visual_rect(page, rect) -> fitz.Rect:
    r = fitz.Rect(rect)
    try:
        if int(page.rotation or 0) % 360:
            return r * page.rotation_matrix
    except Exception:
        pass
    return r


def _anchor_rects(page):
    """Candidate visual-coordinate rectangles for the printed 'แผ่นที่' label."""
    anchors = []
    for needle in ("แผ่นที่", "แผ่นที่ :", "แผ่นที่:"):
        try:
            for rect in page.search_for(needle):
                anchors.append((0, _to_visual_rect(page, rect), f"search:{needle}"))
        except Exception:
            pass
    for annot in list(page.annots() or []):
        try:
            info = annot.info or {}
            metadata = " ".join(str(info.get(k, "")) for k in ("content", "subject", "title", "name"))
            if "แผ่นที่" not in _norm_text(metadata):
                continue
            anchors.append((1, _to_visual_rect(page, annot.rect), "annotation"))
        except Exception:
            pass
    result = []
    for _priority, rect, source in sorted(anchors, key=lambda item: item[0]):
        if rect.is_empty or rect.width <= 0 or rect.height <= 0:
            continue
        if any(abs(rect.x0 - old[0].x0) < 2 and abs(rect.y0 - old[0].y0) < 2 for old in result):
            continue
        result.append((rect, source))
    return result


def _expand_rect(rect, dx, dy, bounds):
    return fitz.Rect(
        max(bounds.x0, rect.x0 - dx), max(bounds.y0, rect.y0 - dy),
        min(bounds.x1, rect.x1 + dx), min(bounds.y1, rect.y1 + dy),
    )


def _ref_rect(page, reference_box):
    if not reference_box or len(reference_box) != 4:
        return None
    pr = page.rect
    try:
        x1, y1, x2, y2 = [float(v) for v in reference_box]
    except Exception:
        return None
    rect = fitz.Rect(x1 * pr.width, y1 * pr.height, x2 * pr.width, y2 * pr.height)
    if rect.is_empty or rect.width <= 5 or rect.height <= 5:
        return None
    return rect


def _longest_run(values):
    best_len = best_start = cur_start = cur_len = 0
    for i, value in enumerate(values):
        if value:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
        else:
            cur_len = 0
    return best_len, best_start, best_start + best_len


def _collapse_axis(candidates, tolerance_px=3):
    if not candidates:
        return []
    candidates = sorted(candidates, key=lambda item: item[0])
    groups = [[candidates[0]]]
    for item in candidates[1:]:
        if item[0] - groups[-1][-1][0] <= tolerance_px:
            groups[-1].append(item)
        else:
            groups.append([item])
    result = []
    for group in groups:
        strongest = max(group, key=lambda x: x[1])
        mean_pos = sum(x[0] for x in group) / len(group)
        result.append((mean_pos, strongest[1], strongest[2], strongest[3]))
    return result


def _raster_lines(page, clip, scale, expected_w=None, expected_h=None, anchor=None):
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, colorspace=fitz.csGRAY, alpha=False, annots=False)
    width, height, stride, samples = pix.width, pix.height, pix.stride, pix.samples
    if width < 10 or height < 10:
        return [], []
    threshold = 205
    dark = [bytearray(width) for _ in range(height)]
    for y in range(height):
        base = y * stride
        row = dark[y]
        for x in range(width):
            row[x] = 1 if samples[base + x] < threshold else 0
    anchor_w = anchor.width if anchor is not None else 0
    anchor_h = anchor.height if anchor is not None else 0
    min_h_run = max(int(24 * scale), int((expected_w or 0) * scale * 0.45), int(anchor_w * scale * 1.4))
    min_v_run = max(int(14 * scale), int((expected_h or 0) * scale * 0.55), int(anchor_h * scale * 1.4))
    h_candidates = []
    for y in range(height):
        run_len, start, end = _longest_run(dark[y])
        if run_len >= min_h_run:
            h_candidates.append((y, run_len, start, end))
    v_candidates = []
    for x in range(width):
        col = [dark[y][x] for y in range(height)]
        run_len, start, end = _longest_run(col)
        if run_len >= min_v_run:
            v_candidates.append((x, run_len, start, end))
    return _collapse_axis(h_candidates), _collapse_axis(v_candidates)


def _candidate_from_local_lines(page, clip, scale, h_lines, v_lines, anchor=None, reference_rect=None):
    if len(h_lines) < 2 or len(v_lines) < 2:
        return None
    hs = [{"y": clip.y0 + ypx / scale, "x0": clip.x0 + sx / scale, "x1": clip.x0 + ex / scale, "run": run / scale} for ypx, run, sx, ex in h_lines]
    vs = [{"x": clip.x0 + xpx / scale, "y0": clip.y0 + sy / scale, "y1": clip.y0 + ey / scale, "run": run / scale} for xpx, run, sy, ey in v_lines]
    ref_w = reference_rect.width if reference_rect is not None else None
    ref_h = reference_rect.height if reference_rect is not None else None
    ref_cx = (reference_rect.x0 + reference_rect.x1) / 2 if reference_rect is not None else None
    ref_cy = (reference_rect.y0 + reference_rect.y1) / 2 if reference_rect is not None else None
    best, best_score = None, float("inf")
    for i, top in enumerate(hs[:-1]):
        for bottom in hs[i + 1:]:
            height = bottom["y"] - top["y"]
            if height < 10:
                continue
            if ref_h is not None and not (0.55 * ref_h <= height <= 1.65 * ref_h):
                continue
            if ref_h is None and anchor is not None and (height < max(12, anchor.height * 1.25) or height > max(180, anchor.height * 12)):
                continue
            for li, left in enumerate(vs[:-1]):
                for right in vs[li + 1:]:
                    width = right["x"] - left["x"]
                    if width < 18:
                        continue
                    if ref_w is not None and not (0.55 * ref_w <= width <= 1.65 * ref_w):
                        continue
                    if ref_w is None and anchor is not None and (width < max(25, anchor.width * 1.45) or width > max(380, anchor.width * 10)):
                        continue
                    tol = 3.0
                    if not (top["x0"] <= left["x"] + tol and top["x1"] >= right["x"] - tol):
                        continue
                    if not (bottom["x0"] <= left["x"] + tol and bottom["x1"] >= right["x"] - tol):
                        continue
                    if not (left["y0"] <= top["y"] + tol and left["y1"] >= bottom["y"] - tol):
                        continue
                    if not (right["y0"] <= top["y"] + tol and right["y1"] >= bottom["y"] - tol):
                        continue
                    rect = fitz.Rect(left["x"], top["y"], right["x"], bottom["y"])
                    if anchor is not None:
                        acx, acy = (anchor.x0 + anchor.x1) / 2, (anchor.y0 + anchor.y1) / 2
                        if not (rect.x0 - 3 <= acx <= rect.x1 + 3 and rect.y0 - 3 <= acy <= rect.y1 + 3):
                            continue
                        if rect.x1 < anchor.x1 + 4:
                            continue
                    score = 0.0
                    if reference_rect is not None:
                        cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
                        score += abs(width - ref_w) / max(ref_w, 1) * 70
                        score += abs(height - ref_h) / max(ref_h, 1) * 90
                        score += abs(cx - ref_cx) / max(ref_w, 1) * 7
                        score += abs(cy - ref_cy) / max(ref_h, 1) * 7
                    if anchor is not None:
                        score += abs(anchor.y0 - rect.y0) * 1.8 + abs(anchor.x0 - rect.x0) * 0.25
                        if (rect.y0 + rect.y1) / 2 <= anchor.y0:
                            score += 500
                    if reference_rect is None:
                        score += rect.get_area() / 2500.0
                    if score < best_score:
                        best_score, best = score, rect
    return best


def _build_detection(page, cell_rect, anchor=None, source="raster"):
    pr = page.rect
    if cell_rect is None or cell_rect.is_empty:
        return None
    left, top, right, bottom = cell_rect.x0, cell_rect.y0, cell_rect.x1, cell_rect.y1
    width, height = max(1.0, right - left), max(1.0, bottom - top)
    margin_x, margin_y = min(2.0, width * 0.025), min(1.5, height * 0.08)
    number_left = max(anchor.x1 + 1.5, left + width * 0.42) if anchor is not None else left + width * 0.42
    number_left = min(number_left, right - max(6.0, width * 0.08))
    return {
        "box_norm": [left / pr.width, top / pr.height, right / pr.width, bottom / pr.height],
        "number_box_norm": [(number_left + margin_x) / pr.width, (top + margin_y) / pr.height, (right - margin_x) / pr.width, (bottom - margin_y) / pr.height],
        "label_rect": [anchor.x0, anchor.y0, anchor.x1, anchor.y1] if anchor is not None else None,
        "label": "แผ่นที่",
        "method": source,
    }


def _raster_detect(page, anchor=None, reference_box=None):
    pr = page.rect
    ref = _ref_rect(page, reference_box)
    if anchor is not None:
        base = fitz.Rect(anchor)
        # SHX comment rectangles can be tiny or inconsistent. Do not let their size
        # determine the search window: an A1/A3 title-block cell is much wider.
        ref_w = ref.width if ref is not None else max(anchor.width * 3.5, 180)
        ref_h = ref.height if ref is not None else max(anchor.height * 4.0, 70)
        clip = fitz.Rect(
            base.x0 - max(30, ref_w * 0.45), base.y0 - max(25, ref_h * 0.65),
            base.x1 + max(80, ref_w * 1.15), base.y1 + max(80, ref_h * 1.25),
        )
        if ref is not None:
            clip |= _expand_rect(ref, max(35, ref.width * 0.7), max(35, ref.height * 0.8), pr)
    elif ref is not None:
        clip = _expand_rect(ref, max(45, ref.width * 0.9), max(45, ref.height * 1.2), pr)
    else:
        return None
    clip &= pr
    if clip.is_empty or clip.width < 20 or clip.height < 20:
        return None
    scale = 2.5
    try:
        h_lines, v_lines = _raster_lines(page, clip, scale, expected_w=(ref.width if ref is not None else None), expected_h=(ref.height if ref is not None else None), anchor=anchor)
    except Exception:
        return None
    cell = _candidate_from_local_lines(page, clip, scale, h_lines, v_lines, anchor=anchor, reference_rect=ref)
    return _build_detection(page, cell, anchor=anchor, source="raster_cell_v260") if cell is not None else None


def _candidate_is_sane(detected, reference_box=None):
    if not detected:
        return False
    try:
        x1, y1, x2, y2 = [float(v) for v in detected["box_norm"]]
    except Exception:
        return False
    if not (0 <= x1 < x2 <= 1.001 and 0 <= y1 < y2 <= 1.001):
        return False
    w, h = x2 - x1, y2 - y1
    if w < 0.01 or h < 0.005:
        return False
    if reference_box:
        try:
            rx1, ry1, rx2, ry2 = [float(v) for v in reference_box]
            rw, rh = rx2 - rx1, ry2 - ry1
            if rw > 0 and not (0.50 * rw <= w <= 1.70 * rw): return False
            if rh > 0 and not (0.50 * rh <= h <= 1.70 * rh): return False
        except Exception:
            pass
    return True


def robust_detect_sheet_number_box_on_page(page, reference_box=None, original_detector=None):
    for anchor, source in _anchor_rects(page):
        detected = _raster_detect(page, anchor=anchor, reference_box=reference_box)
        if detected:
            detected["anchor_source"] = source
            return detected
    if reference_box:
        detected = _raster_detect(page, anchor=None, reference_box=reference_box)
        if detected:
            detected["anchor_source"] = "reference_geometry"
            return detected
    if original_detector is not None:
        try:
            legacy = original_detector(page)
        except Exception:
            legacy = None
        if _candidate_is_sane(legacy, reference_box=reference_box):
            legacy = dict(legacy)
            legacy["method"] = f"legacy_validated_v260:{legacy.get('method', 'unknown')}"
            return legacy
    return None


def robust_detect_sheet_number_box(path: str, max_pages: int = 20, original_detector=None):
    with fitz.open(path) as doc:
        limit = min(doc.page_count, max(1, int(max_pages)))
        for page_index in range(limit):
            detected = robust_detect_sheet_number_box_on_page(doc[page_index], reference_box=None, original_detector=original_detector)
            if detected:
                detected["page_index"] = page_index
                return detected
    return None
