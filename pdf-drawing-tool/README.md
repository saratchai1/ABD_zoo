# PDF Drawing Tool

Windows desktop utility for post-processing engineering drawing PDFs after export from AutoCAD.

## Features

- Drag/drop one or many PDF files
- Preview pages with zoom and pan
- Auto-detect the actual `แผ่นที่` title-block cell from AutoCAD SHX metadata + border lines
- Sequential sheet numbering such as `4, 5, 6, ...`
- Detect installed Windows fonts, including Cordia New when installed
- Remove AutoCAD SHX PDF annotations (yellow comment markers)
- Add text directly in the PDF preview
- Add image/logo/stamp to selected pages
- Add rectangle markup
- Apply added objects to all pages, current page, or a page range
- Manual sheet-box fallback
- Merge many PDFs into one multipage PDF
- Split a multipage PDF into one-page PDFs
- Build as a normal Windows `.exe`
- Optional Setup installer with Desktop and Start Menu shortcuts

## Run from source

```bat
cd pdf-drawing-tool
run_dev.bat
```

## Build Windows application

```bat
build_app.bat
```

Output:

```text
dist\PDF Drawing Tool.exe
```

## Build normal Windows installer

Install Inno Setup 6, then run:

```bat
build_installer.bat
```

Output:

```text
installer_output\PDF_Drawing_Tool_Setup.exe
```

The installer creates a Desktop shortcut, Start Menu shortcut, installs to Program Files, and supports Windows uninstall.

## GitHub Actions

Open **Actions → Build PDF Drawing Tool → Run workflow**. The workflow builds both the portable EXE and Setup EXE on a Windows runner and uploads them as downloadable artifacts.

## Typical workflow

1. Add exported drawing PDF(s).
2. Confirm `Sheet No.: AUTO-DETECTED`.
3. Set start number, e.g. `4`.
4. Select Cordia New and font size.
5. Keep `Remove AutoCAD SHX annotations` selected.
6. Add any text/image/rectangle overlays if needed.
7. Export.

The original PDFs are not overwritten.
