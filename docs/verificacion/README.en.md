# Verification manual

This manual explains how OpenConex is verified, which published references are used and how to reproduce each result. It is aimed at reviewers and auditors; it does not replace the responsible engineer's review.

The complete list of checks, with equations and clauses, is in the [technical catalog](../tecnico/04-verificaciones.md). This document focuses on **validation evidence** and the **comparison protocol**.

## 1. Method

- The engine works in N, mm and MPa; conversions happen only at the edges through `openconex.units`.
- Every check returns a `CheckResult` with `id`, demand, capacity, ratio, clause and calculation trace.
- Checks run per load combination; the report shows the governing combination.
- Test tolerances are **1 %** unless the reference file states otherwise and explains why.
- Tests run on Windows, macOS and Linux on every pull request.

## 2. Published references

| Reference | Use | Test |
|---|---|---|
| AISC DG1 3rd ed. (2024), 20 examples | Base plates, anchors, pedestal, shear lug, weak base and embedded base | `tests/base_plate/test_dg1_acceptance.py`, `tests/reference/dg1/` |
| Steel Tube Institute (2024), Examples 1 and 2 | Round HSS in compression and rectangular HSS with moment | `tests/base_plate/test_hss_moment.py` |
| AISC Design Examples v16.0/v16.1 | Shear connections | `tests/connections/` |
| AISC Manual 16th ed., Tables 7-6 to 7-14 and 8-3 to 8-11 | Eccentric bolt and weld groups | `tests/kernel/test_*_manual*.py` |
| AISC Manual 16th ed., Table 14-2 | Base plate holes and washers | `tests/test_bolting_and_model.py` |
| ACI 318-19 Chapters 17 and 25 | Anchors, anchor reinforcement, straight and hooked development | `tests/kernel/test_anchors.py`, `tests/base_plate/test_anchor_reinforcement.py` |

Only numerical data is used, with its citation; no text, tables or figures are copied from AISC, ACI or ASCE.

## 3. Coverage

| Family | What is validated | Evidence |
|---|---|---|
| Base plate | Compression, moment, uplift, biaxial bending, pressure models, effective area | DG1 4.7-1 to 4.7-14, B.2 and B.3 |
| Anchors | Steel, breakout, pullout, side-face blowout, shear, interaction, reinforcement | DG1 4.7-3 to 4.7-6 and 4.7-15 |
| Shear lug | Bearing, breakout, local plate bending and weld | DG1 4.7-5 |
| Weak seismic base | Ductile anchors, capacity design and stretch length | DG1 6.4-1 |
| Type I embedded base | Horizontal bearing moment, face plates and horizontal reinforcement | DG1 5.3-1 |
| Shear connections | Bolts, plates, angles, welds, copes and seats | AISC II.A-1A to II.A-19A |
| Bolt and weld groups | Elastic and instantaneous-centre methods | Tables 7-6 to 7-14 and 8-3 to 8-11 |
| Units and languages | Invariance, conversion and ES/EN catalogs | `tests/test_units.py`, `tests/test_i18n.py` |
| Outputs | HTML, DOCX, PDF, DXF, STEP and STL | `tests/outputs/` |

## 4. Cross-comparison

The comparison against commercial software (RAM Connection, RISAConnection or SkyCiv) is documented in `casos.csv`. The file contains 20 base plate cases with their input file and empty columns for the external result.

Protocol:

1. Run the case in OpenConex and record the governing check, demand, capacity and ratio.
2. Enter the same data in the reference program with the same standard, method (LRFD/ASD), units and combinations.
3. Record the external result and the relative difference.
4. If the difference exceeds 1 %, document the cause (rounding, pressure assumption, effective area, development length, etc.).
5. Record the external program version and date.

The comparison **has not been executed yet**; the file is the reproducible template. Until it is completed, the numerical validation is the published-reference evidence in Section 2.

## 5. Known differences

Accepted validation differences are listed in [Pending review](../REVISION-PENDIENTE.md), Section 2.2. The main ones:

- Instantaneous centre of II.A-17A/17B: 3.556 and 4.06 versus 3.54 and 4.07 interpolated.
- II.A-1B: U-shaped block shear instead of L-shaped.
- II.A-12A: bearing length and number of bolts in the example.
- II.A-19A: computed `Z_net` 12.75 in³ versus 12.8 in³ from Table 15-2.
- Seats: elastic formulas reconstructed from Tables 10-6 and 10-8.
- Coped beam with λ > 2λ_p: Eq. 9-12/9-13 without a published example.
- II.A-18: double cope and offset or skewed connections pending.

## 6. Declared limitations

Scope limitations are in [Scope and limitations](../usuario/08-limitaciones.md). In particular:

- Round HSS with moment is rejected; rectangular/square HSS is validated against STI.
- Effective area applies only to I-shapes in concentric compression.
- Type II embedded base is not implemented because DG1 does not present a definitive method.
- The pedestal is not designed as a column and its shear is not checked as an element.
- The plate–shear lug interaction uses an effective width, without finite-element validation.

## 7. Reproduction

```bash
pip install -e ".[dev]"
python -m pytest
ruff check .
```

For the complete outputs:

```bash
pip install -e ".[dev,pdf,3d,gui-test]"
python -m pytest tests/outputs -ra
```

Every file under `tests/` states its reference and tolerance in the docstring. Files in `tests/reference/dg1/` hold the input data and published values.
