# powerbi/datasets: generated exports (do not commit)

This folder receives the output of:

```bash
.venv/bin/python -m powerbi.export_powerbi_datasets
```

That produces one `<table>.csv` and one `<table>.parquet` per Power BI table, plus `manifest.json`. The manifest records row counts, columns and types, the export time and the dataset label.

## Rules

* **The exports are generated locally and are patient-level.** Fact tables hold one row per admission, ICU stay, lab result or prescription, with `subject_id` and `hadm_id`.
* **Never commit them.** `.gitignore` excludes everything in this folder except this README (`powerbi/datasets/*`, `!powerbi/datasets/README.md`), as well as `*.csv`, `*.parquet` and `*.pbix` repository-wide. Do not force-add them.
* **Credentialed MIMIC-IV (`HI_DATASET_MODE=full`).** The PhysioNet Credentialed Health Data Use Agreement covers these files and any `.pbix` built from them. They must never be committed, uploaded, emailed, shared with anyone who is not credentialed, or published (including Power BI "Publish to web"). In that mode the export script prints a warning.
* **Public demo (`mimic-iv-demo-2.2`).** The demo is openly licensed. Even so, keep these files local and regenerate them when needed, so that one workflow stays safe when someone switches to the credentialed data.
* Delete the folder contents when you are done: `rm powerbi/datasets/*.csv powerbi/datasets/*.parquet powerbi/datasets/manifest.json`.
