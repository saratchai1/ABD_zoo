# AUTOSHEET V12 Validation Plan

## Dataset

Use 5–10 real DWGs, preferably 30+ Paper Space layouts total. Include more than one drawing/layout pattern where available.

## Per-layout checklist

| Check | Before | After | Notes |
|---|---|---|---|
| Title box recognized | | | |
| Drawing code format | | | |
| Drawing title typography | | | |
| Drawing code typography | | | |
| Scale A3/A1 format | | | |
| Viewport on Defpoints | | | |
| Red geometry removed | | | |
| Source path removed | | | |
| A3 Landscape | | | |
| Plotter = DWG To PDF | | | |
| Plot Area = Window | | | |
| Center Plot | | | |
| Plot scale = 1 mm : 0.001 unit | | | |
| CTB = SIPHYA_LT_R1.ctb | | | |
| Plot styles / lineweights / paper last | | | |

## Timing

For each selected DWG record:

- number of layouts
- manual preparation time
- AUTOSHEET runtime + review time
- time reduction (%)

Formula:

```text
Time reduction (%) = (Manual time - Auto time) / Manual time × 100
```

## Acceptance target for freezing V12

- no destructive error in the test set
- no automatic save
- plot settings verified on representative layouts
- title-box values remain readable/correct
- compliance after AUTOSHEET materially exceeds compliance before
- failures are logged and reproducible rather than silently ignored
