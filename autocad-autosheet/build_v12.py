from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

EXPECTED_V11_SHA256 = "e79ec6cef78f471fe74b53772a18439809e8a04fb856a43d851773e325a376bf"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the standalone AUTOSHEET V12.1 LSP by appending the V12 scan shell "
            "and the live-scan robustness fix to the frozen validated V11 engine."
        )
    )
    parser.add_argument(
        "v11",
        type=Path,
        help="Path to AUTOSHEET_STANDARDIZATION_V11_CTB_FORCE.lsp",
    )
    parser.add_argument(
        "--patch",
        type=Path,
        default=Path(__file__).with_name("AUTOSHEET_V12_SCAN_PATCH.lsp"),
        help="V12 scan/validation shell",
    )
    parser.add_argument(
        "--scan-fix",
        type=Path,
        default=Path(__file__).with_name("AUTOSHEET_V12_1_SCAN_FIX.lsp"),
        help="V12.1 live-scan robustness fix",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("AUTOSHEET_V12_1_SCAN_FIX.lsp"),
        help="Output standalone LSP",
    )
    args = parser.parse_args()

    actual = sha256(args.v11)
    if actual != EXPECTED_V11_SHA256:
        raise SystemExit(
            "V11 SHA-256 mismatch.\n"
            f"Expected: {EXPECTED_V11_SHA256}\n"
            f"Actual:   {actual}\n"
            "Use the validated V11 baseline or update the build intentionally."
        )

    base = args.v11.read_text(encoding="utf-8").rstrip()
    patch = args.patch.read_text(encoding="utf-8").strip()
    scan_fix = args.scan_fix.read_text(encoding="utf-8").strip()

    output = base + "\n\n" + patch + "\n\n" + scan_fix + "\n"
    args.out.write_text(output, encoding="utf-8")

    print(f"Built: {args.out}")
    print(f"SHA-256: {sha256(args.out)}")


if __name__ == "__main__":
    main()
