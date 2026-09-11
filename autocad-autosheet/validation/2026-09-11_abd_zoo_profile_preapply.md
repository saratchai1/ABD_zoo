# ABD Zoo V12.3 pre-apply validation — 2026-09-11

## Dataset

5 Paper Space layouts:

- NZ1-RSDT-ABD-LA-AF-D100.10
- NZ1-RSDT-ABD-LA-AF-D100.11
- NZ1-RSDT-ABD-LA-AF-D100.12
- NZ1-RSDT-ABD-LA-AF-D100.13
- NZ1-RSDT-ABD-LA-AF-D100.14

## Titlebox profile validation

`AUTOSHEETPROFILECHECK` passed all 5 layouts with exactly one recognized titlebox reference each using profile:

`ABD_ZOO_NTT_A3_V1`

Observed legacy block from diagnostic:

- block name: `NTT ABD_Zoo I`
- insertion: `(0,0,0)`
- bbox: approximately `(0,0,-0.0004) -> (0.4205,0.297,0)`
- X/Y scale: `0.0005`
- attributes: none

## Read-only QA baseline after correct profile recognition

- Layouts: 5
- PASS: 48
- WARN: 0
- FAIL: 42
- Compliance: **53.3%**

This is the preferred pre-apply baseline for report use; the earlier 52.3% scan was produced before the legacy titlebox profile was recognized, so title-related checks were skipped/warned and are not directly comparable.

## Main failures before apply

- title/code/scale typography not yet at Cordia Shx, H=0.0015, W=1.0
- 2 red Paper-space geometry objects per layout
- Canon physical printer instead of `DWG To PDF.pc3`
- current media `A3`, not ISO full bleed A3 target
- custom plot scale not yet `1 mm = 0.001 unit`
- CTB still `SIPHYA_LT_C.ctb`
- D100.10 and D100.12 each reported one floating viewport not on Defpoints in this scan

## Checks already passing before apply

- titlebox recognized
- drawing-code format
- title scale contains A3/A1
- source-path cleanup
- Plot Area = Window
- Center Plot = On
- Plot With Plot Styles = On
- Plot Object Lineweights = On
- Plot Paper Space Last = On

## Safety gate

All five layouts passed `AUTOSHEETPROFILECHECK`, so V12.3 is cleared for the first controlled AUTOSHEET apply on a backup DWG. No automatic save is enabled.
