# Power BI package: Dashboard A

This folder holds everything needed to build the five-page Power BI report, "Dashboard A", on top of the PostgreSQL warehouse. The pages are Executive Overview, Hospital Operations, Patient Outcomes, Clinical Analytics, and SQL & Data Quality.

> **No `.pbix` file is included.** Power BI Desktop was not available in the build environment (macOS), so the report itself was not built. This is an import-ready package plus a step-by-step guide that someone with Power BI Desktop on Windows can follow in under an hour.
>
> The **DAX measures and Power Query M were written to spec but not executed in Power BI.** The validation checklist in `documentation/implementation_guide.md` lists the SQL-computed value for every key measure, so the builder can confirm DAX = SQL. On page 5, the `[KPI Reconciliation Status]` measure runs ten of those checks inside the report.

## Contents

| Path | What it is |
|---|---|
| `export_powerbi_datasets.py` | Exports 23 tables (7 facts, 6 warehouse dimensions, 4 derived slicer dimensions, 4 reporting tables, 2 audit tables) to `datasets/` as CSV and Parquet, plus `manifest.json`. The session is read-only, rows stream in batches, and row counts are self-checked. |
| `datasets/` | Export output. **Git-ignored and generated locally.** See `datasets/README.md`. |
| `measures/measures.dax` | 105 DAX measures in 7 display folders: Volume, LOS, ICU, Outcomes, Readmission, Clinical, Data Quality. Each has a comment giving its definition and denominator. Includes Wilson 95% CIs, `PERCENTILE.INC` LOS percentiles and small-cell-aware display measures. The file runs as-is in DAX query view; its `EVALUATE` returns a validation row. |
| `measures/measures_tabular_editor.csx` | Tabular Editor C# script that creates every measure with its folder, format string and description. Generated from `measures.dax`. |
| `measures/generate_tabular_editor_script.py` | Regenerates the `.csx` file from `measures.dax`. |
| `generate_power_query.py` | Regenerates `documentation/power_query.m` from `manifest.json` and the export SQL. |
| `documentation/power_query.m` | Power Query M: parameters, a loader function, and one query per table. Loads from the CSVs (folder parameter) or directly from PostgreSQL (`PostgreSQL.Database` + `Value.NativeQuery`), with an explicit type on every column. |
| `documentation/data_model.md` | Star schema: tables, grain, keys, the 21 relationships (all `*:1`, single direction, none inactive), relationships you must not create, a Mermaid ER diagram, and filter-flow and fan-out guidance. |
| `documentation/dashboard_spec.md` | Page-by-page spec: ASCII layout grid, and every visual's type, fields, measures, filters, sort and formatting. Also the colour palette with contrast ratios and accessibility notes. |
| `documentation/theme.json` | Power BI report theme (accessible clinical palette). |
| `documentation/implementation_guide.md` | Build steps, publishing, refresh strategy, privacy and the MIMIC DUA, and the **validation checklist** (69 rows of SQL-computed expected values). |

## Quick start

```bash
# from the project root, with the warehouse running
.venv/bin/python -m powerbi.export_powerbi_datasets          # writes powerbi/datasets/
.venv/bin/python -m pytest tests/test_powerbi_export.py -q   # export, row-count and KPI checks
```

Then follow `documentation/implementation_guide.md` on a Windows machine with Power BI Desktop.

To regenerate the derived files after changing measures or the export:

```bash
.venv/bin/python -m powerbi.measures.generate_tabular_editor_script
.venv/bin/python -m powerbi.generate_power_query
```

## What was verified, and what was not

| Verified by running it | Not verified (needs Power BI Desktop) |
|---|---|
| Export script runs. Manifest row counts equal `select count(*)` for every source table. | DAX measures evaluate in Power BI and return the checklist values |
| CSV and Parquet row counts agree. Headers match the manifest. | Power Query M runs, in both CSV and PostgreSQL modes |
| KPIs recomputed in pandas from the exported CSVs match `reporting.rpt_executive_kpis`: patients, admissions, admissions per patient, median LOS, ICU %, mortality %, readmission numerator, denominator and %, and unplanned % | Visual rendering, error bars, field parameter, theme appearance |
| Every relationship key in `data_model.md` is unique on the one side and has no orphans on the many side | Tabular Editor script execution |
| Every `table[column]` referenced in the DAX exists in the export. Every `[measure]` reference resolves. No bare `/` division. | |
| The Wilson CI formula used in the DAX matches SciPy's Wilson interval | |
| `theme.json` parses, and its colours meet WCAG contrast for graphics (3:1) and text (4.5:1) | |
| `power_query.m` declares exactly the exported columns for each table | |

## Data caveats shown in the report

* **ICU-patient cohort.** Every MIMIC-IV demo patient had at least one ICU stay, so rates are not hospital-wide. This caveat is the page 1 subtitle.
* De-identified and date-shifted (years 2110 to 2201). There are no calendar trends.
* Demo scale: 100 patients and 275 admissions. Confidence intervals are wide.
* Readmission rates divide by eligible index admissions (255), not by all admissions.
