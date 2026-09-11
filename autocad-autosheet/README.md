# ABD Zoo AUTOSHEET V12 Clean Core

AutoLISP prototype for **pre-plot drawing QA/QC and standardization** in AutoCAD.

This V12 milestone freezes the proven V11/V10 mutation engine and adds a read-only QA layer so the workflow is now:

```text
AUTOSHEETSCAN (read only)
        ↓
Detect drawing/layout issues
        ↓
AUTOSHEET (apply proven rules)
        ↓
AUTOSHEETSCAN AFTER
        ↓
Compliance before/after
```

## Commands

- `AUTOSHEETSCAN` — read-only QA scan of every Paper Space layout.
- `AUTOSHEET` — scan before, apply the proven standardization engine, scan after.
- `AUTOSHEETCTB` — plot-style-only test/set for `SIPHYA_LT_R1.ctb`.
- `AUTOSHEETVERSION` — show current version.

## Current QA checks

Per layout V12 checks:

1. recognized title box
2. drawing-code format (`_` should not remain)
3. A3/A1 title-box scale values
4. drawing-title typography (`Cordia Shx`, H=0.0015, W=1.0 where exposed)
5. drawing-code typography
6. scale typography
7. floating viewport layer (`Defpoints`)
8. remaining red line/polyline geometry
9. visible source/workspace path text
10. plotter (`DWG To PDF.pc3`)
11. A3 landscape media/orientation
12. Plot Area = Window
13. Center Plot = On
14. custom plot scale = `1 mm = 0.001 unit`
15. Plot Style Table = `SIPHYA_LT_R1.ctb`
16. Plot With Plot Styles = On
17. Plot Object Lineweights = On
18. Plot Paper Space Last = On

The scan prints PASS/FAIL by layout and an overall compliance percentage.

## Apply engine retained from live-tested work

The current apply path keeps the rules already tested on ABD Zoo drawings:

- delete unwanted red Paper Space line/polyline geometry
- move floating viewport / MV / VPCLIP support geometry to `Defpoints`
- replace recognized legacy title boxes with the embedded standardized title box
- normalize drawing title, drawing code and scale fields
- change drawing-code underscores to hyphens
- remove visible source/workspace path text
- normalize drawing-area A3/A1 scale layout geometrically
- standardize A3 Landscape plot setup
- force `SIPHYA_LT_R1.ctb` by querying AutoCAD's plot-style list rather than relying on `findfile`

## Safety

- **No automatic save**
- No PDF export
- No batch-folder editing in V12
- Test on a copy/backup DWG first
- Unknown/unrecognized drawing structures should be reviewed before save

## Recommended test workflow

1. Open a fresh copy of a real ABD Zoo DWG.
2. `APPLOAD` `AUTOSHEET_V12_CLEAN_CORE.lsp`.
3. Run `AUTOSHEETVERSION`.
4. Run `AUTOSHEETSCAN` and save the command-line output as the **before** result.
5. Run `AUTOSHEET`.
6. Review the **after** compliance summary.
7. Visually inspect at least 2–3 representative layouts and Plot Preview.
8. Save only after review.

## Engineering-report use

For the cooperative-education report, record at least:

- number of DWGs and layouts tested
- manual processing time vs AUTOSHEET processing time
- compliance before vs after
- remaining warnings/failures
- screenshots of representative before/after cases

## Next milestone after V12 validation

Do not add another one-off patch first. After V12 is validated on multiple drawings, add a **Titlebox Profile System**:

- known profile A/B/C
- rule-based detection
- confidence / match score
- `UNKNOWN → safe skip + warning`

Then add CSV QA report and batch processing only after single-DWG validation is stable.
