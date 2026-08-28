from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: ไม่พบ PyMuPDF")
    print("ติดตั้งด้วยคำสั่ง: python -m pip install PyMuPDF")
    raise SystemExit(2)

DEFAULT_OUTPUT = "รวมแผ่น.pdf"


def natural_key(path: Path):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def last_number(path: Path) -> int | None:
    numbers = re.findall(r"\d+", path.stem)
    return int(numbers[-1]) if numbers else None


def sequence_check(files: list[Path]) -> tuple[bool, str]:
    nums = [last_number(p) for p in files]
    if not files or any(n is None for n in nums):
        return True, "ไม่ตรวจลำดับเลข: มีบางไฟล์ที่ไม่มีเลขท้ายชื่อ"

    values = [int(n) for n in nums if n is not None]
    seen = set()
    duplicates = set()
    for n in values:
        if n in seen:
            duplicates.add(n)
        seen.add(n)
    if duplicates:
        return False, f"พบเลขซ้ำ: {', '.join(map(str, sorted(duplicates)[:20]))}"

    lo, hi = min(values), max(values)
    missing = sorted(set(range(lo, hi + 1)) - set(values))
    if missing:
        preview = ", ".join(map(str, missing[:20]))
        if len(missing) > 20:
            preview += ", ..."
        return False, f"ลำดับไม่ต่อเนื่อง {lo}-{hi}; เลขที่หาย: {preview}"

    return True, f"ลำดับเลขต่อเนื่องครบ {lo}-{hi}"


def collect_pdfs(folder: Path, output: Path) -> list[Path]:
    files = [
        p for p in folder.glob("*.pdf")
        if p.is_file() and p.resolve() != output.resolve()
    ]
    return sorted(files, key=natural_key)


def merge(folder: Path, output_name: str, expected: int | None, strict: bool, check_sequence: bool) -> int:
    folder = folder.expanduser().resolve()
    if not folder.exists():
        print(f"ERROR: ไม่พบโฟลเดอร์\n{folder}")
        return 1
    if not folder.is_dir():
        print(f"ERROR: path นี้ไม่ใช่โฟลเดอร์\n{folder}")
        return 1

    output = folder / output_name
    if output.suffix.lower() != ".pdf":
        output = output.with_suffix(".pdf")

    files = collect_pdfs(folder, output)
    print("=" * 72)
    print("PDF MERGE")
    print(f"Folder : {folder}")
    print(f"Files  : {len(files)}")
    print(f"Output : {output.name}")
    print("=" * 72)

    if not files:
        print("ERROR: ไม่พบ PDF ในโฟลเดอร์")
        return 1

    if expected is not None and len(files) != expected:
        message = f"จำนวนไฟล์ไม่ตรง: ต้องการ {expected} แต่พบ {len(files)}"
        if strict:
            print(f"ERROR: {message}")
            return 1
        print(f"WARNING: {message}")

    if check_sequence:
        ok, message = sequence_check(files)
        print(f"Sequence: {message}")
        if strict and not ok:
            print("ERROR: ยกเลิกเพื่อป้องกันการรวมไฟล์ผิดลำดับ")
            return 1

    print("\nลำดับที่จะรวม:")
    for i, path in enumerate(files, 1):
        print(f"  {i:03d}. {path.name}")

    print("\nกำลังรวม...")
    result = fitz.open()
    total_pages = 0
    temp_output = output.with_name(output.stem + ".__merging__.pdf")

    try:
        for i, path in enumerate(files, 1):
            try:
                with fitz.open(path) as src:
                    pages = src.page_count
                    result.insert_pdf(src)
                    total_pages += pages
                print(f"[{i:03d}/{len(files):03d}] {path.name} ({pages} หน้า)")
            except Exception as exc:
                print(f"ERROR: อ่าน PDF ไม่ได้: {path.name}")
                print(exc)
                return 1

        if temp_output.exists():
            temp_output.unlink()
        result.save(temp_output, garbage=3, deflate=True)
        result.close()
        if output.exists():
            output.unlink()
        temp_output.replace(output)
    finally:
        if not result.is_closed:
            result.close()
        if temp_output.exists() and not output.exists():
            try:
                temp_output.unlink()
            except OSError:
                pass

    print("\n" + "=" * 72)
    print("เสร็จเรียบร้อย")
    print(f"รวมไฟล์ : {len(files)} ไฟล์")
    print(f"รวมหน้า  : {total_pages} หน้า")
    print(f"ได้ไฟล์  : {output}")
    print("=" * 72)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="รวม PDF ในโฟลเดอร์ โดยเรียงชื่อแบบ natural sort")
    parser.add_argument("folder", nargs="?", default=".", help="โฟลเดอร์ที่มี PDF")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"ชื่อไฟล์ผลลัพธ์ (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--expected", type=int, default=None, help="จำนวนไฟล์ที่คาดไว้ เช่น 176")
    parser.add_argument("--strict", action="store_true", help="หยุดทันทีถ้าจำนวนไฟล์หรือลำดับเลขไม่ถูกต้อง")
    parser.add_argument("--no-sequence-check", action="store_true", help="ไม่ตรวจเลขท้ายชื่อไฟล์")
    args = parser.parse_args()
    return merge(Path(args.folder), args.output, args.expected, args.strict, not args.no_sequence_check)


if __name__ == "__main__":
    raise SystemExit(main())
