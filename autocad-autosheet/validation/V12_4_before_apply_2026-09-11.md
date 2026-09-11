# AUTOSHEET V12.4 Before-Apply Validation — 2026-09-11

Source branch: `feat/autosheet-v12-clean-core`

## Frame safety

`AUTOSHEETFRAMECHECK` passed on all five layouts. Each layout had exactly one recognized `NTT ABD_Zoo I` full-sheet frame and `ABD-Zoo-frame=YES`.

## Read-only QA baseline

Layouts: 5

- PASS: 49
- WARN: 0
- FAIL: 41
- Compliance: 54.4%
- Result: REVIEW / APPLY AUTOSHEET

## Per-layout summary

- D100.10: pass 10 / fail 8
- D100.11: pass 10 / fail 8
- D100.12: pass 9 / fail 9
- D100.13: pass 10 / fail 8
- D100.14: pass 10 / fail 8

## Observed failures before apply

Common to all five layouts:

- Title typography not yet standardized
- Code typography not yet standardized
- Scale typography not yet standardized
- 2 red Paper-space geometry objects remain
- Plotter is `Canon iR-ADV C5235/5240 UFR II`
- Paper/media is `A3`, not the requested full-bleed PDF setup
- Plot custom scale is not yet `1 mm = 0.001 unit`
- Plot style is `SIPHYA_LT_C.ctb`, not `SIPHYA_LT_R1.ctb`

Additional:

- D100.12 has 1 floating viewport not on `Defpoints`

## Passed preconditions

- ABD Zoo sheet-frame profile recognized on all layouts
- Drawing code already in hyphen format
- Title scale already contains A3/A1 format
- Source-path cleanup already passes
- Plot area = Window
- Center plot = On
- Plot with styles = On
- Lineweights = On
- Paper space last = On

## Next test

Run `AUTOSHEET` on an untouched backup DWG using V12.4, then verify:

1. `NTT ABD_Zoo I` frame still exists on every layout.
2. No titlebox/frame geometry disappears.
3. Remaining QA failures are reduced after apply.
4. Plot Preview is visually correct before any save.

Do not save the DWG until visual review is complete.
